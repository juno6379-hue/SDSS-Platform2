"""외부 키·네트워크 없이 수행하는 TESTED_SYNTHETIC 계약 시험."""

import unittest
from dataclasses import replace
from datetime import date
from hashlib import sha256

from services.rag.ontology import (
    NODE_TYPES,
    RELATIONS,
    Edge,
    KnowledgeGraph,
    Node,
    SourceDocument,
    SourceSpan,
)
from services.rag.retrieval import Access, Chunk, ChunkMetadata, HybridIndex, SearchQuery
from services.rag.routing import (
    REQUIRED_NUMERIC_CONTEXT,
    canonical_tokens,
    route_question,
    variables_in,
)

TEXT = "Precipitation methodology explains rainfall. 기온 방법론. Suhu methodology explains temperature."


def document(text=TEXT, **changes):
    values = dict(
        id="doc",
        source_id="source",
        version="v1",
        authority="synthetic-institution",
        source_uri="urn:synthetic:climate-method",
        text=text,
        sha256=sha256(text.encode()).hexdigest(),
    )
    values.update(changes)
    return SourceDocument(**values)


def span(doc):
    return SourceSpan(
        doc.id, doc.source_id, doc.version, doc.sha256, doc.authority, 0, len(doc.text), doc.text
    )


def chunk(identifier="c1", doc=None, **changes):
    doc = doc or document()
    values = dict(
        source_span=span(doc),
        authority=doc.authority,
        language="en",
        access=Access("public", frozenset()),
        license="synthetic-test-only",
        retrieval_permitted=True,
        valid_from=date(2020, 1, 1),
        valid_until=None,
        spatial_coverage=(105.0, -8.0, 110.0, -5.0),
        time_coverage=(2020, 2030),
        variable="pr",
        scenario="ssp245",
        model="synthetic-model",
        observed_or_projected="projected",
        unit="mm/day",
        calendar="360_day",
        grid="synthetic-1-degree",
        claim_authority="methodology_reference",
        dataset_id="synthetic-dataset",
        dataset_version="v1",
        acquired_at="2026-11-24T00:00:00Z",
        trace_id="synthetic-trace",
    )
    values.update(changes)
    return Chunk(identifier, doc.text, ChunkMetadata(**values))


def query(**changes):
    values = dict(text="precipitation methodology", as_of=date(2026, 11, 24))
    values.update(changes)
    return SearchQuery(**values)


