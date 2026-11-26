"""Read-only annual LCLUC progress and provenance."""

import json
import re

from fastapi import HTTPException, Query, Request
from fastapi.responses import FileResponse

from services.lcluc.annual import CURATED_PATH, RUN_SCHEMA, load_json

from .results import check_local

ARTIFACTS = {
    f"{sensor}-{kind}": (f"{sensor}-{kind}.tif", field, sensor)
    for sensor in ("sentinel-2", "landsat")
    for kind, field in (("cover", "cover_sha256"), ("confidence", "confidence_sha256"))
}


def mount_lcluc_annual(app, store):
    root = store.root / CURATED_PATH

    def read(run_id):
        if not re.fullmatch(r"[a-f0-9]{64}", run_id):
            return None
        file = root / run_id / "status.json"
        if not file.resolve().is_relative_to(root.resolve()):
            return None
        try:
            item = load_json(file)
        except (OSError, json.JSONDecodeError):
            return None
        return item if item and item.get("schema_version") == RUN_SCHEMA and item.get("run_id") == run_id else None

    def artifact_links(item):
        models = item.get("models") or {}
        return {
            name: {
                "href": f"/api/lcluc/annual-runs/{item['run_id']}/artifacts/{name}",
                "sha256": models[sensor][field],
            }
            for name, (file, field, sensor) in ARTIFACTS.items()
            if models.get(sensor, {}).get(field) and (root / item["run_id"] / file).is_file()
        }

    @app.get("/api/lcluc/annual-runs")
    def annual_runs(request: Request, region: str | None = Query(default=None, max_length=80)):
        check_local(request)
        runs = []
        for path in root.glob("*/status.json"):
            item = read(path.parent.name)
            if not item or (region and region != item.get("region")):
                continue
            row = {key: item.get(key) for key in (
                "run_id", "year", "region", "scope", "state", "blocker", "quality", "updated_at",
            )}
            row["artifacts"] = artifact_links(item)
            cross_sensor = item.get("same_year_sensor_agreement") or {}
            row["sensor_agreement"] = cross_sensor.get("landsat_vs_sentinel-2", {}).get("overall_map_agreement")
            for key, score in (
                ("weak_reference_agreement", "overall_reference_agreement"),
                ("independent_accuracy", "overall_accuracy"), ("synthetic_holdout", "overall_accuracy"),
            ):
                evidence = item.get(key) or {}
                row[key] = {sensor: metrics[score] for sensor, metrics in evidence.get("metrics", {}).items()}
            runs.append(row)
        try:
            worker = load_json(root / "worker.json")
        except (OSError, json.JSONDecodeError):
            worker = None
        return {"runs": sorted(runs, key=lambda row: (row["year"] or 0, row["updated_at"], row["run_id"]), reverse=True),
                "worker": worker}

    @app.get("/api/lcluc/annual-runs/{run_id}")
    def annual_run(request: Request, run_id: str):
        check_local(request)
        item = read(run_id)
        if item is None:
            raise HTTPException(404, detail="ANNUAL_RUN_NOT_FOUND")
        return {**item, "artifacts": artifact_links(item)}

    @app.get("/api/lcluc/annual-runs/{run_id}/artifacts/{name}")
    def annual_artifact(request: Request, run_id: str, name: str):
        check_local(request)
        item, artifact = read(run_id), ARTIFACTS.get(name)
        if item is None or artifact is None:
            raise HTTPException(404, detail="ANNUAL_ARTIFACT_NOT_FOUND")
        filename, field, sensor = artifact
        digest = item.get("models", {}).get(sensor, {}).get(field)
        path = root / run_id / filename
        if not digest or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise HTTPException(404, detail="ANNUAL_ARTIFACT_NOT_FOUND")
        return FileResponse(path, media_type="image/tiff", filename=f"{item['region']}-{item['year']}-{filename}",
                            headers={"X-Artifact-Sha256": digest})
