"""Read-only map overlays from the held, content-pinned BIG boundary snapshot."""

import gzip
import json
from hashlib import sha256
from threading import Lock

from fastapi import HTTPException, Request, Response

from services.datahub.connectors.onemap.boundary import PROVINCES

from .evidence import EvidenceBlocked
from .results import check_local

DIRECTORY = "evidence/onemap_sentinel/audit-20261124/boundary"
SNAPSHOT_SHA256 = "233c034c0b6a777799b14ab5451afedc3ece9abbe836b28e59292a18f4c2a423"
MAX_BOUNDARY_BYTES = 8 * 1024 * 1024


def _read(store, name, expected_sha):
    with store.safe_path(f"{DIRECTORY}/{name}").open("rb") as source:
        raw = source.read(MAX_BOUNDARY_BYTES + 1)
    if len(raw) > MAX_BOUNDARY_BYTES or sha256(raw).hexdigest() != expected_sha:
        raise ValueError("LCLUC_ADMIN_BOUNDARY_PIN_MISMATCH")
    return json.loads(raw)


def _province_features(store, snapshot, region):
    province = next(
        feature
        for feature in snapshot["features"]
        if feature["properties"]["province_id"] == region
    )
    query = next(
        row for row in snapshot["derivation"]["query_evidence"] if row["province_id"] == region
    )
    raw = _read(store, f"{region}.geojson", query["response_sha256"])
    locations = raw["features"]
    province_properties = province["properties"]
    source_ids = {feature["properties"]["objectid"] for feature in locations}
    if (
        raw["type"] != "FeatureCollection"
        or len(locations) != query["feature_count"]
        or len(source_ids) != len(locations)
        or source_ids != set(province_properties["source_object_ids"])
    ):
        raise ValueError("LCLUC_ADMIN_BOUNDARY_SCOPE_MISMATCH")

    def display_feature(feature, level, name):
        geometry = feature["geometry"]
        if (
            geometry["type"] not in ("Polygon", "MultiPolygon")
            or not isinstance(name, str)
            or not name.strip()
        ):
            raise ValueError("LCLUC_ADMIN_BOUNDARY_FEATURE_INVALID")
        return {
            "type": "Feature",
            "geometry": geometry,
            "properties": {"level": level, "name": name, "province_id": region},
        }

    features = [display_feature(province, "province", province_properties["local_name"])]
    features.extend(
        display_feature(feature, "district", feature["properties"]["namobj"])
        for feature in locations
    )
    return features, query["response_sha256"]


def admin_overlay(store, region=None):
    snapshot = _read(store, "boundary.geojson", SNAPSHOT_SHA256)
    regions = [region] if region else PROVINCES
    features = []
    hashes = {}
    for province in regions:
        province_features, hashes[province] = _province_features(store, snapshot, province)
        features.extend(province_features)
    from shapely.geometry import mapping, shape
    from shapely.ops import polylabel

    labels = []
    for feature in features:
        properties = feature["properties"]
        if region is not None and properties["level"] != "province":
            continue
        geometry = shape(feature["geometry"])
        if properties["level"] == "province":
            mainland = (
                max(geometry.geoms, key=lambda part: part.area)
                if geometry.geom_type == "MultiPolygon"
                else geometry
            )
            labels.append(
                {
                    "type": "Feature",
                    "geometry": mapping(polylabel(mainland, tolerance=0.005)),
                    "properties": properties,
                }
            )
        if region is None:
            feature["geometry"] = mapping(geometry.simplify(0.0002, preserve_topology=True))
    return {
        "region": region or "all",
        "province_count": len(hashes),
        "source": {
            "label": "One Map / BIG",
            "uri": snapshot["authority"]["source_url"],
            "acquired_at": snapshot["retrieved_at"],
            "snapshot_sha256": SNAPSHOT_SHA256,
            "district_sha256": hashes[region] if region else None,
            "district_sha256_by_province": hashes,
            "approved_for_project_statistics": snapshot["authority"][
                "approved_for_project_statistics"
            ],
        },
        "district_count": len(features) - len(hashes),
        "geojson": {"type": "FeatureCollection", "features": features},
        "province_labels": {"type": "FeatureCollection", "features": labels},
    }


def mount_lcluc_boundaries(app, store):
    cached = {}
    mutex = Lock()

    def payload(region):
        names = ("boundary", *(PROVINCES if region is None else (region,)))
        with mutex:
            versions = tuple(
                (state.st_mtime_ns, state.st_ctime_ns, state.st_size)
                for name in names
                for state in [store.safe_path(f"{DIRECTORY}/{name}.geojson").stat()]
            )
            hit = cached.get(region)
            if hit is None or hit[0] != versions:
                data = json.dumps(
                    admin_overlay(store, region), ensure_ascii=False, separators=(",", ":")
                ).encode()
                hit = (versions, data, gzip.compress(data, compresslevel=4, mtime=0))
                cached[region] = hit
            return hit[1:]

    @app.get("/api/lcluc/boundaries")
    @app.get("/api/lcluc/boundaries/{region}")
    def boundary(request: Request, region: str | None = None):
        check_local(request)
        if region is not None and region not in PROVINCES:
            raise HTTPException(404, detail="LCLUC_ADMIN_REGION_NOT_SUPPORTED")
        try:
            raw, compressed = payload(region)
            headers = {"Vary": "Accept-Encoding"}
            if "gzip" in request.headers.get("accept-encoding", "").lower():
                headers["Content-Encoding"] = "gzip"
                return Response(compressed, media_type="application/json", headers=headers)
            return Response(raw, media_type="application/json", headers=headers)
        except (EvidenceBlocked, OSError, ValueError, KeyError, TypeError, StopIteration) as error:
            raise HTTPException(409, detail="LCLUC_ADMIN_BOUNDARY_UNAVAILABLE") from error