class OntologyTests(unittest.TestCase):
    def test_all_sixteen_node_types_have_verified_source_span(self):
        doc = document()
        graph = KnowledgeGraph([doc])
        for kind in NODE_TYPES:
            graph.add_node(Node(kind, kind, span(doc), "v1" if kind == "DatasetVersion" else None))
        self.assertEqual(len(graph.nodes), 16)

    def test_all_eleven_relation_domains_are_enforced(self):
        doc = document()
        graph = KnowledgeGraph([doc])
        for kind in NODE_TYPES:
            graph.add_node(Node(kind, kind, span(doc), "v1" if kind == "DatasetVersion" else None))
        for relation, (domains, ranges) in RELATIONS.items():
            if relation == "SUPERSEDES":
                continue
            left, right = sorted(domains)[0], sorted(ranges)[0]
            if left == right:
                right = next(value for value in sorted(ranges) if value != left)
            graph.add_edge(Edge(left, relation, right, span(doc)))
        self.assertEqual(len(graph.edges), 10)
        with self.assertRaises(ValueError):
            graph.add_edge(Edge("Institution", "HAS_VERSION", "Variable", span(doc)))

    def test_supersedes_requires_distinct_version_same_type(self):
        first, second = document(), document(id="doc2", version="v2")
        graph = KnowledgeGraph([first, second])
        graph.add_node(Node("old", "Policy", span(first), "policy-v1"))
        graph.add_node(Node("new", "Policy", span(second), "policy-v2"))
        graph.add_edge(Edge("new", "SUPERSEDES", "old", span(second)))
        with self.assertRaises(ValueError):
            graph.add_edge(Edge("new", "SUPERSEDES", "new", span(second)))
        graph.add_node(Node("other", "Policy", span(second), "policy-v1"))
        with self.assertRaises(ValueError):
            graph.add_edge(Edge("other", "SUPERSEDES", "old", span(second)))

    def test_forged_span_hash_authority_and_dangling_edges_fail(self):
        doc = document()
        graph = KnowledgeGraph([doc])
        for evidence in [
            replace(span(doc), quote="invented"),
            replace(span(doc), version="v2"),
            replace(span(doc), authority="other"),
            replace(span(doc), start=-1),
            replace(span(doc), document_sha256="0" * 64),
        ]:
            with self.assertRaises(ValueError):
                graph.add_node(Node("bad", "Chunk", evidence))
        with self.assertRaises(ValueError):
            graph.add_edge(Edge("missing", "CITES", "also-missing", span(doc)))
        with self.assertRaises(ValueError):
            document(sha256="0" * 64)


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.doc = document()

    def test_metadata_rejects_missing_acl_license_scope_and_invalid_span(self):
        for fields in [
            dict(access=None),
            dict(license=""),
            dict(language="fr"),
            dict(time_coverage=(2030, 2020)),
            dict(spatial_coverage=(110, -8, 105, -5)),
            dict(variable=""),
            dict(claim_authority="independent_truth"),
        ]:
            with self.assertRaises(ValueError):
                chunk(**fields)
        with self.assertRaises(ValueError):
            HybridIndex([self.doc], [replace(chunk(), text="invented")])
        with self.assertRaises(ValueError):
            Access("restricted", frozenset())

    def test_acl_before_scoring_no_restricted_statistics_leak(self):
        public = chunk()
        private = chunk("secret", access=Access("restricted", frozenset({"researcher"})))
        small = HybridIndex([self.doc], [public])
        large = HybridIndex([self.doc], [public, private])
        self.assertEqual(small.search(query()), large.search(query()))
        self.assertEqual(len(large.search(query(roles=frozenset({"researcher"})))), 2)
        with self.assertRaises(ValueError):
            large.verify_citation("secret", TEXT, query())

    def test_license_expiry_and_future_validity_are_hard_filters(self):
        values = [
            chunk("unlicensed", retrieval_permitted=False),
            chunk("expired", valid_until=date(2025, 1, 1)),
            chunk("future", valid_from=date(2027, 1, 1)),
            chunk("not-yet-acquired", acquired_at="2027-01-01T00:00:00Z"),
        ]
        self.assertEqual(HybridIndex([self.doc], values).search(query()), ())

    def test_metadata_spatial_time_and_cf_calendar_filters(self):
        index = HybridIndex([self.doc], [chunk()])
        self.assertEqual(
            len(
                index.search(
                    query(
                        variable="curah hujan",
                        scenario="ssp245",
                        model="synthetic-model",
                        bbox=(106, -7, 107, -6),
                        years=(2025, 2026),
                        calendar="360_day",
                    )
                )
            ),
            1,
        )
        for changes in [
            dict(scenario="ssp585"),
            dict(observed_or_projected="observed"),
            dict(model="other"),
            dict(calendar="gregorian"),
            dict(bbox=(1, 1, 2, 2)),
            dict(years=(2050, 2060)),
        ]:
            self.assertEqual(index.search(query(**changes)), ())

    def test_bm25_vector_components_deterministic_and_id_tiebreak(self):
        index = HybridIndex([self.doc], [chunk("z"), chunk("a")])
        first = index.search(query())
        self.assertEqual(first, index.search(query()))
        self.assertEqual([hit.chunk.id for hit in first], ["a", "z"])
        self.assertGreater(first[0].bm25, 0)
        self.assertGreater(first[0].vector, 0)
        self.assertIn("SYNTHETIC", first[0].method)

    def test_spatial_time_specificity_contributes_to_hybrid_score(self):
        index = HybridIndex(
            [self.doc],
            [
                chunk("broad"),
                chunk(
                    "specific",
                    spatial_coverage=(106.0, -7.0, 107.0, -6.0),
                    time_coverage=(2025, 2026),
                ),
            ],
        )
        hits = index.search(query(bbox=(106.0, -7.0, 107.0, -6.0), years=(2025, 2026)))
        self.assertEqual(hits[0].chunk.id, "specific")
        self.assertGreater(hits[0].metadata_score, hits[1].metadata_score)

    def test_citation_expired_or_unlicensed_cannot_be_reused(self):
        for value in [chunk(valid_until=date(2025, 1, 1)), chunk(retrieval_permitted=False)]:
            with self.assertRaises(ValueError):
                HybridIndex([self.doc], [value]).verify_citation("c1", TEXT, query())

    def test_citation_verifies_exact_quote_version_span_authority(self):
        index = HybridIndex([self.doc], [chunk()])
        result = index.verify_citation("c1", TEXT, query(), "methodology")
        self.assertEqual(result["sha256"], self.doc.sha256)
        self.assertEqual(result["source_span"], [0, len(TEXT)])
        for identifier, quote, kind in [
            ("missing", TEXT, "descriptive"),
            ("c1", "invented", "descriptive"),
            ("c1", TEXT, "numeric"),
            ("c1", TEXT, "policy_context"),
        ]:
            with self.assertRaises(ValueError):
                index.verify_citation(identifier, quote, query(), kind)

    def test_response_is_cited_excerpts_only_no_generated_answer(self):
        result = HybridIndex([self.doc], [chunk()]).respond(query())
        self.assertEqual(result["status"], "CITED_EXCERPTS_ONLY")
        self.assertIsNone(result["answer"])
        self.assertEqual(result["citations"][0]["quote"], TEXT)

    def test_principal_and_bbox_cannot_use_implicit_mutable_acl(self):
        with self.assertRaises(ValueError):
            query(roles="admin")
        with self.assertRaises(ValueError):
            chunk(spatial_coverage=[105, -8, 110, -5])
        with self.assertRaises(ValueError):
            query(bbox=(float("nan"), 0, 10, 10))


