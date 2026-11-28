"""Reproduce the frozen Banten RF benchmark and run its regional holdout transfer."""

import argparse
from contextlib import ExitStack
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from shapely.geometry import shape
from shapely.ops import transform

from services.lcluc.annual_inputs import Pin
from services.lcluc.banten_deeplab_trials import sample_training, score
from services.lcluc.banten_model_trials import partition
from services.lcluc.classifiers import ClassificationDomain, FittedClassifier
from services.lcluc.province_esri import SNAPSHOT_SHA256, digest, write_json
from services.lcluc.province_optical_plan import PROJECT, boundary
from services.lcluc.regional_mosaic import pin
from services.lcluc.regional_trials import (
    esri_held,
    infer,
    raster_grid,
    scene_identity,
    verified_rows,
)
from services.lcluc.taxonomy import load_taxonomy
from services.lcluc.westjava_2020_pilot import read

BANTEN = Path("data/curated/explorer/banten-province")
MODEL = BANTEN / "landsat-explore/sentinel2-benchmark/rf-report.json"
SPECTRAL = BANTEN / "sentinel-explore/2020/spectral.json"


def verify_report(path, expected):
    if digest(path) != expected:
        raise ValueError("FROZEN_BANTEN_REPORT_SHA_MISMATCH")
    return read(path)


def frozen_model(platform, report, taxonomy):
    artifact = Pin.model_validate(report["model"]).local(platform)
    with np.load(artifact, allow_pickle=False) as data:
        parameters = {
            name: data[name] for name in data.files if name not in {"mean", "deviation", "classes"}
        }
        codes = tuple(map(int, data["classes"]))
        if tuple(report["weak_reference_metrics"]["class_codes"]) != codes:
            raise ValueError("FROZEN_MODEL_CLASS_DOMAIN_MISMATCH")
        domain = replace(ClassificationDomain.from_taxonomy(taxonomy), codes=codes)
        return FittedClassifier(
            "random_forest",
            domain,
            data["mean"],
            data["deviation"],
            parameters,
            report["input"]["sha256"],
            "VERIFIED_REAL",
        )


def replay_benchmark(platform, report, model, taxonomy):
    with ExitStack() as stack:
        prediction = stack.enter_context(
            rasterio.open(Pin.model_validate(report["classification"]).local(platform))
        )
        grid = raster_grid(prediction)
        source = stack.enter_context(
            rasterio.open(Pin.model_validate(report["input"]).local(platform))
        )
        raster = stack.enter_context(
            WarpedVRT(source, **grid, nodata=np.nan, resampling=Resampling.nearest)
        )
        reference = stack.enter_context(
            rasterio.open(Pin.model_validate(report["reference_raster"]).local(platform))
        )
        aligned = stack.enter_context(
            WarpedVRT(reference, **grid, nodata=0, resampling=Resampling.nearest)
        )
        features = raster.read(list(range(1, 7)))
        labels = aligned.read(1)
        archived = prediction.read(1)
    valid = np.isfinite(features).all(axis=0)
    held = partition(labels.shape) == 0
    codes = list(model.domain.codes)
    train, actual_codes = sample_training(labels, valid, held, taxonomy.thematic_codes)
    mask = np.zeros_like(held)
    mask.flat[train] = True
    test = valid & held & np.isin(labels, actual_codes)
    if codes != actual_codes or (
        sha256(mask.tobytes()).hexdigest() != report["training_mask_sha256"]
        or sha256(test.tobytes()).hexdigest() != report["test_mask_sha256"]
    ):
        raise ValueError("FROZEN_BANTEN_PILOT_SPLIT_DRIFT")
    measured = np.zeros_like(archived, dtype="uint16")
    for start in range(0, measured.shape[0], 96):
        measured[start : start + 96] = model.predict_forest_reflectance(
            features[:, start : start + 96]
        )[0]
    metrics = score(labels, measured, test, codes)
    if metrics != report["weak_reference_metrics"] or not np.array_equal(archived, measured):
        raise ValueError("FROZEN_BANTEN_PREDICTION_DRIFT")
    return {
        "experiment": "E0",
        "status": "VERIFIED_REAL",
        "region": "banten",
        "scope": "archived ~147 m display-grid spatial holdout using same annual mosaic",
        "comparison_pixels": int(test.sum()),
        "training_pixels": int(mask.sum()),
        "weak_reference_metrics": metrics,
        "matches_archived_predictions": True,
        "grid_resolution_m": float(grid["transform"].a),
    }


