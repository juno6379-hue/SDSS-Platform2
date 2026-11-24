"""합성 bbox·calendar·공개시각으로 계획과 누출 차단을 검사한다. 실제 수치 join은 아니다."""

import json
import unittest
from pathlib import Path

from services.datahub.climate.models import ClimateAsset
from services.geoai.features import BoundaryVersion, FeatureJoinRequest, plan_climate_join


class ClimateFeatureTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(
            (Path(__file__).parents[1] / "climate_lake/fixtures/asset.json").read_text(
                encoding="utf-8"
            )
        )
        self.asset = ClimateAsset.model_validate(self.raw)
        self.boundary_raw = {
            "boundary_id": "synthetic-boundary",
            "version": "2019-v1",
            "sha256": "b" * 64,
            "crs": "EPSG:4326",
            "spatial_coverage": {"bbox": [101.0, -7.0, 103.0, -5.0]},
            "valid_from": "2019-01-01T00:00:00Z",
            "valid_to": None,
            "available_at": "2019-01-01T00:00:00Z",
            "authority_status": "provisional",
        }
        self.request_raw = {
            "as_of": "2022-01-01T00:00:00Z",
            "feature_cutoff_date": "2021-12-31",
            "cutoff_calendar": "standard",
            "feature_window": self.raw["time_coverage"],
            "purpose": "historical_training",
            "principal": "fixture-user",
            "requested_resolution_m": 10.0,
        }

    def plan(self, asset=None, boundary=None, request=None):
        return plan_climate_join(
            asset or self.asset,
            BoundaryVersion.model_validate(boundary or self.boundary_raw),
            FeatureJoinRequest.model_validate(request or self.request_raw),
        )

    def test_valid_as_of_plan_preserves_native_grid_and_never_returns_numbers(self):
        result = self.plan()
        self.assertEqual(result["status"], "PLANNED")
        self.assertFalse(result["execution_started"])
        self.assertIsNone(result["numeric_features"])
        self.assertEqual(result["dataset_ref"]["sha256"], "a" * 64)
        self.assertEqual(result["boundary_ref"]["sha256"], "b" * 64)
        self.assertEqual(
            result["native_grid_cell_candidates"],
            {
                "column_start": 0,
                "column_stop": 2,
                "row_start": 0,
                "row_stop": 2,
                "stop_exclusive": True,
            },
        )
        self.assertTrue(any("DOWNSCALING" in x for x in result["warnings"]))
        self.assertIn("BOUNDARY_AUTHORITY_NOT_APPROVED_DEVELOPMENT_ONLY", result["warnings"])

    def test_new_boundary_must_not_leak_into_earlier_as_of(self):
        for changes in [
            {"available_at": "2023-01-01T00:00:00Z"},
            {"valid_from": "2023-01-01T00:00:00Z"},
            {"valid_to": "2022-01-01T00:00:00Z"},
        ]:
            result = self.plan(boundary={**self.boundary_raw, **changes})
            self.assertIn("BOUNDARY_NOT_VALID_OR_AVAILABLE_AS_OF", result["blockers"])
            self.assertIsNone(result["native_grid_cell_candidates"])

    def test_unreleased_climate_data_cannot_be_used_for_backtest(self):
        asset = ClimateAsset.model_validate({**self.raw, "available_at": "2023-01-01T00:00:00Z"})
        self.assertIn("CLIMATE_ASSET_NOT_AVAILABLE_AS_OF", self.plan(asset=asset)["blockers"])

    def test_derived_feature_requires_parent_as_of_and_fitting_period_resolution(self):
        asset = ClimateAsset.model_validate(
            {
                **self.raw,
                "derived_from": [
                    {
                        "dataset_id": "synthetic-parent",
                        "version": "v1",
                        "sha256": "c" * 64,
                        "role": "normalization_fit_statistics",
                    }
                ],
            }
        )
        result = self.plan(asset=asset)
        self.assertIn("PARENT_LINEAGE_AS_OF_RESOLUTION_REQUIRED", result["blockers"])
        self.assertIsNone(result["native_grid_cell_candidates"])

    def test_future_observation_and_cutoff_cannot_bypass_as_of(self):
        result = self.plan(request={**self.request_raw, "feature_cutoff_date": "2019-12-31"})
        self.assertIn("FUTURE_OBSERVATION_LEAKAGE", result["blockers"])
        result = self.plan(request={**self.request_raw, "feature_cutoff_date": "2030-01-01"})
        self.assertIn("FEATURE_CUTOFF_AFTER_AS_OF", result["blockers"])
        result = self.plan(
            request={
                **self.request_raw,
                "purpose": "scenario_analysis",
                "feature_cutoff_date": "2019-12-31",
            }
        )
        self.assertIn("FUTURE_OBSERVATION_LEAKAGE", result["blockers"])

    def test_future_scenario_window_is_allowed_only_as_declared_projection(self):
        future = {**self.raw["time_coverage"], "start": "2040-01-01", "end": "2040-12-31"}
        asset = ClimateAsset.model_validate(
            {
                **self.raw,
                "observed_or_projected": "projected",
                "model": "synthetic-model",
                "scenario": "ssp245",
                "time_coverage": future,
            }
        )
        result = self.plan(
            asset=asset,
            request={**self.request_raw, "purpose": "scenario_analysis", "feature_window": future},
        )
        self.assertEqual(result["status"], "PLANNED")
        self.assertIsNone(result["numeric_features"])

    def test_different_calendar_is_blocked_instead_of_implicit_resampling(self):
        result = self.plan(request={**self.request_raw, "cutoff_calendar": "noleap"})
        self.assertIn("CALENDAR_MISMATCH_NO_IMPLICIT_CONVERSION", result["blockers"])

    def test_projection_is_scenario_only_and_preserves_model_semantics(self):
        asset = ClimateAsset.model_validate(
            {
                **self.raw,
                "observed_or_projected": "projected",
                "model": "synthetic-model",
                "scenario": "ssp245",
            }
        )
        self.assertIn(
            "PROJECTED_DATA_NOT_HISTORICAL_OBSERVATIONS", self.plan(asset=asset)["blockers"]
        )
        result = self.plan(
            asset=asset, request={**self.request_raw, "purpose": "scenario_analysis"}
        )
        self.assertEqual(result["status"], "PLANNED")
        self.assertEqual(result["scenario"], "ssp245")
        self.assertIn("SCENARIO_ASSUMPTION_NOT_OBSERVED_GROUND_TRUTH", result["warnings"])

    def test_restricted_asset_never_leaks_identifiers_to_unauthorized_user(self):
        asset = ClimateAsset.model_validate(
            {
                **self.raw,
                "access": {"visibility": "restricted", "allowed_principals": ["authorized-user"]},
            }
        )
        result = self.plan(asset=asset)
        self.assertEqual(
            result, {"status": "BLOCKED", "blockers": ["ACCESS_DENIED"], "execution_started": False}
        )
        self.assertEqual(
            self.plan(asset=asset, request={**self.request_raw, "principal": "authorized-user"})[
                "status"
            ],
            "PLANNED",
        )

    def test_crs_mismatch_and_disjoint_space_require_explicit_handling(self):
        self.assertIn(
            "EXPLICIT_REPROJECTION_REQUIRED",
            self.plan(boundary={**self.boundary_raw, "crs": "EPSG:6933"})["blockers"],
        )
        self.assertIn(
            "NO_SPATIAL_INTERSECTION",
            self.plan(
                boundary={
                    **self.boundary_raw,
                    "spatial_coverage": {"bbox": [120.0, -7.0, 121.0, -5.0]},
                }
            )["blockers"],
        )

    def test_boundary_on_cell_edges_excludes_zero_overlap_neighbours(self):
        result = self.plan(
            boundary={**self.boundary_raw, "spatial_coverage": {"bbox": [100.0, -6.0, 102.0, -4.0]}}
        )
        cells = result["native_grid_cell_candidates"]
        self.assertEqual(
            (cells["column_start"], cells["column_stop"], cells["row_start"], cells["row_stop"]),
            (0, 1, 0, 1),
        )

    def test_explicit_ascending_latitude_uses_south_origin_indices(self):
        asset = ClimateAsset.model_validate(
            {**self.raw, "grid": {**self.raw["grid"], "row_order": "south_to_north"}}
        )
        result = self.plan(
            asset=asset,
            boundary={
                **self.boundary_raw,
                "spatial_coverage": {"bbox": [100.0, -6.0, 102.0, -4.0]},
            },
        )
        self.assertEqual(
            (
                result["native_grid_cell_candidates"]["row_start"],
                result["native_grid_cell_candidates"]["row_stop"],
            ),
            (1, 2),
        )


if __name__ == "__main__":
    unittest.main()
