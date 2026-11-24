"""합성 NetCDF와 실원본 증거 시험은 분리한다. 이 파일은 합성 계약시험이다."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

from services.climate_query.global_asset import LICENSE_URI, sha_file
from services.climate_query.models import tool_contract
from services.climate_query.numeric import climate_query, inspect_netcdf


class NumericTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw = self.root / "synthetic.nc"
        with Dataset(self.raw, "w", format="NETCDF3_CLASSIC") as dataset:
            for name, size in [("time", 1), ("lat", 2), ("lon", 2), ("bnds", 2)]:
                dataset.createDimension(name, size)
            for name, value in {
                "Conventions": "CF-1.6",
                "wb_model_label": "era5",
                "wb_collection_label": "era5-x0.25",
                "wb_scenario_label": "historical",
                "wb_type_label": "climatology",
                "wb_period_label": "1951-1980",
                "wb_variable_label": "cdd",
            }.items():
                dataset.setncattr(name, value)
            time = dataset.createVariable("time", "f8", ("time",))
            time.units = "days since 1850-01-01 00:00:00"
            time.calendar = "gregorian"
            time.climatology_period = "1951-1980"
            time[:] = [40000]
            for name, values, unit in [
                ("lat", [60.0, 60.25], "degrees_north"),
                ("lon", [100.0, 100.25], "degrees_east"),
            ]:
                coord = dataset.createVariable(name, "f8", (name,))
                coord.units = unit
                coord.bounds = name + "_bnds"
                coord[:] = values
                bounds = dataset.createVariable(name + "_bnds", "f8", (name, "bnds"))
                bounds[:] = [[x - 0.125, x + 0.125] for x in values]
            variable = dataset.createVariable(
                "synthetic-cdd", "f4", ("time", "lat", "lon"), fill_value=1e20
            )
            variable.units = "days"
            variable[:] = [[[1.0, 3.0], [5.0, 7.0]]]
        self.receipt = self.root / "receipt.json"
        self.receipt.write_text(
            json.dumps(
                {
                    "fixture_only": True,
                    "sha256": sha_file(self.raw),
                    "source_uri": "https://example.invalid/synthetic.nc",
                    "trace_id": "explicit-synthetic-fixture",
                }
            ),
            encoding="utf-8",
        )
        self.license = self.root / "license.json"
        self.license.write_text(
            json.dumps(
                {
                    "status": "VERIFIED_REAL_CATALOGUE_LICENSE",
                    "fixture_only": True,
                    "license": "CC-BY-4.0",
                    "source_uri": LICENSE_URI,
                    "dataset_family": "ERA5",
                }
            ),
            encoding="utf-8",
        )
        self.query = {
            "geography": {
                "geography_id": "synthetic-bbox",
                "method": "bbox_cell_centers",
                "bbox": [99.0, 59.0, 101.0, 61.0],
            },
            "time": {"start": "1951-01-01", "end": "1980-12-31", "calendar": "gregorian"},
            "variable": "cdd",
            "observed_or_projected": "observed",
            "model": "era5",
            "scenario": "not_applicable",
            "aggregation": "bbox_cell_mean",
            "unit": "days",
        }

    def tearDown(self):
        self.temp.cleanup()

    def call(self, request=None, **kwargs):
        return climate_query(
            request or self.query,
            self.raw,
            self.receipt,
            license_evidence_path=self.license,
            license_evidence_sha256=sha_file(self.license),
            allow_fixture=True,
            **kwargs,
        )

    def test_contract_requires_all_numerical_semantics_and_rejects_extra(self):
        self.assertEqual(set(tool_contract()["input_schema"]["required"]), set(self.query))
        for field in self.query:
            request = dict(self.query)
            request.pop(field)
            self.assertEqual(self.call(request)["status"], "BLOCKED")
        self.assertEqual(self.call({**self.query, "rag_generated_number": 42})["status"], "BLOCKED")

    def test_values_come_from_netcdf_and_area_weighting_is_explicit(self):
        result = self.call()
        self.assertEqual(result["status"], "TESTED_SYNTHETIC")
        self.assertEqual(result["value"], 4.0)
        self.assertFalse(result["geography_is_official_country_polygon"])
        self.assertEqual(result["valid_cells"], 4)
        weighted = self.call({**self.query, "aggregation": "bbox_area_weighted_mean"})
        a, b = np.cos(np.deg2rad([60.0, 60.25]))
        self.assertAlmostEqual(weighted["value"], (2 * a + 6 * b) / (a + b), places=10)
        self.assertFalse(weighted["training_executed"])
        self.assertTrue(weighted["citations"])

    def test_fixture_cannot_be_published_as_real(self):
        result = climate_query(self.query, self.raw, self.receipt)
        self.assertEqual(result["blockers"], ["SYNTHETIC_NOT_REAL"])
        self.assertIsNone(result["value"])

    def test_wrong_period_role_model_scenario_variable_unit_are_blocked(self):
        for changes in [
            {"time": {**self.query["time"], "start": "1971-01-01"}},
            {"observed_or_projected": "projected"},
            {"model": "invented-model"},
            {"scenario": "ssp585"},
            {"variable": "tas"},
            {"unit": "K"},
        ]:
            with self.subTest(changes=changes):
                result = self.call({**self.query, **changes})
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIsNone(result["value"])

    def test_sha_license_and_no_data_fail_closed(self):
        license_body = json.loads(self.license.read_text())
        license_body["license"] = "UNKNOWN"
        self.license.write_text(json.dumps(license_body))
        self.assertIsNone(self.call()["value"])
        with self.raw.open("ab") as stream:
            stream.write(b"tamper")
        with self.assertRaises(ValueError):
            inspect_netcdf(self.raw, json.loads(self.receipt.read_text())["sha256"])

    def test_cf_calendar_required_not_inferred_from_file_name(self):
        with Dataset(self.raw, "a") as dataset:
            dataset["time"].delncattr("calendar")
        self.receipt.write_text(
            json.dumps(
                {
                    "fixture_only": True,
                    "sha256": sha_file(self.raw),
                    "source_uri": "https://example.invalid/synthetic.nc",
                    "trace_id": "fixture",
                }
            )
        )
        result = self.call()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("CF_CALENDAR", result["detail"])

    def test_empty_bbox_does_not_emit_a_number(self):
        request = copy.deepcopy(self.query)
        request["geography"]["bbox"] = [0.0, -10.0, 1.0, -9.0]
        result = self.call(request)
        self.assertIsNone(result["value"])

    def test_all_fill_values_return_null_not_zero(self):
        with Dataset(self.raw, "a") as dataset:
            dataset["synthetic-cdd"][:] = np.full((1, 2, 2), 1e20, dtype="float32")
        receipt = json.loads(self.receipt.read_text())
        receipt["sha256"] = sha_file(self.raw)
        self.receipt.write_text(json.dumps(receipt))
        result = self.call()
        self.assertEqual(result["blockers"], ["NO_VALID_NUMERIC_GRID_VALUES"])
        self.assertIsNone(result["value"])


if __name__ == "__main__":
    unittest.main()
