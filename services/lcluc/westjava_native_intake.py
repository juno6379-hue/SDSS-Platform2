"""Translate a complete West Java native batch into sensor-specific trial windows."""

import math
from xml.etree import ElementTree

from shapely.geometry import mapping, shape
from shapely.ops import transform

from services.lcluc.annual_inputs import Bands, Pin
from services.lcluc.province_optical_plan import PROJECT, boundary
from services.lcluc.westjava_2020_pilot import LANDSAT_NAMES, scene_uri

S2_IDS = dict(zip(Bands["sentinel-2"], ("1", "2", "3", "7", "11", "12"), strict=True))


def parse_calibration(path, stac, source_uri):
    root = ElementTree.fromstring(path.read_bytes())
    by_tag = {}
    for item in root.iter():
        by_tag.setdefault(item.tag.split("}")[-1], []).append(item)
    product = next((item.text for tag in ("PRODUCT_URI_2A", "PRODUCT_URI") for item in by_tag.get(tag, [])
                    if item.text and "MSIL2A" in item.text), "")
    baseline = next(item.text for item in by_tag["PROCESSING_BASELINE"] if item.text)
    scale = 1 / float(next(item.text for item in by_tag["BOA_QUANTIFICATION_VALUE"] if item.text))
    offsets = {item.get("band_id"): float(item.text) for item in by_tag.get("BOA_ADD_OFFSET", [])}
    if not product or f"/{product.removesuffix('.SAFE')}.SAFE/" not in source_uri or not math.isfinite(scale) or scale <= 0:
        raise ValueError("NATIVE_SENTINEL_CALIBRATION_IDENTITY_MISMATCH")
    if float(baseline) >= 4 and not set(S2_IDS.values()).issubset(offsets):
        raise ValueError("NATIVE_SENTINEL_POST_BASELINE_OFFSETS_MISSING")
    shift = [offsets.get(identifier, 0) * scale for identifier in S2_IDS.values()]
    if any(not math.isfinite(offset) for offset in shift):
        raise ValueError("NATIVE_SENTINEL_NONFINITE_OFFSET")
    return {"verified": True, "product_identity_verified": True, "scale_offset_applied_to_image": False,
            "baseline": baseline, "product_id": stac["id"], "xml_product_uri": product,
            "band_names": list(S2_IDS), "scale": [scale] * len(S2_IDS), "offset": shift}


def asset_pin(row):
    return {key: row[key] for key in ("path", "bytes", "sha256")}


def read_scene(platform, row, sensor, inbox, *, require_existing_calibration=False):
    # Imported lazily so the collector and the usual annual worker can still be used independently.
    from services.datahub.westjava_native import read
    from services.lcluc.annual import store_json
    from services.lcluc.collector_intake import UNPROJECT
    from services.lcluc.regional_worker import pin

    receipt = read(Pin.model_validate(row).local(platform))
    stac_pin = receipt["stac"]
    stac = read(Pin.model_validate(stac_pin).local(platform))
    if receipt["scene_id"] != stac["id"] or receipt["sensor"] != sensor:
        raise ValueError("NATIVE_SCENE_IDENTITY_MISMATCH")
    assets = receipt["assets"]
    if sensor == "sentinel-2":
        xml = Pin.model_validate(asset_pin(assets["product-metadata"])).local(platform)
        from services.lcluc.province_esri import digest

        calibration = parse_calibration(xml, stac, assets["product-metadata"]["uri"])
        calibration["source_xml_sha256"] = digest(xml)
        stage = inbox / ".calibration"
        target = stage / f"{row['sha256']}.json"
        if target.exists() and read(target) != calibration:
            raise ValueError("NATIVE_CALIBRATION_ALREADY_EXISTS_AND_DIFFERS")
        if not target.exists():
            if require_existing_calibration:
                raise FileNotFoundError(target)
            stage.mkdir(exist_ok=True)
            store_json(target, calibration)
        names = {name: name for name in (*Bands[sensor], "SCL")}
        extra = {"calibration": pin(platform, target), "scale": calibration["scale"],
                 "offset": calibration["offset"]}
        version = "sentinel-2-l2a-" + calibration["baseline"]
        license_text = "Copernicus Sentinel data terms"
    else:
        names = {**LANDSAT_NAMES, "QA_RADSAT": "qa_radsat"}
        extra = {"scale": [0.0000275] * 6, "offset": [-0.2] * 6}
        version = "landsat-c2-l2"
        license_text = "USGS Landsat open data"
    return {
        "source_id": stac["id"].lower(), "observed_on": stac["properties"]["datetime"][:10],
        "raw_root": "platform", "provider": "planetary-computer", "uri": scene_uri(stac),
        "version": version, "license": license_text,
        "acquired_at": next(iter(assets.values()))["received_at"], "stac_item": stac_pin,
        "assets": {name: asset_pin(assets[source]) for name, source in names.items()}, **extra,
    }, transform(PROJECT, shape(stac["geometry"])), UNPROJECT


