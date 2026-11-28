"""Bounded West Java native optical acquisition under a separate approved budget."""

import argparse
import json
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from threading import Event, Lock
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from services.datahub.sentinel.remote import NoRedirect
from services.datahub.sentinel.shared_ledger import (
    SharedLedger,
    active_collectors,
    exclusive_os_lock,
)
from services.lcluc.annual import store_json
from services.lcluc.annual_inputs import Bands, Pin
from services.lcluc.province_esri import SNAPSHOT_SHA256, digest, utc

ROOT = Path("data/raw/explorer/province/west-java-optical/native")
GAPS = Path("evidence/westjava/gap-plan-20261127-final/westjava-optical-gaps.json")
ASSETS = {
    "sentinel-2": (*Bands["sentinel-2"], "SCL", "product-metadata"),
    "landsat": ("blue", "green", "red", "nir08", "swir16", "swir22", "qa_pixel", "qa_radsat"),
}
RANGE_SIZE = 8 * 1024 * 1024
TOKEN_ROOT = "https://planetarycomputer.microsoft.com/api/sas/v1/token/"
OPENER = build_opener(NoRedirect())


class ProviderLimit(RuntimeError):
    def __init__(self, retry_after, origin):
        super().__init__("HTTP_429")
        try:
            delay = int(retry_after)
        except (ValueError, TypeError):
            try:
                delay = round((parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError):
                delay = 120
        self.delay = max(delay, 120)
        self.origin = origin


def pin(root, path):
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}


def read(path):
    return json.loads(path.read_bytes())


def azure_source(uri, sensor):
    parsed = urlsplit(uri)
    account = (parsed.hostname or "").split(".")[0]
    container = "sentinel2-l2" if sensor == "sentinel-2" else "landsat-c2"
    account_pattern = r"sentinel2l2a\d{2}" if sensor == "sentinel-2" else r"landsat[a-z0-9]+"
    if (
        parsed.scheme != "https" or parsed.netloc != f"{account}.blob.core.windows.net"
        or not re.fullmatch(account_pattern, account)
        or not parsed.path.startswith(f"/{container}/") or parsed.query or parsed.fragment
        or not parsed.path.lower().endswith((".tif", "/mtd_msil2a.xml"))
    ):
        raise ValueError("UNEXPECTED_WEST_JAVA_ASSET_URI")
    return account, container


class Provider:
    def __init__(self):
        self.tokens = {}
        self.lock = Lock()
        self.rate_limit = None
        self.next_request = 0

    def request(self, sensor, uri, *, method="GET", headers=None):
        account, container = azure_source(uri, sensor)
        origin = "catalog_signing"
        try:
            with self.lock:
                if self.rate_limit:
                    raise self.rate_limit
                current = datetime.now(timezone.utc).timestamp()
                if account not in self.tokens or self.tokens[account][1] < current + 300:
                    with OPENER.open(TOKEN_ROOT + account + "/" + container, timeout=30) as token_response:
                        raw = token_response.read(65537)
                    if len(raw) > 65536:
                        raise ValueError("PROVIDER_TOKEN_RESPONSE_TOO_LARGE")
                    token = json.loads(raw)
                    expiry = datetime.fromisoformat(token["msft:expiry"].replace("Z", "+00:00")).timestamp()
                    value = token["token"].lstrip("?")
                    if "sig=" not in value or expiry < current + 60:
                        raise ValueError("PROVIDER_TOKEN_INVALID")
                    self.tokens[account] = value, expiry
                signed = uri + "?" + self.tokens[account][0]
                wait = self.next_request - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                self.next_request = time.monotonic() + 0.6
            origin = "asset_storage"
            return OPENER.open(Request(signed, method=method, headers=headers or {}), timeout=60)
        except HTTPError as error:
            # Signed provider URLs are never included in errors or receipts.
            if error.code == 429:
                self.rate_limit = ProviderLimit(error.headers.get("Retry-After"), origin)
                raise self.rate_limit from None
            raise RuntimeError(f"HTTP_{error.code}") from None
        except OSError as error:
            raise RuntimeError(type(error).__name__) from None


