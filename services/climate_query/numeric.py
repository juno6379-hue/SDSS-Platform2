"""원본 SHA/내부 CF/공식 라이선스 근거가 일치할 때만 grid bbox 수치를 계산한다."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from services.datahub.climate.calendars import normalize_calendar, validate_time_units

from .global_asset import CAP, LICENSE_URI, sha_file
from .models import ClimateQueryRequest


def blocked(code, detail=None):
    return {
        "tool": "climate.query",
        "status": "BLOCKED",
        "value": None,
        "blockers": [code],
        "detail": detail,
        "citations": [],
        "training_executed": False,
    }


def _attrs(obj):
    result = {}
    for name in obj.ncattrs():
        value = obj.getncattr(name)
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="strict")
        result[name] = value
    return result


def inspect_netcdf(path, expected_sha256):
    """수치 요청과 분리한 실제 원본 메타데이터 파서. 파일명에서 기간을 만들지 않는다."""
    import numpy as np
    from netCDF4 import Dataset, num2date

    path = Path(path)
    if path.stat().st_size > CAP or sha_file(path) != expected_sha256:
        raise ValueError("RAW_SHA_OR_SIZE_MISMATCH")
    with Dataset(path, "r") as dataset:
        if len(dataset.variables) > 128:
            raise ValueError("TOO_MANY_VARIABLES")
        attrs = _attrs(dataset)
        variables = {
            name: {
                "dimensions": list(var.dimensions),
                "shape": list(var.shape),
                "dtype": str(var.dtype),
                "attributes": _attrs(var),
            }
            for name, var in dataset.variables.items()
        }
        for name in ("lat", "lon", "time"):
            if (
                name not in dataset.variables
                or dataset[name].ndim != 1
                or dataset[name].size > 1000000
            ):
                raise ValueError("MISSING_OR_UNSUPPORTED_" + name.upper() + "_COORDINATE")
        time = dataset["time"]
        calendar = getattr(time, "calendar", None)
        units = getattr(time, "units", None)
        if not calendar or not units:
            raise ValueError("CF_CALENDAR_OR_TIME_UNITS_MISSING")
        canonical_calendar = normalize_calendar(calendar)
        validate_time_units(units, canonical_calendar)
        decoded = num2date(time[:], units, calendar=calendar, only_use_cftime_datetimes=True)
        coordinates = {}
        for name in ("lat", "lon"):
            values = np.ma.asarray(dataset[name][:])
            if np.ma.getmaskarray(values).any() or not np.isfinite(values).all() or values.size < 2:
                raise ValueError("INVALID_COORDINATE_VALUES")
            steps = np.diff(values)
            if not (np.all(steps > 0) or np.all(steps < 0)) or not np.allclose(
                steps, steps[0], rtol=0, atol=1e-8
            ):
                raise ValueError("NON_RECTILINEAR_COORDINATES_UNSUPPORTED")
            required_units = "degrees_north" if name == "lat" else "degrees_east"
            if getattr(dataset[name], "units", "") != required_units:
                raise ValueError("COORDINATE_UNITS_UNVERIFIED")
            coordinates[name] = {
                "count": values.size,
                "first": float(values[0]),
                "last": float(values[-1]),
                "resolution_degrees": abs(float(steps[0])),
                "units": required_units,
            }
        metadata = {
            "file_format": dataset.data_model,
            "global_attributes": attrs,
            "variables": variables,
            "coordinates": coordinates,
            "calendar_raw": calendar,
            "calendar": canonical_calendar,
            "time_units": units,
            "decoded_time_coordinates": [str(item) for item in np.atleast_1d(decoded)],
            "raw_sha256": expected_sha256,
            "inspected_at": datetime.now(timezone.utc).isoformat(),
            "file_license_attribute": attrs.get("license"),
            "numeric_query_executed": False,
        }
    if sha_file(path) != expected_sha256:
        raise ValueError("RAW_CHANGED_DURING_INSPECTION")
    return metadata


def climate_query(
    request,
    raw_path,
    receipt_path,
    *,
    license_evidence_path=None,
    license_evidence_sha256=None,
    allow_fixture=False,
):
    try:
        request = ClimateQueryRequest.model_validate(request)
    except ValidationError as error:
        return blocked(
            "INVALID_QUERY",
            [{"field": ".".join(map(str, e["loc"])), "type": e["type"]} for e in error.errors()],
        )
    try:
        import numpy as np
        from netCDF4 import Dataset

        receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        fixture = receipt.get("fixture_only") is True
        if fixture and not allow_fixture:
            return blocked("SYNTHETIC_NOT_REAL")
        if not fixture and not receipt.get("source_uri", "").startswith(
            "s3://wbg-cckp/data/era5-x0.25/"
        ):
            return blocked("UNVERIFIED_SOURCE_RECEIPT")
        if not fixture:
            seal_path = Path(receipt_path).parent / "receipt-seal.json"
            if not seal_path.is_file() or json.loads(seal_path.read_text(encoding="utf-8")).get(
                "receipt_sha256"
            ) != sha_file(receipt_path):
                return blocked("RECEIPT_SEAL_MISSING_OR_DRIFT")
        path = Path(raw_path)
        metadata = inspect_netcdf(path, receipt["sha256"])
        if not license_evidence_path or sha_file(license_evidence_path) != license_evidence_sha256:
            return blocked("LICENSE_EVIDENCE_MISSING_OR_STALE")
        evidence = json.loads(Path(license_evidence_path).read_text(encoding="utf-8"))
        if (
            evidence.get("status") != "VERIFIED_REAL_CATALOGUE_LICENSE"
            or evidence.get("license") != "CC-BY-4.0"
            or evidence.get("source_uri") != LICENSE_URI
            or evidence.get("dataset_family") != "ERA5"
        ):
            return blocked("LICENSE_OR_DATASET_FAMILY_UNCONFIRMED")
        attrs = metadata["global_attributes"]
        if metadata["file_license_attribute"] not in (None, "CC-BY-4.0"):
            return blocked("FILE_LICENSE_REQUIRES_REVIEW")
        if (
            attrs.get("wb_model_label") != "era5"
            or attrs.get("wb_collection_label") != "era5-x0.25"
            or attrs.get("wb_scenario_label") != "historical"
        ):
            return blocked("UNSUPPORTED_MODEL_SCENARIO_OR_COLLECTION")
        if (
            request.observed_or_projected != "observed"
            or request.model != "era5"
            or request.scenario != "not_applicable"
        ):
            return blocked("QUERY_ROLE_MODEL_SCENARIO_MISMATCH")
        period = attrs.get("wb_period_label")
        with Dataset(path, "r") as dataset:
            if getattr(dataset["time"], "climatology_period", None) != period or not re.fullmatch(
                r"\d{4}-\d{4}", str(period)
            ):
                return blocked("CLIMATOLOGY_INTERVAL_NOT_VERIFIED_IN_METADATA")
            first, last = period.split("-")
            end_day = "30" if metadata["calendar"] == "360_day" else "31"
            if (request.time.start, request.time.end, request.time.calendar) != (
                first + "-01-01",
                last + "-12-" + end_day,
                metadata["calendar"],
            ):
                return blocked("CLIMATOLOGY_PERIOD_MISMATCH_NO_ANNUAL_VALUES_INFERRED")
            if attrs.get("wb_type_label") != "climatology" or dataset["time"].size != 1:
                return blocked("ONLY_SINGLE_PERIOD_CLIMATOLOGY_IMPLEMENTED")
            variable_names = [
                name
                for name, var in dataset.variables.items()
                if var.dimensions == ("time", "lat", "lon")
            ]
            if len(variable_names) != 1 or request.variable != attrs.get("wb_variable_label"):
                return blocked("VARIABLE_NOT_EXACTLY_IDENTIFIED")
            variable = dataset[variable_names[0]]
            unit = getattr(variable, "units", None)
            if not unit or request.unit != unit:
                return blocked("UNIT_MISMATCH_NO_IMPLICIT_CONVERSION")
            if variable.size > 10000000:
                return blocked("GRID_CELL_BUDGET_EXCEEDED")
            lat, lon = np.asarray(dataset["lat"][:]), np.asarray(dataset["lon"][:])
            normalized_lon = ((lon + 180) % 360) - 180
            west, south, east, north = request.geography.bbox
            y = np.flatnonzero((lat >= south) & (lat <= north))
            x = np.flatnonzero((normalized_lon >= west) & (normalized_lon <= east))
            if not len(x) or not len(y):
                return blocked("NO_GRID_CENTERS_IN_BBOX")
            if (
                len(x) * len(y) > 200000
                or not np.all(np.diff(x) == 1)
                or not np.all(np.diff(y) == 1)
            ):
                return blocked("SUBSET_SIZE_OR_WRAPPED_WINDOW_UNSUPPORTED")
            variable.set_auto_maskandscale(True)
            data = np.ma.masked_invalid(variable[0, y[0] : y[-1] + 1, x[0] : x[-1] + 1])
            valid = ~np.ma.getmaskarray(data)
            if not valid.any():
                return blocked("NO_VALID_NUMERIC_GRID_VALUES")
            values = data.compressed().astype("float64")
            method = request.aggregation
            if method == "bbox_area_weighted_mean":
                lat_bounds_name = getattr(dataset["lat"], "bounds", None)
                lon_bounds_name = getattr(dataset["lon"], "bounds", None)
                if (
                    lat_bounds_name not in dataset.variables
                    or lon_bounds_name not in dataset.variables
                ):
                    return blocked("CELL_BOUNDS_REQUIRED_FOR_AREA_WEIGHTING")
                lb = np.asarray(dataset[lat_bounds_name][y, :])
                xb = np.asarray(dataset[lon_bounds_name][x, :])
                weights = (
                    abs(np.sin(np.deg2rad(lb[:, 1])) - np.sin(np.deg2rad(lb[:, 0])))[:, None]
                    * abs(np.deg2rad(xb[:, 1] - xb[:, 0]))[None, :]
                )
                if (
                    weights.shape != data.shape
                    or not np.isfinite(weights).all()
                    or not (weights > 0).all()
                ):
                    return blocked("INVALID_CELL_AREA_WEIGHTS")
                value = float(np.average(np.asarray(data)[valid], weights=weights[valid]))
            elif method == "bbox_min":
                value = float(values.min())
            elif method == "bbox_max":
                value = float(values.max())
            else:
                value = float(values.mean())
            source_variable_attrs = _attrs(variable)
        if not np.isfinite(value) or sha_file(path) != receipt["sha256"]:
            return blocked("NONFINITE_RESULT_OR_SOURCE_DRIFT")
        return {
            "tool": "climate.query",
            "status": "TESTED_SYNTHETIC" if fixture else "VERIFIED_REAL",
            "value": value,
            "unit": unit,
            "aggregation": request.aggregation,
            "geography": request.geography.model_dump(),
            "geography_is_official_country_polygon": False,
            "time": request.time.model_dump(),
            "observed_or_projected": "observed",
            "data_role": "ERA5_REANALYSIS",
            "model": "era5",
            "scenario": "not_applicable",
            "source_scenario": "historical",
            "variable": request.variable,
            "netcdf_variable": variable_names[0],
            "grid_shape": list(data.shape),
            "valid_cells": int(valid.sum()),
            "selected_cells": int(data.size),
            "masked_cells": int(data.size - valid.sum()),
            "native_resolution_degrees": metadata["coordinates"]["lat"]["resolution_degrees"],
            "calendar": metadata["calendar"],
            "provenance": {
                "raw_sha256": receipt["sha256"],
                "acquired_at": receipt.get("acquired_at"),
                "local_content_version": "sha256:" + receipt["sha256"],
                "receipt_sha256": sha_file(receipt_path),
                "license_evidence_sha256": license_evidence_sha256,
                "source_uri": receipt["source_uri"],
                "etag": receipt.get("etag"),
                "etag_is_sha256": False,
                "trace_id": receipt["trace_id"],
                "source_variable_attributes": source_variable_attrs,
                "wb_statistic_label": attrs.get("wb_statistic_label"),
                "wb_percentile_label": attrs.get("wb_percentile_label"),
            },
            "citations": [
                {
                    "source_uri": receipt["source_uri"],
                    "sha256": receipt["sha256"],
                    "locator": variable_names[0] + "[time=0,selected lat/lon centers]",
                },
                {"source_uri": LICENSE_URI, "license": "CC-BY-4.0"},
                {
                    "source_uri": "https://cds.climate.copernicus.eu",
                    "institution": "ECMWF / Copernicus Climate Data Store",
                },
            ],
            "warnings": [
                "BBOX_GRID_STATISTIC_NOT_INDONESIA_ADMINISTRATIVE_MEAN",
                "ERA5_REANALYSIS_NOT_INDEPENDENT_GROUND_TRUTH",
                "COARSE_0_25_DEGREE_GRID_NOT_10M_OBSERVATIONS",
                "SOURCE_CLIMATOLOGY_FIELD_NO_ANNUAL_OR_MONTHLY_VALUES_INFERRED",
            ],
            "numeric_values_verified": True,
            "independent_accuracy_validated": False,
            "curated_asset_registered": False,
            "model_training_authorized": False,
            "training_executed": False,
        }
    except ImportError as error:
        return blocked("OPTIONAL_NETCDF_READER_DEPENDENCY_MISSING", type(error).__name__)
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        return blocked(
            "NETCDF_OR_RECEIPT_VALIDATION_FAILED", type(error).__name__ + ": " + str(error)[:240]
        )
