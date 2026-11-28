"""Publish regional worker inputs from completed, immutable optical collection receipts."""

import json
from functools import partial
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_bounds
from shapely.geometry import box, mapping, shape
from shapely.ops import transform

from services.datahub.westjava_inventory import read_json, under
from services.datahub.westjava_landsat_qa import COMPLETION, DESTINATION
from services.datahub.westjava_optical_gaps import UNPROJECT, pixel_support
from services.lcluc.annual import store_json
from services.lcluc.annual_inputs import Bands, Pin
from services.lcluc.annual_rasters import equal_area_grid
from services.lcluc.province_esri import SNAPSHOT_SHA256, digest
from services.lcluc.province_optical_plan import PROJECT, boundary
from services.lcluc.regional_worker import Receipt, pin
from services.lcluc.westjava_2020_pilot import LANDSAT_NAMES, scene_uri

RECEIPT_SCHEMA = "sdss-regional-optical-receipt/1"
MOSAIC_SCHEMA = "lcluc-regional-mosaic/1"
BLOCK_M = 2400


def publish(inbox, receipt):
    validated = Receipt.model_validate(receipt)
    raw = json.dumps(validated.model_dump(mode="json"), sort_keys=True).encode()
    key = sha256(raw).hexdigest()
    job = inbox / f"{key}.json"
    if job.exists():
        if digest(job) != key:
            raise ValueError("INTAKE_RECEIPT_PIN_CHANGED")
        return key
    with NamedTemporaryFile(dir=inbox, suffix=".pending", delete=False) as stream:
        pending = Path(stream.name)
        stream.write(raw)
    try:
        pending.replace(job)
    finally:
        pending.unlink(missing_ok=True)
    print(f"Published collector receipt {key}", flush=True)
    return key


def dispatch(inbox, source_key, build):
    cache = inbox / ".collector"
    cache.mkdir(exist_ok=True)
    marker = cache / f"{sha256(source_key.encode()).hexdigest()}.json"
    if marker.is_file():
        job = Pin.model_validate(read_json(marker)).local(inbox)
        return job.stem
    key = publish(inbox, build())
    store_json(marker, pin(inbox, inbox / f"{key}.json"))
    return key


def landsat_scene(platform, entry, evidence):
    original = read_json(Pin.model_validate(entry["scene_receipt"]).local(platform))
    page = read_json(Pin.model_validate(entry["stac_page"]).local(platform))
    item = next((item for item in page["features"] if item["id"] == entry["scene_id"]), None)
    if (
        original["stac_page"] != entry["stac_page"] or original["scene"] != entry["scene_id"]
        or item is None or item["properties"]["datetime"] != entry["observed_at"]
        or item["assets"]["qa_radsat"]["href"] != entry["qa"]["uri"]
    ):
        raise ValueError("COLLECTOR_LANDSAT_COMPLETION_SCOPE_INVALID")
    entries = original["assets"]
    assets = {key: {field: entries[name][field] for field in ("path", "bytes", "sha256")}
              for key, name in LANDSAT_NAMES.items()}
    assets["QA_RADSAT"] = {key: entry["qa"][key] for key in ("path", "bytes", "sha256")}
    # A published receipt must never reference partial or unverified QA data.
    Pin.model_validate(assets["QA_RADSAT"]).local(platform)
    return {
        "source_id": entry["scene_id"].lower(), "observed_on": entry["observed_at"][:10],
        "raw_root": "platform", "provider": "planetary-computer", "uri": scene_uri(item),
        "version": "landsat-c2-l2", "license": evidence["license"],
        "acquired_at": entry["qa"]["received_at"], "assets": assets, "scale": [0.0000275] * 6,
        "offset": [-0.2] * 6, "stac_item": entry["stac_page"],
    }, transform(PROJECT, shape(item["geometry"]))


