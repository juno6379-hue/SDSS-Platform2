"""Download the seven Landsat C2 L2 assets for sealed Banten candidate scenes."""

import argparse
import json
import os
import time
from datetime import datetime
from hashlib import sha256
from http.client import IncompleteRead
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

import rasterio

from services.datahub.sentinel.remote import NoRedirect
from services.lcluc.province_esri import digest, utc, write_json
from services.lcluc.province_optical_plan import DEST, PROVIDERS

SCENES = DEST / "landsat-native"
TOKEN_ROOT = "https://planetarycomputer.microsoft.com/api/sas/v1/token/"
opener = build_opener(NoRedirect())


def check_uri(uri):
    parsed = urlsplit(uri)
    host = parsed.hostname or ""
    account = host.split(".", 1)[0]
    if (
        parsed.scheme != "https"
        or parsed.netloc != host
        or host != account + ".blob.core.windows.net"
        or not account.startswith("landsat")
        or not parsed.path.startswith("/landsat-c2/")
        or not parsed.path.endswith(".TIF")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Unexpected Landsat source asset")
    return account


class PlanetaryComputer:
    def __init__(self):
        self.tokens = {}

    def request(self, uri, *, method="GET", match=None):
        account = check_uri(uri)
        current = datetime.fromisoformat(utc()).timestamp()
        if account not in self.tokens or self.tokens[account][1] < current + 300:
            try:
                with opener.open(TOKEN_ROOT + account + "/landsat-c2", timeout=40) as response:
                    raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError("Token response size")
                token = json.loads(raw)
                expiry = datetime.fromisoformat(token["msft:expiry"].replace("Z", "+00:00"))
                signature = token["token"].lstrip("?")
                if "sig=" not in signature or expiry.timestamp() < current + 60:
                    raise ValueError("Token validity")
                self.tokens[account] = (signature, expiry.timestamp())
            except HTTPError as error:
                raise RuntimeError(f"Landsat token HTTP {error.code} for {account}") from None
        secret = self.tokens[account][0]
        headers = {"If-Match": match} if match else {}
        try:
            return opener.open(
                Request(uri + "?" + secret, method=method, headers=headers), timeout=90
            )
        except HTTPError as error:
            raise RuntimeError(f"Landsat asset HTTP {error.code} for {uri}") from None


def acquisition_plan():
    data = json.loads((DEST / "scene-plan.json").read_text(encoding="utf-8"))
    for row in data["entries"]:
        if row["sensor"] != "landsat":
            continue
        pin = row["pinned_stac"]
        catalog = Path(pin["path"])
        if catalog.stat().st_size != pin["bytes"] or digest(catalog) != pin["sha256"]:
            raise ValueError("Landsat source search page SHA mismatch")
        items = {item["id"]: item for item in json.loads(catalog.read_bytes())["features"]}
        for selected in row["selected"]:
            item = items[selected["id"]]
            yield row["year"], item, row["required_assets"], pin


def get_asset(pc, metadata, path, *, expected=None):
    uri = metadata["href"]
    check_uri(uri)
    receipt = path.with_suffix(".receipt.json")
    if receipt.is_file():
        document = json.loads(receipt.read_text(encoding="utf-8"))
        if (
            document["bytes"] != path.stat().st_size
            or document["sha256"] != digest(path)
            or document["uri"] != uri
            or (expected is not None and (document["bytes"], document["etag"]) != expected)
        ):
            raise ValueError(f"Prior Landsat TIFF verification failed: {path}")
        return document
    if path.exists():
        raise FileExistsError(f"Local asset lacks a receipt: {path}")
    with pc.request(uri, method="HEAD") as response:
        size = int(response.headers["Content-Length"])
        etag = response.headers["ETag"]
    if not 0 < size <= 300_000_000:
        raise ValueError(f"Unexpected Landsat asset size: {size}")
    if expected is not None and (size, etag) != expected:
        raise ValueError("Landsat planned HEAD length or ETag changed")
    checksum = sha256()
    total = 0
    pending = None
    try:
        with (
            pc.request(uri, match=etag) as response,
            NamedTemporaryFile(dir=path.parent, suffix=".tif.part", delete=False) as file,
        ):
            pending = Path(file.name)
            if response.status != 200 or response.headers["ETag"] != etag:
                raise ValueError("Landsat download differs from HEAD")
            while chunk := response.read(2 * 1024**2):
                total += len(chunk)
                if total > size:
                    raise ValueError("Landsat body exceeds HEAD metadata")
                file.write(chunk)
                checksum.update(chunk)
            file.flush()
            os.fsync(file.fileno())
        if total != size:
            raise IncompleteRead(b"", size - total)
        with rasterio.open(pending) as raw:
            if raw.count != 1 or raw.dtypes != ("uint16",) or raw.crs is None:
                raise ValueError("Unexpected Landsat native image")
            grid = {"crs": str(raw.crs), "resolution": list(raw.res), "bounds": list(raw.bounds)}
        result = {
            "path": path.as_posix(),
            "uri": uri,
            "bytes": total,
            "etag": etag,
            "sha256": checksum.hexdigest(),
            "received_at": utc(),
            "native_grid": grid,
            "raster_bands": metadata.get("raster:bands"),
        }
        pending.rename(path)
        write_json(receipt, result)
        return result
    finally:
        if pending and pending.exists():
            pending.unlink()


def run():
    entries = list(acquisition_plan())
    pc = PlanetaryComputer()
    for year, item, bands, pin in entries:
        scene_id = item["id"]
        if not scene_id.startswith(("LC08_", "LC09_")) or any(
            not c.isalnum() and c != "_" for c in scene_id
        ):
            raise ValueError("Invalid Landsat source scene ID")
        directory = SCENES / str(year) / scene_id
        directory.mkdir(parents=True, exist_ok=True)
        assets = {}
        for band in bands:
            for delay in (5, 15, 30, 0):
                try:
                    result = get_asset(pc, item["assets"][band], directory / f"{band}.tif")
                except (ConnectionError, TimeoutError, IncompleteRead, URLError) as error:
                    if not delay:
                        raise
                    print(f"{year} {scene_id} {band}: {type(error).__name__}, retry in {delay}s", flush=True)
                    time.sleep(delay)
                else:
                    break
            assets[band] = result
            print(f"{year} {scene_id} {band} {result['bytes']} {result['sha256']}", flush=True)
        write_json(
            directory / "scene-receipt.json",
            {
                "scene": scene_id,
                "observed_at": item["properties"]["datetime"],
                "collection": PROVIDERS["landsat"][1],
                "stac_page": pin,
                "assets": assets,
            },
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args().execute:
        for year, item, bands, _ in acquisition_plan():
            print(year, item["id"], len(bands), flush=True)
        return
    SCENES.mkdir(parents=True, exist_ok=True)
    lock = SCENES / "collector.lock"
    with lock.open("x") as reservation:
        reservation.write(str(os.getpid()))
    try:
        run()
    finally:
        lock.unlink()


if __name__ == "__main__":
    main()
