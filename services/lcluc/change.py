"""Annual land-cover change from content-pinned, aligned categorical GeoTIFFs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.features import geometry_mask, shapes
from rasterio.io import MemoryFile
from rasterio.warp import transform_bounds
from shapely import make_valid
from shapely.errors import ShapelyError
from shapely.geometry import mapping, shape
from shapely.ops import transform as transform_geometry

from .taxonomy import Taxonomy, validate_class_codes

SourceKind = Literal[
    "official_reference", "model_prediction", "research_reference", "synthetic_fixture"
]
SOURCE_KINDS = {"official_reference", "model_prediction", "research_reference", "synthetic_fixture"}
MAX_INPUT_BYTES = 128 * 1024**2
MAX_ZONE_BYTES = 16 * 1024**2
DEFAULT_MAX_PIXELS = 16_000_000
DEFAULT_MAX_HOTSPOTS = 10_000
DEFAULT_MAX_ZONES = 1_000
MAX_ZONAL_PIXEL_CHECKS = 64_000_000
SHA256 = re.compile(r"[0-9a-f]{64}")


class ChangeError(ValueError):
    """A land-cover comparison cannot be computed from the supplied evidence."""


@dataclass(frozen=True)
class MaskPin:
    path: Path | str
    sha256: str


@dataclass(frozen=True)
class RasterPin:
    path: Path | str
    sha256: str
    observed_on: date | str
    taxonomy_sha256: str
    source_kind: SourceKind
    dataset_id: str
    version: str
    valid_mask: MaskPin | None = None
    nodata: int | None = None


@dataclass(frozen=True)
class ZonePin:
    path: Path | str
    sha256: str
    version: str


@dataclass(frozen=True)
class ChangeResult:
    report: dict
    hotspots: dict
    transition_codes: np.ndarray
    profile: dict


@dataclass(frozen=True)
class _Raster:
    codes: np.ndarray
    valid: np.ndarray
    grid: dict
    lineage: dict
    invalid: dict


def _pinned_bytes(path, digest, max_bytes):
    if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
        raise ChangeError("LCLUC_SHA256_REQUIRED")
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except (OSError, TypeError, ValueError) as error:
        raise ChangeError("LCLUC_PINNED_FILE_UNAVAILABLE") from error
    if not data or len(data) > max_bytes:
        raise ChangeError("LCLUC_PINNED_FILE_SIZE_INVALID")
    if sha256(data).hexdigest() != digest:
        raise ChangeError("LCLUC_FILE_SHA256_MISMATCH")
    return data


def _day(value):
    if type(value) is date:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ChangeError("LCLUC_OBSERVATION_DATE_INVALID")


def _positive_int(value, reason):
    if type(value) is not int or value <= 0:
        raise ChangeError(reason)


def _grid(raster, max_pixels):
    if raster.driver != "GTiff" or raster.count != 1:
        raise ChangeError("LCLUC_SINGLE_BAND_GEOTIFF_REQUIRED")
    if raster.width * raster.height > max_pixels:
        raise ChangeError("LCLUC_GRID_PIXEL_LIMIT")
    if np.dtype(raster.dtypes[0]).kind not in {"i", "u"} or not raster.crs:
        raise ChangeError("LCLUC_INTEGER_RASTER_AND_CRS_REQUIRED")
    crs = CRS.from_user_input(raster.crs)
    operation = crs.coordinate_operation
    method = operation.method_name.lower().replace("-", " ") if operation else ""
    metre_axes = len(crs.axis_info) == 2 and all(
        axis.unit_conversion_factor == 1 and axis.unit_name.lower() in {"metre", "meter"}
        for axis in crs.axis_info
    )
    if (
        not crs.is_projected
        or not metre_axes
        or ("equal area" not in method and method not in {"equal earth", "sinusoidal"})
    ):
        raise ChangeError("LCLUC_EQUAL_AREA_METRE_CRS_REQUIRED")
    affine = raster.transform
    if (
        not all(isfinite(value) for value in affine)
        or affine.a <= 0
        or affine.e >= 0
        or affine.b != 0
        or affine.d != 0
        or not 0 < affine.a * -affine.e < float("inf")
    ):
        raise ChangeError("LCLUC_NORTH_UP_GRID_REQUIRED")
    return {
        "width": raster.width,
        "height": raster.height,
        "crs": raster.crs,
        "transform": affine,
        "bounds": tuple(raster.bounds),
        "pixel_area_ha": (affine.a * -affine.e) / 10_000,
    }


def _quality(pin, grid, max_pixels):
    raw = _pinned_bytes(pin.path, pin.sha256, MAX_INPUT_BYTES)
    with MemoryFile(raw) as memory, memory.open() as raster:
        if _grid(raster, max_pixels) != grid:
            raise ChangeError("LCLUC_QUALITY_MASK_GRID_MISMATCH")
        values = raster.read(1)
        if raster.nodata not in {None, 0} or not np.isin(values, (0, 1)).all():
            raise ChangeError("LCLUC_BINARY_QUALITY_MASK_REQUIRED")
        mask = (values == 1) & (raster.read_masks(1) != 0)
    return mask, {"sha256": pin.sha256, "bytes": len(raw), "valid_value": 1}


def _read_raster(pin, observed_on, taxonomy, max_pixels):
    raw = _pinned_bytes(pin.path, pin.sha256, MAX_INPUT_BYTES)
    nodata = taxonomy.nodata if pin.nodata is None else pin.nodata
    if type(nodata) is not int or nodata in taxonomy.codes:
        raise ChangeError("LCLUC_NODATA_COLLIDES_WITH_TAXONOMY")
    if not all(isinstance(value, str) and value.strip() for value in (pin.dataset_id, pin.version)):
        raise ChangeError("LCLUC_DATASET_VERSION_REQUIRED")
    try:
        with MemoryFile(raw) as memory, memory.open() as raster:
            grid = _grid(raster, max_pixels)
            tags = raster.tags()
            expected = {
                "observed_on": observed_on.isoformat(),
                "taxonomy_sha256": taxonomy.sha256,
                "source_kind": pin.source_kind,
            }
            if any(tags.get(key) != value for key, value in expected.items()) or any(
                key in tags and tags[key] != value
                for key, value in {"dataset_id": pin.dataset_id, "version": pin.version}.items()
            ):
                raise ChangeError("LCLUC_RASTER_PROVENANCE_TAG_MISMATCH")
            if raster.nodata != nodata:
                raise ChangeError("LCLUC_RASTER_NODATA_MISMATCH")
            if raster.scales != (1.0,) or raster.offsets != (0.0,):
                raise ChangeError("LCLUC_CATEGORICAL_SCALE_OFFSET_UNSUPPORTED")
            codes = raster.read(1)
            observed = (raster.read_masks(1) != 0) & (codes != nodata)
        try:
            validate_class_codes(np.ma.array(codes, mask=~observed), taxonomy, nodata=nodata)
        except ValueError as error:
            raise ChangeError("LCLUC_UNREGISTERED_CLASS_CODE") from error
        qa = observed & np.isin(codes, taxonomy.qa_codes)
        valid = observed & ~qa
        invalid = {
            "nodata_or_internal_mask_pixels": int((~observed).sum()),
            "taxonomy_quality_pixels": int(qa.sum()),
            "external_mask_pixels": 0,
        }
        mask_evidence = None
        if pin.valid_mask is not None:
            quality, mask_evidence = _quality(pin.valid_mask, grid, max_pixels)
            invalid["external_mask_pixels"] = int((valid & ~quality).sum())
            valid &= quality
    except (rasterio.errors.RasterioError, OverflowError) as error:
        raise ChangeError("LCLUC_INVALID_GEOTIFF") from error
    lineage = {
        "dataset_id": pin.dataset_id,
        "version": pin.version,
        "source_kind": pin.source_kind,
        "observed_on": observed_on.isoformat(),
        "taxonomy_sha256": taxonomy.sha256,
        "sha256": pin.sha256,
        "bytes": len(raw),
        "nodata": nodata,
        "valid_mask": mask_evidence,
    }
    return _Raster(codes, valid, grid, lineage, invalid)


def _group_codes(group, codes):
    declared = tuple(group)
    if any(type(code) is not int or code not in codes for code in declared) or len(
        set(declared)
    ) != len(declared):
        raise ChangeError("LCLUC_INVALID_SEMANTIC_CLASS_GROUP")
    return np.asarray([codes.index(code) for code in declared], dtype=np.intp)


def _metrics(before, after, transition, scope, codes, area, forest, settlements):
    n = len(codes)
    total = before.codes.size if scope is None else int(scope.sum())
    first_valid = before.valid if scope is None else before.valid & scope
    second_valid = after.valid if scope is None else after.valid & scope
    bins = np.bincount(
        transition.ravel() if scope is None else transition[scope], minlength=n**2 + 1
    )
    matrix = bins[1:].reshape(n, n)
    common = int(matrix.sum())
    first_count, second_count = int(first_valid.sum()), int(second_valid.sum())
    unchanged = matrix.diagonal()
    row, column = matrix.sum(axis=1), matrix.sum(axis=0)
    changed = common - int(unchanged.sum())
    first_indices = np.searchsorted(codes, before.codes[first_valid])
    second_indices = np.searchsorted(codes, after.codes[second_valid])
    first_areas = np.bincount(first_indices, minlength=n) * area
    second_areas = np.bincount(second_indices, minlength=n) * area
    stats = [
        {
            "code": code,
            "from_area_ha": float(row[i] * area),
            "to_area_ha": float(column[i] * area),
            "gain_ha": float((column[i] - unchanged[i]) * area),
            "loss_ha": float((row[i] - unchanged[i]) * area),
            "net_ha": float((column[i] - row[i]) * area),
            "from_valid_area_ha": float(first_areas[i]),
            "to_valid_area_ha": float(second_areas[i]),
        }
        for i, code in enumerate(codes)
    ]
    other_forest = np.setdiff1d(np.arange(n), forest)
    other_settlement = np.setdiff1d(np.arange(n), settlements)
    return {
        "status": "CALCULATED" if common else "NO_COMMON_VALID_PIXELS",
        "coverage": {
            "total_pixels": total,
            "earlier_valid_pixels": first_count,
            "later_valid_pixels": second_count,
            "common_valid_pixels": common,
            "excluded_pixels": total - common,
            "common_valid_area_ha": common * area,
            "common_valid_fraction": common / total if total else None,
        },
        "transition_matrix_pixels": matrix.tolist(),
        "transition_matrix_ha": (matrix * area).tolist(),
        "annual_stats": stats,
        "major_changes": {
            "changed_pixels": changed,
            "changed_area_ha": changed * area,
            "change_rate": changed / common if common else None,
            "change_rate_pct": 100 * changed / common if common else None,
            "forest_loss_ha": (
                float(matrix[np.ix_(forest, other_forest)].sum() * area)
                if common and forest.size
                else None
            ),
            "settlement_gain_ha": (
                float(matrix[np.ix_(other_settlement, settlements)].sum() * area)
                if common and settlements.size
                else None
            ),
        },
    }


def _geo_geometry(value):
    try:
        geometry = shape(value)
    except (ShapelyError, TypeError, KeyError, ValueError, AttributeError) as error:
        raise ChangeError("LCLUC_ZONE_GEOMETRY_INVALID") from error
    if (
        geometry.geom_type not in {"Polygon", "MultiPolygon"}
        or geometry.is_empty
        or not geometry.is_valid
    ):
        raise ChangeError("LCLUC_ZONE_GEOMETRY_INVALID")
    west, south, east, north = geometry.bounds
    if not (
        all(isfinite(x) for x in geometry.bounds)
        and -180 <= west <= east <= 180
        and -90 < south <= north < 90
        and east - west < 180
        and not geometry.has_z
    ):
        raise ChangeError("LCLUC_ZONE_CRS84_BOUNDS_INVALID")
    return geometry


def _zone_scopes(pin, grid, max_zones):
    if not isinstance(pin.version, str) or not pin.version.strip():
        raise ChangeError("LCLUC_ZONE_VERSION_REQUIRED")
    raw = _pinned_bytes(pin.path, pin.sha256, MAX_ZONE_BYTES)
    try:
        collection = json.loads(raw)
    except (UnicodeError, ValueError) as error:
        raise ChangeError("LCLUC_ZONE_GEOJSON_INVALID") from error
    if (
        not isinstance(collection, dict)
        or collection.get("type") != "FeatureCollection"
        or "crs" in collection
        or not isinstance(collection.get("features"), list)
        or not collection["features"]
    ):
        raise ChangeError("LCLUC_ZONE_CRS84_FEATURE_COLLECTION_REQUIRED")
    features = collection["features"]
    if len(features) > max_zones or (
        len(features) * grid["height"] * grid["width"] > MAX_ZONAL_PIXEL_CHECKS
    ):
        raise ChangeError("LCLUC_ZONE_RESOURCE_LIMIT")
    ids = set()
    project = Transformer.from_crs("OGC:CRS84", grid["crs"], always_xy=True).transform
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ChangeError("LCLUC_ZONE_FEATURE_REQUIRED")
        props = feature.get("properties")
        if not isinstance(props, dict):
            raise ChangeError("LCLUC_ZONE_PROPERTIES_REQUIRED")
        zone_id = feature.get("id", props.get("id"))
        name = props.get("name")
        if (
            type(zone_id) not in {str, int}
            or not str(zone_id).strip()
            or str(zone_id) in ids
            or not isinstance(name, str)
            or not name.strip()
        ):
            raise ChangeError("LCLUC_ZONE_ID_AND_NAME_REQUIRED")
        ids.add(str(zone_id))
        geographic = _geo_geometry(feature.get("geometry"))
        native = transform_geometry(project, geographic)
        if native.is_empty or not native.is_valid or not isfinite(native.area) or native.area <= 0:
            raise ChangeError("LCLUC_ZONE_PROJECTION_INVALID")
        scope = geometry_mask(
            [mapping(native)],
            out_shape=(grid["height"], grid["width"]),
            transform=grid["transform"],
            all_touched=False,
            invert=True,
        )
        yield str(zone_id), name, scope


def _hotspots(changed, grid, minimum, max_hotspots):
    area = grid["pixel_area_ha"]
    transform = Transformer.from_crs(grid["crs"], "OGC:CRS84", always_xy=True).transform
    features = []
    filtered = 0
    for raw, _ in shapes(
        changed.astype("uint8"), mask=changed, connectivity=4, transform=grid["transform"]
    ):
        geometry = shape(raw)
        count = int(round(geometry.area / (area * 10_000)))
        if count < minimum:
            filtered += count
            continue
        if len(features) >= max_hotspots:
            raise ChangeError("LCLUC_HOTSPOT_FEATURE_LIMIT")
        geometry = make_valid(geometry)
        if geometry.geom_type == "GeometryCollection":
            from shapely.ops import unary_union

            geometry = unary_union(
                [part for part in geometry.geoms if part.geom_type in {"Polygon", "MultiPolygon"}]
            )
        geographic = _geo_geometry(mapping(transform_geometry(transform, geometry)))
        number = len(features) + 1
        features.append(
            {
                "type": "Feature",
                "id": f"change-cluster-{number}",
                "geometry": mapping(geographic),
                "properties": {"pixel_count": count, "area_ha": count * area},
            }
        )
    return {"type": "FeatureCollection", "features": features}, filtered


def analyze_change(
    earlier: RasterPin,
    later: RasterPin,
    taxonomy: Taxonomy,
    *,
    zones: ZonePin | None = None,
    forest_codes=(),
    settlement_codes=(),
    min_hotspot_pixels: int = 1,
    max_pixels: int = DEFAULT_MAX_PIXELS,
    max_hotspots: int = DEFAULT_MAX_HOTSPOTS,
    max_zones: int = DEFAULT_MAX_ZONES,
) -> ChangeResult:
    """Calculate paired changes and zonal summaries using jointly valid observations."""
    _positive_int(max_pixels, "LCLUC_GRID_PIXEL_LIMIT_INVALID")
    _positive_int(max_hotspots, "LCLUC_HOTSPOT_LIMIT_INVALID")
    _positive_int(max_zones, "LCLUC_ZONE_LIMIT_INVALID")
    _positive_int(min_hotspot_pixels, "LCLUC_HOTSPOT_MINIMUM_INVALID")
    from_date, to_date = _day(earlier.observed_on), _day(later.observed_on)
    if from_date.year >= to_date.year:
        raise ChangeError("LCLUC_DISTINCT_ORDERED_YEARS_REQUIRED")
    if earlier.sha256 == later.sha256 or Path(earlier.path).resolve() == Path(later.path).resolve():
        raise ChangeError("LCLUC_REUSED_ANNUAL_RASTER")
    if earlier.source_kind not in SOURCE_KINDS or earlier.source_kind != later.source_kind:
        raise ChangeError("LCLUC_SOURCE_KIND_MISMATCH")
    if not earlier.taxonomy_sha256 == later.taxonomy_sha256 == taxonomy.sha256:
        raise ChangeError("LCLUC_TAXONOMY_PIN_MISMATCH")
    codes = taxonomy.thematic_codes
    if not codes or len(codes) ** 2 > np.iinfo("uint16").max:
        raise ChangeError("LCLUC_TAXONOMY_SIZE_UNSUPPORTED")
    forest, settlements = _group_codes(forest_codes, codes), _group_codes(settlement_codes, codes)
    if np.intersect1d(forest, settlements).size:
        raise ChangeError("LCLUC_SEMANTIC_CLASS_GROUPS_OVERLAP")
    before = _read_raster(earlier, from_date, taxonomy, max_pixels)
    after = _read_raster(later, to_date, taxonomy, max_pixels)
    grid = before.grid
    if grid != after.grid:
        raise ChangeError("LCLUC_ANNUAL_GRID_MISMATCH")
    common = before.valid & after.valid
    if not common.any():
        raise ChangeError("LCLUC_NO_COMMON_VALID_PIXELS")
    before_class = np.searchsorted(codes, before.codes[common])
    after_class = np.searchsorted(codes, after.codes[common])
    transition = np.zeros(common.shape, dtype="uint16")
    transition[common] = 1 + before_class * len(codes) + after_class
    area = grid["pixel_area_ha"]
    metrics = _metrics(before, after, transition, None, codes, area, forest, settlements)
    changed = common & (before.codes != after.codes)
    hotspot_collection, filtered_pixels = _hotspots(changed, grid, min_hotspot_pixels, max_hotspots)
    zone_rows = []
    if zones is not None:
        for zone_id, name, scope in _zone_scopes(zones, grid, max_zones):
            zone_rows.append(
                {
                    "id": zone_id,
                    "name": name,
                    **_metrics(before, after, transition, scope, codes, area, forest, settlements),
                }
            )
    names = {item.code: item for item in taxonomy.classes}
    classes = [
        {"code": code, "name": names[code].label, "name_ko": names[code].name_ko} for code in codes
    ]
    bbox = transform_bounds(grid["crs"], "OGC:CRS84", *grid["bounds"], densify_pts=21)
    if not all(isfinite(value) for value in bbox) or bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
        raise ChangeError("LCLUC_UNSUPPORTED_GEOGRAPHIC_EXTENT")
    report = {
        "schema_version": "sdss-lcluc-change/1",
        "from_year": from_date.year,
        "to_year": to_date.year,
        "inputs": [before.lineage | before.invalid, after.lineage | after.invalid],
        "grid": {
            **grid,
            "crs": grid["crs"].to_string(),
            "transform": list(grid["transform"])[:6],
            "bounds_crs84": list(bbox),
        },
        "taxonomy": {
            "sha256": taxonomy.sha256,
            "version": taxonomy.version,
            "classes": classes,
            "quality_codes_excluded": list(taxonomy.qa_codes),
        },
        "classes": classes,
        **metrics,
        "semantic_groups": {
            "forest": [codes[i] for i in forest],
            "settlement": [codes[i] for i in settlements],
        },
        "hotspot_count": len(hotspot_collection["features"]),
        "hotspot_filtered_pixels": filtered_pixels,
        "hotspot_method": "rook_connected_changed_pixels",
        "min_hotspot_pixels": min_hotspot_pixels,
        "zones": zone_rows,
        "zone_source": (
            {"sha256": zones.sha256, "version": zones.version, "rule": "pixel_center"}
            if zones
            else None
        ),
        "transition_code_rule": "0=NoData; 1 + from_class_index * class_count + to_class_index",
        "area_method": "equal_area_grid_cell_area_ha",
        "scale": "paired_common_valid_except_annual_valid_areas",
    }
    profile = {
        "driver": "GTiff",
        "dtype": "uint16",
        "count": 1,
        "width": grid["width"],
        "height": grid["height"],
        "crs": grid["crs"],
        "transform": grid["transform"],
        "nodata": 0,
        "compress": "deflate",
    }
    return ChangeResult(report, hotspot_collection, transition, profile)


def write_change_assets(result: ChangeResult, output_dir: Path | str) -> dict[str, Path]:
    """Write derived assets without replacing existing files."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "report": destination / "report.json",
        "hotspots": destination / "hotspots.geojson",
        "transition": destination / "transition.tif",
    }
    if any(path.exists() for path in paths.values()):
        raise ChangeError("LCLUC_OUTPUT_EXISTS")
    with TemporaryDirectory(prefix=".lcluc-", dir=destination) as temporary:
        stage = Path(temporary)
        for key, value in (("report", result.report), ("hotspots", result.hotspots)):
            (stage / paths[key].name).write_text(
                json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
                encoding="utf-8",
            )
        with rasterio.open(stage / paths["transition"].name, "w", **result.profile) as raster:
            raster.write(result.transition_codes, 1)
            raster.update_tags(
                source_kind=result.report["inputs"][0]["source_kind"],
                from_year=result.report["from_year"],
                to_year=result.report["to_year"],
                taxonomy_sha256=result.report["taxonomy"]["sha256"],
                transition_code_rule=result.report["transition_code_rule"],
            )
        written = []
        try:
            for target in paths.values():
                target.hardlink_to(stage / target.name)
                written.append(target)
        except OSError as error:
            for target in written:
                target.unlink()
            raise ChangeError("LCLUC_OUTPUT_PUBLICATION_FAILED") from error
    return paths
