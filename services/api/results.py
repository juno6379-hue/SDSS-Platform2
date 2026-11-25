"""Local registration and review of results backed by fixed evidence."""

import ipaddress
import json
from functools import cache
from hashlib import file_digest, sha256
from urllib.parse import urlsplit

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from services.orchestration import WorkflowState
from services.results.registry import RegistryError, ResultRegistry

from .evidence import ROOT, EvidenceBlocked

CATALOG = ROOT / "evidence/results/source-catalog.json"
DATABASE = ROOT / "data/curated/results/registry.sqlite3"
MAX_EVIDENCE_BYTES = 32 * 1024**2
REGISTRATION_PIN = {
    "path": "evidence/results/result-registration-20261125-integrated.json",
    "bytes": 10562,
    "sha256": "488039f38bbf42b5cb5a6b02c61dff79e1d8b6e0b2fadf57ce0b449983075f0d",
}


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=100)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(min_length=1, max_length=32)
    reviewer: str = Field(min_length=1, max_length=80)
    note: str = Field(max_length=2000)
    expected_revision: int = Field(ge=0, strict=True)


def check_local(request: Request):
    try:
        peer_is_local = (
            request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
        )
        host = urlsplit("//" + request.headers.get("host", "")).hostname
    except ValueError:
        peer_is_local = False
        host = None
    if not peer_is_local or host not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(403, detail="LOCAL_RESULT_ACCESS_REQUIRED")


def catalog():
    try:
        value = json.loads(CATALOG.read_text(encoding="utf-8"))
        sources = value["sources"]
        if value["schema_version"] != "sdss-result-sources/1" or not isinstance(sources, dict):
            raise ValueError("unexpected source catalog schema")
        return sources
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise EvidenceBlocked("RESULT_SOURCE_CATALOG_UNAVAILABLE") from error


def verify_evidence(store, evidence):
    for pin in evidence:
        name = pin["path"]
        path = store.safe_path(name)
        try:
            with path.open("rb") as handle:
                size = path.stat().st_size
                if size != pin["bytes"] or size > MAX_EVIDENCE_BYTES:
                    raise EvidenceBlocked("RESULT_EVIDENCE_SIZE_DRIFT:" + name)
                if file_digest(handle, "sha256").hexdigest() != pin["sha256"]:
                    raise EvidenceBlocked("RESULT_EVIDENCE_SHA_DRIFT:" + name)
        except OSError as error:
            raise EvidenceBlocked("RESULT_EVIDENCE_MISSING:" + name) from error


def registration_snapshot(store):
    pin = REGISTRATION_PIN
    path = store.safe_path(pin["path"])
    try:
        if path.stat().st_size != pin["bytes"] or pin["bytes"] > MAX_EVIDENCE_BYTES:
            raise EvidenceBlocked("RESULT_WORKFLOW_EVIDENCE_SIZE_DRIFT")
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != pin["sha256"]:
            raise EvidenceBlocked("RESULT_WORKFLOW_EVIDENCE_SHA_DRIFT")
        state = WorkflowState.model_validate_json(raw)
    except EvidenceBlocked:
        raise
    except (OSError, ValueError) as error:
        raise EvidenceBlocked("RESULT_WORKFLOW_EVIDENCE_UNAVAILABLE") from error
    if state.status != "SUCCEEDED" or any(
        step.status != "SUCCEEDED" for step in state.steps.values()
    ):
        raise EvidenceBlocked("RESULT_WORKFLOW_DID_NOT_COMPLETE")
    readbacks = {
        key: step.message for key, step in state.steps.items() if key.startswith("lookup-")
    }
    return {
        "status": "VERIFIED_REAL",
        "scope": "LOCAL_RESULT_REGISTRATION_AND_READBACK",
        "workflow_id": state.workflow_id,
        "trace_id": state.trace_id,
        "completed_at": state.updated_at.isoformat(),
        "completed_steps": len(state.steps),
        "registered_results": len(readbacks),
        "evidence": pin,
        "execution_started": False,
    }


def mount_results(app, store, registry):
    @cache
    def repository():
        return registry if registry is not None else ResultRegistry(DATABASE)

    @app.exception_handler(RegistryError)
    async def registry_error(request, error):
        code = error.code
        status = 422
        if code == "RESULT_NOT_FOUND":
            status = 404
        elif code in {
            "RESULT_CONFLICT",
            "REVIEW_CONFLICT",
            "PACKAGE_CONFLICT",
            "PACKAGE_DIGEST_INVALID",
            "DECISION_CONFLICT",
            "SCIENTIFIC_APPROVAL_REQUIRED",
            "PUBLICATION_INPUTS_INCOMPLETE",
        }:
            status = 409
        elif code == "REGISTRY_UNAVAILABLE":
            status = 503
        return JSONResponse({"status": "BLOCKED", "blockers": [code]}, status_code=status)

    @app.get("/api/results/sources")
    def sources(request: Request):
        check_local(request)
        return {
            "sources": [
                {
                    "source": name,
                    "domain": spec["domain"],
                    "title": spec["title"],
                    "evidence_status": spec["evidence_status"],
                }
                for name, spec in catalog().items()
            ]
        }

    @app.post("/api/results")
    def register(request: Request, body: Registration):
        check_local(request)
        spec = catalog().get(body.source)
        if spec is None:
            return JSONResponse(
                {"status": "BLOCKED", "blockers": ["RESULT_SOURCE_UNKNOWN"]}, status_code=404
            )
        verify_evidence(store, spec["evidence"])
        return {"result": repository().register(source_key=body.source, **spec)}

    @app.get("/api/results")
    def results(
        request: Request,
        domain: str | None = Query(default=None, max_length=64),
        review_status: str | None = Query(default=None, max_length=32),
        limit: int = Query(default=50, ge=1, le=100),
    ):
        check_local(request)
        return {
            "results": repository().list_results(
                limit=limit, domain=domain, review_status=review_status
            )
        }

    @app.get("/api/results/{result_id}")
    def detail(request: Request, result_id: str):
        check_local(request)
        return {"result": repository().get(result_id)}

    @app.post("/api/results/{result_id}/reviews")
    def review(request: Request, result_id: str, body: Review):
        check_local(request)
        repo = repository()
        verify_evidence(store, repo.get(result_id)["evidence"])
        return {"result": repo.review(result_id, **body.model_dump())}

    from .catalog_api import mount_catalog

    mount_catalog(app, store, repository)
