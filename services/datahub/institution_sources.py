"""기관 자료의 읽기 전용 인계 API. 원본 보존과 공개 승인은 별도 Gate다."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

COLLECTION_IDS = {
    "rtrw": "rtrw",
    "cckp": "cckp",
    "klhk": "klhk",
    "private_index": "documents",
    "sentinel": "sentinel",
    "lake": None,
}

SOURCES = {
    "rtrw": ("evidence/rtrw-20261125/source-candidates.json", "CURRENT_VECTOR_NOT_VERIFIED"),
    "cckp": (
        "evidence/cckp_indonesia/numeric-result-validated.json",
        "COUNTRY_POLYGON_AND_CATALOG_SCOPE_INCOMPLETE",
    ),
    "lake": ("evidence/data_lake/local-handoff-20261125.json", "LIVE_SERVICE_CUTOVER_UNVERIFIED"),
    "klhk": (
        "evidence/klhk_rag/verification-20261124.json",
        "NATIVE_23_DOMAIN_AND_REUSE_RIGHTS_UNVERIFIED",
    ),
    "private_index": (
        "evidence/vectorstore/climate-report-index-pinned.json",
        "PRIVATE_ACL_AND_EMBEDDING_APPROVAL_PENDING",
    ),
    "sentinel": (
        "evidence/onemap_sentinel/coverage-batches/20261125-pass01/progress.json",
        "UNSETTLED_TRANSFER_AND_SPATIAL_GAP",
    ),
}


def _inside(root: Path, relative: str) -> Path:
    """입력 파일은 지정 저장소 내부로 제한한다. junction·symlink도 resolve한다."""
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("EVIDENCE_PATH_OUTSIDE_ROOT")
    return path


def pin_file(root: Path, relative: str, expected_sha256: str | None = None) -> dict:
    path = _inside(root, relative)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    actual = digest.hexdigest()
    if expected_sha256 is not None and actual != expected_sha256:
        raise ValueError("EVIDENCE_SHA_MISMATCH")
    return {"path": relative, "sha256": actual, "bytes": path.stat().st_size}


def _read(root: Path, relative: str) -> tuple[dict, dict]:
    path = _inside(root, relative)
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("EVIDENCE_JSON_TOO_LARGE")
    body = path.read_bytes()
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("EVIDENCE_JSON_NOT_OBJECT")
    return data, {"path": relative, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def build_inventory(root: str | Path) -> dict:
    """로컬 증거를 검증한다. 다운로드·예약·공개 승인·수집 복구는 수행하지 않는다."""
    root = Path(root)
    records = []
    for source_id, (relative, blocker) in SOURCES.items():
        row = {
            "source_id": source_id,
            "verification": "BLOCKED",
            "publication_gate": "BLOCKED",
            "public_search_enabled": False,
            "verification_scope": "LOCAL_EVIDENCE_BYTES_NOT_AUTHORITY_APPROVAL",
            "blockers": [blocker],
            "evidence_pins": [],
        }
        try:
            data, pin = _read(root, relative)
            row["evidence_pins"].append(pin)
            row["verification"] = "VERIFIED_REAL"
            if source_id == "rtrw":
                row["metrics"] = {
                    k: data.get(k)
                    for k in ("current_verified_provinces", "historical_feature_count")
                }
            elif source_id == "cckp":
                provenance = data["provenance"]
                row["evidence_pins"].append(
                    pin_file(
                        root, "evidence/cckp_indonesia/global-asset.nc", provenance["raw_sha256"]
                    )
                )
                row["metrics"] = {
                    k: data.get(k)
                    for k in (
                        "value",
                        "unit",
                        "valid_cells",
                        "geography_is_official_country_polygon",
                    )
                }
            elif source_id == "lake":
                catalog = data["catalog"]
                row["evidence_pins"].append(pin_file(root, catalog["path"], catalog["sha256"]))
                row["metrics"] = {
                    k: data.get(k)
                    for k in (
                        "catalog_object_count",
                        "catalog_reference_count",
                        "live_postgis_or_object_service_cutover",
                    )
                }
            elif source_id == "private_index":
                # 레거시 절대 경로는 정규화한 뒤 저장소 내부 여부를 다시 검사한다.
                database = Path(data["database_path"].replace("\\\\", "\\"))
                resolved = database.resolve()
                if resolved.is_relative_to(root.resolve()):
                    relative_db = resolved.relative_to(root.resolve()).as_posix()
                else:
                    # A committed receipt may name the Windows capture root when replayed in Linux.
                    portable = ("data", "curated", "vector", "climate_reports_pinned.sqlite3")
                    if PureWindowsPath(str(database)).parts[-4:] != portable:
                        raise ValueError("PRIVATE_INDEX_RECEIPT_PATH_INVALID")
                    relative_db = "/".join(portable)
                row["evidence_pins"].append(pin_file(root, relative_db, data["database_sha256"]))
                row["metrics"] = {
                    k: data.get(k)
                    for k in (
                        "document_count",
                        "chunk_count",
                        "embedding_quality_verified",
                        "public_search_enabled",
                    )
                }
                row["visibility"] = "private"
            elif source_id == "klhk":
                docs = data.get("acquired_documents", [])
                row["metrics"] = {
                    "acquired_metadata_documents": len(docs),
                    "verified_native_23": sum(d.get("native_23_verified") is True for d in docs),
                }
            else:
                row["metrics"] = {
                    k: data.get(k)
                    for k in (
                        "completed_windows",
                        "quality_passing_windows",
                        "charged_bytes",
                        "remaining_bytes",
                        "active",
                        "updated_at",
                    )
                }
                row["process_status"] = "NOT_PROBED_DO_NOT_INFER_FROM_RUNNING_FILE"
                row["coverage_reaudit_completed"] = False
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            row["verification"] = "BLOCKED"
            row["blockers"].append(type(exc).__name__)
        records.append(row)
    return {
        "schema_version": "institution-source-handoff/1.0",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "remote_requests": 0,
        "ledger_writes": 0,
        "scope": "LOCAL_READ_ONLY_EVIDENCE_NOT_INSTITUTIONAL_APPROVAL",
    }


def public_summary(inventory: dict) -> dict:
    """공개용 상태만 whitelist한다. 비공개 DB 경로·본문·수치·권한은 전달하지 않는다."""
    return {
        "schema_version": inventory["schema_version"],
        "sources": [
            {
                "source_id": row["source_id"],
                "verification": row["verification"],
                "publication_gate": "BLOCKED",
                "public_search_enabled": False,
                "collection_progress_ref": {
                    "endpoint": "/api/collection-progress",
                    "dataset_id": COLLECTION_IDS.get(row["source_id"]),
                },
            }
            for row in inventory["records"]
        ],
    }
