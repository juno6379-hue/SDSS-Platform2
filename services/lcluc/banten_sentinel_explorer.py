"""Publish pinned Sentinel optical and Esri reference assets over the Banten AOI."""

import argparse
import json
from contextlib import ExitStack
from itertools import combinations
from math import ceil, floor
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.features import geometry_mask
from rasterio.transform import from_bounds, from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling
from rasterio.windows import transform as window_transform
from shapely.geometry import mapping
from shapely.ops import transform

from services.lcluc.annual import worker_lock
from services.lcluc.annual_rasters import atomic_output, raster_profile, windows
from services.lcluc.banten_esri_audit import REPORT
from services.lcluc.banten_esri_preview import INDEX, WEB
from services.lcluc.banten_optical_layers import sentinel_complete
from services.lcluc.classifiers import CLEAR_SCL
from services.lcluc.province_esri import SNAPSHOT_SHA256, digest, write_json
from services.lcluc.province_optical_plan import PROJECT, boundary

ROOT = REPORT.parent / "sentinel-explore"
BANDS = ("blue", "green", "red", "nir", "swir16", "swir22")
BAND_RESOLUTION = dict(zip((*BANDS, "scl"), (10, 10, 10, 10, 20, 20, 20), strict=True))
SPECTRAL_DESCRIPTIONS = ("B02", "B03", "B04", "B08", "B11", "B12", "NDVI", "NDWI", "NBR", "QA")
COMPOSITES = {"natural": (3, 2, 1), "infrared": (4, 3, 2)}
INDICES = {"ndvi": 7, "ndwi": 8, "nbr": 9}
LAYERS = (*COMPOSITES, *INDICES, "quality")
THEMATIC = (1, 2, 4, 5, 7, 8, 9, 11)
QUALITY_PALETTE = {1: (247, 241, 210, 205), 2: (97, 105, 191, 220), 3: (154, 159, 171, 185)}


def grid_for(geom, scale):
    west, south, east, north = geom.bounds
    left, top = scale * floor(west / scale), scale * ceil(north / scale)
    return {"crs": "EPSG:6933", "width": ceil((east - left) / scale),
            "height": ceil((top - south) / scale), "transform": from_origin(left, top, scale, scale)}


def read_vrt(stack, path, grid):
    source = stack.enter_context(rasterio.open(path))
    return stack.enter_context(WarpedVRT(
        source, **grid, src_nodata=0, nodata=0, resampling=Resampling.nearest,
    ))


def check_pin(pin):
    path = Path(pin["path"])
    if path.stat().st_size != pin["bytes"] or digest(path) != pin["sha256"]:
        raise ValueError(f"BANTEN_EXPLORER_SOURCE_MISMATCH: {path.name}")
    return path


def receipt(path):
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}


def scene_inputs(stack, entries, year, grid):
    results = []
    for path, required in entries:
        detail = json.loads(path.read_bytes())
        assets = detail["assets"]
        if detail["observed_at"][:4] != str(year) or assets.keys() != set(required):
            raise ValueError("BANTEN_EXPLORER_SCENE_MISMATCH")
        stac = json.loads(check_pin(detail["stac_page"]).read_bytes())
        item = next(item for item in stac["features"] if item["id"] == detail["scene"])
        opened = {}
        for name in (*BANDS, "scl"):
            raw = check_pin(assets[name])
            if assets[name]["native_grid"]["resolution"] != [BAND_RESOLUTION[name]] * 2:
                raise ValueError("BANTEN_EXPLORER_NATIVE_RESOLUTION_MISMATCH")
            opened[name] = read_vrt(stack, raw, grid)
        metadata = [item["assets"][name]["raster:bands"][0] for name in BANDS]
        scale = np.asarray([row["scale"] for row in metadata], dtype="float32")
        offset = np.asarray([row["offset"] for row in metadata], dtype="float32")
        results.append((detail, opened, scale, offset))
    return sorted(results, key=lambda scene: (scene[0]["observed_at"], scene[0]["scene"]))


def ratio(a, b):
    total = a + b
    return np.divide(a - b, total, out=np.full_like(a, np.nan), where=(a >= 0) & (b >= 0) & (total > 0))


def spectral_block(scenes, window, inside):
    selected = np.zeros(inside.shape, dtype=bool)
    cloud = np.zeros_like(selected)
    shadow = np.zeros_like(selected)
    values = np.full((10, *inside.shape), np.nan, dtype="float32")
    for _, opened, scale, offset in scenes:
        eligible = inside & ~selected
        if not eligible.any():
            break
        classification = opened["scl"].read(1, window=window)
        raw = np.stack([opened[name].read(1, window=window) for name in BANDS])
        available = eligible & (raw != 0).all(axis=0)
        usable = available & np.isin(classification, CLEAR_SCL)
        cloud |= available & np.isin(classification, (8, 9, 10))
        shadow |= available & (classification == 3)
        values[:6, usable] = raw[:, usable] * scale[:, None] + offset[:, None]
        selected |= usable
    _, green, red, nir, _, swir2 = values[:6]
    values[6] = ratio(nir, red)
    values[7] = ratio(green, nir)
    values[8] = ratio(nir, swir2)
    values[9, inside] = 3
    values[9, inside & shadow] = 2
    values[9, inside & cloud] = 1
    values[9, selected] = 0
    return values


