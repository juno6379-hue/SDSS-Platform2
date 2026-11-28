"""Measure retained optical pixels and plan West Java collection without downloading imagery."""

import argparse
import json
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from statistics import median
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
from pyproj import Transformer
from rasterio.features import geometry_mask, shapes
from shapely.geometry import mapping, shape
from shapely.ops import transform, unary_union

from services.datahub.westjava_inventory import (
    HELD_DIR,
    OPTICAL_DIR,
    PILOT_BATCHES,
    current_ledger,
    full_scenes,
    geographic_inputs,
    read_json,
    under,
    verify_file,
)
from services.lcluc.annual import store_json
from services.lcluc.annual_inputs import Bands
from services.lcluc.annual_rasters import equal_area_grid, warp
from services.lcluc.classifiers import CLEAR_SCL
from services.lcluc.province_esri import YEARS, digest, utc
from services.lcluc.province_optical_plan import PROJECT, PROVIDERS, optical_candidates, pick_items
from services.lcluc.regional_mosaic import LANDSAT_RADSAT_MASK
from services.lcluc.regional_trials import scene_identity

GRID = 250
UNPROJECT = Transformer.from_crs(6933, 4326, always_xy=True).transform
CERTAIN = ["physical", "qualified"]


def collection_sources(root, legacy, aoi):
    scenes, sizes, scene_ids = defaultdict(list), defaultdict(list), defaultdict(set)
    for sensor, (_, _, names) in PROVIDERS.items():
        for (_, year), records in full_scenes(
            root, {"west_java": aoi}, sensor, rehash_large_assets=False,
        ).items():
            for row, _ in records:
                prior = read_json(under(root, row["receipt"]["path"]))
                assets = prior["assets"]
                radsat = assets.get("qa_radsat")
                if sensor == "landsat" and radsat is None:
                    from services.datahub.westjava_landsat_qa import DESTINATION

                    supplement = root / DESTINATION / str(year) / row["scene_id"] / "qa-supplement.json"
                    if supplement.is_file():
                        body = read_json(supplement)
                        if body["scene_receipt"] != row["receipt"] or body["stac_page"] != row["stac_page"]:
                            raise ValueError("QA_SUPPLEMENT_DOES_NOT_MATCH_SCENE")
                        radsat = body["qa"]
                        verify_file(under(root, radsat["path"]), radsat)
                qa = under(root, radsat["path"]) if radsat else None
                paths = [under(root, assets[name]["path"]) for name in names]
                scenes[sensor, year].append((paths, qa))
                sizes[sensor].append(sum(assets[name]["bytes"] for name in names) + (radsat or {}).get("bytes", 0))
                scene_ids[sensor, year].add(row["scene_id"])
    roots = legacy / "data/first-group-training-esri-v1/sources"
    window_sizes = []
    for checkpoint in sorted((root / HELD_DIR / "native-checkpoints").glob("*.json")):
        row = read_json(checkpoint)
        if row["province"] != "west_java":
            continue
        folder = under(roots, Path(row["parent_path"]).parent)
        checked = {Path(item["path"]).name: item for item in row["verified_files"]
                   if Path(item["path"]).parent.resolve() == folder}
        names = [f"raw-{name}.tif" for name in ("B02", "B03", "B04", "B08", "B11", "B12", "SCL")]
        if set(names).issubset(checked):
            paths = [folder / name for name in names]
            for path in paths:
                verify_file(path, checked[path.name])
            scenes["sentinel-2", row["year"]].append((paths, None))
    for receipt in sorted((root / PILOT_BATCHES).glob("*/steps/*/transfer/result.json")):
        row = read_json(receipt)
        if row.get("province") != "west_java" or row.get("execution_status") != "PILOT_QA_PASS":
            continue
        if not row["measurement_complete"] or not row["qa"]["same_scene_all_assets"]:
            raise ValueError("SENTINEL_TRANSFER_RECEIPT_INVALID")
        bands = {asset["band"]: asset for asset in row["assets"]}
        paths = []
        for name in ("B02", "B03", "B04", "B08", "B11", "B12", "SCL"):
            entry = bands[name]
            path = under(root, entry["path"])
            verify_file(path, entry)
            paths.append(path)
        scenes["sentinel-2", row["year"]].append((paths, None))
        window_sizes.append(row["remote_body_bytes_read"] / (row["qa"]["pixel_count"] * 100))
    return scenes, sizes, scene_ids, window_sizes


def pixel_support(sensor, grid, inside, sources):
    present = np.zeros_like(inside)
    eligible = np.zeros_like(inside)
    for paths, saturation in sources:
        with ExitStack() as stack:
            qa = warp(stack, paths[-1], grid, quality=True, nodata=0 if sensor == "sentinel-2" else 1).read(1)
            if sensor == "sentinel-2":
                valid = inside & (qa != 0)
                clear = np.isin(qa, tuple(CLEAR_SCL))
            else:
                valid = inside & ((qa & 1) == 0)
                clear = ((qa & 0b111111) == 0) if saturation else np.zeros_like(valid)
                if saturation:
                    flags = warp(stack, saturation, grid, quality=True).read(1)
                    clear &= (flags & LANDSAT_RADSAT_MASK) == 0
            for path in paths[:-1]:
                valid &= warp(stack, path, grid).read(1) > 0
            present |= valid
            eligible |= valid & clear
    return present, eligible


