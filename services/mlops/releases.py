"""Evidence-bound model version selection for approved inference."""

import json
import re
import sqlite3
from contextlib import contextmanager
from hashlib import file_digest, sha256
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from services.mlops.gates import (
    DataReadiness,
    DeploymentEvidence,
    evaluate_deployment_gate,
    evaluate_training_gate,
)
from services.results.catalog import AssetID, Pin, Strict
from services.results.registry import _json, _timestamp


class ReleaseBlocked(ValueError):
    pass


class ModelPin(Pin):
    bytes: int = Field(ge=1, le=512 * 1024**2, strict=True)


class ModelRelease(Strict):
    model_name: AssetID
    version: AssetID
    runtime: Literal["onnx"]
    artifact: ModelPin
    dataset_manifest: Pin
    readiness: Pin
    training_report: Pin
    evaluation: Pin
    environment: Pin
    security_report: Pin
    rollback_report: Pin
    accuracy_reference: Pin
    deployment: DeploymentEvidence
    result_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    package_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def matching_digests(self):
        evidence = self.deployment
        checks = (
            evidence.model_id == f"{self.model_name}:{self.version}",
            evidence.model_sha256 == self.artifact.sha256,
            evidence.training_report_sha256 == self.training_report.sha256,
            evidence.reproducible_environment_sha256 == self.environment.sha256,
            evidence.registry_record_sha256 == self.package_sha256,
            evidence.independent_accuracy is not None
            and evidence.independent_accuracy.evaluator_report_sha256 == self.evaluation.sha256
            and evidence.independent_accuracy.reference_sha256 == self.accuracy_reference.sha256,
        )
        if not all(checks):
            raise ValueError("MODEL_RELEASE_DIGEST_LINKS_MISMATCH")
        return self


def read_pin(root, pin, *, return_bytes=False):
    path = (root / pin.path).resolve()
    if not path.is_relative_to(root):
        raise ReleaseBlocked("MODEL_EVIDENCE_PATH_OUTSIDE_ROOT")
    try:
        with path.open("rb") as handle:
            if path.stat().st_size != pin.bytes:
                raise ReleaseBlocked("MODEL_EVIDENCE_SIZE_DRIFT")
            if return_bytes:
                value = handle.read(pin.bytes + 1)
                valid = len(value) == pin.bytes and sha256(value).hexdigest() == pin.sha256
            else:
                value = None
                valid = file_digest(handle, "sha256").hexdigest() == pin.sha256
            if not valid:
                raise ReleaseBlocked("MODEL_EVIDENCE_SHA_DRIFT")
            return value
    except OSError as error:
        raise ReleaseBlocked("MODEL_EVIDENCE_UNAVAILABLE") from error


