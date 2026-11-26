import json

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from services.api.app import create_app
from services.api.evidence import EvidenceStore
from services.api.lcluc_run import Pair, file_pin, register_pair
from services.lcluc import banten_esri_audit, banten_reports
from services.lcluc.taxonomy import load_taxonomy
from services.results.registry import ResultRegistry


def test_banten_analysis_reports_drift_without_overwriting_verified_totals(tmp_path, monkeypatch):
    pins = [{"sha256": "a" * 64}, {"sha256": "b" * 64}]
    stored = {"common_valid_area_ha": 100.0, "changed_area_ha": 4.0, "transition_matrix_ha": [[96.0, 4.0]]}
    rerun = {"common_valid_area_ha": 100.0, "changed_area_ha": 4.03, "transition_matrix_ha": [[95.97, 4.03]]}
    monkeypatch.setattr(banten_esri_audit, "statistics", lambda years: rerun)
    monkeypatch.setattr(banten_reports, "comparison", lambda root, start, end, source=None: (source or stored, pins))
    store = EvidenceStore(tmp_path, tmp_path / "unused", "unused")
    app = create_app(store, result_registry=ResultRegistry(tmp_path / "results.sqlite3"))
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 55001))
    response = client.post("/api/lcluc/banten-province-analysis", json={"from_year": 2020, "to_year": 2025})
    assert response.status_code == 200
    assert response.json() == {**stored, "recalculation": {"status": "DIFFERS_FROM_PUBLISHED", **rerun}}
    assert "recalculation" not in stored


def fixture_pair(root):
    taxonomy = load_taxonomy()
    store = EvidenceStore(root, root / "not-needed.json", "")
    profile = dict(
        driver="GTiff",
        width=3,
        height=2,
        count=1,
        dtype="uint16",
        crs="EPSG:6933",
        transform=from_origin(0, 200, 100, 100),
        nodata=65535,
    )
    frames = []
    for year, rows in (
        (2020, [[2001, 2001, 2012], [2001, 2500, 65535]]),
        (2025, [[2012, 2001, 2012], [2001, 2012, 2001]]),
    ):
        path = root / f"source-{year}.tif"
        date = f"{year}-12-31"
        with rasterio.open(path, "w", **profile) as target:
            target.write(np.asarray(rows, dtype=np.uint16), 1)
            target.update_tags(
                observed_on=date,
                taxonomy_sha256=taxonomy.sha256,
                source_kind="synthetic_fixture",
                dataset_id=f"fixture-{year}",
                version="demo-1",
            )
        frames.append(
            {
                "raster": file_pin(store, path),
                "observed_on": date,
                "dataset_id": f"fixture-{year}",
                "version": "demo-1",
                "uri": "https://example.invalid/fixture",
            }
        )
    zone = root / "example-boundary.geojson"
    zone.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "test-zone",
                        "properties": {"id": "test-zone", "name": "시험 구역"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = root / "pair.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "sdss-lcluc-pair/1",
                "region": "banten",
                "title": "합성 시험 · LCLUC 2020~2025",
                "institution": "SDSS synthetic test",
                "taxonomy_id": "klhk-23",
                "taxonomy_sha256": taxonomy.sha256,
                "source_kind": "synthetic_fixture",
                "license": "UNVERIFIED",
                "earlier": frames[0],
                "later": frames[1],
                "zones": {"file": file_pin(store, zone), "version": "demo-1"},
            }
        ),
        encoding="utf-8",
    )
    return store, ResultRegistry(root / "results.sqlite3"), file_pin(store, manifest)


