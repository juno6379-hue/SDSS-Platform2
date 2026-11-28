"""Evaluate the frozen 2020 regional RF on an unused, calibrated 2023 West Java window."""

import argparse
from pathlib import Path
from shutil import copyfile

import rasterio
from rasterio.warp import transform_bounds
from shapely.geometry import box, mapping, shape

from services.lcluc.annual_inputs import Bands, Pin
from services.lcluc.classifiers import load_artifact
from services.lcluc.province_esri import digest, write_json
from services.lcluc.regional_mosaic import MosaicInput, produce_mosaic
from services.lcluc.regional_trials import esri_held, infer, scene_identity
from services.lcluc.taxonomy import load_taxonomy
from services.lcluc.westjava_2020_pilot import input_pin, read, scene_uri

TRANSFER = Path(
    "evidence/onemap_sentinel/coverage-batches/20261125-pass01/steps/03-west_java-2023/transfer/result.json"
)
LEGACY_METADATA = Path(
    "data/first-group-training-esri-v1/sources/"
    "parallel-v2-extra-west_java-2023-v2-laneB-west_java-boundary-00/west_java-extra-16-2023"
)


def calibrated_input(platform, legacy, transfer, destination):
    source = legacy / LEGACY_METADATA
    optics = read(source / "calibration.json")
    stac = read(source / "stac-item.json")
    product_id = transfer["scene_id"]
    if (
        transfer["status"] != "VERIFIED_REAL"
        or transfer["execution_status"] != "PILOT_QA_PASS"
        or (transfer["province"], transfer["year"]) != ("west_java", 2023)
        or product_id != optics["product_id"]
        or product_id != stac["id"]
        or digest(source / "product-metadata.xml") != optics["source_xml_sha256"]
        or any(optics["xml_product_uri"] not in asset["source_uri"] for asset in transfer["assets"])
    ):
        raise ValueError("FUTURE_PILOT_PRODUCT_METADATA_MISMATCH")
    assets = {
        item["band"]: input_pin(platform, Path(item["path"]), item["sha256"])
        for item in transfer["assets"]
    }
    if assets.keys() != {*Bands["sentinel-2"], "SCL"}:
        raise ValueError("FUTURE_PILOT_ASSETS_INVALID")
    metadata = destination / "metadata"
    metadata.mkdir()
    for item in ("calibration.json", "stac-item.json", "product-metadata.xml"):
        copyfile(source / item, metadata / item)
    with rasterio.open(Pin.model_validate(assets["B02"]).local(platform)) as raster:
        geometry = mapping(box(*transform_bounds(raster.crs, "EPSG:4326", *raster.bounds)))
    date = stac["properties"]["datetime"]
    return {
        "schema_version": "lcluc-regional-mosaic/1",
        "region": "west_java",
        "year": 2023,
        "sensor": "sentinel-2",
        "evidence": "real",
        "geometry": geometry,
        "scenes": [
            {
                "source_id": product_id.lower(),
                "observed_on": date[:10],
                "raw_root": "platform",
                "provider": "planetary-computer",
                "uri": scene_uri(stac),
                "version": "sentinel-2-l2a-" + optics["baseline"],
                "license": "Copernicus Sentinel data terms",
                "acquired_at": date,
                "assets": assets,
                "scale": optics["scale"],
                "offset": optics["offset"],
                "stac_item": input_pin(platform, metadata / "stac-item.json"),
                "calibration": input_pin(platform, metadata / "calibration.json"),
            }
        ],
    }


def audit_future(mosaic, baseline):
    geometry = shape(mosaic["analysis_geometry"])
    window_gaps = {
        row["window"]: geometry.distance(shape(row["geometry"])) for row in baseline["windows"]
    }
    earlier = [item for row in baseline["windows"] for item in row["source_pins"]]
    (current,) = mosaic["sources"]
    known_years = [row["observed_on"] for row in earlier]
    collision_scene = {scene_identity(item["source_id"]) for item in earlier} & {
        scene_identity(current["source_id"])
    }
    collision_assets = {
        asset["sha256"] for item in earlier for asset in item["assets"].values()
    } & {asset["sha256"] for asset in current["assets"].values()}
    passed = (
        min(window_gaps.values()) >= 300
        and current["observed_on"] > max(known_years)
        and (not collision_scene and not collision_assets)
    )
    return {
        "status": "VERIFIED_REAL" if passed else "BLOCKED",
        "earliest_followup": current["observed_on"],
        "latest_earlier_observation": max(known_years),
        "minimum_aoi_gap_m": min(window_gaps.values()),
        "separation_by_window_m": window_gaps,
        "scene_collisions": sorted(collision_scene),
        "asset_collisions": sorted(collision_assets),
        "reference_kind": "same-year Esri weak reference",
    }


