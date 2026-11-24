"""로컬 API·정적 UI의 fail-closed 및 기존 실제 CCKP 재현 통합시험."""

import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from services.api.app import create_app
from services.api.evidence import ROOT, EvidenceBlocked, EvidenceStore
from services.api.pinned import LOCK_SHA256


def fixture_store(tmp_path, payload=b'{"status":"synthetic"}'):
    path = tmp_path / "fixture.json"
    path.write_bytes(payload)
    captured = datetime(2026, 11, 24, tzinfo=timezone.utc)
    lock = {
        "reviewed_at": captured.isoformat(),
        "valid_days": 7,
        "groups": {
            "fixture": {
                "files": {
                    "fixture.json": {"bytes": len(payload), "sha256": sha256(payload).hexdigest()}
                },
                "missing": [],
            }
        },
    }
    raw = json.dumps(lock).encode()
    pin = tmp_path / "lock.json"
    pin.write_bytes(raw)
    return EvidenceStore(
        tmp_path, pin, sha256(raw).hexdigest(), clock=lambda: captured + timedelta(hours=1)
    )


@pytest.fixture
def actual_store():
    path = ROOT / "services/api/evidence-lock.json"
    reviewed = datetime.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["reviewed_at"])
    # 고정된 역사 snapshot의 무결성을 재현한다. 운영 앱의 실제 clock은 고정하지 않는다.
    return EvidenceStore(ROOT, path, LOCK_SHA256, clock=lambda: reviewed + timedelta(minutes=1))


