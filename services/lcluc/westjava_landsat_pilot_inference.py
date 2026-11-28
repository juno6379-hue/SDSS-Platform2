"""Apply the frozen Landsat RF to a real partial mosaic, without evaluation claims."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from services.lcluc.annual_inputs import Pin
from services.lcluc.banten_westjava_benchmark import BANTEN, verify_report
from services.lcluc.classifiers import load_artifact
from services.lcluc.province_esri import digest, write_json
from services.lcluc.regional_trials import infer
from services.lcluc.taxonomy import load_taxonomy

LANDSAT = BANTEN / "landsat-explore"


def run(platform, path, mosaic_sha, baseline_sha, native_sha, destination):
    baseline = verify_report(platform / LANDSAT / "rf-report.json", baseline_sha)
    native = verify_report(platform / LANDSAT / "2020/manifest.json", native_sha)
    if digest(path) != mosaic_sha:
        raise ValueError("LANDSAT_PILOT_MOSAIC_SHA_MISMATCH")
    mosaic = json.loads(path.read_bytes())
    if (
        mosaic["region"] != "west_java"
        or mosaic["sensor"] != "landsat"
        or mosaic["year"] != 2020
        or mosaic["grid"]["resolution_m"] != 30
        or mosaic["status"] != "VERIFIED_REAL"
        or native["reflectance"] != baseline["input"]
        or native["period"] != [2020, 2020]
    ):
        raise ValueError("LANDSAT_PILOT_SCOPE_OR_INPUT_MISMATCH")
    raster = Pin.model_validate(mosaic["assets"]["reflectance"]).local(path.parent)
    model_pin = Pin.model_validate(baseline["model"])
    weights = model_pin.local(platform)
    taxonomy = load_taxonomy("esri-io-v003")
    model = load_artifact(weights.read_bytes(), model_pin.sha256)
    if model.method != "random_forest" or model.domain.sha256 != taxonomy.sha256:
        raise ValueError("LANDSAT_CLASSIFIER_CONTRACT_INVALID")
    overlap = sorted(
        {item["scene"].lower() for item in native["sources"]}
        & {item["source_id"] for item in mosaic["sources"]}
    )
    blockers = sorted(
        set(
            mosaic["blockers"]
            + ["INDEPENDENT_REFERENCE_NOT_REGISTERED"]
            + (["FROZEN_BANTEN_TRAINING_SCENE_REUSE"] if overlap else [])
        )
    )
    if destination.exists():
        raise FileExistsError(destination)
    with TemporaryDirectory(dir=destination.parent, prefix=".landsat-pilot-") as folder:
        stage = Path(folder) / "result"
        stage.mkdir()
        result = infer(
            {
                "window": "overlap",
                "split": "inference-only",
                "path": raster,
                "input_sha256": mosaic_sha,
            },
            [],
            taxonomy,
            model,
            stage,
            assess=False,
        )
        report = {
            "schema_version": "sdss-landsat-pilot-inference/1",
            "status": "VERIFIED_REAL",
            "year": 2020,
            "region": "west_java",
            "sensor": "landsat",
            "scope": "30m partial-window demonstration; frozen Banten CPU RF",
            "feature_names": ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"],
            "frozen_model_sha256": model_pin.sha256,
            "baseline_sha256": baseline_sha,
            "model_training_scenes_sha256": native_sha,
            "shared_source_scenes": overlap,
            "mosaic_sha256": mosaic_sha,
            "output": result,
            "blockers": blockers,
            "independent_accuracy_measured": False,
            "generalization_measured": False,
            "deployment_allowed": False,
        }
        write_json(stage / "inference.json", report)
        stage.rename(destination)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mosaic", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--baseline-native-sha256", required=True)
    parser.add_argument("--platform", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        args.platform,
        args.mosaic,
        args.expected_sha256,
        args.baseline_sha256,
        args.baseline_native_sha256,
        args.output,
    )
    print(
        result["status"],
        result["blockers"],
        result["shared_source_scenes"],
        digest(args.output / "inference.json"),
    )


if __name__ == "__main__":
    main()
