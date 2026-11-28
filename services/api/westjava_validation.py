"""Expose the fixed public West Java validation receipt through the existing LCLUC API."""

import json
import re
from hashlib import sha256
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import Response

from services.lcluc.annual_inputs import REGIONAL_OUTPUT, REGIONAL_RUN_SCHEMA

from .lcluc_cases import pinned_bytes
from .results import check_local

REPORT = "evidence/westjava/validation-summary.json"
REPORT_SHA256 = "7615b09120bf97e218c1b8198459f754e8b12d366df1580465dee56272d3c0bc"
TREE_BUNDLE = "evidence/westjava/tree-augmentation-display"
TREE_REPORT_SHA256 = "40fc2bc3b6dea267ca55efafa21a476444ab6c088d5d0a924574220bd2addbf6"
TREE_ROUTE = "/api/lcluc/west-java/tree-augmentation"
TREE_BLOCKED = "WEST_JAVA_TREE_COMPARISON_EVIDENCE_UNAVAILABLE"


def tree_report(store):
    try:
        path = store.safe_path(f"{TREE_BUNDLE}/report.json")
        with path.open("rb") as stream:
            raw = stream.read(128 * 1024 + 1)
        if len(raw) > 128 * 1024 or sha256(raw).hexdigest() != TREE_REPORT_SHA256:
            raise ValueError("TREE_REPORT_DIGEST_MISMATCH")
        report = json.loads(raw)
        if (
            report["schema_version"] != "sdss-westjava-tree-augmentation-display/1"
            or (report["region"], report["year"], report["production_release"])
            != ("west-java", 2020, "BLOCKED")
            or any(
                report[k] is not False
                for k in (
                    "independent_accuracy_measured",
                    "human_approval_recorded",
                    "deployment_allowed",
                )
            )
        ):
            raise ValueError("TREE_REPORT_SCOPE_MISMATCH")
    except (OSError, ValueError, TypeError, KeyError):
        raise HTTPException(409, detail=TREE_BLOCKED) from None
    return report


def mount_westjava_validation(app, store):
    @app.get(TREE_ROUTE)
    def tree_comparison(request: Request):
        check_local(request)
        report = tree_report(store)
        for result in report["results"]:
            for holdout in result["matched_holdouts"]:
                prefix = f"{TREE_ROUTE}/{result['sensor']}/{holdout['split']}"
                holdout["maps"] = {phase: f"{prefix}/{phase}.png" for phase in ("before", "after")}
                holdout["legend"] = report["legend"]
        return {**report, "sha256": TREE_REPORT_SHA256}

    @app.get(TREE_ROUTE + "/{sensor}/{split}/{phase}.png")
    def tree_comparison_map(
        request: Request,
        sensor: Literal["sentinel-2", "landsat"],
        split: Literal["test", "validation"],
        phase: Literal["before", "after"],
    ):
        check_local(request)
        report = tree_report(store)
        try:
            result = next(item for item in report["results"] if item["sensor"] == sensor)
            holdout = next(item for item in result["matched_holdouts"] if item["split"] == split)
            pin = holdout["maps"][phase]
            if (
                pin["path"] != f"{sensor}-{split}-{phase}.png"
                or not 0 < pin["bytes"] <= 1024 * 1024
            ):
                raise ValueError("TREE_MAP_PIN_SCOPE_MISMATCH")
            raw = pinned_bytes(store, {**pin, "path": f"{TREE_BUNDLE}/{pin['path']}"})
        except (OSError, ValueError, TypeError, KeyError, StopIteration):
            raise HTTPException(409, detail=TREE_BLOCKED) from None
        return Response(raw, media_type="image/png", headers={"Cache-Control": "private, no-store"})

    @app.get("/api/lcluc/westjava-validation")
    def validation(request: Request):
        check_local(request)
        try:
            path = store.safe_path(REPORT)
            if path.stat().st_size > 1024 * 1024:
                raise ValueError("REPORT_SIZE_EXCEEDED")
            raw = path.read_bytes()
            if sha256(raw).hexdigest() != REPORT_SHA256:
                raise ValueError("REPORT_DIGEST_MISMATCH")
            report = json.loads(raw)
            if report["schema_version"] != "sdss-westjava-validation/1":
                raise ValueError("REPORT_SCHEMA_UNSUPPORTED")
        except (OSError, ValueError, KeyError):
            raise HTTPException(
                status_code=409, detail="WEST_JAVA_VALIDATION_EVIDENCE_UNAVAILABLE"
            ) from None
        return {**report, "sha256": REPORT_SHA256}

    @app.get("/api/lcluc/westjava-intake")
    def intake(request: Request):
        check_local(request)
        root = store.safe_path(REGIONAL_OUTPUT)
        try:
            health = json.loads((root / "worker.json").read_bytes())
            failed_ids = set(health["failures"])
        except (OSError, ValueError, KeyError, TypeError):
            failed_ids = set()
        runs = []
        for path in root.glob("*/status.json"):
            run_id = path.parent.name
            if (
                not re.fullmatch(r"[a-f0-9]{64}", run_id)
                or run_id in failed_ids
                or not path.resolve().is_relative_to(root.resolve())
            ):
                continue
            try:
                if path.stat().st_size > 1024 * 1024:
                    continue
                row = json.loads(path.read_bytes())
                if (row["schema_version"], row["run_id"], row["region"]) != (
                    REGIONAL_RUN_SCHEMA,
                    run_id,
                    "west-java",
                ):
                    continue
                models = {
                    name: {
                        **{
                            key: model[key]
                            for key in ("status", "blockers", "training_pixels")
                            if key in model
                        },
                        "comparison_pixels": model.get("output", {}).get("comparison_pixels"),
                        "weak_agreement": (
                            model.get("output", {}).get("weak_reference_metrics") or {}
                        ).get("overall_accuracy"),
                    }
                    for name, model in row["models"].items()
                }
                runs.append(
                    {
                        **{
                            key: row.get(key)
                            for key in (
                                "run_id",
                                "year",
                                "status",
                                "scope",
                                "finished_at",
                                "mosaics",
                                "comparison",
                                "remote_requests",
                                "production_release",
                                "independent_accuracy_measured",
                            )
                        },
                        "models": models,
                    }
                )
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue
        runs.sort(
            key=lambda row: (row["year"], row["finished_at"] or "", row["run_id"]), reverse=True
        )
        return {"runs": runs, "blocked_run_count": len(failed_ids)}
