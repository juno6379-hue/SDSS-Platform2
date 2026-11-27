from threading import Event

import pytest
from fastapi.testclient import TestClient

from services.api import lcluc_geollm
from services.api.app import create_app
from services.api.geollm_storage import (
    DataLakeGeoLLMStorage,
    LocalGeoLLMStorage,
    StorageBlocked,
    select_geollm_storage,
)
from services.lcluc.question import parse_question


@pytest.mark.parametrize(("question", "kind", "classes"), [
    ("MapBiomas ATBD의 Gap Fill 방법은?", "document", ()),
    ("Berapa luas sawah di Banten pada 2024 menurut MapBiomas?", "area", ("rice",)),
    ("Show MapBiomas forest-to-urban transitions in Banten from 2023 to 2024", "transition", ("forest", "urban")),
    ("MapBiomas 반텐 2023년부터 2024년까지 산림 감소량은?", "forest_loss", ("forest",)),
    ("MapBiomas 반텐 2023년부터 2024년까지 산림 순감소는?", "forest_net_change", ("forest",)),
])
def test_multilingual_intent(question, kind, classes):
    result = parse_question(question)
    assert result.metric == kind and result.classes == classes and result.issue is None


def test_blocked_query_does_not_invoke_document_retrieval_as_fallback(monkeypatch):
    def never(*args):
        pytest.fail("Numeric-only query invoked document retrieval")

    def unavailable(*args):
        raise FileNotFoundError

    monkeypatch.setattr(LocalGeoLLMStorage, "search", never)
    monkeypatch.setattr(lcluc_geollm, "mapbiomas_answer", unavailable)
    questions = {
        "반텐 산림부 2023년부터 2024년까지 산림 감소량은?": "KEMENHUT_ASSET_NOT_READY",
        "MapBiomas Esri Banten rice area 2024": "PRODUCT_AMBIGUOUS",
        "MapBiomas Banten and West Java rice area 2024": "BANTEN_PROVINCE_ONLY",
        "MapBiomas Banten rice area 2024": "EVIDENCE_NOT_READY",
        "MapBiomas Collection 3.0 Banten rice area 2024": "PRODUCT_VERSION_NOT_READY",
        "Esri v002 Banten tree area 2024": "PRODUCT_VERSION_NOT_READY",
        "MapBiomas Banten 2023 to 2024 forest and urban transitions": "TRANSITION_DIRECTION_REQUIRED",
    }
    for question, reason in questions.items():
        reply = lcluc_geollm.answer_question(LocalGeoLLMStorage(None), question)
        assert reply["status"] == "BLOCKED" and reply["route"] == "gis" and reply["reason"] == reason
        assert reply["metrics"] == reply["citations"] == []


def test_forest_loss_uses_transition_margins_and_net_change_uses_annual_areas():
    cover = {"years": [2023, 2024], "classes": [
        {"code": 3, "name": "Forest", "areas_ha": [100, 95]},
        {"code": 24, "name": "Urban", "areas_ha": [10, 15]},
    ]}
    table = {"periods": ["2023-2024"], "pairs": {
        "3:3": {"areas_ha": [90], "row": 1}, "3:24": {"areas_ha": [10], "row": 2},
        "24:3": {"areas_ha": [5], "row": 3}, "24:24": {"areas_ha": [5], "row": 4},
    }}
    intent = parse_question("MapBiomas Banten forest loss from 2023 to 2024")
    values, _, sheet, limitations, rows = lcluc_geollm.mapbiomas_values(intent, cover, table)
    assert sheet == "TRANSITION" and values[0]["value"] == 10 and rows == [2]
    assert "FOREST_START_MARGIN_CHECKED" in limitations
    net = parse_question("MapBiomas Banten net forest area change from 2023 to 2024")
    values, _, sheet, _, _ = lcluc_geollm.mapbiomas_values(net, cover)
    assert sheet == "COVERAGE" and values[0]["value"] == -5
    table["pairs"]["3:3"]["areas_ha"][0] = 89
    with pytest.raises(lcluc_geollm.Unavailable, match="COVERAGE_MISMATCH"):
        lcluc_geollm.mapbiomas_values(intent, cover, table)


