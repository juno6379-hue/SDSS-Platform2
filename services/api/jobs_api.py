"""FastAPI routes for an authorized institution job queue."""

import os
import sqlite3
from hmac import compare_digest

from fastapi import Query, Request
from fastapi.responses import JSONResponse

from services.jobs.contracts import Config, Identifier, JobError, Strict
from services.jobs.store import JobStore
from services.jobs.worker import configuration_path, state_directory

from .results import check_local


class Submission(Strict):
    approval_id: Identifier


def require_operator(request):
    expected = os.getenv("SDSS_JOBS_OPERATOR_TOKEN", "")
    if not expected:
        raise JobError("JOB_OPERATOR_AUTHORITY_NOT_CONFIGURED")
    kind, _, supplied = request.headers.get("authorization", "").partition(" ")
    if kind.lower() != "bearer" or not compare_digest(expected.encode(), supplied.encode()):
        raise JobError("JOB_OPERATOR_AUTHORITY_REQUIRED")


def mount_jobs(app, store, result_registry=None):
    """Mount once alongside the result routes. The worker uses the API's configured database."""
    directory = state_directory(store.root)

    def repository(*, create=False):
        if not directory.is_relative_to(store.root):
            raise JobError("JOB_OUTPUT_ROOT_OUTSIDE_PROJECT")
        if not create and not (directory / "queue.sqlite3").is_file():
            raise JobError("JOB_NOT_FOUND")
        return JobStore(directory)

    def capabilities():
        try:
            config = Config.load(configuration_path())
        except JobError as error:
            return None, [error.code]
        if not any(os.getenv(provider.credential_env) for provider in config.providers.values()):
            return config, ["JOB_PROVIDER_CREDENTIAL_NOT_CONFIGURED"]
        if not config.approvals:
            return config, ["NO_CONFIGURED_JOB_APPROVALS"]
        return config, []

    @app.exception_handler(JobError)
    async def job_error(_request, error):
        statuses = {
            "JOB_NOT_FOUND": 404,
            "JOB_APPROVAL_NOT_FOUND": 404,
            "JOB_OPERATOR_AUTHORITY_REQUIRED": 403,
            "JOB_OPERATOR_AUTHORITY_NOT_CONFIGURED": 503,
            "JOB_PROVIDER_CONFIG_NOT_SET": 503,
            "JOB_PROVIDER_CONFIG_INVALID": 503,
            "JOB_PROVIDER_CREDENTIAL_NOT_CONFIGURED": 503,
            "JOB_OUTPUT_ROOT_OUTSIDE_PROJECT": 503,
            "JOB_CANCELLATION_CONFLICT": 409,
            "JOB_QUEUE_UNAVAILABLE": 503,
        }
        return JSONResponse(
            {"status": "BLOCKED", "blockers": [error.code]},
            status_code=statuses.get(error.code, 409),
        )

    @app.get("/api/jobs")
    def jobs(request: Request, limit: int = Query(default=50, ge=1, le=100)):
        check_local(request)
        _, blockers = capabilities()
        try:
            rows = repository().list(limit)
        except JobError as error:
            if error.code != "JOB_NOT_FOUND":
                raise
            rows = []
        except sqlite3.Error as error:
            raise JobError("JOB_QUEUE_UNAVAILABLE") from error
        return {"status": "BLOCKED" if blockers else "READY", "blockers": blockers, "jobs": rows}

    @app.get("/api/jobs/approvals")
    def approvals(request: Request):
        check_local(request)
        config, blockers = capabilities()
        approvals_list = []
        if config is not None:
            for key in sorted(config.approvals):
                try:
                    approval, _ = config.resolve_approval(store.root, key)
                    approval.ensure_current()
                    config.provider_ready(approval.provider)
                except JobError:
                    continue
                approvals_list.append(
                    {
                        "approval_id": approval.approval_id,
                        "provider": approval.provider,
                        "operation": approval.operation,
                        "model": approval.model.model_dump(),
                        "eligible_until": approval.eligible_until.isoformat(),
                    }
                )
        return {
            "status": "READY" if approvals_list else "BLOCKED",
            "blockers": blockers or ([] if approvals_list else ["NO_CURRENT_JOB_APPROVALS"]),
            "approvals": approvals_list,
        }

    @app.post("/api/jobs", status_code=202)
    def submit(request: Request, body: Submission):
        check_local(request)
        require_operator(request)
        config = Config.load(configuration_path())
        approval, pin = config.resolve_approval(store.root, body.approval_id)
        approval.ensure_current()
        provider = config.provider_ready(approval.provider)
        try:
            return {"job": repository(create=True).submit(approval, pin, provider.fingerprint)}
        except sqlite3.Error as error:
            raise JobError("JOB_QUEUE_UNAVAILABLE") from error

    @app.get("/api/jobs/{job_id}")
    def detail(request: Request, job_id: str):
        check_local(request)
        try:
            queue = repository()
            return {"job": queue.public(queue.get(job_id)), "events": queue.events(job_id)}
        except sqlite3.Error as error:
            raise JobError("JOB_QUEUE_UNAVAILABLE") from error

    @app.post("/api/jobs/{job_id}/cancel", status_code=202)
    def cancel(request: Request, job_id: str):
        check_local(request)
        require_operator(request)
        try:
            return {"job": repository().cancel(job_id)}
        except sqlite3.Error as error:
            raise JobError("JOB_QUEUE_UNAVAILABLE") from error
