from contextlib import contextmanager

from services.api.lineage_projection import _project


def test_lineage_job_result_chain_keeps_catalog_document():
    nodes, links = {}, set()

    class Transaction:
        def put_node(self, kind, key, digest, document):
            nodes[(kind, key)] = (digest, document)

        def link(self, source, source_key, target, target_key):
            assert (source, source_key) in nodes and (target, target_key) in nodes
            links.add((source, target))

        def ancestry(self, kind, key):
            assert nodes[kind, key][1] == {"package": {"institution": "test"}}
            return sorted(links)

    class Store:
        @contextmanager
        def transaction(self, institution):
            assert institution == "institution-a"
            yield Transaction()

    result = _project(
        Store(),
        "institution-a",
        {
            "job_id": "job-id",
            "provider": "fixture",
            "operation": "analysis",
            "model": {"name": "test", "version": "v1", "artifact_sha256": "a" * 64},
        },
        "result-id",
        "b" * 64,
        {"package": {"institution": "test"}},
        {"sha256": "c" * 64},
        {"sha256": "d" * 64, "bytes": 64},
    )
    assert result == [("dataset", "job"), ("job", "result"), ("model", "job")]
