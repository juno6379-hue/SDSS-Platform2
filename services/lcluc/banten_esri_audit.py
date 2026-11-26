"""Measure Esri agreement between years over Banten's pinned equal-area 10 m AOI."""

import argparse
import time
from contextlib import ExitStack
from itertools import combinations
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

from services.lcluc.province_esri import (
    DEST,
    SNAPSHOT_SHA256,
    YEAR_ENDS,
    YEARS,
    acquire,
    write_json,
)
from services.lcluc.province_optical_plan import PROJECT, boundary
from services.lcluc.taxonomy import load_taxonomy

REPORT = Path("data/curated/explorer/banten-province/esri-coverage-and-change.json")


def verified_sources(years=YEARS):
    taxonomy = load_taxonomy("esri-io-v003")
    raws = {}
    for year in years:
        end = YEAR_ENDS.get(year, f"{year + 1}0101")
        receipt = DEST / str(year) / f"48M_{year}0101-{end}.receipt.json"
        if receipt.is_file():
            # An existing receipt makes acquire a local integrity check.
            raws[year] = acquire("48M", year, taxonomy.sha256)
    return taxonomy, raws


def statistics(selected_years=None):
    taxonomy, sources = verified_sources(YEARS if selected_years is None else selected_years)
    from services.api.lcluc_cases import ESRI_PALETTE
    from services.lcluc.banten_esri_preview import publish_province_previews

    if selected_years is not None and set(sources) != set(selected_years):
        raise FileNotFoundError("Requested province annual Esri TIFFs are incomplete")
    if not sources:
        raise FileNotFoundError("No verified 48M source TIFFs")
    source_geometry = boundary()
    if selected_years is None:
        publish_province_previews(source_geometry, sources, ESRI_PALETTE)
    region = transform(PROJECT, source_geometry)
    shape = mapping(region)
    xmin, ymin, xmax, ymax = region.bounds
    west, north = 10 * floor(xmin / 10), 10 * ceil(ymax / 10)
    width, height = ceil((xmax - west) / 10), ceil((north - ymin) / 10)
    affine = from_origin(west, north, 10, 10)
    allowed = np.array([taxonomy.nodata, *taxonomy.codes], dtype=np.uint8)
    codes = tuple(sorted(set(taxonomy.codes) - set(taxonomy.qa_codes)))
    years = list(sources)
    histograms = {year: np.zeros(12, dtype=np.int64) for year in years}
    matrices = {pair: np.zeros((12, 12), dtype=np.int64) for pair in combinations(years, 2)}
    aoi_pixels = 0
    with ExitStack() as stack:
        opened = {}
        for year, pin in sources.items():
            raw = stack.enter_context(rasterio.open(pin["path"]))
            opened[year] = stack.enter_context(
                WarpedVRT(
                    raw,
                    crs="EPSG:6933",
                    transform=affine,
                    width=width,
                    height=height,
                    src_nodata=taxonomy.nodata,
                    nodata=taxonomy.nodata,
                    resampling=Resampling.nearest,
                )
            )
        for row in range(0, height, 512):
            for col in range(0, width, 512):
                window = Window(col, row, min(width - col, 512), min(height - row, 512))
                mask = geometry_mask(
                    [shape],
                    out_shape=(int(window.height), int(window.width)),
                    transform=rasterio.windows.transform(window, affine),
                    invert=True,
                )
                count = int(mask.sum())
                if not count:
                    continue
                aoi_pixels += count
                values = {}
                for year, raster in opened.items():
                    labels = raster.read(1, window=window)[mask]
                    if not np.isin(labels, allowed).all():
                        raise ValueError(f"Unexpected Esri code in {year}")
                    histograms[year] += np.bincount(labels, minlength=12)
                    values[year] = labels
                for a, b in matrices:
                    flat = values[a].astype(np.uint16) * 12 + values[b]
                    matrices[(a, b)] += np.bincount(flat, minlength=144).reshape(12, 12)

    pair_rows = []
    for (a, b), transitions in matrices.items():
        thematic = transitions[np.ix_(codes, codes)]
        common = int(thematic.sum())
        changed = common - int(thematic.trace())
        pair_rows.append(
            {
                "from_year": a,
                "to_year": b,
                "common_valid_area_ha": common / 100,
                "changed_area_ha": changed / 100,
                "change_rate_pct": 100 * changed / common if common else None,
                "transition_matrix_ha": (thematic / 100).tolist(),
            }
        )

    report = {
        "region": "banten",
        "source": "Esri / Impact Observatory v003 48M COG",
        "boundary_sha256": SNAPSHOT_SHA256,
        "grid_crs": "EPSG:6933",
        "grid_resolution_m": 10,
        "aoi_polygon_area_ha": region.area / 10_000,
        "aoi_pixel_center_area_ha": aoi_pixels / 100,
        "polygon_rule": "pixel_center",
        "boundary_approval": "PROJECT_STATISTICS_PENDING",
        "validation": "Esri annual-map comparison; independent accuracy unmeasured",
        "classes": list(codes),
        "annual": [
            {
                "year": year,
                "source_pin": pin,
                "area_ha_by_source_code": {
                    str(code): int(histograms[year][code]) / 100 for code in allowed
                },
                "native_class_or_cloud_pct": 100
                * (aoi_pixels - int(histograms[year][taxonomy.nodata]))
                / aoi_pixels,
                "thematic_valid_pct": 100 * int(histograms[year][list(codes)].sum()) / aoi_pixels,
            }
            for year, pin in sources.items()
        ],
        "pairs": pair_rows,
    }
    if selected_years is None:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        write_json(REPORT, report)
    print(
        f"Banten verified at 10m: {len(years)} years, {len(pair_rows)} pairs, {aoi_pixels / 100:,.2f} ha",
        flush=True,
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-for-collection", action="store_true")
    args = parser.parse_args()
    if not args.wait_for_collection:
        statistics()
        return
    print("Waiting for complete native 48M source receipts", flush=True)
    last_count = 0
    while last_count < len(YEARS):
        current = sum(any((DEST / str(year)).glob("48M_*.receipt.json")) for year in YEARS)
        if current > last_count:
            statistics()
            last_count = current
        if current == len(YEARS):
            return
        if not (DEST / "collector.lock").exists():
            raise SystemExit("Esri collection exited with Banten annual sources outstanding")
        time.sleep(45)


if __name__ == "__main__":
    main()
