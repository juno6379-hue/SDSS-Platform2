"""Acquire bounded historical pilots and publish their Banten Landsat composites."""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from http.client import IncompleteRead
from time import sleep
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
from shapely.ops import transform

from services.lcluc.banten_landsat import PlanetaryComputer, get_asset
from services.lcluc.banten_landsat_explorer import (
    BANDS,
    PROFILES,
    composite,
    context,
    normalize,
    publish,
    validate_band_metadata,
)
from services.lcluc.banten_optical_layers import pinned_window
from services.lcluc.banten_sentinel_explorer import receipt
from services.lcluc.province_esri import write_json
from services.lcluc.province_optical_plan import DEST, PROJECT, PROVIDERS, boundary, pick_items

STAC = DEST / "historical-stac"
NATIVE = DEST / "historical-native"
MAX_BYTES = 500 * 1024**2


def stac_candidates(year, aoi):
    server, collection, _ = PROVIDERS["landsat"]
    query = urlencode({
        "collections": collection, "bbox": ",".join(map(str, aoi.bounds)), "limit": 50,
        "datetime": f"{year}-05-01T00:00:00Z/{year}-11-30T23:59:59Z", "sortby": "+eo:cloud_cover",
    })
    uri = server + "?" + query
    path = STAC / f"{year}.json"
    if not path.is_file():
        with urlopen(uri, timeout=35) as response:
            raw = response.read(12_000_001)
        if len(raw) > 12_000_000:
            raise ValueError("LANDSAT_STAC_RESPONSE_TOO_LARGE")
        write_json(path, json.loads(raw))
    items = json.loads(path.read_bytes())["features"]
    tier1 = [
        item for item in items
        if item["collection"] == collection and item["id"][:4] in PROFILES and item["id"].endswith("_T1")
        and item["properties"]["datetime"].startswith(str(year))
        and (set(BANDS) | {"qa_pixel", "qa_radsat"}).issubset(item["assets"])
        and item["properties"].get("eo:cloud_cover", 100) <= 80
    ]
    return uri, path, items, tier1


def historical_scene(item, folder):
    assets = item["assets"]
    bands = (*BANDS, "qa_pixel", "qa_radsat")
    platform = item["id"][:4]
    pc = PlanetaryComputer()
    total = 0
    for name in bands:
        spec = assets[name]
        if name in BANDS:
            validate_band_metadata(platform, name, spec["href"], spec["raster:bands"])
        with pc.request(spec["href"], method="HEAD") as response:
            total += int(response.headers["Content-Length"])
    if total > MAX_BYTES:
        raise ValueError("LANDSAT_SCENE_OVER_TRANSFER_CAP")
    folder.mkdir(parents=True, exist_ok=True)

    def download(name):
        for delay in (2, 5, 0):
            try:
                asset = get_asset(pc, assets[name], folder / f"{name}.tif")
                print(item["id"], name, asset["bytes"], flush=True)
                return name, asset
            except (IncompleteRead, ConnectionError, TimeoutError, URLError):
                if not delay:
                    raise
                sleep(delay)

    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(pool.map(download, bands))


def annual(year):
    aoi = boundary()
    uri, stac, results, candidates = stac_candidates(year, aoi)
    planned, _ = pick_items(candidates, transform(PROJECT, aoi))
    audit = {"year": year, "query": uri, "stac": receipt(stac), "items_on_first_page": len(results),
             "tier1_candidates_on_first_page": len(candidates)}
    audit_path = stac.with_name(f"{year}.audit.json")
    write_json(audit_path, audit | {"state": "SCENE_CANDIDATES" if planned else "NO_SELECTED_SCENE"})
    if not planned:
        print(year, "no selected scene in this STAC query", flush=True)
        return
    scene_id = planned[0]["id"]
    if not scene_id.replace("_", "").isalnum():
        raise ValueError("LANDSAT_SCENE_ID_INVALID")
    item = next(row for row in candidates if row["id"] == scene_id)
    platform = scene_id[:4]
    folder = NATIVE / str(year) / scene_id
    pins = historical_scene(item, folder)
    report = folder / "scene-receipt.json"
    write_json(report, {"scene": scene_id, "observed_at": item["properties"]["datetime"],
                        "stac": receipt(stac), "assets": pins})
    grid, mask, bounds = context()
    vrt_grid = {key: value for key, value in grid.items() if key != "crs"}
    with ExitStack() as stack:
        bands = np.stack([pinned_window(stack, pins[name], vrt_grid) for name in BANDS])
        qa = pinned_window(stack, pins["qa_pixel"], vrt_grid)
        saturation = pinned_window(stack, pins["qa_radsat"], vrt_grid)
    sources = [{"scene": scene_id, "observed_at": item["properties"]["datetime"], "receipt": receipt(report),
                "band_numbers": PROFILES[platform], "qa_radsat": True}]
    publish(year, composite([normalize(platform, bands, qa, mask, saturation)]), grid, mask, bounds, sources, [year, year])
    write_json(audit_path, audit | {"state": "PUBLISHED", "native_bytes": sum(pin["bytes"] for pin in pins.values())})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="+", type=int)
    args = parser.parse_args()
    STAC.mkdir(parents=True, exist_ok=True)
    failures = 0
    with ThreadPoolExecutor(max_workers=3) as pool:
        for year, future in zip(args.years, [pool.submit(annual, year) for year in args.years], strict=True):
            try:
                future.result()
            except (OSError, ValueError, RuntimeError) as error:
                failures += 1
                print(year, type(error).__name__, str(error).split("?")[0], flush=True)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
