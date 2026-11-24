"""로컬 상태 파일 생성 CLI. 네트워크/학습/실제 모델 추론/배포는 실행하지 않는다."""

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform

import numpy as np

from .adapters import lcluc_synthetic_smoke, rag_synthetic_smoke, AuthorizedDocument
from .catalog import default_catalog, ModelManifest, file_sha, canonical_sha
from .legacy_audit import audit_legacy_checkpoint
from .readiness import model_readiness
from services.mlops.gates import REQUIRED_BANDS


def build(output: Path, legacy_checkpoint: Path | None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    catalog = default_catalog()
    environment = {"python": platform.python_version(), "system": platform.system(),
                   "packages": {name: importlib.metadata.version(name) for name in ("pydantic", "numpy")},
                   "scope": "current_contract_diagnostic_runtime_not_legacy_training_environment"}
    environment["content_sha256"] = canonical_sha(environment)
    smoke = {"lcluc": lcluc_synthetic_smoke(np.ones((6, 2, 2), dtype="float32"),
                np.array([[4, 9], [3, 6]], dtype="uint8"), REQUIRED_BANDS, fixture_kind="synthetic"),
             "rag": rag_synthetic_smoke("climate methodology", [AuthorizedDocument(
                 document_id="synthetic-doc", text="climate methodology", citation="fixture:not-real-source",
                 visibility="public")], "fixture-user")}
    legacy = audit_legacy_checkpoint(legacy_checkpoint) if legacy_checkpoint else {
        "status": "BLOCKED", "blockers": ["LEGACY_CHECKPOINT_NOT_REQUESTED"], "independent_metrics": None}
    payloads = {"catalog.json": {"schema_version": "specialized-catalog/1.0",
                                 "models": [m.model_dump(mode="json") for m in catalog]},
                "model-manifest.schema.json": ModelManifest.model_json_schema(),
                "readiness.json": {"schema_version": "specialized-readiness/1.0",
                    "generated_at": datetime.now(timezone.utc).isoformat(), "status": "BLOCKED",
                    "models": [model_readiness(m, output) for m in catalog],
                    "data_readiness": None, "data_note": "No data evidence imported or fabricated in this repository",
                    "legacy_audit": "legacy-checkpoint-audit.json", "synthetic_smoke": "synthetic-smoke.json",
                    "independent_metrics": None, "training_started": False, "deployment_started": False},
                "runtime-environment.json": environment,
                "synthetic-smoke.json": smoke, "legacy-checkpoint-audit.json": legacy}
    for name, value in payloads.items():
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    index = {name: file_sha(output / name) for name in payloads}
    (output / "evidence-index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return {"status": "BLOCKED", "evidence_files": len(index), "training_started": False,
            "deployment_started": False, "legacy_inspection": legacy.get("inspection_state")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("evidence/models"))
    parser.add_argument("--legacy-checkpoint", type=Path)
    args = parser.parse_args()
    # 소유 evidence 경로 밖에 생성하지 않는다. 과거 저장소는 읽기 전용이다.
    allowed = Path(__file__).resolve().parents[2] / "evidence/models"
    if not args.output.resolve().is_relative_to(allowed.resolve()):
        parser.error("output must be under evidence/models")
    print(json.dumps(build(args.output, args.legacy_checkpoint), ensure_ascii=True))


if __name__ == "__main__":
    main()