def scope(root, approval_path, approval_sha):
    if digest(approval_path) != approval_sha:
        raise ValueError("USER_APPROVAL_SHA_CHANGED")
    approval = read(approval_path)
    gap_path = Pin.model_validate(approval["scope_report"]).local(root)
    summary = read(gap_path)
    if (
        approval["region"] != "west_java" or approval["year_scope"] != [2020, 2025]
        or approval["budget_bytes"] != {"sentinel-2": 59_900_000_000, "landsat": 8_930_000_000}
        or summary["region"]["boundary_snapshot"] != SNAPSHOT_SHA256
    ):
        raise ValueError("WEST_JAVA_APPROVAL_SCOPE_MISMATCH")
    return approval, summary


def catalog_item(root, pages, identity):
    for page in pages:
        path = (root / page["path"]).resolve()
        if not path.is_relative_to(root) or digest(path) != page["sha256"]:
            raise ValueError("COLLECTION_CATALOG_PIN_CHANGED")
        found = next((item for item in read(path)["features"] if item["id"] == identity), None)
        if found is not None:
            return found
    raise ValueError("SELECTED_SCENE_NOT_IN_PINNED_CATALOG")


def plan_scene(root, row, selected, provider):
    sensor, year, identity = row["sensor"], row["year"], selected["id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{12,120}", identity):
        raise ValueError("UNSAFE_SCENE_ID")
    pages = [row["candidate_catalog"]]
    if row.get("targeted_residual_catalog"):
        pages.append(row["targeted_residual_catalog"])
    stac = catalog_item(root, pages, identity)
    collection = {"sentinel-2": "sentinel-2-l2a", "landsat": "landsat-c2-l2"}[sensor]
    if stac["collection"] != collection or stac["properties"]["datetime"][:4] != str(year):
        raise ValueError("COLLECTION_SCENE_SCOPE_DRIFT")
    assets = {}
    for band in ASSETS[sensor]:
        uri = stac["assets"][band]["href"]
        with provider.request(sensor, uri, method="HEAD") as response:
            length = int(response.headers["Content-Length"])
            etag = response.headers["ETag"]
        maximum = 1_000_000 if band == "product-metadata" else 600_000_000
        if not 0 < length <= maximum or not etag:
            raise ValueError("PROVIDER_LENGTH_OR_ETAG_OUT_OF_BOUNDS")
        assets[band] = {"uri": uri, "bytes": length, "etag": etag}
    return {"sensor": sensor, "year": year, "scene_id": identity, "stac": stac, "assets": assets}


def planning(root, summary, output, provider, *, year=None):
    tasks = [(row, selected) for row in sorted(summary["entries"], key=lambda row: (row["year"], row["sensor"]))
             if year is None or row["year"] == year for selected in row["selected"]]
    plans = read(output) if output.exists() else []
    existing = {(plan["sensor"], plan["year"], plan["scene_id"]) for plan in plans}
    tasks = [(row, scene) for row, scene in tasks if (row["sensor"], row["year"], scene["id"]) not in existing]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for plan in pool.map(lambda args: plan_scene(root, *args, provider), tasks):
            plans.append(plan)
            store_json(output, plans)
            print("HEAD", plan["year"], plan["sensor"], plan["scene_id"],
                  sum(row["bytes"] for row in plan["assets"].values()), flush=True)
    store_json(output, plans)
    return plans


