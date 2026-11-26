"""Read-only API for the pinned Banten Sentinel-2 explorer."""

import csv
import json
from functools import lru_cache
from hashlib import file_digest
from io import BytesIO, StringIO
from math import isfinite
from typing import Literal

from fastapi import HTTPException, Query, Request, Response
from fastapi.responses import FileResponse

from .results import check_local

PREFIX = "/api/lcluc/banten-sentinel-explorer"
ROOT = "data/curated/explorer/banten-province/sentinel-explore"
PROVINCE = "data/curated/explorer/banten-province"
YearLayer = Literal["natural", "infrared", "ndvi", "ndwi", "nbr", "quality", "spectral", "land-cover"]


@lru_cache(maxsize=96)
def _digest(path, _size, _mtime, _ctime):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


@lru_cache(maxsize=48)
def _thumbnail(path, _sha256):
    from PIL import Image

    with Image.open(path) as image:
        image.thumbnail((72, 48))
        target = BytesIO()
        image.save(target, "PNG")
        return target.getvalue()


def year_pair(start, end):
    if not 2020 <= start < end <= 2025:
        raise HTTPException(422, detail="BANTEN_YEAR_PAIR_INVALID")


def read_bbox(text):
    if text is None:
        return None
    try:
        w, s, e, n = map(float, text.split(","))
    except ValueError as error:
        raise HTTPException(422, detail="AOI_BOUNDS_INVALID") from error
    if not (all(map(isfinite, (w, s, e, n))) and 104 <= w < e <= 108 and -9 <= s < n <= -4):
        raise HTTPException(422, detail="AOI_BOUNDS_INVALID")
    return w, s, e, n


def stats_csv(payload):
    stream = StringIO()
    rows = csv.writer(stream)
    rows.writerow([
        "source", "scope", "aoi_wgs84", "type", "year", "from_year", "to_year", "from_class",
        "to_class", "area_ha", "share_pct", "denominator_ha",
    ])
    prefix = ["Esri / Impact Observatory v003", payload["scope"], json.dumps(payload["bbox"])]
    for annual in payload["annual"]:
        for row in annual["classes"]:
            rows.writerow([*prefix, "land_cover", annual["year"], "", "", "", row["code"],
                           row["area_ha"], row["share_pct"], annual["valid_ha"]])
    names = [row["code"] for row in payload["annual"][0]["classes"]]
    for from_code, values in zip(names, payload["transition_matrix_ha"], strict=True):
        for to_code, area in zip(names, values, strict=True):
            denominator = payload["common_valid_ha"]
            rows.writerow([*prefix, "transition", "", payload["from_year"], payload["to_year"],
                           from_code, to_code, area, 100 * area / denominator if denominator else "", denominator])
    return stream.getvalue()


