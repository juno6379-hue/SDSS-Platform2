"""기존 CCKP host/목록/ETag bounded primitive를 사용하는 단일 global-grid 취득."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from services.datahub.connectors.cckp.source import (
    ENDPOINT,
    CckpError,
    S3Transport,
    head_object,
    inventory_from_dict,
)

CAP = 64 * 1024**2
LICENSE_URI = "https://datacatalog.worldbank.org/search/dataset/0065626/climate-change-knowledge-portal-observed-climate-data-era5-0-25-degree"


def _write_new(path: Path, value: dict):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024**2), b""):
            h.update(chunk)
    return h.hexdigest()


def _update_state(path, value):
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def fetch_one_listed_global(
    listing_path, output_dir, *, execute=False, transport=None, reviewed_range_retry=False
):
    """국가 prefix를 위조하지 않는다. global 원본과 국가 bbox 파생물을 분리한다."""
    if Path(listing_path).stat().st_size > 2 * 1024**2:
        raise CckpError("LISTING_FILE_TOO_LARGE")
    listing_raw = Path(listing_path).read_bytes()
    if len(listing_raw) > 2 * 1024**2:
        raise CckpError("LISTING_FILE_TOO_LARGE")
    payload = json.loads(listing_raw)
    listing = inventory_from_dict(payload.get("inventory", payload))
    candidates = [obj for obj in listing.objects if obj.key.endswith(".nc") and 0 < obj.size <= CAP]
    if not candidates:
        raise CckpError("NO_LISTED_SMALL_NETCDF")
    selected = sorted(candidates, key=lambda obj: (obj.size, obj.key))[0]
    # 이번 bounded 실증은 이미 확인한 ERA5 collection만 허용한다.
    if not selected.key.startswith("data/era5-x0.25/"):
        raise CckpError("GLOBAL_COLLECTION_NOT_REVIEWED")
    root = Path(output_dir)
    if root.is_symlink():
        raise CckpError("OUTPUT_SYMLINK_NOT_ALLOWED")
    plan = {
        "schema_version": "cckp-global-grid-one/1.0",
        "scope": "GLOBAL_GRID_NOT_COUNTRY_OBJECT",
        "key": selected.key,
        "size": selected.size,
        "etag": selected.etag,
        "inventory_id": listing.inventory_id,
        "inventory_sha256": listing.response_sha256,
        "listing_file_sha256": hashlib.sha256(listing_raw).hexdigest(),
        "max_files": 1,
        "max_bytes": CAP,
        "license": "CC-BY-4.0",
        "license_source_uri": LICENSE_URI,
    }
    plan_id = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    plan["plan_id"] = plan_id
    if not execute:
        return {"status": "PLANNED", "plan": plan, "download_executed": False}
    root.mkdir(parents=True, exist_ok=True)
    raw = root / "global-asset.nc"
    receipt_path = root / "raw-receipt.json"
    if raw.is_symlink() or receipt_path.is_symlink():
        raise CckpError("ARTIFACT_SYMLINK_NOT_ALLOWED")
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["plan_id"] != plan_id or not raw.is_file() or sha_file(raw) != receipt["sha256"]:
            raise CckpError("IMMUTABLE_RECEIPT_OR_RAW_MISMATCH")
        seal = root / "receipt-seal.json"
        if not seal.is_file() or json.loads(seal.read_text(encoding="utf-8")).get(
            "receipt_sha256"
        ) != sha_file(receipt_path):
            raise CckpError("RECEIPT_SEAL_MISSING_OR_DRIFT")
        return {
            "status": "VERIFIED_REAL_REUSED",
            "receipt": receipt,
            "downloaded_bytes_this_call": 0,
        }
    if reviewed_range_retry:
        return _reviewed_ranges(listing, selected, plan, root, transport or S3Transport(timeout=30))
    if raw.exists() or (root / "transfer-state.json").exists():
        raise CckpError("PREVIOUS_TRANSFER_REQUIRES_MANUAL_REVIEW")
    lock = root / "download.lock"
    with lock.open("x", encoding="ascii") as stream:
        stream.write(plan_id)
    try:
        _write_new(root / "plan.json", plan)
        # 오류 시 수신량을 모르면 예약을 보존한다. 자동 재시도/전역 sync 없음.
        _write_new(
            root / "transfer-state.json",
            {"plan_id": plan_id, "reserved_bytes": selected.size, "max_bytes": CAP},
        )
        transport = transport or S3Transport(timeout=30)
        head = head_object(listing, selected.key, transport=transport)
        url = ENDPOINT + "/" + quote(selected.key, safe="/")
        status, headers, body = transport("GET", url, {"If-Match": selected.etag}, selected.size)
        if status != 200 or headers.get("etag") != selected.etag or len(body) != selected.size:
            raise CckpError("GLOBAL_OBJECT_ETAG_OR_SIZE_DRIFT")
        with raw.open("xb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        receipt = {
            **plan,
            "status": "RAW_NOT_QC_VALIDATED",
            "source_uri": "s3://wbg-cckp/" + selected.key,
            "download_uri": url,
            "sha256": sha_file(raw),
            "raw_path": str(raw.resolve()),
            "etag_is_sha256": False,
            "acquired_at": datetime.now(timezone.utc).isoformat(),
            "downloaded_bytes": len(body),
            "trace_id": "cckp-indonesia-numeric-" + plan_id[:16],
            "head_evidence": head,
            "indonesia_subset_verified": False,
        }
        _write_new(receipt_path, receipt)
        _write_new(
            root / "receipt-seal.json",
            {"receipt_sha256": sha_file(receipt_path), "plan_id": plan_id},
        )
        return {
            "status": "VERIFIED_REAL_RAW_ONLY",
            "receipt": receipt,
            "downloaded_bytes_this_call": len(body),
        }
    except Exception as error:
        state_path = root / "transfer-state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state.update(
                status="BLOCKED",
                error_type=type(error).__name__,
                rate_limited=getattr(error, "code", None) == 429,
            )
            if state["rate_limited"] and getattr(error, "headers", None):
                state["retry_after"] = error.headers.get("Retry-After")
            _update_state(state_path, state)
        raise
    finally:
        lock.unlink(missing_ok=True)


def _reviewed_ranges(listing, selected, plan, root, transport):
    """Root가 승인한 동일 계획의 단 한 번 재개. 최초 불확실 수신 예약도 보존한다."""
    state_path = root / "transfer-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if (
        state["plan_id"] != plan["plan_id"]
        or state.get("reviewed_retry_count", 0)
        or state.get("rate_limited")
    ):
        raise CckpError("REVIEWED_RETRY_NOT_AVAILABLE")
    if (root / "global-asset.nc").exists() or (root / "global-asset.nc.part").exists():
        raise CckpError("PARTIAL_REQUIRES_SEPARATE_REVIEW")
    _write_new(root / "first-transfer-state.json", state)
    lock = root / "download.lock"
    with lock.open("x", encoding="ascii") as stream:
        stream.write(plan["plan_id"])
    partial = root / "global-asset.nc.part"
    state.update(
        reviewed_retry_count=1,
        prior_uncertain_reserved_bytes=state["reserved_bytes"],
        partial_bytes=0,
        partial_sha256=hashlib.sha256(b"").hexdigest(),
        conservative_total_bytes=state["reserved_bytes"],
        range_retry_requested_bytes=0,
        status="REVIEWED_RANGE_RETRY_RUNNING",
    )
    _update_state(state_path, state)
    try:
        head = head_object(listing, selected.key, transport=transport)
        url = ENDPOINT + "/" + quote(selected.key, safe="/")
        with partial.open("xb") as stream:
            offset = 0
            index = 0
            while offset < selected.size:
                last = min(selected.size - 1, offset + 256 * 1024 - 1)
                requested = last - offset + 1
                state["range_retry_requested_bytes"] += requested
                state["conservative_total_bytes"] = (
                    state["prior_uncertain_reserved_bytes"] + state["range_retry_requested_bytes"]
                )
                if state["conservative_total_bytes"] > CAP:
                    raise CckpError("CONSERVATIVE_CUMULATIVE_CAP_EXCEEDED")
                _update_state(state_path, state)
                status, headers, body = transport(
                    "GET",
                    url,
                    {"If-Match": selected.etag, "Range": f"bytes={offset}-{last}"},
                    requested,
                )
                if (
                    status != 206
                    or headers.get("etag") != selected.etag
                    or len(body) != requested
                    or headers.get("content-range") != f"bytes {offset}-{last}/{selected.size}"
                ):
                    raise CckpError("RANGE_RESPONSE_DRIFT")
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
                offset += len(body)
                index += 1
                state.update(partial_bytes=offset, partial_sha256=sha_file(partial))
                _write_new(root / f"range-progress-{index:03}.json", dict(state))
                _update_state(state_path, state)
        os.replace(partial, root / "global-asset.nc")
        receipt = {
            **plan,
            "status": "RAW_NOT_QC_VALIDATED",
            "source_uri": "s3://wbg-cckp/" + selected.key,
            "download_uri": url,
            "sha256": sha_file(root / "global-asset.nc"),
            "raw_path": str((root / "global-asset.nc").resolve()),
            "etag_is_sha256": False,
            "acquired_at": datetime.now(timezone.utc).isoformat(),
            "downloaded_bytes": selected.size,
            "trace_id": "cckp-indonesia-numeric-" + plan["plan_id"][:16],
            "head_evidence": head,
            "indonesia_subset_verified": False,
            "conservative_total_bytes": state["conservative_total_bytes"],
            "reviewed_range_retry_count": 1,
            "range_chunks": index,
        }
        _write_new(root / "raw-receipt.json", receipt)
        _write_new(
            root / "receipt-seal.json",
            {"receipt_sha256": sha_file(root / "raw-receipt.json"), "plan_id": plan["plan_id"]},
        )
        state["status"] = "RAW_COMPLETED_NOT_CF_VALIDATED"
        _update_state(state_path, state)
        return {
            "status": "VERIFIED_REAL_RAW_ONLY",
            "receipt": receipt,
            "downloaded_bytes_this_call": selected.size,
        }
    except Exception as error:
        state.update(
            status="BLOCKED",
            error_type=type(error).__name__,
            rate_limited=getattr(error, "code", None) == 429,
        )
        if state["rate_limited"] and getattr(error, "headers", None):
            state["retry_after"] = error.headers.get("Retry-After")
        _update_state(state_path, state)
        raise
    finally:
        lock.unlink(missing_ok=True)
