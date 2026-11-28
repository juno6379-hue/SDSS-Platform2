"""Process sealed regional optical receipts without starting a remote collector."""

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal

from pydantic import Field, model_validator
from rasterio.errors import RasterioError

from services.lcluc.annual import explain, load_json, store_json, worker_lock
from services.lcluc.annual_inputs import REGIONAL_RUN_SCHEMA, Input, Name, Pin, Sha, receipt_bytes
from services.lcluc.banten_westjava_benchmark import run as benchmark
from services.lcluc.classifiers import load_artifact
from services.lcluc.province_esri import digest
from services.lcluc.regional_mosaic import MosaicInput, produce_mosaic
from services.lcluc.regional_trials import SPLITS, esri_held, infer
from services.lcluc.regional_trials import run as train
from services.lcluc.taxonomy import load_taxonomy
from services.lcluc.westjava_future_trial import audit_future
from services.lcluc.westjava_landsat_pilot_inference import run as preview


class Window(Input):
    name: Name
    split: Literal["mosaic-only", "train", "validation", "test"]
    mosaic: MosaicInput


class ModelInputs(Input):
    sentinel_baseline: Sha
    sentinel_lineage: Sha
    landsat_baseline: Sha
    landsat_lineage: Sha


class Receipt(Input):
    schema_version: Literal["sdss-regional-optical-receipt/1"]
    region: Literal["banten", "west_java"]
    year: int
    windows: Annotated[list[Window], Field(min_length=1, max_length=24)]
    # Only the trusted local receipt publication step can request this research replay.
    replay_2020_models: ModelInputs | None = None
    fit_sentinel_candidate: bool = False
    fit_landsat_candidate: bool = False
    sentinel_followup: Pin | None = None
    collector_receipts: list[Pin] = Field(default_factory=list, max_length=64)
    candidate_blocked: dict[Literal["sentinel-2", "landsat"], Literal["NATIVE_BATCH_NEEDS_3_INDEPENDENT_QA_WINDOWS"]] = (
        Field(default_factory=dict)
    )

    @model_validator(mode="after")
    def check_scope(self):
        if len({row.name for row in self.windows}) != len(self.windows):
            raise ValueError("DUPLICATE_REGIONAL_WINDOW")
        if any(
            (row.mosaic.region, row.mosaic.year, row.mosaic.evidence)
            != (self.region, self.year, "real")
            for row in self.windows
        ):
            raise ValueError("REGIONAL_RECEIPT_SCOPE_MISMATCH")
        if self.replay_2020_models is not None and (self.region, self.year) != ("west_java", 2020):
            raise ValueError("FROZEN_BASELINE_SCOPE_MISMATCH")
        if self.sentinel_followup and (
            self.region != "west_java" or len(self.windows) != 1 or
            self.windows[0].mosaic.sensor != "sentinel-2" or
            len(self.windows[0].mosaic.scenes) != 1 or self.windows[0].split != "mosaic-only"
        ):
            raise ValueError("FOLLOWUP_REQUIRES_SINGLE_WEST_JAVA_SENTINEL_WINDOW")
        for enabled, sensor in ((self.fit_sentinel_candidate or self.replay_2020_models, "sentinel-2"),
                                (self.fit_landsat_candidate, "landsat")):
            if enabled:
                splits = {row.split for row in self.windows if row.mosaic.sensor == sensor}
                if self.region != "west_java" or not SPLITS.issubset(splits):
                    raise ValueError("REGIONAL_PILOT_SPLITS_REQUIRED")
        if self.replay_2020_models is not None:
            landsat = [row for row in self.windows if row.mosaic.sensor == "landsat"]
            if len(landsat) != 1 or landsat[0].split != "mosaic-only":
                raise ValueError("REGIONAL_LANDSAT_PILOT_REQUIRED")
        return self


def pin(root, path):
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}


def test_support(report):
    return {
        row["window"]: (row["input_mosaic_sha256"], row["comparison_pixels"],
                        row["weak_reference_metrics"]["overall_accuracy"])
        for row in report.get("evaluations", [])
        if row["split"] == "test" and row["weak_reference_metrics"]
    }


