"""TESTED_SYNTHETIC: 네트워크 없이 receipt·원문·게시 gate를 검증한다."""

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from services.datahub.connectors.klhk.source import (
    DICTIONARY,
    KLHK_CODES,
    Blocked,
    BoundedTransport,
    ImmutableStore,
    check_url,
    classify_metadata,
    discover,
)
from services.rag.ingestion.pipeline import (
    CurationReview,
    MemoryVectorSink,
    SyntheticHashEncoder,
    ingest_curated,
    preserve_graph,
    preserve_stage,
    stage_document,
)
from services.rag.retrieval import Access, ChunkMetadata, SearchQuery


def metadata(year=2024):
    return dict(
        type="Feature Layer",
        name=f"PL{year}_AR_50K",
        capabilities="Query",
        licenseInfo="synthetic-test-only",
        fields=[
            {
                "name": f"PL{year}_ID",
                "domain": {
                    "codedValues": [
                        {"code": v, "name": "synthetic-" + str(v)} for v in sorted(KLHK_CODES)
                    ]
                },
            }
        ],
    )


class FakeTransport:
    evidence_status = "TESTED_SYNTHETIC"

    def fetch(self, url):
        return json.dumps(metadata()).encode(), {}


class ConnectorTests(unittest.TestCase):
    def test_allowlist_and_redirect_url_pins(self):
        for url in (
            "http://sigap.kehutanan.go.id/x",
            "https://evil.example/",
            "https://api.github.com/repos/worldbank/climateknowledgeportal-evil",
            "https://user:password@sigap.kehutanan.go.id/x",
            "https://sigap.kehutanan.go.id/x?token=secret",
        ):
            with self.assertRaises(Blocked):
                check_url(url)

    def test_year_domain_codes_license_separate(self):
        self.assertEqual(classify_metadata(metadata(), 2024)["status"], "IMPLEMENTED_UNVERIFIED")
        self.assertFalse(classify_metadata(metadata(), 2024)["license_use_approved"])
        self.assertFalse(classify_metadata(metadata(), 2024)["download_access_verified"])
        for changed in [
            dict(name="PL2023"),
            dict(licenseInfo=""),
            dict(fields=[]),
            dict(type="MapServer"),
        ]:
            value = metadata()
            value.update(changed)
            self.assertEqual(classify_metadata(value, 2024)["status"], "BLOCKED")
        value = metadata()
        value["fields"][0]["domain"]["codedValues"][0]["code"] = 999
        self.assertFalse(classify_metadata(value, 2024)["native_23_class_schema_verified"])
        for fields in [
            None,
            {"wrong": "shape"},
            [{"name": "PL2024_ID", "domain": {"codedValues": [None] * 23}}],
        ]:
            value = metadata()
            value["fields"] = fields
            self.assertEqual(classify_metadata(value, 2024)["status"], "BLOCKED")

    def test_immutable_duplicate_preserves_first_receipt_and_detects_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ImmutableStore(tmp)
            kw = dict(version="v1", source_id="synthetic", evidence_status="TESTED_SYNTHETIC")
            first = store.preserve(DICTIONARY, b"body", {}, **kw)
            self.assertEqual(first, store.preserve(DICTIONARY, b"body", {}, **kw))
            with self.assertRaises(Blocked):
                store.preserve(DICTIONARY, b"body", {}, **{**kw, "version": "v2"})
            Path(first["raw_path"]).write_bytes(b"tampered")
            with self.assertRaises(Blocked):
                store.preserve(DICTIONARY, b"body", {}, **kw)

    def test_mock_discovery_never_claims_live_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = discover(2024, FakeTransport(), ImmutableStore(tmp))
            self.assertEqual(result["status"], "TESTED_SYNTHETIC")
            self.assertEqual(result["receipt"]["state"], "TESTED_SYNTHETIC")
            self.assertEqual(
                discover(2000, FakeTransport(), ImmutableStore(tmp))["status"], "BLOCKED"
            )

    def test_budget_and_rate_limit_block_before_request(self):
        transport = BoundedTransport(max_requests=1)
        transport.requests = 1
        with self.assertRaises(Blocked):
            transport.fetch(DICTIONARY)
        transport = BoundedTransport()
        transport.rate_limited = True
        with self.assertRaises(Blocked):
            transport.fetch(DICTIONARY)
        with self.assertRaises(ValueError):
            BoundedTransport(max_requests=100)

    def test_declared_response_size_denied_without_body_read(self):
        class Response:
            headers = {"Content-Length": "999999"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, *args):
                raise AssertionError("큰 본문을 읽으면 안 됨")

        class Opener:
            def open(self, *args, **kwargs):
                return Response()

        with patch("services.datahub.connectors.klhk.source.build_opener", return_value=Opener()):
            with self.assertRaises(Blocked):
                BoundedTransport().fetch(DICTIONARY)


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = ImmutableStore(self.root / "raw")
        with patch(
            "services.datahub.connectors.klhk.source.now", return_value="2026-11-24T00:00:00Z"
        ):
            self.receipt = self.store.preserve(
                DICTIONARY,
                "Rainfall methodology. 강수량 방법론.".encode(),
                {},
                version="v1",
                source_id="synthetic",
                evidence_status="TESTED_SYNTHETIC",
            )
        self.staged = stage_document(
            self.receipt, authority="synthetic-authority", raw_root=self.store.directory
        )
        self.review = CurationReview(
            self.receipt["sha256"],
            "synthetic-reviewer",
            "synthetic-test-only",
            "urn:synthetic:license",
            True,
            True,
        )

    def tearDown(self):
        self.temp.cleanup()

    def factory(self, span):
        return ChunkMetadata(
            source_span=span,
            authority=span.authority,
            language="en",
            access=Access("restricted", frozenset({"curator"})),
            license="synthetic-test-only",
            retrieval_permitted=True,
            valid_from=date(2020, 1, 1),
            valid_until=None,
            spatial_coverage=(105.0, -8.0, 110.0, -5.0),
            time_coverage=(2020, 2030),
            variable="pr",
            scenario="not_applicable",
            model="not_applicable",
            observed_or_projected="not_applicable",
            unit="not_applicable",
            calendar="not_applicable",
            grid="not_applicable",
            claim_authority="methodology_reference",
            dataset_id="synthetic-docs",
            dataset_version="v1",
            acquired_at=self.receipt["acquired_at"],
            trace_id="synthetic-trace",
        )

    def test_full_synthetic_pipeline_kg_vector_acl_citation(self):
        sink = MemoryVectorSink()
        result = ingest_curated(
            self.staged, self.factory, SyntheticHashEncoder(), sink, self.review
        )
        self.assertEqual(result["status"], "TESTED_SYNTHETIC")
        self.assertEqual(result["chunk_count"], 1)
        self.assertEqual(len(result["graph"].edges), 1)
        self.assertEqual(len(sink.records), 1)
        index = result["index"]
        q = SearchQuery("강수량 방법론", date(2026, 11, 24))
        self.assertEqual(index.search(q), ())
        hit = index.search(replace(q, roles=frozenset({"curator"})))[0]
        citation = index.verify_citation(
            hit.chunk.id, hit.chunk.text, replace(q, roles=frozenset({"curator"}))
        )
        self.assertEqual(citation["sha256"], self.staged.document.sha256)
        self.assertIsNone(index.respond(replace(q, text="2050년 강수량 알려줘"))["answer"])

    def test_review_license_validity_required_no_sink_mutation(self):
        for review in [
            None,
            replace(self.review, raw_sha256="0" * 64),
            replace(self.review, license="UNKNOWN"),
            replace(self.review, validity_reviewed=False),
        ]:
            sink = MemoryVectorSink()
            with self.assertRaises(ValueError):
                ingest_curated(self.staged, self.factory, SyntheticHashEncoder(), sink, review)
            self.assertEqual(sink.records, {})

    def test_html_spans_are_extracted_unicode_not_raw_byte_offsets(self):
        raw = "<h1>한글</h1><script>HIDDEN</script><p>설명</p>".encode()
        receipt = self.store.preserve(
            DICTIONARY,
            raw,
            {},
            version="html-v1",
            source_id="synthetic",
            evidence_status="TESTED_SYNTHETIC",
        )
        staged = stage_document(
            receipt, authority="synthetic", raw_root=self.store.directory, format="html"
        )
        self.assertNotIn("HIDDEN", staged.document.text)
        self.assertEqual("".join(s.quote for s in staged.spans), staged.document.text)
        self.assertNotEqual(staged.extraction["raw_sha256"], staged.extraction["text_sha256"])
        self.assertEqual(
            preserve_stage(staged, self.root / "staged"),
            preserve_stage(staged, self.root / "staged"),
        )
        graph_path = preserve_graph(staged, self.root / "graphs")
        graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
        self.assertEqual(len(graph["edges"]), len(staged.spans))
        self.assertFalse(graph["institution_authority_certified"])

    def test_bad_vector_and_external_encoder_are_not_published(self):
        class BadEncoder:
            name = "bad"
            requires_network = False

            def encode(self, texts):
                return ((float("nan"),),)

        class Remote:
            name = "remote"
            requires_network = True

            def encode(self, texts):
                raise AssertionError("외부 요청 금지")

        for encoder in (BadEncoder(), Remote()):
            sink = MemoryVectorSink()
            with self.assertRaises(ValueError):
                ingest_curated(self.staged, self.factory, encoder, sink, self.review)
            self.assertEqual(sink.records, {})

    def test_source_hash_path_and_acquisition_lineage(self):
        with self.assertRaises(ValueError):
            stage_document(
                {**self.receipt, "sha256": "0" * 64},
                authority="synthetic",
                raw_root=self.store.directory,
            )
        with self.assertRaises(ValueError):
            stage_document(self.receipt, authority="synthetic", raw_root=self.root / "other")
        with self.assertRaises(ValueError):
            ingest_curated(
                self.staged,
                lambda s: replace(self.factory(s), acquired_at="2026-01-01T00:00:00Z"),
                SyntheticHashEncoder(),
                MemoryVectorSink(),
                self.review,
            )


if __name__ == "__main__":
    unittest.main()
