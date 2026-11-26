"""Versioned post-classification trials for pinned LCLUC candidates."""

import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import rasterio
from pyproj import Geod, Transformer
from rasterio.enums import Resampling
from rasterio.features import sieve
from rasterio.vrt import WarpedVRT

from services.lcluc.annual_rasters import raster_profile
from services.lcluc.banten_sentinel_explorer import rgba_categories, write_png
from services.lcluc.classification_trials import CANDIDATES, SOURCE_DIR
from services.lcluc.classifiers import _metrics
from services.lcluc.province_esri import utc, write_json
from services.lcluc.taxonomy import load_taxonomy, validate_class_codes

ROOT = "data/curated/lcluc/postprocess"
CANDIDATE = "banten-landsat-rf-2020"
ALGORITHM = "spatial-sieve/1"


def spatial_filter(values, nodata, minimum_pixels, connectivity, protected):
    valid = values != nodata
    candidate = sieve(values, size=minimum_pixels, mask=valid, connectivity=connectivity)
    keep = ~valid | np.isin(values, protected) | np.isin(candidate, protected)
    return np.where(keep, values, candidate).astype(values.dtype, copy=False)


def row_areas(transform, crs, height):
    to_geodetic = Transformer.from_crs(crs, 4326, always_xy=True)
    y = np.arange(height + 1)
    col = np.zeros_like(y)
    left = to_geodetic.transform(*((transform.a * col + transform.b * y + transform.c),
                                  (transform.d * col + transform.e * y + transform.f)))
    right = to_geodetic.transform(*((transform.a * (col + 1) + transform.b * y + transform.c),
                                   (transform.d * (col + 1) + transform.e * y + transform.f)))
    geod = Geod(ellps="WGS84")
    return np.array([abs(geod.polygon_area_perimeter(
        [left[0][i], right[0][i], right[0][i + 1], left[0][i + 1]],
        [left[1][i], right[1][i], right[1][i + 1], left[1][i + 1]],
    )[0]) / 10000 for i in range(height)])


def measure(before, after, labels, report):
    codes = report["weak_reference_metrics"]["class_codes"]
    y, x = np.indices(labels.shape)
    holdout = ((y // 48 * 17 + x // 48 * 31) % 5) == 0
    sample = holdout & np.isin(labels, codes) & np.isin(before, codes) & np.isin(after, codes)
    expected = np.searchsorted(codes, labels[sample])

    def evaluate(values):
        predicted = np.searchsorted(codes, values[sample])
        matrix = np.bincount(expected * len(codes) + predicted, minlength=len(codes)**2)
        return _metrics(matrix.reshape(len(codes), len(codes)), codes)

    baseline = evaluate(before)
    old = report["weak_reference_metrics"]
    if not sample.any() or baseline["confusion_matrix_reference_rows"] != old["confusion_matrix_reference_rows"]:
        raise ValueError("POSTPROCESS_WEAK_SAMPLE_MISMATCH")
    return {"reference": report["reference"], "method": "paired_spatial_holdout", "pixels": int(sample.sum()),
            "before": baseline, "after": evaluate(after), "independent": {"status": "REFERENCE_REQUIRED"}}


def file_pin(path):
    return {"bytes": path.stat().st_size, "sha256": sha256(path.read_bytes()).hexdigest()}


def run(store, verified_pin, parameters, palette, candidate=CANDIDATE):
    sealed = store.safe_path(f"{SOURCE_DIR}/{CANDIDATES[candidate]}").read_bytes()
    source = json.loads(sealed)
    if source["year"] != 2020 or source["status"] != "exploratory_weak_reference":
        raise ValueError("POSTPROCESS_CANDIDATE_CONTRACT_MISMATCH")
    original = verified_pin(source["classification"])
    reference = verified_pin(source["reference_raster"])
    contract = {"source_report_sha256": sha256(sealed).hexdigest(), "algorithm": ALGORITHM, "parameters": parameters}
    run_id = sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    root = store.safe_path(ROOT)
    root.mkdir(parents=True, exist_ok=True)
    result = root / run_id
    if result.is_dir():
        return json.loads((result / "report.json").read_bytes())
    taxonomy = load_taxonomy("esri-io-v003")
    with rasterio.open(original) as raw:
        if raw.count != 1 or raw.crs.to_epsg() != 3857 or raw.transform.b or raw.transform.d:
            raise ValueError("POSTPROCESS_GRID_MISMATCH")
        before = raw.read(1)
        validate_class_codes(before, taxonomy, nodata=raw.nodata)
        nodata = int(raw.nodata)
        grid = {"transform": raw.transform, "width": raw.width, "height": raw.height, "crs": raw.crs}
        with rasterio.open(reference) as original_ref, WarpedVRT(
            original_ref, **grid, nodata=0, resampling=Resampling.nearest,
        ) as aligned:
            labels = aligned.read(1)
        after = spatial_filter(before, nodata, **parameters)
        validate_class_codes(after, taxonomy, nodata=nodata)
        changed = before != after
        weights = row_areas(raw.transform, raw.crs, raw.height)
        accuracy = measure(before, after, labels, source)

    classes = []
    for item in (item for item in taxonomy.classes if item.role == "land_cover"):
        base_area = float((before == item.code).sum(axis=1) @ weights)
        final_area = float((after == item.code).sum(axis=1) @ weights)
        classes.append({"code": item.code, "name": item.name_ko, "color": palette[item.code],
                        "before_ha": base_area, "after_ha": final_area, "delta_ha": final_area - base_area})
    colors = {item["code"]: tuple(bytes.fromhex(item["color"].lstrip("#"))) + (255,) for item in classes}
    mask = np.where(before == nodata, 255, changed).astype("uint8")
    with TemporaryDirectory(dir=root) as temporary:
        staged = Path(temporary)
        for name, values, dtype, missing in (("processed", after, "uint16", nodata), ("corrections", mask, "uint8", 255)):
            with rasterio.open(staged / f"{name}.tif", "w", **raster_profile(grid, 1, dtype, missing)) as raster:
                raster.write(values, 1)
        for name, values, palette in (("before", before, colors), ("after", after, colors),
                                      ("corrections", mask, {1: (232, 68, 39, 255)})):
            write_png(staged / f"{name}.png", rgba_categories(values, palette))
        files = {file.name: file_pin(file) for file in staged.iterdir()}
        result_document = {"id": run_id, "candidate": candidate, "year": source["year"], "region": "banten",
                           "status": "REVIEW_CANDIDATE", "created_at": utc(), "original": source["classification"],
                           "grid": {"width": grid["width"], "height": grid["height"], "crs": str(grid["crs"]),
                                    "spacing_m": float(grid["transform"].a)},
                           "changed_pixels": int(changed.sum()), "changed_ha": float(changed.sum(axis=1) @ weights),
                           "valid_pixels": int((before != nodata).sum()), "classes": classes, "accuracy": accuracy,
                           "history": [contract | {"changed_pixels": int(changed.sum())}], "files": files}
        write_json(staged / "report.json", result_document)
        try:
            staged.rename(result)
        except OSError:
            if not (result / "report.json").is_file():
                raise
            return json.loads((result / "report.json").read_bytes())
    return result_document
