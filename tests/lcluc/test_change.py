"""Synthetic fixtures exercise the real raster and spatial-change implementation."""

import json
from dataclasses import replace
from hashlib import sha256

import pytest

np = pytest.importorskip("numpy")
rasterio = pytest.importorskip("rasterio")
pyproj = pytest.importorskip("pyproj")
pytest.importorskip("shapely")

from rasterio.transform import from_origin  # noqa: E402

from services.lcluc.change import (  # noqa: E402
    ChangeError,
    MaskPin,
    RasterPin,
    ZonePin,
    analyze_change,
    write_change_assets,
)
from services.lcluc.taxonomy import load_taxonomy  # noqa: E402

TRANSFORM = from_origin(1_000_000, 1_000_000, 100, 100)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def raster(path, data, *, transform=TRANSFORM, crs="EPSG:6933", nodata=None, tags=None):
    data = np.asarray(data, dtype="uint16")
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=data.shape[1],
        height=data.shape[0],
        count=1,
        dtype=data.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as output:
        output.write(data, 1)
        if tags:
            output.update_tags(**tags)
    return path


def pin_raster(tmp_path, taxonomy, data, year, **profile):
    stamp = f"{year}-12-31"
    tags = {
        "observed_on": stamp,
        "taxonomy_sha256": taxonomy.sha256,
        "source_kind": "synthetic_fixture",
        "dataset_id": "fixture",
        "version": f"v{year}",
    }
    path = raster(tmp_path / f"geo-{year}.tif", data, tags=tags, nodata=taxonomy.nodata, **profile)
    return RasterPin(
        path,
        digest(path),
        stamp,
        taxonomy.sha256,
        "synthetic_fixture",
        "fixture",
        f"v{year}",
    )


def pin_mask(path, data, **kwargs):
    raster(path, data, nodata=0, **kwargs)
    return MaskPin(path, digest(path))


def pin_zone(path):
    project = pyproj.Transformer.from_crs("EPSG:6933", "OGC:CRS84", always_xy=True)
    polygons = [(1_000_000, 1_000_200), (1_001_000, 1_001_200)]
    features = []
    for i, (left, right) in enumerate(polygons, start=1):
        corners = (
            (left, 999_700),
            (right, 999_700),
            (right, 1_000_000),
            (left, 1_000_000),
            (left, 999_700),
        )
        features.append(
            {
                "type": "Feature",
                "id": f"zone-{i}",
                "properties": {"name": f"Test Zone {i}"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[project.transform(x, y) for x, y in corners]],
                },
            }
        )
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
    )
    return ZonePin(path, digest(path), "v1")


@pytest.fixture
def sample(tmp_path):
    taxonomy = load_taxonomy("klhk-23")
    f, u, o = taxonomy.thematic_codes[:3]
    qa, nodata = taxonomy.qa_codes[0], taxonomy.nodata
    a = pin_raster(tmp_path, taxonomy, [[f, f, f, nodata], [f, u, u, qa], [o, o, o, f]], 2020)
    b = pin_raster(tmp_path, taxonomy, [[f, u, f, o], [o, u, u, f], [o, u, f, nodata]], 2025)
    a = replace(
        a,
        valid_mask=pin_mask(tmp_path / "quality-a.tif", [[1, 1, 1, 1], [1, 1, 1, 1], [0, 1, 1, 1]]),
    )
    b = replace(
        b,
        valid_mask=pin_mask(tmp_path / "quality-b.tif", [[1, 1, 0, 1], [1, 1, 1, 1], [1, 1, 1, 1]]),
    )
    return taxonomy, a, b


def test_paired_change_area_stats_and_outputs(sample, tmp_path):
    taxonomy, a, b = sample
    f, u, o = taxonomy.thematic_codes[:3]
    result = analyze_change(
        a,
        b,
        taxonomy,
        zones=pin_zone(tmp_path / "zones.geojson"),
        forest_codes=(f,),
        settlement_codes=(u,),
        min_hotspot_pixels=2,
    )
    report = result.report
    assert (report["from_year"], report["to_year"]) == (2020, 2025)
    assert report["grid"]["pixel_area_ha"] == 1
    assert report["taxonomy"]["quality_codes_excluded"] == [2500]
    assert 2500 not in [item["code"] for item in report["classes"]]
    assert report["coverage"] == {
        "total_pixels": 12,
        "earlier_valid_pixels": 9,
        "later_valid_pixels": 10,
        "common_valid_pixels": 7,
        "excluded_pixels": 5,
        "common_valid_area_ha": 7.0,
        "common_valid_fraction": 7 / 12,
    }
    first_counts = report["inputs"][0]
    assert first_counts["taxonomy_quality_pixels"] == 1
    assert first_counts["nodata_or_internal_mask_pixels"] == 1
    assert first_counts["external_mask_pixels"] == 1
    assert first_counts["valid_mask"]["sha256"] == a.valid_mask.sha256
    matrix = np.array(report["transition_matrix_pixels"])
    assert matrix.sum() == 7
    assert matrix[:3, :3].tolist() == [[1, 1, 1], [0, 2, 0], [1, 1, 0]]
    assert matrix.tolist() == report["transition_matrix_ha"]
    stats = {row["code"]: row for row in report["annual_stats"]}
    assert stats[f]["loss_ha"] == 2 and stats[f]["gain_ha"] == 1 and stats[f]["net_ha"] == -1
    assert stats[u]["gain_ha"] == 2 and stats[o]["net_ha"] == -1
    assert report["major_changes"]["changed_area_ha"] == 4
    assert report["major_changes"]["forest_loss_ha"] == 2
    assert report["major_changes"]["settlement_gain_ha"] == 2
    assert report["hotspot_count"] == 1
    assert report["hotspot_filtered_pixels"] == 2
    assert result.hotspots["features"][0]["properties"] == {"pixel_count": 2, "area_ha": 2}
    west, outside = report["zones"]
    assert west["coverage"]["total_pixels"] == 6
    assert west["coverage"]["common_valid_pixels"] == 5
    assert west["major_changes"]["changed_area_ha"] == 3
    assert outside["major_changes"]["change_rate_pct"] is None
    assert outside["status"] == "NO_COMMON_VALID_PIXELS"
    assert report["zone_source"]["rule"] == "pixel_center"

    paths = write_change_assets(result, tmp_path / "derived")
    assert json.loads(paths["report"].read_text(encoding="utf-8"))["from_year"] == 2020
    assert json.loads(paths["hotspots"].read_text(encoding="utf-8"))["type"] == "FeatureCollection"
    with rasterio.open(paths["transition"]) as published:
        assert published.nodata == 0 and published.crs.to_epsg() == 6933
        assert published.tags()["taxonomy_sha256"] == taxonomy.sha256
        assert published.read(1).tolist() == result.transition_codes.tolist()
    with pytest.raises(ChangeError, match="OUTPUT_EXISTS"):
        write_change_assets(result, tmp_path / "derived")