def run(platform, legacy, trial_path, transfer_pin, trial_pin, destination):
    trial = read(
        Pin(
            path=trial_path.relative_to(platform).as_posix(),
            bytes=trial_path.stat().st_size,
            sha256=trial_pin,
        ).local(platform)
    )
    if trial["experiment"] != "E2" or trial["status"] != "VERIFIED_REAL" or trial["year"] != 2020:
        raise ValueError("E2_BASELINE_UNVERIFIED")
    file = platform / TRANSFER
    if digest(file) != transfer_pin:
        raise ValueError("FUTURE_PILOT_TRANSFER_SHA_MISMATCH")
    baseline = read(Pin.model_validate(trial["dataset"]).local(trial_path.parent))
    candidate_pin = Pin.model_validate(trial["model"])
    candidate = load_artifact(
        candidate_pin.local(trial_path.parent).read_bytes(), candidate_pin.sha256
    )
    taxonomy = load_taxonomy("esri-io-v003")
    if (
        candidate.dataset_sha256 != trial["dataset_sha256"]
        or candidate.domain.sha256 != taxonomy.sha256
    ):
        raise ValueError("E2_CANDIDATE_LINEAGE_MISMATCH")
    destination.mkdir(exist_ok=False)
    configuration = calibrated_input(platform, legacy, read(file), destination)
    source = destination / "mosaic.inputs.json"
    write_json(source, configuration)
    mosaic_path = destination / "mosaic"
    mosaic = produce_mosaic(
        MosaicInput.model_validate(configuration),
        {"platform": platform},
        mosaic_path,
        digest(source),
    )
    audit = audit_future(mosaic, baseline)
    eligible = (
        audit["status"] == "VERIFIED_REAL"
        and "DEVELOPMENT_COVERAGE_THRESHOLDS_NOT_MET" not in mosaic["blockers"]
    )
    report = {
        "schema_version": "sdss-regional-lcluc-temporal/1",
        "experiment": "E4",
        "sensor": "sentinel-2",
        "region": "west_java",
        "train_year": 2020,
        "test_year": 2023,
        "candidate_sha256": candidate_pin.sha256,
        "status": "VERIFIED_REAL" if eligible else "BLOCKED",
        "spatial_temporal_audit": audit,
        "baseline_trial_sha256": trial_pin,
        "test_transfer_sha256": transfer_pin,
        "test_source_metadata_sha256": digest(destination / "metadata/product-metadata.xml"),
        "scope": "future-year disjoint pilot window; no operational representativeness",
        "independent_accuracy_measured": False,
        "deployment_allowed": False,
    }
    if eligible:
        rasters = esri_held(platform, 2023, taxonomy)
        target = Pin.model_validate(mosaic["assets"]["reflectance"]).local(mosaic_path)
        report.update(
            {
                "references": [row for _, row in rasters],
                "evaluation": infer(
                    {
                        "window": "future-2023",
                        "split": "test",
                        "path": target,
                        "input_sha256": digest(mosaic_path / "mosaic.json"),
                    },
                    rasters,
                    taxonomy,
                    candidate,
                    destination,
                ),
            }
        )
    write_json(destination / "trial.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", type=Path, default=Path("."))
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--e2", type=Path, required=True)
    parser.add_argument("--e2-sha256", required=True)
    parser.add_argument("--transfer-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        args.platform.resolve(),
        args.legacy.resolve(),
        args.e2.resolve(),
        args.transfer_sha256,
        args.e2_sha256,
        args.output.resolve(),
    )
    estimate = result.get("evaluation", {})
    print(
        result["status"],
        estimate.get("comparison_pixels"),
        (estimate.get("weak_reference_metrics") or {}).get("overall_accuracy"),
        digest(args.output / "trial.json"),
        flush=True,
    )


if __name__ == "__main__":
    main()
