"""Read the published Esri reference and Sentinel-2 samples for the Banten explorer."""

import json
from contextlib import ExitStack
from functools import lru_cache
from io import BytesIO
from math import ceil, floor, isfinite

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window
from shapely.geometry import box, mapping
from shapely.ops import transform

from services.lcluc.banten_esri_audit import REPORT
from services.lcluc.banten_esri_preview import WEB
from services.lcluc.banten_reports import comparison
from services.lcluc.banten_sentinel_explorer import THEMATIC, display_grid, rgba_categories
from services.lcluc.province_esri import SNAPSHOT_SHA256
from services.lcluc.province_optical_plan import PROJECT, boundary
from services.lcluc.taxonomy import load_taxonomy


def annual_areas(year, areas, names):
    valid = round(sum(areas), 2)
    return {
        "year": year, "valid_ha": valid,
        "classes": [{"code": code, "name": names[code], "area_ha": area,
                     "share_pct": 100 * area / valid if valid else None}
                    for code, area in zip(THEMATIC, areas, strict=True)],
    }


def change_summary(start, end, common, changed):
    return {"from_year": start, "to_year": end, "common_valid_ha": common, "changed_ha": changed,
            "change_pct": 100 * changed / common if common else None}


def provenance(audit):
    return {
        "source": "Esri / Impact Observatory v003",
        "grid_crs": "EPSG:6933",
        "grid_resolution_m": 10,
        "boundary_sha256": audit["boundary_sha256"],
        "boundary_approval": audit["boundary_approval"],
        "independent_accuracy_measured": False,
        "sources": [{"year": row["year"], "uri": row["source_pin"]["uri"],
                     "sha256": row["source_pin"]["sha256"]} for row in audit["annual"]],
    }


def load_audit(root):
    audit = json.loads((root / REPORT).read_bytes())
    if audit["region"] != "banten" or audit["boundary_sha256"] != SNAPSHOT_SHA256:
        raise ValueError("BANTEN_EXPLORER_AUDIT_BOUNDARY_MISMATCH")
    return audit


def province_statistics(root, start, end):
    audit = load_audit(root)
    pair = comparison(root, start, end, audit)
    if pair is None:
        raise FileNotFoundError("Banten land-cover comparison pending")
    base, _ = pair
    names = {row["code"]: row["name"] for row in base["classes"]}
    return {
        **provenance(audit),
        "scope": "province_boundary", "bbox": None, "aoi_area_ha": base["boundary_area_ha"],
        **change_summary(start, end, base["common_valid_area_ha"], base["changed_area_ha"]),
        "annual": [annual_areas(row["year"], [row["areas_ha"][str(code)] for code in THEMATIC], names)
                   for row in base["annual_area"]],
        "annual_changes": [change_summary(row["from_year"], row["to_year"], row["common_valid_area_ha"],
                                          row["changed_area_ha"])
                           for row in audit["pairs"] if row["to_year"] == row["from_year"] + 1],
        "transition_matrix_ha": base["transition_matrix_ha"],
    }


def type_counts(values):
    return np.bincount(values, minlength=12)[list(THEMATIC)]


def transition_counts(left, right):
    common = np.isin(left, THEMATIC) & np.isin(right, THEMATIC)
    matrix = np.bincount(left[common].astype("uint16") * 12 + right[common], minlength=144)
    return matrix.reshape(12, 12)[np.ix_(THEMATIC, THEMATIC)]


@lru_cache(maxsize=24)
def transition_preview(root, first, second, _first_sha256, _second_sha256, from_class, to_class, bounds):
    grid = display_grid(root)
    with ExitStack() as stack:
        rasters = (stack.enter_context(rasterio.open(path)) for path in (first, second))
        left, right = (stack.enter_context(WarpedVRT(raster, **grid, nodata=0, resampling=Resampling.nearest)).read(1)
                       for raster in rasters)
    changed = (left == from_class) & (right == to_class)
    if bounds:
        footprint = mapping(transform(WEB.transform, box(*bounds)))
        changed &= geometry_mask([footprint], changed.shape, grid["transform"], invert=True)
    target = BytesIO()
    Image.fromarray(rgba_categories(changed, {True: (242, 32, 128, 220)})).save(target, "PNG")
    return target.getvalue()


