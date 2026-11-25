"""Pinned configuration and provider contracts for institutional execution."""

import json
import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator

from services.results.catalog import Pin, ResultPackage

Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
MAX_APPROVAL_BYTES = 64 * 1024
MAX_CONFIG_BYTES = 1024 * 1024
MAX_JOB_OUTPUT_BYTES = 64 * 1024**2


class JobError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value) -> str:
    return sha256(canonical(value)).hexdigest()


class ModelPin(Strict):
    name: Identifier
    version: str = Field(min_length=1, max_length=128)
    artifact_sha256: Digest


class ProviderSpec(Strict):
    kind: Literal["institution_toolbox", "external_model", "project_model"]
    base_url: str = Field(max_length=1024)
    credential_env: str = Field(pattern=r"^SDSS_PROVIDER_[A-Z0-9_]+_TOKEN$")
    operations: frozenset[Identifier] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def check_endpoint(self):
        uri = urlsplit(self.base_url)
        port = uri.port
        if (
            uri.scheme != "https"
            or not uri.hostname
            or uri.username is not None
            or uri.password is not None
            or (port is not None and port == 0)
            or uri.query
            or uri.fragment
            or "%" in uri.path
            or ".." in uri.path.split("/")
            or self.base_url.endswith("/")
            or not uri.path
            or "\\" in self.base_url
            or any(ord(char) < 33 for char in self.base_url)
        ):
            raise ValueError("PROVIDER_HTTPS_ENDPOINT_INVALID")
        return self

    @property
    def fingerprint(self):
        return digest(
            {
                "kind": self.kind,
                "base_url": self.base_url,
                "credential_env": self.credential_env,
                "operations": sorted(self.operations),
            }
        )


class Approval(Strict):
    schema_version: Literal["sdss-job-approval/1"]
    approval_id: Identifier
    provider: Identifier
    operation: Identifier
    model: ModelPin
    approved_by: str = Field(min_length=1, max_length=200)
    eligible_until: AwareDatetime
    parameters: dict[str, Any] = Field(max_length=64)

    @model_validator(mode="after")
    def bounded_payload(self):
        try:
            if len(canonical(self.parameters)) > MAX_APPROVAL_BYTES:
                raise ValueError("APPROVAL_PARAMETERS_TOO_LARGE")
        except (ValueError, TypeError, RecursionError) as error:
            raise ValueError("APPROVAL_PARAMETERS_INVALID") from error
        return self

    def ensure_current(self):
        if self.eligible_until <= datetime.now(UTC):
            raise JobError("JOB_APPROVAL_EXPIRED")


class Config(Strict):
    schema_version: Literal["sdss-institution-jobs/1"]
    providers: dict[Identifier, ProviderSpec] = Field(min_length=1, max_length=32)
    approvals: dict[Identifier, Pin] = Field(max_length=256)

    @classmethod
    def load(cls, file: Path | None):
        if file is None:
            raise JobError("JOB_PROVIDER_CONFIG_NOT_SET")
        try:
            with file.open("rb") as handle:
                raw = handle.read(MAX_CONFIG_BYTES + 1)
            if len(raw) > MAX_CONFIG_BYTES:
                raise JobError("JOB_PROVIDER_CONFIG_INVALID")
            return cls.model_validate_json(raw)
        except (OSError, ValidationError, RecursionError) as error:
            raise JobError("JOB_PROVIDER_CONFIG_INVALID") from error

    def resolve_approval(self, root: Path, key: str) -> tuple[Approval, Pin]:
        pin = self.approvals.get(key)
        if pin is None:
            raise JobError("JOB_APPROVAL_NOT_FOUND")
        path = (root / pin.path).resolve()
        if not path.is_relative_to(root) or pin.bytes > MAX_APPROVAL_BYTES:
            raise JobError("JOB_APPROVAL_EVIDENCE_INVALID")
        try:
            with path.open("rb") as handle:
                raw = handle.read(pin.bytes + 1)
            if len(raw) != pin.bytes or sha256(raw).hexdigest() != pin.sha256:
                raise JobError("JOB_APPROVAL_EVIDENCE_DRIFT")
            approval = Approval.model_validate_json(raw)
        except (OSError, ValidationError, RecursionError) as error:
            raise JobError("JOB_APPROVAL_EVIDENCE_INVALID") from error
        provider = self.providers.get(approval.provider)
        if (
            approval.approval_id != key
            or provider is None
            or approval.operation not in provider.operations
        ):
            raise JobError("JOB_APPROVAL_NOT_ALLOWLISTED")
        return approval, pin

    def provider_ready(self, key: str):
        provider = self.providers.get(key)
        if provider is None:
            raise JobError("JOB_PROVIDER_NOT_ALLOWLISTED")
        if not os.getenv(provider.credential_env):
            raise JobError("JOB_PROVIDER_CREDENTIAL_NOT_CONFIGURED")
        return provider


class ProviderProgress(Strict):
    job_id: str = Field(pattern=r"^j-[a-f0-9]{60}$")
    state: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
    progress: int = Field(ge=0, le=100, strict=True)


class ProviderAsset(Strict):
    id: Identifier
    pin: Pin

    @model_validator(mode="after")
    def flat_filename(self):
        if "/" in self.pin.path or self.pin.path.startswith("."):
            raise ValueError("PROVIDER_ASSET_FILENAME_INVALID")
        return self


class ProviderResult(Strict):
    job_id: str = Field(pattern=r"^j-[a-f0-9]{60}$")
    model: ModelPin
    package: ResultPackage
    assets: list[ProviderAsset] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def bounded_assets(self):
        if sum(item.pin.bytes for item in self.assets) > MAX_JOB_OUTPUT_BYTES:
            raise ValueError("PROVIDER_ASSET_BYTES_EXCEEDED")
        if len({item.id for item in self.assets}) != len(self.assets) or len(
            {item.pin.path for item in self.assets}
        ) != len(self.assets):
            raise ValueError("PROVIDER_ASSET_DUPLICATE")
        for source in self.package.sources:
            uri = urlsplit(source.uri)
            if uri.query or uri.fragment:
                raise ValueError("PROVIDER_SOURCE_URI_REQUIRES_PUBLIC_LOCATOR")
        return self
