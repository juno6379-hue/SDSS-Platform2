import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.evidence import EvidenceStore
from services.api.jobs_api import mount_jobs
from services.jobs.contracts import Config, canonical
from services.jobs.providers import HttpProvider
from services.jobs.store import JobStore
from services.jobs.worker import Worker
from services.results.registry import ResultRegistry

MODEL = {"name": "drought", "version": "v1.2", "artifact_sha256": "a" * 64}
OPERATOR = {"Authorization": "Bearer operator-test"}


def write_pin(root, name, value):
    data = canonical(value)
    (root / name).write_bytes(data)
    return {"path": name, "bytes": len(data), "sha256": sha256(data).hexdigest()}


class FixtureProvider:
    raw = b'{"verified":true}'
    geojson = b'{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[104,0]},"properties":{"risk":42}}]}'

    def __init__(self):
        self.remote = {}
        self.submits = []
        self.polls = []
        self.calls = []
        self.errors = 0
        self.bad_asset = False
        self.wrong_release = False

    def respond(self, request):
        self.calls.append(request)
        assert request.url.host == "toolbox.institution.invalid"
        assert request.headers["Authorization"] == "Bearer provider-test"
        path = request.url.path.replace("/toolbox/v1", "")
        if path == "/jobs":
            content = json.loads(request.content)
            job_id = content["job_id"]
            assert request.headers["Idempotency-Key"] == job_id
            assert content["model"] == MODEL
            self.submits.append(job_id)
            self.remote.setdefault(job_id, "RUNNING")
            if self.errors:
                self.errors -= 1
                raise httpx.ReadTimeout("synthetic response timeout after receipt", request=request)
            return self.status(job_id)
        job_id = path.split("/")[2]
        if path.endswith("/cancel"):
            assert request.headers["Idempotency-Key"] == job_id + "-cancel"
            self.remote[job_id] = "CANCELLED"
            return self.status(job_id)
        if path.endswith("/result"):
            return httpx.Response(200, json=self.output(job_id))
        if path.endswith("/assets/report"):
            return httpx.Response(200, content=b'{"altered":true}' if self.bad_asset else self.raw)
        if path.endswith("/assets/layer"):
            return httpx.Response(200, content=self.geojson)
        self.polls.append(job_id)
        return self.status(job_id)

    def status(self, job_id):
        state = self.remote[job_id]
        return httpx.Response(
            200,
            json={
                "job_id": job_id,
                "state": state,
                "progress": 100 if state == "SUCCEEDED" else 10,
            },
        )

    def output(self, job_id):
        raw = {"path": "raw.json", "bytes": len(self.raw), "sha256": sha256(self.raw).hexdigest()}
        layer = {
            "path": "extent.geojson",
            "bytes": len(self.geojson),
            "sha256": sha256(self.geojson).hexdigest(),
        }
        model = {**MODEL, "version": "other"} if self.wrong_release else MODEL
        return {
            "job_id": job_id,
            "model": model,
            "assets": [{"id": "report", "pin": raw}, {"id": "layer", "pin": layer}],
            "package": {
                "institution": "Fixture Institute",
                "adapter": "toolbox-fixture/1",
                "spatial": {"crs": "OGC:CRS84", "bbox": [90, -10, 110, 10]},
                "period": {"start": "2024-01-01", "end": "2024-12-31", "kind": "observation"},
                "metrics": [
                    {
                        "id": "risk",
                        "label": "Risk",
                        "value": 42,
                        "unit": "percent",
                        "source_id": "provider",
                    }
                ],
                "layers": [
                    {
                        "id": "extent",
                        "title": "Extent",
                        "file": layer,
                        "source_id": "provider",
                        "format": "GeoJSON",
                        "crs": "OGC:CRS84",
                        "nodata": {"kind": "not_applicable"},
                        "metric_field": "risk",
                        "unit": "percent",
                    }
                ],
                "sources": [
                    {
                        "id": "provider",
                        "title": "Fixture",
                        "uri": "https://toolbox.institution.invalid/output",
                        "version": "1",
                        "license": "UNVERIFIED",
                        "raw": raw,
                    }
                ],
                "reports": [
                    {
                        "id": "report",
                        "title": "Fixture report",
                        "file": raw,
                        "source_id": "provider",
                        "format": "JSON",
                    }
                ],
                "uncertainty": {"status": "NOT_REPORTED", "reason": "Synthetic contract"},
            },
        }


