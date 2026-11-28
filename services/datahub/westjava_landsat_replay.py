"""Re-download and replay the sealed 2025 West Java Landsat batch in isolation."""

import argparse
import shutil
import time
from pathlib import Path

from services.datahub.sentinel.shared_ledger import (
    SharedLedger,
    active_collectors,
    exclusive_os_lock,
)
from services.datahub.westjava_native import (
    ASSETS,
    ROOT,
    Provider,
    ProviderLimit,
    collect_group,
    digest,
    pin,
    read,
    store_json,
    utc,
)
from services.lcluc.annual_inputs import REGIONAL_OUTPUT, Pin
from services.lcluc.collector_intake import publish
from services.lcluc.regional_worker import run
from services.lcluc.westjava_native_intake import native_batch_receipt

ASSET_LIMIT = 1_507_487_085
LANDSAT_REPLAY = Path("data/raw/explorer/province/west-java-optical/landsat-2025-redownload")
REPLAY_EVIDENCE = Path("evidence/westjava/native-collection-runtime")
REPLAY_OUTPUT = Path("data/curated/lcluc/westjava-2025-landsat-replay")


def frozen_plans(root, batch):
    original, plans = {}, []
    for entry in batch["scenes"]:
        scene = read(Pin.model_validate(entry).local(root))
        key = scene["scene_id"]
        if key in original or scene["sensor"] != "landsat" or scene["year"] != 2025:
            raise ValueError("LANDSAT_REPLAY_SCENE_SCOPE_CHANGED")
        if set(scene["assets"]) != set(ASSETS["landsat"]):
            raise ValueError("LANDSAT_REPLAY_ASSETS_CHANGED")
        stac = read(Pin.model_validate(scene["stac"]).local(root))
        original[key] = scene["assets"]
        plans.append(
            {
                "sensor": "landsat",
                "year": 2025,
                "scene_id": key,
                "stac": stac,
                "assets": {
                    name: {k: asset[k] for k in ("bytes", "uri", "etag")}
                    for name, asset in scene["assets"].items()
                },
            }
        )
    if (
        len(plans) != 3
        or sum(a["bytes"] for plan in plans for a in plan["assets"].values()) != ASSET_LIMIT
    ):
        raise ValueError("LANDSAT_REPLAY_TRANSFER_LIMIT_MISMATCH")
    return original, plans


def check_trial(root, existing, repeated):
    results = []
    evaluations = []
    for folder in (existing, repeated):
        state = read(folder / "status.json")
        if state["models"]["landsat"]["status"] != "VERIFIED_REAL" or state["deployment_allowed"]:
            raise ValueError("LANDSAT_REPLAY_MODEL_NOT_EVALUATED")
        for held in state["artifacts"]:
            Pin.model_validate(held).local(folder)
        trial = read(folder / "landsat-candidate/trial.json")
        runs = {row["split"]: row for row in trial["evaluations"]}
        results.append(
            (
                state["mosaics"],
                trial["training_pixels"],
                trial["training_counts"],
                trial["split_audit"]["status"],
                trial["sources"],
            )
        )
        evaluations.append(runs)
    if results[0] != results[1]:
        raise ValueError("LANDSAT_REPLAY_QA_OR_TRAINING_DRIFT")
    holdouts = []
    for split in ("test", "validation"):
        before, after = (rows[split] for rows in evaluations)
        if (before["comparison_pixels"], before["weak_reference_metrics"], before["assets"]) != (
            after["comparison_pixels"],
            after["weak_reference_metrics"],
            after["assets"],
        ):
            raise ValueError("LANDSAT_REPLAY_HELDOUT_DRIFT")
        holdouts.append(
            {
                "split": split,
                "pixels": after["comparison_pixels"],
                "weak_reference_agreement": after["weak_reference_metrics"]["overall_accuracy"],
                "classification_sha256": after["assets"]["cover"]["sha256"],
                "confidence_sha256": after["assets"]["confidence"]["sha256"],
            }
        )
    first, second = (read(folder / "receipt.json")["windows"] for folder in (existing, repeated))
    for a, b in zip(first, second, strict=True):
        if (
            a["split"],
            a["mosaic"]["geometry"],
            [s["source_id"] for s in a["mosaic"]["scenes"]],
        ) != (
            b["split"],
            b["mosaic"]["geometry"],
            [s["source_id"] for s in b["mosaic"]["scenes"]],
        ):
            raise ValueError("LANDSAT_REPLAY_WINDOW_SCOPE_CHANGED")
        for scene in b["mosaic"]["scenes"]:
            if any(
                not Pin.model_validate(asset)
                .source_path(root)
                .is_relative_to(root / LANDSAT_REPLAY)
                for asset in scene["assets"].values()
            ):
                raise ValueError("LANDSAT_REPLAY_USED_PREVIOUS_IMAGE")
    return results[1][1], holdouts


