"""Inventory West Java and the existing Banten baseline from held, receipted assets."""

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from subprocess import SubprocessError

from rasterio.warp import transform_bounds
from shapely.geometry import box, shape
from shapely.ops import transform, unary_union

from services.datahub.sentinel.shared_ledger import SharedLedger, active_collectors
from services.lcluc.banten_historical_trend import WORKBOOK, WORKBOOK_SHA256, import_trend
from services.lcluc.province_esri import DEST as ESRI_DIR
from services.lcluc.province_esri import (
    SNAPSHOT_SHA256,
    SOURCE,
    YEARS,
    digest,
    plan,
    utc,
    write_json,
)
from services.lcluc.province_optical_plan import DEST as OPTICAL_DIR
from services.lcluc.province_optical_plan import PROJECT, PROVIDERS

REGIONS = {
    "banten": ("반텐", "Banten", "Banten", "36"),
    "west_java": ("서자바", "Jawa Barat", "West Java", "32"),
}
HELD_DIR = Path("evidence/onemap_sentinel/held-audit-20261124")
BOUNDARY_RECEIPT = Path("evidence/onemap_sentinel/audit-20261124/boundary/receipt.json")
PILOT_BATCHES = Path("evidence/onemap_sentinel/coverage-batches")
KLHK_METADATA = Path("evidence/klhk_rag/verification-20261124.json")
LEDGER = Path("data/first-group-training-budget/global-ledger.json")
MAPBIOMAS = Path("data/curated/explorer/west-java-province/mapbiomas-4.1-trend.json")
DEFAULT_OUTPUT = Path("evidence/westjava/held-data-audit.json")
NATIVE_SENTINEL = frozenset({"B02", "B03", "B04", "B08", "B11", "B12", "SCL"})


def read_json(path):
    return json.loads(path.read_bytes())


def under(root, candidate):
    root = root.resolve()
    candidate = (root / candidate).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"PIN_OUTSIDE_SOURCE_ROOT: {candidate.name}")
    return candidate


def file_pin(root, path):
    return {
        "path": path.resolve().relative_to(root).as_posix(),
        "sha256": digest(path),
        "bytes": path.stat().st_size,
    }


def verify_file(path, pin, *, rehash=True):
    if not path.is_file() or ("bytes" in pin and path.stat().st_size != pin["bytes"]):
        raise ValueError(f"PIN_MISSING_OR_SIZE_CHANGED: {path.name}")
    if rehash and digest(path) != pin["sha256"]:
        raise ValueError(f"PIN_SHA_DRIFT: {path.name}")


def coverage(region, footprints):
    union = unary_union(footprints).intersection(region)
    return {
        "footprint_area_m2": round(union.area, 2),
        "footprint_pct": round(100 * union.area / region.area, 6),
    }


def geographic_inputs(root):
    source = under(root, SOURCE)
    verify_file(source, {"sha256": SNAPSHOT_SHA256})
    receipt = read_json(under(root, BOUNDARY_RECEIPT))
    if receipt["boundary"]["sha256"] != SNAPSHOT_SHA256:
        raise ValueError("BOUNDARY_RECEIPT_SHA_MISMATCH")
    geometries = {}
    evidence = {}
    for feature in read_json(source)["features"]:
        region = feature["properties"]["province_id"]
        if region not in REGIONS:
            continue
        geometry = shape(feature["geometry"])
        projected = transform(PROJECT, geometry)
        derived = root / BOUNDARY_RECEIPT.parent / (region + ".geojson")
        clip = next(pin for pin in receipt["files"] if Path(pin["path"]).name == derived.name)
        verify_file(derived, clip)
        names = REGIONS[region]
        geometries[region] = projected
        evidence[region] = {
            "name_ko": names[0],
            "name_id": names[1],
            "name_en": names[2],
            "province_code": names[3],
            "bbox_crs84": list(geometry.bounds),
            "area_m2_epsg6933": round(projected.area, 2),
            "boundary": file_pin(root, derived),
            "boundary_snapshot": SNAPSHOT_SHA256,
            "boundary_source": receipt["source_uri"],
            "boundary_acquired_at": receipt["acquired_at"],
            "publisher_version": receipt["publisher_version"],
            "project_statistics_approved": receipt["approved_for_project_statistics"],
        }
    if geometries.keys() != REGIONS.keys():
        raise ValueError("PINNED_REGION_MISSING")
    return geometries, evidence


