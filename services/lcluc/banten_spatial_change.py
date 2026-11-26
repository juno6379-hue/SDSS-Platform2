"""Aggregate the real Banten 10 m change raster onto an equal-area 1 km grid."""

import json
from contextlib import ExitStack
from hashlib import sha256
from io import BytesIO
from math import ceil, floor

import numpy as np
import rasterio
from PIL import Image
from rasterio.features import geometry_mask
from rasterio.transform import from_bounds, from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window
from shapely.geometry import box, mapping
from shapely.ops import transform

from services.lcluc.banten_esri_audit import verified_sources
from services.lcluc.banten_esri_preview import DIRECTORY, INDEX, WEB
from services.lcluc.province_esri import write_json
from services.lcluc.province_optical_plan import PROJECT, boundary

GRID_M = 1000
SCALE = 10
CELL = GRID_M // SCALE
BLOCK = 512
SPATIAL = DIRECTORY / "spatial"
THEMATIC = (1, 2, 4, 5, 7, 8, 9, 11)


def spatial_path(start, end):
    return SPATIAL / f"{start}-{end}.json"


def compute(start, end, expected):
    _, pins = verified_sources((start, end))
    if set(pins) != {start, end}:
        raise FileNotFoundError("Both annual Banten sources are required")
    if [pins[year]["sha256"] for year in (start, end)] != [
        item["source_sha256"] for item in expected["annual"]
    ]:
        raise ValueError("Banten spatial and tabular source pins differ")
    geometry = boundary()
    equal = transform(PROJECT, geometry)
    shape = mapping(equal)
    w, s, e, n = equal.bounds
    left, top = SCALE * floor(w / SCALE), SCALE * ceil(n / SCALE)
    width, height = ceil((e - left) / SCALE), ceil((top - s) / SCALE)
    rows, cols = ceil(height / CELL), ceil(width / CELL)
    affine = from_origin(left, top, SCALE, SCALE)
    valid = np.zeros(rows * cols, dtype=np.int64)
    changed = np.zeros_like(valid)
    with ExitStack() as stack:
        read = [
            stack.enter_context(
                WarpedVRT(
                    stack.enter_context(rasterio.open(pins[year]["path"])),
                    crs="EPSG:6933",
                    transform=affine,
                    width=width,
                    height=height,
                    src_nodata=0,
                    nodata=0,
                    resampling=Resampling.nearest,
                )
            )
            for year in (start, end)
        ]
        for y in range(0, height, BLOCK):
            for x in range(0, width, BLOCK):
                h, w = min(height - y, BLOCK), min(width - x, BLOCK)
                window = Window(x, y, w, h)
                mask = geometry_mask(
                    [shape],
                    out_shape=(h, w),
                    invert=True,
                    transform=rasterio.windows.transform(window, affine),
                )
                if not mask.any():
                    continue
                first, last = [image.read(1, window=window) for image in read]
                jointly_valid = mask & np.isin(first, THEMATIC) & np.isin(last, THEMATIC)
                row_bins = (np.arange(y, y + h) // CELL) * cols
                col_bins = np.arange(x, x + w) // CELL
                region_keys = row_bins[:, None] + col_bins
                valid += np.bincount(region_keys[jointly_valid], minlength=rows * cols)
                changed += np.bincount(
                    region_keys[jointly_valid & (first != last)], minlength=rows * cols
                )
    valid = valid.reshape(rows, cols)
    changed = changed.reshape(rows, cols)
    if int(valid.sum()) != round(100 * expected["common_valid_area_ha"]) or int(
        changed.sum()
    ) != round(100 * expected["changed_area_ha"]):
        raise ValueError("Province-wide spatial and transition pixel counts differ")

    order = sorted((int(r), int(c)) for r, c in zip(*np.where(changed > 0), strict=True))
    order.sort(key=lambda point: -int(changed[point]))
    hotspots = []
    for rank, (r, c) in enumerate(order[:20], 1):
        pixels = int(changed[r, c])
        centercell = box(
            left + c * GRID_M, top - (r + 1) * GRID_M, left + (c + 1) * GRID_M, top - r * GRID_M
        )
        clip = equal.intersection(centercell)
        hotspots.append(
            {
                "rank": rank,
                "row": r,
                "column": c,
                "changed_area_ha": pixels / 100,
                "common_valid_area_ha": int(valid[r, c]) / 100,
                "rate_pct": 100 * pixels / int(valid[r, c]),
                "geometry": mapping(transform(rasterio_transformer().transform, clip)),
            }
        )
    manifest = json.loads(INDEX.read_bytes())
    west, south, east, north = manifest["bounds"]
    lower = WEB.transform(west, south)
    upper = WEB.transform(east, north)
    with Image.open(DIRECTORY / f"esri-{start}.png") as preview:
        pw, ph = preview.size
    frame = from_bounds(*lower, *upper, pw, ph)
    raster = np.divide(
        changed * 100.0, valid, out=np.full(valid.shape, -1, dtype=np.float32), where=valid > 0
    )
    view = np.full((ph, pw), -1, dtype=np.float32)
    reproject(
        raster,
        view,
        src_crs="EPSG:6933",
        src_transform=from_origin(left, top, GRID_M, GRID_M),
        src_nodata=-1,
        dst_crs="EPSG:3857",
        dst_transform=frame,
        dst_nodata=-1,
        resampling=Resampling.nearest,
    )
    inside = geometry_mask(
        [mapping(transform(WEB.transform, geometry))],
        out_shape=view.shape,
        transform=frame,
        invert=True,
    )
    image = np.zeros((ph, pw, 4), dtype=np.uint8)
    for low, high, color in (
        (0, 1, (231, 234, 237, 160)),
        (1, 10, (254, 215, 170, 220)),
        (10, 25, (251, 146, 60, 235)),
        (25, 50, (234, 88, 12, 245)),
        (50, 101, (153, 27, 27, 255)),
    ):
        image[inside & (view >= low) & (view < high)] = color
    buffer = BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    raw = buffer.getvalue()
    SPATIAL.mkdir(parents=True, exist_ok=True)
    path = SPATIAL / f"{start}-{end}.png"
    part = path.with_suffix(".png.tmp")
    part.write_bytes(raw)
    part.replace(path)
    result = {
        "bounds": manifest["bounds"],
        "visual_grid_m": GRID_M,
        "sample_grid_m": SCALE,
        "source_sha256": [pins[year]["sha256"] for year in (start, end)],
        "changed_grid_cells": len(order),
        "hotspots": hotspots,
        "preview": {"bytes": len(raw), "sha256": sha256(raw).hexdigest(), "path": path.as_posix()},
    }
    write_json(spatial_path(start, end), result)
    return result


def rasterio_transformer():
    from pyproj import Transformer

    return Transformer.from_crs(6933, 4326, always_xy=True)