def compare_models(candidate, incumbent):
    before, after = test_support(incumbent), test_support(candidate)
    if before.keys() != after.keys() or not before or any(
        before[name][:2] != after[name][:2] for name in before
    ):
        return {"status": "BLOCKED", "reason": "MATCHED_HOLDOUT_REQUIRED"}
    # Both RFs classify exactly the same finite support with the same taxonomy and reference.
    pixels = sum(row[1] for row in before.values())
    scores = [sum(count * score for _, count, score in rows.values()) / pixels
              for rows in (before, after)]
    return {"status": "EVALUATED_WEAK_REFERENCE", "pixels": pixels, "incumbent": scores[0],
            "candidate": scores[1], "improved": scores[1] > scores[0]}


def followup(platform, frozen, item, stage):
    path = frozen.local(platform)
    trial = load_json(path)
    if trial["experiment"] != "E2" or trial["status"] != "VERIFIED_REAL":
        raise ValueError("FROZEN_E2_CANDIDATE_REQUIRED")
    folder = stage / "followup"
    folder.mkdir()
    mosaic_file = Pin.model_validate(item["mosaic"]).local(stage)
    mosaic = load_json(mosaic_file)
    baseline = load_json(Pin.model_validate(trial["dataset"]).local(path.parent))
    audit = audit_future(mosaic, baseline)
    record = {"status": "BLOCKED", "audit": audit, "model_year": trial["year"],
              "model_sha256": trial["model"]["sha256"], "independent_accuracy_measured": False}
    if audit["status"] == "VERIFIED_REAL" and (
        "DEVELOPMENT_COVERAGE_THRESHOLDS_NOT_MET" not in mosaic["blockers"]
    ):
        taxonomy = load_taxonomy("esri-io-v003")
        model_pin = Pin.model_validate(trial["model"])
        model = load_artifact(model_pin.local(path.parent).read_bytes(), model_pin.sha256)
        if model.dataset_sha256 != trial["dataset_sha256"] or model.domain.sha256 != taxonomy.sha256:
            raise ValueError("E2_CANDIDATE_LINEAGE_MISMATCH")
        references = esri_held(platform, mosaic["year"], taxonomy)
        raster = Pin.model_validate(mosaic["assets"]["reflectance"]).local(mosaic_file.parent)
        result = infer({"window": item["window"], "split": "test", "path": raster,
                        "input_sha256": item["mosaic"]["sha256"]}, references, taxonomy, model, folder)
        metrics = result["weak_reference_metrics"]
        record.update(status="EVALUATED_WEAK_REFERENCE" if metrics else "BLOCKED", output=result,
                      sources=[source for _, source in references])
    store_json(folder / "evaluation.json", record)
    return record