def optical_window(platform, province, scene, extent, occupied, target_fraction, sensor="landsat"):
    """Select from fixed blocks with optical QA only, ahead of any Esri sampling."""
    available = province.intersection(extent)
    bounds = available.bounds
    west, south, east, north = province.bounds
    target_x = west + (east - west) * target_fraction
    target_y = (south + north) / 2
    grid = equal_area_grid(available, 300)
    affine = grid["transform"]
    inside = geometry_mask([mapping(available)], (grid["height"], grid["width"]), affine, invert=True)
    keys = (*Bands[sensor], "SCL") if sensor == "sentinel-2" else tuple(LANDSAT_NAMES)
    paths = [under(platform, scene["assets"][name]["path"]) for name in keys]
    qa = under(platform, scene["assets"]["QA_RADSAT"]["path"]) if sensor == "landsat" else None
    present, clear = pixel_support(sensor, grid, inside, [(paths, qa)])
    samples = BLOCK_M // 300
    selected, nearest = None, float("inf")
    for x in range(int(bounds[0]) // BLOCK_M * BLOCK_M, int(bounds[2]), BLOCK_M):
        for y in range(int(bounds[1]) // BLOCK_M * BLOCK_M, int(bounds[3]), BLOCK_M):
            block = box(x, y, x + BLOCK_M, y + BLOCK_M)
            clipped = available.intersection(block)
            if clipped.area < 450_000 or any(clipped.distance(prior) < 6000 for prior in occupied):
                continue
            column, row = (x - int(affine.c)) // 300, (int(affine.f) - y - BLOCK_M) // 300
            cell = np.s_[max(0, row):row+samples, max(0, column):column+samples]
            count = inside[cell].sum()
            distance = (x + BLOCK_M / 2 - target_x) ** 2 + (y + BLOCK_M / 2 - target_y) ** 2
            if (count >= 5 and distance < nearest and present[cell].sum() / count >= 0.98
                and clear[cell].sum() / count >= 0.86):
                selected, nearest = clipped, distance
    if selected is None:
        raise ValueError(f"SPATIALLY_SEPARATE_QUALITY_WINDOW_UNAVAILABLE:{scene['source_id']}")
    return selected


def landsat_receipt(platform, complete_path, year):
    evidence = read_json(complete_path)
    if (
        evidence["schema_version"] != COMPLETION or evidence["boundary_sha256"] != SNAPSHOT_SHA256
        or evidence["region"] != "west_java"
        or complete_path.name != f"{evidence['plan_sha256']}.complete.json"
        or sum(entry["qa"]["bytes"] for entry in evidence["entries"]) != evidence["estimated_bytes"]
    ):
        raise ValueError("LANDSAT_COMPLETION_RECEIPT_INVALID")
    entries = [entry for entry in evidence["entries"] if entry["year"] == year]
    if len({entry["observed_at"][:10] for entry in entries}) < 3:
        raise ValueError("LANDSAT_THREE_DISTINCT_SPLIT_DATES_REQUIRED")
    province = transform(PROJECT, boundary(platform, province="west_java"))
    distinct, dates = [], set()
    for entry in entries:
        if entry["observed_at"][:10] in dates:
            continue
        distinct.append(landsat_scene(platform, entry, evidence))
        dates.add(entry["observed_at"][:10])
    # Allocate the scene with the smallest West Java intersection first, as the test split.
    ordered = sorted(distinct, key=lambda item: (item[1].intersection(province).area, item[0]["source_id"]))
    windows, occupied = [], []
    for (scene, extent), split, target in zip(
        ordered[:3], ("test", "train", "validation"), (0.30, 0.75, 0.50), strict=True,
    ):
        block = optical_window(platform, province, scene, extent, occupied, target)
        windows.append({"name": f"landsat-{split}", "split": split, "mosaic": {
            "schema_version": MOSAIC_SCHEMA, "region": "west_java", "year": year,
            "sensor": "landsat", "evidence": "real",
            "geometry": mapping(transform(UNPROJECT, block)), "scenes": [scene],
        }})
        occupied.append(block)
    return {"schema_version": RECEIPT_SCHEMA, "year": year, "region": "west_java",
            "windows": windows, "fit_landsat_candidate": True,
            "collector_receipts": [pin(platform, complete_path)]}


def sentinel_collected(platform, route):
    if "plan" in route:
        plan_path = Pin.model_validate(route["plan"]).local(platform)
        plan = read_json(plan_path)
        collected = plan_path.parent / "transfer" / "result.json"
        if not collected.is_file():
            raise FileNotFoundError("COLLECTOR_COMPLETION_PENDING")
        body = read_json(collected)
        if (body["plan_sha256"] != route["plan"]["sha256"]
            or any(body[field] != plan[field] for field in ("idempotency_key", "scene_id", "province", "year"))):
            raise ValueError("SENTINEL_COMPLETION_DIFFERS_FROM_APPROVED_PLAN")
        stac_path = Pin.model_validate(route["stac_item"]).local(platform)
        stac = read_json(stac_path)
        optics = read_json(Pin.model_validate(route["calibration"]).local(platform))
        xml = Pin.model_validate(route["product_metadata"]).local(platform)
        if (
            stac["id"] != body["scene_id"] or optics["product_id"] != body["scene_id"]
            or digest(xml) != optics["source_xml_sha256"]
            or any(optics["xml_product_uri"] not in row["source_uri"] for row in body["assets"])
        ):
            raise ValueError("SENTINEL_COLLECTION_CALIBRATION_MISMATCH")
        assets = {item["band"]: pin(platform, under(platform, item["path"])) for item in body["assets"]}
        expected = {name: item["sha256"] for name, item in assets.items()}
        if expected != {item["band"]: item["sha256"] for item in body["assets"]} or set(assets) != {*Bands["sentinel-2"], "SCL"}:
            raise ValueError("SENTINEL_COMPLETION_ASSET_DRIFT")
        with rasterio.open(Pin.model_validate(assets["B02"]).local(platform)) as image:
            geometry = mapping(box(*transform_bounds(image.crs, "EPSG:4326", *image.bounds)))
        calibrated = {
            "schema_version": MOSAIC_SCHEMA, "year": body["year"], "region": body["province"],
            "sensor": "sentinel-2", "evidence": "real", "geometry": geometry, "scenes": [{
                "source_id": stac["id"].lower(), "observed_on": stac["properties"]["datetime"][:10],
                "raw_root": "platform", "provider": "planetary-computer", "uri": scene_uri(stac),
                "version": "sentinel-2-l2a-" + optics["baseline"], "license": "Copernicus Sentinel data terms",
                "acquired_at": body["completed_at"], "assets": assets, "scale": optics["scale"],
                "offset": optics["offset"], "stac_item": route["stac_item"], "calibration": route["calibration"],
            }],
        }
        pins = [route["plan"], pin(platform, collected), route["product_metadata"]]
    else:
        collected = Pin.model_validate(route["transfer"]).local(platform)
        calibrated = read_json(Pin.model_validate(route["calibrated_mosaic"]).local(platform))
        pins = [route["transfer"], route["calibrated_mosaic"]]
    body = read_json(collected)
    scene, = calibrated["scenes"]
    original = {item["band"]: (under(platform, item["path"]), item["sha256"]) for item in body["assets"]}
    received = {name: (under(platform, item["path"]), item["sha256"]) for name, item in scene["assets"].items()}
    if (
        body["status"] != "VERIFIED_REAL" or body["execution_status"] != "PILOT_QA_PASS"
        or not body["measurement_complete"] or not body["qa"]["same_scene_all_assets"]
        or (body["province"], body["year"], body["scene_id"].lower())
        != (calibrated["region"], calibrated["year"], scene["source_id"]) or original != received
    ):
        raise ValueError("SENTINEL_COMPLETION_SCOPE_INVALID")
    return calibrated, pins


def sentinel_receipt(platform, route_path):
    route = read_json(route_path)
    windows, pins = [], []
    source_rows = route.get("training_splits", [{"name": "collected-sentinel", "split": "mosaic-only", "source": route}])
    for entry in source_rows:
        mosaic, evidence = sentinel_collected(platform, entry["source"])
        windows.append({"name": entry["name"], "split": entry["split"], "mosaic": mosaic})
        pins += evidence
    source = windows[0]["mosaic"]
    return {"schema_version": RECEIPT_SCHEMA, "year": source["year"], "region": source["region"],
            "windows": windows, "fit_sentinel_candidate": "training_splits" in route,
            "sentinel_followup": route.get("frozen_trial"), "collector_receipts": pins}


def scan(platform, inbox, policy):
    """One trusted operator policy contains allowed collector completion pins."""
    inbox.mkdir(parents=True, exist_ok=True)
    choices = read_json(policy)
    pending = {}
    for row in choices.get("landsat", []):
        authority = Pin.model_validate(row["plan"])
        try:
            plan = read_json(authority.local(platform))
            path = under(platform, DESTINATION / f"{authority.sha256}.complete.json")
            if not path.exists():
                pending[f"landsat-{row['year']}"] = "COLLECTOR_COMPLETION_PENDING"
                continue
            completed = read_json(path)
            expected = {(entry["year"], entry["scene_id"], entry["bytes"], entry["etag"])
                        for entry in plan["assets"]}
            observed = {(entry["year"], entry["scene_id"], entry["qa"]["bytes"], entry["qa"]["etag"])
                        for entry in completed["entries"]}
            if expected != observed or len(observed) != len(completed["entries"]):
                raise ValueError("LANDSAT_COMPLETION_DIFFERS_FROM_APPROVED_PLAN")
            key = f"landsat-qa/1:{digest(path)}:{row['year']}"
            dispatch(inbox, key, partial(landsat_receipt, platform, path, row["year"]))
        except (OSError, ValueError, KeyError) as error:
            pending[f"landsat-{row['year']}"] = str(error).split("\n", 1)[0]
    for source in choices.get("sentinel", []):
        try:
            route = Pin.model_validate(source).local(platform)
            dispatch(inbox, f"sentinel/1:{source['sha256']}", partial(sentinel_receipt, platform, route))
        except (OSError, ValueError, KeyError) as error:
            pending[str(source.get("sha256", "sentinel"))] = str(error).split("\n", 1)[0]
    if choices.get("native"):
        from services.datahub.westjava_native import ROOT
        from services.lcluc.westjava_native_intake import native_batch_receipt

        authority = Pin.model_validate(choices["native"]["approval"])
        authority.local(platform)
        metadata = platform / ROOT / ".intake-metadata"
        metadata.mkdir(exist_ok=True)
        for path in sorted((platform / ROOT).glob("*/*/batch-complete.json")):
            try:
                dispatch(
                    inbox, f"westjava-native/1:{digest(path)}",
                    partial(native_batch_receipt, platform, path, authority.sha256, metadata,
                            supplemental_approval=choices["native"].get("supplemental_approval")),
                )
            except (OSError, ValueError, KeyError, RuntimeError) as error:
                pending[f"native-{path.parent.parent.name}-{path.parent.name}"] = str(error).split("\n", 1)[0]
    for key, reason in pending.items():
        print(f"Collector intake {key} {reason}", flush=True)
    return pending
