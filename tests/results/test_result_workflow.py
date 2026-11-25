import hashlib

import pytest

from services.api import result_workflow
from services.api.evidence import EvidenceBlocked, EvidenceStore
from services.results.registry import ResultRegistry


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    keys = {
        "rtrw-v1": {"domain": "rtrw", "evidence_status": "BLOCKED"},
        "sentinel-v1": {"domain": "sentinel", "evidence_status": "VERIFIED_REAL"},
    }
    fixed_catalog = {}
    for source, entry in keys.items():
        path = tmp_path / f"{source}.json"
        raw = f'{{"scope":"{source}"}}'.encode("utf-8")
        path.write_bytes(raw)
        fixed_catalog[source] = {
            **entry,
            "title": f"검토 자료 {source}",
            "summary": {"scope": source},
            "evidence": [
                {"path": path.name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
            ],
            "blockers": ["SOURCE_VERSION_PENDING"] if source == "rtrw-v1" else [],
        }
    monkeypatch.setattr(result_workflow, "catalog", lambda: fixed_catalog)
    return fixed_catalog, {
        "sources": list(reversed(fixed_catalog)),
        "store": EvidenceStore(tmp_path, tmp_path / "unused-lock.json", "0" * 64),
        "database": tmp_path / "registry.sqlite3",
        "state_root": tmp_path / "workflows",
        "workflow_id": "result-test",
    }


def test_preflight_is_read_only_and_run_registers_verifies_and_reads_back(workflow):
    _, options = workflow
    pending, identifiers = result_workflow.run_registration(**options)
    assert pending.status == "PENDING" and identifiers == {}
    assert not options["state_root"].exists() and not options["database"].exists()

    first, identifiers = result_workflow.run_registration(**options, execute=True)
    assert first.status == "SUCCEEDED"
    assert list(identifiers) == ["rtrw-v1", "sentinel-v1"]
    assert first.steps["verify-01"].evidence_sha256
    assert first.steps["register-01"].message == first.steps["lookup-01"].message
    repository = ResultRegistry(options["database"])
    stored = repository.get(identifiers["rtrw-v1"])
    assert stored["evidence_status"] == "BLOCKED" and stored["review_status"] == "PENDING"
    resumed, retried = result_workflow.run_registration(**options, execute=True)
    assert resumed.status == "SUCCEEDED" and retried == identifiers
    assert resumed.steps["verify-01"].attempts == 2
    assert resumed.steps["register-01"].attempts == 1
    assert resumed.steps["lookup-01"].attempts == 2
    assert len(repository.list_results()) == 2


def test_drifted_pin_blocks_before_creating_database(workflow):
    _, options = workflow
    (options["store"].root / "sentinel-v1.json").write_bytes(b"x")
    state, identifiers = result_workflow.run_registration(**options, execute=True)
    assert state.status == "BLOCKED" and identifiers == {}
    assert state.steps["verify-02"].blockers == ("RESULT_EVIDENCE_SIZE_DRIFT:sentinel-v1.json",)
    assert state.steps["register-01"].status == "PENDING"
    assert not options["database"].exists()


def test_payload_and_database_changes_require_new_workflow_identity(workflow):
    catalog, options = workflow
    result_workflow.run_registration(**options, execute=True)
    with pytest.raises(ValueError, match="INPUT_DRIFT_REQUIRES_NEW_WORKFLOW_ID"):
        result_workflow.run_registration(
            **{**options, "database": options["database"].with_name("other.sqlite3")}, execute=True
        )
    catalog["sentinel-v1"]["summary"] = {"changed": True}
    with pytest.raises(ValueError, match="INPUT_DRIFT_REQUIRES_NEW_WORKFLOW_ID"):
        result_workflow.run_registration(**options, execute=True)


def test_unknown_catalogue_source_fails_before_writing(workflow):
    _, options = workflow
    with pytest.raises(EvidenceBlocked, match="RESULT_SOURCE_UNKNOWN"):
        result_workflow.run_registration(**{**options, "sources": ["unknown"]}, execute=True)
    assert not options["state_root"].exists()
