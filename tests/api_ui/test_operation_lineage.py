from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api import operation_lineage


def test_storage_routes_only_expose_institution_pinned_fields(monkeypatch):
    request_log = []

    class Repository:
        def __init__(self, dsn):
            assert dsn == "fixture"

        @contextmanager
        def transaction(self, institution):
            request_log.append(institution)
            yield self

        def get_node(self, kind, key):
            return {
                "kind": kind,
                "node_key": key,
                "sha256": "1" * 64,
                "document": {"hidden": "private"},
            }

        def ancestry(self, kind, key):
            return [{"kind": "job", "node_key": "fixture-job", "sha256": "2" * 64}]

        def get_asset(self, kind, key, purpose):
            return None if purpose == "absent" else {"digest": "1" * 64}

    class Objects:
        @classmethod
        def from_env(cls):
            return cls()

        def download_link(self, tx, kind, key, purpose, *, expires_in):
            assert (kind, key, purpose) == ("result", "result-1", "report")
            return {"url": "https://example.test/signed", "expires_in_seconds": expires_in}

    app = FastAPI()
    operation_lineage.mount_operation_lineage(app)
    for k, v in {
        "SDSS_STORAGE_DSN": "fixture",
        "SDSS_STORAGE_INSTITUTION": "org-a",
        "SDSS_STORAGE_READ_TOKEN": "fixture-token",
        "SDSS_STORAGE_BUCKET": "fixture-bucket",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(operation_lineage, "LineageStore", Repository)
    monkeypatch.setattr(operation_lineage, "ObjectStore", Objects)
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50000)) as client:
        root = "/api/lineage/result/result-1"
        assert client.get("/api/storage/status").json()["status"] == "CONFIGURED_PROBE_REQUIRED"
        assert client.get(root).status_code == 403 and not request_log
        headers = {"Authorization": "Bearer fixture-token"}
        answer = client.get(root, headers=headers)
        assert answer.status_code == 200 and set(answer.json()["node"]) == {
            "kind",
            "node_key",
            "sha256",
        }
        assert answer.json()["ancestors"][0]["node_key"] == "fixture-job"
        assert client.get(root + "/assets/absent", headers=headers).status_code == 404
        assert (
            client.get(root + "/assets/report", headers=headers).json()["expires_in_seconds"] == 300
        )
        assert set(request_log) == {"org-a"}
