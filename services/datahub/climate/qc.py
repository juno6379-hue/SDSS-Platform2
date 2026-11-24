"""허용된 변수·단위만 검사/변환한다. 데이터 값을 RAG나 메타데이터에서 추정하지 않는다."""

import math

from pydantic import ValidationError

from .calendars import period_days
from .models import CFTimeCoverage, ClimateAsset

UNITS = {
    "tas": {"K", "degC"},
    "tasmin": {"K", "degC"},
    "tasmax": {"K", "degC"},
    "pr": {"kg m-2 s-1", "mm day-1", "mm"},
    "ps": {"Pa", "hPa"},
    "hurs": {"1", "%"},
    "sfcWind": {"m s-1"},
}


def raw_receipt_gate(receipt: dict) -> dict:
    """원천 RAW receipt는 보존하고 미확인 기후 의미를 추정/duck-cast하지 않는다."""
    required = ("unit", "calendar", "model", "scenario", "observed_or_projected", "grid", "crs")
    missing = [
        field for field in required if receipt.get(field) is None or receipt.get(field) == ""
    ]
    return {
        "status": "BLOCKED",
        "code": "CLIM_METADATA_MISSING" if missing else "EXPLICIT_NORMALIZATION_ADAPTER_REQUIRED",
        "missing_fields": missing,
        "raw_receipt_preserved": True,
        "feature_generation_allowed": False,
        "numeric_values_verified": False,
    }


def nominal_resolution_metres(asset: ClimateAsset) -> float:
    spacing = max(asset.grid.resolution_x, asset.grid.resolution_y)
    return spacing * 111320 if asset.grid.unit == "degrees" else spacing


def check_asset(value: ClimateAsset | dict) -> dict:
    if isinstance(value, dict) and value.get("schema_version") == "cckp-raw-receipt/1.0":
        return {
            **raw_receipt_gate(value),
            "metadata_valid": False,
            "errors": [{"field": "raw_receipt", "reason": "RAW_RECEIPT_IS_NOT_CLIMATE_ASSET"}],
            "warnings": [],
        }
    try:
        asset = value if isinstance(value, ClimateAsset) else ClimateAsset.model_validate(value)
    except ValidationError as error:
        return {
            "status": "BLOCKED",
            "metadata_valid": False,
            "errors": [
                {"field": ".".join(map(str, item["loc"])), "reason": item["msg"]}
                for item in error.errors(include_input=False)
            ],
            "warnings": [],
            "numeric_values_verified": False,
        }
    errors = []
    if asset.variable not in UNITS or asset.unit not in UNITS[asset.variable]:
        errors.append({"field": "unit", "reason": "UNKNOWN_VARIABLE_OR_INCOMPATIBLE_UNIT"})
    if asset.variable == "pr":
        if asset.unit in {"kg m-2 s-1", "mm day-1"} and asset.temporal_method != "mean_rate":
            errors.append(
                {"field": "temporal_method", "reason": "PRECIPITATION_RATE_REQUIRES_MEAN_RATE"}
            )
        if asset.unit == "mm" and asset.temporal_method != "sum":
            errors.append(
                {"field": "temporal_method", "reason": "PRECIPITATION_AMOUNT_REQUIRES_SUM"}
            )
    warnings = []
    if nominal_resolution_metres(asset) >= 1000:
        warnings.append("COARSE_NATIVE_GRID_NOT_SENTINEL_2_10M_OBSERVATIONS")
    return {
        "status": "BLOCKED" if errors else "IMPLEMENTED_UNVERIFIED",
        "metadata_valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "native_resolution_nominal_m": nominal_resolution_metres(asset),
        "numeric_values_verified": False,
        "independent_accuracy_validated": False,
        "resolution_interpretation": "degrees use nominal equatorial scale; exact ground area not computed",
    }


def convert_value(
    value: float,
    variable: str,
    from_unit: str,
    to_unit: str,
    *,
    period: CFTimeCoverage | None = None,
    temporal_method: str | None = None,
) -> dict:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("FINITE_NUMERIC_VALUE_REQUIRED")
    if variable not in UNITS or from_unit not in UNITS[variable] or to_unit not in UNITS[variable]:
        raise ValueError("INCOMPATIBLE_VARIABLE_UNITS")
    assumptions = []
    if variable in {"tas", "tasmin", "tasmax"}:
        if from_unit == "K" and value < 0 or from_unit == "degC" and value < -273.15:
            raise ValueError("TEMPERATURE_BELOW_ABSOLUTE_ZERO")
        result = (
            value
            if from_unit == to_unit
            else value - 273.15
            if from_unit == "K"
            else value + 273.15
        )
    elif variable == "pr":
        if value < 0:
            raise ValueError("NEGATIVE_PRECIPITATION")
        if (
            from_unit == "mm"
            and temporal_method != "sum"
            or from_unit != "mm"
            and temporal_method != "mean_rate"
        ):
            raise ValueError("EXPLICIT_PRECIPITATION_TEMPORAL_METHOD_REQUIRED")
        if from_unit == to_unit:
            result = value
        else:
            if "mm" in {from_unit, to_unit} and period is None:
                raise ValueError("CF_PERIOD_REQUIRED_FOR_RATE_AMOUNT_CONVERSION")
            duration = period_days(period.start, period.end, period.calendar) if period else 1
            rate = (
                value / duration
                if from_unit == "mm"
                else value * 86400
                if from_unit == "kg m-2 s-1"
                else value
            )
            result = (
                rate * duration
                if to_unit == "mm"
                else rate / 86400
                if to_unit == "kg m-2 s-1"
                else rate
            )
            assumptions = [
                "water-equivalent 1 kg m-2 = 1 mm",
                "CF day = 86400 seconds",
                "period mean rate or period sum explicitly declared",
            ]
    elif variable == "ps":
        if value <= 0:
            raise ValueError("PRESSURE_MUST_BE_POSITIVE")
        result = (
            value if from_unit == to_unit else value / 100 if from_unit == "Pa" else value * 100
        )
    elif variable == "hurs":
        if not 0 <= value <= (1 if from_unit == "1" else 100):
            raise ValueError("HUMIDITY_OUT_OF_RANGE")
        result = value if from_unit == to_unit else value * 100 if from_unit == "1" else value / 100
    else:
        if value < 0:
            raise ValueError("NEGATIVE_WIND_SPEED")
        result = value
    if not math.isfinite(result):
        raise ValueError("CONVERSION_OVERFLOW")
    return {
        "value": result,
        "unit": to_unit,
        "source_unit": from_unit,
        "calendar": period.calendar if period else None,
        "assumptions": assumptions,
    }
