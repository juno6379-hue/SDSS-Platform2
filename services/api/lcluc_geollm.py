"""Serve provenance-backed GeoLLM land-cover answers and contextual maps."""

import json
from math import fsum, isclose

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from services.lcluc.banten_historical_trend import (
    OUTPUT,
    TRANSITIONS,
    WORKBOOK,
    WORKBOOK_SHA256,
)
from services.lcluc.province_esri import SNAPSHOT_SHA256
from services.lcluc.question import parse_question
from services.rag.mapbiomas import search as document_search

from .lcluc_sentinel_explorer import PREFIX, PROVINCE, _digest
from .results import check_local

COVERAGE_SHA256 = "55314ca9ec7b8340811355a8016d89506634e8752d302a7071ccf6c9f7c84e82"
TRANSITIONS_SHA256 = "0f02a4e05d9628ef57770a3e631888898be6084dcbf8bb2f97c93098b1e9402c"
ESRI_AUDIT_SHA256 = "495c94ec9859e9c6b26f75a7592cc41004a2163fc35a87050ab59e358c2c621c"
FOREST = {3, 5, 76}
MAPBIOMAS = {
    "forest": FOREST, "forest_formation": {3}, "mangrove": {5}, "peat_forest": {76},
    "rice": {40}, "other_agriculture": {21}, "palm": {35}, "agriculture": {9, 21, 35, 40},
    "urban": {24}, "water": {33}, "aquaculture": {31}, "natural_nonforest": {13}, "nonvegetation": {25},
}
ESRI = {"water": {1}, "trees": {2}, "flooded": {4}, "crops": {5}, "urban": {7}, "bare": {8}, "rangeland": {11}}
NAMES_ESRI = {1: "Water", 2: "Trees", 4: "Flooded vegetation", 5: "Crops", 7: "Built area", 8: "Bare ground",
              9: "Snow/ice", 11: "Rangeland"}


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=400)


class Unavailable(ValueError):
    """A valid query whose evidence or spatial scope is unavailable."""


def checked(store, path, expected):
    file = store.safe_path(path)
    stamp = file.stat()
    if _digest(file, stamp.st_size, stamp.st_mtime_ns, stamp.st_ctime_ns) != expected:
        raise Unavailable("SOURCE_INTEGRITY_FAILURE")
    return file


def codes_for(concept, product, available):
    if concept == "all":
        return set(available)
    if concept == "nonforest" and product == "mapbiomas":
        return set(available) - FOREST - {27}
    known = (MAPBIOMAS if product == "mapbiomas" else ESRI).get(concept, set())
    if not known:
        raise Unavailable("CLASS_NOT_DEFINED_IN_PRODUCT")
    if not (known & available):
        raise Unavailable("CLASS_NOT_PUBLISHED")
    return known & available


def metric(kind, value, *, source_codes=(), destination_codes=(), name=None):
    return {"key": kind, "value": round(value, 2), "unit": "ha", "name": name,
            "from_codes": sorted(source_codes), "to_codes": sorted(destination_codes)}


def sum_transitions(table, period, source_codes, destination_codes, *, aggregate=False):
    if period not in table["periods"]:
        raise Unavailable("PERIOD_NOT_PUBLISHED")
    index = table["periods"].index(period)
    pairs = [table["pairs"].get(f"{origin}:{destination}")
             for origin in sorted(source_codes) for destination in sorted(destination_codes)]
    missing = pairs.count(None)
    present = [pair for pair in pairs if pair is not None]
    values = [pair["areas_ha"][index] for pair in present]
    if not values or None in values or (missing and not aggregate):
        raise Unavailable("TRANSITION_NOT_PUBLISHED")
    return fsum(values), missing, [pair["row"] for pair in present]


def check_forest_margins(cover, table, period, year, forest, available):
    index = cover["years"].index(year)
    known = {row["code"]: row["areas_ha"][index] for row in cover["classes"]}
    for code in sorted(forest):
        value, _, _ = sum_transitions(table, period, {code}, available, aggregate=True)
        if code not in known or not isclose(value, known[code], rel_tol=0, abs_tol=0.005):
            raise Unavailable("FOREST_TRANSITION_COVERAGE_MISMATCH")