def replay(root, legacy):
    evidence = root / REPLAY_EVIDENCE
    prior = read(evidence / "2025-landsat-end-to-end-verification.json")
    source = root / ROOT / "landsat/2025/batch-complete.json"
    expected = prior["publication"]["batch_sha256"]
    if digest(source) != expected:
        raise ValueError("LANDSAT_REPLAY_ORIGINAL_BATCH_SHA_MISMATCH")
    batch = read(source)
    original, plans = frozen_plans(root, batch)
    archive = root / LANDSAT_REPLAY
    archive.mkdir(parents=True, exist_ok=True)
    authority = archive / "replay-authority.json"
    scope = {
        "reason": "user-requested Landsat re-download verification",
        "year": 2025,
        "sensor": "landsat",
        "region": "west_java",
        "original_batch_sha256": expected,
        "scenes": sorted(original),
        "maximum_raw_bytes": ASSET_LIMIT,
        "production_release": "BLOCKED",
    }
    if authority.exists() and read(authority) != scope:
        raise ValueError("LANDSAT_REPLAY_EXISTING_SCOPE_DRIFT")
    if not authority.exists():
        store_json(authority, scope)
    progress_file = archive / "progress.json"

    def progress(status, _sensor=None, _year=None, **fields):
        store_json(progress_file, {"status": status, "checked_at": utc(), **scope, **fields})

    last = read(progress_file) if progress_file.exists() else {}
    retry = last.get("retry_not_before_unix", 0)
    if retry > time.time():
        raise RuntimeError("LANDSAT_REPLAY_RATE_LIMIT_COOLDOWN")
    ledger = SharedLedger(legacy)
    ledger_sha = digest(ledger.path)
    if ledger.snapshot(ledger_sha).get("rate_limit_active") or active_collectors():
        raise ValueError("LANDSAT_REPLAY_COLLECTOR_OR_429_ACTIVE")
    if shutil.disk_usage(archive).free < ASSET_LIMIT * 2:
        raise ValueError("LANDSAT_REPLAY_STORAGE_INSUFFICIENT")
    coordinator = root / "evidence/onemap_sentinel/coverage-batches/coordinator.lock"
    with exclusive_os_lock(archive / "replay.lock"):
        with exclusive_os_lock(coordinator), exclusive_os_lock(ledger.execution_lock):
            try:
                progress("RUNNING", planned_scenes=3)
                fresh = collect_group(
                    root,
                    archive,
                    "landsat",
                    2025,
                    plans,
                    ASSET_LIMIT,
                    progress,
                    Provider(),
                    batch["approval_sha256"],
                    supplement=batch["supplemental_approval"],
                )
            except ProviderLimit as error:
                progress(
                    "STOPPED_ON_HTTP429",
                    retry_not_before_unix=time.time() + error.delay,
                    provider_stage=error.origin,
                )
                raise
        for entry in fresh["scenes"]:
            row = read(Pin.model_validate(entry).local(root))
            for name, asset in row["assets"].items():
                archived = original[row["scene_id"]][name]
                if asset["sha256"] != archived["sha256"]:
                    raise ValueError("LANDSAT_REPLAY_REMOTE_PAYLOAD_DRIFT")
                for version in (asset, archived):
                    Pin.model_validate(
                        {key: version[key] for key in ("path", "bytes", "sha256")}
                    ).local(root)
        progress("VERIFYING", matched_assets=24)
        dest = root / REPLAY_OUTPUT
        inbox = dest / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        receipt = native_batch_receipt(
            root,
            archive / "landsat/2025/batch-complete.json",
            batch["approval_sha256"],
            archive,
            supplemental_approval=batch["supplemental_approval"],
        )
        run_id = publish(inbox, receipt)
        run(inbox / f"{run_id}.json", dest, {"platform": root, "legacy": root})
        pixels, holdouts = check_trial(
            root, root / REGIONAL_OUTPUT / prior["publication"]["run_id"], dest / run_id
        )
        proof = {
            **scope,
            "status": "VERIFIED_REAL",
            "checked_at": utc(),
            "downloaded_raw_bytes": ASSET_LIMIT,
            "source_assets_sha_matched": 24,
            "scene_count": 3,
            "training_pixels": pixels,
            "qa_radsat_every_scene": True,
            "same_windows_and_predictions": True,
            "independent_accuracy_measured": False,
            "deployment_allowed": False,
            "holdouts": holdouts,
            "fresh_batch": pin(root, archive / "landsat/2025/batch-complete.json"),
            "original_run": prior["publication"]["run_id"],
            "verified_run": run_id,
            "legacy_ledger_sha256_before": ledger_sha,
            "legacy_ledger_sha256_after": digest(ledger.path),
        }
        store_json(evidence / "2025-landsat-redownload-verification.json", proof)
        progress("VERIFIED_REAL", matched_assets=24, verified_run=run_id)
        return proof


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-ledger", type=Path, required=True)
    args = parser.parse_args()
    print(replay(Path.cwd().resolve(), args.legacy_ledger), flush=True)
