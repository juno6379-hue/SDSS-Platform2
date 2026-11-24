"""climate.query 수치 요청 계약. 원본/모델 경로를 사용자 입력으로 받지 않는다."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from services.datahub.climate.calendars import normalize_calendar, period_days
from services.datahub.climate.models import SpatialCoverage


class QueryTime(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    start: str
    end: str
    calendar: str
    _calendar = field_validator("calendar", mode="before")(normalize_calendar)

    @model_validator(mode="after")
    def period(self):
        period_days(self.start, self.end, self.calendar)
        return self


class QueryGeography(SpatialCoverage):
    geography_id: str = Field(min_length=1, max_length=128)
    method: Literal["bbox_cell_centers"]

    @model_validator(mode="after")
    def geographic(self):
        w, s, e, n = self.bbox
        if not -180 <= w < e <= 180 or not -90 <= s < n <= 90:
            raise ValueError("INVALID_GEOGRAPHIC_BBOX")
        return self


class ClimateQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    geography: QueryGeography
    time: QueryTime
    variable: str = Field(min_length=1)
    observed_or_projected: Literal["observed", "projected"]
    model: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    aggregation: Literal["bbox_cell_mean", "bbox_area_weighted_mean", "bbox_min", "bbox_max"]
    unit: str = Field(min_length=1)


def tool_contract():
    return {
        "name": "climate.query",
        "description": "검증된 원본 grid의 명시 bbox/기간 통계. RAG 숫자 생성 금지.",
        "input_schema": ClimateQueryRequest.model_json_schema(),
        "read_only": True,
        "source": "configured pinned local NetCDF + receipt; not user-supplied arbitrary URL",
    }