def mapbiomas_values(intent, cover, transitions=None):
    names = {row["code"]: row["name"] for row in cover["classes"]}
    years = cover["years"]
    if any(year not in years for year in intent.years):
        raise Unavailable("PERIOD_NOT_PUBLISHED")
    limitations = ["PUBLISHER_PROVINCE_BOUNDARY", "MAPBIOMAS_BOUNDARY_CONTEXT_ONLY"]
    source_rows = []
    if intent.metric in ("area", "forest_net_change"):
        indexes = [years.index(year) for year in intent.years]
        concepts = codes_for(intent.classes[0], "mapbiomas", names.keys())
        selected = {row["code"]: row["areas_ha"] for row in cover["classes"] if row["code"] in concepts}
        if intent.metric == "forest_net_change":
            start, end = [fsum(areas[index] for areas in selected.values()) for index in indexes]
            values = [metric("forest_net_change", end - start, source_codes=concepts),
                      metric("start_forest_area", start, source_codes=concepts),
                      metric("end_forest_area", end, source_codes=concepts)]
        elif intent.classes == ("all",):
            values = [metric("area", areas[indexes[0]], source_codes={code}, name=names[code])
                      for code, areas in selected.items()]
        else:
            values = [metric("area", fsum(areas[indexes[0]] for areas in selected.values()), source_codes=concepts,
                             name=names[next(iter(concepts))] if len(concepts) == 1 else None)]
        return values, names, "COVERAGE", limitations, source_rows

    # Transition-only published classes may be absent from the coverage worksheet.
    available = {int(code) for pair in transitions["pairs"] for code in pair.split(":")}
    origin = codes_for(intent.classes[0], "mapbiomas", available)
    target = codes_for("nonforest" if intent.metric == "forest_loss" else intent.classes[1], "mapbiomas", available)
    if origin & target:
        raise Unavailable("TRANSITION_CLASSES_OVERLAP")
    period = "-".join(map(str, intent.years))
    value, missing, source_rows = sum_transitions(transitions, period, origin, target,
                                                  aggregate=intent.metric == "forest_loss")
    if intent.metric == "forest_loss":
        check_forest_margins(cover, transitions, period, intent.years[0], origin, available)
        limitations.append("FOREST_START_MARGIN_CHECKED")
    if missing:
        limitations.append("GROSS_LOSS_PUBLISHED_PAIRS_ONLY")
    limitations.append("DIRECT_PERIOD_NO_ANNUAL_SUM")
    return [metric(intent.metric, value, source_codes=origin, destination_codes=target)], names, "TRANSITION", limitations, source_rows


def mapbiomas_answer(store, intent):
    checked(store, WORKBOOK, WORKBOOK_SHA256)
    cover = json.loads(checked(store, OUTPUT, COVERAGE_SHA256).read_bytes())
    table = (json.loads(checked(store, TRANSITIONS, TRANSITIONS_SHA256).read_bytes())
             if intent.metric in ("transition", "forest_loss") else None)
    values, names, sheet, limitations, rows = mapbiomas_values(intent, cover, table)
    source = {"name": "MapBiomas Indonesia", "version": "Collection 4.1", "url": cover["source_url"],
              "download_url": cover["workbook_url"], "sha256": WORKBOOK_SHA256, "sheet": sheet,
              "worksheet_rows": rows, "acquired_on": cover["acquired_on"]}
    return values, names, [source], limitations, None


