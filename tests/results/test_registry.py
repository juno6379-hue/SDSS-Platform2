from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from services.results.registry import RegistryError, ResultRegistry


@pytest.fixture
def registry(tmp_path):
    return ResultRegistry(tmp_path / "review" / "results.sqlite3")


def sample(**kwargs):
    return {
        "domain": "rtrw",
        "source_key": "one-map-14/2026-11-25",
        "title": "공개 서비스의 주별 공간계획 현황",
        "evidence_status": "BLOCKED",
        "summary": {"official_current_regions": 0, "older_versions": 6},
        "evidence": [{"path": "evidence/rtrw/sample.json", "sha256": "1" * 64, "bytes": 42}],
        "blockers": ["CURRENT_PROVINCIAL_VECTOR_NOT_VERIFIED"],
        **kwargs,
    }


def review(registry, identifier, revision, *, decision="ACCEPTED", note="근거 확인"):
    return registry.review(
        identifier, decision=decision, reviewer="내부 검토", note=note, expected_revision=revision
    )


def test_registration_is_durable_immutable_and_idempotent(registry):
    item = registry.register(**sample())
    assert item["review_status"] == "PENDING"
    assert item["revision"] == 0 and item["reviews"] == []
    assert (
        registry.register(**sample(summary={"older_versions": 6, "official_current_regions": 0}))
        == item
    )
    with pytest.raises(RegistryError, match="^RESULT_CONFLICT$"):
        registry.register(**sample(evidence_status="VERIFIED_REAL"))
    reopened = ResultRegistry(registry.path)
    assert reopened.get(item["id"]) == item
    assert reopened.list_results(domain="rtrw", review_status="PENDING") == [item]
    assert reopened.list_results(domain="klhk") == []


def test_append_only_review_retry_keeps_original_and_does_not_promote_evidence(registry):
    before = registry.register(**sample())
    identifier = before["id"]
    accepted = review(registry, identifier, 0)
    assert accepted["review_status"] == "ACCEPTED"
    assert accepted["revision"] == 1
    assert accepted["evidence_status"] == before["evidence_status"] == "BLOCKED"
    assert accepted["summary"] == before["summary"]
    assert accepted["evidence"] == before["evidence"]
    assert accepted["blockers"] == before["blockers"]
    assert review(registry, identifier, 0) == accepted
    with pytest.raises(RegistryError, match="^REVIEW_CONFLICT$"):
        review(registry, identifier, 0, note="수정된 요청")
    changes = review(registry, identifier, 1, decision="CHANGES_REQUESTED", note="현행성 추가 확인")
    assert changes["revision"] == 2
    assert [event["decision"] for event in changes["reviews"]] == ["ACCEPTED", "CHANGES_REQUESTED"]
    assert review(registry, identifier, 0) == changes
    assert registry.list_results(review_status="ACCEPTED") == []
    assert registry.list_results(review_status="CHANGES_REQUESTED") == [changes]


def test_concurrent_writes_allow_only_one_different_review_at_a_revision(registry):
    start_registration = Barrier(2)

    def register_once(_):
        start_registration.wait(timeout=5)
        return registry.register(**sample())

    with ThreadPoolExecutor(max_workers=2) as pool:
        result, duplicate = pool.map(register_once, range(2))
    assert result == duplicate
    assert len(registry.list_results()) == 1

    start_review = Barrier(2)

    def record_review(note):
        start_review.wait(timeout=5)
        try:
            return review(registry, result["id"], 0, note=note)["revision"]
        except RegistryError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(record_review, ["검토 A", "검토 B"]))
    assert set(outcomes) == {1, "REVIEW_CONFLICT"}
    assert len(registry.get(result["id"])["reviews"]) == 1


@pytest.mark.parametrize(
    "path",
    [
        "../data.json",
        "evidence/../data.json",
        "evidence/.. /data.json",
        "C:/data.json",
        "/data.json",
        "\\\\server\\data.json",
        "evidence//data.json",
    ],
)
def test_rejects_nonportable_or_outside_root_evidence(registry, path):
    with pytest.raises(RegistryError, match="^RESULT_VALIDATION_ERROR$"):
        registry.register(**sample(evidence=[{"path": path, "sha256": "1" * 64, "bytes": 1}]))
    assert registry.list_results() == []


def test_validation_does_not_write_partial_records(registry):
    assert registry.list_results() == []
    with pytest.raises(RegistryError, match="^RESULT_VALIDATION_ERROR$"):
        registry.register(**sample(summary={"value": float("nan")}))
    with pytest.raises(RegistryError, match="^RESULT_NOT_FOUND$"):
        registry.get("0" * 64)
    assert registry.list_results() == []
