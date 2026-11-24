from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from services.contracts.climate import (
    AccessPolicy,
    AssetLineage,
    CanonicalResult,
    ClimateQuery,
    EvidenceCitation,
    ObservationKind,
    QueryRoute,
    SpatialCoverage,
    TimeCoverage,
)


def _coverage() -> SpatialCoverage:
    return SpatialCoverage(
        geography_ids=("IDN",),
        bbox_wgs84=(95.0, -11.0, 141.0, 6.0),
        grid_resolution_degrees=0.25,
        crs="EPSG:4326",
    )


def _lineage(**updates: object) -> AssetLineage:
    payload = {
        "source_id": "worldbank-cckp",
        "dataset_id": "cmip6-x0.25-tas",
        "version": "2026-11-24-inventory",
        "source_uri": "https://example.org/tas.nc",
        "sha256": "a" * 64,
        "license": "SOURCE_ASSET_LICENSE_MUST_BE_RECORDED",
        "acquired_at": datetime(2026, 11, 24, tzinfo=timezone.utc),
        "observed_or_projected": ObservationKind.OBSERVED,
        "variable": "tas",
        "unit": "K",
        "spatial_coverage": _coverage(),
        "time_coverage": TimeCoverage(
            start=date(1950, 1, 1), end=date(2022, 12, 31), calendar="standard"
        ),
        "grid": "x0.25",
        "crs": "EPSG:4326",
        "access": AccessPolicy(visibility="public"),
        "trace_id": "trace-1",
    }
    payload.update(updates)
    return AssetLineage.model_validate(payload)


def test_projected_asset_requires_model_and_scenario() -> None:
    with pytest.raises(ValidationError, match="model and scenario"):
        _lineage(observed_or_projected="projected")


def test_observed_asset_rejects_scenario() -> None:
    with pytest.raises(ValidationError, match="only valid for projected"):
        _lineage(scenario="ssp245")


def test_lineage_accepts_cf_calendar_and_timezone() -> None:
    item = _lineage(
        observed_or_projected="projected",
        model="access-cm2",
        scenario="ssp245",
        time_coverage={"start": "2015-01-01", "end": "2100-12-30", "calendar": "360_day"},
    )
    assert item.time_coverage.calendar == "360_day"


def test_numeric_query_requires_structured_slots() -> None:
    with pytest.raises(ValidationError, match="variable and time range"):
        ClimateQuery(
            query_text="2040년 인도네시아 평균기온은?",
            language="ko",
            route="structured_climate_tool",
            geography_ids=("IDN",),
        )


def test_rag_cannot_return_numeric_payload() -> None:
    citation = EvidenceCitation(
        source_id="worldbank-cckp",
        dataset_id="documentation",
        version="main",
        source_uri="https://github.com/worldbank/climateknowledgeportal",
        source_span="README collections section",
        authority="World Bank",
    )
    with pytest.raises(ValidationError, match="forbidden for knowledge RAG"):
        CanonicalResult(
            trace_id="trace-2",
            route=QueryRoute.KNOWLEDGE_RAG,
            status="ok",
            answer="금지된 수치 응답",
            citations=(citation,),
            numeric_payload={"value": 1.0},
        )
