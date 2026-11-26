import pytest

from services.lcluc.banten_area_comparison import ESRI_CLASSES, compare


def test_native_area_uses_latest_common_year_and_excludes_cloud_and_nodata_from_thematic_total():
    codes = {str(code): 0.0 for code, _ in ESRI_CLASSES} | {"0": 1.25, "1": 15_160.0, "10": 378.05}
    esri = {"annual": [{"year": year, "area_ha_by_source_code": codes, "source_pin": {"sha256": str(year)}}
                       for year in (2023, 2024, 2025)],
            "boundary_sha256": "esri-boundary", "aoi_pixel_center_area_ha": 15_539.30}
    mapbiomas = {"years": [2023, 2024], "sha256": "published-workbook", "classes": [
        {"code": 33, "name": "Water", "areas_ha": [6000, 7050.8248]},
        {"code": 31, "name": "Aquaculture", "areas_ha": [9500, 13807.1435]},
        {"code": 40, "name": "Rice", "areas_ha": [120, 100]},
    ]}
    result = compare(esri, mapbiomas)
    by_code = {row["code"]: row for row in result["esri"]["classes"]}
    assert len(by_code) == 9 and "difference_ha" not in by_code[1]
    assert result["year"] == 2024
    assert by_code[9]["area_ha"] == 0 and by_code[10]["area_ha"] == 378.05
    assert result["esri"]["aoi_area_ha"] == 15_539.30
    assert result["esri"]["thematic_area_ha"] == 15_160.0
    assert result["esri"]["nodata_area_ha"] == 1.25
    assert result["esri"]["source_sha256"] == "2024"
    assert [row["code"] for row in result["mapbiomas"]["classes"]] == [33, 31, 40]
    assert result["mapbiomas"]["published_area_ha"] == 20_957.97
    assert compare(esri, mapbiomas, 2023)["mapbiomas"]["classes"][0]["area_ha"] == 6000
    with pytest.raises(ValueError, match="NO_COMMON_PRODUCT_YEAR"):
        compare(esri, mapbiomas, 2025)
