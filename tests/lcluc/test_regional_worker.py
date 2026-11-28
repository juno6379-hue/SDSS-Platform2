"""Regional intake gates that are independent of retained real imagery."""

import json
from hashlib import sha256

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.evidence import EvidenceStore
from services.api.westjava_validation import mount_westjava_validation
from services.lcluc import regional_worker
from services.lcluc.annual_inputs import REGIONAL_OUTPUT


def test_comparison_requires_matched_support_and_records_regression():
    def trial(agreement, sha="a", pixels=10):
        return {"evaluations": [{
            "window": "holdout", "split": "test", "input_mosaic_sha256": sha,
            "comparison_pixels": pixels, "weak_reference_metrics": {"overall_accuracy": agreement},
        }]}

    comparison = regional_worker.compare_models(trial(0.2), trial(0.4))
    assert comparison == {
        "status": "EVALUATED_WEAK_REFERENCE", "pixels": 10, "incumbent": 0.4,
        "candidate": 0.2, "improved": False,
    }
    assert regional_worker.compare_models(trial(0.6, "b"), trial(0.4))["status"] == "BLOCKED"
    assert regional_worker.compare_models(trial(0.6, pixels=11), trial(0.4))["status"] == "BLOCKED"


def test_receipt_lock_idempotence_output_pin_and_read_api(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    output = tmp_path / REGIONAL_OUTPUT
    raw = b'{"year":2023}'
    key = sha256(raw).hexdigest()
    job = inbox / f"{key}.json"
    job.write_bytes(raw)
    calls = []

    class Sealed:
        region, year = "west_java", 2023
        collector_receipts = ()

    def execute(receipt, roots, destination):
        calls.append(receipt)
        (destination / "mosaic.json").write_text("{}", encoding="utf-8")
        return {"mosaics": [], "models": {}, "comparison": None}

    monkeypatch.setattr(regional_worker.Receipt, "model_validate_json", lambda data: Sealed())
    monkeypatch.setattr(regional_worker, "execute", execute)
    regional_worker.scan(inbox, output, {})
    status = output / key / "status.json"
    first = status.read_bytes()
    regional_worker.scan(inbox, output, {})
    assert len(calls) == 1 and status.read_bytes() == first
    app = FastAPI()
    mount_westjava_validation(app, EvidenceStore(tmp_path, tmp_path / "lock", ""))
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 1234)) as client:
        run, = client.get("/api/lcluc/westjava-intake").json()["runs"]
    assert run["run_id"] == key and run["production_release"] == "BLOCKED"
    assert "artifacts" not in run

    with pytest.raises(ValueError, match="REGIONAL_RECEIPT_FILENAME_PIN_MISMATCH"):
        altered = inbox / "renamed.json"
        altered.write_bytes(raw)
        regional_worker.run(altered, output, {})
    (output / key / "mosaic.json").write_bytes(b"[]")
    regional_worker.scan(inbox, output, {})
    assert json.loads((output / "worker.json").read_bytes())["failures"][key] == "ASSET_PIN_MISMATCH"
