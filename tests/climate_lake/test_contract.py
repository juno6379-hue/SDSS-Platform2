"""합성 메타데이터/수치만 시험하며 실제 CCKP 수신·과학 검증을 주장하지 않는다."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from services.datahub.climate import (
    CFTimeCoverage,
    ClimateAsset,
    check_asset,
    convert_value,
    lake_paths,
    raw_receipt_gate,
)
from services.datahub.climate.calendars import ordinal, period_days
from services.datahub.climate.lake import require_curated_lineage


class ClimateLakeTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(
            (Path(__file__).parent / "fixtures/asset.json").read_text(encoding="utf-8")
        )

    def test_pydantic_v2_schema_roundtrip_and_frozen_extra_forbid(self):
        asset = ClimateAsset.model_validate(self.raw)
        self.assertEqual(ClimateAsset.model_validate_json(asset.model_dump_json()), asset)
        self.assertIn("derived_from", ClimateAsset.model_json_schema()["properties"])
        with self.assertRaises(ValidationError):
            ClimateAsset.model_validate({**self.raw, "numeric_fact_from_rag": 42})
        with self.assertRaises(ValidationError):
            asset.unit = "mm"

    def test_calendar_specific_february_and_leap_rules(self):
        self.assertEqual(period_days("2020-01-01", "2020-12-30", "360_day"), 360)
        self.assertEqual(period_days("2020-01-01", "2020-12-31", "noleap"), 365)
        self.assertEqual(period_days("2020-01-01", "2020-12-31", "standard"), 366)
        ordinal("2020-02-30", "360_day")
        ordinal("1900-02-29", "julian")
        ordinal("2019-02-29", "all_leap")
        for date, calendar in [
            ("2020-02-29", "noleap"),
            ("1900-02-29", "proleptic_gregorian"),
            ("2020-01-31", "360_day"),
            ("1582-10-15", "standard"),
        ]:
            with self.subTest(date=date, calendar=calendar), self.assertRaises(ValueError):
                ordinal(date, calendar)

    def test_calendar_aliases_and_unsupported_time_units_fail_closed(self):
        for alias, expected in [
            ("365_day", "noleap"),
            ("366_day", "all_leap"),
            ("GREGORIAN", "standard"),
        ]:
            coverage = CFTimeCoverage(
                calendar=alias,
                start="2020-01-01",
                end="2020-01-02",
                time_units="days since 1850-01-01",
                frequency="daily",
            )
            self.assertEqual(coverage.calendar, expected)
        for changes in [
            {"calendar": "none"},
            {"time_units": "months since 1850-01-01"},
            {"start": "2021-01-01", "end": "2020-12-31"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                CFTimeCoverage.model_validate({**self.raw["time_coverage"], **changes})

    def test_projection_requires_scenario_model_and_does_not_become_observed(self):
        for changes in [
            {"observed_or_projected": "projected"},
            {"scenario": "ssp245"},
            {"model": "unknown"},
            {"scenario": " "},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ClimateAsset.model_validate({**self.raw, **changes})
        asset = ClimateAsset.model_validate(
            {
                **self.raw,
                "observed_or_projected": "projected",
                "scenario": "ssp245",
                "model": "synthetic-cmip6-model",
            }
        )
        self.assertEqual(asset.observed_or_projected, "projected")

    def test_no_naive_time_unknown_license_mutable_version_or_signed_uri(self):
        for changes in [
            {"acquired_at": "2021-01-01"},
            {"license": "unknown"},
            {"version": "latest"},
            {"source_uri": "https://example.invalid/a?token=must-not-log"},
            {"dataset_id": "../escape"},
            {"dataset_id": "CON"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ClimateAsset.model_validate({**self.raw, **changes})

    def test_backdated_availability_needs_explicit_release_evidence(self):
        with self.assertRaises(ValidationError):
            ClimateAsset.model_validate({**self.raw, "available_at": "2020-01-01T00:00:00Z"})
        asset = ClimateAsset.model_validate(
            {
                **self.raw,
                "available_at": "2020-12-31T12:00:00Z",
                "availability_evidence_uri": "https://example.invalid/synthetic-release",
                "availability_evidence_sha256": "c" * 64,
            }
        )
        self.assertLess(asset.available_at, asset.acquired_at)

    def test_future_observations_cannot_be_declared_already_available(self):
        with self.assertRaises(ValidationError):
            ClimateAsset.model_validate(
                {**self.raw, "time_coverage": {**self.raw["time_coverage"], "end": "2040-12-31"}}
            )

    def test_grid_extent_crs_and_resolution_cannot_be_silently_changed(self):
        for changes in [
            {"grid": {**self.raw["grid"], "width": 3}},
            {"grid": {**self.raw["grid"], "unit": "m"}},
            {"grid": {**self.raw["grid"], "resolution_x": float("nan")}},
            {"spatial_coverage": {"bbox": [104.0, -8.0, 100.0, -4.0]}},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ClimateAsset.model_validate({**self.raw, **changes})

    def test_unknown_dimension_and_precipitation_statistic_blocked(self):
        for changes in [
            {"unit": "mm"},
            {"variable": "invented-index"},
            {"variable": "pr", "unit": "mm", "temporal_method": "mean"},
        ]:
            result = check_asset({**self.raw, **changes})
            self.assertEqual(result["status"], "BLOCKED")
        result = check_asset(self.raw)
        self.assertTrue(result["metadata_valid"])
        self.assertFalse(result["numeric_values_verified"])
        self.assertIn("COARSE_NATIVE_GRID_NOT_SENTINEL_2_10M_OBSERVATIONS", result["warnings"])

    def test_scalar_conversion_and_cf_period_water_equivalent(self):
        self.assertAlmostEqual(convert_value(300, "tas", "K", "degC")["value"], 26.85)
        self.assertEqual(convert_value(101300, "ps", "Pa", "hPa")["value"], 1013)
        self.assertEqual(convert_value(0.8, "hurs", "1", "%")["value"], 80)
        period = CFTimeCoverage(
            calendar="360_day",
            start="2020-02-01",
            end="2020-02-30",
            time_units="days since 1850-01-01",
            frequency="monthly",
        )
        self.assertEqual(
            convert_value(1, "pr", "mm day-1", "mm", period=period, temporal_method="mean_rate")[
                "value"
            ],
            30,
        )
        self.assertEqual(
            convert_value(
                1 / 86400, "pr", "kg m-2 s-1", "mm", period=period, temporal_method="mean_rate"
            )["value"],
            30,
        )
        for args in [
            (float("nan"), "tas", "K", "degC"),
            (-1, "pr", "mm", "mm"),
            (2, "hurs", "1", "%"),
            (300, "tas", "K", "mm"),
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                convert_value(*args)
        with self.assertRaises(ValueError):
            convert_value(1, "pr", "mm day-1", "mm", temporal_method="mean_rate")

    def test_lake_paths_are_confined_content_versioned_and_do_not_write(self):
        asset = ClimateAsset.model_validate(self.raw)
        with tempfile.TemporaryDirectory() as directory:
            paths = lake_paths(asset, Path(directory))
            self.assertTrue(all(Path(p).is_relative_to(Path(directory)) for p in paths.values()))
            self.assertTrue(all(asset.sha256 in p for p in paths.values()))
            self.assertEqual(list(Path(directory).iterdir()), [])
            with self.assertRaises(ValueError):
                lake_paths(asset, Path(directory), "../../escape")
        with self.assertRaises(ValueError):
            require_curated_lineage(asset, check_asset(asset))

    def test_partial_raw_receipt_is_preserved_and_never_duck_cast(self):
        receipt = {
            "schema_version": "cckp-raw-receipt/1.0",
            "unit": None,
            "calendar": None,
            "model": None,
            "scenario": None,
            "observed_or_projected": None,
            "grid": None,
            "crs": None,
        }
        original = copy.deepcopy(receipt)
        self.assertEqual(raw_receipt_gate(receipt)["code"], "CLIM_METADATA_MISSING")
        self.assertFalse(check_asset(receipt)["metadata_valid"])
        self.assertEqual(receipt, original)


if __name__ == "__main__":
    unittest.main()