class RoutingTests(unittest.TestCase):
    def test_korean_indonesian_english_aliases(self):
        for alias in ("강수량", "curah hujan", "precipitation", "rainfall", "pr"):
            self.assertEqual(variables_in(alias), ("pr",))
        for alias in ("최고 기온", "suhu maksimum", "maximum temperature"):
            self.assertEqual(variables_in(alias), ("tasmax",))
        self.assertEqual(canonical_tokens("Suhu"), canonical_tokens("기온"))

    def test_quantitative_queries_in_three_languages_never_return_rag(self):
        index = HybridIndex([document()], [chunk()])
        for question in (
            "2050년 강수량 알려줘",
            "평균 기온은 얼마인가",
            "Berapa curah hujan 2050?",
            "Average temperature in Indonesia?",
            "Temperature 2050",
            "강수량 20 mm",
            "nilai iklim",
            "현재 기온",
            "What will rainfall be in twenty fifty?",
            "suhu di Jakarta",
        ):
            decision = route_question(question)
            self.assertEqual(decision.kind, "structured_climate_tool", question)
            self.assertEqual(decision.status, "BLOCKED")
            result = index.respond(query(text=question))
            self.assertEqual(result["citations"], ())
            self.assertIsNone(result["answer"])
            with self.assertRaises(ValueError):
                index.search(query(text=question))

    def test_complete_numeric_context_still_requires_tool_no_vector_answer(self):
        context = {field: "explicit-value" for field in REQUIRED_NUMERIC_CONTEXT}
        result = HybridIndex([document()], [chunk()]).respond(
            query(text="average temperature"), context
        )
        self.assertEqual(result["status"], "TOOL_REQUIRED")
        self.assertEqual(result["citations"], ())
        self.assertEqual(result["route"].tool_id, "climate.query")

    def test_explanation_retrieval_and_empty_query_limits(self):
        self.assertEqual(route_question("precipitation methodology").kind, "descriptive_rag")
        for text in ("", " " * 10, "x" * 4001):
            with self.assertRaises(ValueError):
                route_question(text)


if __name__ == "__main__":
    unittest.main()
