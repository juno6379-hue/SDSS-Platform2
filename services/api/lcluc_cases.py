"""Local LCLUC case catalog. Years, data lineage and assets are exact pins."""

import json
from hashlib import sha256
from io import BytesIO
from threading import Lock
from typing import Annotated, Literal

from fastapi import HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from services.results.registry import ResultRegistry

from .evidence import EvidenceBlocked
from .lcluc_boundaries import mount_lcluc_boundaries
from .lcluc_explorer import mount_explorer_imagery
from .results import DATABASE, check_local, verify_evidence


class BantenYearPair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_year: int = Field(ge=2020, le=2025, strict=True)
    to_year: int = Field(ge=2020, le=2025, strict=True)


ResultID = Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")]
CASE_KEY = "lcluc-analysis/"
NO_CASE = "EXACT_LCLUC_YEAR_PAIR_NOT_AVAILABLE"
PROVINCE_ANALYSIS = Lock()
ESRI_PALETTE = {
    1: "#419bdf",
    2: "#397d49",
    4: "#7a87c6",
    5: "#e49635",
    7: "#c4281b",
    8: "#a59b8f",
    9: "#a8ebff",
    10: "#616161",
    11: "#e3e2c3",
}
ASSETS = {
    "earlier-preview": ("image/png", "inline", "earlier.png"),
    "later-preview": ("image/png", "inline", "later.png"),
    "change-preview": ("image/png", "inline", "change.png"),
    "report": ("application/json", "attachment", "report.json"),
    "matrix": ("text/csv", "attachment", "matrix.csv"),
    "hotspots": ("application/geo+json", "attachment", "hotspots.geojson"),
    "transition": ("image/tiff", "attachment", "transition.tif"),
    "earlier": ("image/tiff", "attachment", "earlier.tif"),
    "later": ("image/tiff", "attachment", "later.tif"),
}


def pinned_bytes(store, pin):
    try:
        path = store.safe_path(pin["path"])
        with path.open("rb") as reader:
            raw = reader.read(pin["bytes"] + 1)
        if len(raw) != pin["bytes"] or sha256(raw).hexdigest() != pin["sha256"]:
            raise EvidenceBlocked("LCLUC_ASSET_INTEGRITY_MISMATCH")
        return raw
    except OSError as error:
        raise EvidenceBlocked("LCLUC_ASSET_UNAVAILABLE") from error


def is_case(row):
    return row["source_key"].startswith(CASE_KEY) and isinstance(row["summary"], dict)


def case_summary(row):
    summary = row["summary"]
    return {
        **{
            key: summary[key]
            for key in ("region", "from_year", "to_year", "source_kind", "taxonomy_id")
        },
        "id": row["id"],
        "evidence_status": row["evidence_status"],
    }