def test_unchanged_is_measured_and_semantic_groups_can_be_unknown(tmp_path):
    taxonomy = load_taxonomy("klhk-23")
    code = taxonomy.thematic_codes[0]
    a = pin_raster(tmp_path, taxonomy, [[code]], 2020)
    b = pin_raster(tmp_path, taxonomy, [[code]], 2025)
    result = analyze_change(a, b, taxonomy)
    assert result.report["major_changes"]["change_rate_pct"] == 0
    assert result.report["major_changes"]["forest_loss_ha"] is None
    assert result.report["major_changes"]["settlement_gain_ha"] is None
    assert result.hotspots["features"] == []
    assert result.transition_codes.item() == 1


def test_integrity_date_and_source_kinds_fail_closed(sample):
    taxonomy, a, b = sample
    with pytest.raises(ChangeError, match="FILE_SHA256_MISMATCH"):
        analyze_change(replace(a, sha256="0" * 64), b, taxonomy)
    with pytest.raises(ChangeError, match="REUSED_ANNUAL_RASTER"):
        analyze_change(a, replace(a, observed_on=b.observed_on), taxonomy)
    with pytest.raises(ChangeError, match="DISTINCT_ORDERED_YEARS_REQUIRED"):
        analyze_change(b, a, taxonomy)
    with pytest.raises(ChangeError, match="PROVENANCE_TAG_MISMATCH"):
        analyze_change(a, replace(b, observed_on="2023-12-31"), taxonomy)
    with pytest.raises(ChangeError, match="SOURCE_KIND_MISMATCH"):
        analyze_change(a, replace(b, source_kind="official_reference"), taxonomy)
    with pytest.raises(ChangeError, match="TAXONOMY_PIN_MISMATCH"):
        analyze_change(a, replace(b, taxonomy_sha256="0" * 64), taxonomy)
    with pytest.raises(ChangeError, match="NODATA_COLLIDES_WITH_TAXONOMY"):
        analyze_change(a, replace(b, nodata=2500), taxonomy)


def test_grid_quality_and_class_checks(tmp_path):
    taxonomy = load_taxonomy("klhk-23")
    code = taxonomy.thematic_codes[0]
    a = pin_raster(tmp_path, taxonomy, [[code]], 2020)
    moved = pin_raster(
        tmp_path, taxonomy, [[code]], 2021, transform=from_origin(1_000_050, 1_000_000, 100, 100)
    )
    with pytest.raises(ChangeError, match="ANNUAL_GRID_MISMATCH"):
        analyze_change(a, moved, taxonomy)
    non_equal_area = pin_raster(tmp_path, taxonomy, [[code]], 2022, crs="EPSG:3857")
    with pytest.raises(ChangeError, match="EQUAL_AREA_METRE_CRS_REQUIRED"):
        analyze_change(a, non_equal_area, taxonomy)
    unsupported_code = pin_raster(tmp_path, taxonomy, [[12345]], 2023)
    with pytest.raises(ChangeError, match="UNREGISTERED_CLASS_CODE"):
        analyze_change(a, unsupported_code, taxonomy)
    b = pin_raster(tmp_path, taxonomy, [[code]], 2025)
    bad_mask = pin_mask(tmp_path / "bad-mask.tif", [[2]])
    with pytest.raises(ChangeError, match="BINARY_QUALITY_MASK_REQUIRED"):
        analyze_change(a, replace(b, valid_mask=bad_mask), taxonomy)
    outside = pin_mask(tmp_path / "empty-mask.tif", [[0]])
    with pytest.raises(ChangeError, match="NO_COMMON_VALID_PIXELS"):
        analyze_change(a, replace(b, valid_mask=outside), taxonomy)
