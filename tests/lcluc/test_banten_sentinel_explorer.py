"""Regression checks for the optical composite and its separate reference cross-tab."""

from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

np = pytest.importorskip("numpy")
rasterio = pytest.importorskip("rasterio")
pytest.importorskip("shapely")

from services.lcluc import banten_sentinel_statistics as statistics  # noqa: E402
from services.lcluc.banten_esri_preview import WEB  # noqa: E402
from services.lcluc.banten_sentinel_explorer import BANDS, spectral_block  # noqa: E402
from services.lcluc.banten_sentinel_statistics import transition_counts  # noqa: E402


def test_clear_replacement_keeps_all_bands_from_one_observation():
    def scene(scl, samples):
        arrays = {"scl": np.asarray([scl], dtype="uint8")}
        arrays.update({band: np.full((1, 4), value, dtype="uint16")
                       for band, value in zip(BANDS, samples, strict=True)})
        sources = {name: SimpleNamespace(read=lambda index, window, v=data: v)
                   for name, data in arrays.items()}
        return {}, sources, np.full(6, 0.01, dtype="float32"), np.zeros(6, dtype="float32")

    first = scene([9, 4, 3, 4], [8, 15, 12, 30, 25, 20])
    second = scene([4, 5, 3, 5], [10, 20, 15, 40, 30, 10])
    data = spectral_block([first, second], None, np.array([[True, True, True, False]]))
    np.testing.assert_allclose(data[:6, 0, 0], [0.10, 0.20, 0.15, 0.40, 0.30, 0.10])
    np.testing.assert_allclose(data[:6, 0, 1], [0.08, 0.15, 0.12, 0.30, 0.25, 0.20])
    np.testing.assert_allclose(data[6:9, 0, 0], [(0.4 - 0.15) / 0.55, -1 / 3, 0.6], rtol=1e-6)
    assert data[9, 0, :3].tolist() == [0, 0, 2]
    assert np.isnan(data[:9, 0, 2]).all() and np.isnan(data[:, 0, 3]).all()


def test_transition_excludes_clouds_and_nodata_from_both_years():
    left = np.array([1, 2, 10, 0, 2, 2], dtype="uint8")
    right = np.array([2, 2, 1, 7, 10, 0], dtype="uint8")
    matrix = transition_counts(left, right)
    assert matrix.shape == (8, 8)
    assert matrix.sum() == 2 and matrix.trace() == 1 and matrix[0, 1] == 1


def test_transition_preview_keeps_direction_and_clips_to_rectangle(tmp_path, monkeypatch):
    transform = rasterio.transform.from_bounds(*WEB.transform(106, -7), *WEB.transform(108, -5), 2, 2)
    grid = {"crs": "EPSG:3857", "transform": transform, "width": 2, "height": 2}
    monkeypatch.setattr(statistics, "display_grid", lambda root: grid)
    sources = [tmp_path / "earlier.tif", tmp_path / "later.tif"]
    for path, pixels in zip(sources, ([[2, 7], [2, 0]], [[7, 2], [7, 7]]), strict=True):
        with rasterio.open(path, "w", driver="GTiff", **grid, count=1, dtype="uint8", nodata=0) as output:
            output.write(np.array(pixels, dtype="uint8"), 1)
    result = statistics.transition_preview(tmp_path, *sources, "a", "b", 2, 7, (106, -6, 107, -5))
    with Image.open(BytesIO(result)) as image:
        assert np.array(image.getchannel("A")).tolist() == [[220, 0], [0, 0]]