def esri_receipts(root, regions, *, years=YEARS, rehash_large_assets=True):
    grouped = defaultdict(list)
    province_tiles, _ = plan(root=root)
    for path in sorted((root / ESRI_DIR).glob("*/*.receipt.json")):
        if int(path.parent.name) not in years:
            continue
        row = read_json(path)
        if not any(row["tile"] in province_tiles[region] for region in regions):
            continue
        if row["boundary_sha256"] != SNAPSHOT_SHA256 or row["year"] != int(path.parent.name):
            raise ValueError("ESRI_BOUNDARY_SHA_MISMATCH")
        raw = under(root, row["path"])
        verify_file(raw, row, rehash=rehash_large_assets)
        grid = row["native_grid"]
        footprint = transform(
            PROJECT, box(*transform_bounds(grid["crs"], "EPSG:4326", *grid["bounds"]))
        )
        for region, polygon in regions.items():
            if row["tile"] not in province_tiles[region]:
                continue
            row_with_pin = {
                "tile": row["tile"],
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "raster": raw.relative_to(root).as_posix(),
                "source_uri": row["uri"],
                "dataset": row["dataset"],
                "license": row["license"],
                "etag": row["etag"],
                "acquired_at": row["retrieved_at"],
                "receipt": file_pin(root, path),
                "scope": "weak_reference",
                "integrity_check": "sha256" if rehash_large_assets else "size_and_held_receipt",
                "native_grid": grid,
            }
            grouped[region, row["year"]].append((row_with_pin, footprint.intersection(polygon)))
    return dict(grouped), province_tiles


def full_scenes(root, regions, sensor, *, rehash_large_assets=True):
    _, collection, required_assets = PROVIDERS[sensor]
    source_folder = "sentinel-native" if sensor == "sentinel-2" else "landsat-native"
    grouped = defaultdict(list)
    trusted_catalogs = {}
    for path in sorted((root / OPTICAL_DIR / source_folder).glob("*/*/scene-receipt.json")):
        row = read_json(path)
        date_observed = date.fromisoformat(row["observed_at"][:10])
        year = date_observed.year
        if row["collection"] != collection or str(year) != path.parent.parent.name:
            raise ValueError("OPTICAL_RECEIPT_COLLECTION_OR_YEAR_MISMATCH")
        pin = row["stac_page"]
        resolved = under(root, pin["path"])
        cache_key = (resolved, pin["sha256"])
        if cache_key not in trusted_catalogs:
            verify_file(resolved, pin)
            trusted_catalogs[cache_key] = {
                item["id"]: item for item in read_json(resolved)["features"]
            }
        item = trusted_catalogs[cache_key][row["scene"]]
        if item["properties"]["datetime"] != row["observed_at"]:
            raise ValueError("OPTICAL_RECEIPT_DATE_DRIFT")
        projected = transform(PROJECT, shape(item["geometry"]))
        region_intersections = {
            region: polygon.intersection(projected)
            for region, polygon in regions.items()
            if polygon.intersects(projected)
        }
        if not any(intersection.area > 0 for intersection in region_intersections.values()):
            continue
        if not set(required_assets).issubset(row["assets"]):
            raise ValueError("OPTICAL_REQUIRED_ASSET_NOT_RECEIPTED")
        for band in required_assets:
            asset = row["assets"][band]
            if item["assets"][band]["href"] != asset["uri"]:
                raise ValueError("OPTICAL_ASSET_URI_MISMATCH")
            verify_file(under(root, asset["path"]), asset, rehash=rehash_large_assets)
        qa_radsat = False
        if sensor == "landsat" and "qa_radsat" in row["assets"]:
            asset = row["assets"]["qa_radsat"]
            if item["assets"]["qa_radsat"]["href"] != asset["uri"]:
                raise ValueError("LANDSAT_QA_RADSAT_URI_MISMATCH")
            verify_file(under(root, asset["path"]), asset, rehash=rehash_large_assets)
            qa_radsat = True
        record = {
            "scene_id": row["scene"],
            "observed_at": row["observed_at"],
            "scene_cloud_pct": item["properties"].get("eo:cloud_cover"),
            "receipt": file_pin(root, path),
            "stac_page": pin,
            "asset_count": len(row["assets"]),
            "integrity_check": "sha256" if rehash_large_assets else "size_and_held_receipt",
            "native_resolution_m": {
                band: row["assets"][band]["native_grid"]["resolution"] for band in required_assets
            },
            "qa_radsat_catalogued": sensor == "landsat" and "qa_radsat" in item["assets"],
            "qa_radsat_held": qa_radsat,
        }
        for region, intersection in region_intersections.items():
            if intersection.area > 0:
                grouped[region, year].append(
                    (record | {"footprint_overlap_m2": round(intersection.area, 2)}, intersection)
                )
    return dict(grouped)


