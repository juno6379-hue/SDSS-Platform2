"""Serve provenance-backed GeoLLM land-cover answers and contextual maps."""

from math import fsum, isclose

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from services.lcluc.banten_historical_trend import WORKBOOK_SHA256
from services.lcluc.geollm_lake import BASE as LAKE_MAP
from services.lcluc.geollm_lake import PRODUCT_YEARS
from services.lcluc.province_esri import SNAPSHOT_SHA256
from services.lcluc.question import parse_question

from .geollm_storage import DataLakeGeoLLMStorage, StorageBlocked, Unavailable
from .results import check_local

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


def mapbiomas_answer(storage, intent):
    cover, table = storage.mapbiomas(intent.metric in ("transition", "forest_loss"))
    values, names, sheet, limitations, rows = mapbiomas_values(intent, cover, table)
    source = {"name": "MapBiomas Indonesia", "version": "Collection 4.1", "url": cover["source_url"],
              "download_url": cover["workbook_url"], "sha256": WORKBOOK_SHA256, "sheet": sheet,
              "worksheet_rows": rows, "acquired_on": cover["acquired_on"]}
    return values, names, [source], limitations, None


def esri_answer(storage, intent):
    if intent.metric.startswith("forest_"):
        raise Unavailable("ESRI_TREES_NOT_FOREST_DEFINITION")
    audit = storage.esri_audit()
    if audit["boundary_sha256"] != SNAPSHOT_SHA256:
        raise Unavailable("SOURCE_INTEGRITY_FAILURE")
    annual = {row["year"]: row for row in audit["annual"]}
    if not set(intent.years).issubset(annual):
        raise Unavailable("PERIOD_NOT_PUBLISHED")
    sources = []
    for year in intent.years:
        pin = annual[year]["source_pin"]
        storage.attest_esri(year, pin)
        sources.append({"name": "Esri / Impact Observatory", "version": "v003", "year": year,
                        "url": pin["uri"], "sha256": pin["sha256"], "grid": "EPSG:6933 · 10 m"})
    codes = codes_for(intent.classes[0], "esri", NAMES_ESRI.keys())
    start = intent.years[0]
    limitations = ["ESRI_TEN_METRE_GRID", "BOUNDARY_REVIEW_PENDING"]
    if intent.metric == "area":
        cover = annual[start]["area_ha_by_source_code"]
        values = [metric("area", cover[str(code)], source_codes={code}, name=NAMES_ESRI[code])
                  for code in sorted(codes)]
        image = f"{storage.cover_url}/{start}"
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
        image = f"{storage.transition_url}/{start}/{end}?from_class={origin}&to_class={target}"
        limitations.append("ESRI_TRANSITION_DISPLAY_GRID")
    return values, NAMES_ESRI, sources, limitations, image


def search_documents(storage, question):
    try:
        return storage.search(question)
    except StorageBlocked as error:
        return {"status": "BLOCKED", "reason": str(error), "citations": [], "answer": None}


def answer_question(storage, question):
    intent = parse_question(question)
    if intent.metric == "document":
        return {"route": "rag", **search_documents(storage, question)}

    response = {"route": "gis", "query": {"intent": intent.metric, "region": intent.region,
                                         "years": intent.years, "product": intent.product, "classes": intent.classes},
                "metrics": [], "sources": [], "citations": []}
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
        values, names, sources, limitations, image = run(storage, intent)
        if intent.document:
            response["citations"] = storage.search(question)["citations"]
    except Unavailable as error:
        return response | {"status": "BLOCKED", "reason": str(error)}
    except FileNotFoundError:
        return response | {"status": "BLOCKED", "reason": "EVIDENCE_NOT_READY"}
    except (KeyError, OSError, ValueError):
        return response | {"status": "BLOCKED", "reason": "SOURCE_INTEGRITY_FAILURE"}
    response |= storage.provenance
    return response | {"status": "VERIFIED_REAL", "metrics": values, "sources": sources,
                       "class_names": names, "limitations": [*limitations, "INDEPENDENT_ACCURACY_UNMEASURED"],
                       "result_id": None, "independent_accuracy_measured": False,
                       "map": {"boundary_url": storage.boundary_url, "boundary_sha256": SNAPSHOT_SHA256,
                                "boundary_source": "One Map / BIG", "image_url": image,
                                "background_url": f"{storage.cover_url}/{intent.years[-1]}"
                                if image and intent.metric == "transition" else None,
                                "kind": "cover" if image and intent.metric == "area" else
                                "transition" if image else "boundary"}}


def mount_lcluc_geollm(app, storage):
    @app.post("/api/lcluc/geollm/query")
    def query_lcluc(request: Request, body: Question):
        check_local(request)
        return answer_question(storage, body.question)


    if not isinstance(storage, DataLakeGeoLLMStorage):
        return

    @app.get(LAKE_MAP + "/boundary")
    def lake_boundary(request: Request):
        check_local(request)
        try:
            return storage.boundary()
        except StorageBlocked as error:
            raise HTTPException(503, detail=str(error)) from None

    @app.get(LAKE_MAP + "/cover/{year}")
    def lake_cover(request: Request, year: int):
        check_local(request)
        if year not in PRODUCT_YEARS:
            raise HTTPException(404, detail="GEOLLM_MAP_YEAR_UNAVAILABLE")
        try:
            return Response(storage.cover(year), media_type="image/png")
        except StorageBlocked as error:
            raise HTTPException(503, detail=str(error)) from None

    @app.get(LAKE_MAP + "/transition/{start}/{end}")
    def lake_transition(request: Request, start: int, end: int, from_class: int, to_class: int):
        check_local(request)
        if (start not in PRODUCT_YEARS or end not in PRODUCT_YEARS or start >= end
                or from_class == to_class or not {from_class, to_class} <= NAMES_ESRI.keys()):
            raise HTTPException(422, detail="GEOLLM_TRANSITION_INPUT_INVALID")
        try:
            return Response(storage.transition(start, end, from_class, to_class), media_type="image/png")
        except StorageBlocked as error:
            raise HTTPException(503, detail=str(error)) from None