def test_no_missing_transition_value_or_period_is_replaced_by_zero():
    table = {"periods": ["2023-2024"], "pairs": {"3:24": {"areas_ha": [None], "row": 19}}}
    with pytest.raises(lcluc_geollm.Unavailable, match="TRANSITION_NOT_PUBLISHED"):
        lcluc_geollm.sum_transitions(table, "2023-2024", {3}, {24})
    with pytest.raises(lcluc_geollm.Unavailable, match="PERIOD_NOT_PUBLISHED"):
        lcluc_geollm.sum_transitions(table, "2022-2024", {3}, {24})

def test_staging_numeric_query_uses_published_tables_and_remote_boundary():
    class Lake:
        release = "test-release"

        def __init__(self):
            self.asset_names = []

        def attested(self, name, purpose, digest):
            self.asset_names.append((name, purpose, digest))

        def document(self, name):
            assert name == "mapbiomas"
            return {"document": {"coverage": {
                "years": [2024], "classes": [{"code": 40, "name": "Rice Paddy", "areas_ha": [195653.67]}],
                "source_url": "https://example.test/statistics", "workbook_url": "https://example.test/workbook",
                "acquired_on": "2026-11-26",
            }}}

    lake = Lake()
    response = lcluc_geollm.answer_question(DataLakeGeoLLMStorage(lake), "MapBiomas Banten rice area 2024")
    assert response["metrics"][0]["value"] == 195653.67
    assert response["data_release"] == "test-release"
    assert response["map"]["boundary_url"] == "/api/lcluc/geollm/map/boundary"
    assert [item[1] for item in lake.asset_names] == ["workbook", "coverage"]


def test_staging_document_outage_does_not_fall_back_to_local_index(monkeypatch):
    class UnavailableLake:
        def search(self, question):
            raise OSError("unavailable")

    def unexpected(*args):
        pytest.fail("Staging query invoked local index")

    monkeypatch.setattr(LocalGeoLLMStorage, "search", unexpected)
    reply = lcluc_geollm.answer_question(DataLakeGeoLLMStorage(UnavailableLake()), "MapBiomas ATBD의 Gap Fill 방법은?")
    assert reply["status"] == "BLOCKED" and reply["citations"] == []
    assert reply["reason"] == "GEOLLM_STORAGE_UNAVAILABLE"


