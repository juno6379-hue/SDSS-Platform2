"""Acquire provider-native Esri v003 COGs intersecting the pinned six-province AOI."""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from hashlib import file_digest, sha256
from http.client import IncompleteRead
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import rasterio
from shapely.geometry import box, shape

from services.api.lcluc_boundaries import DIRECTORY, SNAPSHOT_SHA256
from services.lcluc.taxonomy import load_taxonomy

YEARS = range(2020, 2026)
BASE = "https://lulctimeseries.blob.core.windows.net/lulctimeseriesv003"
DATASET = "https://livingatlas.arcgis.com/landcover/"
SOURCE = Path(DIRECTORY) / "boundary.geojson"
DEST = Path("data/raw/explorer/province/esri-v003")
YEAR_ENDS = {2024: "20241231", 2025: "20251231"}


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def plan(province=None):
    raw = SOURCE.read_bytes()
    if sha256(raw).hexdigest() != SNAPSHOT_SHA256:
        raise ValueError("Pinned One Map snapshot mismatch")
    provinces = {
        feature["properties"]["province_id"]: shape(feature["geometry"])
        for feature in json.loads(raw)["features"]
    }
    if province:
        provinces = {province: provinces[province]}
    candidates = {
        f"{zone}{band}": box(6 * zone - 186, south, 6 * zone - 180, south + 8)
        for zone in range(47, 53)
        for band, south in (("L", -16), ("M", -8), ("N", 0))
    }
    province_tiles = {
        region: [tile for tile, footprint in candidates.items() if footprint.intersects(geometry)]
        for region, geometry in provinces.items()
    }
    tiles = sorted(set().union(*province_tiles.values()), key=lambda tile: (tile != "48M", tile))
    return province_tiles, [(tile, year) for tile in tiles for year in YEARS]


def write_json(path, document):
    with NamedTemporaryFile(dir=path.parent, suffix=".json.tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write((json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    try:
        # Windows readers can hold a destination open for a moment.
        for attempt in range(10):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.1)
    finally:
        temporary.unlink(missing_ok=True)


def acquire(tile, year, tax_sha):
    end = YEAR_ENDS.get(year, f"{year + 1}0101")
    name = f"{tile}_{year}0101-{end}.tif"
    uri = f"{BASE}/lc{year}/{name}"
    directory = DEST / str(year)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    receipt = path.with_suffix(".receipt.json")
    if receipt.exists():
        saved = json.loads(receipt.read_text(encoding="utf-8"))
        if (
            saved["uri"] != uri
            or saved["boundary_sha256"] != SNAPSHOT_SHA256
            or path.stat().st_size != saved["bytes"]
            or digest(path) != saved["sha256"]
        ):
            raise ValueError(f"Pinned raw file mismatch: {path}")
        return saved
    if path.exists():
        raise FileExistsError(f"Unreceipted destination: {path}")
    with urlopen(Request(uri, method="HEAD"), timeout=45) as metadata:
        length = int(metadata.headers["Content-Length"])
        etag = metadata.headers["ETag"]
    if not 0 < length <= 1_000_000_000:
        raise ValueError(f"Invalid upstream byte length: {length}")
    tmp_path = None
    try:
        checksum = sha256()
        received = 0
        with (
            urlopen(Request(uri, headers={"If-Match": etag}), timeout=90) as source,
            NamedTemporaryFile(dir=directory, suffix=".tif.part", delete=False) as target,
        ):
            tmp_path = Path(target.name)
            if source.status != 200 or source.headers["ETag"] != etag:
                raise ValueError("Provider response does not match HEAD pin")
            while chunk := source.read(2 * 1024**2):
                received += len(chunk)
                if received > length:
                    raise ValueError("Provider body exceeds HEAD length")
                checksum.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        if received != length:
            raise IncompleteRead(b"", length - received)
        with rasterio.open(tmp_path) as raster:
            if raster.count != 1 or raster.dtypes != ("uint8",) or raster.crs is None:
                raise ValueError("Unexpected Esri raster format")
            grid = {
                "crs": str(raster.crs),
                "shape": [raster.height, raster.width],
                "bounds": list(raster.bounds),
            }
        metadata = {
            "dataset": "Esri / Impact Observatory v003",
            "dataset_uri": DATASET,
            "license": "CC-BY-4.0",
            "uri": uri,
            "tile": tile,
            "year": year,
            "path": path.as_posix(),
            "bytes": received,
            "sha256": checksum.hexdigest(),
            "etag": etag,
            "retrieved_at": utc(),
            "native_grid": grid,
            "boundary_sha256": SNAPSHOT_SHA256,
            "taxonomy_sha256": tax_sha,
        }
        tmp_path.rename(path)
        write_json(receipt, metadata)
        return metadata
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--province", choices=("banten",))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    tiles, pairs = plan(args.province)
    print(json.dumps({"province_tiles": tiles, "requested_rasters": len(pairs)}), flush=True)
    if not args.execute:
        return
    DEST.mkdir(parents=True, exist_ok=True)
    taxonomy = load_taxonomy("esri-io-v003")
    # Exclusive creation also prevents a second worker from re-requesting the same tile.
    lock = DEST / "collector.lock"
    with lock.open("x") as reservation:
        reservation.write(str(os.getpid()))
    try:
        for tile, year in pairs:
            for attempt, delay in enumerate((5, 15, 30, 0), start=1):
                try:
                    item = acquire(tile, year, taxonomy.sha256)
                except HTTPError as error:
                    if not delay or error.code not in (408, 500, 502, 503, 504):
                        raise
                    print(f"{tile} {year} attempt {attempt}: HTTP {error.code}; retry in {delay}s", flush=True)
                except (ConnectionError, TimeoutError, IncompleteRead, URLError) as error:
                    if not delay:
                        raise
                    print(f"{tile} {year} attempt {attempt}: {type(error).__name__}; retry in {delay}s", flush=True)
                else:
                    break
                time.sleep(delay)
            print(f"{tile} {year} {item['bytes']} {item['sha256']}", flush=True)
    except HTTPError as error:
        print(f"HTTP {error.code} from {error.url}", flush=True)
        raise
    finally:
        lock.unlink()


if __name__ == "__main__":
    main()
