"""Build an immutable candidate that quarantines original scenes spanning splits."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

from services.mlops.scene_split_audit import MAX_MANIFEST_BYTES, audit_scene_splits


def canonical(document):
    return (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False).encode()
        + b"\n"
    )


def save_version(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as target:
            target.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError("DATASET_CANDIDATE_OUTPUT_CONFLICT") from None


def quarantine(source, expected_sha, output):
    with source.open("rb") as handle:
        payload = handle.read(MAX_MANIFEST_BYTES + 1)
    if len(payload) > MAX_MANIFEST_BYTES or sha256(payload).hexdigest() != expected_sha:
        raise ValueError("DATASET_SOURCE_MANIFEST_PIN_MISMATCH")
    manifest = json.loads(payload)
    audit = audit_scene_splits(manifest, expected_sha)
    if audit["invalid_rows"]:
        raise ValueError("DATASET_ORIGINAL_ROWS_INVALID")
    scenes = {entry["scene_id"] for entry in audit["conflicts"]}
    candidate = {
        **manifest,
        "scenes": [row for row in manifest["scenes"] if row["scene_id"] not in scenes],
    }
    candidate["split_candidate"] = {
        "source_manifest_sha256": expected_sha,
        "operation": "QUARANTINE_ENTIRE_CROSS_SPLIT_SCENE",
        "quarantined_scene_ids": sorted(scenes),
        "authorized_for_training": False,
    }
    candidate_raw = canonical(candidate)
    digest = sha256(candidate_raw).hexdigest()
    checked = audit_scene_splits(candidate, digest)
    if (
        not checked["scene_split_gate_passed"]
        or min(checked["eligible_split_counts"].values()) == 0
    ):
        raise ValueError("DATASET_QUARANTINE_RESULT_INVALID")
    target = output / f"{digest}.json"
    save_version(target, candidate_raw)
    return {
        "schema_version": "sdss-scene-quarantine/1",
        "status": "VERIFIED_REAL_LOCAL_CANDIDATE",
        "source_manifest_sha256": expected_sha,
        "candidate_sha256": digest,
        "candidate_bytes": len(candidate_raw),
        "physical_rows_before": audit["physical_row_count"],
        "physical_rows_after": checked["physical_row_count"],
        "eligible_rows_before": audit["eligible_row_count"],
        "eligible_rows_after": checked["eligible_row_count"],
        "eligible_splits_after": checked["eligible_split_counts"],
        "original_scene_conflicts_before": audit["conflict_scene_count"],
        "original_scene_conflicts_after": checked["conflict_scene_count"],
        "quarantined_scene_count": len(scenes),
        "training_allowed": False,
        "deployment_allowed": False,
        "remaining_checks": ["GEOGRAPHIC_SPLIT_OVERLAP", "SOURCE_COVERAGE", "INDEPENDENT_LABELS"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = quarantine(args.source, args.sha256, args.directory)
    save_version(args.report, canonical(report))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