def active_area(shape, window, grid):
    return geometry_mask(
        [shape], (int(window.height), int(window.width)), window_transform(window, grid["transform"]), invert=True,
    )


def display_grid(root=Path(".")):
    index = root / INDEX
    bounds = json.loads(index.read_bytes())["bounds"]
    w, s, e, n = bounds
    with Image.open(index.parent / "esri-2020.png") as image:
        width, height = image.size
    return {"crs": "EPSG:3857", "width": width, "height": height,
            "transform": from_bounds(*WEB.transform(w, s), *WEB.transform(e, n), width, height)}


def rgba_rgb(data):
    valid = np.isfinite(data).all(axis=0)
    rgb = np.sqrt(np.nan_to_num(data, nan=0).clip(0, 0.32) / 0.32) * 255
    return np.dstack((np.rint(rgb).astype("uint8").transpose(1, 2, 0), valid.astype("uint8") * 255))


def rgba_index(data):
    valid = np.isfinite(data)
    fraction = (np.nan_to_num(data).clip(-1, 1) + 1) * 0.5
    colors = [(128, 66, 29), (248, 244, 214), (14, 104, 118)]
    rgb = np.stack([np.interp(fraction, [0, 0.5, 1], channel) for channel in zip(*colors, strict=True)], axis=-1)
    return np.dstack((np.rint(rgb).astype("uint8"), valid.astype("uint8") * 255))


def rgba_categories(data, palette):
    rgba = np.zeros((*data.shape, 4), dtype="uint8")
    for code, color in palette.items():
        rgba[data == code] = color
    return rgba


def write_png(path, rgba):
    with atomic_output(path) as temporary:
        Image.fromarray(rgba).save(temporary, "PNG")
    return receipt(path)


def spectral_year(year, entries, geom):
    folder = ROOT / str(year)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "spectral.tif"
    grid = grid_for(geom, 30)
    footprint = geometry_mask([mapping(geom)], (grid["height"], grid["width"]), grid["transform"], invert=True)
    counts = np.zeros(4, dtype=np.int64)
    with atomic_output(path) as temporary, ExitStack() as stack:
        scenes = scene_inputs(stack, entries, year, grid)
        profile = raster_profile(grid, 10, "float32", np.nan) | {"predictor": 3}
        output = stack.enter_context(rasterio.open(temporary, "w", **profile))
        output.descriptions = SPECTRAL_DESCRIPTIONS
        for window in windows(grid):
            row, col = int(window.row_off), int(window.col_off)
            inside = footprint[row:row + int(window.height), col:col + int(window.width)]
            if inside.any():
                block = spectral_block(scenes, window, inside)
                counts += np.bincount(block[9, inside].astype("uint8"), minlength=4)
            else:
                block = np.full((10, int(window.height), int(window.width)), np.nan, dtype="float32")
            output.write(block, window=window)
    with rasterio.open(path) as src, WarpedVRT(
        src, **display_grid(), nodata=np.nan, resampling=Resampling.nearest,
    ) as preview:
        layers = {name: write_png(folder / f"{name}.png", rgba_rgb(preview.read(bands)))
                  for name, bands in COMPOSITES.items()}
        layers.update({name: write_png(folder / f"{name}.png", rgba_index(preview.read(band)))
                       for name, band in INDICES.items()})
        layers["quality"] = write_png(folder / "quality.png", rgba_categories(preview.read(10), QUALITY_PALETTE))
    write_json(folder / "spectral.json", {
        "schema": "banten-sentinel-optical/1", "year": year, "boundary_sha256": SNAPSHOT_SHA256,
        "grid": {"crs": "EPSG:6933", "pixel_size_m": 30, "nodata": "NaN"},
        "bands": list(SPECTRAL_DESCRIPTIONS), "clear_scl_codes": list(CLEAR_SCL),
        "qa_counts": dict(zip(("clear", "cloud", "shadow", "other"), map(int, counts), strict=True)),
        "method": "first jointly valid six-band observation in date/scene order after SCL mask; nearest resampling",
        "sources": [{"scene": item["scene"], "observed_at": item["observed_at"],
                     "assets": {name: {key: asset[key] for key in ("sha256", "native_grid", "uri") if key in asset}
                                for name, asset in item["assets"].items()}}
                    for item, *_ in scenes],
        "raster": receipt(path), "layers": layers,
    })
    print(f"Sentinel-2 {year}: {counts.tolist()}", flush=True)


