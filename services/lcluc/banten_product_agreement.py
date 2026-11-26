"""Compare the same-year WorldCover and Esri maps within the pinned Banten boundary."""

import argparse
import json
from contextlib import ExitStack
from datetime import date
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from services.lcluc.banten_sentinel_explorer import ROOT, THEMATIC
from services.lcluc.province_esri import SNAPSHOT_SHA256, digest, write_json

YEAR = 2021
OUTPUT = Path("data/curated/explorer/banten-province/esri-worldcover-2021-agreement.json")
SOURCE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
TILES = {
    "S06E105": "1e4ed09caa49f02b6888292b41e21cbf73cccaf8df77109062921c6f91de012a",
    "S09E105": "2578bd221a6817c939222c5e1cc1727f994f675483d3579c057d1e4ccb642f39",
}
# Six broad map concepts. Wetland, mangrove, snow and moss/lichen are outside this comparison.
CROSSWALK = (
    ("Water", 1, (80,)),
    ("Tree cover", 2, (10,)),
    ("Cropland", 5, (40,)),
    ("Built area", 7, (50,)),
    ("Bare ground", 8, (60,)),
    ("Grass or shrub", 11, (20, 30)),
)


def agreement(worldcover, acquired_on):
    reference = json.loads((ROOT / str(YEAR) / "land-cover.json").read_bytes())
    esri_path = Path(reference["raster"]["path"])
    if (reference["source"]["year"] != YEAR or reference["source"]["boundary_sha256"] != SNAPSHOT_SHA256
            or digest(esri_path) != reference["raster"]["sha256"]):
        raise ValueError("2021 Esri source or boundary fingerprint changed")
    pins = []
    for tile, sha in TILES.items():
        name = f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
        path = worldcover / name
        if digest(path) != sha:
            raise ValueError(f"2021 WorldCover tile changed: {name}")
        pins.append({"path": path.as_posix(), "uri": f"{SOURCE}/{name}", "sha256": sha,
                     "bytes": path.stat().st_size, "acquired_on": acquired_on.isoformat()})

    esri_keys = np.zeros(256, dtype="uint8")
    esa_keys = np.zeros(256, dtype="uint8")
    for index, (_, esri_code, esa_codes) in enumerate(CROSSWALK, 1):
        esri_keys[esri_code] = index
        esa_keys[list(esa_codes)] = index
    size = len(CROSSWALK) + 1
    counts = np.zeros((size, size), dtype="int64")
    both_valid = 0
    with ExitStack() as stack:
        esri = stack.enter_context(rasterio.open(esri_path))
        if esri.crs.to_epsg() != 6933 or esri.res != (10, 10) or esri.nodata != 0:
            raise ValueError("expected the Esri 10 m equal-area grid")
        grid = {"crs": esri.crs, "transform": esri.transform, "width": esri.width, "height": esri.height}
        esa = []
        for pin in pins:
            tile = stack.enter_context(rasterio.open(pin["path"]))
            if tile.crs.to_epsg() != 4326 or tile.count != 1 or tile.dtypes != ("uint8",):
                raise ValueError("expected the native WorldCover map grid")
            esa.append(stack.enter_context(WarpedVRT(tile, **grid, nodata=0, resampling=Resampling.nearest)))
        for _, window in esri.block_windows(1):
            left = esri.read(1, window=window)
            if not left.any():
                continue
            right = esa[0].read(1, window=window)
            fill = esa[1].read(1, window=window)
            right[right == 0] = fill[right == 0]
            valid = np.isin(left, THEMATIC) & np.isin(right, (10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100))
            both_valid += int(valid.sum())
            codes = esri_keys[left[valid]].astype("int16") * size + esa_keys[right[valid]]
            counts += np.bincount(codes, minlength=size * size).reshape(size, size)

    comparison = counts[1:, 1:]
    comparable = int(comparison.sum())
    if not comparable:
        raise ValueError("WorldCover and Esri have no comparable Banten pixels")
    return {
        "region": "banten", "year": YEAR, "scope": "province_boundary",
        "boundary_sha256": SNAPSHOT_SHA256, "grid_crs": "EPSG:6933", "grid_resolution_m": 10,
        "resampling": "nearest", "independent_accuracy_measured": False,
        "all_common_thematic_ha": both_valid / 100, "compared_ha": comparable / 100,
        "excluded_by_crosswalk_ha": (both_valid - comparable) / 100,
        "overall_map_agreement_pct": 100 * int(comparison.trace()) / comparable,
        "classes": [{"name": name, "esri_code": code, "worldcover_codes": codes}
                    for name, code, codes in CROSSWALK],
        "matrix_ha": (comparison / 100).tolist(),
        "esri": reference["source"], "worldcover_tiles": pins,
        "worldcover_source": "https://doi.org/10.5281/zenodo.7254221",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worldcover", type=Path)
    parser.add_argument("--acquired-on", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    write_json(OUTPUT, agreement(args.worldcover, args.acquired_on))


if __name__ == "__main__":
    main()
