"""Train reproducible display-grid candidates from pinned Banten rasters."""

import argparse
import json
from hashlib import sha256

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from services.lcluc.annual_rasters import atomic_output, raster_profile
from services.lcluc.banten_landsat_baseline import verified
from services.lcluc.banten_landsat_explorer import ROOT, context
from services.lcluc.banten_sentinel_explorer import ROOT as SENTINEL
from services.lcluc.banten_sentinel_explorer import receipt, rgba_categories, write_png
from services.lcluc.classifiers import _metrics, _network
from services.lcluc.postprocess import measure, spatial_filter
from services.lcluc.province_esri import write_json
from services.lcluc.siamese import network as siamese_network

BLOCK = 48
SEED = 2020


def raster(pin, grid, *, spectral=False):
    with rasterio.open(verified(pin)) as source, WarpedVRT(
        source, **grid, nodata=np.nan if spectral else 0, resampling=Resampling.nearest,
    ) as aligned:
        return aligned.read(list(range(1, 7))) if spectral else aligned.read(1)


def partition(shape):
    y, x = np.indices(shape)
    return (y // BLOCK * 17 + x // BLOCK * 31) % 5


def fit(torch, net, features, targets, valid, train, classes, epochs, *, calibration=None):
    """Use complete spatial blocks and loss only at the chosen training coordinates."""
    _, height, width = features.shape
    pad = ((0, 0), (0, -height % BLOCK), (0, -width % BLOCK))
    training_values = features[:, train]
    mean = training_values.mean(axis=1)
    deviation = training_values.std(axis=1).clip(min=1e-5)
    image = (features - mean[:, None, None]) / deviation[:, None, None]
    image[:, ~valid] = 0
    image = np.pad(image, pad)
    target = np.full((height, width), -1, dtype="int64")
    target[train] = np.searchsorted(classes, targets[train])
    target = np.pad(target, pad[1:], constant_values=-1)
    tiles = [(slice(y, y + BLOCK), slice(x, x + BLOCK)) for y in range(0, height, BLOCK) for x in range(0, width, BLOCK)]
    train_tiles = [index for index, region in enumerate(tiles) if (target[region] >= 0).any()]
    if not train_tiles or not np.isfinite(image).all():
        raise ValueError("BANTEN_TRIAL_FEATURES_INVALID")
    arrays = torch.from_numpy(np.stack([image[:, y, x] for y, x in tiles]))
    labels = torch.from_numpy(np.stack([target[tile] for tile in tiles]))
    weight = np.bincount(target[target >= 0], minlength=len(classes)).astype("float32")
    if np.any(weight == 0):
        raise ValueError("BANTEN_TRIAL_CLASS_SUPPORT_MISSING")
    weight = (weight.max() / weight) ** (1 if calibration is not None else 0.5)
    loss_fn = torch.nn.CrossEntropyLoss(weight=torch.from_numpy(weight), ignore_index=-1)
    opt = torch.optim.Adam(net.parameters(), lr=0.003)
    rng = np.random.default_rng(SEED)
    for epoch in range(epochs):
        for indices in np.array_split(rng.permutation(train_tiles), (len(train_tiles) + 15) // 16):
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(net(arrays[indices]), labels[indices])
            loss.backward()
            opt.step()
        print(f"{type(net).__name__} {epoch + 1}/{epochs} final batch loss {loss.item():.4f}", flush=True)
    code_grid = np.empty(target.shape, dtype="uint16")
    positive_grid = np.empty(target.shape, dtype="float32") if calibration is not None else None
    net.eval()
    with torch.inference_mode():
        for start in range(0, len(tiles), 16):
            logits = net(arrays[start:start + 16])
            codes = np.asarray(classes)[logits.argmax(1).numpy()]
            for tile, values in zip(tiles[start:start + 16], codes, strict=False):
                code_grid[tile] = values
            if positive_grid is not None:
                for tile, values in zip(tiles[start:start + 16], logits.softmax(1)[:, 1].numpy(), strict=False):
                    positive_grid[tile] = values
    weights = {"tensor_" + key: val.detach().cpu().numpy() for key, val in net.state_dict().items()}
    if positive_grid is not None:
        probabilities = positive_grid[:height, :width]
        truth = targets[calibration].astype(bool)
        if not truth.any() or truth.all():
            raise ValueError("BANTEN_SIAMESE_VALIDATION_CLASS_SUPPORT_MISSING")

        def f1(cut):
            predicts = probabilities[calibration] >= cut
            return 2 * np.sum(predicts & truth) / (predicts.sum() + truth.sum())

        threshold = max(np.linspace(0.05, 0.95, 37), key=f1)
        code_grid[:height, :width] = (probabilities >= threshold).astype("uint16")
        weights["validation_threshold"] = np.asarray(threshold)
    return code_grid[:height, :width], weights | {"mean": mean, "deviation": deviation, "classes": np.asarray(classes)}


def publish(path, values, grid, nodata, weights):
    with atomic_output(path) as staged, rasterio.open(staged, "w", **raster_profile(grid, 1, "uint16", nodata)) as handle:
        handle.write(values, 1)
    model = path.with_suffix(".npz")
    with atomic_output(model) as staged, staged.open("wb") as handle:
        np.savez_compressed(handle, **weights)
    return receipt(path), receipt(model)


def tiny_trial(torch, grid, epochs):
    baseline_path = ROOT / "rf-report.json"
    baseline = json.loads(baseline_path.read_bytes())
    bands = raster(baseline["input"], grid, spectral=True)
    labels = raster(baseline["reference_raster"], grid)
    codes = baseline["weak_reference_metrics"]["class_codes"]
    holdout = partition(labels.shape) == 0
    valid = np.isfinite(bands).all(axis=0)
    train = np.zeros(labels.shape, dtype=bool)
    rng = np.random.default_rng(SEED)
    for code in codes:
        choices = np.flatnonzero(valid & ~holdout & (labels == code))
        train.flat[rng.choice(choices, min(3500, len(choices)), replace=False)] = True
    if train.sum() != baseline["training_pixels"]:
        raise ValueError("BANTEN_RF_TRAIN_SAMPLE_MISMATCH")
    result, weights = fit(torch, _network(torch, len(codes)), bands, labels, valid, train, codes, epochs)
    result = np.where(valid, result, 0).astype("uint16")
    forest = raster(baseline["classification"], grid)
    paired = measure(forest, result, labels, baseline)
    classification, model = publish(ROOT / "2020-tiny-unet-cover.tif", result, grid, 0, weights)
    report = baseline | {"method": "Tiny U-Net", "weak_reference_metrics": paired["after"], "classification": classification,
                         "model": model, "epochs": epochs, "seed": SEED, "rf_report": receipt(baseline_path),
                         "training_mask_sha256": sha256(train.tobytes()).hexdigest(), "input_type": "six_band_landsat"}
    write_json(ROOT / "tiny-unet-report.json", report)
    print(f"Same {paired['pixels']} weak-reference test pixels; RF {paired['before']['overall_accuracy']:.6f}; Tiny U-Net {paired['after']['overall_accuracy']:.6f}", flush=True)


def siamese_trial(torch, grid, epochs):
    years = (2020, 2025)
    optics, references = [], []
    for year in years:
        folder = SENTINEL / str(year)
        imagery = json.loads((folder / "spectral.json").read_bytes())
        cover = json.loads((folder / "land-cover.json").read_bytes())
        if imagery["year"] != year or cover["source"]["year"] != year:
            raise ValueError("BANTEN_SIAMESE_SOURCE_YEAR_MISMATCH")
        optics.append(imagery["raster"])
        references.append(cover["raster"])
    features = np.concatenate([raster(pin, grid, spectral=True) for pin in optics])
    first, last = (raster(pin, grid) for pin in references)
    valid = np.isfinite(features).all(axis=0)
    observed = valid & ~np.isin(first, [0, 10]) & ~np.isin(last, [0, 10])
    folds = partition(first.shape)
    holdout, calibration = observed & (folds == 0), observed & (folds == 1)
    training = observed & (folds >= 2)
    target = (first != last).astype("uint8")
    result, weights = fit(torch, siamese_network(torch), features, target, valid, training, [0, 1], epochs, calibration=calibration)
    raw = np.where(valid, result, 255).astype("uint16")
    cleaned = spatial_filter(raw, 255, 3, 8, [])
    sample = holdout
    metrics = [_metrics(np.bincount(2 * target[sample] + data[sample], minlength=4).reshape(2, 2), [0, 1])
               for data in (raw, cleaned)]
    classification, model = publish(ROOT / "2020-2025-siamese-v2-change.tif", raw, grid, 255, weights)
    colors = {1: (245, 100, 40, 245), 0: (36, 106, 133, 140)}
    preview = write_png(ROOT / "2020-2025-siamese-v2-change.png", rgba_categories(raw, colors))
    after_preview = write_png(ROOT / "2020-2025-siamese-v2-filtered.png", rgba_categories(cleaned, colors))
    filtered = ROOT / "2020-2025-siamese-v2-filtered.tif"
    with atomic_output(filtered) as staged, rasterio.open(staged, "w", **raster_profile(grid, 1, "uint16", 255)) as handle:
        handle.write(cleaned, 1)
    write_json(ROOT / "siamese-report.json", {"method": "Siamese U-Net", "years": years, "inputs": optics, "references": references,
               "epochs": epochs, "seed": SEED, "training_pixels": int(training.sum()), "validation_pixels": int(calibration.sum()),
               "validation_threshold": float(weights["validation_threshold"]),
               "heldout_pixels": int(sample.sum()), "weak_reference": "same-year Esri v003 maps differ", "independent_accuracy_measured": False,
               "before": metrics[0], "after": metrics[1], "filter": {"minimum_pixels": 3, "connectivity": 8},
               "classification": classification, "preview": preview, "model": model,
               "filtered": receipt(filtered), "filtered_preview": after_preview})
    print(f"Sentinel-2 Siamese same {int(sample.sum())} weak-reference test pixels; F1 {metrics[0]['per_class'][1]['f1']:.6f} → {metrics[1]['per_class'][1]['f1']:.6f}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=("tiny", "siamese", "both"))
    parser.add_argument("--epochs", type=int, default=10, choices=range(1, 41), metavar="1..40")
    args = parser.parse_args()
    import torch

    torch.set_num_threads(2)
    grid, _, _ = context()
    for name, trial in (("tiny", tiny_trial), ("siamese", siamese_trial)):
        if args.model in (name, "both"):
            torch.manual_seed(SEED)
            trial(torch, grid, args.epochs)


if __name__ == "__main__":
    main()
