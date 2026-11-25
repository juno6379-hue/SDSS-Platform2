"""Run and resume approved jobs using the existing WorkflowRunner."""

import argparse
import json
import os
import sys
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from time import sleep

from services.api.evidence import LOCK_PATH, ROOT, EvidenceStore
from services.api.pinned import LOCK_SHA256
from services.api.results import DATABASE, verify_evidence
from services.orchestration import StepResult, StepSpec, WorkflowRunner, WorkflowSpec
from services.results.catalog import Pin, package_pins, prepare_package
from services.results.registry import ResultRegistry

from .contracts import Approval, Config, JobError, ModelPin, canonical, digest
from .providers import HttpProvider, ProviderTemporary
from .store import FINAL, JobStore

MAX_ATTEMPTS = 5


def configuration_path():
    configured = os.getenv("SDSS_JOBS_CONFIG")
    return Path(configured) if configured else None


def state_directory(root):
    return (root / os.getenv("SDSS_JOBS_STATE_DIR", "data/curated/jobs")).resolve()


class Worker:
    def __init__(
        self,
        queue,
        evidence,
        registry,
        config_loader,
        provider_factory=HttpProvider,
        model_selector=None,
    ):
        self.queue = queue
        self.evidence = evidence
        self.registry = registry
        self.config_loader = config_loader
        self.provider_factory = provider_factory
        self.model_selector = model_selector
        self.workflow_root = queue.directory / "workflows"
        if not queue.directory.is_relative_to(evidence.root):
            raise JobError("JOB_OUTPUT_ROOT_OUTSIDE_PROJECT")

    def configured_provider(self, row, approval):
        config = self.config_loader()
        provider = config.provider_ready(approval.provider)
        if provider.fingerprint != row["provider_fingerprint"]:
            raise JobError("JOB_PROVIDER_CONFIG_DRIFT")
        return config, provider

    def verify_submission(self, config, provider, approval, pin, job_id):
        approved, current_pin = config.resolve_approval(self.evidence.root, approval.approval_id)
        if current_pin != pin or approved != approval:
            raise JobError("JOB_APPROVAL_EVIDENCE_DRIFT")
        approval.ensure_current()
        with self.evidence.safe_path(pin.path).open("rb") as handle:
            raw = handle.read(pin.bytes + 1)
        if len(raw) != pin.bytes or sha256(raw).hexdigest() != pin.sha256:
            raise JobError("JOB_APPROVAL_EVIDENCE_DRIFT")
        self.save_output(self.output_prefix(job_id) + "/approval.json", raw)
        if provider.kind == "project_model":
            binding = self.model_selector(approval.model.name) if self.model_selector else None
            if not binding or binding["model"] != approval.model.model_dump():
                raise JobError("ACTIVE_MODEL_VERSION_PIN_MISMATCH")
            return self.save_output(
                self.output_prefix(job_id) + "/model-release.json", canonical(binding)
            )
        return None

    def output_prefix(self, job_id):
        return (
            (self.queue.directory / "received" / job_id).relative_to(self.evidence.root).as_posix()
        )

    def save_output(self, name, data):
        path = self.evidence.safe_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            temporary = path.with_name(path.name + ".incoming")
            with temporary.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if path.exists():
                if path.read_bytes() != data:
                    raise JobError("JOB_OUTPUT_REPLAY_CONFLICT")
            else:
                os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return {"path": name, "bytes": len(data), "sha256": sha256(data).hexdigest()}

    def verify_output(self, provider, job_id, approval, approval_pin, provider_spec):
        output = provider.result(job_id)
        if output.model != approval.model:
            raise JobError("JOB_OUTPUT_MODEL_PIN_MISMATCH")
        package = output.package.model_dump(mode="json")
        pins = {asset.pin.path: asset for asset in output.assets}
        referenced = {pin["path"] for pin in package_pins(package)}
        if referenced != pins.keys():
            raise JobError("JOB_OUTPUT_ASSET_COVERAGE_MISMATCH")
        prefix = (
            (self.queue.directory / "received" / job_id).relative_to(self.evidence.root).as_posix()
        )
        local_pins = {}
        for pin in package_pins(package):
            asset = pins[pin["path"]]
            if asset.pin.model_dump() != pin:
                raise JobError("JOB_OUTPUT_ASSET_PIN_MISMATCH")
            if pin["path"] in local_pins:
                continue
            name = f"{prefix}/assets/{asset.id}/{pin['path']}"
            path = self.evidence.safe_path(name)
            if path.is_file():
                local_pin = {**pin, "path": name}
                verify_evidence(self.evidence, [local_pin])
            else:
                raw = provider.asset(job_id, asset)
                if len(raw) != asset.pin.bytes or sha256(raw).hexdigest() != asset.pin.sha256:
                    raise JobError("JOB_OUTPUT_ASSET_HASH_MISMATCH")
                local_pin = self.save_output(name, raw)
            local_pins[pin["path"]] = local_pin

        normalized = deepcopy(package)
        for source in normalized["sources"]:
            for field in ("raw", "license_evidence"):
                if source.get(field):
                    source[field] = local_pins[source[field]["path"]]
        for group in ("layers", "reports"):
            for item in normalized[group]:
                item["file"] = local_pins[item["file"]["path"]]
        checked = prepare_package(
            normalized,
            safe_path=self.evidence.safe_path,
            verify_pins=lambda entries: verify_evidence(self.evidence, entries),
            adapter_checks=("PROVIDER_RESPONSE_JOB_AND_MODEL_BINDING",),
        )
        release_pin = None
        if provider_spec.kind == "project_model":
            release_pin = json.loads(self.queue.get(job_id)["model_release"])
            verify_evidence(self.evidence, [release_pin])
        approval_snapshot = {**approval_pin.model_dump(), "path": f"{prefix}/approval.json"}
        verify_evidence(self.evidence, [approval_snapshot])
        provider_manifest = self.save_output(
            f"{prefix}/provider-manifest.json", canonical(output.model_dump(mode="json"))
        )
        receipt = self.save_output(
            f"{prefix}/receipt.json",
            canonical(
                {
                    "schema_version": "sdss-provider-receipt/1",
                    "job_id": job_id,
                    "approval": approval_snapshot,
                    "provider": approval.provider,
                    "provider_fingerprint": provider_spec.fingerprint,
                    "operation": approval.operation,
                    "model_release": release_pin,
                    "approval_parameters_sha256": digest(approval.parameters),
                    "model": approval.model.model_dump(),
                    "provider_manifest": provider_manifest,
                    "assets": list(local_pins.values()),
                }
            ),
        )
        return checked, receipt

    def workflow(self, row, approval, approval_pin, config, spec, provider):
        job_id = row["id"]
        workflow = WorkflowSpec(
            workflow_id=job_id,
            trace_id=job_id,
            input_fingerprint=digest(
                [approval_pin.sha256, spec.fingerprint, approval.model.model_dump()]
            ),
            steps=(
                StepSpec(id="submit", adapter="provider.submit"),
                StepSpec(id="poll", adapter="provider.poll", depends_on=("submit",)),
                StepSpec(id="register", adapter="result.register", depends_on=("poll",)),
            ),
        )

        def submit(_step, _state):
            working = self.queue.get(job_id)
            release_pin = None
            if not working["remote_started"]:
                release_pin = self.verify_submission(config, spec, approval, approval_pin, job_id)
            # Journal before sending. A crash before acknowledgment reuses the same provider key.
            working = self.queue.update(
                job_id,
                state="RUNNING",
                mark_remote=True,
                failure=None,
                model_release=json.dumps(release_pin) if release_pin else None,
            )
            if working["state"] != "RUNNING":
                return StepResult(status="BLOCKED", blockers=("JOB_CANCELLATION_REQUESTED",))
            status = provider.submit(job_id, approval, approval_pin.sha256)
            if status.state in {"FAILED", "CANCELLED"}:
                raise JobError("PROVIDER_SUBMISSION_REJECTED")
            self.queue.update(
                job_id, state="RUNNING", progress=min(status.progress, 99), failure=False
            )
            return StepResult(
                status="SUCCEEDED", evidence_sha256=(approval_pin.sha256,), message=job_id
            )

        def poll(_step, _state):
            working = self.queue.get(job_id)
            if working["cancel_requested"]:
                return StepResult(status="BLOCKED", blockers=("JOB_CANCELLATION_REQUESTED",))
            status = provider.progress(job_id)
            if status.state == "FAILED":
                self.queue.update(
                    job_id, state="FAILED", blocker="PROVIDER_JOB_FAILED", progress=status.progress
                )
                return StepResult(status="FAILED", blockers=("PROVIDER_JOB_FAILED",))
            if status.state == "CANCELLED":
                self.queue.update(job_id, state="CANCELLED", progress=status.progress)
                return StepResult(status="FAILED", blockers=("PROVIDER_JOB_CANCELLED",))
            if status.state != "SUCCEEDED":
                self.queue.update(
                    job_id, state="RUNNING", progress=min(status.progress, 99), failure=False
                )
                return StepResult(status="BLOCKED", blockers=("PROVIDER_JOB_IN_PROGRESS",))
            return StepResult(status="SUCCEEDED")

        def register(_step, _state):
            working = self.queue.get(job_id)
            if working["cancel_requested"]:
                return StepResult(status="BLOCKED", blockers=("JOB_CANCELLATION_REQUESTED",))
            package, receipt = self.verify_output(provider, job_id, approval, approval_pin, spec)
            working = self.queue.update(job_id, state="FINALIZING", progress=99, failure=None)
            if working["state"] != "FINALIZING":
                return StepResult(status="BLOCKED", blockers=("JOB_CANCELLATION_REQUESTED",))
            result = self.registry.register(
                domain="workflow",
                source_key=job_id,
                title=f"{approval.provider} · {approval.operation}",
                evidence_status="IMPLEMENTED_UNVERIFIED",
                summary={
                    "job_id": job_id,
                    "provider": approval.provider,
                    "operation": approval.operation,
                    "model": approval.model.model_dump(),
                    "source_role": "PROVIDER_RECORDED_OUTPUT",
                },
                evidence=[receipt],
                blockers=["INDEPENDENT_SCIENTIFIC_REVIEW_PENDING"],
            )
            package_sha = self.registry.attach_package(result["id"], package)
            return StepResult(
                status="SUCCEEDED",
                evidence_sha256=(receipt["sha256"], package_sha),
                message=result["id"],
            )

        def safely(adapter):
            def run(step, state):
                try:
                    return adapter(step, state)
                except ProviderTemporary as error:
                    self.handle_temporary(job_id, error)
                    return StepResult(status="BLOCKED", blockers=(error.code,))
                except Exception as error:
                    code = (
                        error.code
                        if isinstance(error, JobError)
                        else "JOB_EXECUTION_VALIDATION_FAILED"
                    )
                    self.queue.fail(job_id, code)
                    return StepResult(status="FAILED", blockers=(code,))

            return run

        runner = WorkflowRunner(
            self.workflow_root,
            {
                "provider.submit": safely(submit),
                "provider.poll": safely(poll),
                "result.register": safely(register),
            },
        )
        # The OS-backed outer lock proves that prior worker-owned lock files are stale.
        lock = self.workflow_root / job_id / ".execution.lock"
        lock.unlink(missing_ok=True)
        state = runner.run(workflow, execute=True)
        if state.status == "SUCCEEDED":
            registration = state.steps["register"]
            self.queue.update(
                job_id,
                state="SUCCEEDED",
                progress=100,
                result=(registration.message, registration.evidence_sha256[-1]),
            )
        return state

    def handle_temporary(self, job_id, error):
        row = self.queue.get(job_id)
        if row["state"] in FINAL:
            return
        if row["failures"] + 1 >= MAX_ATTEMPTS and row["state"] not in {"FINALIZING", "CANCELLING"}:
            self.queue.fail(job_id, error.code + "_RETRY_LIMIT")
        else:
            self.queue.update(job_id, state=row["state"], blocker=error.code, failure=True)

    def process(self, job_id) -> None:
        row = self.queue.get(job_id)
        if row["state"] in FINAL:
            return
        approval = Approval.model_validate_json(row["approval"])
        approval_pin = Pin.model_validate_json(row["approval_pin"])
        try:
            config, spec = self.configured_provider(row, approval)
            with self.provider_factory(spec) as provider:
                if row["cancel_requested"]:
                    action = provider.cancel(job_id)
                    if action.state == "CANCELLED":
                        self.queue.update(job_id, state="CANCELLED", progress=action.progress)
                    elif action.state in {"FAILED", "SUCCEEDED"}:
                        self.queue.update(
                            job_id, state="FAILED", blocker="PROVIDER_ALREADY_TERMINAL_AFTER_CANCEL"
                        )
                    else:
                        self.queue.update(job_id, state="CANCELLING", progress=action.progress)
                else:
                    self.workflow(row, approval, approval_pin, config, spec, provider)
        except ProviderTemporary as error:
            self.handle_temporary(job_id, error)
        except JobError as error:
            if error.code in {
                "JOB_PROVIDER_CONFIG_NOT_SET",
                "JOB_PROVIDER_CONFIG_INVALID",
                "JOB_PROVIDER_CREDENTIAL_NOT_CONFIGURED",
            }:
                self.queue.update(job_id, state=row["state"], blocker=error.code, failure=None)
            else:
                self.queue.fail(job_id, error.code)

    def tick(self, limit=8):
        try:
            with self.queue.worker_lock():
                jobs = self.queue.pending_ids(limit)
                for job_id in jobs:
                    self.process(job_id)
                return len(jobs)
        except JobError as error:
            if error.code == "JOB_WORKER_BUSY":
                return 0
            raise