def esri_answer(store, intent):
    if intent.metric.startswith("forest_"):
        raise Unavailable("ESRI_TREES_NOT_FOREST_DEFINITION")
    audit = json.loads(checked(store, f"{PROVINCE}/esri-coverage-and-change.json", ESRI_AUDIT_SHA256).read_bytes())
    if audit["boundary_sha256"] != SNAPSHOT_SHA256:
        raise Unavailable("SOURCE_INTEGRITY_FAILURE")
    annual = {row["year"]: row for row in audit["annual"]}
    if not set(intent.years).issubset(annual):
        raise Unavailable("PERIOD_NOT_PUBLISHED")
    sources = []
    for year in intent.years:
        pin = annual[year]["source_pin"]
        checked(store, pin["path"], pin["sha256"])
        sources.append({"name": "Esri / Impact Observatory", "version": "v003", "year": year,
                        "url": pin["uri"], "sha256": pin["sha256"], "grid": "EPSG:6933 · 10 m"})
    codes = codes_for(intent.classes[0], "esri", NAMES_ESRI.keys())
    start = intent.years[0]
    limitations = ["ESRI_TEN_METRE_GRID", "BOUNDARY_REVIEW_PENDING"]
    if intent.metric == "area":
        cover = annual[start]["area_ha_by_source_code"]
        values = [metric("area", cover[str(code)], source_codes={code}, name=NAMES_ESRI[code])
                  for code in sorted(codes)]
        image = f"/api/lcluc/banten-province-display/{start}"
    else:
        end = intent.years[1]
        pair = next((row for row in audit["pairs"] if (row["from_year"], row["to_year"]) == (start, end)), None)
        if pair is None:
            raise Unavailable("PERIOD_NOT_PUBLISHED")
        origin = next(iter(codes))
        target = next(iter(codes_for(intent.classes[1], "esri", NAMES_ESRI.keys())))
        if origin == target:
            raise Unavailable("TRANSITION_CLASSES_OVERLAP")
        value = pair["transition_matrix_ha"][audit["classes"].index(origin)][audit["classes"].index(target)]
        values = [metric("transition", value, source_codes={origin}, destination_codes={target})]
        image = f"{PREFIX}/transition/{start}/{end}?from_class={origin}&to_class={target}"
        limitations.append("ESRI_TRANSITION_DISPLAY_GRID")
    return values, NAMES_ESRI, sources, limitations, image


def answer_question(store, question):
    intent = parse_question(question)
    if intent.metric == "document":
        return {"route": "rag", **document_search(store, question)}

    response = {"route": "gis", "query": {"intent": intent.metric, "region": intent.region,
                                         "years": intent.years, "product": intent.product, "classes": intent.classes},
                "metrics": [], "sources": [], "citations": []}
    if intent.document:
        response["citations"] = document_search(store, question)["citations"]
    issue = intent.issue
    if not issue and not intent.region:
        issue = "REGION_REQUIRED"
    if not issue and intent.metric == "overlap":
        issue = "OVERLAY_ASSET_NOT_READY"
    if not issue and not intent.product:
        issue = "PRODUCT_REQUIRED"
    if not issue and intent.product not in ("mapbiomas", "esri"):
        issue = "KEMENHUT_ASSET_NOT_READY" if intent.product == "kemenhut" else "PRODUCT_NOT_READY"
    if issue:
        return response | {"status": "BLOCKED", "reason": issue}

    try:
        run = mapbiomas_answer if intent.product == "mapbiomas" else esri_answer
        values, names, sources, limitations, image = run(store, intent)
    except Unavailable as error:
        return response | {"status": "BLOCKED", "reason": str(error)}
    except FileNotFoundError:
        return response | {"status": "BLOCKED", "reason": "EVIDENCE_NOT_READY"}
    except (KeyError, OSError, ValueError):
        return response | {"status": "BLOCKED", "reason": "SOURCE_INTEGRITY_FAILURE"}
    return response | {"status": "VERIFIED_REAL", "metrics": values, "sources": sources,
                       "class_names": names, "limitations": [*limitations, "INDEPENDENT_ACCURACY_UNMEASURED"],
                       "result_id": None, "independent_accuracy_measured": False,
                       "map": {"boundary_url": "/api/lcluc/boundaries/banten", "boundary_sha256": SNAPSHOT_SHA256,
                                "boundary_source": "One Map / BIG", "image_url": image,
                                "background_url": f"/api/lcluc/banten-province-display/{intent.years[-1]}"
                                if image and intent.metric == "transition" else None,
                                "kind": "cover" if image and intent.metric == "area" else
                                "transition" if image else "boundary"}}


def mount_lcluc_geollm(app, store):
    @app.post("/api/lcluc/geollm/query")
    def query_lcluc(request: Request, body: Question):
        check_local(request)
        return answer_question(store, body.question)