def remote_candidates(root, sensor, year, bbox, output, *, suffix=""):
    _, collection, _ = PROVIDERS[sensor]
    url = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
    params = {"collections": collection, "bbox": ",".join(map(str, bbox)), "limit": 100,
              "datetime": f"{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z", "sortby": "+eo:cloud_cover"}
    with urlopen(url + "?" + urlencode(params), timeout=20) as response:
        raw = response.read(12 * 1024 * 1024 + 1)
    if len(raw) > 12 * 1024 * 1024:
        raise ValueError("OPTICAL_CATALOG_PAGE_TOO_LARGE")
    page = json.loads(raw)
    file = output / f"{sensor}-{year}{suffix}.stac.json"
    file.write_bytes(raw)
    if sensor == "sentinel-2":
        required = {*Bands[sensor], "SCL", "product-metadata"}
        candidates = [item for item in page["features"]
                      if item["collection"] == collection
                      and item["properties"]["datetime"][:4] == str(year)
                      and item["properties"].get("platform", "").lower() in {"sentinel-2a", "sentinel-2b", "sentinel-2c"}
                      and required.issubset(item["assets"])]
    else:
        candidates = optical_candidates(page, sensor, year)
    return candidates, {
        "source": url, "path": file.relative_to(root).as_posix(), "sha256": digest(file),
        "scope": "pinned_bounded_west_java_candidates",
        "next_page_available": any(link.get("rel") == "next" for link in page.get("links", ())),
    }


def planning_page(root, sensor, year, aoi_card, output, live):
    if live:
        try:
            return remote_candidates(root, sensor, year, aoi_card["bbox_crs84"], output)
        except (OSError, ValueError, KeyError) as error:
            failure = type(error).__name__
    else:
        failure = None
    plan = read_json(root / OPTICAL_DIR / "scene-plan.json")
    entry = next(row for row in plan["entries"] if (row["sensor"], row["year"]) == (sensor, year))
    path = under(root, entry["pinned_stac"]["path"])
    verify_file(path, entry["pinned_stac"])
    return optical_candidates(read_json(path), sensor, year), {
        "scope": "pinned_banten_catalog_fallback", "west_java_search_error": failure,
        "sha256": entry["pinned_stac"]["sha256"],
    }


def run(root, legacy, output, *, live=False):
    regions, cards = geographic_inputs(root)
    aoi, card = regions["west_java"], cards["west_java"]
    grid = equal_area_grid(aoi, GRID)
    inside = geometry_mask([mapping(aoi)], (grid["height"], grid["width"]), grid["transform"], invert=True)
    scenes, sizes, held_ids, transfer_density = collection_sources(root, legacy, aoi)
    output.mkdir(parents=True, exist_ok=True)
    metrics, layers = [], []
    for year in YEARS:
        for sensor in PROVIDERS:
            present, qualified = pixel_support(sensor, grid, inside, scenes[sensor, year])
            gaps = {}
            for kind, available in zip(CERTAIN, (present, qualified), strict=True):
                missing = inside & ~available
                area = unary_union([
                    shape(polygon) for polygon, _ in shapes(
                        missing.astype("uint8"), mask=missing, transform=grid["transform"],
                    )
                ]).intersection(aoi)
                gaps[kind] = area
                layers.append({"type": "Feature", "geometry": mapping(transform(UNPROJECT, area)),
                               "properties": {"sensor": sensor, "year": year, "gap": kind,
                                              "area_km2": round(area.area / 1000000, 2)}})
            candidates, page = planning_page(root, sensor, year, card, output, live)
            known = {scene_identity(identity) for identity in held_ids[sensor, year]}
            candidates = [
                item for item in candidates if scene_identity(item["id"]) not in known
                and (sensor != "landsat" or "qa_radsat" in item["assets"])
            ]
            chosen, residual = pick_items(candidates, gaps["physical"])
            basis = median(sizes[sensor])
            density = median(transfer_density) if transfer_density and sensor == "sentinel-2" else None
            metrics.append({
                "sensor": sensor, "year": year, "held_scenes_and_windows": len(scenes[sensor, year]),
                "present_sample_pct": 100 * float(present.sum()) / inside.sum(),
                "quality_eligible_sample_pct": 100 * float(qualified.sum()) / inside.sum(),
                "missing_physical_km2": gaps["physical"].area / 1000000,
                "missing_quality_km2": gaps["qualified"].area / 1000000,
                "candidate_catalog": page, "selected": chosen,
                "residual_after_selected_footprints_km2": residual / 1000000,
                "scene_median_compressed_bytes": basis,
                "selected_whole_scene_estimated_bytes": round(len(chosen) * basis),
                "sentinel_window_body_estimated_bytes": (
                    round(gaps["physical"].area * density) if density is not None else None
                ),
                "estimated_bytes_are_unapproved_and_not_a_cap": True,
            })
            print(sensor, year, round(gaps["physical"].area / 1000000, 2),
                  len(chosen), round(residual / 1000000, 2), flush=True)
    store_json(output / "westjava-optical-gaps.geojson", {"type": "FeatureCollection", "features": layers})
    store_json(output / "westjava-optical-gaps.json", {
        "schema_version": "sdss-westjava-optical-gaps/1", "observed_at": utc(),
        "region": card, "analysis_grid_m": GRID, "pixel_method": "nearest_cell_center",
        "year_scope": [min(YEARS), max(YEARS)], "ledger": current_ledger(legacy), "entries": metrics,
    })


