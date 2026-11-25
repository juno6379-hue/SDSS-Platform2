"""Normalize pinned institutional evidence and attach it to existing result IDs."""

import argparse
import csv
import json
from hashlib import sha256
from math import isclose

from services.climate_query.numeric import climate_query
from services.results.catalog import Pin, prepare_package
from services.results.registry import ResultRegistry

from .evidence import LOCK_PATH, ROOT, EvidenceStore
from .pinned import LOCK_SHA256
from .results import DATABASE, catalog, verify_evidence

CCKP = "evidence/cckp_indonesia/"
RTRW = "evidence/rtrw-20261125/"
CCKP_KEY = "cckp-cdd-1951-1980"
RTRW_KEY = "rtrw-six-province-review-20261125"


def metric(id_, label, value, unit, source):
    return {"id": id_, "label": label, "value": value, "unit": unit, "source_id": source}


def report(id_, title, pin, source, format_="JSON"):
    return {"id": id_, "title": title, "file": pin, "source_id": source, "format": format_}


def verified_json(store, pin):
    verify_evidence(store, [pin])
    raw = store.safe_path(pin["path"]).read_bytes()
    if len(raw) != pin["bytes"] or sha256(raw).hexdigest() != pin["sha256"]:
        raise ValueError("PIN_CHANGED_DURING_READ")
    return json.loads(raw)


