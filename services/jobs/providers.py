"""HTTP client for explicitly configured institutional provider origins."""

import os
from time import monotonic

import httpx
from pydantic import ValidationError

from .contracts import (
    Approval,
    JobError,
    ProviderAsset,
    ProviderProgress,
    ProviderResult,
    ProviderSpec,
)


class ProviderTemporary(JobError):
    """A request might have reached the provider, so replays must remain idempotent."""


class HttpProvider:
    def __init__(self, spec: ProviderSpec, client: httpx.Client | None = None):
        token = os.getenv(spec.credential_env)
        if not token:
            raise JobError("JOB_PROVIDER_CREDENTIAL_NOT_CONFIGURED")
        self.spec = spec
        self.client = client or httpx.Client(trust_env=False, timeout=httpx.Timeout(10.0))
        self.owns_client = client is None
        self.headers = {"Authorization": "Bearer " + token, "Accept-Encoding": "identity"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.owns_client:
            self.client.close()

    def request(self, method, path, limit, *, payload=None, idempotency=None):
        headers = dict(self.headers)
        if idempotency is not None:
            headers["Idempotency-Key"] = idempotency
        started = monotonic()
        try:
            with self.client.stream(
                method,
                self.spec.base_url + path,
                json=payload,
                headers=headers,
                follow_redirects=False,
            ) as response:
                if response.status_code == 429:
                    raise ProviderTemporary("PROVIDER_RATE_LIMITED")
                if response.status_code in {408, 425} or 500 <= response.status_code <= 599:
                    raise ProviderTemporary("PROVIDER_TEMPORARILY_UNAVAILABLE")
                if not 200 <= response.status_code < 300:
                    raise JobError("PROVIDER_REQUEST_REJECTED")
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise JobError("PROVIDER_CONTENT_ENCODING_UNSUPPORTED")
                value = bytearray()
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    if monotonic() - started > 25:
                        raise ProviderTemporary("PROVIDER_RESPONSE_DEADLINE_EXCEEDED")
                    if len(value) + len(chunk) > limit:
                        raise JobError("PROVIDER_RESPONSE_TOO_LARGE")
                    value.extend(chunk)
                return bytes(value)
        except httpx.RequestError as error:
            raise ProviderTemporary("PROVIDER_NETWORK_UNAVAILABLE") from error

    @staticmethod
    def parse(schema, content, job_id):
        try:
            parsed = schema.model_validate_json(content)
        except (ValidationError, ValueError, RecursionError) as error:
            raise JobError("PROVIDER_RESPONSE_SCHEMA_INVALID") from error
        if parsed.job_id != job_id:
            raise JobError("PROVIDER_RESPONSE_JOB_MISMATCH")
        return parsed

    def submit(self, job_id, approval: Approval, approval_sha256):
        body = {
            "job_id": job_id,
            "approval_sha256": approval_sha256,
            "operation": approval.operation,
            "model": approval.model.model_dump(mode="json"),
            "parameters": approval.parameters,
        }
        raw = self.request("POST", "/jobs", 32 * 1024, payload=body, idempotency=job_id)
        return self.parse(ProviderProgress, raw, job_id)

    def progress(self, job_id):
        raw = self.request("GET", f"/jobs/{job_id}", 32 * 1024)
        return self.parse(ProviderProgress, raw, job_id)

    def cancel(self, job_id):
        raw = self.request(
            "POST", f"/jobs/{job_id}/cancel", 32 * 1024, payload={}, idempotency=job_id + "-cancel"
        )
        return self.parse(ProviderProgress, raw, job_id)

    def result(self, job_id):
        raw = self.request("GET", f"/jobs/{job_id}/result", 512 * 1024)
        return self.parse(ProviderResult, raw, job_id)

    def asset(self, job_id, asset: ProviderAsset):
        return self.request("GET", f"/jobs/{job_id}/assets/{asset.id}", asset.pin.bytes)
