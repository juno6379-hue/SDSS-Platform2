"""ACL을 먼저 적용하는 결정적 합성 hybrid 검색과 원문 인용 검증."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from math import log, sqrt
from types import MappingProxyType

from .ontology import SourceSpan, verify_span
from .routing import canonical_tokens, route_question


def checked_bbox(value):
    if (
        not isinstance(value, tuple)
        or len(value) != 4
        or any(type(x) not in (int, float) for x in value)
    ):
        raise ValueError("WGS84 bbox 4개 수치 필요")
    w, s, e, n = value
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError("bbox 범위 오류; 날짜변경선 횡단은 별도 분할 필요")


@dataclass(frozen=True)
class Access:
    visibility: str
    allowed_roles: frozenset[str]

    def __post_init__(self):
        if self.visibility not in ("public", "restricted") or not isinstance(
            self.allowed_roles, frozenset
        ):
            raise ValueError("명시적 ACL 필수")
        if any(not isinstance(role, str) or not role.strip() for role in self.allowed_roles):
            raise ValueError("ACL 역할 형식 오류")
        if self.visibility == "restricted" and not self.allowed_roles:
            raise ValueError("restricted ACL에 허용 역할 필요")

    def permits(self, roles):
        return self.visibility == "public" or bool(self.allowed_roles.intersection(roles))


@dataclass(frozen=True)
class ChunkMetadata:
    source_span: SourceSpan
    authority: str
    language: str
    access: Access
    license: str
    retrieval_permitted: bool
    valid_from: date
    valid_until: date | None
    spatial_coverage: tuple[float, float, float, float]
    time_coverage: tuple[int, int]
    variable: str
    scenario: str
    model: str
    observed_or_projected: str
    unit: str
    calendar: str
    grid: str
    claim_authority: str
    dataset_id: str
    dataset_version: str
    acquired_at: str
    trace_id: str

    def __post_init__(self):
        if self.language not in ("ko", "id", "en") or not isinstance(self.access, Access):
            raise ValueError("ko/id/en 및 ACL 필수")
        if self.authority != self.source_span.authority:
            raise ValueError("chunk authority와 출처 불일치")
        for field in (
            "license",
            "variable",
            "scenario",
            "model",
            "unit",
            "calendar",
            "grid",
            "dataset_id",
            "dataset_version",
            "acquired_at",
            "trace_id",
        ):
            if not isinstance(getattr(self, field), str) or not getattr(self, field).strip():
                raise ValueError(field + " 누락; 해당 없음은 명시적 not_applicable 사용")
        if type(self.retrieval_permitted) is not bool:
            raise ValueError("라이선스에 따른 검색 허용을 명시해야 함")
        acquired = datetime.fromisoformat(self.acquired_at.replace("Z", "+00:00"))
        if acquired.tzinfo is None:
            raise ValueError("취득 시각에 timezone 필수")
        if self.observed_or_projected not in ("observed", "projected", "not_applicable"):
            raise ValueError("관측/전망 구분 누락")
        if self.claim_authority not in (
            "descriptive_only",
            "methodology_reference",
            "policy_reference",
        ):
            raise ValueError("허용되지 않은 claim authority; 독립 과학 정확도 자동 주장 금지")
        if type(self.valid_from) is not date or (
            self.valid_until is not None
            and (type(self.valid_until) is not date or self.valid_until < self.valid_from)
        ):
            raise ValueError("문서 유효기간 오류")
        checked_bbox(self.spatial_coverage)
        if (
            not isinstance(self.time_coverage, tuple)
            or len(self.time_coverage) != 2
            or any(type(v) is not int for v in self.time_coverage)
            or self.time_coverage[0] > self.time_coverage[1]
        ):
            raise ValueError("시간 범위 오류")


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: ChunkMetadata


@dataclass(frozen=True)
class SearchQuery:
    text: str
    as_of: date
    roles: frozenset[str] = frozenset()
    bbox: tuple[float, float, float, float] | None = None
    years: tuple[int, int] | None = None
    variable: str | None = None
    scenario: str | None = None
    model: str | None = None
    observed_or_projected: str | None = None
    calendar: str | None = None
    language: str | None = None

    def __post_init__(self):
        if not isinstance(self.roles, frozenset) or any(not isinstance(v, str) for v in self.roles):
            raise ValueError("검증된 principal 역할 집합 필요")
        if type(self.as_of) is not date:
            raise ValueError("결정적 유효시점 필수")
        if self.bbox is not None:
            checked_bbox(self.bbox)
        if self.years is not None and (
            len(self.years) != 2
            or any(type(v) is not int for v in self.years)
            or self.years[0] > self.years[1]
        ):
            raise ValueError("질의 시간 범위 오류")


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    bm25: float
    vector: float
    metadata_score: float
    method: str = "TESTED_SYNTHETIC_BM25_HASH_VECTOR"


def synthetic_vector(tokens, dimensions=64):
    """진짜 다국어 embedding이 아닌 재현 가능한 feature hashing 시험 벡터다."""
    values = [0.0] * dimensions
    for token in tokens:
        digest = sha256(token.encode("utf-8")).digest()
        values[int.from_bytes(digest[:4], "big") % dimensions] += 1 if digest[4] % 2 else -1
    norm = sqrt(sum(v * v for v in values))
    return tuple(v / norm if norm else 0.0 for v in values)


def metadata_similarity(metadata, query, tokens):
    components = [float(bool(set(tokens).intersection(canonical_tokens(metadata.variable))))]
    for field in ("scenario", "model", "observed_or_projected", "calendar", "language", "variable"):
        if getattr(query, field) is not None:
            components.append(1.0)  # 앞의 hard filter를 통과한 명시적 조건이다.
    if query.bbox is not None:
        a, b = query.bbox, metadata.spatial_coverage
        intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
            0, min(a[3], b[3]) - max(a[1], b[1])
        )
        union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
        # 도 단위 bbox IoU는 순위용일 뿐 과학적 면적이나 실제 관측 피복률이 아니다.
        components.append(intersection / union if union else 0.0)
    if query.years is not None:
        a, b = query.years, metadata.time_coverage
        intersection = max(0, min(a[1], b[1]) - max(a[0], b[0]) + 1)
        union = max(a[1], b[1]) - min(a[0], b[0]) + 1
        components.append(intersection / union)
    return sum(components) / len(components)


class HybridIndex:
    def __init__(self, documents, chunks):
        documents, chunks = tuple(documents), tuple(chunks)
        self.documents = MappingProxyType({d.id: d for d in documents})
        if len(self.documents) != len(documents) or len({c.id for c in chunks}) != len(chunks):
            raise ValueError("문서/chunk ID 중복")
        for chunk in chunks:
            if not chunk.id or not chunk.text or not isinstance(chunk.metadata, ChunkMetadata):
                raise ValueError("chunk 계약 오류")
            document = self.documents.get(chunk.metadata.source_span.document_id)
            if document is None:
                raise ValueError("원본 문서 없음")
            verify_span(chunk.metadata.source_span, document)
            if chunk.text != chunk.metadata.source_span.quote:
                raise ValueError("chunk는 원본 문자 범위와 정확히 일치해야 함")
        self.chunks = MappingProxyType({c.id: c for c in chunks})

    def eligible(self, chunk, query):
        m = chunk.metadata
        acquired_day = (
            datetime.fromisoformat(m.acquired_at.replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .date()
        )
        if acquired_day > query.as_of:
            return False
        if (
            not m.access.permits(query.roles)
            or not m.retrieval_permitted
            or not m.valid_from <= query.as_of
            or (m.valid_until is not None and query.as_of > m.valid_until)
        ):
            return False
        for field in ("scenario", "model", "observed_or_projected", "calendar", "language"):
            if getattr(query, field) is not None and getattr(query, field) != getattr(m, field):
                return False
        if query.variable is not None and canonical_tokens(query.variable) != canonical_tokens(
            m.variable
        ):
            return False
        if query.years is not None and (
            m.time_coverage[1] < query.years[0] or query.years[1] < m.time_coverage[0]
        ):
            return False
        if query.bbox is not None:
            a, b = query.bbox, m.spatial_coverage
            if a[0] >= b[2] or b[0] >= a[2] or a[1] >= b[3] or b[1] >= a[3]:
                return False
        return True

    def search(self, query, limit=5):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("limit은 1~50")
        if route_question(query.text).kind != "descriptive_rag":
            raise ValueError("NUMERIC_TOOL_REQUIRED: 수치 질의는 RAG 검색 금지")
        # ACL/라이선스/유효기간을 순위 계산보다 먼저 적용해 비공개 문서 통계도 노출하지 않는다.
        pool = sorted(
            (c for c in self.chunks.values() if self.eligible(c, query)), key=lambda c: c.id
        )
        if not pool:
            return ()
        query_tokens = canonical_tokens(query.text)
        vector = synthetic_vector(query_tokens)
        docs = [Counter(canonical_tokens(c.text)) for c in pool]
        average_length = sum(sum(d.values()) for d in docs) / len(docs)
        scores = []
        for chunk, tokens in zip(pool, docs, strict=True):
            bm25 = 0.0
            for term in set(query_tokens):
                frequency = tokens[term]
                df = sum(term in doc for doc in docs)
                idf = log(1 + (len(docs) - df + 0.5) / (df + 0.5))
                denominator = frequency + 1.2 * (
                    0.25 + 0.75 * sum(tokens.values()) / (average_length or 1)
                )
                bm25 += idf * frequency * 2.2 / denominator
            cosine = max(
                0.0,
                sum(
                    a * b
                    for a, b in zip(
                        vector,
                        synthetic_vector(canonical_tokens(chunk.text)),
                        strict=True,
                    )
                ),
            )
            meta = metadata_similarity(chunk.metadata, query, query_tokens)
            scores.append((chunk, bm25, cosine, meta))
        maximum = max((v[1] for v in scores), default=1) or 1
        hits = [
            Hit(c, round(0.45 * b / maximum + 0.35 * v + 0.20 * m, 12), b, v, m)
            for c, b, v, m in scores
            if b > 0 or v > 0 or m > 0
        ]
        return tuple(sorted(hits, key=lambda hit: (-hit.score, hit.chunk.id))[:limit])

    def verify_citation(self, chunk_id, quote, query, claim_kind="descriptive"):
        chunk = self.chunks.get(chunk_id)
        if chunk is None or not self.eligible(chunk, query):
            raise ValueError("인용 불가")
        if route_question(query.text).kind != "descriptive_rag" or claim_kind == "numeric":
            raise ValueError("정량 기후 사실은 structured tool만 인용 가능")
        allowed = {
            "descriptive_only": {"descriptive"},
            "methodology_reference": {"descriptive", "methodology"},
            "policy_reference": {"descriptive", "policy_context"},
        }
        if claim_kind not in allowed[chunk.metadata.claim_authority] or quote != chunk.text:
            raise ValueError("claim authority 또는 원문 범위 불일치")
        document = self.documents[chunk.metadata.source_span.document_id]
        verify_span(chunk.metadata.source_span, document)
        return {
            "chunk_id": chunk.id,
            "document_id": document.id,
            "source_id": document.source_id,
            "version": document.version,
            "sha256": document.sha256,
            "source_uri": document.source_uri,
            "source_span": [chunk.metadata.source_span.start, chunk.metadata.source_span.end],
            "authority": chunk.metadata.authority,
            "claim_authority": chunk.metadata.claim_authority,
            "license": chunk.metadata.license,
            "quote": quote,
            "language": chunk.metadata.language,
            "dataset_id": chunk.metadata.dataset_id,
            "dataset_version": chunk.metadata.dataset_version,
            "spatial_coverage": chunk.metadata.spatial_coverage,
            "time_coverage": chunk.metadata.time_coverage,
            "variable": chunk.metadata.variable,
            "scenario": chunk.metadata.scenario,
            "model": chunk.metadata.model,
            "unit": chunk.metadata.unit,
            "calendar": chunk.metadata.calendar,
            "grid": chunk.metadata.grid,
            "observed_or_projected": chunk.metadata.observed_or_projected,
            "acquired_at": chunk.metadata.acquired_at,
            "trace_id": chunk.metadata.trace_id,
        }

    def respond(self, query, context=None):
        decision = route_question(query.text, context)
        if decision.kind == "structured_climate_tool":
            return {
                "status": decision.status,
                "route": decision,
                "citations": (),
                "answer": None,
                "reason": "구조화 도구 실행 adapter 미연결; RAG로 수치 응답하지 않음",
            }
        citations = tuple(
            self.verify_citation(hit.chunk.id, hit.chunk.text, query) for hit in self.search(query)
        )
        return {
            "status": "CITED_EXCERPTS_ONLY" if citations else "BLOCKED_NO_AUTHORIZED_EVIDENCE",
            "route": decision,
            "citations": citations,
            "answer": None,
        }
