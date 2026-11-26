"""Receive the approved Banten Sentinel-2 native COGs, with byte-range resume."""

import argparse
import json
import os
import re
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

import rasterio

from services.datahub.sentinel.remote import NoRedirect
from services.datahub.sentinel.shared_ledger import active_collectors, exclusive_os_lock
from services.lcluc.province_esri import digest, write_json
from services.lcluc.province_optical_plan import DEST, PROVIDERS

NATIVE = DEST / "sentinel-native"
SOURCE_PLAN = DEST / "sentinel-full-native-head.json"
APPROVED = NATIVE / "approval.json"
PROGRESS = NATIVE / "progress.json"
OBSERVED = NATIVE / "observed-progress.json"
BANDS = PROVIDERS["sentinel-2"][2]
CAP = 21_626_452_905
HOST = "sentinel-cogs.s3.us-west-2.amazonaws.com"


class RateLimited(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def checked_rows():
    approval = json.loads(APPROVED.read_bytes())
    if approval["bytes"] != CAP or digest(SOURCE_PLAN) != approval["head_inventory_sha256"]:
        raise ValueError("Native archive approval pin mismatch")
    data = json.loads(SOURCE_PLAN.read_bytes())
    rows = data["assets"]
    keys = set()
    for row in rows:
        url = urlsplit(row["uri"])
        key = (row["year"], row["scene"], row["band"])
        if (
            row["status"] != 200
            or not 0 < row["bytes"] <= 600_000_000
            or row["year"] not in range(2020, 2026)
            or not re.fullmatch(r"S2[A-C]_\d{2}[A-Z]{3}_\d{8}_\d+_L2A", row["scene"])
            or row["band"] not in BANDS
            or key in keys
            or url.scheme != "https"
            or url.netloc != HOST
            or url.query
            or url.fragment
            or not url.path.startswith("/sentinel-s2-l2a-cogs/")
            or not re.fullmatch(r'"[0-9a-fA-F-]+"', row["etag"])
        ):
            raise ValueError("Invalid native scene plan")
        keys.add(key)
    if len(keys) != 224 or sum(row["bytes"] for row in rows) != CAP:
        raise ValueError("Approved native asset quantity mismatch")
    scenes = {(row["year"], row["scene"]) for row in rows}
    if any(sum(key[:2] == scene for key in keys) != len(BANDS) for scene in scenes):
        raise ValueError("Plan must pin seven assets per scene")
    return rows


def path_for(row):
    return NATIVE / str(row["year"]) / row["scene"] / (row["band"] + ".tif")


def transfer(row, part, stop):
    offset = part.stat().st_size if part.exists() else 0
    expected = row["bytes"]
    if offset > expected:
        raise ValueError("Local partial exceeds approved object")
    if offset == expected:
        return
    headers = {"If-Match": row["etag"], "Accept-Encoding": "identity"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    opener = build_opener(NoRedirect())
    with opener.open(Request(row["uri"], headers=headers), timeout=60) as response:
        if (
            response.headers["ETag"] != row["etag"]
            or int(response.headers["Content-Length"]) != expected - offset
        ):
            raise ValueError("Provider object length or ETag drift")
        if offset:
            if (
                response.status != 206
                or response.headers["Content-Range"] != f"bytes {offset}-{expected - 1}/{expected}"
            ):
                raise ValueError("Provider did not resume at exact byte")
        elif response.status != 200:
            raise ValueError("Unexpected native COG response")
        with part.open("ab") as target:
            # read1 commits returned blocks before a later socket timeout.
            while not stop.is_set() and (chunk := response.read1(1024**2)):
                offset += len(chunk)
                if offset > expected:
                    raise ValueError("Provider exceeded approved byte count")
                target.write(chunk)
                target.flush()
            target.flush()
            os.fsync(target.fileno())
    if not stop.is_set() and offset != expected:
        raise OSError("Incomplete native body")


def one(row, stop):
    if stop.is_set():
        return False
    path = path_for(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = path.with_suffix(".receipt.json")
    part = path.with_suffix(".tif.part")
    if receipt.is_file():
        saved = json.loads(receipt.read_bytes())
        if (
            any(saved[k] != row[k] for k in ("uri", "etag", "bytes"))
            or path.stat().st_size != row["bytes"]
            or digest(path) != saved["sha256"]
        ):
            raise ValueError("Stored native COG failed integrity check")
        return True
    # If process exited after the atomic rename, validate the orphaned file using the same pinned contract.
    if path.exists() and part.exists():
        raise FileExistsError("Duplicate COG and partial")
    for attempt in range(4):
        if stop.is_set():
            return False
        try:
            if not path.exists():
                transfer(row, part, stop)
            break
        except HTTPError as exc:
            if exc.code == 429:
                stop.set()
                raise RateLimited(
                    f"HTTP 429, retry-after={exc.headers.get('Retry-After', 'unspecified')}"
                ) from None
            if exc.code not in {500, 502, 503, 504} or attempt == 3:
                raise RuntimeError(f"Native COG HTTP {exc.code}") from None
        except (OSError, URLError):
            if attempt == 3:
                raise
        stop.wait(min(45, 4 * (2**attempt)))
    if stop.is_set():
        return False
    source = path if path.exists() else part
    if source.stat().st_size != row["bytes"]:
        raise ValueError("Native COG verification size mismatch")
    with rasterio.open(source) as raster:
        expected_dtype = "uint8" if row["band"] == "scl" else "uint16"
        if raster.count != 1 or raster.crs is None or raster.dtypes != (expected_dtype,):
            raise ValueError("Unexpected native Sentinel raster profile")
        profile = {
            "crs": str(raster.crs),
            "shape": [raster.height, raster.width],
            "resolution": list(raster.res),
        }
    saved = {
        **row,
        "sha256": digest(source),
        "path": path.as_posix(),
        "received_at": now(),
        "native_grid": profile,
    }
    if source == part:
        part.rename(path)
    write_json(receipt, saved)
    print(row["year"], row["scene"], row["band"], row["bytes"], saved["sha256"], flush=True)
    return True


def check_scenes(rows):
    scenes = {(row["year"], row["scene"]) for row in rows}
    complete = 0
    for year, scene in sorted(scenes):
        current = [row for row in rows if (row["year"], row["scene"]) == (year, scene)]
        receipts = [path_for(row).with_suffix(".receipt.json") for row in current]
        if not all(path.is_file() for path in receipts):
            continue
        target = receipts[0].parent / "scene-receipt.json"
        if target.is_file():
            complete += 1
            continue
        plan = json.loads((DEST / "scene-plan.json").read_bytes())
        entry = next(
            row for row in plan["entries"] if row["sensor"] == "sentinel-2" and row["year"] == year
        )
        pin = entry["pinned_stac"]
        stac = Path(pin["path"])
        if stac.stat().st_size != pin["bytes"] or digest(stac) != pin["sha256"]:
            raise ValueError("Source STAC search page drift")
        observed = next(row["datetime"] for row in entry["selected"] if row["id"] == scene)
        if not target.is_file():
            write_json(
                target,
                {
                    "scene": scene,
                    "observed_at": observed,
                    "stac_page": pin,
                    "collection": "sentinel-2-l2a",
                    "assets": {
                        row["band"]: json.loads(receipt.read_bytes())
                        for row, receipt in zip(current, receipts, strict=True)
                    },
                },
            )
        complete += 1
    return complete


def log_progress(rows, status, error=None):
    received = [row for row in rows if path_for(row).with_suffix(".receipt.json").is_file()]
    incomplete = [path_for(row).with_suffix(".tif.part") for row in rows if row not in received]
    partial = 0
    for path in incomplete:
        try:
            partial += path.stat().st_size
        except FileNotFoundError:
            pass
    write_json(
        PROGRESS,
        {
            "status": status,
            "pid": os.getpid(),
            "completed_assets": len(received),
            "completed_scenes": check_scenes(rows),
            "approved_assets": len(rows),
            "approved_body_bytes": CAP,
            "verified_source_bytes": sum(row["bytes"] for row in received),
            "partial_file_bytes": partial,
            "error": error,
            "checked_at": now(),
        },
    )


def run(rows, parallel):
    stop = Event()
    failures = []
    log_progress(rows, "RUNNING")
    with ThreadPoolExecutor(max_workers=parallel) as threads:
        futures = {threads.submit(one, row, stop): row for row in rows}
        pending = set(futures)
        while pending:
            completed, pending = wait(pending, timeout=15, return_when=FIRST_COMPLETED)
            for future in completed:
                row = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    stop.set()
                    if not failures or isinstance(exc, RateLimited):
                        failures[:] = [
                            {
                                "type": type(exc).__name__,
                                "message": str(exc),
                                "year": row["year"],
                                "scene": row["scene"],
                                "band": row["band"],
                            }
                        ]
            log_progress(rows, "STOPPING" if failures else "RUNNING")
    log_progress(
        rows,
        (
            "STOPPED_ON_HTTP429"
            if failures[0]["type"] == "RateLimited"
            else "STOPPED_ON_TRANSFER_ERROR"
        )
        if failures
        else "COMPLETE",
        failures[0] if failures else None,
    )
    if failures:
        raise SystemExit(failures[0]["type"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--shared-execution-lock", type=Path)
    parser.add_argument("--parallel", type=int, choices=(1, 2, 3, 4), default=4)
    args = parser.parse_args()
    rows = checked_rows()
    if not args.execute:
        print(len(rows), CAP)
        return
    if not args.shared_execution_lock:
        parser.error("--execute requires the existing Sentinel execution lock path")
    marker = args.shared_execution_lock.resolve()
    if marker.name != "global-ledger.execution.lock":
        parser.error("Unexpected shared lock name")
    coordinator = Path("evidence/onemap_sentinel/coverage-batches/coordinator.lock").resolve()
    with exclusive_os_lock(NATIVE / "collector.lock"):
        while marker.exists() or coordinator.exists() or active_collectors():
            log_progress(rows, "WAITING_FOR_PREVIOUS_SENTINEL_BATCH")
            time.sleep(20)
        with exclusive_os_lock(coordinator), exclusive_os_lock(marker):
            run(rows, args.parallel)


if __name__ == "__main__":
    main()