def legacy_sentinel_windows(root, reference):
    grouped = defaultdict(list)
    source_root = reference / "data/first-group-training-esri-v1/sources"
    for pin in sorted((root / HELD_DIR / "native-checkpoints").glob("*.json")):
        row = read_json(pin)
        if row["province"] not in REGIONS:
            continue
        folder = under(source_root, Path(row["parent_path"]).parent)
        verified = {
            Path(asset["path"]).name: asset
            for asset in row["verified_files"]
            if Path(asset["path"]).parent.resolve() == folder
        }
        names = {f"raw-{band}.tif" for band in NATIVE_SENTINEL} | {"stac-item.json"}
        if not names.issubset(verified):
            continue
        for name in names:
            verify_file(folder / name, verified[name])
        stac = read_json(folder / "stac-item.json")
        observed = stac["properties"]["datetime"]
        if date.fromisoformat(observed[:10]).year != row["year"]:
            raise ValueError("LEGACY_NATIVE_SENTINEL_YEAR_MISMATCH")
        grouped[row["province"], row["year"]].append(
            {
                "scene_id": stac["id"],
                "observed_at": observed,
                "verified_assets": sorted(names),
                "geometry_scope": "native_window",
                "receipt": file_pin(root, pin),
                "b02_sha256": verified["raw-B02.tif"]["sha256"],
            }
        )
    return grouped


def pilot_sentinel_windows(root):
    grouped = defaultdict(list)
    for path in sorted((root / PILOT_BATCHES).glob("*/steps/*/transfer/result.json")):
        row = read_json(path)
        if row.get("province") not in REGIONS or row.get("execution_status") != "PILOT_QA_PASS":
            continue
        if not (
            row["measurement_complete"]
            and row["qa"]["same_scene_all_assets"]
            and {item["band"] for item in row["assets"]} == NATIVE_SENTINEL
        ):
            raise ValueError("PILOT_QA_RECEIPT_MISMATCH")
        for item in row["assets"]:
            asset = (
                root / "data/raw/sentinel-pilots" / row["idempotency_key"] / Path(item["path"]).name
            )
            verify_file(under(root, asset), item)
        grouped[row["province"], row["year"]].append(
            {
                "scene_id": row["scene_id"],
                "receipt": file_pin(root, path),
                "qa_clear_pct": 100 * row["qa"]["clear_fraction"],
                "geometry_scope": "native_window",
                "remote_body_bytes_from_receipt": row["remote_body_bytes_read"],
            }
        )
    return grouped


def current_ledger(reference):
    path = under(reference, LEDGER)
    sha = digest(path)
    ledger = SharedLedger(path)
    state = ledger.snapshot(sha)
    try:
        observed = [item["ProcessId"] for item in active_collectors()]
        collector_scan = "VERIFIED"
    except (OSError, SubprocessError):
        observed = None
        collector_scan = "BLOCKED_PROCESS_SCAN_FAILED"
    return {
        "observed_at": utc(),
        "sha256": sha,
        "updated_at": state["updated_at"],
        "additional_maximum_bytes": state["additional_maximum_bytes"],
        "charged_including_reservations_bytes": state["new_charged_bytes"],
        "remaining_bytes": state["additional_maximum_bytes"] - state["new_charged_bytes"],
        "http429_circuit_active": state.get("rate_limit_active", False),
        "active_collectors": observed,
        "collector_scan_status": collector_scan,
        "execution_lock_present": ledger.execution_lock.exists(),
        "ledger_lock_present": ledger.lock.exists(),
        "pending": [
            {
                "id": key,
                "reserved_bytes": row["reserved_bytes"],
                "io_started": row.get("io_started"),
            }
            for key, row in state["batches"].items()
            if row["status"] == "pending"
        ],
        "west_java_new_scope_approval_verified": False,
        "remote_requests_in_audit": 0,
    }


def historical_patch_audit(root, region, year):
    path = root / HELD_DIR / "cell-checkpoints" / f"{region}-{year}.json"
    report = read_json(path)
    row = report["cell"]
    if (row["province"], row["year"], report["input_pins"]["boundary"]) != (
        region,
        year,
        SNAPSHOT_SHA256,
    ):
        raise ValueError("PATCH_RECEIPT_SCOPE_MISMATCH")
    return {
        "receipt": file_pin(root, path),
        "physical_patch_records": row["physical_patch_records"],
        "manifest_quality_eligible": row["manifest_quality_eligible"],
        "verified_six_band_scl_patches": row["verified_six_band_scl_patches"],
        "present_coverage_pct": row["present_coverage_pct"],
        "clear_coverage_pct": row["clear_coverage_pct"],
        "missing_joint_area_m2": row["missing_joint_area_m2"],
    }