def rectangle_statistics(root, start, end, bounds, rasters):
    # Both rectangles and the province use the common equal-area grid and the pixel-center rule.
    intersection = transform(PROJECT, boundary(root)).intersection(transform(PROJECT, box(*bounds)))
    if intersection.is_empty or intersection.area <= 0:
        raise ValueError("AOI_OUTSIDE_BANTEN")
    source = load_audit(root)
    names = {row.code: row.label for row in load_taxonomy("esri-io-v003").classes}
    years = sorted(rasters)
    adjacent = [(a, b) for a, b in zip(years, years[1:], strict=False) if b - a == 1]
    histograms = {year: np.zeros(len(THEMATIC), dtype="int64") for year in years}
    matrices = {pair: np.zeros((len(THEMATIC), len(THEMATIC)), dtype="int64") for pair in {*adjacent, (start, end)}}
    aoi_pixels = 0
    with ExitStack() as stack:
        opened = {year: stack.enter_context(rasterio.open(path)) for year, path in rasters.items()}
        ref = opened[start]
        if any((item.transform, item.shape, item.crs, item.nodata) != (ref.transform, ref.shape, ref.crs, 0)
               for item in opened.values()):
            raise ValueError("BANTEN_AOI_GRID_MISMATCH")
        span = ref.window(*intersection.bounds)
        y0, x0 = max(0, floor(span.row_off)), max(0, floor(span.col_off))
        y1 = min(ref.height, ceil(span.row_off + span.height))
        x1 = min(ref.width, ceil(span.col_off + span.width))
        footprint = mapping(intersection)
        for y in range(y0, y1, 512):
            for x in range(x0, x1, 512):
                height, width = min(512, y1 - y), min(512, x1 - x)
                window = Window(x, y, width, height)
                valid = geometry_mask([footprint], (height, width), ref.window_transform(window), invert=True)
                if not valid.any():
                    continue
                aoi_pixels += int(valid.sum())
                values = {year: item.read(1, window=window)[valid] for year, item in opened.items()}
                for year, data in values.items():
                    histograms[year] += type_counts(data)
                for a, b in matrices:
                    matrices[a, b] += transition_counts(values[a], values[b])
    if not aoi_pixels:
        raise ValueError("AOI_CONTAINS_NO_10M_PIXELS")

    def summary(a, b):
        data = matrices[a, b]
        return change_summary(a, b, int(data.sum()) / 100, int(data.sum() - data.trace()) / 100)

    return {
        **provenance(source),
        "scope": "rectangle_intersected_with_province", "bbox": bounds, "aoi_area_ha": aoi_pixels / 100,
        **summary(start, end),
        "annual": [annual_areas(year, (histograms[year] / 100).tolist(), names) for year in years],
        "annual_changes": [summary(a, b) for a, b in adjacent],
        "transition_matrix_ha": (matrices[start, end] / 100).tolist(),
    }


def sample_point(spectral, cover, lon, lat):
    position = PROJECT(lon, lat)
    with rasterio.open(spectral) as src, rasterio.open(cover) as ref:
        data = next(src.sample([position])).tolist()
        code = int(next(ref.sample([position]))[0])
    bands = dict(zip(("B02", "B03", "B04", "B08", "B11", "B12", "NDVI", "NDWI", "NBR"), data[:9], strict=True))
    return {"values": {name: value if isfinite(value) else None for name, value in bands.items()},
            "qa": int(data[9]) if isfinite(data[9]) else None, "cover_code": code or None}