def save_layer(store, path, document):
    raw = json.dumps(document, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    digest = sha256(raw).hexdigest()
    name = f"{path}/{digest}.geojson"
    target = store.safe_path(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        pass
    pin = {"path": name, "bytes": len(raw), "sha256": digest}
    verify_evidence(store, [pin])
    return pin


def cckp_package(store, _registration):
    store.check("cckp")
    files = store._lock()["groups"]["cckp"]["files"]

    def pin(name):
        return {"path": CCKP + name, **files[CCKP + name]}

    request = verified_json(store, pin("query-request.json"))
    result = verified_json(store, pin("numeric-result-validated.json"))
    license_pin = pin("license-evidence.json")
    license_proof = verified_json(store, license_pin)
    replay = climate_query(
        request,
        store.safe_path(CCKP + "global-asset.nc"),
        store.safe_path(CCKP + "raw-receipt.json"),
        license_evidence_path=store.safe_path(license_pin["path"]),
        license_evidence_sha256=license_pin["sha256"],
    )
    fields = ("status", "unit", "time", "valid_cells", "masked_cells")
    if any(replay.get(field) != result[field] for field in fields) or not isclose(
        replay["value"], result["value"], abs_tol=1e-10
    ):
        raise ValueError("CCKP_NUMERIC_REPLAY_MISMATCH")
    if json.loads(json.dumps(replay["geography"])) != result["geography"]:
        raise ValueError("CCKP_GEOGRAPHY_REPLAY_MISMATCH")
    provenance = result["provenance"]
    if replay["provenance"]["raw_sha256"] != provenance["raw_sha256"]:
        raise ValueError("CCKP_ORIGINAL_MISMATCH")

    manifest = verified_json(store, pin("evidence-manifest.json"))
    csv_name = "indonesia-bbox-values.csv"
    csv_pin = {"path": CCKP + csv_name, **manifest["files"][csv_name]}
    verify_evidence(store, [csv_pin])
    features = []
    coordinates_seen = set()
    with store.safe_path(csv_pin["path"]).open(encoding="utf-8", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            coordinates = (float(row["lon_degrees_east"]), float(row["lat_degrees_north"]))
            if coordinates in coordinates_seen:
                raise ValueError("CCKP_GRID_DUPLICATE_COORDINATE")
            coordinates_seen.add(coordinates)
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": coordinates},
                    "properties": {"cdd_days": float(row["cdd_days_1951_1980_climatology"])},
                }
            )
    if len(features) != result["valid_cells"]:
        raise ValueError("CCKP_GRID_CELL_COUNT_MISMATCH")
    layer = save_layer(
        store, "data/curated/results/assets", {"type": "FeatureCollection", "features": features}
    )
    source = "world-bank-cckp"
    return {
        "institution": "World Bank CCKP",
        "adapter": "cckp-era5-cdd/1",
        "spatial": {"crs": "OGC:CRS84", "bbox": result["geography"]["bbox"]},
        "period": {key: result["time"][key] for key in ("start", "end")} | {"kind": "climatology"},
        "metrics": [
            metric(
                "cdd",
                "개발용 경위도 사각형의 면적가중 연속 건조일수",
                result["value"],
                result["unit"],
                source,
            ),
            metric("valid-cells", "유효 격자 수", result["valid_cells"], "count", source),
            metric("masked-cells", "마스킹 격자 수", result["masked_cells"], "count", source),
        ],
        "layers": [
            {
                "id": "cdd-grid",
                "title": "ERA5 0.25° 건조일수 격자 중심",
                "source_id": source,
                "format": "GeoJSON",
                "crs": "OGC:CRS84",
                "nodata": {"kind": "not_applicable"},
                "metric_field": "cdd_days",
                "unit": "days",
                "file": layer,
            }
        ],
        "sources": [
            {
                "id": source,
                "title": "World Bank CCKP · ECMWF / Copernicus ERA5",
                "uri": provenance["source_uri"],
                "version": provenance["local_content_version"],
                "license": license_proof["license"],
                "license_evidence": license_pin,
                "raw": pin("global-asset.nc"),
            }
        ],
        "reports": [
            report(
                "cdd-verification",
                "CCKP 산출 근거와 검산",
                pin("numeric-result-validated.json"),
                source,
            ),
            report("cdd-grid-table", "격자별 값 CSV", csv_pin, source, "CSV"),
        ],
        "uncertainty": {
            "status": "NOT_REPORTED",
            "reason": "ERA5 0.25° 재분석 격자의 개발용 경위도 사각형 집계입니다. 이 결과의 독립 관측 오차나 신뢰구간은 산출하지 않았습니다.",
        },
    }, ("NETCDF_PERIOD_UNITS_AND_MASK_REPLAYED", "PINNED_SUBSET_GRID")


def rtrw_package(store, registration):
    from shapely.geometry import shape

    pins = {entry["path"]: entry for entry in registration["evidence"]}
    raw_pin = pins[RTRW + "banten-historical-sample.geojson"]
    receipt_pin = pins[RTRW + "banten-historical-sample.receipt.json"]
    document = verified_json(store, raw_pin)
    receipt = verified_json(store, receipt_pin)
    features = document["features"]
    if (
        len(features) != receipt["sample"]["physical_features"]
        or [feature["properties"] for feature in features] != receipt["sample"]["properties"]
        or receipt["sha256"] != raw_pin["sha256"]
        or receipt["bytes"] != raw_pin["bytes"]
        or receipt["current_ordinance_match"] is not False
    ):
        raise ValueError("BIG_HISTORICAL_SAMPLE_RECEIPT_MISMATCH")
    source = "big-one-map"
    return {
        "institution": "BIG One Map",
        "adapter": "big-rtrw-rest-sample/1",
        "spatial": {"crs": "OGC:CRS84", "bbox": shape(features[0]["geometry"]).bounds},
        "period": None,
        "period_reason": "2017년 조례 표기가 있는 과거 표본입니다. 현행 법적 효력 기간은 확인되지 않았습니다.",
        "metrics": [
            metric(
                "historical-features",
                "보존한 반텐 과거 표본 도형 수",
                len(features),
                "count",
                source,
            )
        ],
        "layers": [
            {
                "id": "banten-historical",
                "title": "반텐 과거 용도지역 폴리곤 표본",
                "format": "GeoJSON",
                "crs": "OGC:CRS84",
                "nodata": {"kind": "not_applicable"},
                "file": raw_pin,
                "source_id": source,
            }
        ],
        "sources": [
            {
                "id": source,
                "title": "BIG One Map Pola Ruang REST",
                "uri": receipt["source_uri"],
                "version": features[0]["properties"]["nothpd"],
                "license": receipt["license"],
                "raw": raw_pin,
            }
        ],
        "reports": [
            report("historical-receipt", "BIG 수신 영수증과 조례 검토 결과", receipt_pin, source)
        ],
        "uncertainty": {
            "status": "NOT_REPORTED",
            "reason": "단일 과거 폴리곤의 출처만 검증했습니다. 반텐 전체 범위, 현행 용도지역과 위치 정확도는 평가하지 않았습니다.",
        },
    }, ("BIG_REST_RECEIPT_AND_FEATURE_PROVENANCE",)


def attach(store, repo, result_id, package, checks=()):
    normalized = prepare_package(
        package,
        safe_path=store.safe_path,
        verify_pins=lambda pins: verify_evidence(store, pins),
        adapter_checks=checks,
    )
    repo.attach_package(result_id, normalized)
    return repo.catalog_entry(result_id)


def seed_verified(store, repo, sources=(CCKP_KEY, RTRW_KEY)):
    registrations = catalog()
    attached = []
    for key, builder in ((CCKP_KEY, cckp_package), (RTRW_KEY, rtrw_package)):
        if key not in sources:
            continue
        registration = registrations[key]
        verify_evidence(store, registration["evidence"])
        package, checks = builder(store, registration)
        result = repo.register(source_key=key, **registration)
        attached.append(attach(store, repo, result["id"], package, checks))
    return attached


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-verified", action="store_true")
    parser.add_argument("--source", choices=(CCKP_KEY, RTRW_KEY), action="append")
    parser.add_argument("--result-id")
    parser.add_argument("--manifest")
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    generic = (args.result_id, args.manifest, args.manifest_sha256)
    if (args.seed_verified and any(generic)) or (not args.seed_verified and not all(generic)):
        parser.error("Use --seed-verified or all of --result-id, --manifest, --manifest-sha256.")
    if args.source and not args.seed_verified:
        parser.error("--source requires --seed-verified.")
    store = EvidenceStore(ROOT, LOCK_PATH, LOCK_SHA256)
    repo = ResultRegistry(DATABASE)
    if args.seed_verified:
        results = seed_verified(store, repo, args.source or (CCKP_KEY, RTRW_KEY))
    else:
        path = store.safe_path(args.manifest)
        pin = Pin(path=args.manifest, sha256=args.manifest_sha256, bytes=path.stat().st_size)
        source = verified_json(store, pin.model_dump())
        if (
            source.get("schema_version") != "sdss-institution-result/1"
            or source.get("result_id") != args.result_id
        ):
            parser.error(
                "Institutional manifest must declare the same result ID and supported schema."
            )
        results = [attach(store, repo, args.result_id, source["package"])]
    for result in results:
        print(json.dumps({key: result[key] for key in ("result_id", "status", "package_sha256")}))


if __name__ == "__main__":
    main()
