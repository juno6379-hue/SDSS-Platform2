"""Pydantic v2 모델 카탈로그: 알 수 없는 해시/클래스 대응은 null로 보존한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from services.mlops.gates import StrictModel, REQUIRED_BANDS


def canonical_sha(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ArtifactRef(StrictModel):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def verify_artifact(ref: ArtifactRef, allowed_root: Path) -> dict:
    # 등록 메타데이터만으로 파일 실재/무결성을 주장하지 않는다. 경로 이탈도 차단한다.
    root = allowed_root.resolve()
    path = Path(ref.path)
    target = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not target.is_relative_to(root):
        return {"verified": False, "blocker": "ARTIFACT_OUTSIDE_ALLOWED_ROOT"}
    if not target.is_file():
        return {"verified": False, "blocker": "ARTIFACT_MISSING"}
    actual = file_sha(target)
    return {"verified": actual == ref.sha256, "actual_sha256": actual,
            "blocker": None if actual == ref.sha256 else "ARTIFACT_SHA_MISMATCH"}


class InputSignature(StrictModel):
    task: Literal["lcluc_segmentation", "structured_climate_features", "rag_embedding_reranker"]
    band_names: tuple[str, ...] = ()
    tensor_layout: Literal["CHW", "structured", "authorized_text"]
    required_fields: tuple[str, ...]
    normalization: str
    scl_required: bool = False
    class_mapping_23_to_internal: dict[str, int] | None = None
    climate_resolution_policy: str | None = None
    numeric_answer_allowed: Literal[False] = False

    @model_validator(mode="after")
    def task_contract(self):
        mandatory = {
            "lcluc_segmentation": {"image", "scl", "normalization_evidence", "source_sha256"},
            "structured_climate_features": {"asset", "boundary", "as_of", "observed_or_projected",
                "model", "scenario", "calendar", "unit", "grid", "feature_window"},
            "rag_embedding_reranker": {"principal", "authorized_documents", "question", "citations"},
        }
        if not mandatory[self.task].issubset(self.required_fields):
            raise ValueError("TASK_REQUIRED_FIELDS_MISSING")
        normalization = {"lcluc_segmentation": "per_product_verified_scale_offset",
                         "structured_climate_features": "explicit_unit_conversion_only",
                         "rag_embedding_reranker": "acl_before_tokenization_embedding_reranking"}
        if self.normalization != normalization[self.task]:
            raise ValueError("TASK_NORMALIZATION_CONTRACT_MISMATCH")
        if self.task == "lcluc_segmentation":
            if self.band_names != REQUIRED_BANDS or self.tensor_layout != "CHW" or not self.scl_required:
                raise ValueError("LCLUC_SIX_BANDS_SCL_SIGNATURE_REQUIRED")
            # v1에 권위 있는 23종 대응표가 없다. 임의 대응표를 검증된 것으로 등록하지 않는다.
            if self.class_mapping_23_to_internal is not None:
                raise ValueError("CLASS_MAPPING_NOT_VALIDATED_IN_V1")
        elif self.band_names or self.scl_required or self.class_mapping_23_to_internal is not None:
            raise ValueError("NON_LCLUC_RASTER_SIGNATURE_FORBIDDEN")
        if self.task == "structured_climate_features" and self.tensor_layout != "structured":
            raise ValueError("CLIMATE_STRUCTURED_INPUT_REQUIRED")
        if self.task == "rag_embedding_reranker" and self.tensor_layout != "authorized_text":
            raise ValueError("RAG_AUTHORIZED_TEXT_REQUIRED")
        return self

    @property
    def sha256(self) -> str:
        return canonical_sha(self.model_dump(mode="json"))


class ModelManifest(StrictModel):
    schema_version: Literal["specialized-model/1.0"] = "specialized-model/1.0"
    model_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,79}$")
    version: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,40}$")
    lifecycle: Literal["Draft"] = "Draft"
    implementation_status: Literal["IMPLEMENTED_UNVERIFIED", "BLOCKED"] = "BLOCKED"
    signature: InputSignature
    signature_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    checkpoint: ArtifactRef | None = None
    training_report: ArtifactRef | None = None
    reproducible_environment: ArtifactRef | None = None
    metric_kind: Literal["unavailable", "weak_reference_agreement", "synthetic_diagnostic"] = "unavailable"
    independent_metrics: None = None

    @model_validator(mode="after")
    def signature_integrity(self):
        if self.signature_sha256 != self.signature.sha256:
            raise ValueError("INPUT_SIGNATURE_SHA_MISMATCH")
        return self


def default_catalog() -> tuple[ModelManifest, ...]:
    signatures = [
        InputSignature(task="lcluc_segmentation", band_names=REQUIRED_BANDS,
                       tensor_layout="CHW", scl_required=True,
                       required_fields=("image", "scl", "normalization_evidence", "source_sha256"),
                       normalization="per_product_verified_scale_offset"),
        InputSignature(task="structured_climate_features", tensor_layout="structured",
                       required_fields=("asset", "boundary", "as_of", "observed_or_projected", "model",
                                        "scenario", "calendar", "unit", "grid", "feature_window"),
                       normalization="explicit_unit_conversion_only",
                       climate_resolution_policy="native_grid_preserved_no_10m_observation_claim"),
        InputSignature(task="rag_embedding_reranker", tensor_layout="authorized_text",
                       required_fields=("principal", "authorized_documents", "question", "citations"),
                       normalization="acl_before_tokenization_embedding_reranking"),
    ]
    return tuple(ModelManifest(model_id=s.task, version="v1", signature=s,
                               signature_sha256=s.sha256) for s in signatures)


def register_manifest(manifest: ModelManifest, directory: Path) -> Path:
    """동일 ID/version 덮어쓰기를 거부한다. 등록은 운영 승인과 별개다."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{manifest.model_id}--{manifest.version}.json"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(manifest.model_dump_json(indent=2))
    return path
