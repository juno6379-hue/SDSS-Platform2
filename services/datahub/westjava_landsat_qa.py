"""Backfill only pinned radiometric-saturation QA for previously retained Landsat scenes."""

import argparse
from datetime import date
from pathlib import Path

import rasterio
from shapely.geometry import shape
from shapely.ops import transform

from services.datahub.sentinel.shared_ledger import exclusive_os_lock
from services.datahub.westjava_inventory import read_json, under, verify_file
from services.lcluc.annual import store_json
from services.lcluc.annual_inputs import Pin
from services.lcluc.banten_landsat import PlanetaryComputer, check_uri, get_asset
from services.lcluc.province_esri import SNAPSHOT_SHA256, utc
from services.lcluc.province_optical_plan import DEST, PROJECT, boundary

DESTINATION = Path("data/raw/explorer/province/west-java-optical/landsat-qa")
COMPLETION = "landsat-qa-backfill-completed/1"
ASSET_CAP = 512 * 1024
TOTAL_CAP = 8 * 1024 * 1024


def source(root, row, aoi):
    year, identity = row["year"], row["scene_id"]
    prior_path = Pin.model_validate(row["scene_receipt"]).local(root)
    expected = root / DEST / "landsat-native" / str(year) / identity / "scene-receipt.json"
    if prior_path != expected.resolve() or not identity.startswith(("LC08_", "LC09_")):
        raise ValueError("QA_BACKFILL_REQUIRES_HELD_LANDSAT_RECEIPT")
    prior = read_json(prior_path)
    page = Pin.model_validate(row["stac_page"]).local(root)
    item = next((item for item in read_json(page)["features"] if item["id"] == identity), None)
    if (
        item is None or prior["stac_page"] != row["stac_page"] or prior["scene"] != identity
        or prior["collection"] != "landsat-c2-l2" or item["collection"] != "landsat-c2-l2"
        or prior["observed_at"] != item["properties"]["datetime"]
        or date.fromisoformat(prior["observed_at"][:10]).year != year
        or aoi.intersection(transform(PROJECT, shape(item["geometry"]))).area <= 0
    ):
        raise ValueError("QA_BACKFILL_STAC_OR_BOUNDARY_MISMATCH")
    asset = item["assets"]["qa_radsat"]
    if row["href"] != asset["href"] or not row["href"].endswith("_QA_RADSAT.TIF"):
        raise ValueError("QA_BACKFILL_REQUIRES_EXACT_RADSAT_URI")
    check_uri(row["href"])
    return prior, item, asset


def download(root, plan, expected_sha, *, execute=False, transport=None):
    verify_file(plan, {"sha256": expected_sha})
    document = read_json(plan)
    rows = document["assets"]
    total = sum(row["bytes"] for row in rows)
    if (
        not 0 < len(rows) <= 64
        or len({row["scene_id"] for row in rows}) != len(rows)
        or total != document["total_bytes"] or total > TOTAL_CAP
        or any(type(row["bytes"]) is not int or not 0 < row["bytes"] <= ASSET_CAP or not row["etag"]
               for row in rows)
    ):
        raise ValueError("QA_BACKFILL_PLAN_OUT_OF_BOUNDS")
    aoi = transform(PROJECT, boundary(root, province="west_java"))
    sources = [source(root, row, aoi) for row in rows]
    if not execute:
        return {"scenes": len(rows), "estimated_bytes": total, "transferred_bytes": 0}
    raw = under(root, DESTINATION)
    raw.mkdir(parents=True, exist_ok=True)
    pc = transport if transport is not None else PlanetaryComputer()
    with exclusive_os_lock(raw / "collector.lock"):
        complete_path = raw / f"{expected_sha}.complete.json"
        if complete_path.exists():
            done = read_json(complete_path)
            if done["plan_sha256"] != expected_sha or done["schema_version"] != COMPLETION:
                raise ValueError("QA_COMPLETION_DRIFT")
            for entry in done["entries"]:
                verify_file(under(root, entry["qa"]["path"]), entry["qa"])
            return done
        entries, charged = [], 0
        for row, (prior, _, asset) in zip(rows, sources, strict=True):
            folder = raw / str(row["year"]) / row["scene_id"]
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / "qa_radsat.tif"
            held = path.is_file()
            received = get_asset(pc, asset, path, expected=(row["bytes"], row["etag"]))
            received["path"] = path.relative_to(root).as_posix()
            cloud = prior["assets"]["qa_pixel"]
            cloud_file = under(root, cloud["path"])
            verify_file(cloud_file, cloud, rehash=False)
            with rasterio.open(path) as saturation, rasterio.open(cloud_file) as quality:
                if (saturation.dtypes != ("uint16",) or saturation.res != (30, 30)
                    or (saturation.crs, saturation.transform, saturation.shape)
                    != (quality.crs, quality.transform, quality.shape)):
                    raise ValueError("QA_RADSAT_GRID_DIFFERS_FROM_QA_PIXEL")
            supplement = {
                "region": "west_java", "year": row["year"], "scene_id": row["scene_id"],
                "collection": prior["collection"], "observed_at": prior["observed_at"],
                "license": "USGS Landsat open data", "scene_receipt": row["scene_receipt"],
                "stac_page": row["stac_page"], "qa": received,
            }
            supplement_path = folder / "qa-supplement.json"
            if not supplement_path.exists():
                store_json(supplement_path, supplement)
            elif read_json(supplement_path) != supplement:
                raise ValueError("QA_SUPPLEMENT_CHANGED")
            entries.append(supplement)
            charged += 0 if held else received["bytes"]
            print(row["year"], row["scene_id"], received["bytes"], flush=True)
        done = {
            "schema_version": COMPLETION, "plan_sha256": expected_sha, "region": "west_java",
            "boundary_sha256": SNAPSHOT_SHA256, "license": "USGS Landsat open data",
            "received_at": utc(), "estimated_bytes": total, "transferred_bytes": charged,
            "entries": entries,
        }
        store_json(complete_path, done)
        return done


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = download(Path.cwd().resolve(), args.plan, args.expected_sha256, execute=args.execute)
    print(f"{result['estimated_bytes']} planned bytes, {result['transferred_bytes']} downloaded bytes")


if __name__ == "__main__":
    main()
