import json
from hashlib import sha256

import pytest

from services.mlops.releases import ModelRelease, ModelReleases, ReleaseBlocked


def write_pin(root, name, contents):
    raw = contents if isinstance(contents, bytes) else json.dumps(contents, sort_keys=True).encode()
    (root / name).write_bytes(raw)
    return {"path": name, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def candidate(root, version, artifact_bytes, *, kind="independent_ground_truth"):
    def put(name, contents):
        return write_pin(root, f"{version}-{name}", contents)

    artifact = put("model.onnx", artifact_bytes)
    dataset = put("manifest.json", {"input_count": 1100})
    readiness = put(
        "readiness.json",
        {
            "manifest_sha256": dataset["sha256"],
            "ledger_sha256": "1" * 64,
            "province_count": 6,
            "complete_year_cells": 36,
            "spatial_coverage_ratio": 0.97,
            "valid_pixel_ratio": 0.98,
            "physical_patches": 1100,
            "eligible_patches": 1000,
            "train_patches": 800,
            "validation_patches": 100,
            "test_patches": 100,
            "band_names": ["B02", "B03", "B04", "B08", "B11", "B12"],
            "scl_complete": True,
            "split_group_leakage": False,
            "future_leakage": False,
            "source_files_verified": True,
        },
    )
    reference = put("reference.json", {"fixture_only": True})
    training = put(
        "training.json",
        {
            "status": "SUCCEEDED",
            "dataset_sha256": dataset["sha256"],
            "model_sha256": artifact["sha256"],
        },
    )
    environment = put("environment.json", {"python": "3.11", "runtime": "onnx"})
    independent = {
        "reference_sha256": reference["sha256"],
        "reference_kind": kind,
        "sample_count": 230,
        "macro_f1": 0.92,
        "overall_accuracy": 0.95,
        "spatially_disjoint": True,
        "temporally_matched": True,
        "label_source_disjoint": True,
    }
    evaluation = put("evaluation.json", {**independent, "model_sha256": artifact["sha256"]})
    security = put("security.json", {"status": "PASSED", "model_sha256": artifact["sha256"]})
    rollback = put("rollback-test.json", {"status": "PASSED", "model_sha256": artifact["sha256"]})
    return ModelRelease.model_validate(
        {
            "model_name": "fixture-geoai",
            "version": version,
            "runtime": "onnx",
            "artifact": artifact,
            "dataset_manifest": dataset,
            "readiness": readiness,
            "training_report": training,
            "evaluation": evaluation,
            "environment": environment,
            "security_report": security,
            "rollback_report": rollback,
            "accuracy_reference": reference,
            "result_id": sha256(version.encode()).hexdigest(),
            "package_sha256": sha256((version + "-package").encode()).hexdigest(),
            "deployment": {
                "model_id": f"fixture-geoai:{version}",
                "model_sha256": artifact["sha256"],
                "training_report_sha256": training["sha256"],
                "registry_record_sha256": sha256((version + "-package").encode()).hexdigest(),
                "reproducible_environment_sha256": environment["sha256"],
                "security_scan_passed": True,
                "rollback_test_passed": True,
                "operator_approval_id": "fixture-operator-001",
                "independent_accuracy": {
                    **independent,
                    "reference_source": "fixture",
                    "reference_version": "1",
                    "evaluator_report_sha256": evaluation["sha256"],
                },
            },
        }
    )


def registry(root, candidates):
    return ModelReleases(root, root / "test.sqlite3", lambda rid: candidates[rid])


def evidence_snapshot(release):
    return {
        "package_sha256": release.package_sha256,
        "governance": {"scientific": {"status": "APPROVED"}},
        "package": {"sources": [{"raw": {"sha256": release.artifact.sha256}}]},
    }


def transition(store, root, release, registered, action, rev):
    pin = write_pin(
        root,
        f"approval-{rev}.json",
        {
            "authority": "fixture-reviewer",
            "action": action,
            "model": release.model_name,
            "version": release.version,
            "manifest_sha": registered["manifest_sha"],
            "previous_revision": rev,
            "approval_id": release.deployment.operator_approval_id,
        },
    )
    from services.results.catalog import Pin

    return store.transition(
        release.model_name,
        version=release.version,
        action=action,
        expected_revision=rev,
        approval=Pin.model_validate(pin),
        approver="fixture-reviewer",
    )


def test_weak_reference_cannot_register_model(tmp_path):
    weak = candidate(tmp_path, "v1", b"test", kind="weak_reference")
    with pytest.raises(ReleaseBlocked, match="REFERENCE_IS_NOT_INDEPENDENT"):
        registry(tmp_path, {weak.result_id: evidence_snapshot(weak)}).register(weak)


def test_version_reuse_rollback_and_stale_evidence(tmp_path):
    first = candidate(tmp_path, "v1", b"test-one")
    second = candidate(tmp_path, "v2", b"test-two")
    snapshots = {item.result_id: evidence_snapshot(item) for item in (first, second)}
    store = registry(tmp_path, snapshots)
    model = first.model_name
    r1, r2 = store.register(first), store.register(second)
    assert store.register(first) == r1
    with pytest.raises(ReleaseBlocked, match="ACTIVE_VERSION_UNAVAILABLE"):
        store.active_version(model)
    with pytest.raises(ReleaseBlocked, match="NEVER_ACTIVE"):
        transition(store, tmp_path, first, r1, "rollback", 0)
    transition(store, tmp_path, first, r1, "activate", 0)
    with pytest.raises(ReleaseBlocked, match="REVISION_CONFLICT"):
        transition(store, tmp_path, second, r2, "activate", 0)
    transition(store, tmp_path, second, r2, "activate", 1)
    assert (store.active_version(model)[0].version, store.active_version(model)[2]) == ("v2", 2)
    transition(store, tmp_path, first, r1, "rollback", 2)
    assert store.active_version(model)[0].version == "v1"
    snapshots[first.result_id]["governance"]["scientific"]["status"] = "REJECTED"
    with pytest.raises(ReleaseBlocked, match="SCIENTIFIC_APPROVAL_REQUIRED"):
        store.active_version(model)


def test_native_onnx_outputs_change_with_version_and_rollback(tmp_path):
    onnx = pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    import numpy as np

    def graph(bias):
        node = onnx.helper.make_node("Add", ["x", "constant"], ["y"])
        incoming = onnx.helper.make_tensor_value_info("x", onnx.TensorProto.FLOAT, [1])
        outgoing = onnx.helper.make_tensor_value_info("y", onnx.TensorProto.FLOAT, [1])
        constant = onnx.helper.make_tensor("constant", onnx.TensorProto.FLOAT, [1], [bias])
        model = onnx.helper.make_model(
            onnx.helper.make_graph([node], "fixture", [incoming], [outgoing], [constant]),
            ir_version=8,
            opset_imports=[onnx.helper.make_operatorsetid("", 13)],
        )
        return model.SerializeToString()

    first = candidate(tmp_path, "v1", graph(1))
    second = candidate(tmp_path, "v2", graph(2))
    store = registry(
        tmp_path, {item.result_id: evidence_snapshot(item) for item in (first, second)}
    )
    r1, r2 = store.register(first), store.register(second)
    for rev, release, registered, action, expected in (
        (0, first, r1, "activate", 11),
        (1, second, r2, "activate", 12),
        (2, first, r1, "rollback", 11),
    ):
        transition(store, tmp_path, release, registered, action, rev)
        outputs, trace = store.run_onnx(first.model_name, {"x": np.array([10], dtype=np.float32)})
        assert outputs[0].item() == expected
        assert trace["artifact_sha256"] == release.artifact.sha256
        assert trace["version"] == release.version
