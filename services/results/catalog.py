"""Versioned, locally pinned measurements and assets attached to result IDs."""

import json
from datetime import date
from math import isfinite
from pathlib import PurePosixPath
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

AssetID = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
Units = Literal["days", "count", "percent", "km2", "m2", "ha", "m", "mm", "degC", "K", "1"]
MAX_CATALOG_FILE_BYTES = 32 * 1024**2


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Pin(Strict):
    path: str = Field(min_length=1, max_length=512)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bytes: int = Field(ge=1, le=MAX_CATALOG_FILE_BYTES, strict=True)

    @model_validator(mode="after")
    def relative_path(self):
        if (
            PurePosixPath(self.path).is_absolute()
            or any(part in ("", ".", "..") for part in self.path.split("/"))
            or any(ord(char) < 32 or char in "\\:?#<>|*" for char in self.path)
        ):
            raise ValueError("PACKAGE_PIN_RELATIVE_PATH_REQUIRED")
        return self


class Spatial(Strict):
    crs: str = Field(pattern=r"^(?:OGC:CRS84|EPSG:[1-9][0-9]{1,6})$")
    bbox: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]

    @model_validator(mode="after")
    def ordered_bbox(self):
        from pyproj import CRS

        crs = CRS.from_user_input(self.crs)
        west, south, east, north = self.bbox
        if not (west <= east and south <= north):
            raise ValueError("PACKAGE_BBOX_ORDER_INVALID")
        if crs.is_geographic and not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
            raise ValueError("PACKAGE_BBOX_OUTSIDE_CRS")
        return self


class Period(Strict):
    start: date
    end: date
    kind: Literal["observation", "climatology", "projection", "plan_effective"]

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.start > self.end:
            raise ValueError("PACKAGE_PERIOD_ORDER_INVALID")
        return self


class Source(Strict):
    id: AssetID
    title: str = Field(min_length=1, max_length=240)
    uri: str = Field(min_length=1, max_length=2000)
    version: str = Field(min_length=1, max_length=240)
    license: str = Field(min_length=1, max_length=128)
    raw: Pin
    license_evidence: Pin | None = None

    @model_validator(mode="after")
    def source_uri(self):
        uri = urlsplit(self.uri)
        if (
            uri.scheme not in {"https", "s3"}
            or not uri.hostname
            or uri.username is not None
            or uri.password is not None
        ):
            raise ValueError("PACKAGE_SOURCE_URI_INVALID")
        return self


class Metric(Strict):
    id: AssetID
    label: str = Field(min_length=1, max_length=240)
    value: FiniteFloat
    unit: Units
    source_id: AssetID

    @model_validator(mode="after")
    def value_range(self):
        if (self.unit == "count" and (self.value < 0 or not self.value.is_integer())) or (
            self.unit == "percent" and not 0 <= self.value <= 100
        ):
            raise ValueError("PACKAGE_METRIC_RANGE_INVALID")
        return self


class NoData(Strict):
    kind: Literal["mask", "value", "not_applicable"]
    value: FiniteFloat | None = None

    @model_validator(mode="after")
    def meaning(self):
        if (self.kind == "value") != (self.value is not None):
            raise ValueError("PACKAGE_NODATA_INVALID")
        return self


class Artifact(Strict):
    id: AssetID
    title: str = Field(min_length=1, max_length=240)
    file: Pin
    source_id: AssetID


class Layer(Artifact):
    format: Literal["GeoJSON", "GeoTIFF"]
    crs: str
    nodata: NoData
    metric_field: AssetID | None = None
    unit: Units | None = None

    @model_validator(mode="after")
    def metric_metadata(self):
        if (self.metric_field is None) != (self.unit is None):
            raise ValueError("PACKAGE_LAYER_UNITS_UNSPECIFIED")
        return self


class Report(Artifact):
    format: Literal["JSON", "PDF", "CSV", "Markdown"]


class Uncertainty(Strict):
    status: Literal["NOT_REPORTED", "QUANTIFIED"]
    reason: str = Field(min_length=1, max_length=1000)
    method: str | None = Field(default=None, max_length=240)
    lower: FiniteFloat | None = None
    upper: FiniteFloat | None = None
    unit: Units | None = None

    @model_validator(mode="after")
    def bounds(self):
        values = (self.method, self.lower, self.upper, self.unit)
        if self.status == "QUANTIFIED":
            if any(value is None for value in values) or not self.method or self.lower > self.upper:
                raise ValueError("PACKAGE_UNCERTAINTY_BOUNDS_INVALID")
        elif any(value is not None for value in values):
            raise ValueError("PACKAGE_UNCERTAINTY_NOT_REPORTED_HAS_BOUNDS")
        return self