@pytest.fixture
def job_system(tmp_path, monkeypatch):
    pytest.importorskip("pyproj")
    pytest.importorskip("shapely")
    monkeypatch.setenv("SDSS_PROVIDER_TEST_TOKEN", "provider-test")
    monkeypatch.setenv("SDSS_JOBS_OPERATOR_TOKEN", "operator-test")
    monkeypatch.setenv("SDSS_JOBS_STATE_DIR", "queue")
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("SDSS_JOBS_CONFIG", str(config_path))
    documents = {
        "schema_version": "sdss-institution-jobs/1",
        "providers": {
            "toolbox": {
                "kind": "institution_toolbox",
                "base_url": "https://toolbox.institution.invalid/toolbox/v1",
                "credential_env": "SDSS_PROVIDER_TEST_TOKEN",
                "operations": ["summary"],
            }
        },
        "approvals": {},
    }
    for key, expiry in (("scoped", 2), ("scoped-second", 2), ("expired", -2)):
        documents["approvals"][key] = write_pin(
            tmp_path,
            f"{key}.json",
            {
                "schema_version": "sdss-job-approval/1",
                "approval_id": key,
                "provider": "toolbox",
                "operation": "summary",
                "model": MODEL,
                "approved_by": "fixture",
                "eligible_until": (datetime.now(UTC) + timedelta(hours=expiry)).isoformat(),
                "parameters": {"dataset_id": "immutable-example"},
            },
        )
    config_path.write_bytes(canonical(documents))
    store = EvidenceStore(tmp_path, tmp_path / "unused", "unused")
    registry = ResultRegistry(tmp_path / "results.sqlite3")
    app = FastAPI()
    mount_jobs(app, store)
    queue = JobStore(tmp_path / "queue")
    upstream = FixtureProvider()
    with httpx.Client(transport=httpx.MockTransport(upstream.respond)) as fake_http:

        def worker(model_selector=None):
            return Worker(
                queue,
                store,
                registry,
                lambda: Config.load(config_path),
                provider_factory=lambda spec: HttpProvider(spec, client=fake_http),
                model_selector=model_selector,
            )

        with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 55443)) as client:
            yield SimpleNamespace(
                client=client,
                worker=worker,
                queue=queue,
                upstream=upstream,
                registry=registry,
                config=config_path,
                root=tmp_path,
            )


def submit(system, key="scoped"):
    response = system.client.post("/api/jobs", headers=OPERATOR, json={"approval_id": key})
    assert response.status_code == 202
    return response.json()["job"]["id"]


def detail(system, job_id):
    return system.client.get(f"/api/jobs/{job_id}").json()


def test_authorized_worker_resumes_and_registers_catalog(job_system):
    s = job_system
    assert s.client.get("/api/jobs").json()["status"] == "READY"
    assert s.client.post("/api/jobs", json={"approval_id": "scoped"}).status_code == 403
    assert (
        s.client.post("/api/jobs", headers=OPERATOR, json={"approval_id": "expired"}).status_code
        == 409
    )
    assert (
        s.client.post(
            "/api/jobs",
            headers=OPERATOR,
            json={"approval_id": "scoped", "url": "https://example.invalid"},
        ).status_code
        == 422
    )
    assert s.client.get("/api/jobs", headers={"Host": "untrusted.invalid"}).status_code == 403
    assert s.client.get("/api/jobs/approvals").json()["approvals"][0]["model"] == MODEL
    job_id = submit(s)
    assert submit(s) == job_id
    assert detail(s, job_id)["job"]["state"] == "QUEUED"
    s.upstream.errors = 1
    worker = s.worker()
    assert worker.tick() == 1
    state_file = s.queue.directory / "workflows" / job_id / "state.json"
    (state_file.parent / ".execution.lock").touch()
    with s.queue.worker_lock():
        assert s.worker().tick() == 0
    assert s.worker().tick() == 1
    assert s.upstream.submits == [job_id, job_id]
    assert len(s.upstream.remote) == 1
    assert detail(s, job_id)["job"]["progress"] == 10
    assert s.worker().tick() == 1
    assert len(s.upstream.submits) == 2
    s.upstream.remote[job_id] = "SUCCEEDED"
    assert s.worker().tick() == 1
    complete = detail(s, job_id)
    events = complete["events"]
    assert [events[0]["state"], events[-2]["state"], events[-1]["state"]] == [
        "QUEUED",
        "FINALIZING",
        "SUCCEEDED",
    ]
    assert any(event["blocker"] == "PROVIDER_NETWORK_UNAVAILABLE" for event in events)
    job = complete["job"]
    catalog = s.registry.catalog_entry(job["result_id"])
    assert catalog["package_sha256"] == job["package_sha256"]
    assert catalog["package"]["metrics"][0]["value"] == 42
    assert not catalog["governance"]["release_eligible"]
    assert json.loads(state_file.read_bytes())["status"] == "SUCCEEDED"
    assert s.worker().tick() == 0


