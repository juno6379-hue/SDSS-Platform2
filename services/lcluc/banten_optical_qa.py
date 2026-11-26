"""Measure Banten Landsat six-band footprint and clear support against same-year Esri."""

import argparse
import json
import time
from contextlib import ExitStack
from math import ceil, floor
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling
from rasterio.windows import Window
from shapely.geometry import mapping
from shapely.ops import transform

from services.lcluc.banten_esri_audit import verified_sources
from services.lcluc.banten_landsat import SCENES, acquisition_plan
from services.lcluc.province_esri import SNAPSHOT_SHA256, digest, write_json
from services.lcluc.province_optical_plan import PROJECT, boundary

REPORT = Path("data/curated/explorer/banten-province/landsat-esri-support.json")
SENTINEL_REPORT = REPORT.with_name("sentinel-esri-support.json")
SCALE = 30


def complete_years():
    planned = {}
    for year, item, bands, _ in acquisition_plan():
        path = SCENES / str(year) / item["id"] / "scene-receipt.json"
        planned.setdefault(year, []).append((path, bands))
    return {
        year: entries
        for year, entries in planned.items()
        if all(path.is_file() for path, _ in entries)
    }


def audited_windows(year, entries, esri, grid, geometry, *, sensor="landsat"):
    is_sentinel = sensor == "sentinel-2"
    qa_band = "scl" if is_sentinel else "qa_pixel"
    counts = {
        "boundary": 0,
        "six_band_present": 0,
        "clear_optical": 0,
        "esri_thematic": 0,
        "clear_and_esri_thematic": 0,
    }
    with ExitStack() as stack:

        def open_pin(pin):
            path = Path(pin["path"])
            if path.stat().st_size != pin["bytes"] or digest(path) != pin["sha256"]:
                raise ValueError("Source raster pin mismatch")
            source = stack.enter_context(rasterio.open(path))
            return stack.enter_context(
                WarpedVRT(
                    source,
                    **grid,
                    src_nodata=0,
                    nodata=0,
                    resampling=Resampling.nearest,
                )
            )

        scenes = []
        for receipt, expected in entries:
            item = json.loads(receipt.read_text(encoding="utf-8"))
            if not item["observed_at"].startswith(str(year)) or set(item["assets"]) != set(
                expected
            ):
                raise ValueError("Incomplete or out-of-year Landsat receipt")
            bands = {band: open_pin(pin) for band, pin in item["assets"].items()}
            qa = bands.pop(qa_band)
            scenes.append((qa, tuple(bands.values())))
        reference = open_pin(esri) if esri else None
        width, height = grid["width"], grid["height"]
        for row in range(0, height, 512):
            for col in range(0, width, 512):
                window = Window(col, row, min(width - col, 512), min(height - row, 512))
                shape = int(window.height), int(window.width)
                aoi = geometry_mask(
                    [geometry],
                    out_shape=shape,
                    invert=True,
                    transform=rasterio.windows.transform(window, grid["transform"]),
                )
                if not aoi.any():
                    continue
                present = np.zeros(shape, dtype=bool)
                clear = np.zeros(shape, dtype=bool)
                for qa, bands in scenes:
                    quality = qa.read(1, window=window)
                    valid = quality > 0 if is_sentinel else (quality & 1) == 0
                    for band in bands:
                        valid &= band.read(1, window=window) > 0
                    present |= valid
                    clear |= valid & (
                        np.isin(quality, (4, 5, 6, 7, 11))
                        if is_sentinel
                        else ((quality & 0b111110) == 0)
                    )
                counts["boundary"] += int(aoi.sum())
                counts["six_band_present"] += int((aoi & present).sum())
                counts["clear_optical"] += int((aoi & clear).sum())
                if reference:
                    thematic = np.isin(reference.read(1, window=window), (1, 2, 4, 5, 7, 8, 9, 11))
                    counts["esri_thematic"] += int((aoi & thematic).sum())
                    counts["clear_and_esri_thematic"] += int((aoi & thematic & clear).sum())
    return {
        "year": year,
        "optical_scene_receipts": len(entries),
        "esri_same_year_present": reference is not None,
        "areas_ha": {key: value * SCALE**2 / 10_000 for key, value in counts.items()},
        f"{'sentinel' if is_sentinel else 'landsat'}_clear_pct": 100
        * counts["clear_optical"]
        / counts["boundary"],
        "six_band_present_pct": 100 * counts["six_band_present"] / counts["boundary"],
        "joint_support_pct": 100 * counts["clear_and_esri_thematic"] / counts["boundary"]
        if esri
        else None,
    }


def audit(results, *, sensor="landsat"):
    report_path = SENTINEL_REPORT if sensor == "sentinel-2" else REPORT
    region = transform(PROJECT, boundary())
    w, s, e, n = region.bounds
    w, n = SCALE * floor(w / SCALE), SCALE * ceil(n / SCALE)
    grid = {
        "crs": "EPSG:6933",
        "transform": from_origin(w, n, SCALE, SCALE),
        "width": ceil((e - w) / SCALE),
        "height": ceil((n - s) / SCALE),
    }
    _, esri = verified_sources()
    reports = [
        audited_windows(year, entries, esri.get(year), grid, mapping(region), sensor=sensor)
        for year, entries in results.items()
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        report_path,
        {
            "boundary_sha256": SNAPSHOT_SHA256,
            "region": "banten",
            "grid_resolution_m": SCALE,
            "sensor": sensor,
            "profile": "six-band native data and QA clear support, same-year Esri class support",
            "semantic_agreement_measured": False,
            "independent_accuracy_measured": False,
            "annual": reports,
        },
    )
    print(f"Banten optical support validated for {len(reports)} years", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-for-collection", action="store_true")
    parser.add_argument("--sensor", choices=("landsat", "sentinel-2"), default="landsat")
    args = parser.parse_args()
    ready_years = complete_years
    lock = SCENES / "collector.lock"
    if args.sensor == "sentinel-2":
        from services.lcluc.banten_optical_layers import sentinel_complete
        from services.lcluc.banten_sentinel_native import NATIVE

        ready_years = sentinel_complete
        lock = NATIVE / "collector.lock"
    if not args.wait_for_collection:
        if not (ready := ready_years()):
            raise SystemExit("No complete Banten Landsat year")
        audit(ready, sensor=args.sensor)
        return
    print(f"Waiting for complete annual Banten {args.sensor} receipts", flush=True)
    last_ready = set()
    while True:
        ready = ready_years()
        if set(ready) != last_ready:
            audit(ready, sensor=args.sensor)
            last_ready = set(ready)
        if len(ready) == 6 or not lock.exists():
            return
        time.sleep(45)


if __name__ == "__main__":
    main()