def native_batch_receipt(platform, path, approval_sha, inbox, *, supplemental_approval=None):
    from services.datahub.westjava_landsat_qa import COMPLETION, DESTINATION
    from services.datahub.westjava_native import ASSETS, ROOT, read, read_supplement
    from services.lcluc.collector_intake import (
        MOSAIC_SCHEMA,
        RECEIPT_SCHEMA,
        UNPROJECT,
        landsat_scene,
        optical_window,
    )
    from services.lcluc.province_esri import digest
    from services.lcluc.regional_worker import pin

    batch = read(path)
    sensor, year = batch["sensor"], batch["year"]
    if (
        batch["schema_version"] != "westjava-native-batch/1" or batch["region"] != "west_java"
        or batch["approval_sha256"] != approval_sha
        or (path.parent.name, path.parent.parent.name) != (str(year), sensor)
    ):
        raise ValueError("NATIVE_BATCH_RECEIPT_SCOPE_MISMATCH")
    scenes = []
    byte_sum = 0
    pins = batch["scenes"].copy()
    if (sensor, year) == ("landsat", 2025):
        authority = Pin.model_validate(supplemental_approval)
        if batch.get("supplemental_approval") != authority.model_dump():
            raise ValueError("NATIVE_BATCH_SUPPLEMENTAL_APPROVAL_MISMATCH")
        read_supplement(platform, authority.local(platform), authority.sha256, approval_sha,
                        digest(platform / ROOT / "head-plan.json"))
        pins.append(authority.model_dump())
    for item in batch["scenes"]:
        raw_entry = read(Pin.model_validate(item).local(platform))
        if (raw_entry["sensor"], raw_entry["year"], set(raw_entry["assets"])) != (sensor, year, set(ASSETS[sensor])):
            raise ValueError("NATIVE_BATCH_SCENE_ASSETS_MISMATCH")
        byte_sum += sum(asset["bytes"] for asset in raw_entry["assets"].values())
        scenes.append(read_scene(platform, item, sensor, inbox))
    if byte_sum != batch["expected_bytes"]:
        raise ValueError("NATIVE_BATCH_BYTE_COUNT_MISMATCH")
    newly_collected = {scene["source_id"] for scene, _, _ in scenes}
    if sensor == "landsat":
        for qa_receipt in sorted((platform / DESTINATION).glob("*.complete.json")):
            supplement = read(qa_receipt)
            if supplement["schema_version"] != COMPLETION or supplement["region"] != "west_java":
                raise ValueError("NATIVE_LANDSAT_SUPPLEMENT_SCOPE_MISMATCH")
            for entry in supplement["entries"]:
                if entry["year"] == year:
                    scene, footprint = landsat_scene(platform, entry, supplement)
                    scenes.append((scene, footprint, UNPROJECT))
            pins.append(pin(platform, qa_receipt))
    province = transform(PROJECT, boundary(platform, province="west_java"))
    windows, occupied, dates, identities = [], [], set(), set()
    def priority(item):
        return item[0]["source_id"] not in newly_collected, -item[1].intersection(province).area

    for scene, footprint, unproject in sorted(scenes, key=priority):
        if scene["observed_on"] in dates or scene["source_id"] in identities:
            continue
        split = ("train", "test", "validation")[len(windows)]
        try:
            geom = optical_window(platform, province, scene, footprint, occupied, (0.30, 0.75, 0.50)[len(windows)], sensor)
        except ValueError as error:
            if "SPATIALLY_SEPARATE_QUALITY_WINDOW_UNAVAILABLE" in str(error):
                continue
            raise
        windows.append({"name": f"native-{sensor}-{split}", "split": split, "mosaic": {
            "schema_version": MOSAIC_SCHEMA, "region": "west_java", "year": year, "sensor": sensor,
            "evidence": "real", "geometry": mapping(transform(unproject, geom)), "scenes": [scene],
        }})
        occupied.append(geom)
        dates.add(scene["observed_on"])
        identities.add(scene["source_id"])
        if len(windows) == 3:
            break
    train = len(windows) == 3 and windows[0]["mosaic"]["scenes"][0]["source_id"] in newly_collected
    if not windows:
        raise ValueError("NATIVE_BATCH_HAS_NO_QUALITY_ELIGIBLE_WINDOW")
    flag = "fit_sentinel_candidate" if sensor == "sentinel-2" else "fit_landsat_candidate"
    return {"schema_version": RECEIPT_SCHEMA, "region": "west_java", "year": year, "windows": windows,
            flag: train, "collector_receipts": [pin(platform, path), *pins],
            "candidate_blocked": {} if train else {sensor: "NATIVE_BATCH_NEEDS_3_INDEPENDENT_QA_WINDOWS"}}
