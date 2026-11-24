"""Pydantic v2 전용의 지역 기후 계약. 공통 계약 파일을 변경하지 않는다."""

import re
from datetime import timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from .calendars import date_parts, normalize_calendar, period_days, validate_time_units

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Positive = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def token(value: str) -> str:
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value)
        or value.endswith(".")
        or value.split(".")[0].upper()
        in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *{f"COM{i}" for i in range(1, 10)},
            *{f"LPT{i}" for i in range(1, 10)},
        }
        or value.lower() in {"latest", "current", "unknown"}
    ):
        raise ValueError("FIXED_SAFE_IDENTIFIER_REQUIRED")
    return value


def source_uri(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"https", "s3"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("UNSIGNED_SOURCE_URI_REQUIRED")
    return value


class LineageRef(Contract):
    dataset_id: str
    version: str
    sha256: Digest
    role: str = Field(min_length=1, max_length=128)

    _identifiers = field_validator("dataset_id", "version")(token)


class CFTimeCoverage(Contract):
    calendar: str
    start: str
    end: str
    time_units: str
    frequency: Literal["daily", "monthly", "annual", "period"]

    _calendar = field_validator("calendar", mode="before")(normalize_calendar)

    @model_validator(mode="after")
    def valid_dates(self):
        period_days(self.start, self.end, self.calendar)
        validate_time_units(self.time_units, self.calendar)
        return self


class SpatialCoverage(Contract):
    bbox: tuple[Number, Number, Number, Number]

    @model_validator(mode="after")
    def extent(self):
        west, south, east, north = self.bbox
        if west >= east or south >= north:
            raise ValueError("ORDERED_NONEMPTY_BBOX_REQUIRED")
        return self


class Grid(Contract):
    resolution_x: Positive
    resolution_y: Positive
    width: Annotated[int, Field(strict=True, gt=0, le=1000000)]
    height: Annotated[int, Field(strict=True, gt=0, le=1000000)]
    unit: Literal["degrees", "m"]
    layout: Literal["rectilinear_cell_bounds"]
    row_order: Literal["north_to_south", "south_to_north"]
    column_order: Literal["west_to_east"]


class AccessPolicy(Contract):
    visibility: Literal["public", "restricted"]
    allowed_principals: tuple[str, ...] = ()

    @model_validator(mode="after")
    def restricted_access(self):
        if self.visibility == "restricted" and not self.allowed_principals:
            raise ValueError("RESTRICTED_ASSET_REQUIRES_PRINCIPALS")
        if any(not value.strip() for value in self.allowed_principals):
            raise ValueError("EMPTY_ACCESS_PRINCIPAL")
        return self


class ClimateAsset(Contract):
    schema_version: Literal["climate-asset/1.0"] = "climate-asset/1.0"
    source_id: str
    dataset_id: str
    version: str
    source_uri: str
    sha256: Digest
    license: str = Field(min_length=1, max_length=1000)
    acquired_at: AwareDatetime
    available_at: AwareDatetime
    availability_evidence_uri: str | None = None
    availability_evidence_sha256: Digest | None = None
    observed_or_projected: Literal["observed", "projected"]
    model: str = Field(min_length=1, max_length=128)
    scenario: str = Field(min_length=1, max_length=128)
    variable: str = Field(min_length=1, max_length=128)
    unit: str = Field(min_length=1, max_length=128)
    temporal_method: Literal["mean", "sum", "point", "mean_rate"]
    spatial_coverage: SpatialCoverage
    time_coverage: CFTimeCoverage
    grid: Grid
    crs: str = Field(pattern=r"^EPSG:[1-9][0-9]*$")
    derived_from: tuple[LineageRef, ...]
    access: AccessPolicy
    trace_id: str = Field(min_length=1, max_length=256)

    _identifiers = field_validator("source_id", "dataset_id", "version")(token)
    _uri = field_validator("source_uri")(source_uri)

    @model_validator(mode="after")
    def coherent(self):
        if any(
            value.strip() != value or not value.strip()
            for value in (self.model, self.scenario, self.variable, self.unit)
        ):
            raise ValueError("EXPLICIT_NONBLANK_CLIMATE_SEMANTICS_REQUIRED")
        if self.model.lower() == "unknown":
            raise ValueError("MODEL_OR_OBSERVATIONAL_PRODUCT_REQUIRED")
        if self.license.strip().lower() in {"", "unknown", "tbd", "not_specified"}:
            raise ValueError("LICENSE_UNCONFIRMED")
        if self.observed_or_projected == "observed" and self.scenario != "not_applicable":
            raise ValueError("OBSERVATIONS_MUST_NOT_HAVE_SCENARIO")
        available = self.available_at.astimezone(timezone.utc)
        if self.observed_or_projected == "observed" and date_parts(
            self.time_coverage.end, self.time_coverage.calendar
        ) > (available.year, available.month, available.day):
            raise ValueError("OBSERVATIONS_AFTER_DECLARED_AVAILABILITY")
        if self.observed_or_projected == "projected":
            if self.model.strip().lower() in {
                "unknown",
                "not_applicable",
                "",
            } or self.scenario not in {
                "historical",
                "ssp126",
                "ssp245",
                "ssp370",
                "ssp585",
                "rcp26",
                "rcp45",
                "rcp60",
                "rcp85",
            }:
                raise ValueError("EXPLICIT_PROJECTION_MODEL_SCENARIO_REQUIRED")
        if self.available_at < self.acquired_at:
            if not self.availability_evidence_uri or not self.availability_evidence_sha256:
                raise ValueError("BACKDATED_AVAILABILITY_REQUIRES_RELEASE_EVIDENCE")
            source_uri(self.availability_evidence_uri)
        elif self.availability_evidence_uri:
            source_uri(self.availability_evidence_uri)
        west, south, east, north = self.spatial_coverage.bbox
        if self.crs == "EPSG:4326":
            if self.grid.unit != "degrees" or not (
                -180 <= west < east <= 180 and -90 <= south < north <= 90
            ):
                raise ValueError("GEOGRAPHIC_GRID_CRS_UNITS_OR_BOUNDS_INVALID")
        elif self.crs != "EPSG:6933" or self.grid.unit != "m":
            raise ValueError("UNSUPPORTED_CRS_OR_PROJECTED_GRID_UNITS")
        from math import isclose

        if not isclose(
            east - west, self.grid.width * self.grid.resolution_x, rel_tol=1e-9, abs_tol=1e-9
        ) or not isclose(
            north - south, self.grid.height * self.grid.resolution_y, rel_tol=1e-9, abs_tol=1e-9
        ):
            raise ValueError("GRID_SHAPE_RESOLUTION_EXTENT_MISMATCH")
        if any(
            ref.dataset_id == self.dataset_id and ref.version == self.version
            for ref in self.derived_from
        ):
            raise ValueError("SELF_REFERENTIAL_LINEAGE")
        return self
