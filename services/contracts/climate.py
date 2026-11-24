"""Fail-closed contracts shared by climate lake, GeoAI and Climate RAG.

The contract deliberately separates numeric climate queries from narrative
knowledge retrieval. Numeric facts must be produced by a structured data tool.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ObservationKind(StrEnum):
    OBSERVED = "observed"
    PROJECTED = "projected"
    DERIVED = "derived"


class QueryRoute(StrEnum):
    STRUCTURED_CLIMATE_TOOL = "structured_climate_tool"
    KNOWLEDGE_RAG = "knowledge_rag"


class SpatialCoverage(StrictModel):
    geography_ids: tuple[str, ...] = Field(min_length=1)
    bbox_wgs84: tuple[float, float, float, float] | None = None
    grid_resolution_degrees: float | None = Field(default=None, gt=0)
    crs: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_bbox(self) -> "SpatialCoverage":
        if self.bbox_wgs84 is None:
            return self
        west, south, east, north = self.bbox_wgs84
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("bbox_wgs84 must be ordered and inside WGS84 bounds")
        return self


class TimeCoverage(StrictModel):
    start: date
    end: date
    calendar: Literal[
        "standard",
        "gregorian",
        "proleptic_gregorian",
        "360_day",
        "365_day",
        "noleap",
        "366_day",
        "all_leap",
        "julian",
    ]

    @model_validator(mode="after")
    def validate_order(self) -> "TimeCoverage":
        if self.end < self.start:
            raise ValueError("time coverage end must not precede start")
        return self


class AccessPolicy(StrictModel):
    visibility: Literal["public", "restricted", "private"]
    allowed_roles: tuple[str, ...] = ()

    @model_validator(mode="after")
    def restricted_requires_roles(self) -> "AccessPolicy":
        if self.visibility != "public" and not self.allowed_roles:
            raise ValueError("restricted/private assets require allowed_roles")
        return self


class AssetLineage(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    source_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source_uri: HttpUrl
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    license: str = Field(min_length=1)
    acquired_at: datetime
    observed_or_projected: ObservationKind
    variable: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    spatial_coverage: SpatialCoverage
    time_coverage: TimeCoverage
    grid: str = Field(min_length=1)
    crs: str = Field(min_length=1)
    access: AccessPolicy
    trace_id: str = Field(min_length=1)
    model: str | None = None
    scenario: str | None = None
    derived_from: tuple[str, ...] = ()
    etag: str | None = None

    @model_validator(mode="after")
    def projection_semantics(self) -> "AssetLineage":
        if self.acquired_at.tzinfo is None or self.acquired_at.utcoffset() is None:
            raise ValueError("acquired_at must include a timezone")
        if self.observed_or_projected == ObservationKind.PROJECTED:
            if not self.model or not self.scenario:
                raise ValueError("projected assets require both model and scenario")
        elif self.scenario is not None:
            raise ValueError("scenario is only valid for projected assets")
        if self.crs != self.spatial_coverage.crs:
            raise ValueError("asset CRS and spatial coverage CRS must match")
        return self


class ClimateQuery(StrictModel):
    query_text: str = Field(min_length=1)
    language: Literal["ko", "id", "en"]
    route: QueryRoute
    geography_ids: tuple[str, ...] = Field(min_length=1)
    start: date | None = None
    end: date | None = None
    variable: str | None = None
    scenario: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def numeric_route_requires_slots(self) -> "ClimateQuery":
        if (self.start is None) != (self.end is None):
            raise ValueError("start and end must be provided together")
        if self.start and self.end and self.end < self.start:
            raise ValueError("query end must not precede start")
        if self.route == QueryRoute.STRUCTURED_CLIMATE_TOOL:
            if self.variable is None or self.start is None:
                raise ValueError("structured climate queries require variable and time range")
        return self


class EvidenceCitation(StrictModel):
    source_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source_uri: HttpUrl
    source_span: str = Field(min_length=1)
    authority: str = Field(min_length=1)
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class CanonicalResult(StrictModel):
    trace_id: str = Field(min_length=1)
    route: QueryRoute
    status: Literal["ok", "insufficient_evidence", "forbidden", "failed"]
    answer: str
    citations: tuple[EvidenceCitation, ...] = ()
    numeric_payload: dict[str, Any] | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_result_evidence(self) -> "CanonicalResult":
        if self.status == "ok" and not self.citations:
            raise ValueError("successful results require at least one citation")
        if self.numeric_payload is not None and self.route != QueryRoute.STRUCTURED_CLIMATE_TOOL:
            raise ValueError("numeric payload is forbidden for knowledge RAG results")
        return self
