"""Expose native Banten product statistics without equating their classes."""

ESRI_CLASSES = (
    (1, "수역"),
    (2, "수목"),
    (4, "침수 식생"),
    (5, "농경지"),
    (7, "시가지"),
    (8, "나지"),
    (9, "눈·얼음"),
    (10, "구름"),
    (11, "초지·관목지"),
)


def compare(esri, mapbiomas, year=None):
    years = sorted({row["year"] for row in esri["annual"]} & set(mapbiomas["years"]))
    if not years or (year is not None and year not in years):
        raise ValueError("BANTEN_NO_COMMON_PRODUCT_YEAR")
    year = years[-1] if year is None else year
    annual = next(row for row in esri["annual"] if row["year"] == year)
    areas = annual["area_ha_by_source_code"]
    index = mapbiomas["years"].index(year)
    esri_classes = [{"code": code, "name": name, "area_ha": areas[str(code)]} for code, name in ESRI_CLASSES]
    mapbiomas_classes = [{"code": row["code"], "name": row["name"], "area_ha": row["areas_ha"][index]}
                        for row in mapbiomas["classes"]]
    return {
        "year": year,
        "common_years": years,
        "region": "banten",
        "scope": "native_statistics_separate_boundaries",
        "comparison_status": "COMMON_BOUNDARY_AND_REVIEWED_CROSSWALK_REQUIRED",
        "esri": {
            "aoi_area_ha": esri["aoi_pixel_center_area_ha"],
            "thematic_area_ha": round(sum(row["area_ha"] for row in esri_classes if row["code"] != 10), 2),
            "nodata_area_ha": areas["0"],
            "boundary_sha256": esri["boundary_sha256"],
            "source_sha256": annual["source_pin"]["sha256"],
            "classes": esri_classes,
        },
        "mapbiomas": {
            "published_area_ha": round(sum(row["area_ha"] for row in mapbiomas_classes), 2),
            "source_sha256": mapbiomas["sha256"],
            "classes": mapbiomas_classes,
        },
    }