def mount_lcluc_cases(app, store, result_registry=None):
    mount_explorer_imagery(app, store, pinned_bytes)
    mount_lcluc_boundaries(app, store)

    def repository():
        return result_registry if result_registry is not None else ResultRegistry(DATABASE)

    def case_rows(region=None):
        return [
            row
            for row in repository().list_results(domain="lcluc", limit=100)
            if is_case(row) and (region is None or row["summary"]["region"] == region)
        ]

    @app.get("/api/lcluc/taxonomy")
    def taxonomy(request: Request):
        check_local(request)
        from services.lcluc.taxonomy import load_taxonomy

        value = load_taxonomy()
        return {
            "version": value.version,
            "sha256": value.sha256,
            "evidence_status": value.evidence_status,
            "approval_status": value.approval_status,
            "classes": [
                {"code": item.code, "label": item.label, "name_ko": item.name_ko, "role": item.role}
                for item in value.classes
            ],
        }

    @app.get("/api/lcluc/cases")
    def list_cases(
        request: Request,
        region: Annotated[str | None, Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")] = None,
    ):
        check_local(request)
        return {"cases": [case_summary(row) for row in case_rows(region)]}

    @app.get("/api/lcluc/selection")
    def exact_case(
        request: Request,
        region: Annotated[str, Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")],
        from_year: Annotated[int, Query(ge=1972, le=2100)],
        to_year: Annotated[int, Query(ge=1972, le=2100)],
    ):
        check_local(request)
        if from_year >= to_year:
            raise HTTPException(422, detail="LCLUC_YEAR_ORDER_INVALID")
        cases = [
            case_summary(row)
            for row in case_rows(region)
            if row["summary"]["from_year"] == from_year and row["summary"]["to_year"] == to_year
        ]
        return {
            "status": "READY" if cases else "BLOCKED",
            "blockers": [] if cases else [NO_CASE],
            "cases": cases,
        }

    @app.get("/api/lcluc/cases/{result_id}")
    def case_detail(request: Request, result_id: ResultID):
        check_local(request)
        repo = repository()
        row = repo.get(result_id)
        if not is_case(row):
            raise HTTPException(404, detail="LCLUC_CASE_NOT_FOUND")
        catalog = repo.catalog_entry(result_id)
        if catalog["status"] != "CATALOG_READY":
            raise HTTPException(409, detail="LCLUC_CASE_REGISTRATION_PENDING")
        manifest = json.loads(pinned_bytes(store, row["summary"]["report"]))
        verify_evidence(store, row["summary"]["inputs"])
        return {
            **case_summary(row),
            "package_sha256": catalog["package_sha256"],
            "report": manifest,
            "esri_display": {
                "colors": ESRI_PALETTE,
                "earlier": f"/api/lcluc/cases/{result_id}/esri-display/earlier",
                "later": f"/api/lcluc/cases/{result_id}/esri-display/later",
            }
            if row["summary"]["taxonomy_id"] == "esri-io-v003"
            else None,
            "previews": {
                key: f"/api/lcluc/cases/{result_id}/assets/{key}"
                for key in ("earlier-preview", "later-preview", "change-preview")
            },
            "assets": [
                {"id": key, "href": f"/api/lcluc/cases/{result_id}/assets/{key}"}
                for key in ASSETS
                if ASSETS[key][1] == "attachment" and key in row["summary"]["assets"]
            ],
        }

    @app.get("/api/lcluc/banten-province-comparison")
    def banten_compare(request: Request, from_year: int, to_year: int):
        check_local(request)
        from services.lcluc.banten_reports import comparison

        if not 2020 <= from_year < to_year <= 2025:
            raise HTTPException(422, detail="BANTEN_YEAR_PAIR_INVALID")
        pair = comparison(store.root, from_year, to_year)
        if pair is None:
            raise HTTPException(409, detail="BANTEN_PROVINCE_YEARS_NOT_READY")
        return pair[0]

    @app.post("/api/lcluc/banten-province-analysis")
    def banten_analyze(request: Request, pair: BantenYearPair):
        check_local(request)
        from services.lcluc.banten_esri_audit import statistics
        from services.lcluc.banten_reports import comparison

        if pair.from_year >= pair.to_year:
            raise HTTPException(422, detail="BANTEN_YEAR_PAIR_INVALID")
        if not PROVINCE_ANALYSIS.acquire(blocking=False):
            raise HTTPException(409, detail="BANTEN_ANALYSIS_ALREADY_RUNNING")
        try:
            audit = statistics((pair.from_year, pair.to_year))
            result, pins = comparison(store.root, pair.from_year, pair.to_year, source=audit)
            published = comparison(store.root, pair.from_year, pair.to_year)
            if published:
                verified, verified_pins = published
                if (
                    [pin["sha256"] for pin in pins] == [pin["sha256"] for pin in verified_pins]
                    and result["transition_matrix_ha"] != verified["transition_matrix_ha"]
                ):
                    return {
                        **verified,
                        "recalculation": {
                            "status": "DIFFERS_FROM_PUBLISHED",
                            "common_valid_area_ha": result["common_valid_area_ha"],
                            "changed_area_ha": result["changed_area_ha"],
                            "transition_matrix_ha": result["transition_matrix_ha"],
                        },
                    }
            if result["spatial"] is None:
                from services.lcluc.banten_spatial_change import compute

                compute(pair.from_year, pair.to_year, result)
                result, _ = comparison(store.root, pair.from_year, pair.to_year, source=audit)
            return result
        except FileNotFoundError as error:
            raise HTTPException(409, detail="BANTEN_PROVINCE_YEARS_NOT_READY") from error
        except ValueError as error:
            raise HTTPException(409, detail="BANTEN_SOURCE_INTEGRITY_MISMATCH") from error
        finally:
            PROVINCE_ANALYSIS.release()

    @app.post("/api/lcluc/banten-province-reports", status_code=201)
    def banten_publish(request: Request, pair: BantenYearPair):
        check_local(request)
        from services.lcluc.banten_reports import comparison, publish

        if pair.from_year >= pair.to_year:
            raise HTTPException(422, detail="BANTEN_YEAR_PAIR_INVALID")
        result = comparison(store.root, pair.from_year, pair.to_year)
        if result is None:
            raise HTTPException(409, detail="BANTEN_PROVINCE_YEARS_NOT_READY")
        try:
            key = publish(store.root, *result)
        except (OSError, ValueError) as error:
            raise HTTPException(409, detail="BANTEN_SOURCE_INTEGRITY_MISMATCH") from error
        return {
            "id": key,
            "assets": {
                kind: f"/api/lcluc/banten-province-reports/{key}/{kind}"
                for kind in ("html", "json", "csv")
            },
        }

    @app.get("/api/lcluc/banten-province-reports/{key}/{kind}")
    def banten_report(request: Request, key: ResultID, kind: Literal["html", "json", "csv"]):
        check_local(request)
        from services.lcluc.banten_reports import load_report, matrix_csv, report_html

        try:
            raw = load_report(store.root, key)
        except FileNotFoundError as error:
            raise HTTPException(404, detail="BANTEN_PROVINCE_REPORT_NOT_FOUND") from error
        except ValueError as error:
            raise HTTPException(409, detail="BANTEN_REPORT_INTEGRITY_MISMATCH") from error
        if kind == "html":
            return Response(report_html(json.loads(raw)), media_type="text/html")
        headers = {"Content-Disposition": f'attachment; filename="banten-{key[:12]}.{kind}"'}
        if kind == "csv":
            return Response(matrix_csv(json.loads(raw)), media_type="text/csv", headers=headers)
        return Response(raw, media_type="application/json", headers=headers)

    @app.get("/api/lcluc/banten-province-change-preview/{start}/{end}")
    def banten_change_preview(request: Request, start: int, end: int):
        check_local(request)
        from services.lcluc.banten_spatial_change import spatial_path

        if not 2020 <= start < end <= 2025:
            raise HTTPException(422, detail="BANTEN_YEAR_PAIR_INVALID")
        path = store.safe_path(spatial_path(start, end).as_posix())
        if not path.is_file():
            raise HTTPException(404, detail="BANTEN_SPATIAL_RESULT_NOT_READY")
        pin = json.loads(path.read_bytes())["preview"]
        return Response(pinned_bytes(store, pin), media_type="image/png")

    @app.get("/api/lcluc/banten-province-collection")
    def banten_collection(request: Request):
        check_local(request)
        from services.lcluc.banten_esri_audit import REPORT
        from services.lcluc.banten_landsat import SCENES
        from services.lcluc.banten_optical_qa import REPORT as LANDSAT_QA
        from services.lcluc.banten_optical_qa import SENTINEL_REPORT
        from services.lcluc.banten_sentinel_native import NATIVE, OBSERVED, PROGRESS

        def read(relative):
            path = store.safe_path(relative.as_posix())
            return json.loads(path.read_bytes()) if path.is_file() else {}

        progress = read(OBSERVED) or read(PROGRESS)
        sentinel = store.safe_path(NATIVE.as_posix())
        landsat = store.safe_path(SCENES.as_posix())
        return {
            "esri_years": [
                {
                    "year": row["year"],
                    "thematic_valid_pct": row["thematic_valid_pct"],
                    "uri": row["source_pin"]["uri"],
                    "sha256": row["source_pin"]["sha256"],
                }
                for row in read(REPORT).get("annual", [])
            ],
            "sentinel_assets": len(list(sentinel.glob("*/*/*.receipt.json"))),
            "sentinel_scenes": progress.get("completed_scenes", 0),
            "sentinel_status": progress.get("status", "NOT_STARTED"),
            "sentinel_verified_bytes": progress.get("verified_source_bytes", 0),
            "landsat_assets": len(list(landsat.glob("*/*/*.receipt.json"))),
            "landsat_scenes": len(list(landsat.glob("*/*/scene-receipt.json"))),
            "optical_qa": {
                "sentinel-2": read(SENTINEL_REPORT).get("annual", []),
                "landsat": read(LANDSAT_QA).get("annual", []),
            },
        }

    @app.get("/api/lcluc/banten-province-display")
    def banten_province_display(request: Request):
        check_local(request)
        from services.lcluc.banten_esri_preview import INDEX
        from services.lcluc.banten_optical_layers import INDEX as OPTICAL_INDEX

        path = store.safe_path(INDEX.as_posix())
        if not path.is_file():
            return {"years": {}}
        value = json.loads(path.read_bytes())
        index = store.safe_path(OPTICAL_INDEX.as_posix())
        optical = json.loads(index.read_bytes()).get("sensors", {}) if index.is_file() else {}
        return {
            "optical": {
                sensor: {
                    year: {
                        "preview": f"/api/lcluc/banten-province-optical/{sensor}/{year}",
                        "display_clear_pct": pin["display_clear_pct"],
                        "scene_count": len(pin["scene_ids"]),
                    }
                    for year, pin in years.items()
                }
                for sensor, years in optical.items()
            },
            "bounds": value["bounds"],
            "data_resolution_m": value["data_resolution_m"],
            "colors": ESRI_PALETTE,
            "years": {
                year: f"/api/lcluc/banten-province-display/{year}" for year in value["years"]
            },
        }

    @app.get("/api/lcluc/banten-province-optical/{sensor}/{year}")
    def banten_optical_png(
        request: Request,
        sensor: Literal["sentinel-2", "landsat"],
        year: Annotated[int, Path(ge=2020, le=2025)],
    ):
        check_local(request)
        from services.lcluc.banten_optical_layers import DIRECTORY, INDEX

        index = store.safe_path(INDEX.as_posix())
        pin = (
            json.loads(index.read_bytes()).get("sensors", {}).get(sensor, {}).get(str(year))
            if index.is_file()
            else None
        )
        if not pin:
            raise HTTPException(404, detail="BANTEN_OPTICAL_YEAR_NOT_READY")
        data = pinned_bytes(store, {**pin, "path": (DIRECTORY / f"{sensor}-{year}.png").as_posix()})
        return Response(data, media_type="image/png")

    @app.get("/api/lcluc/banten-province-display/{year}")
    def banten_province_png(request: Request, year: Annotated[int, Path(ge=2020, le=2025)]):
        check_local(request)
        from services.lcluc.banten_esri_preview import DIRECTORY, INDEX

        path = store.safe_path(INDEX.as_posix())
        pin = json.loads(path.read_bytes())["years"].get(str(year)) if path.is_file() else None
        if not pin:
            raise HTTPException(404, detail="LCLUC_BANTEN_YEAR_NOT_READY")
        data = pinned_bytes(store, {**pin, "path": (DIRECTORY / f"esri-{year}.png").as_posix()})
        return Response(data, media_type="image/png")

    @app.get("/api/lcluc/cases/{result_id}/esri-display/{year_role}")
    def esri_display(request: Request, result_id: ResultID, year_role: Literal["earlier", "later"]):
        check_local(request)
        repo = repository()
        row = repo.get(result_id)
        if not is_case(row) or row["summary"]["taxonomy_id"] != "esri-io-v003":
            raise HTTPException(404, detail="LCLUC_ESRI_DISPLAY_NOT_FOUND")
        if repo.catalog_entry(result_id)["status"] != "CATALOG_READY":
            raise HTTPException(409, detail="LCLUC_CASE_REGISTRATION_PENDING")
        verify_evidence(store, row["summary"]["inputs"])
        from PIL import Image

        from .lcluc_run import Pair, frame_preview

        pair = Pair.model_validate_json(pinned_bytes(store, row["summary"]["inputs"][0]))
        _, rgba = frame_preview(store, getattr(pair, year_role), ESRI_PALETTE, default_nodata=0)
        output = BytesIO()
        Image.fromarray(rgba).save(output, format="PNG")
        return Response(
            output.getvalue(),
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=300"},
        )

    @app.get("/api/lcluc/cases/{result_id}/assets/{asset_id}")
    def case_asset(request: Request, result_id: ResultID, asset_id: str):
        check_local(request)
        repo = repository()
        row = repo.get(result_id)
        if not is_case(row) or asset_id not in ASSETS or asset_id not in row["summary"]["assets"]:
            raise HTTPException(404, detail="LCLUC_CASE_ASSET_NOT_FOUND")
        if repo.catalog_entry(result_id)["status"] != "CATALOG_READY":
            raise HTTPException(409, detail="LCLUC_CASE_REGISTRATION_PENDING")
        verify_evidence(store, row["summary"]["inputs"])
        media_type, disposition, filename = ASSETS[asset_id]
        content = pinned_bytes(store, row["summary"]["assets"][asset_id])
        return Response(
            content,
            media_type=media_type,
            headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
        )
