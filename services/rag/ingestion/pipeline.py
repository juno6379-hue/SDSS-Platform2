"""원문 span과 메타데이터를 검증한 뒤에만 플러그인 인덱스에 게시한다."""

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from html.parser import HTMLParser
from math import isfinite
from pathlib import Path
from typing import Protocol

from services.rag.ontology import Edge, KnowledgeGraph, Node, SourceDocument, SourceSpan
from services.rag.retrieval import Chunk, ChunkMetadata, HybridIndex, synthetic_vector
from services.rag.routing import canonical_tokens


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in ("p", "div", "tr", "h1", "h2", "h3", "br"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


@dataclass(frozen=True)
class StagedDocument:
    document: SourceDocument
    receipt: dict
    spans: tuple[SourceSpan, ...]
    extraction: dict


def staged_graph(staged):
    """실제 원문에서 Document/Chunk/CITES만 만든다. 기관 승인이나 기후 사실 관계를 생성하지 않는다."""
    graph = KnowledgeGraph([staged.document])
    graph.add_node(Node(staged.document.id, "Document", staged.spans[0]))
    for span in staged.spans:
        identifier = (
            "chunk-"
            + sha256(
                (staged.document.id + ":" + str(span.start) + ":" + str(span.end)).encode()
            ).hexdigest()
        )
        graph.add_node(Node(identifier, "Chunk", span))
        graph.add_edge(Edge(identifier, "CITES", staged.document.id, span))
    return graph


def preserve_graph(staged, directory):
    graph = staged_graph(staged)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    payload = dict(
        status="BLOCKED_PENDING_CURATED_METADATA",
        institution_authority_certified=False,
        raw_sha256=staged.receipt["sha256"],
        text_sha256=staged.document.sha256,
        nodes=[asdict(node) for node in graph.nodes.values()],
        edges=[asdict(edge) for edge in graph.edges],
    )
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode()
    target = directory / (staged.document.id + ".kg.json")
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError("IMMUTABLE_KG_CONFLICT")
    else:
        with target.open("xb") as stream:
            stream.write(raw)
    return str(target)


def stage_document(receipt, *, authority, raw_root, format="text", chunk_size=1000):
    if type(chunk_size) is not int or not 50 <= chunk_size <= 4000:
        raise ValueError("chunk size 50~4000")
    path = Path(receipt["raw_path"]).resolve()
    if not path.is_relative_to(Path(raw_root).resolve()) or path.suffix != ".raw":
        raise ValueError("RAW_PATH_OUTSIDE_STORE")
    if (
        type(receipt["byte_count"]) is not int
        or not 0 < receipt["byte_count"] <= 512 * 1024
        or path.stat().st_size != receipt["byte_count"]
    ):
        raise ValueError("RAW_SIZE_CONTRACT_MISMATCH")
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != receipt["sha256"] or len(raw) != receipt["byte_count"]:
        raise ValueError("RAW_RECEIPT_HASH_MISMATCH")
    text = raw.decode("utf-8-sig", errors="strict")
    if format == "html":
        parser = TextExtractor()
        parser.feed(text)
        text = "".join(parser.parts)
    elif format not in ("text", "markdown", "json"):
        raise ValueError("지원하지 않는 문서 형식")
    # HTML은 추출 text의 문자 offset이며 raw HTML byte offset이라고 주장하지 않는다.
    text_hash = sha256(text.encode()).hexdigest()
    doc = SourceDocument(
        "doc-" + text_hash,
        receipt["source_id"],
        receipt["version"],
        authority,
        receipt["source_uri"],
        text,
        text_hash,
    )
    spans = tuple(
        SourceSpan(
            doc.id,
            doc.source_id,
            doc.version,
            doc.sha256,
            authority,
            start,
            min(len(text), start + chunk_size),
            text[start : start + chunk_size],
        )
        for start in range(0, len(text), chunk_size)
    )
    return StagedDocument(
        doc,
        dict(receipt),
        spans,
        dict(
            raw_sha256=receipt["sha256"],
            text_sha256=text_hash,
            parser_version="bounded-text/1",
            format=format,
            offset_unit="unicode_character",
            source_authority_status=receipt["authority_status"],
            publication_status="BLOCKED_PENDING_CURATED_METADATA",
        ),
    )


class Encoder(Protocol):
    name: str
    requires_network: bool

    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...


class VectorSink(Protocol):
    def upsert_atomic(self, records: tuple[dict, ...]): ...


class SyntheticHashEncoder:
    name = "synthetic-sha256-feature-hash-64"
    requires_network = False

    def encode(self, texts):
        return tuple(synthetic_vector(canonical_tokens(text)) for text in texts)


class MemoryVectorSink:
    """합성 시험용 atomic batch 저장소. 운영 DB·검색 서비스가 아니다."""

    def __init__(self):
        self.records = {}

    def upsert_atomic(self, records):
        candidate = dict(self.records)
        for record in records:
            if record["chunk_id"] in candidate and candidate[record["chunk_id"]] != record:
                raise ValueError("IMMUTABLE_INDEX_CONFLICT")
            candidate[record["chunk_id"]] = record
        self.records = candidate


@dataclass(frozen=True)
class CurationReview:
    raw_sha256: str
    reviewer: str
    license: str
    license_evidence_uri: str
    access_reviewed: bool
    validity_reviewed: bool

    def validate(self, staged):
        if self.raw_sha256 != staged.receipt["sha256"] or not self.reviewer.strip():
            raise ValueError("CURATION_RECEIPT_OR_REVIEWER_MISMATCH")
        if self.license in (
            "NOT_VERIFIED",
            "UNKNOWN",
            "",
        ) or not self.license_evidence_uri.startswith(("https://", "urn:synthetic:")):
            raise ValueError("LICENSE_EVIDENCE_REQUIRED")
        if self.access_reviewed is not True or self.validity_reviewed is not True:
            raise ValueError("ACCESS_VALIDITY_REVIEW_REQUIRED")


def ingest_curated(staged, metadata_factory, encoder, sink, review):
    """승인된 metadata factory만 게시한다. 미확인 license/validity/authority는 이 단계로 넘기지 않는다."""
    if encoder.requires_network:
        raise ValueError("EXTERNAL_EMBEDDING_DISABLED")
    if not isinstance(review, CurationReview):
        raise ValueError("CURATION_REVIEW_REQUIRED")
    review.validate(staged)
    chunks = []
    for span in staged.spans:
        metadata = metadata_factory(span)
        if not isinstance(metadata, ChunkMetadata) or metadata.source_span != span:
            raise ValueError("CURATED_SPAN_METADATA_MISMATCH")
        if not metadata.retrieval_permitted or metadata.license != review.license:
            raise ValueError("LICENSE_REVIEW_REQUIRED")
        if metadata.acquired_at != staged.receipt["acquired_at"]:
            raise ValueError("ACQUISITION_LINEAGE_MISMATCH")
        chunks.append(
            Chunk(
                "chunk-"
                + sha256(
                    (staged.document.id + ":" + str(span.start) + ":" + str(span.end)).encode()
                ).hexdigest(),
                span.quote,
                metadata,
            )
        )
    index = HybridIndex([staged.document], chunks)
    vectors = encoder.encode(tuple(chunk.text for chunk in chunks))
    if len(vectors) != len(chunks) or not vectors:
        raise ValueError("EMBEDDING_CARDINALITY_MISMATCH")
    dimension = len(vectors[0])
    if (
        not dimension
        or dimension > 4096
        or any(
            len(v) != dimension or any(type(x) not in (int, float) or not isfinite(x) for x in v)
            for v in vectors
        )
    ):
        raise ValueError("INVALID_EMBEDDING_VECTOR")
    graph = staged_graph(staged)
    records = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        records.append(
            dict(
                chunk_id=chunk.id,
                document_id=staged.document.id,
                text_sha256=staged.document.sha256,
                raw_sha256=staged.receipt["sha256"],
                source_span=[chunk.metadata.source_span.start, chunk.metadata.source_span.end],
                vector=tuple(vector),
                metadata=asdict(chunk.metadata),
                encoder=encoder.name,
            )
        )
    # 모든 검증이 끝난 뒤 단 한 번 atomic sink를 호출한다. 플러그인은 이 계약을 보장해야 한다.
    sink.upsert_atomic(tuple(records))
    return {
        "status": "TESTED_SYNTHETIC"
        if encoder.name == SyntheticHashEncoder.name
        else "IMPLEMENTED_UNVERIFIED",
        "chunk_count": len(chunks),
        "dimension": dimension,
        "embedding_quality_verified": False,
        "institution_authority_certified": False,
        "graph": graph,
        "index": index,
    }


def preserve_stage(staged, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    payload = dict(
        document=asdict(staged.document),
        receipt=staged.receipt,
        spans=[asdict(s) for s in staged.spans],
        extraction=staged.extraction,
        status="BLOCKED_PENDING_CURATED_METADATA",
        embedding_quality_verified=False,
        institution_authority_certified=False,
    )
    target = directory / (staged.document.id + ".stage.json")
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode()
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError("IMMUTABLE_STAGE_CONFLICT")
    else:
        with target.open("xb") as stream:
            stream.write(raw)
    return str(target)
