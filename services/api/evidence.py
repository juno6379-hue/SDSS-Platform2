"""검토 시 고정한 SHA와 검사 유효기간을 매 요청마다 확인한다."""

import argparse
import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).parent
LOCK_PATH = DIRECTORY / "evidence-lock-v2.json"
GROUPS = {
    "cckp": [
        "evidence/cckp_indonesia/" + name
        for name in (
            "global-asset.nc",
            "raw-receipt.json",
            "receipt-seal.json",
            "license-evidence.json",
            "numeric-result-validated.json",
            "query-request.json",
            "evidence-manifest.json",
        )
    ],
    "klhk": [
        "evidence/klhk_rag/verification-20261124.json",
        "evidence/klhk_rag/live-20261124-1/summary.json",
        "evidence/klhk_rag/dictionary-20261124-bounded-retry/summary.json",
    ],
    "sentinel": [
        "evidence/onemap_sentinel/" + name
        for name in (
            "handoff-summary-20261124.json",
            "held-audit-20261124/completeness.json",
            "migration-receipt-20261124.json",
            "post-migration-state-20261124.json",
            "pilot-unit-20261124/run-01/result.json",
            "pilot-unit-20261124/final-state.json",
            "pilot-unit-20261124/postflight-integrity.json",
            "post-pilot-reaudit.json",
        )
    ],
    "models": ["evidence/models/readiness.json", "evidence/models/legacy-checkpoint-audit.json"],
    "vector": [
        "data/curated/vector/climate_reports_pinned.sqlite3",
        "evidence/vectorstore/climate-report-index-pinned.json",
        "services/vectorstore/pgvector_schema.sql",
    ],
    "workflow": ["evidence/workflows/current-state.json"],
}


class EvidenceBlocked(ValueError):
    pass


class EvidenceStore:
    def __init__(self, root, lock_path, expected_sha, clock=None):
        self.root, self.lock_path, self.expected_sha = (
            Path(root).resolve(),
            Path(lock_path),
            expected_sha,
        )
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def safe_path(self, name):
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root):
            raise EvidenceBlocked("EVIDENCE_PATH_OUTSIDE_ROOT")
        return path

    def _lock(self):
        try:
            raw = self.lock_path.read_bytes()
            if len(raw) > 2 * 1024 * 1024 or sha256(raw).hexdigest() != self.expected_sha:
                raise EvidenceBlocked("EVIDENCE_LOCK_SHA_MISMATCH")
            lock = json.loads(raw)
            captured = datetime.fromisoformat(lock["reviewed_at"])
            if (
                captured.tzinfo is None
                or self.clock() < captured
                or self.clock() > captured + timedelta(days=lock["valid_days"])
            ):
                raise EvidenceBlocked("EVIDENCE_REVIEW_STALE_OR_FUTURE")
            return lock
        except EvidenceBlocked:
            raise
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise EvidenceBlocked("EVIDENCE_LOCK_MISSING_OR_INVALID") from error

    def check(self, group):
        lock = self._lock()
        entry = lock.get("groups", {}).get(group)
        if not entry or entry.get("missing") or not entry.get("files"):
            raise EvidenceBlocked("EVIDENCE_SOURCE_MISSING:" + group)
        for name, pin in entry["files"].items():
            path = self.safe_path(name)
            if (
                not path.is_file()
                or path.stat().st_size != pin["bytes"]
                or pin["bytes"] > 32 * 1024 * 1024
            ):
                raise EvidenceBlocked("EVIDENCE_MISSING_OR_SIZE_DRIFT:" + name)
            if sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
                raise EvidenceBlocked("EVIDENCE_SHA_DRIFT:" + name)
        return {
            "status": "VERIFIED_REAL",
            "group": group,
            "reviewed_at": lock["reviewed_at"],
            "lock_sha256": self.expected_sha,
            "files_verified": len(entry["files"]),
            "meaning": "고정 evidence 스냅샷 무결성; 현재 제공처 가용성과 별도",
        }

    def read_json(self, group, name, *, max_bytes=2 * 1024 * 1024):
        proof = self.check(group)
        lock = self._lock()
        if name not in lock["groups"][group]["files"]:
            raise EvidenceBlocked("UNPINNED_EVIDENCE_FILE")
        path = self.safe_path(name)
        if path.stat().st_size > max_bytes:
            raise EvidenceBlocked("JSON_EVIDENCE_TOO_LARGE")
        try:
            raw = path.read_bytes()
            if sha256(raw).hexdigest() != lock["groups"][group]["files"][name]["sha256"]:
                raise EvidenceBlocked("EVIDENCE_CHANGED_DURING_READ")
            return json.loads(raw), proof
        except (ValueError, OSError) as error:
            raise EvidenceBlocked("EVIDENCE_JSON_INVALID") from error


def pin():
    """명시적 로컬 검토 시에만 pin을 갱신한다. 앱 시작 때 자동 실행하지 않는다."""
    groups = {}
    for group, names in GROUPS.items():
        names = list(names)
        if group == "klhk":
            for receipt_path in (ROOT / "evidence/klhk_rag/live-20261124-1/raw").glob(
                "*.receipt.json"
            ):
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                raw = Path(receipt["raw_path"]).resolve()
                if not raw.is_relative_to(ROOT):
                    raise ValueError("RAW_OUTSIDE_PROJECT")
                names.extend(
                    [receipt_path.relative_to(ROOT).as_posix(), raw.relative_to(ROOT).as_posix()]
                )
        files = {}
        missing = []
        for name in names:
            path = ROOT / name
            if not path.is_file():
                missing.append(name)
                continue
            files[name] = {
                "bytes": path.stat().st_size,
                "sha256": sha256(path.read_bytes()).hexdigest(),
            }
        groups[group] = {"files": files, "missing": missing}
    lock = {
        "schema_version": "api-evidence-lock/1",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "valid_days": 7,
        "groups": groups,
        "note": "manual local integrity snapshot; licensing/authority readiness separate",
    }
    raw = json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True).encode()
    LOCK_PATH.write_bytes(raw)
    (DIRECTORY / "pinned.py").write_text(
        "# 검토된 evidence lock. 갱신은 명시적 pin 명령만 사용한다.\nLOCK_SHA256 = "
        + repr(sha256(raw).hexdigest())
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "lock_sha256": sha256(raw).hexdigest(),
                "groups": {
                    g: {"files": len(v["files"]), "missing": v["missing"]}
                    for g, v in groups.items()
                },
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pin-reviewed", action="store_true")
    args = parser.parse_args()
    if not args.pin_reviewed:
        parser.error("검토 후 --pin-reviewed 필요")
    pin()