def westjava_transfer(platform, rows, model, taxonomy, spectral, stage, buffer_m):
    source_keys = {scene_identity(row["scene"]) for row in spectral["sources"]}
    source_dates = {row["observed_at"][:10] for row in spectral["sources"]}
    source_hashes = {
        asset["sha256"] for row in spectral["sources"] for asset in row["assets"].values()
    }
    banten = transform(PROJECT, boundary(platform, province="banten"))
    filters, blockers = [], []
    holdout = [
        row for row in rows if row["split"] == "test" and row["mosaic"]["region"] == "west_java"
    ]
    if not holdout:
        blockers.append("WEST_JAVA_UNSEEN_TEST_MOSAIC_REQUIRED")
    for row in holdout:
        mosaic = row["mosaic"]
        if mosaic["year"] != spectral["year"] or mosaic["boundary_sha256"] != SNAPSHOT_SHA256:
            blockers.append("WEST_JAVA_TEST_SCOPE_MISMATCH")
        test_scenes = {scene_identity(src["source_id"]) for src in mosaic["sources"]}
        test_dates = {src["observed_on"] for src in mosaic["sources"]}
        test_hashes = {
            asset["sha256"] for src in mosaic["sources"] for asset in src["assets"].values()
        }
        separation = banten.distance(shape(mosaic["analysis_geometry"]))
        checks = {
            "window": row["window"],
            "distance_from_banten_m": separation,
            "scene_collisions": sorted(source_keys & test_scenes),
            "date_collisions": sorted(source_dates & test_dates),
            "shared_asset_hashes": sorted(source_hashes & test_hashes),
            "same_reference_product_family": True,
        }
        filters.append(checks)
        if (
            any(
                checks[key]
                for key in ("scene_collisions", "date_collisions", "shared_asset_hashes")
            )
            or separation < buffer_m
        ):
            blockers.append("BANTEN_TO_WEST_JAVA_TRANSFER_LEAKAGE")
    result = {
        "experiment": "E1",
        "region": "west_java",
        "scope": "frozen Banten RF applied on West Java 10 m pilot holdout; ~147 m Banten training grid",
        "audit": filters,
        "blockers": sorted(set(blockers)),
        "status": "BLOCKED" if blockers else "VERIFIED_REAL",
        "same_feature_names": list(spectral["bands"][:6]),
        "compatibility": "cross-resolution exploratory",
    }
    if not blockers:
        references = esri_held(platform, spectral["year"], taxonomy)
        result["evaluations"] = [infer(row, references, taxonomy, model, stage) for row in holdout]
    return result


def run(platform, index, index_sha, report_sha, spectral_sha, destination):
    if digest(index) != index_sha:
        raise ValueError("TRIAL_INDEX_SHA_MISMATCH")
    report = verify_report(platform / MODEL, report_sha)
    spectral = verify_report(platform / SPECTRAL, spectral_sha)
    if (
        spectral["year"] != report["year"]
        or spectral["raster"] != report["input"]
        or report["sensor"] != "sentinel-2"
        or spectral["boundary_sha256"] != SNAPSHOT_SHA256
    ):
        raise ValueError("FROZEN_BANTEN_LINEAGE_MISMATCH")
    taxonomy = load_taxonomy("esri-io-v003")
    model = frozen_model(platform, report, taxonomy)
    rows = verified_rows(index.parent, read(index), "sentinel-2")
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent, prefix=".regional-benchmark-") as folder:
        stage = Path(folder) / "result"
        stage.mkdir()
        output = {
            "schema_version": "sdss-banten-westjava-benchmark/1",
            "sensor": "sentinel-2",
            "year": report["year"],
            "weak_reference": "same-year Esri / Impact Observatory v003",
            "independent_accuracy_measured": False,
            "stage": "EXPLORATORY",
            "deployment_allowed": False,
            "frozen_model_sha256": report["model"]["sha256"],
            "frozen_benchmark_sha256": report_sha,
            "frozen_spectral_receipt_sha256": spectral_sha,
            "test_index_sha256": index_sha,
            "trials": [
                replay_benchmark(platform, report, model, taxonomy),
                westjava_transfer(platform, rows, model, taxonomy, spectral, stage, 300),
            ],
        }
        write_json(stage / "benchmark.json", output)
        stage.rename(destination)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--index-sha256", required=True)
    parser.add_argument("--banten-report-sha256", required=True)
    parser.add_argument("--banten-spectral-sha256", required=True)
    parser.add_argument("--platform", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(
        args.platform,
        args.index,
        args.index_sha256,
        args.banten_report_sha256,
        args.banten_spectral_sha256,
        args.output,
    )
    print(pin(args.output / "benchmark.json"))
    for trial in report["trials"]:
        print(
            trial["experiment"],
            trial["status"],
            trial.get("comparison_pixels"),
            trial.get("weak_reference_metrics", {}).get("overall_accuracy"),
        )
        for row in trial.get("evaluations", []):
            print(
                row["window"],
                row["comparison_pixels"],
                (row["weak_reference_metrics"] or {}).get("overall_accuracy"),
            )


if __name__ == "__main__":
    main()
