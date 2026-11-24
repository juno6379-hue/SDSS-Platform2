import hashlib

import pytest

from services.orchestration.workflow import (
    StepResult,
    StepSpec,
    WorkflowRunner,
    WorkflowSpec,
)


def spec(fingerprint: str = "a" * 64) -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="gate-demo",
        trace_id="trace-demo",
        input_fingerprint=fingerprint,
        steps=(
            StepSpec(id="source", adapter="source"),
            StepSpec(id="qc", adapter="qc", depends_on=("source",)),
            StepSpec(id="training_gate", adapter="gate", depends_on=("qc",)),
        ),
    )


def evidence(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()


def test_preflight_has_no_files_or_adapter_calls(tmp_path) -> None:
    calls = []
    runner = WorkflowRunner(
        tmp_path,
        {name: lambda *_, name=name: calls.append(name) for name in ("source", "qc", "gate")},
    )
    state = runner.run(spec(), execute=False)
    assert state.status == "PENDING"
    assert calls == []
    assert not list(tmp_path.rglob("*"))


def test_success_is_durable_and_resume_is_idempotent(tmp_path) -> None:
    calls = []

    def adapter(step, _state):
        calls.append(step.id)
        return StepResult(status="SUCCEEDED", evidence_sha256=(evidence(step.id),))

    runner = WorkflowRunner(tmp_path, {name: adapter for name in ("source", "qc", "gate")})
    first = runner.run(spec(), execute=True)
    second = runner.run(spec(), execute=True)
    assert first.status == second.status == "SUCCEEDED"
    assert calls == ["source", "qc", "training_gate"]
    assert not list(tmp_path.rglob(".execution.lock"))


def test_blocked_gate_stops_downstream_and_persists_reason(tmp_path) -> None:
    calls = []

    def source(step, _state):
        calls.append(step.id)
        return StepResult(status="SUCCEEDED", evidence_sha256=(evidence(step.id),))

    def blocked(step, _state):
        calls.append(step.id)
        return StepResult(status="BLOCKED", blockers=("SPATIAL_COVERAGE_INSUFFICIENT",))

    runner = WorkflowRunner(tmp_path, {"source": source, "qc": blocked, "gate": source})
    state = runner.run(spec(), execute=True)
    assert state.status == "BLOCKED"
    assert calls == ["source", "qc"]
    assert state.steps["training_gate"].status == "PENDING"
    assert state.steps["qc"].blockers == ("SPATIAL_COVERAGE_INSUFFICIENT",)


def test_plan_or_input_drift_cannot_reuse_state(tmp_path) -> None:
    adapter = lambda step, _state: StepResult(  # noqa: E731
        status="SUCCEEDED", evidence_sha256=(evidence(step.id),)
    )
    runner = WorkflowRunner(tmp_path, {name: adapter for name in ("source", "qc", "gate")})
    runner.run(spec(), execute=True)
    with pytest.raises(ValueError, match="INPUT_DRIFT"):
        runner.run(spec("b" * 64), execute=True)
    changed = spec().model_copy(
        update={
            "steps": (
                StepSpec(id="source", adapter="source"),
                StepSpec(id="qc", adapter="qc", depends_on=("source",), allow_resume=False),
            )
        }
    )
    with pytest.raises(ValueError, match="PLAN_DRIFT"):
        runner.run(changed, execute=True)


def test_unknown_adapter_and_concurrent_lock_fail_closed(tmp_path) -> None:
    runner = WorkflowRunner(tmp_path, {})
    with pytest.raises(ValueError, match="unregistered adapters"):
        runner.run(spec())

    valid = WorkflowRunner(
        tmp_path,
        {name: lambda *_: StepResult(status="SUCCEEDED") for name in ("source", "qc", "gate")},
    )
    _, lock = valid._paths(spec())
    lock.parent.mkdir(parents=True)
    lock.write_text("active", encoding="utf-8")
    with pytest.raises(FileExistsError):
        valid.run(spec(), execute=True)
