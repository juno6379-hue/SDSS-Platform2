"""RAW/staging/curated의 내용 해시 경로 계약. 이 모듈은 파일을 만들지 않는다."""

from pathlib import Path

from .models import ClimateAsset


def lake_paths(asset: ClimateAsset, lake_root: Path, extension: str = "nc") -> dict[str, str]:
    if extension not in {"nc", "parquet", "json"}:
        raise ValueError("UNSUPPORTED_LAKE_EXTENSION")
    root = Path(lake_root).resolve()
    namespace = Path(asset.source_id) / asset.dataset_id / asset.version / asset.sha256
    values = {
        "raw": root / "raw" / namespace / ("asset." + extension),
        "receipt": root / "raw" / namespace / "receipt.json",
        "staging": root / "staging" / namespace / "qc.json",
        "curated": root / "curated" / namespace / ("asset." + extension),
    }
    for value in values.values():
        if not value.resolve().is_relative_to(root):
            raise ValueError("LAKE_PATH_ESCAPES_ROOT")
    return {key: str(value) for key, value in values.items()}


def require_curated_lineage(asset: ClimateAsset, qc: dict) -> None:
    if qc.get("metadata_valid") is not True or qc.get("numeric_values_verified") is not True:
        raise ValueError("CURATED_REQUIRES_ACTUAL_NUMERIC_QA")
    if not asset.derived_from:
        raise ValueError("CURATED_REQUIRES_PINNED_PARENT_LINEAGE")
