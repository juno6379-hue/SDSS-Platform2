"""Run local registration for selected, evidence-backed result sources."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from services.orchestration import StepResult, StepSpec, WorkflowRunner, WorkflowSpec
from services.results.registry import RegistryError, ResultRegistry

from .evidence import LOCK_PATH, ROOT, EvidenceBlocked, EvidenceStore
from .pinned import LOCK_SHA256
from .results import DATABASE, catalog, verify_evidence

STATE_DIRECTORY = ROOT / "data/curated/results/workflows"
PAYLOAD_FIELDS = (
    "domain",
    "source_key",
    "title",
    "evidence_status",
    "summary",
    "evidence",
    "blockers",
)


def _digest(payload):
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def run_registration(*, sources, store, database, state_root, workflow_id, execute=False):
    """Return a persisted state and result IDs after locally validating the selected pins."""
    if not sources or len(set(sources)) != len(sources):
        raise ValueError("RESULT_WORKFLOW_REQUIRES_DISTINCT_SOURCES")
    fixed_catalog = catalog()
    payloads = {}
    for number, source in enumerate(sorted(sources), start=1):
        if source not in fixed_catalog:
            raise EvidenceBlocked("RESULT_SOURCE_UNKNOWN:" + source)
        payloads[f"{number:02}"] = {**fixed_catalog[source], "source_key": source}

    database = Path(database).resolve()
    phases = ("verify", "register", "lookup")
    checks = tuple(f"verify-{number}" for number in payloads)
    steps = tuple(
        StepSpec(
            id=f"{phase}-{number}",
            adapter=f"result.{phase}",
            depends_on=checks
            if phase == "register"
            else (f"register-{number}",)
            if phase == "lookup"
            else (),
            allow_resume=phase == "register",
        )
        for phase in phases
        for number in payloads
    )
    fingerprint = _digest(
        {"sources": [_digest(payload) for payload in payloads.values()], "database": str(database)}
    )
    spec = WorkflowSpec(
        workflow_id=workflow_id,
        trace_id=f"result-registration-{fingerprint[:16]}",
        input_fingerprint=fingerprint,
        steps=steps,
    )
    repository = None

    def adapter(step, state):
        nonlocal repository
        phase, number = step.id.split("-")
        payload = payloads[number]
        pins = payload["evidence"]
        try:
            if phase in {"verify", "register"}:
                verify_evidence(store, pins)
            if phase == "verify":
                return StepResult(
                    status="SUCCEEDED", evidence_sha256=tuple(pin["sha256"] for pin in pins)
                )
            if repository is None:
                repository = ResultRegistry(database)
            if phase == "register":
                result = repository.register(**payload)
            else:
                result = repository.get(state.steps[f"register-{number}"].message)
                if _digest({key: result[key] for key in PAYLOAD_FIELDS}) != _digest(payload):
                    return StepResult(
                        status="BLOCKED", blockers=("RESULT_WORKFLOW_READBACK_DRIFT",)
                    )
            return StepResult(status="SUCCEEDED", message=result["id"])
        except EvidenceBlocked as error:
            return StepResult(status="BLOCKED", blockers=(str(error),))
        except RegistryError as error:
            return StepResult(status="BLOCKED", blockers=(error.code,))

    runner = WorkflowRunner(state_root, {f"result.{phase}": adapter for phase in phases})
    state = runner.run(spec, execute=execute)
    result_ids = {
        payload["source_key"]: state.steps[f"lookup-{number}"].message
        for number, payload in payloads.items()
        if state.status == "SUCCEEDED"
    }
    return state, result_ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", action="append", required=True, help="catalog source key (repeatable)"
    )
    parser.add_argument("--workflow-id", default="result-registration")
    parser.add_argument("--database", type=Path, default=DATABASE)
    parser.add_argument("--state-root", type=Path, default=STATE_DIRECTORY)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        state, result_ids = run_registration(
            sources=args.source,
            store=EvidenceStore(ROOT, LOCK_PATH, LOCK_SHA256),
            database=args.database,
            state_root=args.state_root,
            workflow_id=args.workflow_id,
            execute=args.execute,
        )
    except FileExistsError:
        parser.error("RESULT_WORKFLOW_ALREADY_RUNNING")
    except ValueError as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "status": state.status,
                "state_file": str(args.state_root.resolve() / state.workflow_id / "state.json"),
                "result_ids": result_ids,
                "external_requests": 0,
                "training_executed": False,
                "deployment_executed": False,
            },
            ensure_ascii=False,
        )
    )
    return int(state.status in {"BLOCKED", "FAILED"})


if __name__ == "__main__":
    raise SystemExit(main())
