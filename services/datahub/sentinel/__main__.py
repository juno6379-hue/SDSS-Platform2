"""참조 저장소를 읽는 OneMap-Sentinel 완전성 감사. 수집 실행 옵션은 제공하지 않는다."""
import argparse
import json
from pathlib import Path
from services.datahub.connectors.onemap.boundary import pin_big_snapshot, sha256, write_json_new
from .completeness import audit, guarded_batch_preflight


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--boundary", type=Path, required=True)
    parser.add_argument("--boundary-sha256", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--ledger-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output, reference = args.output.resolve(), args.reference_root.resolve()
    # 참조 원본/원장에 결과를 쓰는 실수를 먼저 차단한다.
    if output.is_relative_to(reference) or reference.is_relative_to(output):
        raise ValueError("OUTPUT_MUST_BE_SEPARATE_FROM_READ_ONLY_REFERENCE")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("OUTPUT_NOT_EMPTY")
    boundary = pin_big_snapshot(args.boundary, args.boundary_sha256, reference, output / "boundary")
    result = audit(reference, boundary, args.manifest, args.manifest_sha256,
                   args.ledger, args.ledger_sha256, output / "audit")
    # 정확한 geometry 큐는 있으나 신규 scene/전역원장 reservation 승인이 없는 상태를 구분한다.
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    preflight = guarded_batch_preflight(ledger=ledger, ledger_sha256=args.ledger_sha256,
        observed_ledger_sha256=sha256(args.ledger), active_collectors=None,
        lock_exists=args.ledger.with_name("global-ledger.execution.lock").exists(),
        disk_free_bytes=__import__('shutil').disk_usage(output).free,
        candidate_keys=[], existing_keys=list(ledger["batches"]), reserve_bytes=32 * 1024 * 1024,
        shared_reservation_writable=False)
    preflight["active_collector_scan"] = "EXTERNAL_OPERATOR_CHECK_REQUIRED; NOT_ASSUMED_BY_THIS_CLI"
    write_json_new(output / "collection-preflight.json", preflight)
    print(json.dumps({k: result[k] for k in ("status", "physical_records", "manifest_quality_eligible",
        "verified_joint_patch_count", "minimum_patch_cells_met", "full_spatial_coverage",
        "remote_downloads", "ledger_writes")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