def transfer(provider, sensor, band, row, path, stop):
    downloaded = path.with_suffix(path.suffix + ".part")
    length = row["bytes"]
    offset = downloaded.stat().st_size if downloaded.exists() else 0
    if not 0 <= offset <= length:
        raise ValueError("PARTIAL_LENGTH_EXCEEDS_PLAN")
    while offset < length and not stop.is_set():
        end = min(offset + RANGE_SIZE, length) - 1
        headers = {"If-Match": row["etag"], "Accept-Encoding": "identity", "Range": f"bytes={offset}-{end}"}
        with provider.request(sensor, row["uri"], headers=headers) as response:
            if (
                response.status != 206 or response.headers["ETag"] != row["etag"]
                or int(response.headers["Content-Length"]) != end + 1 - offset
                or response.headers["Content-Range"] != f"bytes {offset}-{end}/{length}"
            ):
                raise ValueError("PROVIDER_OBJECT_DRIFT")
            with downloaded.open("ab") as out:
                while not stop.is_set() and (chunk := response.read1(1024**2)):
                    offset += len(chunk)
                    if offset > end + 1:
                        raise ValueError("PROVIDER_BODY_EXCEEDS_PLAN")
                    out.write(chunk)
                    out.flush()
                os.fsync(out.fileno())
        if offset != end + 1 and not stop.is_set():
            raise OSError("INCOMPLETE_PROVIDER_BODY")
    if stop.is_set():
        return False
    verify_native_file(downloaded, row["bytes"], sensor, band)
    downloaded.rename(path)
    return True


def verify_native_file(path, expected_bytes, sensor, band):
    if path.stat().st_size != expected_bytes:
        raise ValueError("NATIVE_ASSET_SIZE_MISMATCH")
    if band != "product-metadata":
        import rasterio

        with rasterio.open(path) as raster:
            native = 10 if sensor == "sentinel-2" and band in Bands[sensor][:4] else (20 if sensor == "sentinel-2" else 30)
            expected = "uint8" if band == "SCL" else "uint16"
            if raster.res != (native, native) or not raster.crs or raster.dtypes != (expected,):
                raise ValueError("NATIVE_OPTICAL_GRID_INVALID")


def collect_scene(root, home, plan, stop, provider):
    sensor, year, identity = plan["sensor"], plan["year"], plan["scene_id"]
    folder = home / sensor / str(year) / identity
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / "scene-receipt.json"
    stac = folder / "stac-item.json"
    if stac.exists() and read(stac) != plan["stac"]:
        raise ValueError("NATIVE_ARCHIVE_STAC_DRIFT")
    if not stac.exists():
        store_json(stac, plan["stac"])
    assets = {}
    for band, row in plan["assets"].items():
        if stop.is_set():
            return None
        path = folder / ("product-metadata.xml" if band == "product-metadata" else f"{band}.tif")
        audit = path.with_suffix(".receipt.json")
        if audit.exists():
            saved = read(audit)
            if any(saved[key] != row[key] for key in ("uri", "bytes", "etag")):
                raise ValueError("NATIVE_ARCHIVE_ASSET_PIN_DRIFT")
            Pin.model_validate({key: saved[key] for key in ("path", "bytes", "sha256")}).local(root)
        else:
            if path.exists():
                verify_native_file(path, row["bytes"], sensor, band)
            for attempt in range(3):
                try:
                    if not path.exists() and not transfer(provider, sensor, band, row, path, stop):
                        return None
                    break
                except (OSError, RuntimeError) as error:
                    transient = str(error) in {
                        "HTTP_500", "HTTP_502", "HTTP_503", "HTTP_504", "TimeoutError", "URLError",
                        "INCOMPLETE_PROVIDER_BODY", "ConnectionResetError",
                    }
                    if not transient or attempt == 2:
                        stop.set()
                        raise
                    stop.wait(3 * (attempt + 1))
                    if stop.is_set():
                        return None
            saved = {**row, **pin(root, path), "received_at": utc()}
            store_json(audit, saved)
        assets[band] = saved
        print("STORED", year, sensor, identity, band, saved["bytes"], flush=True)
    completed = {"schema_version": "westjava-native-scene/1", "region": "west_java", "sensor": sensor,
                 "year": year, "scene_id": identity, "stac": pin(root, stac), "assets": assets}
    if receipt.exists() and read(receipt) != completed:
        raise ValueError("NATIVE_ARCHIVE_SCENE_RECEIPT_DRIFT")
    if not receipt.exists():
        store_json(receipt, completed)
    return pin(root, receipt)


