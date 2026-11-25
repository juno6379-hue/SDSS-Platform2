"""Local durable submission, state and cancellation journal."""

import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .contracts import Approval, JobError, Pin, digest

FINAL = ("SUCCEEDED", "FAILED", "CANCELLED")
JOB_ID_PATTERN = re.compile(r"j-[a-f0-9]{60}")


class JobStore:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "queue.sqlite3"
        with self.transaction(write=True) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, approval TEXT NOT NULL, approval_pin TEXT NOT NULL,
                    provider_fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                    cancel_requested INTEGER NOT NULL DEFAULT 0, remote_started INTEGER NOT NULL DEFAULT 0,
                    result_id TEXT, package_sha256 TEXT, blocker TEXT, model_release TEXT,
                    failures INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
            """)
            if "model_release" not in {
                row["name"] for row in conn.execute("PRAGMA table_info(jobs)")
            }:
                conn.execute("ALTER TABLE jobs ADD COLUMN model_release TEXT")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
                    at TEXT NOT NULL, state TEXT NOT NULL, progress INTEGER NOT NULL, blocker TEXT
                )
            """)

    @contextmanager
    def transaction(self, *, write=False):
        conn = sqlite3.connect(self.database, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                yield conn
        finally:
            conn.close()

    @contextmanager
    def worker_lock(self):
        # The operating system releases this lock when a worker dies, including hard exits.
        conn = sqlite3.connect(self.directory / "worker-lock.sqlite3", timeout=0)
        try:
            try:
                conn.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as error:
                if error.sqlite_errorcode == sqlite3.SQLITE_BUSY:
                    raise JobError("JOB_WORKER_BUSY") from error
                raise
            yield
        finally:
            conn.close()

    @staticmethod
    def row(conn, job_id):
        if not JOB_ID_PATTERN.fullmatch(job_id):
            raise JobError("JOB_NOT_FOUND")
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise JobError("JOB_NOT_FOUND")
        return row

    @staticmethod
    def public(row):
        approval = Approval.model_validate_json(row["approval"])
        return {
            "id": row["id"],
            "approval_id": approval.approval_id,
            "provider": approval.provider,
            "operation": approval.operation,
            "model": approval.model.model_dump(),
            "state": row["state"],
            "progress": row["progress"],
            "cancel_requested": bool(row["cancel_requested"]),
            "result_id": row["result_id"],
            "package_sha256": row["package_sha256"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "blockers": [row["blocker"]] if row["blocker"] else [],
        }

    @staticmethod
    def event(conn, row):
        conn.execute(
            "INSERT INTO job_events(job_id,at,state,progress,blocker) VALUES (?,?,?,?,?)",
            (row["id"], row["updated_at"], row["state"], row["progress"], row["blocker"]),
        )

    def submit(self, approval, pin: Pin, provider_fingerprint):
        job_id = "j-" + digest([approval.approval_id, pin.sha256, provider_fingerprint])[:60]
        now = datetime.now(UTC).isoformat()
        with self.transaction(write=True) as conn:
            inserted = conn.execute(
                """INSERT OR IGNORE INTO jobs
                (id, approval, approval_pin, provider_fingerprint, state, created_at, updated_at)
                VALUES (?,?,?,?,'QUEUED',?,?)""",
                (
                    job_id,
                    approval.model_dump_json(),
                    pin.model_dump_json(),
                    provider_fingerprint,
                    now,
                    now,
                ),
            )
            row = self.row(conn, job_id)
            if inserted.rowcount:
                self.event(conn, row)
            return self.public(row)

    def get(self, job_id):
        with self.transaction() as conn:
            return dict(self.row(conn, job_id))

    def list(self, limit):
        with self.transaction() as conn:
            return [
                self.public(row)
                for row in conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
                )
            ]

    def pending_ids(self, limit):
        with self.transaction() as conn:
            return [
                row["id"]
                for row in conn.execute(
                    """SELECT id FROM jobs WHERE state NOT IN ('SUCCEEDED','FAILED','CANCELLED')
                   ORDER BY updated_at, id LIMIT ?""",
                    (limit,),
                )
            ]

    def update(
        self,
        job_id,
        *,
        state,
        progress=None,
        blocker=None,
        result=None,
        failure=False,
        mark_remote=False,
        model_release=None,
    ):
        with self.transaction(write=True) as conn:
            row = self.row(conn, job_id)
            if row["state"] in FINAL:
                return dict(row)
            if state is None:
                state = "CANCELLING" if row["cancel_requested"] else "FAILED"
            if row["cancel_requested"] and state in {"RUNNING", "FINALIZING"}:
                state = "CANCELLING"
            if state == "CANCELLING" and not row["remote_started"]:
                state = "CANCELLED"
            result_id, package_sha = result if result else (row["result_id"], row["package_sha256"])
            conn.execute(
                """UPDATE jobs SET state=?, progress=?, blocker=?, result_id=?, package_sha256=?,
                   failures=?, remote_started=?, model_release=?, updated_at=? WHERE id=?""",
                (
                    state,
                    row["progress"] if progress is None else max(progress, row["progress"]),
                    blocker,
                    result_id,
                    package_sha,
                    row["failures"] if failure is None else row["failures"] + 1 if failure else 0,
                    int(row["remote_started"] or (mark_remote and state == "RUNNING")),
                    model_release
                    if mark_remote and state == "RUNNING" and model_release
                    else row["model_release"],
                    datetime.now(UTC).isoformat(),
                    job_id,
                ),
            )
            updated = self.row(conn, job_id)
            if any(updated[name] != row[name] for name in ("state", "progress", "blocker")):
                self.event(conn, updated)
            return dict(updated)

    def fail(self, job_id, blocker):
        return self.update(job_id, state=None, blocker=blocker, failure=True)

    def cancel(self, job_id):
        with self.transaction(write=True) as conn:
            row = self.row(conn, job_id)
            if row["state"] == "CANCELLED" or row["cancel_requested"]:
                return self.public(row)
            if row["state"] in {"SUCCEEDED", "FINALIZING"} or (
                row["state"] == "FAILED" and not row["remote_started"]
            ):
                raise JobError("JOB_CANCELLATION_CONFLICT")
            state = "CANCELLING" if row["remote_started"] else "CANCELLED"
            conn.execute(
                "UPDATE jobs SET cancel_requested=1,state=?,updated_at=?,blocker=NULL WHERE id=?",
                (state, datetime.now(UTC).isoformat(), job_id),
            )
            updated = self.row(conn, job_id)
            self.event(conn, updated)
            return self.public(updated)

    def events(self, job_id):
        with self.transaction() as conn:
            self.row(conn, job_id)
            return [
                dict(row)
                for row in reversed(
                    conn.execute(
                        "SELECT at,state,progress,blocker FROM job_events WHERE job_id=? ORDER BY id DESC LIMIT 100",
                        (job_id,),
                    ).fetchall()
                )
            ]
