from hashlib import sha256

from fastapi.testclient import TestClient

from services.api import results
from services.api.app import create_app
from services.api.evidence import EvidenceStore
from services.results.registry import ResultRegistry


def make_app(tmp_path, monkeypatch):
    raw = b'{"status":"BLOCKED"}\n'
    proof = tmp_path / "proof.json"
    proof.write_bytes(raw)
    pin = {"path": proof.name, "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}
    monkeypatch.setattr(
        results,
        "catalog",
        lambda: {
            "version-1": {
                "domain": "mlops",
                "title": "평가 Gate",
                "summary": "독립정확도 증거 대기",
                "evidence_status": "BLOCKED",
                "evidence": [pin],
                "blockers": ["INDEPENDENT_ACCURACY_MISSING"],
            },
        },
    )
    store = EvidenceStore(tmp_path, tmp_path / "unused.json", "unused")
    registry = ResultRegistry(tmp_path / "results.sqlite3")
    return create_app(store, result_registry=registry), proof


def local_client(app):
    return TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50000))


def test_registration_review_and_filtered_query_persist(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with local_client(app) as client:
        assert client.get("/api/results/sources").json()["sources"][0]["source"] == "version-1"
        registered = client.post("/api/results", json={"source": "version-1"})
        assert registered.status_code == 200
        result = registered.json()["result"]
        assert (result["review_status"], result["revision"]) == ("PENDING", 0)
        assert client.post("/api/results", json={"source": "version-1"}).json()["result"] == result
        root = "/api/results/" + result["id"]
        review = {
            "decision": "CHANGES_REQUESTED",
            "reviewer": "test-reviewer",
            "note": "근거 필요",
            "expected_revision": 0,
        }
        assert client.post(root + "/reviews", json=review).json()["result"]["revision"] == 1
        stale = client.post(root + "/reviews", json={**review, "decision": "ACCEPTED"})
        assert (stale.status_code, stale.json()["blockers"]) == (409, ["REVIEW_CONFLICT"])
        written = client.post(
            root + "/reviews", json={**review, "decision": "ACCEPTED", "expected_revision": 1}
        ).json()["result"]
        assert written["evidence_status"] == "BLOCKED"
        assert written["blockers"] == ["INDEPENDENT_ACCURACY_MISSING"]
        assert written["review_status"] == "ACCEPTED"
        assert written["revision"] == 2
        assert [r["decision"] for r in written["reviews"]] == ["CHANGES_REQUESTED", "ACCEPTED"]
        assert client.get(root).json()["result"] == written
        assert client.get("/api/results?domain=mlops&review_status=ACCEPTED").json()["results"] == [
            written
        ]
        assert client.get("/api/results?review_status=PENDING").json()["results"] == []


def test_evidence_drift_blocks_registration_and_review(tmp_path, monkeypatch):
    app, proof = make_app(tmp_path, monkeypatch)
    with local_client(app) as client:
        result_id = client.post("/api/results", json={"source": "version-1"}).json()["result"]["id"]
        proof.write_bytes(proof.read_bytes().replace(b"BLOCKED", b"DELETED"))
        register = client.post("/api/results", json={"source": "version-1"})
        assert register.status_code == 409
        assert register.json()["blockers"] == ["RESULT_EVIDENCE_SHA_DRIFT:proof.json"]
        root = "/api/results/" + result_id
        blocked = client.post(
            root + "/reviews",
            json={
                "decision": "ACCEPTED",
                "reviewer": "test-reviewer",
                "note": "",
                "expected_revision": 0,
            },
        )
        assert blocked.status_code == 409
        assert client.get(root).json()["result"]["revision"] == 0


def test_untrusted_registration_and_hosts_are_denied(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with local_client(app) as client:
        assert client.post("/api/results", json={"source": "unknown"}).status_code == 404
        assert (
            client.post(
                "/api/results", json={"source": "version-1", "evidence_status": "VERIFIED_REAL"}
            ).status_code
            == 422
        )
        assert client.get("/api/results", headers={"Host": "rebound.test"}).status_code == 403
        assert (
            client.post(
                "/api/results",
                json={"source": "version-1"},
                headers={"Origin": "https://elsewhere.test"},
            ).status_code
            == 403
        )
    with TestClient(app, base_url="http://localhost", client=("192.0.2.7", 50000)) as client:
        assert client.get("/api/results").status_code == 403