def collect_group(root, home, sensor, year, plans, charge, progress, provider, approval_sha, *, supplement=None):
    output = home / sensor / str(year)
    output.mkdir(parents=True, exist_ok=True)
    ready = output / "batch-complete.json"
    if ready.exists():
        done = read(ready)
        if (done["expected_bytes"] != charge or done["approval_sha256"] != approval_sha
            or done.get("supplemental_approval") != supplement):
            raise ValueError("BATCH_RECEIPT_CHARGE_DRIFT")
        for source in done["scenes"]:
            Pin.model_validate(source).local(root)
        return done
    stop = Event()
    # Each task is a complete scene. The first fault closes the other in-progress requests.
    def one(plan):
        try:
            return collect_scene(root, home, plan, stop, provider)
        except Exception:
            stop.set()
            raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = []
        for scene in pool.map(one, plans):
            if scene is not None:
                receipts.append(scene)
                progress("RUNNING", sensor, year, completed_scenes=len(receipts), planned_scenes=len(plans))
    if len(receipts) != len(plans):
        raise ValueError("BATCH_DID_NOT_SETTLE")
    result = {"schema_version": "westjava-native-batch/1", "region": "west_java",
              "sensor": sensor, "year": year, "scenes": receipts, "expected_bytes": charge,
              "completed_at": utc(), "approval_sha256": approval_sha, "production_release": "BLOCKED"}
    if supplement is not None:
        result["supplemental_approval"] = supplement
    store_json(ready, result)
    return result


def read_supplement(root, path, expected_sha, approval_sha, plan_sha):
    if not path.resolve().is_relative_to(root) or not plan_sha or digest(path) != expected_sha:
        raise ValueError("WEST_JAVA_SUPPLEMENT_PIN_MISMATCH")
    extra = read(path)
    if (extra["schema_version"], extra["region"], extra["sensor"], extra["year"], extra["additional_bytes"],
        extra["approval_sha256"], extra["head_plan_sha256"]) != (
            "westjava-native-supplement/1", "west_java", "landsat", 2025, 343_105_303, approval_sha, plan_sha,
        ):
        raise ValueError("WEST_JAVA_SUPPLEMENT_SCOPE_MISMATCH")
    return pin(root, path.resolve()), extra["additional_bytes"]


