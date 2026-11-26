"""Local LCLUC post-classification trial, evidence and artifact routes."""

import json
from re import fullmatch
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.lcluc.classification_trials import CANDIDATES, SENSOR_MODELS, SOURCE_DIR
from services.lcluc.specialists import GROUPS, NAMES, intake, integrate

from .lcluc_cases import ESRI_PALETTE
from .lcluc_sentinel_explorer import _digest
from .results import check_local

PREFIX = "/api/lcluc/postprocess"
ROOT = "data/curated/lcluc/postprocess"
SOURCE = f"{SOURCE_DIR}/rf-report.json"


class Trial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate: str
    minimum_pixels: int = Field(3, strict=True, ge=2, le=30)
    connectivity: Literal[4, 8] = 8

    @field_validator("candidate")
    @classmethod
    def supported_candidate(cls, value):
        if value not in CANDIDATES:
            raise ValueError("POSTPROCESS_CANDIDATE_UNKNOWN")
        return value


def pin_matches(path, pin):
    stat = path.stat()
    return stat.st_size == pin["bytes"] and _digest(path, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) == pin["sha256"]


def mount_postprocess(app, store):
    def verified_original(pin):
        path = store.safe_path(pin["path"])
        if not pin_matches(path, pin):
            raise ValueError("POSTPROCESS_ASSET_INTEGRITY_FAILURE")
        return path

    def get_run(run_id):
        if not fullmatch(r"[0-9a-f]{64}", run_id):
            raise HTTPException(404, detail="POSTPROCESS_RUN_NOT_FOUND")
        file = store.safe_path(f"{ROOT}/{run_id}/report.json")
        if not file.is_file():
            raise HTTPException(404, detail="POSTPROCESS_RUN_NOT_FOUND")
        return json.loads(file.read_bytes())

    @app.get(PREFIX)
    def catalog(request: Request):
        check_local(request)
        files = (path for path in store.safe_path(ROOT).glob("*/report.json")
                 if fullmatch(r"[0-9a-f]{64}", path.parent.name))
        runs = sorted(files, key=lambda path: path.stat().st_mtime_ns, reverse=True)[:30]
        source_dir = store.safe_path(SOURCE).parent
        models = {}
        for key, name in (("rf", "rf-report.json"), ("tiny", "tiny-unet-report.json"), ("siamese", "siamese-report.json")):
            path = source_dir / name
            if path.is_file():
                report = json.loads(path.read_bytes())
                if key == "siamese" and "validation_threshold" not in report:
                    continue
                models[key] = {field: report[field] for field in (
                    "method", "heldout_pixels", "weak_reference_metrics", "before", "after", "years",
                ) if field in report}
        candidates = [candidate for candidate, file in CANDIDATES.items() if (source_dir / file).is_file()]
        return {"candidate": candidates[0] if candidates else None, "candidates": candidates,
                "models": models, "runs": [get_run(path.parent.name) for path in runs]}

    @app.post(PREFIX + "/runs")
    def submit(request: Request, trial: Trial):
        check_local(request)
        from services.lcluc.postprocess import run

        try:
            parameters = trial.model_dump(exclude={"candidate"}) | {"protected": [1, 4, 10]}
            return run(store, verified_original, parameters, ESRI_PALETTE, trial.candidate)
        except FileNotFoundError as error:
            raise HTTPException(409, detail="POSTPROCESS_CANDIDATE_INPUT_REQUIRED") from error
        except (ValueError, OSError) as error:
            raise HTTPException(409, detail="POSTPROCESS_RUN_BLOCKED") from error

    @app.get(PREFIX + "/runs/{run_id}")
    def detail(request: Request, run_id: str):
        check_local(request)
        return get_run(run_id)

    @app.get(PREFIX + "/benchmarks/{sensor}")
    def benchmark(request: Request, sensor: Literal["landsat", "sentinel-2"]):
        check_local(request)
        rows = []
        for method, name in SENSOR_MODELS[sensor].items():
            path = store.safe_path(f"{SOURCE_DIR}/{name}")
            if not path.is_file():
                continue
            report = json.loads(path.read_bytes())
            rows.append({field: report[field] for field in ("method", "heldout_pixels", "training_pixels", "weak_reference_metrics")}
                        | {"key": method, "download": f"{PREFIX}/benchmarks/{sensor}/{method}/classification"})
        return {"region": "banten", "year": 2020, "sensor": sensor, "reference": "Esri / Impact Observatory v003",
                "independent_accuracy_measured": False, "rows": rows}

    @app.get(PREFIX + "/benchmarks/{sensor}/{method}/classification")
    def benchmark_raster(request: Request, sensor: Literal["landsat", "sentinel-2"], method: Literal["rf", "tiny-unet", "deeplabv3plus"]):
        check_local(request)
        report = store.safe_path(f"{SOURCE_DIR}/{SENSOR_MODELS[sensor][method]}")
        if not report.is_file():
            raise HTTPException(404, detail="POSTPROCESS_CLASSIFICATION_PENDING")
        try:
            raster = verified_original(json.loads(report.read_bytes())["classification"])
        except (ValueError, OSError) as error:
            raise HTTPException(409, detail="POSTPROCESS_ASSET_INTEGRITY_FAILURE") from error
        return FileResponse(raster, media_type="image/tiff", filename=f"banten-{sensor}-{method}-2020.tif")

    @app.get(PREFIX + "/siamese/{kind}")
    def siamese(request: Request, kind: Literal["preview", "classification", "filtered", "filtered_preview"]):
        check_local(request)
        report = store.safe_path(SOURCE).with_name("siamese-report.json")
        if not report.is_file():
            raise HTTPException(404, detail="POSTPROCESS_CHANGE_CANDIDATE_PENDING")
        trial = json.loads(report.read_bytes())
        if "validation_threshold" not in trial:
            raise HTTPException(404, detail="POSTPROCESS_CHANGE_CANDIDATE_PENDING")
        try:
            path = verified_original(trial[kind])
        except (ValueError, OSError) as error:
            raise HTTPException(409, detail="POSTPROCESS_ASSET_INTEGRITY_FAILURE") from error
        is_image = kind.endswith("preview")
        return FileResponse(path, media_type="image/png" if is_image else "image/tiff",
                            filename=None if is_image else path.name)

    @app.get(PREFIX + "/hierarchy")
    def hierarchy(request: Request):
        check_local(request)
        groups = {key: [NAMES[code] for code in codes] for key, codes in GROUPS.items()}
        try:
            source = json.loads(store.safe_path(SOURCE).read_bytes())
            plan, _, _ = intake(store, source)
            return {"status": "READY", "groups": groups, "registered": [NAMES[layer.class_code] for layer in plan.layers]}
        except FileNotFoundError:
            return {"status": "SAME_YEAR_LABELS_AND_LAYERS_REQUIRED", "groups": groups}
        except (ValueError, OSError):
            return {"status": "INTAKE_CONTRACT_INVALID", "groups": groups}

    @app.post(PREFIX + "/hierarchy")
    def run_hierarchy(request: Request):
        check_local(request)
        try:
            source = json.loads(store.safe_path(SOURCE).read_bytes())
            return integrate(store, source, verified_original(source["classification"]))
        except (ValueError, OSError) as error:
            raise HTTPException(409, detail="POSTPROCESS_SPECIALIST_INPUTS_REQUIRED_OR_INVALID") from error

    @app.get(PREFIX + "/hierarchy/{run_id}/classification")
    def hierarchy_asset(request: Request, run_id: str):
        check_local(request)
        if not fullmatch(r"[0-9a-f]{64}", run_id):
            raise HTTPException(404, detail="POSTPROCESS_RUN_NOT_FOUND")
        path = store.safe_path(f"data/curated/lcluc/hierarchy/{run_id}/report.json")
        try:
            raster = verified_original(json.loads(path.read_bytes())["asset"])
        except FileNotFoundError as error:
            raise HTTPException(404, detail="POSTPROCESS_RUN_NOT_FOUND") from error
        except (ValueError, OSError) as error:
            raise HTTPException(409, detail="POSTPROCESS_ASSET_INTEGRITY_FAILURE") from error
        return FileResponse(raster, media_type="image/tiff", filename="banten-specialist-integration.tif")

    @app.get(PREFIX + "/runs/{run_id}/assets/{asset}")
    def asset(request: Request, run_id: str, asset: str):
        check_local(request)
        report = get_run(run_id)
        try:
            if asset == "original.tif":
                path = verified_original(report["original"])
            else:
                pin = report["files"].get(asset)
                if pin is None:
                    raise HTTPException(404, detail="POSTPROCESS_ASSET_NOT_FOUND")
                path = store.safe_path(f"{ROOT}/{run_id}/{asset}")
                if not pin_matches(path, pin):
                    raise ValueError("POSTPROCESS_ASSET_INTEGRITY_FAILURE")
        except (ValueError, OSError) as error:
            raise HTTPException(409, detail="POSTPROCESS_ASSET_INTEGRITY_FAILURE") from error
        if asset.endswith(".tif"):
            return FileResponse(path, media_type="image/tiff", filename=f"banten-2020-{asset}")
        return FileResponse(path, media_type="image/png")
