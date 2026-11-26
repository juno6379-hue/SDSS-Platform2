"""Fit a Banten Landsat RF candidate using a same-year weak reference."""

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from services.lcluc.annual_rasters import atomic_output, raster_profile
from services.lcluc.banten_landsat_explorer import ROOT, context
from services.lcluc.banten_sentinel_explorer import ROOT as SENTINEL_ROOT
from services.lcluc.banten_sentinel_explorer import receipt
from services.lcluc.classifiers import ClassificationDomain, _metrics, fit_annual_forest
from services.lcluc.province_esri import write_json
from services.lcluc.taxonomy import load_taxonomy

YEAR = 2020


def verified(pin):
    path = Path(pin["path"])
    if receipt(path) != pin:
        raise ValueError("RF_INPUT_FINGERPRINT_CHANGED")
    return path


def run():
    manifest = json.loads((ROOT / str(YEAR) / "manifest.json").read_bytes())
    reference = json.loads((SENTINEL_ROOT / str(YEAR) / "land-cover.json").read_bytes())
    if manifest["period"] != [YEAR, YEAR] or reference["source"]["year"] != YEAR:
        raise ValueError("RF_REFERENCE_YEAR_MISMATCH")
    grid, _, _ = context()
    with rasterio.open(verified(manifest["reflectance"])) as optical:
        data = optical.read(list(range(1, 7)))
    with rasterio.open(verified(reference["raster"])) as land_cover, WarpedVRT(
        land_cover, **grid, nodata=0, resampling=Resampling.nearest,
    ) as aligned:
        labels = aligned.read(1)
    domain = ClassificationDomain.from_taxonomy(load_taxonomy("esri-io-v003"))
    valid = np.isfinite(data).all(axis=0) & np.isin(labels, domain.codes)
    y, x = np.indices(labels.shape)
    # Whole display-grid blocks are assigned to one split before class sampling.
    holdout = ((y // 48 * 17 + x // 48 * 31) % 5) == 0
    rng = np.random.default_rng(2020)
    training, validation = [], []
    for code in domain.codes:
        available = valid & (labels == code)
        train = np.flatnonzero(available & ~holdout)
        test = np.flatnonzero(available & holdout)
        if len(train) >= 40 and len(test) >= 20:
            training.append(rng.choice(train, min(3500, len(train)), replace=False))
            validation.append(test)
    train, test = np.concatenate(training), np.concatenate(validation)
    flat_labels = labels.ravel()
    fingerprint = sha256((manifest["reflectance"]["sha256"] + reference["raster"]["sha256"]
                          + "banten-2020-spatial-block-rf-v1").encode()).hexdigest()
    model = fit_annual_forest(data.reshape(6, -1)[:, train].T, flat_labels[train], domain, fingerprint, fixture=False)
    classified = ROOT / f"{YEAR}-rf-cover.tif"
    prediction = np.full(labels.shape, model.domain.nodata, dtype="uint16")
    for y0 in range(0, labels.shape[0], 96):
        prediction[y0:y0 + 96], _ = model.predict_forest_reflectance(data[:, y0:y0 + 96])
    with atomic_output(classified) as staged, rasterio.open(
        staged, "w", **raster_profile(grid, 1, "uint16", model.domain.nodata),
    ) as output:
        output.write(prediction, 1)
    artifact = ROOT / f"{YEAR}-rf.npz"
    with atomic_output(artifact) as staged:
        staged.write_bytes(model.artifact_bytes())
    codes = list(model.domain.codes)
    seen = np.searchsorted(codes, flat_labels[test])
    inferred = np.searchsorted(codes, prediction.ravel()[test])
    matrix = np.bincount(seen * len(codes) + inferred, minlength=len(codes)**2).reshape(len(codes), len(codes))
    report = {
        "year": YEAR, "method": "Random Forest", "scope": "banten_display_grid",
        "status": "exploratory_weak_reference", "training_pixels": len(train), "heldout_pixels": len(test),
        "reference": "Esri / Impact Observatory v003, 2020", "independent_accuracy_measured": False,
        "split": "disjoint 48-by-48 display-grid blocks",
        "weak_reference_metrics": _metrics(matrix, codes), "input": manifest["reflectance"],
        "reference_raster": reference["raster"], "classification": receipt(classified), "model": receipt(artifact),
    }
    write_json(ROOT / "rf-report.json", report)
    print("weak reference only", len(train), len(test), report["weak_reference_metrics"]["overall_accuracy"], flush=True)


if __name__ == "__main__":
    run()
