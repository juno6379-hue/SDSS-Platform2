"""고정 누락 geometry를 재개·중복 검사 가능한 target ID로 바꾼다. 수집하지 않는다."""
import hashlib
import json
from pathlib import Path

from shapely.geometry import shape

from services.datahub.connectors.onemap.boundary import sha256, PROVINCES
from .completeness import BANDS, guarded_batch_preflight


def derive_missing_targets(path: Path, expected_sha: str, *, maximum=6, existing_target_ids=()):
    if type(maximum) is not int or not 1 <= maximum <= 6:
        raise ValueError("BOUNDED_TARGET_COUNT_REQUIRED")
    if path.stat().st_size > 512 * 1024 * 1024 or sha256(path) != expected_sha:
        raise ValueError("EXACT_QUEUE_PIN_OR_SIZE_INVALID")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("crs", {}).get("properties", {}).get("name") != "EPSG:6933":
        raise ValueError("EXACT_QUEUE_CRS_REQUIRED")
    if doc.get("type") != "FeatureCollection" or len(doc["features"]) > 72:
        raise ValueError("EXACT_QUEUE_FEATURE_COUNT_INVALID")
    candidates, seen = [], set()
    for index, feature in enumerate(doc["features"]):
        properties = feature["properties"]
        if properties["reason"] != "MISSING_SIMULTANEOUS_SIX_BANDS_SCL":
            continue
        province, year = properties["province"], properties["year"]
        if properties["required_bands"] != list(BANDS) + ["SCL"] or (province, year) in seen:
            raise ValueError("EXACT_QUEUE_ASSETS_OR_DUPLICATE_INVALID")
        seen.add((province, year))
        if province not in PROVINCES or type(year) is not int or not 2020 <= year <= 2025:
            raise ValueError("EXACT_QUEUE_SCOPE_INVALID")
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid or geometry.area <= 0:
            raise ValueError("EXACT_QUEUE_GEOMETRY_INVALID")
        # 원장의 timestamp만 바뀌어도 동일 공간을 새 target으로 가장하지 못하게 한다.
        identity = json.dumps({"geometry_sha256": hashlib.sha256(geometry.normalize().wkb).hexdigest(),
                               "province": province, "year": year,
                               "assets": list(BANDS) + ["SCL"]}, sort_keys=True).encode()
        target_id = hashlib.sha256(identity).hexdigest()
        if target_id in existing_target_ids:
            continue
        candidates.append({"target_id": target_id, "province": province, "year": year,
            "queue": {"path": str(path.resolve()), "sha256": expected_sha, "feature_index": index},
            "missing_area_m2": geometry.area, "projected_bounds": list(geometry.bounds),
            "scene_id": None, "asset_window_pins": None, "executable": False,
            "status": "PLANNED_EXACT_GEOMETRY_REQUIRES_SCENE_AND_SHARED_LEDGER_ADAPTER"})
    candidates.sort(key=lambda x: (-x["missing_area_m2"], x["province"], x["year"]))
    # 한 주의6개 연도만 선점하지 않고 서로 다른 주의 누락을 먼저 제안한다.
    selected, provinces = [], set()
    for item in candidates:
        if item["province"] not in provinces:
            selected.append(item)
            provinces.add(item["province"])
            if len(selected) == maximum:
                break
    return selected


def plan_missing_batch(targets, *, ledger, ledger_sha, current_ledger_sha,
                       active_collectors, lock_exists, disk_free_bytes, reserve_bytes=32 * 1024 * 1024):
    result = guarded_batch_preflight(ledger=ledger, ledger_sha256=ledger_sha,
        observed_ledger_sha256=current_ledger_sha, active_collectors=active_collectors,
        lock_exists=lock_exists, disk_free_bytes=disk_free_bytes,
        candidate_keys=[x["target_id"] for x in targets], existing_keys=ledger.get("target_ids", []),
        reserve_bytes=reserve_bytes, shared_reservation_writable=False)
    if any(x.get("scene_id") is None or not x.get("asset_window_pins") for x in targets):
        result["errors"].append("EXACT_SCENE_ASSET_WINDOW_PINS_MISSING")
        result["status"] = "BLOCKED"
    return {**result, "targets": targets, "source_scope": "SIX_BANDS_PLUS_SCL_SAME_SCENE",
            "raw_reference_ledger_write_authorized": False, "new_local_ledger_budget_reset_allowed": False}