def test_missing_hash_drift_unpinned_and_stale_are_blocked(tmp_path):
    store = fixture_store(tmp_path)
    assert store.read_json("fixture", "fixture.json")[0]["status"] == "synthetic"
    with pytest.raises(EvidenceBlocked):
        store.read_json("fixture", "other.json")
    with pytest.raises(EvidenceBlocked):
        store.check("missing")
    store.clock = lambda: datetime(2027, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(EvidenceBlocked, match="STALE"):
        store.check("fixture")
    store.clock = lambda: datetime(2026, 11, 24, tzinfo=timezone.utc)
    (tmp_path / "fixture.json").write_bytes(b"changed")
    with pytest.raises(EvidenceBlocked):
        store.check("fixture")


def test_lock_tamper_path_escape_and_invalid_json(tmp_path):
    store = fixture_store(tmp_path, b"not-json")
    with pytest.raises(EvidenceBlocked, match="JSON_INVALID"):
        store.read_json("fixture", "fixture.json")
    with pytest.raises(EvidenceBlocked):
        store.safe_path("../outside")
    store.lock_path.write_text("{}")
    with pytest.raises(EvidenceBlocked, match="LOCK_SHA"):
        store.check("fixture")


def test_health_static_headers_and_no_external_assets(tmp_path):
    client = TestClient(create_app(fixture_store(tmp_path)))
    health = client.get("/api/health")
    assert health.status_code == 200 and health.json()["scope"] == "LOCAL_API_PROCESS_ONLY"
    page = client.get("/")
    assert page.status_code == 200 and "frame-ancestors" in page.headers["content-security-policy"]
    assert 'data-testid="climate-run"' in page.text
    assert 'data-testid="report-search"' in page.text
    assert 'data-testid="training-execute" disabled' in page.text
    assert 'data-testid="deployment-execute" disabled' in page.text
    assert client.get("/assets/app.js").status_code == 200
    assert "https://" not in client.get("/assets/app.js").text


def test_missing_evidence_is_409_without_value(tmp_path):
    client = TestClient(create_app(fixture_store(tmp_path)))
    for path in ("cckp", "klhk", "models", "sentinel", "vector"):
        response = client.get("/api/" + path)
        assert response.status_code == 409 and response.json()["status"] == "BLOCKED"
        assert response.json()["value"] is None


def test_execution_remains_disabled_and_cross_origin_denied(tmp_path):
    client = TestClient(create_app(fixture_store(tmp_path)))
    for action in ("training", "deployment"):
        response = client.post("/api/actions/" + action)
        assert response.status_code == 409 and response.json()["execution_started"] is False
    assert (
        client.post("/api/actions/training", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert client.get("/api/gates").json()["gates"][0]["allowed"] is False


def test_invalid_input_no_role_or_path_injection(tmp_path):
    client = TestClient(create_app(fixture_store(tmp_path)))
    assert (
        client.post(
            "/api/climate/query", json={"raw_path": "C:/private", "url": "https://example.com"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/rag/search", json={"question": "metadata", "roles": ["data_steward"]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/reports/search", json={"question": "metadata", "roles": ["admin"]}
        ).status_code
        == 422
    )


def test_numeric_rag_never_returns_values_or_citations(tmp_path):
    client = TestClient(create_app(fixture_store(tmp_path)))
    for path in ("rag/search", "reports/search"):
        response = client.post("/api/" + path, json={"question": "2050년 강수량은 얼마인가?"})
        assert response.status_code == 200 and response.json()["route"] == "climate.query"
        assert response.json()["answer"] is None and response.json()["citations"] == []


def test_real_snapshot_and_local_numeric_reproduction(actual_store):
    client = TestClient(create_app(actual_store))
    snapshot = client.get("/api/cckp")
    assert snapshot.status_code == 200 and snapshot.json()["status"] == "VERIFIED_REAL"
    contract = client.get("/api/climate/contract").json()
    replay = client.post("/api/climate/query", json=contract["sample"])
    assert replay.status_code == 200 and replay.json()["status"] == "VERIFIED_REAL"
    assert replay.json()["result"]["value"] == pytest.approx(
        snapshot.json()["result"]["value"], abs=1e-10
    )
    assert replay.json()["result"]["geography_is_official_country_polygon"] is False
    assert replay.json()["external_requests"] == 0
    bad = {**contract["sample"], "scenario": "ssp585"}
    assert client.post("/api/climate/query", json=bad).json()["status"] == "BLOCKED"


def test_klhk_private_rag_vector_and_workflow_truth(actual_store):
    client = TestClient(create_app(actual_store))
    klhk = client.get("/api/klhk").json()
    assert klhk["status"] == "BLOCKED" and klhk["institution_authority_certified"] is False
    vector = client.get("/api/vector").json()
    assert vector["backend"] == "SQLITE_LOCAL_PRIVATE_REVIEW" and vector["chunk_count"] == 122
    assert vector["public_search_enabled"] is False and vector["steward_auth_implemented"] is False
    rag = client.post("/api/rag/search", json={"question": "CCKP methodology"}).json()
    assert rag["status"] == "BLOCKED" and rag["citations"] == []
    report = client.post("/api/reports/search", json={"question": "CCKP methodology"}).json()
    assert report["status"] == "BLOCKED" and report["citations"] == [] and report["answer"] is None
    workflow = client.get("/api/workflow").json()
    assert workflow["execution_started"] is False
    assert workflow["persisted_workflow"]["status"] == "BLOCKED"


def test_actual_model_catalog_and_checkpoint_audit_do_not_open_execution(actual_store):
    client = TestClient(create_app(actual_store))
    response = client.get("/api/models")
    assert response.status_code == 200
    value = response.json()
    assert value["status"] == "BLOCKED" and value["execution_started"] is False
    assert value["legacy_checkpoint_audit"]["status"] == "BLOCKED"
    assert value["legacy_checkpoint_audit"]["independent_metrics"] is None
    assert all(model["axes"]["deployment"]["allowed"] is False for model in value["models"])


def test_final_sentinel_audit_is_not_collection_completion(actual_store):
    client = TestClient(create_app(actual_store))
    response = client.get("/api/sentinel")
    assert response.status_code == 200
    value = response.json()
    assert value["status"] == "BLOCKED_COLLECTION_NOT_COMPLETE"
    assert value["audit_state"] == "VERIFIED_REAL"
    assert value["audited_cells"] == value["expected_cells"] == 36
    assert value["completion"] is False and value["full_spatial_coverage"] is False
    assert value["physical_patch_records"] == 1779
    assert value["quality_eligible_patches"] == 1407
    assert value["verified_parent_frames"] == 119
    assert value["paired_six_band_same_scene_scl_coverage_pct"] == pytest.approx(0.9767414314)
    assert value["clear_coverage_pct"] == pytest.approx(0.8898034033)
    assert value["migration"]["cas_objects"] == 6125
    assert value["migration"]["cas_bytes"] == 3904601927
    assert value["pre_pilot_audit_remote_downloads"] == 0
    assert value["runtime_snapshot"]["active_collector_count"] == 0
    assert value["runtime_snapshot"]["reference_execution_lock_exists"] is False
    assert value["runtime_snapshot"]["migration_lock_exists"] is False
    assert value["exact_missing_queue"]["features"] == 72
    assert value["exact_missing_queue"]["geometry_included"] is False
    assert len(value["exact_missing_queue"]["sha256"]) == 64
    assert len(response.content) < 20000
    lock = json.loads(actual_store.lock_path.read_text(encoding="utf-8"))
    assert len(lock["groups"]["sentinel"]["files"]) == 7
    assert not any(".geojson" in path for path in lock["groups"]["sentinel"]["files"])


def test_verified_pilot_does_not_recompute_global_coverage_or_independent_accuracy(actual_store):
    client = TestClient(create_app(actual_store))
    response = client.get("/api/sentinel")
    value = response.json()
    pilot = value["pilot"]
    assert pilot["status"] == "VERIFIED_REAL"
    assert pilot["execution_status"] == "PILOT_QA_PASS"
    assert pilot["province"] == "east_java" and pilot["year"] == 2023
    assert pilot["bands"] == ["B02", "B03", "B04", "B08", "B11", "B12", "SCL"]
    assert pilot["qa"]["same_scene_all_assets"] is True
    assert pilot["qa"]["clear_pixels"] == pilot["qa"]["pixel_count"] == 65536
    assert pilot["qa"]["clear_fraction"] == 1.0
    assert pilot["qa"]["independent_accuracy_measured"] is False
    assert pilot["remote_body_bytes_read"] == 7471506
    assert pilot["remote_request_count"] == 28 and pilot["measurement_complete"] is True
    assert pilot["error_count"] == 0 and pilot["observed_http429"] is False
    assert pilot["remaining_global_bytes"] == 1678521030
    assert pilot["subsequent_pilots_started"] == pilot["collector_count"] == 0
    assert pilot["execution_lock_exists"] is pilot["ledger_lock_exists"] is False
    assert "BIG_AUTHORITY_APPROVAL_PENDING" in pilot["acceptance_blockers"]
    assert "INDEPENDENT_GROUND_TRUTH_UNVERIFIED" in pilot["acceptance_blockers"]
    assert value["global_coverage_aggregate_updated"] is False
    assert value["completion"] is value["full_spatial_coverage"] is False
    assert value["coverage_basis"] == "PRE_PILOT_HELD_AUDIT_NOT_RECOMPUTED"
    assert (
        value["reservation_adapter"] == "BOUNDED_PILOT_VERIFIED_NO_GENERAL_COLLECTION_AUTHORIZATION"
    )
    assert "GENERAL_COLLECTION_AUTHORIZATION_PENDING" in value["blockers"]
    assert "POST_PILOT_AGGREGATE_NOT_RECOMPUTED" in value["blockers"]
    assert "READ_ONLY_REFERENCE_LEDGER_NO_AUTHORIZED_RESERVATION_ADAPTER" not in value["blockers"]
    assert "EXACT_SCENE_ASSET_WINDOW_PINS_MISSING" not in value["blockers"]
    assert len(response.content) < 20000
