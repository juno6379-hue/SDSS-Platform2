import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("rasterio")

from services.lcluc.postprocess import spatial_filter  # noqa: E402


def test_spatial_sieve_protects_nodata_and_registered_water():
    original = np.full((9, 9), 2, dtype="uint16")
    original[1, 1] = 7
    original[3, 3] = 1
    original[5, 5] = 4
    original[:, 0] = 0
    result = spatial_filter(original, 0, 3, 8, [1, 4, 10])
    assert result[1, 1] == 2
    assert result[3, 3] == 1 and result[5, 5] == 4
    assert not result[:, 0].any()
    assert original[1, 1] == 7
    assert np.count_nonzero(original != result) == 1


def test_spatial_sieve_connectivity_retains_diagonal_patch_only_for_eight_neighbors():
    original = np.full((9, 9), 2, dtype="uint16")
    original[2, 2] = original[3, 3] = 7
    assert (spatial_filter(original, 0, 2, 4, [1, 4]) == 7).sum() == 0
    assert (spatial_filter(original, 0, 2, 8, [1, 4]) == 7).sum() == 2