def execute(receipt, roots, stage):
    for collected in receipt.collector_receipts:
        collected.local(roots["platform"])
    records, index = [], []
    for row in receipt.windows:
        # Preserve the exact model input and raw pin set that produced each mosaic.
        path = stage / f"{row.name}.input.json"
        store_json(path, row.mosaic.model_dump(mode="json"))
        folder = stage / row.name
        result = produce_mosaic(row.mosaic, roots, folder, digest(path))
        index.append({"window": row.name, "sensor": row.mosaic.sensor, "split": row.split,
                      "mosaic": pin(stage, folder / "mosaic.json")})
        records.append({"window": row.name, "sensor": row.mosaic.sensor, "scope": result["scope"],
                        "resolution_m": result["grid"]["resolution_m"], "qa": result["qa"],
                        "blockers": result["blockers"]})
    index_path = stage / "index.json"
    store_json(index_path, index)
    models = {sensor: {"status": "BLOCKED", "blockers": [reason]}
              for sensor, reason in receipt.candidate_blocked.items()}
    comparison = None
    plan = receipt.replay_2020_models
    platform = roots["platform"]
    index_sha = digest(index_path)
    trial = None
    if plan or receipt.fit_sentinel_candidate:
        try:
            trial = train(platform, index_path, index_sha, stage / "candidate", 300)
        except FileNotFoundError:
            models["sentinel-2"] = {"status": "BLOCKED", "blockers": ["SAME_YEAR_SOURCE_REQUIRED"]}
        else:
            models["sentinel-2"] = {"status": trial["status"], "blockers": trial["blockers"],
                                   "training_pixels": trial.get("training_pixels")}
    if plan:
        if trial and trial["status"] == "VERIFIED_REAL":
            before = benchmark(platform, index_path, index_sha, plan.sentinel_baseline,
                               plan.sentinel_lineage, stage / "incumbent")
            comparison = compare_models(trial, before["trials"][1])
        landsat = next(row["mosaic"] for row in index if row["sensor"] == "landsat")
        report = preview(platform, stage / landsat["path"], landsat["sha256"], plan.landsat_baseline,
                         plan.landsat_lineage, stage / "landsat-inference")
        models["landsat"] = {"status": "FROZEN_INFERENCE_ONLY", "blockers": report["blockers"],
                             "shared_source_scenes": report["shared_source_scenes"]}
    if receipt.sentinel_followup:
        models["sentinel-2"] = followup(platform, receipt.sentinel_followup, index[0], stage)
    if receipt.fit_landsat_candidate:
        try:
            result = train(platform, index_path, index_sha, stage / "landsat-candidate", 300, sensor="landsat")
        except FileNotFoundError:
            models["landsat"] = {"status": "BLOCKED", "blockers": ["SAME_YEAR_SOURCE_REQUIRED"]}
        else:
            holdout = next((row for row in result.get("evaluations", []) if row["split"] == "test"), None)
            models["landsat"] = {"status": result["status"], "blockers": result["blockers"],
                                 "training_pixels": result.get("training_pixels"), "output": holdout or {}}
    return {"mosaics": records, "models": models, "comparison": comparison}


def run(path, root, roots):
    raw = receipt_bytes(path)
    run_id = sha256(raw).hexdigest()
    if path.name != f"{run_id}.json":
        raise ValueError("REGIONAL_RECEIPT_FILENAME_PIN_MISMATCH")
    output = root / run_id
    if not output.resolve().is_relative_to(root.resolve()):
        raise ValueError("REGIONAL_OUTPUT_OUTSIDE_ROOT")
    if output.exists():
        current = load_json(output / "status.json")
        if not current or current["run_id"] != run_id or current["schema_version"] != REGIONAL_RUN_SCHEMA:
            raise ValueError("REGIONAL_OUTPUT_STATUS_INVALID")
        for pin_data in current["artifacts"]:
            Pin.model_validate(pin_data).local(output)
        return current
    receipt = Receipt.model_validate_json(raw)
    with TemporaryDirectory(dir=root, prefix=".regional-") as scratch:
        stage = Path(scratch) / "run"
        stage.mkdir()
        (stage / "receipt.json").write_bytes(raw)
        result = execute(receipt, roots, stage)
        artifacts = [pin(stage, item) for item in sorted(stage.rglob("*")) if item.is_file()]
        status = {"schema_version": REGIONAL_RUN_SCHEMA, "run_id": run_id,
                  "region": receipt.region.replace("_", "-"), "year": receipt.year,
                  "status": "VERIFIED_REAL",
                  "scope": "collector_completion" if receipt.collector_receipts else "sealed_held_sources",
                  "finished_at": datetime.now(timezone.utc).isoformat(),
                  "remote_requests": 0, "independent_accuracy_measured": False,
                  "production_release": "BLOCKED", "deployment_allowed": False,
                  "artifacts": artifacts, **result}
        store_json(stage / "status.json", status)
        stage.rename(output)
    return status


def scan(inbox, root, roots):
    root.mkdir(parents=True, exist_ok=True)
    with worker_lock(root) as owns_lock:
        if not owns_lock:
            return
        failures = {}
        for path in sorted(inbox.glob("*.json")):
            if not path.resolve().is_relative_to(inbox.resolve()):
                continue
            try:
                status = run(path, root, roots)
                print(f'Regional intake {status["run_id"]} {status["status"]}', flush=True)
            except (OSError, ValueError, KeyError, RasterioError) as error:
                failures[path.stem] = explain(error)
                print(f'Regional intake {path.stem} BLOCKED {failures[path.stem]}', flush=True)
        store_json(root / "worker.json", {"intake_mounted": inbox.is_dir(), "failures": failures})