def mount_sentinel_explorer(app, store):
    def record(name):
        path = store.safe_path(f"{ROOT}/{name}")
        if not path.is_file():
            raise HTTPException(404, detail="SENTINEL_EXPLORER_ASSET_PENDING")
        return json.loads(path.read_bytes())

    def checked(pin):
        path = store.safe_path(pin["path"])
        try:
            stat = path.stat()
            if not path.is_file() or stat.st_size != pin["bytes"] or _digest(
                path, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns,
            ) != pin["sha256"]:
                raise ValueError("fingerprint mismatch")
        except (OSError, ValueError) as error:
            raise HTTPException(409, detail="SENTINEL_EXPLORER_ASSET_INTEGRITY_FAILURE") from error
        return path

    @app.get(PREFIX)
    def catalog(request: Request):
        check_local(request)
        return {
            "region": "banten",
            "spectral_years": [year for year in range(2020, 2026)
                               if store.safe_path(f"{ROOT}/{year}/spectral.json").is_file()],
            "cover_years": [year for year in range(2020, 2026)
                            if store.safe_path(f"{ROOT}/{year}/land-cover.json").is_file()],
            "change_pairs": [[a, b] for a in range(2020, 2026) for b in range(a + 1, 2026)
                             if store.safe_path(f"{ROOT}/change/{a}-{b}.json").is_file()],
        }

    @app.get(PREFIX + "/years/{year}/metadata")
    def metadata(request: Request, year: int):
        check_local(request)
        if not 2020 <= year <= 2025:
            raise HTTPException(422, detail="BANTEN_YEAR_INVALID")
        return record(f"{year}/spectral.json")

    @app.get(PREFIX + "/years/{year}/layers/{layer}")
    def year_asset(request: Request, year: int, layer: YearLayer, download: bool = False, thumbnail: bool = False):
        check_local(request)
        if not 2020 <= year <= 2025:
            raise HTTPException(422, detail="BANTEN_YEAR_INVALID")
        if layer == "land-cover":
            pin = record(f"{year}/land-cover.json")["raster"]
            extension = "tif"
        else:
            document = record(f"{year}/spectral.json")
            extension = "tif" if layer == "spectral" else "png"
            pin = document["raster"] if layer == "spectral" else document["layers"][layer]
        path = checked(pin)
        if thumbnail and extension == "png" and not download:
            return Response(_thumbnail(path, pin["sha256"]), media_type="image/png",
                            headers={"ETag": f'"{pin["sha256"]}-thumb"', "Cache-Control": "private, max-age=300"})
        return FileResponse(
            path, media_type="image/tiff" if extension == "tif" else "image/png",
            filename=f"banten-{year}-{layer}.{extension}" if download or extension == "tif" else None,
            headers={"X-Artifact-Sha256": pin["sha256"]},
        )

    @app.get(PREFIX + "/change/{start}/{end}/{kind}")
    def change_asset(request: Request, start: int, end: int, kind: Literal["overlay", "raster"]):
        check_local(request)
        year_pair(start, end)
        pin = record(f"change/{start}-{end}.json")["preview" if kind == "overlay" else "raster"]
        return FileResponse(
            checked(pin), media_type="image/png" if kind == "overlay" else "image/tiff",
            filename=f"banten-{start}-{end}-esri-change.tif" if kind == "raster" else None,
            headers={"X-Artifact-Sha256": pin["sha256"]},
        )

    @app.get(PREFIX + "/transition/{start}/{end}")
    def transition_asset(request: Request, start: int, end: int, from_class: int, to_class: int,
                         bbox: str | None = Query(default=None, max_length=100)):
        check_local(request)
        from services.lcluc.banten_sentinel_explorer import THEMATIC
        from services.lcluc.banten_sentinel_statistics import transition_preview

        year_pair(start, end)
        if from_class == to_class or any(code not in THEMATIC for code in (from_class, to_class)):
            raise HTTPException(422, detail="BANTEN_TRANSITION_CLASSES_INVALID")
        first, second = (record(f"{year}/land-cover.json")["raster"] for year in (start, end))
        bounds = read_bbox(bbox)
        changed = transition_preview(store.root, checked(first), checked(second), first["sha256"], second["sha256"],
                                     from_class, to_class, bounds)
        return Response(changed, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})

    @app.get(PREFIX + "/product-support")
    def product_support(request: Request):
        check_local(request)
        from services.lcluc.banten_product_agreement import OUTPUT as AGREEMENT
        from services.lcluc.province_esri import SNAPSHOT_SHA256

        output = {}
        for sensor, file in (("sentinel-2", "sentinel-esri-support"), ("landsat", "landsat-esri-support")):
            path = store.safe_path(f"{PROVINCE}/{file}.json")
            if not path.is_file():
                continue
            report = json.loads(path.read_bytes())
            if report.get("boundary_sha256") != SNAPSHOT_SHA256 or report.get("region") != "banten":
                raise HTTPException(409, detail="BANTEN_SUPPORT_BOUNDARY_MISMATCH")
            output[sensor] = report
        path = store.safe_path(AGREEMENT.as_posix())
        agreement = json.loads(path.read_bytes()) if path.is_file() else None
        if agreement and (agreement.get("boundary_sha256") != SNAPSHOT_SHA256
                          or agreement.get("region") != "banten" or agreement.get("year") != 2021):
            raise HTTPException(409, detail="BANTEN_AGREEMENT_SOURCE_MISMATCH")
        return {"scope": "province_boundary", "reports": output, "thematic_agreement": agreement}

    @app.get(PREFIX + "/historical-trend")
    def historical_trend(request: Request, download: bool = False):
        check_local(request)
        from services.lcluc.banten_historical_trend import OUTPUT, WORKBOOK_SHA256

        path = store.safe_path(OUTPUT.as_posix())
        if not path.is_file():
            raise HTTPException(404, detail="BANTEN_HISTORICAL_TREND_PENDING")
        payload = json.loads(path.read_bytes())
        if payload.get("sha256") != WORKBOOK_SHA256 or payload.get("region") != "banten":
            raise HTTPException(409, detail="BANTEN_HISTORICAL_TREND_SOURCE_MISMATCH")
        if download:
            return FileResponse(path, media_type="application/json", filename="banten-mapbiomas-4.1-1990-2024.json")
        return payload

    @app.get(PREFIX + "/mapbiomas-area-comparison")
    def mapbiomas_area_comparison(request: Request, year: int | None = None):
        check_local(request)
        from services.lcluc.banten_area_comparison import compare
        from services.lcluc.banten_historical_trend import OUTPUT, WORKBOOK_SHA256
        from services.lcluc.province_esri import SNAPSHOT_SHA256

        try:
            historical = json.loads(store.safe_path(OUTPUT).read_bytes())
            annual = json.loads(store.safe_path(f"{PROVINCE}/esri-coverage-and-change.json").read_bytes())
        except FileNotFoundError as error:
            raise HTTPException(404, detail="BANTEN_AREA_COMPARISON_PENDING") from error
        if (historical.get("sha256") != WORKBOOK_SHA256 or historical.get("region") != "banten"
                or annual.get("region") != "banten" or annual.get("boundary_sha256") != SNAPSHOT_SHA256):
            raise HTTPException(409, detail="BANTEN_AREA_COMPARISON_SOURCE_MISMATCH")
        try:
            return compare(annual, historical, year)
        except ValueError as error:
            raise HTTPException(422, detail=str(error)) from error

    @app.get(PREFIX + "/statistics")
    def statistics(request: Request, from_year: int, to_year: int,
                   bbox: str | None = Query(default=None, max_length=100),
                   format: Literal["csv", "json"] = "json", download: bool = False):
        check_local(request)
        from services.lcluc.banten_sentinel_statistics import (
            province_statistics,
            rectangle_statistics,
        )

        year_pair(from_year, to_year)
        bounds = read_bbox(bbox)
        try:
            if bounds:
                rasters = {year: checked(record(f"{year}/land-cover.json")["raster"]) for year in range(2020, 2026)}
                payload = rectangle_statistics(store.root, from_year, to_year, bounds, rasters)
            else:
                payload = province_statistics(store.root, from_year, to_year)
        except FileNotFoundError as error:
            raise HTTPException(404, detail="SENTINEL_EXPLORER_STATS_PENDING") from error
        except ValueError as error:
            raise HTTPException(422, detail=str(error)) from error
        if format == "csv" or download:
            body = "\ufeff" + stats_csv(payload) if format == "csv" else json.dumps(payload, ensure_ascii=False)
            return Response(
                body, media_type="text/csv" if format == "csv" else "application/json",
                headers={"Content-Disposition": f'attachment; filename="banten-{from_year}-{to_year}-aoi.{format}"'},
            )
        return payload

    @app.get(PREFIX + "/point")
    def point(request: Request, from_year: int, to_year: int,
              lon: float = Query(ge=104, le=108, allow_inf_nan=False),
              lat: float = Query(ge=-9, le=-4, allow_inf_nan=False)):
        check_local(request)
        from services.lcluc.banten_sentinel_statistics import sample_point

        year_pair(from_year, to_year)
        years = []
        for year in (from_year, to_year):
            spectral = checked(record(f"{year}/spectral.json")["raster"])
            cover = checked(record(f"{year}/land-cover.json")["raster"])
            years.append({"year": year, **sample_point(spectral, cover, lon, lat)})
        return {"longitude": lon, "latitude": lat, "years": years}
