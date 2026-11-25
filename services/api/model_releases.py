"""Local edges for version, promotion and rollback evidence."""

import os
import sqlite3
from hmac import compare_digest
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import Field, ValidationError

from services.mlops.releases import ModelRelease, ModelReleases, ReleaseBlocked, document
from services.results.catalog import AssetID, Pin, Strict
from services.results.registry import RegistryError, ResultRegistry

from .catalog_api import validate_entry
from .evidence import EvidenceBlocked
from .results import DATABASE as RESULTS_DATABASE
from .results import check_local


class Candidate(Strict):
    manifest: Pin


class Approval(Strict):
    version: AssetID
    evidence: Pin
    expected_revision: int = Field(ge=0, strict=True)


def model_release_store(store, result_registry=None):
    def catalog_entry(result_id):
        registry = result_registry or ResultRegistry(RESULTS_DATABASE)
        entry = registry.catalog_entry(result_id)
        validate_entry(store, entry)
        return entry

    return ModelReleases(
        store.root,
        store.root / "data/curated/models/releases.sqlite3",
        catalog_entry,
    )


def _authority(request):
    required = os.getenv("SDSS_MODEL_RELEASE_TOKEN", "")
    approver = os.getenv("SDSS_MODEL_RELEASE_AUTHORITY", "").strip()
    if not required or not approver:
        raise HTTPException(503, detail="MODEL_RELEASE_AUTHORITY_NOT_CONFIGURED")
    prefix, _, token = request.headers.get("authorization", "").partition(" ")
    if prefix.lower() != "bearer" or not compare_digest(token.encode(), required.encode()):
        raise HTTPException(403, detail="MODEL_RELEASE_AUTHORITY_REQUIRED")
    return approver


def mount_model_releases(app, store, result_registry=None):
    @app.get("/api/model-releases")
    def models(request: Request):
        check_local(request)
        try:
            repository = model_release_store(store, result_registry)
            rows = repository.list()
            for row in rows:
                active = row["history"][0] if row["history"] else None
                row["active_version"] = active["version"] if active else None
                row["active_revision"] = active["revision"] if active else 0
                try:
                    _, _, revision = repository.active_version(row["model"])
                    row["execution_ready"] = revision == row["active_revision"]
                    row["blockers"] = [] if row["execution_ready"] else ["MODEL_ACTIVATION_CHANGED"]
                except (ReleaseBlocked, RegistryError, EvidenceBlocked) as error:
                    row["execution_ready"] = False
                    row["blockers"] = [str(error)]
        except (sqlite3.Error, OSError) as error:
            raise HTTPException(503, detail="MODEL_RELEASE_STORE_UNAVAILABLE") from error
        ready = any(row["execution_ready"] for row in rows)
        return {
            "status": "ACTIVE_VERIFIED" if ready else "BLOCKED",
            "models": rows,
            "blockers": [] if ready else ["APPROVED_MODEL_VERSION_UNAVAILABLE"],
        }

    @app.post("/api/model-releases")
    def register(request: Request, body: Candidate):
        check_local(request)
        _authority(request)
        try:
            candidate = ModelRelease.model_validate(document(store.root, body.manifest))
            return {"candidate": model_release_store(store, result_registry).register(candidate)}
        except ValidationError as error:
            raise HTTPException(422, detail="MODEL_RELEASE_MANIFEST_INVALID") from error
        except (ReleaseBlocked, RegistryError) as error:
            raise HTTPException(409, detail=str(error)) from error
        except (sqlite3.Error, OSError) as error:
            raise HTTPException(503, detail="MODEL_RELEASE_STORE_UNAVAILABLE") from error

    @app.post("/api/model-releases/{name}/{action}")
    def transition(
        request: Request, name: AssetID, action: Literal["activate", "rollback"], body: Approval
    ):
        check_local(request)
        approver = _authority(request)
        try:
            event = model_release_store(store, result_registry).transition(
                name,
                version=body.version,
                action=action,
                expected_revision=body.expected_revision,
                approval=body.evidence,
                approver=approver,
            )
            return {"event": event}
        except (ReleaseBlocked, RegistryError) as error:
            raise HTTPException(409, detail=str(error)) from error
        except (sqlite3.Error, OSError) as error:
            raise HTTPException(503, detail="MODEL_RELEASE_STORE_UNAVAILABLE") from error