class ResultPackage(Strict):
    schema_version: Literal["sdss-result-package/1"] = "sdss-result-package/1"
    institution: str = Field(min_length=1, max_length=240)
    adapter: str = Field(min_length=1, max_length=240)
    spatial: Spatial | None
    period: Period | None
    period_reason: str | None = Field(default=None, max_length=1000)
    metrics: list[Metric] = Field(max_length=100)
    layers: list[Layer] = Field(max_length=50)
    sources: list[Source] = Field(min_length=1, max_length=50)
    reports: list[Report] = Field(max_length=50)
    uncertainty: Uncertainty

    @model_validator(mode="after")
    def relationships(self):
        from pyproj import CRS

        if self.period is None and not self.period_reason:
            raise ValueError("PACKAGE_PERIOD_REASON_REQUIRED")
        references = {source.id for source in self.sources}
        if len(references) != len(self.sources):
            raise ValueError("PACKAGE_SOURCE_ID_DUPLICATE")
        identifiers = [item.id for item in [*self.metrics, *self.layers, *self.reports]]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("PACKAGE_OUTPUT_ID_DUPLICATE")
        if any(
            item.source_id not in references
            for item in [*self.metrics, *self.layers, *self.reports]
        ):
            raise ValueError("PACKAGE_SOURCE_REFERENCE_UNKNOWN")
        if self.layers:
            if self.spatial is None:
                raise ValueError("PACKAGE_LAYER_SPATIAL_REQUIRED")
            expected = CRS.from_user_input(self.spatial.crs)
            if any(
                not expected.equals(CRS.from_user_input(item.crs), ignore_axis_order=True)
                for item in self.layers
            ):
                raise ValueError("PACKAGE_LAYER_CRS_MISMATCH")
        if self.uncertainty.unit and not any(
            metric.unit == self.uncertainty.unit for metric in self.metrics
        ):
            raise ValueError("PACKAGE_UNCERTAINTY_UNITS_MISMATCH")
        return self


def package_pins(package):
    return (
        [item["raw"] for item in package["sources"]]
        + [item["license_evidence"] for item in package["sources"] if item.get("license_evidence")]
        + [item["file"] for item in [*package["layers"], *package["reports"]]]
    )


def _inside(bbox, extent):
    west, south, east, north = bbox
    return all(isfinite(x) for x in extent) and (
        west - 1e-8 <= extent[0] <= extent[2] <= east + 1e-8
        and south - 1e-8 <= extent[1] <= extent[3] <= north + 1e-8
    )


def validate_layer(path, layer, spatial):
    from pyproj import CRS

    expected = CRS.from_user_input(layer.crs)
    if layer.format == "GeoTIFF":
        import rasterio
        from rasterio.enums import MaskFlags

        with rasterio.open(path) as raster:
            if (
                raster.driver != "GTiff"
                or not raster.crs
                or not expected.equals(CRS.from_user_input(raster.crs), ignore_axis_order=True)
            ):
                raise ValueError("PACKAGE_RASTER_CRS_MISMATCH")
            if not _inside(spatial.bbox, raster.bounds):
                raise ValueError("PACKAGE_LAYER_BOUNDS_OUTSIDE_EXTENT")
            if layer.nodata.kind == "value":
                valid = all(value == layer.nodata.value for value in raster.nodatavals)
            elif layer.nodata.kind == "mask":
                valid = all(MaskFlags.all_valid not in flags for flags in raster.mask_flag_enums)
            else:
                valid = False
            if not valid:
                raise ValueError("PACKAGE_RASTER_NODATA_MISMATCH")
        return

    from shapely.geometry import shape

    document = json.loads(path.read_bytes())
    if (
        not isinstance(document, dict)
        or document.get("type") != "FeatureCollection"
        or not document.get("features")
    ):
        raise ValueError("PACKAGE_GEOJSON_FEATURES_REQUIRED")
    # RFC 7946 longitudes and latitudes are always CRS84, even when EPSG:4326 is declared.
    if "crs" in document or not expected.equals(
        CRS.from_user_input("OGC:CRS84"), ignore_axis_order=True
    ):
        raise ValueError("PACKAGE_GEOJSON_CRS_MISMATCH")
    if layer.nodata.kind != "not_applicable":
        raise ValueError("PACKAGE_VECTOR_NODATA_MISMATCH")
    for feature in document["features"]:
        geometry = shape(feature["geometry"])
        if (
            feature.get("type") != "Feature"
            or not geometry.is_valid
            or geometry.is_empty
            or not _inside(spatial.bbox, geometry.bounds)
        ):
            raise ValueError("PACKAGE_GEOJSON_GEOMETRY_INVALID")
        if layer.metric_field:
            value = (feature.get("properties") or {}).get(layer.metric_field)
            if type(value) not in (int, float) or not isfinite(value):
                raise ValueError("PACKAGE_GEOJSON_METRIC_NODATA")


def prepare_package(raw, *, safe_path, verify_pins, adapter_checks=()):
    package = ResultPackage.model_validate(raw)
    value = package.model_dump(mode="json")
    verify_pins(package_pins(value))
    for source in package.sources:
        if source.license_evidence is not None:
            proof = json.loads(safe_path(source.license_evidence.path).read_bytes())
            if (
                not isinstance(proof, dict)
                or proof.get("license") != source.license
                or not proof.get("source_uri")
            ):
                raise ValueError("PACKAGE_LICENSE_EVIDENCE_MISMATCH")
    for layer in package.layers:
        validate_layer(safe_path(layer.file.path), layer, package.spatial)
    for report in package.reports:
        report_path = safe_path(report.file.path)
        if report.format == "JSON":
            json.loads(report_path.read_bytes())
        elif report.format == "PDF":
            with report_path.open("rb") as handle:
                if handle.read(5) != b"%PDF-":
                    raise ValueError("PACKAGE_PDF_HEADER_INVALID")
        else:
            report_path.read_text(encoding="utf-8")
    value["quality"] = {
        "checks": [
            "ORIGINAL_AND_OUTPUT_SHA256",
            "PERIOD_ORDER" if package.period else "PERIOD_NOT_DOCUMENTED",
            "METRIC_UNITS",
            "LAYER_CRS_EXTENT_NODATA" if package.layers else "NO_LAYER",
            *adapter_checks,
        ],
        "publication_inputs_complete": bool(
            package.period
            and all(
                source.license_evidence is not None
                and source.license in {"CC-BY-4.0", "CC-BY-SA-4.0", "CC0-1.0"}
                for source in package.sources
            )
        ),
    }
    return value
