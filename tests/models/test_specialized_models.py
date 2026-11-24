"""합성 계약 시험. 가짜 해시·수치는 실제 승인/정확도 증거가 아니다."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from pydantic import ValidationError

from services.models.catalog import (ArtifactRef, ModelManifest, default_catalog, file_sha,
                                     register_manifest, verify_artifact)
from services.models.readiness import model_readiness
from services.models.adapters import (AuthorizedDocument, climate_feature_plan,
                                      lcluc_synthetic_smoke, rag_synthetic_smoke)
from services.models.legacy_audit import audit_legacy_checkpoint
from services.mlops.gates import DataReadiness, DeploymentEvidence, AccuracyEvidence, REQUIRED_BANDS
from services.datahub.climate.models import ClimateAsset
from services.geoai.features.climate_join import BoundaryVersion, FeatureJoinRequest


class ModelContractTests(unittest.TestCase):
    def test_three_catalog_manifests_round_trip_and_signature_tamper(self):
        catalog = default_catalog()
        self.assertEqual(len(catalog), 3)
        for manifest in catalog:
            self.assertEqual(ModelManifest.model_validate_json(manifest.model_dump_json()), manifest)
            bad = manifest.model_dump(mode="json")
            bad["signature_sha256"] = "0" * 64
            with self.assertRaises(ValidationError):
                ModelManifest.model_validate(bad)
        self.assertIsNone(catalog[0].signature.class_mapping_23_to_internal)

    def test_unverified_23_class_mapping_and_band_order_rejected(self):
        for change in ({"class_mapping_23_to_internal": {"1": 0}},
                       {"band_names": list(reversed(REQUIRED_BANDS))}):
            bad = default_catalog()[0].model_dump(mode="json")
            bad["signature"].update(change)
            with self.assertRaises(ValidationError):
                ModelManifest.model_validate(bad)

    def test_climate_required_semantics_and_rag_acl_signature_cannot_be_removed(self):
        for manifest in default_catalog()[1:]:
            bad = manifest.model_dump(mode="json")
            bad["signature"]["required_fields"] = []
            with self.assertRaises(ValidationError):
                ModelManifest.model_validate(bad)
        bad = default_catalog()[2].model_dump(mode="json")
        bad["signature"]["normalization"] = "tokenize_before_acl"
        with self.assertRaises(ValidationError):
            ModelManifest.model_validate(bad)

    def test_registry_version_is_not_overwritten_or_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = default_catalog()[0]
            path = register_manifest(manifest, Path(tmp))
            with self.assertRaises(FileExistsError):
                register_manifest(manifest, Path(tmp))
            self.assertEqual(json.loads(path.read_text())["lifecycle"], "Draft")
            bad = manifest.model_dump(mode="json")
            bad["lifecycle"] = "Deployed"
            with self.assertRaises(ValidationError):
                ModelManifest.model_validate(bad)

    def test_artifact_actual_sha_and_path_containment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "weights.bin"
            path.write_bytes(b"synthetic")
            ref = ArtifactRef(path="weights.bin", sha256=file_sha(path))
            self.assertTrue(verify_artifact(ref, root)["verified"])
            path.write_bytes(b"tampered")
            self.assertEqual(verify_artifact(ref, root)["blocker"], "ARTIFACT_SHA_MISMATCH")
            outside = ArtifactRef(path="../outside.bin", sha256="a" * 64)
            self.assertEqual(verify_artifact(outside, root)["blocker"], "ARTIFACT_OUTSIDE_ALLOWED_ROOT")

    def test_missing_data_artifacts_never_become_ready(self):
        for manifest in default_catalog():
            result = model_readiness(manifest, Path("."))
            for axis in result["axes"].values():
                self.assertFalse(axis["allowed"])
            self.assertIsNone(result["independent_metrics"])

    def test_common_data_gate_scene_leakage_propagates(self):
        data = DataReadiness(manifest_sha256="a" * 64, ledger_sha256="b" * 64,
            province_count=6, complete_year_cells=36, spatial_coverage_ratio=.99,
            valid_pixel_ratio=.9, physical_patches=1100, eligible_patches=1000,
            train_patches=700, validation_patches=150, test_patches=150,
            band_names=REQUIRED_BANDS, scl_complete=True, split_group_leakage=True,
            future_leakage=False, source_files_verified=True)
        result = model_readiness(default_catalog()[0], Path("."), data)
        self.assertIn("SPLIT_GROUP_LEAKAGE", result["axes"]["training"]["blockers"])
        self.assertIn("CLASS_MAPPING_23_NOT_VALIDATED", result["axes"]["training"]["blockers"])

    def test_weak_reference_and_unbound_deployment_never_promoted(self):
        weak = AccuracyEvidence(reference_kind="weak_reference", reference_source="synthetic-worldcover",
            reference_version="2021", reference_sha256="a"*64, sample_count=1000,
            macro_f1=.99, overall_accuracy=.99, spatially_disjoint=True,
            temporally_matched=True, label_source_disjoint=False, evaluator_report_sha256="b"*64)
        evidence = DeploymentEvidence(model_id="other-model", model_sha256="c"*64,
            training_report_sha256="d"*64, registry_record_sha256="e"*64,
            reproducible_environment_sha256="f"*64, security_scan_passed=True,
            rollback_test_passed=True, operator_approval_id="synthetic-not-real", independent_accuracy=weak)
        result = model_readiness(default_catalog()[0], Path("."), deployment=evidence)
        blockers = result["axes"]["deployment"]["blockers"]
        self.assertIn("REFERENCE_IS_NOT_INDEPENDENT_GROUND_TRUTH", blockers)
        self.assertIn("DEPLOYMENT_MODEL_SHA256_MISMATCH", blockers)
        self.assertFalse(result["axes"]["deployment"]["allowed"])

    def test_synthetic_lcluc_cloud_mask_and_determinism_not_segmentation(self):
        image = np.ones((6, 2, 2), dtype="float32")
        scl = np.array([[4, 9], [3, 6]], dtype="uint8")
        a = lcluc_synthetic_smoke(image, scl, REQUIRED_BANDS, fixture_kind="synthetic")
        image[:, 0, 1] = 999
        b = lcluc_synthetic_smoke(image, scl, REQUIRED_BANDS, fixture_kind="synthetic")
        self.assertEqual(a, b)
        self.assertEqual(a["valid_pixels"], 2)
        self.assertIsNone(a["segmentation"])
        self.assertIsNone(a["independent_metrics"])

    def test_scl_grid_nan_and_non_synthetic_inputs_rejected(self):
        image = np.ones((6, 2, 2), dtype="float32")
        for scl in (np.ones((3, 2), dtype="uint8"), np.full((2, 2), 12, dtype="uint8")):
            with self.assertRaises(ValueError):
                lcluc_synthetic_smoke(image, scl, REQUIRED_BANDS, fixture_kind="synthetic")
        image[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            lcluc_synthetic_smoke(image, np.ones((2, 2), dtype="uint8"), REQUIRED_BANDS,
                                  fixture_kind="synthetic")
        with self.assertRaises(ValueError):
            lcluc_synthetic_smoke(image, image[0], REQUIRED_BANDS, fixture_kind="actual")

    def test_rag_acl_before_embedding_and_tokenization(self):
        secret = AuthorizedDocument(document_id="secret", text="SECRET_NEVER_TOKENIZED",
            citation="restricted", visibility="restricted", allowed_principals=("owner",))
        public = AuthorizedDocument(document_id="public", text="climate methodology",
            citation="https://example.org/fixture", visibility="public")
        from services.models import adapters
        original = adapters.canonical_tokens
        with patch.object(adapters, "canonical_tokens", wraps=original) as spy:
            result = rag_synthetic_smoke("climate methodology", [secret, public], "reader")
            self.assertNotIn(secret.text, [call.args[0] for call in spy.call_args_list])
        self.assertEqual([x["document_id"] for x in result["ranked_documents"]], ["public"])
        self.assertIsNone(result["answer"])
        self.assertEqual(result, rag_synthetic_smoke("climate methodology", [public, secret], "reader"))

    def test_rag_numeric_question_cannot_generate_answer(self):
        with patch("services.models.adapters._diagnostic_embedding", side_effect=AssertionError):
            result = rag_synthetic_smoke("2021 평균 기온은 얼마?", [], "reader")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["tool_id"], "climate.query")
        self.assertIsNone(result["answer"])

    def test_climate_metadata_and_asof_propagation(self):
        raw = json.loads((Path(__file__).parents[1] / "climate_lake/fixtures/asset.json").read_text())
        asset = ClimateAsset.model_validate(raw)
        boundary = BoundaryVersion(boundary_id="synthetic", version="v1", sha256="b"*64,
            crs="EPSG:4326", spatial_coverage={"bbox": [101., -7., 103., -5.]},
            valid_from="2019-01-01T00:00:00Z", available_at="2023-01-01T00:00:00Z",
            authority_status="provisional")
        req = FeatureJoinRequest(as_of="2022-01-01T00:00:00Z", feature_cutoff_date="2021-12-31",
            cutoff_calendar="standard", feature_window=raw["time_coverage"],
            purpose="historical_training", principal="fixture-user", requested_resolution_m=10.)
        result = climate_feature_plan(asset, boundary, req)
        self.assertIn("BOUNDARY_NOT_VALID_OR_AVAILABLE_AS_OF", result["plan"]["blockers"])
        self.assertEqual(result["input_metadata"]["unit"], asset.unit)
        self.assertIsNone(result["model_prediction"])
        self.assertFalse(result["plan"]["execution_started"])
        for field in ("unit", "model", "scenario"):
            bad = dict(raw)
            del bad[field]
            with self.assertRaises(ValidationError):
                ClimateAsset.model_validate(bad)

    def test_legacy_sha_mismatch_never_deserializes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.pt"
            path.write_bytes(b"not-a-checkpoint")
            result = audit_legacy_checkpoint(path)
            self.assertEqual(result["blockers"], ["LEGACY_CHECKPOINT_SHA_MISMATCH"])
            self.assertFalse(result["inference_started"])


if __name__ == "__main__":
    unittest.main()
