"""Benchmark DeepLabv3+ using the established Banten 2020 spatial splits."""

import argparse
import json
from hashlib import sha256

import numpy as np

from services.lcluc.banten_landsat_explorer import ROOT, context
from services.lcluc.banten_model_trials import SEED, fit, partition, publish, raster
from services.lcluc.banten_sentinel_explorer import ROOT as SENTINEL
from services.lcluc.classification_trials import SENSOR_MODELS
from services.lcluc.classifiers import ClassificationDomain, _metrics, _network, fit_annual_forest
from services.lcluc.deeplab import network as deeplab
from services.lcluc.postprocess import measure
from services.lcluc.province_esri import write_json
from services.lcluc.taxonomy import load_taxonomy


def sample_training(labels, valid, held, codes):
    rng = np.random.default_rng(SEED)
    selected, supported = [], []
    for code in codes:
        available = valid & (labels == code)
        train = np.flatnonzero(available & ~held)
        if len(train) >= 40 and (available & held).sum() >= 20:
            selected.append(rng.choice(train, min(3500, len(train)), replace=False))
            supported.append(code)
    if len(supported) < 2:
        raise ValueError("BANTEN_BENCHMARK_CLASSES_INSUFFICIENT")
    return np.concatenate(selected), supported


def score(labels, values, sample, codes):
    truth = np.searchsorted(codes, labels[sample])
    guess = np.searchsorted(codes, values[sample])
    return _metrics(np.bincount(truth * len(codes) + guess, minlength=len(codes)**2).reshape(len(codes), len(codes)), codes)


def run(sensor, epochs):
    import torch

    torch.set_num_threads(2)
    grid, _, _ = context()
    domain = ClassificationDomain.from_taxonomy(load_taxonomy("esri-io-v003"))
    original = json.loads((ROOT / "rf-report.json").read_bytes())
    if sensor == "sentinel-2":
        spectral = json.loads((SENTINEL / "2020/spectral.json").read_bytes())
        if spectral["year"] != original["year"]:
            raise ValueError("BANTEN_BENCHMARK_SOURCE_YEAR_MISMATCH")
        source = spectral["raster"]
    else:
        source = original["input"]
    labels = raster(original["reference_raster"], grid)
    features = raster(source, grid, spectral=True)
    valid = np.isfinite(features).all(axis=0)
    held = partition(labels.shape) == 0
    selected, codes = sample_training(labels, valid, held, domain.codes)
    training = np.zeros(labels.shape, dtype=bool)
    training.flat[selected] = True
    test = valid & held & np.isin(labels, codes)
    fingerprint = sha256((source["sha256"] + original["reference_raster"]["sha256"]).encode())
    fingerprint.update(training.tobytes())
    fingerprint.update(test.tobytes())
    baseline = original if sensor == "landsat" else None
    if baseline and (codes != baseline["weak_reference_metrics"]["class_codes"] or len(selected) != baseline["training_pixels"]):
        raise ValueError("BANTEN_BENCHMARK_LANDSAT_SPLIT_MISMATCH")
    methods = ("deeplabv3plus",) if baseline else tuple(SENSOR_MODELS[sensor])
    for method in methods:
        torch.manual_seed(SEED)
        path = ROOT / SENSOR_MODELS[sensor][method]
        path.parent.mkdir(parents=True, exist_ok=True)
        model_path = path.with_name(f"2020-{method}-cover.tif")
        if method == "rf":
            rf = fit_annual_forest(features.reshape(6, -1)[:, selected].T, labels.ravel()[selected], domain, fingerprint.hexdigest(), fixture=False)
            values = np.zeros(labels.shape, dtype="uint16")
            for y in range(0, values.shape[0], 96):
                values[y:y + 96] = rf.predict_forest_reflectance(features[:, y:y + 96])[0]
            weights = rf.parameters | {"mean": rf.mean, "deviation": rf.deviation, "classes": np.asarray(rf.domain.codes)}
            classification, model = publish(model_path, values, grid, 0, weights)
        else:
            model_network = deeplab if method == "deeplabv3plus" else _network
            values, weights = fit(torch, model_network(torch, len(codes)), features, labels, valid, training, codes, epochs)
            values = np.where(valid, values, 0).astype("uint16")
            classification, model = publish(model_path, values, grid, 0, weights)
        metrics = score(labels, values, test, codes)
        if baseline and measure(raster(baseline["classification"], grid), values, labels, baseline)["after"] != metrics:
            raise ValueError("BANTEN_BENCHMARK_LANDSAT_TEST_MISMATCH")
        name = {"rf": "Random Forest", "tiny-unet": "Tiny U-Net", "deeplabv3plus": "DeepLabv3+"}[method]
        report = {"method": name, "year": 2020, "sensor": sensor, "status": "exploratory_weak_reference",
                  "scope": "banten_display_grid", "reference": original["reference"], "input": source,
                  "reference_raster": original["reference_raster"], "independent_accuracy_measured": False,
                  "training_pixels": int(training.sum()), "heldout_pixels": int(test.sum()),
                  "training_mask_sha256": sha256(training.tobytes()).hexdigest(), "test_mask_sha256": sha256(test.tobytes()).hexdigest(),
                  "seed": SEED, "epochs": None if method == "rf" else epochs, "classification": classification, "model": model,
                  "weak_reference_metrics": metrics}
        write_json(path, report)
        print(sensor, name, report["training_pixels"], report["heldout_pixels"], metrics["overall_accuracy"], metrics["mean_iou"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sensor", choices=tuple(SENSOR_MODELS))
    parser.add_argument("--epochs", type=int, default=10, choices=range(1, 41), metavar="1..40")
    options = parser.parse_args()
    run(options.sensor, options.epochs)
