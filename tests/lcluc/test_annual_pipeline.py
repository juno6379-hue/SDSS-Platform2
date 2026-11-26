"""Small complete two-sensor input with independently located synthetic holdouts."""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from services.lcluc.annual import load_json, run_bundle, scan
from services.lcluc.annual_inputs import Bands, Quality
from services.lcluc.taxonomy import load_taxonomy

np = pytest.importorskip("numpy")
rasterio = pytest.importorskip("rasterio")
pytest.importorskip("sklearn")


def make_annual_fixture(folder):
    from pyproj import Transformer
    from rasterio.transform import from_origin

    folder.mkdir(parents=True)
    year = 2026
    taxonomy = load_taxonomy("esri-io-v003")
    projection = Transformer.from_crs(4326, 6933, always_xy=True)
    west, north = (int(x / 30) * 30 for x in projection.transform(106.1, -6.2))
    affine = from_origin(west, north, 30, 30)
    grid = {"driver": "GTiff", "width": 32, "height": 32, "count": 1, "crs": "EPSG:6933", "transform": affine}
    reverse = Transformer.from_crs(6933, 4326, always_xy=True)
    coords = [(west + x, north - y) for x, y in [(1, 1), (959, 1), (959, 959), (1, 959), (1, 1)]]
    (folder / "boundary.geojson").write_text(json.dumps({
        "type": "Polygon", "coordinates": [[reverse.transform(x, y) for x, y in coords]],
    }), encoding="utf-8")

    def pin(name):
        asset = (folder / name).read_bytes()
        return {"path": name, "bytes": len(asset), "sha256": sha256(asset).hexdigest()}

    def write(name, array, nodata=0):
        with rasterio.open(folder / name, "w", **grid, nodata=nodata, dtype="uint16") as dst:
            dst.write(np.asarray(array, dtype="uint16"), 1)
        return pin(name)

    def metadata(source):
        return {"source_id": source, "provider": source, "uri": f"fixture:{source}",
                "acquired_at": "2026-11-26T00:00:00Z",
                "version": "fixture-1", "license": "synthetic test data"}

    def reference(source, raster):
        return {**metadata(source), "year": year, "taxonomy_sha256": taxonomy.sha256, "raster": raster}

    expected = np.tile(np.array([1] * 16 + [2] * 16), (32, 1))
    training, independent = np.zeros_like(expected), np.zeros_like(expected)
    training[:8] = expected[:8]
    independent[24:] = expected[24:]
    bundle = {
        "schema_version": "lcluc-annual-input/1", "year": year, "region": "banten",
        "evidence": "synthetic", "taxonomy": taxonomy.id, "taxonomy_sha256": taxonomy.sha256,
        "boundary": pin("boundary.geojson"), "boundary_source": metadata("boundary-fixture"),
        "training": reference("training-team", write("train.tif", training)),
        "sensors": {},
    }
    for sensor, bands in Bands.items():
        sentinel = sensor == "sentinel-2"
        dn = np.where(expected == 1, 2700 if sentinel else 17000, 6700 if sentinel else 30000)
        quality = np.full((32, 32), 4 if sentinel else 64, dtype="uint16")
        quality[15, 15] = 9 if sentinel else (1 << 3)
        assets = {band: write(f"{sensor}-{band}.tif", dn + index) for index, band in enumerate(bands)}
        assets[Quality[sensor]] = write(f"{sensor}-quality.tif", quality, 0 if sentinel else 1)
        bundle["sensors"][sensor] = [{
            **metadata(sensor), "observed_on": f"{year}-04-02", "assets": assets,
            "scale": [0.0001 if sentinel else 0.0000275] * 6,
            "offset": [-0.1 if sentinel else -0.2] * 6,
        }]
    receipt = folder / "bundle.json"
    receipt.write_text(json.dumps(bundle), encoding="utf-8")
    run_id = sha256(receipt.read_bytes()).hexdigest()
    (folder / "protocol.txt").write_text("Synthetic 30 m holdout cells", encoding="utf-8")
    approvals = {
        "training-approval.json": {"schema_version": "lcluc-annual-training/1", "input_sha256": run_id,
                                   "approval_id": "synthetic-training", "authority": "synthetic-qa"},
        "verification.json": {
            "schema_version": "lcluc-annual-verification/1", "input_sha256": run_id,
            "weak_reference": reference("weak-map", write("weak.tif", expected)),
            "independent_reference": reference("holdout-team", write("holdout.tif", independent)),
            "independent_protocol": pin("protocol.txt"), "approval_id": "synthetic-holdout",
            "authority": "synthetic-qa",
        },
    }
    return receipt, run_id, approvals


