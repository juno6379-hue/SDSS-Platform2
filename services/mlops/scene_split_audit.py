"""원본 scene_id의 분할 교집합 감사. prefix group이나 패치 개수로 누출을 숨기지 않는다.

CLI는 고정 manifest SHA를 필수로 받고 단일 결과 JSON만 쓴다.
감사 통과도 데이터 대표성·독립 정답·학습·배포 승인을 의미하지 않는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

MAX_MANIFEST_BYTES = 64 * 1024 * 1024
SPLITS = {"train": "train", "val": "val", "validation": "val", "test": "test"}


def audit_scene_splits(manifest: dict, manifest_sha256: str) -> dict:
    """입력 전체 행에 대해 감사한다. 품질 부적격 행도 누출 검사에서 제외하지 않는다."""
    if not re.fullmatch(r"[a-f0-9]{64}", manifest_sha256):
        raise ValueError("MANIFEST_SHA256_REQUIRED")
    scenes = manifest.get("scenes") if isinstance(manifest, dict) else None
    groups = defaultdict(lambda: defaultdict(list))
    split_counts, eligible_counts = Counter(), Counter()
    invalid = []
    if not isinstance(scenes, list) or not scenes:
        scenes = []
        invalid.append({"row": None, "reason": "NONEMPTY_SCENES_REQUIRED"})
    for index, row in enumerate(scenes):
        if not isinstance(row, dict):
            invalid.append({"row": index, "reason": "SCENE_ROW_OBJECT_REQUIRED"})
            continue
        scene, split = row.get("scene_id"), row.get("split")
        if not isinstance(scene, str) or not scene.strip() or scene != scene.strip():
            invalid.append({"row": index, "reason": "ORIGINAL_SCENE_ID_REQUIRED"})
            continue
        if not isinstance(split, str) or split not in SPLITS:
            invalid.append({"row": index, "reason": "EXPLICIT_TRAIN_VAL_TEST_SPLIT_REQUIRED"})
            continue
        split = SPLITS[split]
        groups[scene][split].append(
            {"row": index, "province": row.get("province"), "source_group": row.get("source_group")}
        )
        split_counts[split] += 1
        if row.get("quality_status") == "quality_eligible":
            eligible_counts[split] += 1
    conflicts = [
        {
            "scene_id": scene,
            "splits": sorted(by_split),
            "rows_by_split": dict(sorted(by_split.items())),
        }
        for scene, by_split in sorted(groups.items())
        if len(by_split) > 1
    ]
    blockers = []
    if invalid:
        blockers.append("SCENE_SPLIT_EVIDENCE_INVALID")
    if conflicts:
        blockers.append("ORIGINAL_SCENE_SPLIT_LEAKAGE")
    return {
        "schema_version": "scene-split-audit/1.0",
        "status": "BLOCKED" if blockers else "VERIFIED_REAL",
        "scene_split_gate_passed": not blockers,
        "manifest_sha256": manifest_sha256,
        "physical_row_count": len(scenes),
        "eligible_row_count": sum(eligible_counts.values()),
        "split_counts": {s: split_counts[s] for s in ("train", "val", "test")},
        "eligible_split_counts": {s: eligible_counts[s] for s in ("train", "val", "test")},
        "unique_original_scene_count": len(groups),
        "conflict_scene_count": len(conflicts),
        "conflicts": conflicts,
        "invalid_rows": invalid,
        "blockers": blockers,
        "training_allowed": False,
        "deployment_allowed": False,
        "scientific_execution_started": False,
        "scope": "original_scene_identity_only_not_full_geometric_overlap_or_training_readiness",
    }


def audit_manifest_path(path: Path, expected_sha256: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("EXPECTED_MANIFEST_SHA256_REQUIRED")
    with path.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("MANIFEST_SIZE_CAP_EXCEEDED")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("PINNED_MANIFEST_SHA_MISMATCH")
    result = audit_scene_splits(json.loads(raw), digest)
    # 수집 중 파일을 감사한 것처럼 보고하지 않기 위해 기록 직전 재검증한다.
    with path.open("rb") as stream:
        after = stream.read(MAX_MANIFEST_BYTES + 1)
    unchanged = hashlib.sha256(after).hexdigest() == digest
    result.update(
        {
            "source_path": str(path.resolve()),
            "expected_manifest_sha256": expected_sha256,
            "snapshot_unchanged_after_read": unchanged,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    if not unchanged:
        result["blockers"].append("MANIFEST_CHANGED_DURING_AUDIT")
        result.update(status="BLOCKED", scene_split_gate_passed=False)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # 출력은 이 작업의 모델 증거 경로로 제한하고 기존 고정 증거 덮어쓰기를 거부한다.
    root = Path(__file__).resolve().parents[2] / "evidence/models"
    if not args.output.resolve().is_relative_to(root.resolve()):
        parser.error("output must be under evidence/models")
    result = audit_manifest_path(args.manifest, args.expected_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "status",
                    "manifest_sha256",
                    "physical_row_count",
                    "eligible_row_count",
                    "conflict_scene_count",
                    "training_allowed",
                )
            },
            ensure_ascii=True,
        )
    )
    return 2 if not result["scene_split_gate_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
