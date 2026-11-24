"""공통 MLOps Gate 재사용. 유형별 미구현 정책이나 누락 증거는 허용으로 바꾸지 않는다."""

from pathlib import Path

from services.mlops.gates import (DataReadiness, DeploymentEvidence, evaluate_training_gate,
                                  evaluate_deployment_gate, GateDecision)
from .catalog import ModelManifest, verify_artifact, canonical_sha


def axis(blockers: list[str]) -> dict:
    return {"status": "BLOCKED" if blockers else "READY", "allowed": not blockers,
            "blockers": sorted(set(blockers))}


def model_readiness(manifest: ModelManifest, artifact_root: Path,
                    data: DataReadiness | None = None,
                    deployment: DeploymentEvidence | None = None) -> dict:
    task = manifest.signature.task
    training = []
    common_training = None
    if task == "lcluc_segmentation":
        if data is None:
            training.append("DATA_READINESS_EVIDENCE_MISSING")
        else:
            common_training = evaluate_training_gate(data)
            training.extend(common_training.blockers)
        training += ["CLASS_MAPPING_23_NOT_VALIDATED", "CLASS_BALANCE_EVIDENCE_MISSING"]
    else:
        training.append("TYPE_SPECIFIC_TRAINING_POLICY_NOT_IMPLEMENTED")
    artifacts = []
    for field in ("checkpoint", "training_report", "reproducible_environment"):
        ref = getattr(manifest, field)
        if ref is None:
            artifacts.append(f"{field.upper()}_MISSING")
        else:
            result = verify_artifact(ref, artifact_root)
            if not result["verified"]:
                artifacts.append(f"{field.upper()}_{result['blocker']}")
    inference = list(artifacts) + ["PRODUCTION_EXECUTOR_NOT_IMPLEMENTED"]
    if task == "lcluc_segmentation":
        inference.append("CLASS_MAPPING_23_NOT_VALIDATED")
    deploy = list(training) + list(artifacts)
    if task != "lcluc_segmentation":
        deploy.append("TYPE_SPECIFIC_DEPLOYMENT_POLICY_NOT_IMPLEMENTED")
    elif deployment is None:
        deploy.append("DEPLOYMENT_EVIDENCE_MISSING")
        deploy.append("INDEPENDENT_ACCURACY_MISSING")
    else:
        # 결합한 Gate를 전달하여 추가 차단도 공통 배포 Gate에서 우회할 수 없게 한다.
        gate = GateDecision(gate="training", allowed=not training,
                            status="BLOCKED" if training else "READY", blockers=tuple(training))
        deploy.extend(evaluate_deployment_gate(gate, deployment).blockers)
        if deployment.model_id != manifest.model_id:
            deploy.append("DEPLOYMENT_MODEL_ID_MISMATCH")
        if deployment.registry_record_sha256 != canonical_sha(manifest.model_dump(mode="json")):
            deploy.append("DEPLOYMENT_REGISTRY_RECORD_SHA_MISMATCH")
        for field, expected in (("model_sha256", manifest.checkpoint),
                                ("training_report_sha256", manifest.training_report),
                                ("reproducible_environment_sha256", manifest.reproducible_environment)):
            if expected is None or getattr(deployment, field) != expected.sha256:
                deploy.append(f"DEPLOYMENT_{field.upper()}_MISMATCH")
    deploy.append("PRODUCTION_EXECUTOR_NOT_IMPLEMENTED")
    return {"model_id": manifest.model_id, "version": manifest.version,
            "input_signature_sha256": manifest.signature_sha256, "lifecycle": "Draft",
            "evidence_state": "BLOCKED", "runtime_contract": "IMPLEMENTED_UNVERIFIED",
            "axes": {"training": axis(training), "inference": axis(inference),
                     "deployment": axis(deploy)}, "independent_metrics": None,
            "scientific_execution_started": False}