def project_active_model(evidence, name):
    from services.api.model_releases import model_release_store
    from services.mlops.releases import ReleaseBlocked

    try:
        candidate, manifest_sha, activation_revision = model_release_store(evidence).active_version(
            name
        )
    except ReleaseBlocked as error:
        raise JobError("ACTIVE_MODEL_VERSION_NOT_APPROVED") from error
    return {
        "model": ModelPin(
            name=name, version=candidate.version, artifact_sha256=candidate.artifact.sha256
        ).model_dump(),
        "manifest_sha256": manifest_sha,
        "activation_revision": activation_revision,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=5)
    args = parser.parse_args()
    if not 5 <= args.interval <= 300:
        parser.error("--interval must be between 5 and 300 seconds")
    try:
        Config.load(
            configuration_path()
        )  # Avoid creating queue state when the deployment is unconfigured.
        evidence = EvidenceStore(ROOT, LOCK_PATH, LOCK_SHA256)
        worker = Worker(
            JobStore(state_directory(ROOT)),
            evidence,
            ResultRegistry(DATABASE),
            lambda: Config.load(configuration_path()),
            model_selector=lambda name: project_active_model(evidence, name),
        )
        while True:
            processed = worker.tick()
            if args.once:
                print(json.dumps({"jobs_checked": processed}))
                return
            sleep(args.interval)
    except JobError as error:
        print(error.code, file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
