"""경계 as-of·기후 calendar·native grid를 보존하는 실행 전 결합 계획."""

import math
from datetime import timezone
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from services.datahub.climate.calendars import date_parts, normalize_calendar, ordinal
from services.datahub.climate.models import (
    CFTimeCoverage,
    ClimateAsset,
    Contract,
    Digest,
    Positive,
    SpatialCoverage,
    token,
)
from services.datahub.climate.qc import check_asset, nominal_resolution_metres


class BoundaryVersion(Contract):
    boundary_id: str
    version: str
    sha256: Digest
    crs: str = Field(pattern=r"^EPSG:[1-9][0-9]*$")
    spatial_coverage: SpatialCoverage
    valid_from: AwareDatetime
    valid_to: AwareDatetime | None = None
    available_at: AwareDatetime
    authority_status: Literal["approved", "provisional", "unverified"]

    _identifiers = field_validator("boundary_id", "version")(token)

    @model_validator(mode="after")
    def ordered(self):
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("BOUNDARY_VALIDITY_REVERSED")
        return self


class FeatureJoinRequest(Contract):
    as_of: AwareDatetime
    feature_cutoff_date: str
    cutoff_calendar: str
    feature_window: CFTimeCoverage
    purpose: Literal["historical_training", "scenario_analysis"]
    principal: str = Field(min_length=1)
    requested_resolution_m: Positive | None = None
    aggregation: Literal["native_cell_candidates"] = "native_cell_candidates"

    _calendar = field_validator("cutoff_calendar", mode="before")(normalize_calendar)

    @model_validator(mode="after")
    def valid_cutoff(self):
        date_parts(self.feature_cutoff_date, self.cutoff_calendar)
        return self


def plan_climate_join(
    asset: ClimateAsset, boundary: BoundaryVersion, request: FeatureJoinRequest
) -> dict:
    qc = check_asset(asset)
    blockers = [error["reason"] for error in qc["errors"]]
    warnings = list(qc["warnings"])
    if (
        asset.access.visibility == "restricted"
        and request.principal not in asset.access.allowed_principals
    ):
        # 비인가 계획에는 dataset/boundary 상세 식별자나 값을 반환하지 않는다.
        return {"status": "BLOCKED", "blockers": ["ACCESS_DENIED"], "execution_started": False}
    if asset.available_at > request.as_of:
        blockers.append("CLIMATE_ASSET_NOT_AVAILABLE_AS_OF")
    if asset.derived_from:
        # 부모의 공개 시점·fit 기간을 모르면 간접 미래 누출이 해소됐다고 할 수 없다.
        blockers.append("PARENT_LINEAGE_AS_OF_RESOLUTION_REQUIRED")
    if (
        boundary.available_at > request.as_of
        or boundary.valid_from > request.as_of
        or boundary.valid_to is not None
        and request.as_of >= boundary.valid_to
    ):
        blockers.append("BOUNDARY_NOT_VALID_OR_AVAILABLE_AS_OF")
    if boundary.authority_status != "approved":
        warnings.append("BOUNDARY_AUTHORITY_NOT_APPROVED_DEVELOPMENT_ONLY")
    if asset.crs != boundary.crs:
        blockers.append("EXPLICIT_REPROJECTION_REQUIRED")
    calendar = asset.time_coverage.calendar
    if (
        normalize_calendar(request.cutoff_calendar) != calendar
        or request.feature_window.calendar != calendar
    ):
        blockers.append("CALENDAR_MISMATCH_NO_IMPLICIT_CONVERSION")
    else:
        cutoff = ordinal(request.feature_cutoff_date, calendar)
        start, end = (
            ordinal(request.feature_window.start, calendar),
            ordinal(request.feature_window.end, calendar),
        )
        if start < ordinal(asset.time_coverage.start, calendar) or end > ordinal(
            asset.time_coverage.end, calendar
        ):
            blockers.append("FEATURE_WINDOW_OUTSIDE_ASSET_COVERAGE")
        as_of_utc = request.as_of.astimezone(timezone.utc)
        if date_parts(request.feature_cutoff_date, calendar) > (
            as_of_utc.year,
            as_of_utc.month,
            as_of_utc.day,
        ):
            blockers.append("FEATURE_CUTOFF_AFTER_AS_OF")
        if asset.observed_or_projected == "observed" and end > cutoff:
            blockers.append("FUTURE_OBSERVATION_LEAKAGE")
        if request.purpose == "historical_training":
            if asset.observed_or_projected != "observed":
                blockers.append("PROJECTED_DATA_NOT_HISTORICAL_OBSERVATIONS")
    if request.purpose == "scenario_analysis" and asset.observed_or_projected == "projected":
        warnings.append("SCENARIO_ASSUMPTION_NOT_OBSERVED_GROUND_TRUTH")
    if (
        request.requested_resolution_m is not None
        and request.requested_resolution_m < nominal_resolution_metres(asset)
    ):
        warnings.append(
            "REQUESTED_FINER_RESOLUTION_REQUIRES_EXPLICIT_DOWNSCALING_NOT_NEW_OBSERVATIONS"
        )
    cells = None
    if asset.crs == boundary.crs:
        west, south, east, north = asset.spatial_coverage.bbox
        bw, bs, be, bn = boundary.spatial_coverage.bbox
        left, bottom, right, top = max(west, bw), max(south, bs), min(east, be), min(north, bn)
        if left >= right or bottom >= top:
            blockers.append("NO_SPATIAL_INTERSECTION")
        else:
            row_start = (
                (north - top) if asset.grid.row_order == "north_to_south" else (bottom - south)
            )
            row_stop = (
                (north - bottom) if asset.grid.row_order == "north_to_south" else (top - south)
            )
            cells = {
                "column_start": max(0, math.floor((left - west) / asset.grid.resolution_x)),
                "column_stop": min(
                    asset.grid.width, math.ceil((right - west) / asset.grid.resolution_x)
                ),
                "row_start": max(0, math.floor(row_start / asset.grid.resolution_y)),
                "row_stop": min(asset.grid.height, math.ceil(row_stop / asset.grid.resolution_y)),
                "stop_exclusive": True,
            }
    return {
        "status": "BLOCKED" if blockers else "PLANNED",
        "blockers": blockers,
        "warnings": warnings,
        "execution_started": False,
        "numeric_features": None,
        "scientific_validation": False,
        "dataset_ref": {
            "dataset_id": asset.dataset_id,
            "version": asset.version,
            "sha256": asset.sha256,
        },
        "boundary_ref": {
            "boundary_id": boundary.boundary_id,
            "version": boundary.version,
            "sha256": boundary.sha256,
        },
        "as_of": request.as_of.isoformat(),
        "calendar": calendar,
        "scenario": asset.scenario,
        "model": asset.model,
        "unit": asset.unit,
        "variable": asset.variable,
        "native_grid_cell_candidates": cells if not blockers else None,
        "spatial_method": "bbox candidate windows only; polygon intersection/area weighting not executed",
        "native_resolution_preserved": True,
        "trace_id": asset.trace_id,
    }
