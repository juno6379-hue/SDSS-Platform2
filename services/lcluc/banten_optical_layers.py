"""Publish QA-masked Banten whole-province imagery from complete source years."""

import argparse
import json
import time
from contextlib import ExitStack
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.features import geometry_mask
from rasterio.transform import from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling
from shapely.geometry import mapping
from shapely.ops import transform

from services.lcluc.banten_esri_preview import INDEX as ESRI_INDEX
from services.lcluc.banten_esri_preview import WEB
from services.lcluc.banten_optical_qa import complete_years as landsat_complete
from services.lcluc.banten_sentinel_native import NATIVE
from services.lcluc.province_esri import digest, write_json
from services.lcluc.province_optical_plan import DEST, boundary

DIRECTORY = Path("data/curated/explorer/banten-province")
INDEX = DIRECTORY / "annual-optical-display.json"
SENSORS = ("sentinel-2", "landsat")


def sentinel_complete():
    plan = json.loads((DEST / "scene-plan.json").read_bytes())
    result = {}
    for row in plan["entries"]:
        if row["sensor"] != "sentinel-2":
            continue
        year = row["year"]
        paths = [
            (NATIVE / str(year) / item["id"] / "scene-receipt.json", row["required_assets"])
            for item in row["selected"]
        ]
        if all(path.is_file() for path, _ in paths):
            result[year] = paths
    return result


def pinned_window(stack, pin, grid):
    path = Path(pin["path"])
    if path.stat().st_size != pin["bytes"] or digest(path) != pin["sha256"]:
        raise ValueError("BANTEN_OPTICAL_RASTER_PIN_MISMATCH")
    raster = stack.enter_context(rasterio.open(path))
    image = stack.enter_context(
        WarpedVRT(
            raster,
            crs="EPSG:3857",
            **grid,
            src_nodata=0,
            nodata=0,
            resampling=Resampling.nearest,
        )
    )
    return image.read(1)


def preview_year(sensor, year, entries, grid, polygon):
    output = np.zeros((grid["height"], grid["width"], 4), dtype=np.uint8)
    covered = np.zeros(output.shape[:2], dtype=bool)
    inside = geometry_mask(
        [polygon], out_shape=covered.shape, transform=grid["transform"], invert=True
    )
    names = ["red", "green", "blue"]
    qa_name = "scl" if sensor == "sentinel-2" else "qa_pixel"
    sources = []
    for receipt, bands in entries:
        scene = json.loads(receipt.read_bytes())
        if not scene["observed_at"].startswith(str(year)) or set(scene["assets"]) != set(bands):
            raise ValueError("BANTEN_OPTICAL_SCENE_RECEIPT_MISMATCH")
        if sensor == "sentinel-2":
            pin = scene["stac_page"]
            metadata = Path(pin["path"])
            if metadata.stat().st_size != pin["bytes"] or digest(metadata) != pin["sha256"]:
                raise ValueError("BANTEN_OPTICAL_STAC_PIN_MISMATCH")
            item = next(
                i
                for i in json.loads(metadata.read_bytes())["features"]
                if i["id"] == scene["scene"]
            )
        with ExitStack() as stack:
            qa = pinned_window(stack, scene["assets"][qa_name], grid)
            good = (
                np.isin(qa, (4, 5, 6, 7, 11)) if sensor == "sentinel-2" else ((qa & 0b111111) == 0)
            )
            colors = {}
            for name, asset in scene["assets"].items():
                if name == qa_name:
                    continue
                img = pinned_window(stack, asset, grid)
                good &= img > 0
                if name in names:
                    metadata = (
                        item["assets"][name]["raster:bands"][0]
                        if sensor == "sentinel-2"
                        else asset["raster_bands"][0]
                    )
                    scale, offset = metadata["scale"], metadata["offset"]
                    colors[name] = np.rint(
                        np.sqrt((img.astype(np.float32) * scale + offset).clip(0, 0.32) / 0.32)
                        * 255
                    ).astype(np.uint8)
            use = inside & good & ~covered
            for channel, name in enumerate(names):
                output[:, :, channel][use] = colors[name][use]
            output[:, :, 3][use] = 255
            covered |= use
            sources.append(scene["scene"])
    buffer = BytesIO()
    Image.fromarray(output).save(buffer, format="PNG")
    return buffer.getvalue(), sources, int(covered.sum()), int(inside.sum())


def publish():
    esri = json.loads(ESRI_INDEX.read_bytes())
    w, s, e, n = esri["bounds"]
    low = WEB.transform(w, s)
    high = WEB.transform(e, n)
    first_year = next(iter(esri["years"]))
    with Image.open(DIRECTORY / f"esri-{first_year}.png") as display:
        width, height = display.size
    grid = {"width": width, "height": height, "transform": from_bounds(*low, *high, width, height)}
    polygon = mapping(transform(WEB.transform, boundary()))
    old = json.loads(INDEX.read_bytes()) if INDEX.is_file() else {}
    result = {"bounds": esri["bounds"], "sensors": {}}
    ready = {"sentinel-2": sentinel_complete(), "landsat": landsat_complete()}
    for sensor in SENSORS:
        result["sensors"][sensor] = {}
        for year, entries in sorted(ready[sensor].items()):
            version = sha256("".join(digest(path) for path, _ in entries).encode()).hexdigest()
            saved = old.get("sensors", {}).get(sensor, {}).get(str(year), {})
            path = DIRECTORY / f"{sensor}-{year}.png"
            if (
                saved.get("scope_sha256") == version
                and path.is_file()
                and digest(path) == saved["sha256"]
            ):
                result["sensors"][sensor][str(year)] = saved
                continue
            payload, scenes, clear, total = preview_year(sensor, year, entries, grid, polygon)
            temp = path.with_suffix(".png.tmp")
            temp.write_bytes(payload)
            temp.replace(path)
            result["sensors"][sensor][str(year)] = {
                "scope_sha256": version,
                "scene_ids": scenes,
                "bytes": len(payload),
                "sha256": sha256(payload).hexdigest(),
                "display_clear_pct": 100 * clear / total,
            }
            print(
                sensor,
                year,
                len(scenes),
                f"{100 * clear / total:.2f}% clear on display grid",
                flush=True,
            )
    write_json(INDEX, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    while True:
        result = publish()
        if not args.wait or all(len(result["sensors"][sensor]) == 6 for sensor in SENSORS):
            return
        time.sleep(60)


if __name__ == "__main__":
    main()
