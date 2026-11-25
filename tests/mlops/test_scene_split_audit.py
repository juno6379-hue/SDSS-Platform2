"""합성 회귀시험: 서로 다른 주 prefix도 같은 원본 scene이면 누출이다."""

import hashlib
import json

import pytest

from services.mlops.scene_split_audit import audit_manifest_path, audit_scene_splits


def row(scene, split, province="synthetic-a", **extra):
    return dict(
        scene_id=scene,
        split=split,
        province=province,
        source_group=f"{province}/{scene}",
        quality_status="quality_eligible",
        **extra,
    )


def test_cross_province_prefix_cannot_hide_original_scene_leakage():
    result = audit_scene_splits(
        {"scenes": [row("same", "val"), row("same", "test", "synthetic-b")]}, "a" * 64
    )
    assert result["status"] == "BLOCKED"
    assert result["conflict_scene_count"] == 1
    assert result["conflicts"][0]["splits"] == ["test", "val"]
    assert "ORIGINAL_SCENE_SPLIT_LEAKAGE" in result["blockers"]
    assert result["training_allowed"] is result["deployment_allowed"] is False


def test_many_patches_same_scene_same_split_are_not_a_cross_split_leak():
    result = audit_scene_splits(
        {"scenes": [row("one", "train"), row("one", "train"), row("two", "validation")]}, "a" * 64
    )
    assert result["scene_split_gate_passed"]
    assert result["split_counts"] == {"train": 2, "val": 1, "test": 0}
    assert not result["training_allowed"]  # 단일 검사 통과는 학습 허가가 아니다.


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"scenes": []},
        {"scenes": [row("", "train")]},
        {"scenes": [row("one", "unknown")]},
        {"scenes": [None]},
    ],
)
def test_missing_or_invalid_evidence_fails_closed(bad):
    result = audit_scene_splits(bad, "b" * 64)
    assert not result["scene_split_gate_passed"]
    assert result["invalid_rows"]


def test_quality_ineligible_row_is_still_checked():
    a, b = row("same", "train"), row("same", "test")
    b["quality_status"] = "quality_rejected"
    result = audit_scene_splits({"scenes": [a, b]}, "a" * 64)
    assert result["eligible_row_count"] == 1
    assert result["conflict_scene_count"] == 1


def test_pinned_manifest_hash_must_match_and_source_is_unchanged(tmp_path):
    path = tmp_path / "manifest.json"
    raw = json.dumps({"scenes": [row("one", "train")]}).encode()
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="PINNED_MANIFEST_SHA_MISMATCH"):
        audit_manifest_path(path, "0" * 64)
    result = audit_manifest_path(path, hashlib.sha256(raw).hexdigest())
    assert result["snapshot_unchanged_after_read"]
    assert path.read_bytes() == raw
