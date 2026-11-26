import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("rasterio")
pytest.importorskip("shapely")

from services.lcluc.banten_landsat_explorer import (  # noqa: E402
    PROFILES,
    composite,
    index_values,
    normalize,
    quality_mask,
    validate_band_metadata,
)


def test_landsat_sensor_mapping_and_quality_bits():
    assert PROFILES["LT04"] == PROFILES["LT05"] == PROFILES["LE07"] == (1, 2, 3, 4, 5, 7)
    assert PROFILES["LC08"] == PROFILES["LC09"] == (2, 3, 4, 5, 6, 7)
    calibration = [{"scale": 0.0000275, "offset": -0.2}]
    validate_band_metadata("LE07", "red", "LE07_SR_B3.TIF", calibration)
    with pytest.raises(ValueError, match="LANDSAT_RADIOMETRY_OR_BAND_MISMATCH"):
        validate_band_metadata("LC09", "red", "LC09_SR_B3.TIF", calibration)
    qa = np.array([64, 4, 8, 16, 32, 1, 64], dtype="uint16")
    saturation = np.array([0, 0, 0, 0, 0, 0, 2], dtype="uint16")
    assert quality_mask("LC08", qa, saturation).tolist() == [True, False, False, False, False, False, False]
    assert quality_mask("LE07", qa, saturation).tolist() == [True, True, False, False, False, False, False]


def test_landsat_composite_counts_clear_observations_and_keeps_no_data():
    pixels = np.zeros((6, 1, 3), dtype="uint16")
    pixels[:, :, :2] = 10000
    clear = np.array([[64, 64, 0]], dtype="uint16")
    cloud = np.array([[64, 8, 0]], dtype="uint16")
    polygon = np.ones((1, 3), dtype=bool)
    before = normalize("LT05", pixels, clear, polygon)
    after = normalize("LC08", pixels * 2, cloud, polygon)
    result = composite([before, after])
    assert result[6].tolist() == [[2, 1, 0]]
    np.testing.assert_allclose(result[0, 0, :2], [0.2125, 0.075], atol=1e-6)
    assert np.isnan(result[0, 0, 2])
    indices = index_values(np.array([0.4, 0.0, np.nan]), np.array([0.1, 0.0, 0.1]))
    np.testing.assert_allclose(indices, [0.6, np.nan, np.nan])