def document(root, pin):
    try:
        value = json.loads(read_pin(root, pin, return_bytes=True))
        if not isinstance(value, dict):
            raise TypeError("object required")
        return value
    except (TypeError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ReleaseBlocked("MODEL_EVIDENCE_JSON_INVALID") from error


def verify_release(root, candidate, resolve_catalog):
    pins = (
        candidate.artifact,
        candidate.dataset_manifest,
        candidate.training_report,
        candidate.environment,
        candidate.accuracy_reference,
    )
    for pin in pins:
        read_pin(root, pin)
    readiness = DataReadiness.model_validate(document(root, candidate.readiness))
    if readiness.manifest_sha256 != candidate.dataset_manifest.sha256:
        raise ReleaseBlocked("MODEL_DATASET_LINEAGE_MISMATCH")
    training = evaluate_training_gate(readiness)
    if not training.allowed:
        raise ReleaseBlocked("MODEL_TRAINING_GATE:" + ",".join(training.blockers))
    deployment = evaluate_deployment_gate(training, candidate.deployment)
    if not deployment.allowed:
        raise ReleaseBlocked("MODEL_DEPLOYMENT_GATE:" + ",".join(deployment.blockers))

    accuracy = candidate.deployment.independent_accuracy
    binding = {"model_sha256": candidate.artifact.sha256}
    expected = {
        "reference_sha256": accuracy.reference_sha256,
        "reference_kind": accuracy.reference_kind.value,
        "sample_count": accuracy.sample_count,
        "macro_f1": accuracy.macro_f1,
        "overall_accuracy": accuracy.overall_accuracy,
        "spatially_disjoint": accuracy.spatially_disjoint,
        "temporally_matched": accuracy.temporally_matched,
        "label_source_disjoint": accuracy.label_source_disjoint,
    }
    for pin, facts in (
        (candidate.evaluation, expected),
        (candidate.security_report, {"status": "PASSED"}),
        (candidate.rollback_report, {"status": "PASSED"}),
        (
            candidate.training_report,
            {"status": "SUCCEEDED", "dataset_sha256": candidate.dataset_manifest.sha256},
        ),
    ):
        evidence = document(root, pin)
        if any(evidence.get(key) != value for key, value in (binding | facts).items()):
            raise ReleaseBlocked("MODEL_VERIFICATION_REPORT_BINDING_MISMATCH")

    result = resolve_catalog(candidate.result_id)
    if (
        result["package_sha256"] != candidate.package_sha256
        or result["governance"]["scientific"]["status"] != "APPROVED"
    ):
        raise ReleaseBlocked("MODEL_RESULT_SCIENTIFIC_APPROVAL_REQUIRED")
    # Deployment is internal. Public access to the result still uses the separate publication gate.
    if candidate.artifact.sha256 not in {
        source["raw"]["sha256"] for source in result["package"]["sources"]
    }:
        raise ReleaseBlocked("MODEL_CATALOG_ARTIFACT_LINK_MISSING")


class ModelReleases:
    def __init__(self, root, path, resolve_catalog):
        self.root = Path(root).resolve()
        self.path = Path(path)
        self.resolve_catalog = resolve_catalog
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction(write=True) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS model_releases (
                    model TEXT, version TEXT, manifest_sha TEXT NOT NULL, manifest TEXT NOT NULL,
                    PRIMARY KEY(model, version))"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS model_release_events (
                    model TEXT, revision INTEGER, version TEXT NOT NULL, previous_version TEXT, action TEXT NOT NULL,
                    approver TEXT NOT NULL, approval_sha TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(model, revision), FOREIGN KEY(model, version) REFERENCES model_releases(model, version))"""
            )

    @contextmanager
    def transaction(self, *, write=False):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def candidate(connection, name, version):
        row = connection.execute(
            "SELECT * FROM model_releases WHERE model = ? AND version = ?", (name, version)
        ).fetchone()
        if row is None:
            raise ReleaseBlocked("MODEL_RELEASE_NOT_FOUND")
        digest = sha256(row["manifest"].encode()).hexdigest()
        if digest != row["manifest_sha"]:
            raise ReleaseBlocked("MODEL_RELEASE_MANIFEST_DRIFT")
        return ModelRelease.model_validate_json(row["manifest"]), digest

    @staticmethod
    def events(connection, name):
        return [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM model_release_events WHERE model = ? ORDER BY revision DESC",
                (name,),
            )
        ]

    def list(self):
        with self.transaction() as connection:
            models = [
                row["model"]
                for row in connection.execute(
                    "SELECT DISTINCT model FROM model_releases ORDER BY model"
                )
            ]
            return [
                {
                    "model": name,
                    "versions": [
                        dict(row)
                        for row in connection.execute(
                            "SELECT version, manifest_sha FROM model_releases WHERE model = ? ORDER BY version",
                            (name,),
                        )
                    ],
                    "history": self.events(connection, name),
                }
                for name in models
            ]

    def register(self, candidate):
        verify_release(self.root, candidate, self.resolve_catalog)
        value = _json(candidate.model_dump(mode="json"))
        digest = sha256(value.encode()).hexdigest()
        with self.transaction(write=True) as connection:
            connection.execute(
                "INSERT INTO model_releases VALUES (?, ?, ?, ?) ON CONFLICT(model, version) DO NOTHING",
                (candidate.model_name, candidate.version, digest, value),
            )
            _, stored_digest = self.candidate(connection, candidate.model_name, candidate.version)
            if stored_digest != digest:
                raise ReleaseBlocked("MODEL_RELEASE_VERSION_CONFLICT")
        return {"model": candidate.model_name, "version": candidate.version, "manifest_sha": digest}

    def transition(self, name, *, version, action, expected_revision, approval, approver):
        with self.transaction(write=True) as connection:
            events = self.events(connection, name)
            current = events[0] if events else None
            revision = current["revision"] if current else 0
            if revision != expected_revision:
                raise ReleaseBlocked("MODEL_RELEASE_REVISION_CONFLICT")
            previous_version = current["version"] if current else None
            if version == previous_version:
                raise ReleaseBlocked("MODEL_VERSION_ALREADY_ACTIVE")
            if action == "rollback" and version not in {event["version"] for event in events}:
                raise ReleaseBlocked("MODEL_ROLLBACK_TARGET_NEVER_ACTIVE")
            candidate, digest = self.candidate(connection, name, version)
            expected = {
                "authority": approver,
                "action": action,
                "model": name,
                "version": version,
                "manifest_sha": digest,
                "previous_revision": revision,
                "approval_id": candidate.deployment.operator_approval_id,
            }
            decision = document(self.root, approval)
            if any(decision.get(key) != value for key, value in expected.items()):
                raise ReleaseBlocked("MODEL_OPERATOR_APPROVAL_BINDING_INVALID")
            verify_release(self.root, candidate, self.resolve_catalog)
            connection.execute(
                "INSERT INTO model_release_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    name,
                    revision + 1,
                    version,
                    previous_version,
                    action,
                    approver,
                    approval.sha256,
                    _timestamp(),
                ),
            )
            return self.events(connection, name)[0]

    def active_version(self, name):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", name):
            raise ReleaseBlocked("MODEL_NAME_INVALID")
        with self.transaction() as connection:
            events = self.events(connection, name)
            if not events:
                raise ReleaseBlocked("MODEL_ACTIVE_VERSION_UNAVAILABLE")
            event = events[0]
            candidate, digest = self.candidate(connection, name, event["version"])
        verify_release(self.root, candidate, self.resolve_catalog)
        return candidate, digest, event["revision"]

    def run_onnx(self, name, inputs):
        import onnxruntime

        candidate, digest, revision = self.active_version(name)
        model = read_pin(self.root, candidate.artifact, return_bytes=True)
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        session = onnxruntime.InferenceSession(
            model, sess_options=options, providers=["CPUExecutionProvider"]
        )
        outputs = session.run(None, inputs)
        return outputs, {
            "model": name,
            "version": candidate.version,
            "revision": revision,
            "manifest_sha": digest,
            "artifact_sha256": candidate.artifact.sha256,
            "dataset_sha256": candidate.dataset_manifest.sha256,
            "result_id": candidate.result_id,
            "package_sha256": candidate.package_sha256,
        }
