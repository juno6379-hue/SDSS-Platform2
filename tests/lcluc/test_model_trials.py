import json
from hashlib import sha256
from types import SimpleNamespace

import pytest

np = pytest.importorskip("numpy")

from services.lcluc.specialists import FOLDER, SpecialistIntake, integrate, merge  # noqa: E402


def test_specialist_precedence_protects_no_data_and_audits_conflicts():
    base = np.array([[4, 5, 7, 0]], dtype="uint16")
    mask = np.ones(base.shape, dtype="uint8")
    result, rows, overlaps = merge(base, [(131, mask), (140, mask)], 0)
    assert result.tolist() == [[131, 131, 7, 0]]
    assert [row["pixels"] for row in rows] == [2, 0]
    assert overlaps == 2


def test_specialist_intake_rejects_label_from_another_year():
    fingerprint = "a" * 64
    pin = {"path": "asset.tif", "bytes": 1, "sha256": fingerprint}
    layer = {"source_id": "source", "provider": "provider", "uri": "https://example.org/",
             "version": "1", "license": "reviewed", "acquired_at": "2026-01-01T00:00:00Z",
             "class_code": 140, "year": 2020, "label_year": 2021, "mask": pin,
             "training_labels": pin, "model_sha256": fingerprint}
    with pytest.raises(ValueError, match="SPECIALIST_LAYER_CLASS_OR_YEAR_INVALID"):
        SpecialistIntake(year=2020, base_sha256=fingerprint, approval_id="review", layers=[layer])


def test_hierarchy_writes_downloadable_aligned_raster_without_overwriting_candidate(tmp_path):
    rio = pytest.importorskip("rasterio")
    folder = tmp_path / FOLDER / "2020"
    folder.mkdir(parents=True)
    grid = {"driver": "GTiff", "width": 4, "height": 3, "count": 1, "dtype": "uint16",
            "crs": "EPSG:3857", "transform": rio.transform.from_origin(100, 200, 30, 30)}
    base = np.full((3, 4), 5, dtype="uint16")
    base[0, 0] = 0
    base_path = tmp_path / "base.tif"
    mask = folder / "rice.tif"
    with rio.open(base_path, "w", **grid, nodata=0) as output:
        output.write(base, 1)
    with rio.open(mask, "w", **grid, nodata=255) as output:
        output.write(np.ones(base.shape, dtype="uint16"), 1)
    fingerprint = sha256(base_path.read_bytes()).hexdigest()
    pin = {"path": mask.name, "bytes": mask.stat().st_size, "sha256": sha256(mask.read_bytes()).hexdigest()}
    layer = {"source_id": "rice-fixture", "provider": "fixture", "uri": "https://example.org/", "version": "1",
             "license": "fixture", "acquired_at": "2026-01-01T00:00:00Z", "class_code": 140, "year": 2020,
             "label_year": 2020, "mask": pin, "training_labels": pin, "model_sha256": fingerprint}
    (folder / "integration.json").write_text(json.dumps({"year": 2020, "base_sha256": fingerprint,
                                                        "approval_id": "fixture", "layers": [layer]}), encoding="utf-8")
    store = SimpleNamespace(root=tmp_path, safe_path=lambda name: tmp_path / name)
    report = integrate(store, {"year": 2020, "classification": {"sha256": fingerprint}}, base_path)
    assert sha256(base_path.read_bytes()).hexdigest() == fingerprint
    asset = tmp_path / report["asset"]["path"]
    with rio.open(asset) as output:
        assert output.transform == grid["transform"]
        assert (output.read(1) == 140).sum() == 11
        assert output.read(1)[0, 0] == 0


def test_siamese_swapping_dates_preserves_binary_result():
    torch = pytest.importorskip("torch")
    from services.lcluc.siamese import network

    model = network(torch).eval()
    a, b = torch.rand(1, 6, 16, 16), torch.rand(1, 6, 16, 16)
    with torch.inference_mode():
        first = model(torch.cat((a, b), dim=1))
        last = model(torch.cat((b, a), dim=1))
    assert first.shape == (1, 2, 16, 16)
    torch.testing.assert_close(first, last)