def reference_year(row, grid, geom_shape):
    year = row["year"]
    folder = ROOT / str(year)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "land-cover.tif"
    source = row["source_pin"]
    counts = np.zeros(12, dtype=np.int64)
    with atomic_output(path) as temporary, ExitStack() as stack:
        vrt = read_vrt(stack, check_pin(source), grid)
        output = stack.enter_context(rasterio.open(temporary, "w", **raster_profile(grid, 1, "uint8", 0)))
        output.set_band_description(1, "Esri / Impact Observatory v003 land cover")
        for window in windows(grid):
            inside = active_area(geom_shape, window, grid)
            if not inside.any():
                continue
            labels = vrt.read(1, window=window)
            counts += np.bincount(labels[inside], minlength=12)
            labels[~inside] = 0
            output.write(labels, 1, window=window)
    if any(int(counts[int(code)]) != round(float(area) * 100)
           for code, area in row["area_ha_by_source_code"].items()):
        raise ValueError(f"BANTEN_EXPLORER_REFERENCE_AUDIT_MISMATCH: {year}")
    write_json(folder / "land-cover.json", {"source": source, "raster": receipt(path)})
    print(f"Esri reference {year}: {sum(counts):,} audited pixels", flush=True)


def change_pairs(pairs, grid, audit):
    if not pairs:
        return
    folder = ROOT / "change"
    folder.mkdir(parents=True, exist_ok=True)
    paths = {pair: folder / f"{pair[0]}-{pair[1]}.tif" for pair in pairs}
    counts = {pair: np.zeros(2, dtype=np.int64) for pair in pairs}
    years = sorted({year for pair in pairs for year in pair})
    with ExitStack() as stack:
        sources = {year: stack.enter_context(rasterio.open(ROOT / str(year) / "land-cover.tif"))
                   for year in years}
        outputs = {}
        for pair, path in paths.items():
            temporary = stack.enter_context(atomic_output(path))
            raster = stack.enter_context(rasterio.open(temporary, "w", **raster_profile(grid, 1, "uint8", 0)))
            raster.set_band_description(1, "1 stable, 2 changed, 0 outside jointly valid Esri reference")
            outputs[pair] = raster
        for window in windows(grid):
            labels = {year: vrt.read(1, window=window) for year, vrt in sources.items()}
            valid = {year: (data != 0) & (data != 10) for year, data in labels.items()}
            for (a, b), out in outputs.items():
                common = valid[a] & valid[b]
                if common.any():
                    changed = common & (labels[a] != labels[b])
                    counts[a, b] += (int(common.sum()), int(changed.sum()))
                    out.write(common.astype("uint8") + changed.astype("uint8"), 1, window=window)
        for pair, (common, changed) in counts.items():
            if changed != round(audit[pair]["changed_area_ha"] * 100) or common != round(audit[pair]["common_valid_area_ha"] * 100):
                raise ValueError(f"BANTEN_EXPLORER_CHANGE_AUDIT_MISMATCH: {pair}")
    preview_grid = display_grid()
    for pair, path in paths.items():
        with rasterio.open(path) as src, WarpedVRT(src, **preview_grid, nodata=0, resampling=Resampling.nearest) as display:
            overlay = write_png(path.with_suffix(".png"), rgba_categories(display.read(1), {2: (242, 32, 128, 220)}))
        write_json(path.with_suffix(".json"), {"raster": receipt(path), "preview": overlay,
                   "common_valid_area_ha": audit[pair]["common_valid_area_ha"], "changed_area_ha": audit[pair]["changed_area_ha"]})
        print(f"Esri change {path.stem}: {counts[pair][1]:,} audited changed pixels", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("spectral", "reference", "change"))
    parser.add_argument("--year", type=int, action="append", choices=range(2020, 2026),
                        help="Select spectral years for an independent publishing run.")
    args = parser.parse_args()
    if args.year and args.kind != "spectral":
        parser.error("--year applies to spectral assets")
    geom = transform(PROJECT, boundary())
    if args.kind == "spectral":
        completed = sentinel_complete()
        targets = args.year or sorted(completed, key=lambda year: (year not in (2020, 2025), year))
        if not set(targets).issubset(completed):
            raise ValueError("BANTEN_EXPLORER_SENTINEL_YEAR_PENDING")
        with rasterio.Env(GDAL_CACHEMAX=256 * 1024**2):
            for year in targets:
                folder = ROOT / str(year)
                folder.mkdir(parents=True, exist_ok=True)
                with worker_lock(folder) as allowed:
                    if allowed and not (folder / "spectral.json").is_file():
                        spectral_year(year, completed[year], geom)
        return
    data = json.loads(REPORT.read_bytes())
    if data["boundary_sha256"] != SNAPSHOT_SHA256:
        raise ValueError("BANTEN_EXPLORER_AUDIT_BOUNDARY_MISMATCH")
    grid = grid_for(geom, 10)
    if args.kind == "reference":
        for row in data["annual"]:
            if not (ROOT / str(row["year"]) / "land-cover.json").is_file():
                reference_year(row, grid, mapping(geom))
        return
    pairs = {(row["from_year"], row["to_year"]): row for row in data["pairs"]}
    pending = [pair for pair in combinations(sorted(row["year"] for row in data["annual"]), 2)
               if not (ROOT / "change" / f"{pair[0]}-{pair[1]}.json").is_file()]
    priority = ((2020, 2025), (2024, 2025))
    change_pairs([pair for pair in pending if pair in priority], grid, pairs)
    change_pairs([pair for pair in pending if pair not in priority], grid, pairs)


if __name__ == "__main__":
    main()