def build_inventory(root, reference, *, rehash_large_assets=True):
    root, reference = root.resolve(), reference.resolve()
    regions, records = geographic_inputs(root)
    esri, expected_tiles = esri_receipts(root, regions, rehash_large_assets=rehash_large_assets)
    sentinel = full_scenes(root, regions, "sentinel-2", rehash_large_assets=rehash_large_assets)
    landsat = full_scenes(root, regions, "landsat", rehash_large_assets=rehash_large_assets)
    legacy_windows = legacy_sentinel_windows(root, reference)
    pilot_windows = pilot_sentinel_windows(root)
    known_klhk = {
        row["year"]: row
        for row in read_json(root / KLHK_METADATA)["acquired_documents"]
        if "year" in row and row["source_id"].startswith("klhk-")
    }
    mapbiomas_root = "data/curated/explorer"
    for region, polygon in regions.items():
        records[region]["annual"] = {}
        trend_dir = "banten-province" if region == "banten" else "west-java-province"
        trend_path = root / mapbiomas_root / trend_dir / MAPBIOMAS.name
        trend = read_json(trend_path)
        if trend["region"] != region or trend["sha256"] != WORKBOOK_SHA256:
            raise ValueError("MAPBIOMAS_REGION_OR_SOURCE_MISMATCH")
        trend_pin = file_pin(root, trend_path)
        for year in YEARS:
            key = (region, year)
            esri_rows = esri.get(key, [])
            sentinel_rows = sentinel.get(key, [])
            landsat_rows = landsat.get(key, [])
            official_metadata = known_klhk.get(year)
            records[region]["annual"][str(year)] = {
                "sentinel-2": {
                    "scope": "native_stac_footprint_and_separate_windows",
                    "full_scenes": [r for r, _ in sentinel_rows],
                    "full_scene_count": len(sentinel_rows),
                    **coverage(polygon, [footprint for _, footprint in sentinel_rows]),
                    "legacy_windows": legacy_windows[key],
                    "pilot_qa_pass_windows": pilot_windows[key],
                    "archive_patch_audit_20261124": historical_patch_audit(root, region, year),
                    "mosaic_qa_state": "NOT_ESTIMATED_BY_INVENTORY",
                },
                "landsat": {
                    "scope": "native_stac_footprint",
                    "full_scenes": [r for r, _ in landsat_rows],
                    "full_scene_count": len(landsat_rows),
                    **coverage(polygon, [footprint for _, footprint in landsat_rows]),
                    "qa_radsat_held_count": sum(row["qa_radsat_held"] for row, _ in landsat_rows),
                    "mosaic_qa_state": "NOT_ESTIMATED_BY_INVENTORY",
                },
                "esri": {
                    "scope": "native_tile_extent_weak_reference",
                    "tiles": [r for r, _ in esri_rows],
                    "expected_tiles": expected_tiles[region],
                    **coverage(polygon, [footprint for _, footprint in esri_rows]),
                },
                "mapbiomas": {
                    "scope": "publisher_province_statistics",
                    "statistics": trend_pin if year in trend["years"] else None,
                    "pixel_raster_held": False,
                },
                "klhk": {
                    "scope": "metadata_only",
                    "metadata": {
                        key: official_metadata[key]
                        for key in (
                            "source_uri",
                            "version",
                            "sha256",
                            "year_verified",
                            "native_23_verified",
                            "license_verified",
                        )
                    }
                    if official_metadata
                    else None,
                    "vector_or_raster_held": False,
                },
            }
    return {
        "schema_version": "sdss-regional-held-data/1",
        "status": "VERIFIED_REAL",
        "checked_at": utc(),
        "large_asset_integrity": "all_rehashed" if rehash_large_assets else "size_and_held_receipt",
        "regions": records,
        "shared_sentinel_ledger": current_ledger(reference),
        "mapbiomas_workbook": file_pin(root, root / WORKBOOK),
        "independent_reference": {
            "status": "BLOCKED",
            "reason": "APPROVED_SAME_YEAR_CAMPAIGN_MISSING",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--receipt-size-audit",
        action="store_true",
        help="Check large raw files by byte length and held receipt. Native windows retain SHA-256 verification.",
    )
    args = parser.parse_args()
    root = Path.cwd().resolve()
    # Preserve the workbook's original acquisition date when publishing a second regional slice.
    banten = read_json(root / MAPBIOMAS.parent.with_name("banten-province") / MAPBIOMAS.name)
    west_java = import_trend(
        root / WORKBOOK, date.fromisoformat(banten["acquired_on"]), region="west_java"
    )
    output = root / MAPBIOMAS
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, west_java)
    evidence = build_inventory(
        root, args.reference_root, rehash_large_assets=not args.receipt_size_audit
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, evidence)
    print(
        json.dumps({"status": evidence["status"], "output": str(args.output)}, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