def refresh_catalog(root, report_path, output):
    """Replan from the saved gap shapes when acquisition metadata changes."""
    report = read_json(report_path)
    geometry = read_json(report_path.with_suffix(".geojson"))
    gaps = {(item["properties"]["sensor"], item["properties"]["year"]):
            transform(PROJECT, shape(item["geometry"])) for item in geometry["features"]
            if item["properties"]["gap"] == "physical"}
    known = {}
    aoi = geographic_inputs(root)[0]["west_java"]
    for sensor in PROVIDERS:
        records = full_scenes(root, {"west_java": aoi}, sensor, rehash_large_assets=False)
        for (_, year), rows in records.items():
            known[sensor, year] = {scene_identity(item["scene_id"]) for item, _ in rows}
    output.mkdir(parents=True, exist_ok=True)
    for row in report["entries"]:
        sensor, year = row["sensor"], row["year"]
        candidates, page = planning_page(root, sensor, year, report["region"], output, True)
        chosen, residual = pick_items([
            item for item in candidates if scene_identity(item["id"]) not in known.get((sensor, year), ())
            and (sensor != "landsat" or "qa_radsat" in item["assets"])
        ], gaps[sensor, year])
        row.update(candidate_catalog=page, selected=chosen, residual_after_selected_footprints_km2=residual / 1e6,
                   selected_whole_scene_estimated_bytes=round(len(chosen) * row["scene_median_compressed_bytes"]))
        print(sensor, year, page["scope"], len(chosen), round(residual / 1e6, 2), flush=True)
    store_json(output / report_path.name, report)
    store_json(output / report_path.with_suffix(".geojson").name, geometry)


def close_catalog_gaps(root, report_path, output):
    """Search the residual bboxes where the first candidate page left a significant gap."""
    report = read_json(report_path)
    geometry = read_json(report_path.with_suffix(".geojson"))
    shapes_by_scope = {(feature["properties"]["sensor"], feature["properties"]["year"]):
                       shape(feature["geometry"]) for feature in geometry["features"]
                       if feature["properties"]["gap"] == "physical"}
    aoi = geographic_inputs(root)[0]["west_java"]
    known = {
        (sensor, year): {scene_identity(item["scene_id"]) for item, _ in rows}
        for sensor in PROVIDERS for (_, year), rows in full_scenes(
            root, {"west_java": aoi}, sensor, rehash_large_assets=False,
        ).items()
    }
    output.mkdir(parents=True, exist_ok=True)
    for row in report["entries"]:
        if row["residual_after_selected_footprints_km2"] <= 0.25 or "path" not in row["candidate_catalog"]:
            continue
        sensor, year = row["sensor"], row["year"]
        selected = {entry["id"] for entry in row["selected"]}
        page = read_json(under(root, row["candidate_catalog"]["path"]))
        existing = unary_union([
            transform(PROJECT, shape(item["geometry"])) for item in page["features"] if item["id"] in selected
        ])
        gap = transform(PROJECT, shapes_by_scope[sensor, year]).difference(existing)
        bbox = transform(UNPROJECT, gap).bounds
        candidates, evidence = remote_candidates(root, sensor, year, bbox, output, suffix="-residual")
        excluded = known.get((sensor, year), set()) | {scene_identity(identity) for identity in selected}
        additional, residual = pick_items([
            item for item in candidates if scene_identity(item["id"]) not in excluded
            and (sensor != "landsat" or "qa_radsat" in item["assets"])
        ], gap)
        row["selected"].extend(additional)
        row["residual_after_selected_footprints_km2"] = residual / 1e6
        row["selected_whole_scene_estimated_bytes"] = round(len(row["selected"]) * row["scene_median_compressed_bytes"])
        row["targeted_residual_catalog"] = evidence
        print(sensor, year, len(additional), round(residual / 1e6, 2), flush=True)
    store_json(output / report_path.name, report)
    store_json(output / report_path.with_suffix(".geojson").name, geometry)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live-catalog", action="store_true")
    parser.add_argument("--refresh-from", type=Path)
    parser.add_argument("--close-gaps-from", type=Path)
    arguments = parser.parse_args()
    if arguments.close_gaps_from:
        close_catalog_gaps(Path.cwd(), arguments.close_gaps_from, arguments.output.resolve())
    elif arguments.refresh_from:
        refresh_catalog(Path.cwd(), arguments.refresh_from, arguments.output.resolve())
    else:
        run(Path.cwd(), arguments.reference_root.resolve(), arguments.output.resolve(), live=arguments.live_catalog)


if __name__ == "__main__":
    main()
