from services.mlops.gates import (
    AccuracyEvidence,
    DataReadiness,
    DeploymentEvidence,
    ReferenceKind,
    evaluate_deployment_gate,
    evaluate_training_gate,
)


def readiness(**updates: object) -> DataReadiness:
    values = {
        "manifest_sha256": "a" * 64,
        "ledger_sha256": "b" * 64,
        "province_count": 6,
        "complete_year_cells": 36,
        "spatial_coverage_ratio": 0.98,
        "valid_pixel_ratio": 0.90,
        "physical_patches": 1_100,
        "eligible_patches": 1_000,
        "train_patches": 700,
        "validation_patches": 150,
        "test_patches": 150,
        "band_names": ("B02", "B03", "B04", "B08", "B11", "B12"),
        "scl_complete": True,
        "split_group_leakage": False,
        "future_leakage": False,
        "source_files_verified": True,
    }
    values.update(updates)
    return DataReadiness.model_validate(values)


def accuracy(kind: ReferenceKind = ReferenceKind.INDEPENDENT_GROUND_TRUTH) -> AccuracyEvidence:
    return AccuracyEvidence(
        reference_kind=kind,
        reference_source="field-survey-v1",
        reference_version="2026",
        reference_sha256="c" * 64,
        sample_count=200,
        macro_f1=0.82,
        overall_accuracy=0.86,
        spatially_disjoint=True,
        temporally_matched=True,
        label_source_disjoint=True,
        evaluator_report_sha256="d" * 64,
    )


def deployment(reference: AccuracyEvidence | None) -> DeploymentEvidence:
    return DeploymentEvidence(
        model_id="lcluc-v1",
        model_sha256="e" * 64,
        training_report_sha256="f" * 64,
        registry_record_sha256="1" * 64,
        reproducible_environment_sha256="2" * 64,
        security_scan_passed=True,
        rollback_test_passed=True,
        operator_approval_id="approval-2026-001",
        independent_accuracy=reference,
    )


def test_training_gate_accepts_complete_evidence() -> None:
    decision = evaluate_training_gate(readiness())
    assert decision.allowed and decision.status == "READY"


def test_training_gate_blocks_current_low_spatial_coverage_even_with_patch_count() -> None:
    decision = evaluate_training_gate(readiness(spatial_coverage_ratio=0.07711080))
    assert not decision.allowed
    assert "SPATIAL_COVERAGE_INSUFFICIENT" in decision.blockers


def test_training_gate_blocks_missing_scl_wrong_bands_and_leakage() -> None:
    decision = evaluate_training_gate(
        readiness(
            band_names=("B02", "B03", "B04"),
            scl_complete=False,
            split_group_leakage=True,
            future_leakage=True,
        )
    )
    assert {
        "SIX_BAND_CONTRACT_MISMATCH",
        "SCL_INCOMPLETE",
        "SPLIT_GROUP_LEAKAGE",
        "FUTURE_LEAKAGE",
    }.issubset(decision.blockers)


def test_worldcover_weak_reference_never_unlocks_deployment() -> None:
    training = evaluate_training_gate(readiness())
    weak = accuracy(ReferenceKind.WEAK_REFERENCE).model_copy(
        update={"reference_source": "WorldCover-2021"}
    )
    decision = evaluate_deployment_gate(training, deployment(weak))
    assert not decision.allowed
    assert "REFERENCE_IS_NOT_INDEPENDENT_GROUND_TRUTH" in decision.blockers
    assert decision.weak_reference_metrics == {
        "reference_kind": "weak_reference",
        "sample_count": 200,
        "macro_f1": 0.82,
        "overall_accuracy": 0.86,
    }


def test_deployment_requires_independent_metrics_and_operator_approval() -> None:
    training = evaluate_training_gate(readiness())
    blocked = deployment(None).model_copy(update={"operator_approval_id": None})
    decision = evaluate_deployment_gate(training, blocked)
    assert not decision.allowed
    assert "INDEPENDENT_ACCURACY_MISSING" in decision.blockers
    assert "OPERATOR_APPROVAL_MISSING" in decision.blockers


def test_deployment_accepts_only_full_independent_evidence() -> None:
    training = evaluate_training_gate(readiness())
    decision = evaluate_deployment_gate(training, deployment(accuracy()))
    assert decision.allowed and decision.status == "READY"