def test_cancel_before_and_after_provider_submission(job_system):
    s = job_system
    local = submit(s)

    def cancel(key):
        return s.client.post(f"/api/jobs/{key}/cancel", headers=OPERATOR).json()["job"]

    assert cancel(local)["state"] == "CANCELLED"
    assert s.worker().tick() == 0
    assert s.upstream.calls == []
    remote = submit(s, "scoped-second")
    s.worker().tick()
    assert s.client.post(f"/api/jobs/{remote}/cancel").status_code == 403
    assert cancel(remote)["state"] == "CANCELLING"
    s.worker().tick()
    assert cancel(remote)["state"] == "CANCELLED"
    assert not detail(s, remote)["job"]["result_id"]


@pytest.mark.parametrize(
    ("error", "blocker"),
    [
        ("bad_asset", "JOB_OUTPUT_ASSET_HASH_MISMATCH"),
        ("wrong_release", "JOB_OUTPUT_MODEL_PIN_MISMATCH"),
    ],
)
def test_bad_provider_result_never_registered(job_system, error, blocker):
    s = job_system
    job_id = submit(s)
    s.worker().tick()
    s.upstream.remote[job_id] = "SUCCEEDED"
    setattr(s.upstream, error, True)
    s.worker().tick()
    job = detail(s, job_id)["job"]
    assert job["state"] == "FAILED" and job["blockers"] == [blocker]
    assert not job["result_id"]
    assert s.registry.list_results() == []


def test_project_release_requires_active_matching_version(job_system):
    s = job_system
    config = json.loads(s.config.read_bytes())
    config["providers"]["toolbox"]["kind"] = "project_model"
    s.config.write_bytes(canonical(config))
    blocked = submit(s)
    binding = {
        "model": {**MODEL, "version": "v2"},
        "activation_revision": 3,
        "manifest_sha256": "b" * 64,
    }
    s.worker(lambda name: binding).tick()
    assert detail(s, blocked)["job"]["blockers"] == ["ACTIVE_MODEL_VERSION_PIN_MISMATCH"]
    assert s.upstream.calls == []
    allowed = submit(s, "scoped-second")
    binding["model"] = MODEL
    s.worker(lambda name: binding).tick()
    s.upstream.remote[allowed] = "SUCCEEDED"
    s.worker().tick()
    job = detail(s, allowed)["job"]
    assert job["state"] == "SUCCEEDED"
    receipt = s.registry.get(job["result_id"])["evidence"][0]
    evidence = json.loads((s.root / receipt["path"]).read_bytes())
    release = evidence["model_release"]
    assert json.loads((s.root / release["path"]).read_bytes()) == binding


def test_empty_config_disables_deployment_without_initializing_queue(tmp_path, monkeypatch):
    monkeypatch.delenv("SDSS_JOBS_CONFIG", raising=False)
    monkeypatch.delenv("SDSS_JOBS_STATE_DIR", raising=False)
    app = FastAPI()
    mount_jobs(app, EvidenceStore(tmp_path, tmp_path / "unused", "unused"))
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 80)) as client:
        assert client.get("/api/jobs").json() == {
            "status": "BLOCKED",
            "blockers": ["JOB_PROVIDER_CONFIG_NOT_SET"],
            "jobs": [],
        }
        assert not (tmp_path / "data").exists()


def test_approval_drift_blocks_before_network(job_system):
    s = job_system
    job_id = submit(s)
    (s.root / "scoped.json").write_bytes(b"{}")
    s.worker().tick()
    job = detail(s, job_id)["job"]
    assert job["state"] == "FAILED"
    assert job["blockers"] == ["JOB_APPROVAL_EVIDENCE_DRIFT"]
    assert not s.upstream.calls


def test_completed_workflow_replays_queue_commit_without_provider_calls(job_system, monkeypatch):
    s = job_system
    job_id = submit(s)
    s.worker().tick()
    s.upstream.remote[job_id] = "SUCCEEDED"
    original = s.queue.update

    def simulate_exit(key, **kwargs):
        if kwargs["state"] == "SUCCEEDED":
            raise OSError("temporary process stop after durable workflow commit")
        return original(key, **kwargs)

    with monkeypatch.context() as checkpoint:
        checkpoint.setattr(s.queue, "update", simulate_exit)
        with pytest.raises(OSError, match="temporary process stop"):
            s.worker().tick()
    assert detail(s, job_id)["job"]["state"] == "FINALIZING"
    assert len(s.registry.list_results()) == 1
    total_provider_calls = len(s.upstream.calls)
    assert s.worker().tick() == 1
    assert detail(s, job_id)["job"]["state"] == "SUCCEEDED"
    assert len(s.upstream.calls) == total_provider_calls
    assert len(s.registry.list_results()) == 1