def test_exact_year_pair_and_catalog_output(tmp_path):
    store, repo, pin = fixture_pair(tmp_path)
    with pytest.raises(ValueError, match="EXPLICIT_OPT_IN"):
        register_pair(store, repo, pin)
    catalog = register_pair(store, repo, pin, allow_fixture=True)
    assert register_pair(store, repo, pin, allow_fixture=True) == catalog
    key = catalog["result_id"]
    assert catalog["status"] == "CATALOG_READY"
    assert not catalog["governance"]["release_eligible"]
    assert (
        catalog["package"]["sources"][0]["raw"]["sha256"]
        != catalog["package"]["sources"][1]["raw"]["sha256"]
    )
    with TestClient(
        create_app(store, result_registry=repo),
        base_url="http://localhost",
        client=("127.0.0.1", 49000),
    ) as client:
        assert len(client.get("/api/lcluc/taxonomy").json()["classes"]) == 23
        missing = client.get(
            "/api/lcluc/selection?region=banten&from_year=2023&to_year=2025"
        ).json()
        assert missing == {
            "status": "BLOCKED",
            "blockers": ["EXACT_LCLUC_YEAR_PAIR_NOT_AVAILABLE"],
            "cases": [],
        }
        chosen = client.get("/api/lcluc/selection?region=banten&from_year=2020&to_year=2025").json()
        assert chosen["cases"][0]["id"] == key
        assert chosen["cases"][0]["evidence_status"] == "TESTED_SYNTHETIC"
        response = client.get(f"/api/lcluc/cases/{key}")
        assert response.status_code == 200, response.text
        detail = response.json()
        assert detail["report"]["coverage"]["common_valid_area_ha"] == 4
        assert detail["report"]["major_changes"]["changed_area_ha"] == 1
        assert detail["report"]["major_changes"]["change_rate_pct"] == 25
        assert detail["report"]["hotspot_count"] == 1
        assert len(detail["report"]["zones"]) == 1
        assert client.get(detail["previews"]["earlier-preview"]).content.startswith(b"\x89PNG")
        for asset in detail["assets"]:
            assert client.get(asset["href"]).status_code == 200
        common = client.get(f"/api/results/{key}/catalog").json()
        assert common["result_id"] == key
        assert common["package_sha256"] == detail["package_sha256"]
        assert len(common["package"]["reports"]) == 2
        stored = repo.get(key)["summary"]["assets"]["earlier-preview"]
        store.safe_path(stored["path"]).write_bytes(b"tampered")
        assert client.get(detail["previews"]["earlier-preview"]).status_code == 409


def test_pair_rejects_identical_original_hash(tmp_path):
    store, _, pin = fixture_pair(tmp_path)
    value = json.loads(store.safe_path(pin["path"]).read_bytes())
    value["later"]["raster"] = value["earlier"]["raster"]
    with pytest.raises(ValueError, match="SAME_SOURCE_BYTES_FOR_DIFFERENT_YEARS"):
        Pair.model_validate(value)


def test_late_worldcover_v200_receipt_cannot_make_a_new_year(tmp_path):
    from services.api.lcluc_run import validate_source_years

    store, _, manifest_pin = fixture_pair(tmp_path)
    value = json.loads(store.safe_path(manifest_pin["path"]).read_bytes())
    value["source_kind"] = "research_reference"
    value["license"] = "CC-BY-4.0"
    rights = tmp_path / "rights.json"
    rights.write_text(
        json.dumps({"source_uri": "https://example.invalid/research", "license": value["license"]}),
        encoding="utf-8",
    )
    value["license_evidence"] = file_pin(store, rights)
    for key, product in (("earlier", "v100"), ("later", "v200")):
        frame = value[key]
        frame["dataset_id"] = "ESA WorldCover"
        frame["version"] = product
        receipt = tmp_path / f"{key}-receipt.json"
        receipt.write_text(
            json.dumps(
                {
                    "schema_version": "sdss-lcluc-source/1",
                    "observed_on": frame["observed_on"],
                    "dataset_id": frame["dataset_id"],
                    "version": product,
                    "source_uri": frame["uri"],
                    "sha256": frame["raster"]["sha256"],
                    "source_kind": value["source_kind"],
                    "license": value["license"],
                }
            ),
            encoding="utf-8",
        )
        frame["source_receipt"] = file_pin(store, receipt)
    with pytest.raises(ValueError, match="LCLUC_WORLDCOVER_SOURCE_YEAR_MISMATCH"):
        validate_source_years(store, Pair.model_validate(value))
