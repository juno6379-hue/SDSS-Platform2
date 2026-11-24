"""구 저장소 체크포인트는 고정 SHA 확인 후 weights-only CPU 메타데이터만 읽는다."""

import hashlib
import io
import json
import pickle
from pathlib import Path

from .catalog import file_sha

LEGACY_SHA = "ad74f5cf5ab4bfd42bffd94b2fa399bf28f3527bc8e9f424d6a9d5339b12cd6c"


def audit_legacy_checkpoint(path: Path, expected_sha: str = LEGACY_SHA) -> dict:
    result = {"status": "BLOCKED", "inspection_state": "IMPLEMENTED_UNVERIFIED",
              "checkpoint_path": str(path), "expected_sha256": expected_sha,
              "training_started": False, "inference_started": False,
              "independent_metrics": None, "blockers": []}
    if not path.is_file():
        result["blockers"] = ["LEGACY_CHECKPOINT_MISSING"]
        return result
    result["bytes"] = path.stat().st_size
    if result["bytes"] > 16 * 1024 * 1024:
        result["blockers"] = ["LEGACY_INSPECTION_SIZE_CAP"]
        return result
    # 해시 계산과 역직렬화 사이 경로 교체가 있어도 같은 고정 바이트만 검사한다.
    with path.open("rb") as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        result["blockers"] = ["LEGACY_INSPECTION_SIZE_CAP"]
        return result
    actual = hashlib.sha256(raw).hexdigest()
    result["actual_sha256"] = actual
    if actual != expected_sha:
        result["blockers"] = ["LEGACY_CHECKPOINT_SHA_MISMATCH"]
        return result
    try:
        import torch
        checkpoint = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
    except (ImportError, RuntimeError, ValueError, OSError, pickle.UnpicklingError) as exc:
        result["blockers"] = ["SAFE_CHECKPOINT_METADATA_UNAVAILABLE"]
        result["error_type"] = type(exc).__name__
        return result
    result["inspection_state"] = "VERIFIED_REAL"
    result["checkpoint_keys"] = sorted(checkpoint.keys())
    state = checkpoint.get("state_dict", checkpoint.get("model_state", checkpoint.get("model_state_dict", {})))
    shapes = {key: list(value.shape) for key, value in state.items() if hasattr(value, "shape")}
    result["tensor_shapes"] = shapes
    convs = [(key, shape) for key, shape in shapes.items() if len(shape) == 4]
    result["first_convolution"] = {"key": convs[0][0], "shape": convs[0][1]} if convs else None
    result["observed_input_channels"] = convs[0][1][1] if convs else None
    result["metadata"] = {key: checkpoint.get(key) for key in ("architecture", "in_channels", "num_classes", "seed")}
    blockers = ["CLASS_MAPPING_23_NOT_VALIDATED", "INDEPENDENT_ACCURACY_MISSING",
                "REPRODUCIBLE_ENVIRONMENT_NOT_BOUND_TO_CHECKPOINT"]
    if result["observed_input_channels"] != 6:
        blockers.append("SIX_BAND_CHECKPOINT_SIGNATURE_MISMATCH")
    result["report_path"] = str(path.with_name("report.json"))
    result["report_sha256"] = file_sha(path.with_name("report.json")) if path.with_name("report.json").is_file() else None
    if result["report_sha256"]:
        report = json.loads(path.with_name("report.json").read_text(encoding="utf-8"))
        result["report_reference_kind"] = report.get("reference_kind")
        result["report_synthetic"] = report.get("synthetic")
        result["historical_epoch_count"] = len(report.get("history", []))
        blockers.append("LEGACY_REPORT_WEAK_REFERENCE_ONLY" if report.get("reference_kind") == "worldcover_weak_label"
                        else "LEGACY_REPORT_INDEPENDENCE_UNVERIFIED")
    else:
        blockers.append("LEGACY_TRAINING_REPORT_MISSING")
    result["blockers"] = blockers
    return result
