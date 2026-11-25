"""Small durable orchestrator for evidence-producing SDSS workflows.

The runner intentionally executes registered Python adapters only. It never
accepts shell commands from workflow JSON, which keeps UI/API plans from
becoming an arbitrary command execution surface.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class StepSpec(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    adapter: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,127}$")
    depends_on: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    allow_resume: bool = True


class WorkflowSpec(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    workflow_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    trace_id: str = Field(min_length=1, max_length=128)
    input_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    steps: tuple[StepSpec, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dag(self) -> "WorkflowSpec":
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("workflow step ids must be unique")
        seen: set[str] = set()
        for step in self.steps:
            missing = set(step.depends_on) - seen
            if missing:
                raise ValueError(f"dependencies must precede step {step.id}: {sorted(missing)}")
            if step.id in step.depends_on:
                raise ValueError("a step cannot depend on itself")
            seen.add(step.id)
        return self

    @property
    def plan_sha256(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()


class StepResult(StrictModel):
    status: Literal["SUCCEEDED", "BLOCKED", "FAILED"]
    evidence_sha256: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    message: str = ""

    @model_validator(mode="after")
    def validate_semantics(self) -> "StepResult":
        if self.status == "SUCCEEDED" and self.blockers:
            raise ValueError("successful steps cannot contain blockers")
        if self.status == "BLOCKED" and not self.blockers:
            raise ValueError("blocked steps require blockers")
        for digest in self.evidence_sha256:
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("evidence SHA-256 must be lowercase hexadecimal")
        return self


class StepState(StrictModel):
    status: Literal["PENDING", "RUNNING", "SUCCEEDED", "BLOCKED", "FAILED"]
    attempts: int = Field(ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    evidence_sha256: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    message: str = ""


class WorkflowState(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    workflow_id: str
    trace_id: str
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["PENDING", "RUNNING", "SUCCEEDED", "BLOCKED", "FAILED"]
    created_at: datetime
    updated_at: datetime
    steps: dict[str, StepState]


Adapter = Callable[[StepSpec, WorkflowState], StepResult]


def _atomic_json(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = value.model_dump_json(indent=2).encode("utf-8") + b"\n"
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class WorkflowRunner:
    def __init__(self, root: Path, adapters: dict[str, Adapter]):
        self.root = Path(root).resolve()
        self.adapters = dict(adapters)

    def _paths(self, spec: WorkflowSpec) -> tuple[Path, Path]:
        directory = self.root / spec.workflow_id
        return directory / "state.json", directory / ".execution.lock"

    def _new_state(self, spec: WorkflowSpec) -> WorkflowState:
        now = datetime.now(UTC)
        return WorkflowState(
            workflow_id=spec.workflow_id,
            trace_id=spec.trace_id,
            plan_sha256=spec.plan_sha256,
            input_fingerprint=spec.input_fingerprint,
            status="PENDING",
            created_at=now,
            updated_at=now,
            steps={step.id: StepState(status="PENDING", attempts=0) for step in spec.steps},
        )

    def _load(self, spec: WorkflowSpec, state_path: Path) -> WorkflowState:
        if not state_path.exists():
            return self._new_state(spec)
        state = WorkflowState.model_validate_json(state_path.read_text(encoding="utf-8"))
        if state.input_fingerprint != spec.input_fingerprint:
            raise ValueError("INPUT_DRIFT_REQUIRES_NEW_WORKFLOW_ID")
        if state.plan_sha256 != spec.plan_sha256:
            raise ValueError("PLAN_DRIFT_REQUIRES_NEW_WORKFLOW_ID")
        return state

    def run(self, spec: WorkflowSpec, *, execute: bool = False) -> WorkflowState:
        unknown = sorted({step.adapter for step in spec.steps} - self.adapters.keys())
        if unknown:
            raise ValueError(f"unregistered adapters: {unknown}")
        state_path, lock_path = self._paths(spec)
        if not execute:
            return self._load(spec, state_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(descriptor)
        try:
            state = self._load(spec, state_path)
            for step in spec.steps:
                prior = state.steps[step.id]
                if prior.status == "SUCCEEDED" and step.allow_resume:
                    continue
                dependency_states = [state.steps[item].status for item in step.depends_on]
                if any(status != "SUCCEEDED" for status in dependency_states):
                    blocked = StepState(
                        status="BLOCKED",
                        attempts=prior.attempts,
                        blockers=("DEPENDENCY_NOT_SUCCEEDED",),
                        message="dependency gate is not satisfied",
                    )
                    state = state.model_copy(
                        update={
                            "status": "BLOCKED",
                            "updated_at": datetime.now(UTC),
                            "steps": {**state.steps, step.id: blocked},
                        }
                    )
                    _atomic_json(state_path, state)
                    return state
                running = StepState(
                    status="RUNNING",
                    attempts=prior.attempts + 1,
                    started_at=datetime.now(UTC),
                )
                state = state.model_copy(
                    update={
                        "status": "RUNNING",
                        "updated_at": datetime.now(UTC),
                        "steps": {**state.steps, step.id: running},
                    }
                )
                _atomic_json(state_path, state)
                try:
                    result = self.adapters[step.adapter](step, state)
                except Exception as error:
                    result = StepResult(status="FAILED", message=type(error).__name__)
                finished = StepState(
                    status=result.status,
                    attempts=running.attempts,
                    started_at=running.started_at,
                    completed_at=datetime.now(UTC),
                    evidence_sha256=result.evidence_sha256,
                    blockers=result.blockers,
                    message=result.message,
                )
                state = state.model_copy(
                    update={
                        "status": result.status,
                        "updated_at": datetime.now(UTC),
                        "steps": {**state.steps, step.id: finished},
                    }
                )
                _atomic_json(state_path, state)
                if result.status != "SUCCEEDED":
                    return state
            state = state.model_copy(
                update={"status": "SUCCEEDED", "updated_at": datetime.now(UTC)}
            )
            _atomic_json(state_path, state)
            return state
        finally:
            lock_path.unlink(missing_ok=True)