def run(root, home, legacy_path, approval, summary, approval_sha, *, plan_sha=None, supplement=None):
    ledger = SharedLedger(legacy_path)
    state = ledger.snapshot(digest(ledger.path))
    if state.get("rate_limit_active") or active_collectors():
        raise ValueError("EXISTING_COLLECTOR_OR_429_CIRCUIT_ACTIVE")
    old = home / "progress.json"
    if old.exists() and read(old).get("status") == "STOPPED_ON_HTTP429":
        last = read(old)
        if datetime.fromisoformat(last["checked_at"]).timestamp() + last["retry_after_seconds"] > time.time():
            raise ValueError("WEST_JAVA_HTTP429_CIRCUIT_STILL_OPEN")
    budget = approval["budget_bytes"]
    extra_pin, extra_bytes = supplement or (None, 0)
    if shutil.disk_usage(home).free < (sum(budget.values()) + extra_bytes) * 2:
        raise ValueError("WEST_JAVA_STORAGE_INSUFFICIENT")
    usage = {sensor: 0 for sensor in budget}
    record = {"approval_sha256": approval_sha, "region": "west_java", "pid": os.getpid(),
              "budget_bytes": budget, "legacy_ledger_sha256": digest(ledger.path), "batches": [],
              "production_release": "BLOCKED"}
    if extra_pin is not None:
        record["supplemental_approval"] = extra_pin

    def progress(status, sensor=None, year=None, **detail):
        store_json(old, {**record, "status": status, "sensor": sensor, "year": year, "checked_at": utc(),
                         "reserved_or_completed_bytes": usage, **detail})
    coordinator = root / "evidence/onemap_sentinel/coverage-batches/coordinator.lock"
    provider = Provider()
    with exclusive_os_lock(home / "collector.lock"), exclusive_os_lock(coordinator), exclusive_os_lock(ledger.execution_lock):
        sensor = year = None
        try:
            head_path = home / "head-plan.json"
            if plan_sha:
                if digest(head_path) != plan_sha:
                    raise ValueError("NATIVE_HEAD_PLAN_DRIFT")
                plans = read(head_path)
            else:
                plans = []
            over_budget = set()
            for year in range(2020, 2026):
                if not plan_sha:
                    progress("CHECKING_PROVIDER_HEAD", year=year)
                    plans = planning(root, summary, head_path, provider, year=year)
                current = [p for p in plans if p["year"] == year]
                expected = {(row["sensor"], scene["id"]) for row in summary["entries"] if row["year"] == year
                            for scene in row["selected"]}
                if {(p["sensor"], p["scene_id"]) for p in current} != expected or len(current) != len(expected):
                    raise ValueError("NATIVE_HEAD_PLAN_SCOPE_DRIFT")
                record["head_plan_sha256"] = digest(head_path)
                for sensor in ("sentinel-2", "landsat"):
                    if sensor in over_budget:
                        continue
                    batch = [p for p in plans if (p["sensor"], p["year"]) == (sensor, year)]
                    charge = sum(a["bytes"] for p in batch for a in p["assets"].values())
                    grant = extra_bytes if (sensor, year) == ("landsat", 2025) else 0
                    if grant and usage[sensor] + charge - budget[sensor] != grant:
                        raise ValueError("WEST_JAVA_SUPPLEMENT_AMOUNT_DRIFT")
                    if usage[sensor] + charge > budget[sensor] + grant:
                        record["batches"].append({"status": "BUDGET_BLOCKED", "sensor": sensor, "year": year,
                                                  "required_bytes": charge, "remaining_bytes": budget[sensor] - usage[sensor]})
                        over_budget.add(sensor)
                        continue
                    usage[sensor] += charge
                    progress("RUNNING", sensor, year, planned_scenes=len(batch))
                    done = collect_group(root, home, sensor, year, batch, charge, progress, provider, approval_sha,
                                         supplement=extra_pin if grant else None)
                    record["batches"].append({"status": "RAW_COMPLETE", "sensor": sensor, "year": year,
                                              "scenes": len(done["scenes"]), "bytes": charge})
                    progress("BATCH_RAW_COMPLETE", sensor, year)
            progress("BUDGET_BLOCKED" if over_budget else "RAW_COMPLETE")
        except ProviderLimit as error:
            progress("STOPPED_ON_HTTP429", sensor, year, retry_after_seconds=error.delay,
                     provider_stage=error.origin)
            raise
        except (OSError, RuntimeError, ValueError, KeyError) as error:
            progress("STOPPED_ON_ERROR", sensor, year, error={"type": type(error).__name__, "reason": str(error)[:180]})
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--approval-sha256", required=True)
    parser.add_argument("--legacy-ledger", type=Path, required=True)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--head-plan-sha256")
    parser.add_argument("--supplement", type=Path)
    parser.add_argument("--supplement-sha256")
    parser.add_argument("--retry-rate-limit", action="store_true")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    approval, summary = scope(root, args.approval, args.approval_sha256)
    if bool(args.supplement) != bool(args.supplement_sha256) or (args.plan_only and args.supplement):
        parser.error("supplemental approval requires a pinned collection plan")
    supplement = (read_supplement(root, args.supplement, args.supplement_sha256,
                                  args.approval_sha256, args.head_plan_sha256) if args.supplement else None)
    home = root / ROOT
    home.mkdir(parents=True, exist_ok=True)
    head = home / "head-plan.json"
    if args.plan_only:
        planning(root, summary, head, Provider())
        return
    for attempt in range(2 if args.retry_rate_limit else 1):
        try:
            run(root, home, args.legacy_ledger, approval, summary, args.approval_sha256,
                plan_sha=args.head_plan_sha256, supplement=supplement)
            return
        except ProviderLimit as error:
            if attempt or not args.retry_rate_limit:
                raise
            time.sleep(error.delay + 2)


if __name__ == "__main__":
    main()
