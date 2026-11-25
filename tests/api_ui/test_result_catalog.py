import json
from hashlib import sha256

import pytest
from test_results_api import local_client, make_app

from services.api.evidence import EvidenceBlocked, EvidenceStore
from services.api.result_catalog import attach
from services.results.registry import ResultRegistry


def pin(tmp_path, name, document):
    raw = json.dumps(document).encode()
    (tmp_path / name).write_bytes(raw)
    return {"path": name, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def package(tmp_path):
    source = pin(tmp_path, "source.json", {"fixture": True})
    license_pin = pin(
        tmp_path,
        "rights.json",
        {"license": "CC-BY-4.0", "source_uri": "https://example.test/rights"},
    )
    layer = pin(
        tmp_path,
        "layer.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [100, -5]},
                    "properties": {"days": 8},
                }
            ],
        },
    )
    return {
        "institution": "Test Institution",
        "adapter": "test/1",
        "period": {"start": "2020-01-01", "end": "2020-12-31", "kind": "observation"},
        "spatial": {"crs": "OGC:CRS84", "bbox": [95, -11, 141, 6]},
        "sources": [
            {
                "id": "test",
                "version": "1",
                "title": "Source",
                "uri": "https://example.test/source",
                "license": "CC-BY-4.0",
                "license_evidence": license_pin,
                "raw": source,
            }
        ],
        "metrics": [
            {
                "id": "result-value",
                "label": "Test metric",
                "value": 8,
                "unit": "days",
                "source_id": "test",
            }
        ],
        "layers": [
            {
                "id": "layer",
                "title": "Test layer",
                "source_id": "test",
                "format": "GeoJSON",
                "file": layer,
                "crs": "OGC:CRS84",
                "nodata": {"kind": "not_applicable"},
                "metric_field": "days",
                "unit": "days",
            }
        ],
        "reports": [
            {
                "id": "report",
                "title": "Test report",
                "source_id": "test",
                "format": "JSON",
                "file": source,
            }
        ],
        "uncertainty": {"status": "NOT_REPORTED", "reason": "Fixture has no uncertainty estimate"},
    }


def test_catalog_same_id_links_drift_and_separate_decisions(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    repo = ResultRegistry(tmp_path / "results.sqlite3")
    store = EvidenceStore(tmp_path, tmp_path / "unused.json", "unused")
    with local_client(app) as client:
        result_id = client.post("/api/results", json={"source": "version-1"}).json()["result"]["id"]
        path = f"/api/results/{result_id}/catalog"
        assert client.get(path).json()["status"] == "CATALOG_PENDING"
        raw = package(tmp_path)
        assert attach(store, repo, result_id, raw) == attach(store, repo, result_id, raw)
        catalog = client.get(path).json()
        digest = catalog["package_sha256"]
        assert catalog["status"] == "CATALOG_READY"
        assert catalog["result_id"] == result_id
        assert catalog["package"]["metrics"][0]["value"] == 8
        assert catalog["package"]["sources"][0]["sha256"] == raw["sources"][0]["raw"]["sha256"]
        assert catalog["package"]["uncertainty"]["status"] == "NOT_REPORTED"
        for group in ("reports", "layers"):
            artifact = catalog["package"][group][0]
            response = client.get(artifact["href"])
            assert response.status_code == 200
            assert sha256(response.content).hexdigest() == artifact["sha256"]
        assert client.get(path + "/assets/missing").status_code == 404

        def decision(axis, status="APPROVED", revision=0):
            actor = axis + "-authority"
            body = pin(
                tmp_path,
                f"{axis}-{status}.json",
                {
                    "result_id": result_id,
                    "package_sha256": digest,
                    "axis": axis,
                    "decision": status,
                    "authority": actor,
                    "reference": "fixture",
                    "scope": {
                        "scientific": "INDEPENDENT_SCIENTIFIC",
                        "publication": "INSTITUTIONAL_PUBLICATION",
                    }[axis],
                },
            )
            return {
                "decision": status,
                "note": "controlled test",
                "package_sha256": digest,
                "expected_revision": revision,
                "evidence": body,
            }

        def submit(axis, body, token):
            return client.post(
                path + "/decisions/" + axis, json=body, headers={"Authorization": "Bearer " + token}
            )

        for axis in ("scientific", "publication"):
            monkeypatch.delenv(f"SDSS_CATALOG_{axis.upper()}_TOKEN", raising=False)
            monkeypatch.delenv(f"SDSS_CATALOG_{axis.upper()}_AUTHORITY", raising=False)
        scientific, publication = decision("scientific"), decision("publication")
        assert submit("scientific", scientific, "scientific-token").status_code == 503
        for axis in ("scientific", "publication"):
            monkeypatch.setenv(f"SDSS_CATALOG_{axis.upper()}_TOKEN", axis + "-token")
            monkeypatch.setenv(f"SDSS_CATALOG_{axis.upper()}_AUTHORITY", axis + "-authority")
        assert submit("scientific", scientific, "publication-token").status_code == 403
        assert submit("publication", publication, "publication-token").status_code == 409
        assert (
            submit("scientific", scientific, "scientific-token").json()["governance"]["scientific"][
                "status"
            ]
            == "APPROVED"
        )
        assert submit("publication", publication, "publication-token").json()["governance"][
            "release_eligible"
        ]
        rejected = submit(
            "scientific", decision("scientific", "REJECTED", 1), "scientific-token"
        ).json()
        assert not rejected["governance"]["release_eligible"]
        assert rejected["governance"]["publication"]["status"] == "APPROVED"
        assert (
            client.get(f"/api/results/{result_id}").json()["result"]["review_status"] == "PENDING"
        )
        (tmp_path / "layer.geojson").write_text("changed")
        assert client.get(path).status_code == 409


@pytest.mark.parametrize(
    "change, expected",
    [
        (lambda raw: raw["period"].update(start="2021-01-01"), "PACKAGE_PERIOD_ORDER_INVALID"),
        (lambda raw: raw["layers"][0].update(crs="EPSG:3857"), "PACKAGE_LAYER_CRS_MISMATCH"),
        (
            lambda raw: raw["layers"][0].update(nodata={"kind": "value", "value": 0}),
            "PACKAGE_VECTOR_NODATA_MISMATCH",
        ),
        (lambda raw: raw["metrics"][0].update(unit="invalid"), "days"),
        (lambda raw: raw["sources"][0]["raw"].update(sha256="0" * 64), "RESULT_EVIDENCE_SHA_DRIFT"),
    ],
)
def test_nonconforming_packages_fail_closed(tmp_path, monkeypatch, change, expected):
    app, _ = make_app(tmp_path, monkeypatch)
    repo = ResultRegistry(tmp_path / "results.sqlite3")
    store = EvidenceStore(tmp_path, tmp_path / "unused.json", "unused")
    with local_client(app) as client:
        result_id = client.post("/api/results", json={"source": "version-1"}).json()["result"]["id"]
        raw = package(tmp_path)
        change(raw)
        with pytest.raises((ValueError, EvidenceBlocked), match=expected):
            attach(store, repo, result_id, raw)
        assert repo.catalog_entry(result_id)["status"] == "CATALOG_PENDING"
