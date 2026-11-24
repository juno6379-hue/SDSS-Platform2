"""합성 계약 진단과 기존 feature 계획 연결. 학습/운영 추론·과학 수치 생성은 하지 않는다."""

from __future__ import annotations

import hashlib
import math
from typing import Literal

import numpy as np
from pydantic import Field

from services.mlops.gates import StrictModel, REQUIRED_BANDS
from services.datahub.climate.models import ClimateAsset
from services.geoai.features.climate_join import BoundaryVersion, FeatureJoinRequest, plan_climate_join
from services.rag.routing import canonical_tokens, route_question


def lcluc_synthetic_smoke(image: np.ndarray, scl: np.ndarray,
                          bands: tuple[str, ...], *, fixture_kind: Literal["synthetic"]) -> dict:
    """클래스 대응표가 없으므로 segmentation 대신 유효 마스크/진단 digest만 반환한다."""
    if fixture_kind != "synthetic":
        raise ValueError("SYNTHETIC_FIXTURE_ONLY")
    image, scl = np.asarray(image), np.asarray(scl)
    if bands != REQUIRED_BANDS or image.ndim != 3 or image.shape[0] != 6:
        raise ValueError("SIX_BAND_CHW_REQUIRED")
    if min(image.shape[1:]) < 1 or max(image.shape[1:]) > 256:
        raise ValueError("SMOKE_WINDOW_MUST_BE_1_TO_256")
    if not np.issubdtype(image.dtype, np.floating) or not np.isfinite(image).all():
        raise ValueError("FINITE_FLOAT_IMAGE_REQUIRED")
    if scl.shape != image.shape[1:] or not np.issubdtype(scl.dtype, np.integer):
        raise ValueError("SCL_GRID_INTEGER_REQUIRED")
    if not np.isin(scl, np.arange(12)).all():
        raise ValueError("SCL_CODE_OUT_OF_RANGE")
    mask = np.isin(scl, [4, 5, 6, 7, 11])
    # 구름/그림자/결측 픽셀의 값은 모델 진단에도 포함하지 않는다.
    clean = np.where(mask[None], image, 0).astype("<f4")
    return {"status": "TESTED_SYNTHETIC", "adapter": "six_band_mask_diagnostic_v1",
            "valid_pixels": int(mask.sum()), "total_pixels": int(mask.size),
            "diagnostic_sha256": hashlib.sha256(clean.tobytes() + mask.tobytes()).hexdigest(),
            "segmentation": None, "independent_metrics": None,
            "training_started": False, "production_inference": False}


def climate_feature_plan(asset: ClimateAsset, boundary: BoundaryVersion,
                         request: FeatureJoinRequest) -> dict:
    plan = plan_climate_join(asset, boundary, request)
    # 기존 계약의 as-of/달력/ACL/공간 경고를 유지하고 예측값은 만들지 않는다.
    return {"adapter": "structured_climate_feature_plan_v1", "plan": plan,
            "model_prediction": None, "training_started": False,
            "input_metadata": None if "ACCESS_DENIED" in plan.get("blockers", []) else {
                "observed_or_projected": asset.observed_or_projected,
                "model": asset.model, "scenario": asset.scenario,
                "calendar": asset.time_coverage.calendar, "variable": asset.variable,
                "unit": asset.unit, "grid": asset.grid.model_dump(mode="json")}}


class AuthorizedDocument(StrictModel):
    document_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=20000)
    citation: str = Field(min_length=1, max_length=1000)
    visibility: Literal["public", "restricted"]
    allowed_principals: tuple[str, ...] = ()


def _diagnostic_embedding(tokens: tuple[str, ...]) -> list[float]:
    """학습 임베딩이 아닌 결정적 16차원 hash fixture. 실제 의미 검색 성능을 뜻하지 않는다."""
    values = [0.0] * 16
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        values[digest[0] % 16] += 1 if digest[1] % 2 else -1
    norm = math.sqrt(sum(x*x for x in values)) or 1
    return [x / norm for x in values]


def rag_synthetic_smoke(question: str, documents: list[AuthorizedDocument], principal: str) -> dict:
    if not principal.strip() or len(documents) > 100:
        raise ValueError("PRINCIPAL_AND_BOUNDED_DOCUMENTS_REQUIRED")
    base = {"status": "TESTED_SYNTHETIC", "answer": None, "numeric_answer_allowed": False,
            "embedding_model": "synthetic_hash_fixture_not_pretrained", "production_inference": False}
    route = route_question(question)
    if route.kind == "structured_climate_tool":
        return {**base, "status": "BLOCKED", "blockers": ["STRUCTURED_NUMERIC_TOOL_REQUIRED"],
                "tool_id": "climate.query", "ranked_documents": []}
    # 비인가 본문은 tokenization/embedding/reranking 전에 제외한다.
    allowed = [doc for doc in documents if doc.visibility == "public" or principal in doc.allowed_principals]
    query_tokens = canonical_tokens(question)
    query = set(query_tokens)
    ranked = []
    for doc in allowed:
        tokens = canonical_tokens(doc.text)
        score = len(query & set(tokens)) / max(1, len(query | set(tokens)))
        ranked.append({"document_id": doc.document_id, "diagnostic_similarity": score,
                       "embedding": _diagnostic_embedding(tokens), "citation": doc.citation})
    ranked.sort(key=lambda item: (-item["diagnostic_similarity"], item["document_id"]))
    return {**base, "ranked_documents": ranked, "blockers": ["TRAINED_RERANKER_EMBEDDING_NOT_INSTALLED"]}
