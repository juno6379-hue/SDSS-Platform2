"""출처 버전·문자 범위로 추적하는 작은 검증형 온톨로지."""

from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType

NODE_TYPES = frozenset(
    "Institution Source Collection Dataset DatasetVersion Variable Scenario ClimateModel TimePeriod Geography SpatialUnit Document Chunk FeatureSet Result Policy".split()
)
RELATIONS = MappingProxyType(
    {
        key: (frozenset(domain), frozenset(target))
        for key, (domain, target) in {
            "PUBLISHED_BY": (
                {"Source", "Collection", "Dataset", "Document", "Policy"},
                {"Institution"},
            ),
            "HAS_VERSION": ({"Dataset"}, {"DatasetVersion"}),
            "CONTAINS_VARIABLE": (
                {"Collection", "DatasetVersion", "FeatureSet", "Result"},
                {"Variable"},
            ),
            "USES_SCENARIO": ({"DatasetVersion", "FeatureSet", "Result"}, {"Scenario"}),
            "PRODUCED_BY_MODEL": ({"DatasetVersion", "FeatureSet", "Result"}, {"ClimateModel"}),
            "COVERS_TIME": (
                {"Collection", "DatasetVersion", "Document", "Policy", "FeatureSet", "Result"},
                {"TimePeriod"},
            ),
            "COVERS_GEOGRAPHY": (
                {"Collection", "DatasetVersion", "Document", "Policy", "FeatureSet", "Result"},
                {"Geography", "SpatialUnit"},
            ),
            "DERIVED_FROM": (
                {"DatasetVersion", "FeatureSet", "Result"},
                {"Source", "DatasetVersion", "FeatureSet"},
            ),
            "CITES": (
                {"Document", "Chunk", "Result", "Policy"},
                {"Document", "Chunk", "Source", "DatasetVersion"},
            ),
            "GOVERNS": (
                {"Policy"},
                {"Dataset", "DatasetVersion", "FeatureSet", "Result", "SpatialUnit"},
            ),
            "SUPERSEDES": (
                {"DatasetVersion", "Document", "Policy"},
                {"DatasetVersion", "Document", "Policy"},
            ),
        }.items()
    }
)


@dataclass(frozen=True)
class SourceDocument:
    id: str
    source_id: str
    version: str
    authority: str
    source_uri: str
    text: str
    sha256: str

    def __post_init__(self):
        if not all(
            isinstance(v, str) and v.strip()
            for v in (
                self.id,
                self.source_id,
                self.version,
                self.authority,
                self.source_uri,
                self.text,
            )
        ):
            raise ValueError("출처 식별자·버전·authority·URI·본문 필수")
        if not self.source_uri.startswith(("https://", "urn:synthetic:")):
            raise ValueError("공식 HTTPS 또는 명시적인 합성 URN만 허용")
        if sha256(self.text.encode("utf-8")).hexdigest() != self.sha256:
            raise ValueError("문서 본문 SHA 불일치")


@dataclass(frozen=True)
class SourceSpan:
    document_id: str
    source_id: str
    version: str
    document_sha256: str
    authority: str
    start: int
    end: int
    quote: str


def verify_span(span: SourceSpan, document: SourceDocument):
    if (span.document_id, span.source_id, span.version, span.document_sha256, span.authority) != (
        document.id,
        document.source_id,
        document.version,
        document.sha256,
        document.authority,
    ):
        raise ValueError("출처·버전·authority 결속 불일치")
    # offset은 UTF-8 byte가 아닌 Python Unicode 문자 인덱스이며 끝 위치는 제외한다.
    if (
        type(span.start) is not int
        or type(span.end) is not int
        or not 0 <= span.start < span.end <= len(document.text)
    ):
        raise ValueError("출처 문자 범위 오류")
    if document.text[span.start : span.end] != span.quote:
        raise ValueError("원문 인용 불일치")


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    evidence: SourceSpan
    entity_version: str | None = None


@dataclass(frozen=True)
class Edge:
    source: str
    relation: str
    target: str
    evidence: SourceSpan


class KnowledgeGraph:
    """증명 범위는 typed 관계와 확인된 출처 span이다. 의미적 진실·기관 승인을 자동 인증하지 않는다."""

    def __init__(self, documents):
        documents = tuple(documents)
        self.documents = MappingProxyType({d.id: d for d in documents})
        if len(self.documents) != len(documents):
            raise ValueError("중복 문서 ID")
        self._nodes = {}
        self._edges = []

    @property
    def nodes(self):
        return MappingProxyType(self._nodes)

    @property
    def edges(self):
        return tuple(self._edges)

    def _verify(self, evidence):
        document = self.documents.get(evidence.document_id)
        if document is None:
            raise ValueError("미등록 출처 문서")
        verify_span(evidence, document)

    def add_node(self, node):
        if not node.id or node.kind not in NODE_TYPES or node.id in self._nodes:
            raise ValueError("잘못된 타입 또는 중복 노드")
        self._verify(node.evidence)
        if node.kind == "DatasetVersion" and (
            not isinstance(node.entity_version, str) or not node.entity_version.strip()
        ):
            raise ValueError("DatasetVersion의 실제 entity_version 필요; 출처 문서 버전과 구분")
        self._nodes[node.id] = node

    def add_edge(self, edge):
        self._verify(edge.evidence)
        if (
            edge.relation not in RELATIONS
            or edge.source not in self._nodes
            or edge.target not in self._nodes
        ):
            raise ValueError("관계 또는 노드 미등록")
        left, right = self._nodes[edge.source], self._nodes[edge.target]
        domains, ranges = RELATIONS[edge.relation]
        if left.kind not in domains or right.kind not in ranges or left.id == right.id:
            raise ValueError("관계 domain/range 오류")
        if edge.relation == "SUPERSEDES" and (
            left.kind != right.kind
            or not left.entity_version
            or not right.entity_version
            or left.entity_version == right.entity_version
        ):
            raise ValueError(
                "SUPERSEDES는 같은 타입의 서로 다른 entity_version 필요; 문서 버전을 대신 쓰지 않음"
            )
        if edge in self._edges:
            raise ValueError("중복 관계")
        # 관계가 인용하는 원본과 양 끝 노드가 동일 authority에 의해 뒷받침되는지 확인한다.
        if any(n.evidence.authority != edge.evidence.authority for n in (left, right)):
            raise ValueError("관계 authority 교차 결속 없음")
        self._edges.append(edge)