def publish(folder, name, approvals):
    (folder / name).write_text(json.dumps(approvals[name]), encoding="utf-8")


def test_arrival_resume_and_disjoint_evaluation(tmp_path):
    inbox = tmp_path / "incoming"
    bundle, run_id, approvals = make_annual_fixture(inbox / "banten/2026/r1")
    root = tmp_path / "output"
    status = root / run_id / "status.json"
    source = bundle.parent / "landsat-SR_B7.tif"
    pending = source.rename(source.with_suffix(".pending"))
    scan(inbox, root, allow_synthetic=True)
    assert load_json(status)["state"] == "WAITING_INPUT"
    pending.rename(source)
    scan(inbox, root, allow_synthetic=True)
    assert load_json(status)["state"] == "WAITING_TRAINING_APPROVAL"
    publish(bundle.parent, "training-approval.json", approvals)
    scan(inbox, root, allow_synthetic=True)
    result = load_json(status)
    assert result["state"] == "WAITING_INDEPENDENT_REFERENCE"
    assert result["quality"]["sentinel-2"]["clear_pixels"] == 1023
    assert result["quality"]["landsat"]["clear_pixels"] == 1023
    assert result["same_year_sensor_agreement"]["landsat_vs_sentinel-2"]["overall_map_agreement"] == 1
    model = status.parent / "landsat-candidate.npz"
    mtime = model.stat().st_mtime_ns
    publish(bundle.parent, "verification.json", approvals)
    scan(inbox, root, allow_synthetic=True)
    result = load_json(status)
    assert result["state"] == "TESTED_SYNTHETIC"
    assert result["independent_accuracy"] is None
    assert result["synthetic_holdout"]["metrics"]["landsat"]["eligible_pixels"] == 256
    assert result["weak_reference_agreement"]["metrics"]["sentinel-2"]["overall_reference_agreement"] == 1
    assert model.stat().st_mtime_ns == mtime
    scan(inbox, root, allow_synthetic=True)
    assert load_json(status) == result
    assert model.stat().st_mtime_ns == mtime


def test_disabled_synthetic_intake(tmp_path):
    bundle, run_id, _ = make_annual_fixture(tmp_path / "fixture")
    run_bundle(bundle, tmp_path)
    result = load_json(tmp_path / run_id / "status.json")
    assert result["state"] == "BLOCKED"
    assert result["blocker"] == "SYNTHETIC_INTAKE_DISABLED"


def test_cross_year_and_independent_overlap_are_rejected(tmp_path):
    bundle, run_id, approvals = make_annual_fixture(tmp_path / "fixture")
    publish(bundle.parent, "training-approval.json", approvals)
    verification = approvals["verification.json"]
    verification["weak_reference"]["year"] = 2021
    verification["independent_reference"]["raster"] = {
        **verification["weak_reference"]["raster"]
    }
    verification["weak_reference"] = None
    publish(bundle.parent, "verification.json", approvals)
    run_bundle(bundle, tmp_path, allow_synthetic=True)
    status = tmp_path / run_id / "status.json"
    assert "INDEPENDENT_SAMPLES_OVERLAP_TRAINING_BUFFER" in load_json(status)["blocker"]
    verification["weak_reference"] = {**verification["independent_reference"], "year": 2021}
    verification["independent_reference"] = None
    publish(bundle.parent, "verification.json", approvals)
    run_bundle(bundle, tmp_path, allow_synthetic=True)
    assert "REFERENCE_YEAR_OR_TAXONOMY_MISMATCH" in load_json(status)["blocker"]


if __name__ == "__main__":
    import sys

    base = Path(sys.argv[1])
    receipt, _, approvals = make_annual_fixture(base / "annual-lcluc/banten/2026/r1")
    staged = base / "staged"
    staged.mkdir()
    for name in approvals:
        publish(staged, name, approvals)
    (receipt.parent / "landsat-SR_B7.tif").rename(staged / "landsat-SR_B7.tif")
