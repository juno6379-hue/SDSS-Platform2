"""Poll the trusted annual intake and advance each immutable run to its next gate."""

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from errno import EACCES, EAGAIN, EDEADLK
from hashlib import sha256 as hash_bytes
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import ValidationError

from services.datahub.connectors.onemap.boundary import sha256
from services.lcluc.annual_inputs import (
    AnnualBundle,
    TrainingAuthorization,
    Verification,
    receipt_bytes,
)
from services.mlops.gates import MLOpsPolicy

CURATED_PATH = "data/curated/lcluc/annual-v1"
INBOX_PATH = "data/raw/annual-lcluc"
RUN_SCHEMA = "lcluc-annual-run/1"


def load_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_bytes())


def store_json(path, value):
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        staged = Path(handle.name)
        try:
            json.dump(value, handle, ensure_ascii=False, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            staged.unlink(missing_ok=True)
            raise
    try:
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


@contextmanager
def worker_lock(root):
    """Release on worker death and preserve the file used for the OS advisory lock."""
    with (root / "worker.lock").open("a+b") as handle:
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno not in {EAGAIN, EACCES, EDEADLK}:
                raise
            yield False
            return
        yield True


def status_file(output, result, state, *, blocker=None):
    file = output / "status.json"
    payload = {
        **result, "state": state, "blocker": blocker,
        "production_release": "SEPARATE_APPROVAL_REQUIRED",
    }
    # Round-trip integer keys and tuples before the next poll compares persisted state.
    payload = json.loads(json.dumps(payload, allow_nan=False))
    existing = load_json(file)
    if existing and {key: value for key, value in existing.items() if key != "updated_at"} == payload:
        return
    store_json(file, {**payload, "updated_at": datetime.now(timezone.utc).isoformat()})
    if not existing or (existing["state"], existing["blocker"]) != (state, blocker):
        print(f'{result["run_id"]} {result.get("region")} {result.get("year")} {state} {blocker or ""}', flush=True)


def explain(error):
    if isinstance(error, ValidationError):
        first = error.errors(include_context=False, include_input=False)[0]
        return f'{first["msg"]} [{"/".join(map(str, first["loc"]))}]'
    if isinstance(error, ValueError):
        return str(error)[:220]
    if isinstance(error, FileNotFoundError):
        return "PINNED_INPUT_PENDING"
    return type(error).__name__


def evaluate_checks(bundle, folder, output, grid, taxonomy, geometry, result, verification):
    from services.lcluc.annual_rasters import compare

    errors = []
    if verification.weak_reference:
        try:
            reference = verification.weak_reference
            bundle.check_reference(reference)
            metrics, _ = compare(output, grid, taxonomy, geometry, reference=reference.raster.local(folder))
            for row in metrics.values():
                row["overall_reference_agreement"] = row.pop("overall_accuracy")
            result["weak_reference_agreement"] = {
                "reference": reference.model_dump(mode="json"), "metrics": metrics,
            }
        except (ValueError, OSError) as error:
            errors.append(f"WEAK_REFERENCE: {explain(error)}")
    if verification.independent_reference:
        try:
            verification.check_independent(bundle)
            reference = verification.independent_reference
            verification.independent_protocol.local(folder)
            metrics, available = compare(
                output, grid, taxonomy, geometry, reference=reference.raster.local(folder),
                training=bundle.training.raster.local(folder),
            )
            policy = MLOpsPolicy()
            if any(row["eligible_pixels"] < policy.min_independent_samples for row in metrics.values()):
                raise ValueError("INDEPENDENT_SAMPLE_COUNT_BELOW_MINIMUM")
            evidence = {
                "reference": reference.model_dump(mode="json"),
                "protocol_sha256": verification.independent_protocol.sha256,
                "approval_id": verification.approval_id, "authority": verification.authority,
                "available_reference_pixels": available, "metrics": metrics,
                "minimum_score_met": all(row["macro_f1"] >= policy.min_macro_f1
                                         and row["overall_accuracy"] >= policy.min_overall_accuracy
                                         for row in metrics.values()),
            }
            key = "synthetic_holdout" if bundle.evidence == "synthetic" else "independent_accuracy"
            result[key] = evidence
        except (ValueError, OSError) as error:
            errors.append(f"INDEPENDENT_REFERENCE: {explain(error)}")
    return errors


def run_bundle(receipt, root, *, allow_synthetic=False):
    from rasterio.errors import RasterioError

    from services.lcluc.annual_rasters import annual_grid, compare, predict_year, prepare
    from services.lcluc.taxonomy import load_taxonomy

    raw = receipt_bytes(receipt)
    run_id = hash_bytes(raw).hexdigest()
    output = root / run_id
    output.mkdir(exist_ok=True)
    folder = receipt.parent
    result = {"schema_version": RUN_SCHEMA, "run_id": run_id}
    try:
        bundle = AnnualBundle.model_validate_json(raw)
        result.update(
            year=bundle.year, region=bundle.region, scope=bundle.evidence, taxonomy=bundle.taxonomy,
            independent_accuracy=None, weak_reference_agreement=None,
        )
        if bundle.evidence == "synthetic" and not allow_synthetic:
            raise ValueError("SYNTHETIC_INTAKE_DISABLED")
        taxonomy = load_taxonomy(bundle.taxonomy, bundle.taxonomy_sha256)
        result["provenance"] = bundle.model_dump(mode="json")
        qc = load_json(output / "quality.json")
        grid = geometry = None
        if qc is None:
            for scenes in bundle.sensors.values():
                for scene in scenes:
                    for pin in scene.assets.values():
                        pin.source_path(folder)
            bundle.boundary.source_path(folder)
            status_file(output, result, "PREPROCESSING")
            grid, geometry = annual_grid(bundle, folder)
            qc = prepare(bundle, folder, output, grid, geometry)
            store_json(output / "quality.json", qc)
        result["quality"] = qc
        policy = MLOpsPolicy()
        if any(row["physical_fraction"] < policy.min_spatial_coverage
               or row["clear_fraction"] < policy.min_valid_pixel_ratio for row in qc.values()):
            return status_file(output, result, "QUALITY_BLOCKED", blocker="OPTICAL_COVERAGE_BELOW_MINIMUM")
        if not bundle.training:
            return status_file(output, result, "WAITING_TRAINING_REFERENCE", blocker="SAME_YEAR_TRAINING_LABELS_REQUIRED")
        auth = folder / "training-approval.json"
        if not auth.is_file():
            return status_file(output, result, "WAITING_TRAINING_APPROVAL", blocker="TRAINING_APPROVAL_REQUIRED")
        approval = TrainingAuthorization.model_validate_json(receipt_bytes(auth))
        if approval.input_sha256 != run_id:
            raise ValueError("TRAINING_APPROVAL_INPUT_MISMATCH")
        result["training_approval"] = approval.model_dump(mode="json")
        analysis = load_json(output / "candidate-analysis.json")
        if analysis is None:
            bundle.training.raster.source_path(folder)
            status_file(output, result, "TRAINING_AND_INFERENCE")
            if grid is None:
                grid, geometry = annual_grid(bundle, folder)
            models = predict_year(bundle, folder, output, grid, taxonomy, qc, run_id)
            comparisons, _ = compare(output, grid, taxonomy, geometry)
            for row in comparisons.values():
                row["overall_map_agreement"] = row.pop("overall_accuracy")
                row["common_area_ha"] = row["eligible_pixels"] * 0.09
            analysis = {"models": models, "same_year_sensor_agreement": comparisons}
            store_json(output / "candidate-analysis.json", analysis)
        result.update(analysis)
        receipt = folder / "verification.json"
        if not receipt.is_file():
            return status_file(output, result, "WAITING_INDEPENDENT_REFERENCE", blocker="INDEPENDENT_REFERENCE_REQUIRED")
        verification_raw = receipt_bytes(receipt)
        verification_sha = hash_bytes(verification_raw).hexdigest()
        verification = Verification.model_validate_json(verification_raw)
        if verification.input_sha256 != run_id:
            raise ValueError("VERIFICATION_INPUT_MISMATCH")
        evaluated = load_json(output / f"verification-{verification_sha}.json")
        if evaluated is None:
            evaluated = {}
            if grid is None:
                grid, geometry = annual_grid(bundle, folder)
            if any(sha256(output / f"{sensor}-cover.tif") != model["cover_sha256"]
                   for sensor, model in analysis["models"].items()):
                raise ValueError("CANDIDATE_RASTER_PIN_MISMATCH")
            errors = evaluate_checks(bundle, folder, output, grid, taxonomy, geometry, evaluated, verification)
            result.update(evaluated)
            if errors:
                return status_file(output, result, "VERIFICATION_BLOCKED", blocker="; ".join(errors))
            store_json(output / f"verification-{verification_sha}.json", evaluated)
        result.update(evaluated, verification_sha256=verification_sha)
        if result.get("synthetic_holdout"):
            return status_file(output, result, "TESTED_SYNTHETIC")
        if result["independent_accuracy"]:
            return status_file(output, result, "INDEPENDENT_EVALUATED")
        return status_file(output, result, "WAITING_INDEPENDENT_REFERENCE", blocker="INDEPENDENT_REFERENCE_REQUIRED")
    except FileNotFoundError:
        status_file(output, result, "WAITING_INPUT", blocker="PINNED_INPUT_PENDING")
    except (ValueError, RasterioError) as error:
        status_file(output, result, "BLOCKED", blocker=explain(error))
    except OSError as error:
        status_file(output, result, "RETRYABLE_ERROR", blocker=explain(error))


def scan(inbox, root, *, allow_synthetic=False):
    root.mkdir(parents=True, exist_ok=True)
    with worker_lock(root) as owns_lock:
        if not owns_lock:
            return
        for path in sorted(inbox.glob("*/*/*/bundle.json")):
            if not path.resolve().is_relative_to(inbox.resolve()):
                continue
            try:
                run_bundle(path, root, allow_synthetic=allow_synthetic)
            except (ValueError, OSError) as error:
                print(f"Annual intake receipt rejected: {explain(error)}", flush=True)
        store_json(root / "worker.json", {
            "last_completed_scan": datetime.now(timezone.utc).isoformat(),
            "intake_mounted": inbox.is_dir(),
            "synthetic_allowed": allow_synthetic,
        })
