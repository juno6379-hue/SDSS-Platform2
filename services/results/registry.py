"""Store result snapshots and their independent, append-only reviews."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

EVIDENCE_STATES = frozenset(
    {"VERIFIED_REAL", "TESTED_SYNTHETIC", "IMPLEMENTED_UNVERIFIED", "BLOCKED", "PLANNED"}
)
REVIEW_DECISIONS = frozenset({"ACCEPTED", "CHANGES_REQUESTED"})
REVIEW_STATES = REVIEW_DECISIONS | {"PENDING"}
DOMAIN = re.compile(r"[a-z][a-z0-9_-]{0,63}")
DIGEST = re.compile(r"[0-9a-f]{64}")
SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS results (
        id TEXT PRIMARY KEY NOT NULL,
        domain TEXT NOT NULL,
        source_key TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (domain, source_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS result_reviews (
        result_id TEXT NOT NULL REFERENCES results(id),
        revision INTEGER NOT NULL CHECK (revision > 0),
        decision TEXT NOT NULL CHECK (decision IN ('ACCEPTED', 'CHANGES_REQUESTED')),
        reviewer TEXT NOT NULL,
        note TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (result_id, revision)
    )
    """,
    "CREATE INDEX IF NOT EXISTS results_created ON results(created_at DESC, id)",
    """
    CREATE TABLE IF NOT EXISTS result_packages (
        result_id TEXT PRIMARY KEY REFERENCES results(id),
        sha256 TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS result_decisions (
        result_id TEXT NOT NULL REFERENCES result_packages(result_id),
        axis TEXT NOT NULL CHECK(axis IN ('scientific', 'publication')),
        revision INTEGER NOT NULL CHECK(revision > 0),
        decision TEXT NOT NULL CHECK(decision IN ('APPROVED', 'REJECTED')),
        actor TEXT NOT NULL,
        evidence TEXT NOT NULL,
        note TEXT NOT NULL,
        scientific_revision INTEGER,
        created_at TEXT NOT NULL,
        PRIMARY KEY(result_id, axis, revision)
    )
    """,
)


