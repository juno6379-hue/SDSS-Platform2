"""Seal Banten optical candidates against the held province polygon and exact year."""

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

from services.lcluc.province_esri import SNAPSHOT_SHA256, SOURCE, YEARS, digest, write_json

PROVIDERS = {
    "sentinel-2": (
        "https://earth-search.aws.element84.com/v1/search",
        "sentinel-2-l2a",
        ("blue", "green", "red", "nir", "swir16", "swir22", "scl"),
    ),
    "landsat": (
        "https://planetarycomputer.microsoft.com/api/stac/v1/search",
        "landsat-c2-l2",
        ("blue", "green", "red", "nir08", "swir16", "swir22", "qa_pixel"),
    ),
}
DEST = Path("data/raw/explorer/province/banten-optical")
PROJECT = Transformer.from_crs(4326, 6933, always_xy=True).transform


def boundary(root=Path(".")):
    source = root / SOURCE
    if digest(source) != SNAPSHOT_SHA256:
        raise ValueError("Pinned One Map snapshot mismatch")
    features = json.loads(source.read_text(encoding="utf-8"))["features"]
    return shape(
        next(row["geometry"] for row in features if row["properties"]["province_id"] == "banten")
    )


def catalog_search(provider, year, bbox):
    server, collection, assets = PROVIDERS[provider]
    params = {
        "collections": collection,
        "bbox": ",".join(map(str, bbox)),
        "limit": 100,
        "datetime": f"{year}-06-01T00:00:00Z/{year}-10-31T23:59:59Z",
    }
    if provider == "landsat":
        params["sortby"] = "+eo:cloud_cover"
    uri = server + "?" + urlencode(params)
    path = DEST / f"{provider}-{year}.stac.json"
    if not path.exists():
        with urlopen(uri, timeout=45) as response:
            raw = response.read(24 * 1024**2 + 1)
        if len(raw) > 24 * 1024**2:
            raise ValueError("Unbounded STAC response")
        page = json.loads(raw)
        with path.open("xb") as target:
            target.write(raw)
    else:
        page = json.loads(path.read_text(encoding="utf-8"))
    candidates = [
        item
        for item in page["features"]
        if item["collection"] == collection
        and item["properties"]["datetime"].startswith(str(year))
        and set(assets).issubset(item["assets"])
        and item["properties"].get("platform")
        in ("sentinel-2a", "sentinel-2b", "sentinel-2c", "landsat-8", "landsat-9")
    ]
    return uri, path, candidates


def pick_items(candidates, geometry):
    """Prioritize effective footprint; keep the residual area measurable."""
    remaining = geometry
    projected = [
        (item, transform(PROJECT, shape(item["geometry"])).intersection(geometry))
        for item in candidates
    ]
    chosen = []
    while projected:
        scored = []
        for item, footprint in projected:
            area = remaining.intersection(footprint).area
            cloud = item["properties"].get("eo:cloud_cover", 100)
            effective = area * (1 - min(100, cloud) / 100)
            scored.append((effective, item["id"], area, item, footprint))
        _, _, area, item, footprint = max(scored, key=lambda row: row[:3])
        if area < 100:
            break
        chosen.append(
            {
                "id": item["id"],
                "datetime": item["properties"]["datetime"],
                "scene_cloud_pct": item["properties"].get("eo:cloud_cover"),
                "added_footprint_m2": area,
            }
        )
        remaining = remaining.difference(footprint)
        if remaining.area < 100:
            break
        projected = [
            (candidate, region) for candidate, region in projected if candidate["id"] != item["id"]
        ]
    return chosen, remaining.area


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    aoi = boundary()
    area = transform(PROJECT, aoi)
    entries = []
    for provider in PROVIDERS:
        for year in YEARS:
            uri, path, candidates = catalog_search(provider, year, aoi.bounds)
            selected, missing = pick_items(candidates, area)
            entries.append(
                {
                    "sensor": provider,
                    "year": year,
                    "query_uri": uri,
                    "pinned_stac": {
                        "path": path.as_posix(),
                        "sha256": digest(path),
                        "bytes": path.stat().st_size,
                    },
                    "candidates": len(candidates),
                    "required_assets": list(PROVIDERS[provider][2]),
                    "footprint_remaining_m2": missing,
                    "coverage_pct": (1 - missing / area.area) * 100,
                    "selected": selected,
                }
            )
            print(
                provider,
                year,
                len(candidates),
                len(selected),
                f"{entries[-1]['coverage_pct']:.5f}%",
                flush=True,
            )
    write_json(
        DEST / "scene-plan.json",
        {
            "boundary_sha256": SNAPSHOT_SHA256,
            "region": "banten",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "scope": "June through October, selected geometrical footprint coverage; pixel/QA validation pending",
            "province_area_m2": area.area,
            "entries": entries,
        },
    )


if __name__ == "__main__":
    main()
