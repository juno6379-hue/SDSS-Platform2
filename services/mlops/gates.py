"""Evidence-based gates for training and deployment.

Weak-reference agreement can support development diagnostics, but it can never
satisfy the independent-accuracy gate used for production deployment.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ReferenceKind(StrEnum):
    INDEPENDENT_GROUND_TRUTH = "independent_ground_truth"
    WEAK_REFERENCE = "weak_reference"
    PSEUDO_LABEL = "pseudo_label"


class MLOpsPolicy(StrictModel):
    required_provinces: int = Field(default=6, ge=1)
    required_year_cells: int = Field(default=36, ge=1)
    min_spatial_coverage: float = Field(default=0.95, gt=0, le=1)
    min_valid_pixel_ratio: float = Field(default=0.80, gt=0, le=1)
    min_patches: int = Field(default=1_000, ge=1)
    min_train_patches: int = Field(default=600, ge=1)
    min_validation_patches: int = Field(default=100, ge=1)
    min_test_patches: int = Field(default=100, ge=1)
    min_independent_samples: int = Field(default=100, ge=1)
    min_macro_f1: float = Field(default=0.70, ge=0, le=1)
    min_overall_accuracy: float = Field(default=0.75, ge=0, le=1)


class DataReadiness(StrictModel):
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    ledger_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    province_count: int = Field(ge=0)
    complete_year_cells: int = Field(ge=0)
    spatial_coverage_ratio: float = Field(ge=0, le=1)
    valid_pixel_ratio: float = Field(ge=0, le=1)
    physical_patches: int = Field(ge=0)
    eligible_patches: int = Field(ge=0)
    train_patches: int = Field(ge=0)
    validation_patches: int = Field(ge=0)
    test_patches: int = Field(ge=0)
    band_names: tuple[str, ...]
    scl_complete: bool
    split_group_leakage: bool
    future_leakage: bool
    source_files_verified: bool


class AccuracyEvidence(StrictModel):
    reference_kind: ReferenceKind
    reference_source: str = Field(min_length=1)
    reference_version: str = Field(min_length=1)
    reference_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    sample_count: int = Field(ge=0)
    macro_f1: float | None = Field(default=None, ge=0, le=1)
    overall_accuracy: float | None = Field(default=None, ge=0, le=1)
    spatially_disjoint: bool
    temporally_matched: bool
    label_source_disjoint: bool
    evaluator_report_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class DeploymentEvidence(StrictModel):
    model_id: str = Field(min_length=1)
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    training_report_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    registry_record_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reproducible_environment_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    security_scan_passed: bool
    rollback_test_passed: bool
    operator_approval_id: str | None = None
    independent_accuracy: AccuracyEvidence | None = None

    @model_validator(mode="after")
    def approval_is_not_blank(self) -> "DeploymentEvidence":
        if self.operator_approval_id is not None and not self.operator_approval_id.strip():
            raise ValueError("operator_approval_id must be non-empty when supplied")
        return self


class GateDecision(StrictModel):
    gate: Literal["training", "deployment"]
    allowed: bool
    status: Literal["READY", "BLOCKED"]
    blockers: tuple[str, ...]
    weak_reference_metrics: dict[str, float | int | str | None] | None = None


REQUIRED_BANDS = ("B02", "B03", "B04", "B08", "B11", "B12")


def evaluate_training_gate(data: DataReadiness, policy: MLOpsPolicy | None = None) -> GateDecision:
    policy = policy or MLOpsPolicy()
    blockers: list[str] = []
    if data.province_count < policy.required_provinces:
        blockers.append("PROVINCE_COVERAGE_INSUFFICIENT")
    if data.complete_year_cells < policy.required_year_cells:
        blockers.append("PROVINCE_YEAR_COMPLETENESS_INSUFFICIENT")
    if data.spatial_coverage_ratio < policy.min_spatial_coverage:
        blockers.append("SPATIAL_COVERAGE_INSUFFICIENT")
    if data.valid_pixel_ratio < policy.min_valid_pixel_ratio:
        blockers.append("VALID_PIXEL_RATIO_INSUFFICIENT")
    if tuple(data.band_names) != REQUIRED_BANDS:
        blockers.append("SIX_BAND_CONTRACT_MISMATCH")
    if not data.scl_complete:
        blockers.append("SCL_INCOMPLETE")
    if not data.source_files_verified:
        blockers.append("SOURCE_FILE_VERIFICATION_MISSING")
    if data.eligible_patches < policy.min_patches:
        blockers.append("ELIGIBLE_PATCH_COUNT_INSUFFICIENT")
    if data.train_patches < policy.min_train_patches:
        blockers.append("TRAIN_PATCH_COUNT_INSUFFICIENT")
    if data.validation_patches < policy.min_validation_patches:
        blockers.append("VALIDATION_PATCH_COUNT_INSUFFICIENT")
    if data.test_patches < policy.min_test_patches:
        blockers.append("TEST_PATCH_COUNT_INSUFFICIENT")
    if data.train_patches + data.validation_patches + data.test_patches != data.eligible_patches:
        blockers.append("SPLIT_TOTAL_MISMATCH")
    if data.eligible_patches > data.physical_patches:
        blockers.append("ELIGIBLE_EXCEEDS_PHYSICAL")
    if data.split_group_leakage:
        blockers.append("SPLIT_GROUP_LEAKAGE")
    if data.future_leakage:
        blockers.append("FUTURE_LEAKAGE")
    return GateDecision(
        gate="training",
        allowed=not blockers,
        status="READY" if not blockers else "BLOCKED",
        blockers=tuple(blockers),
    )


def _independent_accuracy_blockers(
    accuracy: AccuracyEvidence | None, policy: MLOpsPolicy
) -> tuple[str, ...]:
    if accuracy is None:
        return ("INDEPENDENT_ACCURACY_MISSING",)
    blockers: list[str] = []
    if accuracy.reference_kind != ReferenceKind.INDEPENDENT_GROUND_TRUTH:
        blockers.append("REFERENCE_IS_NOT_INDEPENDENT_GROUND_TRUTH")
    if accuracy.sample_count < policy.min_independent_samples:
        blockers.append("INDEPENDENT_SAMPLE_COUNT_INSUFFICIENT")
    if accuracy.macro_f1 is None or accuracy.macro_f1 < policy.min_macro_f1:
        blockers.append("INDEPENDENT_MACRO_F1_INSUFFICIENT")
    if accuracy.overall_accuracy is None or accuracy.overall_accuracy < policy.min_overall_accuracy:
        blockers.append("INDEPENDENT_OVERALL_ACCURACY_INSUFFICIENT")
    if not accuracy.spatially_disjoint:
        blockers.append("INDEPENDENT_SPATIAL_HOLDOUT_MISSING")
    if not accuracy.temporally_matched:
        blockers.append("INDEPENDENT_REFERENCE_TIME_MISMATCH")
    if not accuracy.label_source_disjoint:
        blockers.append("INDEPENDENT_LABEL_SOURCE_LEAKAGE")
    return tuple(blockers)


def evaluate_deployment_gate(
    training: GateDecision,
    deployment: DeploymentEvidence,
    policy: MLOpsPolicy | None = None,
) -> GateDecision:
    policy = policy or MLOpsPolicy()
    blockers: list[str] = []
    if training.gate != "training" or not training.allowed:
        blockers.append("TRAINING_GATE_NOT_READY")
    blockers.extend(_independent_accuracy_blockers(deployment.independent_accuracy, policy))
    if not deployment.security_scan_passed:
        blockers.append("SECURITY_SCAN_NOT_PASSED")
    if not deployment.rollback_test_passed:
        blockers.append("ROLLBACK_TEST_NOT_PASSED")
    if deployment.operator_approval_id is None:
        blockers.append("OPERATOR_APPROVAL_MISSING")
    weak_metrics = None
    accuracy = deployment.independent_accuracy
    if accuracy and accuracy.reference_kind != ReferenceKind.INDEPENDENT_GROUND_TRUTH:
        weak_metrics = {
            "reference_kind": accuracy.reference_kind.value,
            "sample_count": accuracy.sample_count,
            "macro_f1": accuracy.macro_f1,
            "overall_accuracy": accuracy.overall_accuracy,
        }
    return GateDecision(
        gate="deployment",
        allowed=not blockers,
        status="READY" if not blockers else "BLOCKED",
        blockers=tuple(blockers),
        weak_reference_metrics=weak_metrics,
    )