class RegistryError(ValueError):
    """Public error code for an invalid, conflicting, or unavailable result."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _json(value) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _text(value, max_length, *, optional=False):
    if not isinstance(value, str) or len(value) > max_length or "\x00" in value:
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return optional or bool(value.strip())


def _matches(pattern, value):
    return isinstance(value, str) and bool(pattern.fullmatch(value))


def _validate_evidence(entry):
    if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "bytes"}:
        return False
    path = entry["path"]
    return (
        _text(path, 1024)
        and not any(character in path for character in ("\\", ":", "?", "*", "|", "<", ">"))
        and not any(ord(character) < 32 for character in path)
        and all(part.strip() and part.rstrip(" .") == part for part in path.split("/"))
        and _matches(DIGEST, entry["sha256"])
        and type(entry["bytes"]) is int
        and entry["bytes"] >= 0
    )


class ResultRegistry:
    """Use a versioned result per domain/source key and a revision per decision."""

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise RegistryError("REGISTRY_UNAVAILABLE") from error
        with self._transaction(write=True) as conn:
            for statement in SCHEMA:
                conn.execute(statement)

    @contextmanager
    def _transaction(self, *, write=False):
        try:
            with closing(sqlite3.connect(self.path, timeout=10.0)) as conn, conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                yield conn
        except sqlite3.Error as error:
            raise RegistryError("REGISTRY_UNAVAILABLE") from error

    @staticmethod
    def _row(conn, result_id):
        row = conn.execute("SELECT * FROM results WHERE id = ?", (result_id,)).fetchone()
        if row is None:
            raise RegistryError("RESULT_NOT_FOUND")
        return row

    @staticmethod
    def _materialize(conn, row):
        reviews = [
            dict(review)
            for review in conn.execute(
                """
                SELECT revision, decision, reviewer, note, created_at
                FROM result_reviews WHERE result_id = ? ORDER BY revision
                """,
                (row["id"],),
            )
        ]
        latest = reviews[-1] if reviews else None
        return {
            **json.loads(row["payload"]),
            "id": row["id"],
            "created_at": row["created_at"],
            "review_status": latest["decision"] if latest else "PENDING",
            "revision": latest["revision"] if latest else 0,
            "reviews": reviews,
        }

    def register(self, *, domain, source_key, title, evidence_status, summary, evidence, blockers):
        if (
            not _matches(DOMAIN, domain)
            or not _text(source_key, 512)
            or not _text(title, 240)
            or not isinstance(evidence_status, str)
            or evidence_status not in EVIDENCE_STATES
            or not isinstance(summary, (str, dict))
            or not isinstance(evidence, (list, tuple))
            or not all(_validate_evidence(entry) for entry in evidence)
            or not isinstance(blockers, (list, tuple))
            or not all(_text(blocker, 1000) for blocker in blockers)
        ):
            raise RegistryError("RESULT_VALIDATION_ERROR")
        try:
            payload = _json(
                dict(
                    domain=domain,
                    source_key=source_key,
                    title=title,
                    evidence_status=evidence_status,
                    summary=summary,
                    evidence=evidence,
                    blockers=blockers,
                )
            )
            result_id = hashlib.sha256(_json([domain, source_key]).encode("utf-8")).hexdigest()
            payload.encode("utf-8")
        except (TypeError, ValueError, RecursionError) as error:
            raise RegistryError("RESULT_VALIDATION_ERROR") from error
        with self._transaction(write=True) as conn:
            conn.execute(
                """
                INSERT INTO results (id, domain, source_key, payload, created_at)
                VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING
                """,
                (result_id, domain, source_key, payload, _timestamp()),
            )
            row = self._row(conn, result_id)
            if row["payload"] != payload:
                raise RegistryError("RESULT_CONFLICT")
            return self._materialize(conn, row)

    def list_results(self, *, limit=50, domain=None, review_status=None):
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or (domain is not None and not _matches(DOMAIN, domain))
            or (
                review_status is not None
                and (not isinstance(review_status, str) or review_status not in REVIEW_STATES)
            )
        ):
            raise RegistryError("RESULT_VALIDATION_ERROR")
        with self._transaction() as conn:
            rows = conn.execute(
                """
                SELECT r.* FROM results AS r
                WHERE (? IS NULL OR r.domain = ?)
                    AND (? IS NULL OR COALESCE((
                        SELECT rr.decision FROM result_reviews AS rr
                        WHERE rr.result_id = r.id ORDER BY rr.revision DESC LIMIT 1
                    ), 'PENDING') = ?)
                ORDER BY r.created_at DESC, r.id
                LIMIT ?
                """,
                (domain, domain, review_status, review_status, limit),
            ).fetchall()
            return [self._materialize(conn, row) for row in rows]

    def get(self, result_id):
        if not _matches(DIGEST, result_id):
            raise RegistryError("RESULT_NOT_FOUND")
        with self._transaction() as conn:
            return self._materialize(conn, self._row(conn, result_id))

    def attach_package(self, result_id, package):
        with self._transaction(write=True) as conn:
            self._row(conn, result_id)
            payload = _json(package)
            digest = hashlib.sha256(payload.encode()).hexdigest()
            conn.execute(
                "INSERT INTO result_packages VALUES (?, ?, ?) ON CONFLICT(result_id) DO NOTHING",
                (result_id, digest, payload),
            )
            row = conn.execute(
                "SELECT sha256, payload FROM result_packages WHERE result_id = ?", (result_id,)
            ).fetchone()
            if row["sha256"] != digest or row["payload"] != payload:
                raise RegistryError("PACKAGE_CONFLICT")
            return digest

    @staticmethod
    def _catalog_snapshot(conn, result_id):
        package = conn.execute(
            "SELECT sha256, payload FROM result_packages WHERE result_id = ?", (result_id,)
        ).fetchone()
        if (
            package is not None
            and hashlib.sha256(package["payload"].encode()).hexdigest() != package["sha256"]
        ):
            raise RegistryError("PACKAGE_DIGEST_INVALID")
        axes = {
            axis: {"status": "PENDING", "revision": 0, "history": []}
            for axis in ("scientific", "publication")
        }
        for row in conn.execute(
            "SELECT * FROM result_decisions WHERE result_id = ? ORDER BY axis, revision",
            (result_id,),
        ):
            event = dict(row)
            axis = axes[event.pop("axis")]
            event["evidence"] = json.loads(event["evidence"])
            axis["history"].append(event)
            axis.update(status=event["decision"], revision=event["revision"])
        science, publication = axes["scientific"], axes["publication"]
        axes["release_eligible"] = (
            science["status"] == publication["status"] == "APPROVED"
            and publication["history"][-1]["scientific_revision"] == science["revision"]
        )
        return {
            "result_id": result_id,
            "status": "CATALOG_READY" if package else "CATALOG_PENDING",
            "package_sha256": package["sha256"] if package else None,
            "package": json.loads(package["payload"]) if package else None,
            "governance": axes,
        }

    def catalog_entry(self, result_id):
        with self._transaction() as conn:
            self._row(conn, result_id)
            return self._catalog_snapshot(conn, result_id)

    def record_decision(
        self, result_id, *, axis, decision, actor, note, evidence, expected_revision, package_sha256
    ):
        if (
            axis not in {"scientific", "publication"}
            or decision not in {"APPROVED", "REJECTED"}
            or not _text(actor, 128)
            or not _text(note, 2000)
            or not _validate_evidence(evidence)
            or type(expected_revision) is not int
            or expected_revision < 0
            or not _matches(DIGEST, package_sha256)
        ):
            raise RegistryError("DECISION_VALIDATION_ERROR")
        with self._transaction(write=True) as conn:
            self._row(conn, result_id)
            entry = self._catalog_snapshot(conn, result_id)
            if entry["package_sha256"] != package_sha256:
                raise RegistryError("PACKAGE_CONFLICT")
            state = entry["governance"][axis]
            if expected_revision < state["revision"]:
                event = state["history"][expected_revision]
                if (event["decision"], event["actor"], event["note"], event["evidence"]) == (
                    decision,
                    actor,
                    note,
                    evidence,
                ):
                    return entry
            if state["revision"] != expected_revision:
                raise RegistryError("DECISION_CONFLICT")
            science = entry["governance"]["scientific"]
            science_revision = None
            if decision == "APPROVED" and axis == "publication":
                if science["status"] != "APPROVED":
                    raise RegistryError("SCIENTIFIC_APPROVAL_REQUIRED")
                if not entry["package"]["quality"]["publication_inputs_complete"]:
                    raise RegistryError("PUBLICATION_INPUTS_INCOMPLETE")
                science_revision = science["revision"]
            conn.execute(
                "INSERT INTO result_decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result_id,
                    axis,
                    expected_revision + 1,
                    decision,
                    actor,
                    _json(evidence),
                    note,
                    science_revision,
                    _timestamp(),
                ),
            )
            return self._catalog_snapshot(conn, result_id)

    def review(self, result_id, *, decision, reviewer, note, expected_revision):
        if not _matches(DIGEST, result_id):
            raise RegistryError("RESULT_NOT_FOUND")
        if (
            not isinstance(decision, str)
            or decision not in REVIEW_DECISIONS
            or not _text(reviewer, 128)
            or not _text(note, 4000, optional=True)
            or type(expected_revision) is not int
            or expected_revision < 0
        ):
            raise RegistryError("REVIEW_VALIDATION_ERROR")
        content = (decision, reviewer, note)
        with self._transaction(write=True) as conn:
            row = self._row(conn, result_id)
            result = self._materialize(conn, row)
            if expected_revision < result["revision"]:
                event = result["reviews"][expected_revision]
                if content == (event["decision"], event["reviewer"], event["note"]):
                    return result
                raise RegistryError("REVIEW_CONFLICT")
            if expected_revision != result["revision"]:
                raise RegistryError("REVIEW_CONFLICT")
            conn.execute(
                """
                INSERT INTO result_reviews (result_id, revision, decision, reviewer, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (result_id, expected_revision + 1, *content, _timestamp()),
            )
            return self._materialize(conn, row)