@pytest.mark.parametrize(("mode", "release", "reason"), [
    ("lake", None, "GEOLLM_STORAGE_CONFIG_REQUIRED"),
    ("typo", None, "GEOLLM_STORAGE_MODE_INVALID"),
    (None, "existing-release", "GEOLLM_STORAGE_CONFIG_REQUIRED"),
])
def test_lake_misconfiguration_leaves_application_running(monkeypatch, mode, release, reason):
    for name, value in (("SDSS_GEOLLM_STORAGE_MODE", mode), ("SDSS_GEOLLM_LAKE_RELEASE", release)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    monkeypatch.delenv("SDSS_STORAGE_DSN", raising=False)
    with TestClient(create_app(), base_url="http://localhost", client=("127.0.0.1", 51437)) as client:
        assert client.get("/api/health").status_code == 200
        for text in ("MapBiomas Banten rice area 2024", "MapBiomas ATBD의 Gap Fill 방법은?"):
            answer = client.post("/api/lcluc/geollm/query", json={"question": text}).json()
            assert answer["status"] == "BLOCKED" and answer["reason"] == reason
            assert not answer["citations"] and not answer.get("metrics") and "map" not in answer
        catalog = client.get("/api/rag/mapbiomas/catalog").json()
        assert catalog["blockers"] == [reason] and not catalog["documents"]
        remote_map = client.get("/api/lcluc/geollm/map/boundary")
        assert remote_map.status_code == 503 and remote_map.json()["detail"] == reason


def test_explicit_local_mode_is_available_with_lake_settings(monkeypatch):
    monkeypatch.setenv("SDSS_GEOLLM_STORAGE_MODE", "local")
    monkeypatch.setenv("SDSS_GEOLLM_LAKE_RELEASE", "ignored-release")
    assert isinstance(select_geollm_storage(None), LocalGeoLLMStorage)


def test_data_lake_gis_retries_same_backend_after_outage(monkeypatch):
    def unexpected(*args):
        pytest.fail("Data Lake query attempted local access")

    monkeypatch.setattr(LocalGeoLLMStorage, "mapbiomas", unexpected)

    class Lake:
        release = "test-release"
        available = False

        def attested(self, *args):
            if not self.available:
                raise OSError("private storage connection data")

        def document(self, name):
            return {"document": {"coverage": {
                "years": [2024], "classes": [{"code": 40, "name": "Rice Paddy", "areas_ha": [195653.67]}],
                "source_url": "https://example.test/statistics", "workbook_url": "https://example.test/workbook",
                "acquired_on": "2026-11-26",
            }}}

    lake = Lake()
    storage = DataLakeGeoLLMStorage(lake)
    question = "MapBiomas Banten rice area 2024"
    blocked = lcluc_geollm.answer_question(storage, question)
    assert blocked["reason"] == "GEOLLM_STORAGE_UNAVAILABLE"
    assert blocked["metrics"] == blocked["sources"] == [] and "map" not in blocked
    lake.available = True
    assert lcluc_geollm.answer_question(storage, question)["metrics"][0]["value"] == 195653.67


def test_document_preparation_retries_in_background_after_startup_failure():
    retry_started = Event()
    release_retry = Event()
    retry_finished = Event()

    class Lake:
        available = False

        def warm_model(self):
            if not self.available:
                raise OSError("store unavailable at startup")
            retry_started.set()
            assert release_retry.wait(3)

        def search(self, question):
            return {"status": "FOUND"}

    lake = Lake()
    storage = DataLakeGeoLLMStorage(lake)
    storage.warm_documents()
    lake.available = True
    warm = storage.warm_documents

    def run_retry():
        warm()
        retry_finished.set()

    storage.warm_documents = run_retry
    try:
        with pytest.raises(StorageBlocked, match="GEOLLM_STORAGE_UNAVAILABLE"):
            storage.search("Explain Gap Fill")
        assert retry_started.wait(3)
        with pytest.raises(StorageBlocked, match="GEOLLM_STORAGE_INITIALIZING"):
            storage.search("Explain Gap Fill")
    finally:
        release_retry.set()
    assert retry_finished.wait(3)
    assert storage.search("Explain Gap Fill") == {"status": "FOUND"}


def test_staging_object_exporter_publishes_the_verified_cache_path(monkeypatch):
    from pathlib import Path

    from services.lcluc.geollm_lake import GeoLLMLake

    class Exporter:
        def export_asset(self, institution, digest, size, directory):
            assert institution == "staging-cckp"
            assert size == 3
            (Path(directory) / digest).write_bytes(b"map")

    lake = GeoLLMLake("test-release", "unused", "staging-cckp", Exporter())
    monkeypatch.setattr(lake, "binding", lambda *args: {"sha256": "a" * 64, "byte_count": 3})
    assert lake.file("esri", "preview-2024").read_bytes() == b"map"

    def disconnected(asset):
        raise OSError("object store offline")

    monkeypatch.setattr(lake, "_attest_object", disconnected)
    with pytest.raises(OSError, match="object store offline"):
        lake.file("esri", "preview-2024", require_live=True)
    lake._cache.cleanup()
