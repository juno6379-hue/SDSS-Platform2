"""Publish a pinned Banten GeoLLM release to the explicitly scoped Staging lake."""

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from hashlib import file_digest
from pathlib import Path

from services.api.evidence import LOCK_PATH, ROOT, EvidenceStore
from services.api.geollm_storage import COVERAGE_SHA256, ESRI_AUDIT_SHA256, TRANSITIONS_SHA256
from services.api.lcluc_boundaries import DIRECTORY, SNAPSHOT_SHA256, admin_overlay
from services.api.pinned import LOCK_SHA256
from services.lcluc.banten_esri_audit import REPORT
from services.lcluc.banten_esri_preview import INDEX as ESRI_INDEX
from services.lcluc.banten_historical_trend import OUTPUT, TRANSITIONS, WORKBOOK, WORKBOOK_SHA256
from services.lcluc.banten_sentinel_explorer import ROOT as RASTERS
from services.lcluc.geollm_embedding import MODEL_FILES, MODEL_ID, MODEL_REVISION, embed
from services.lcluc.geollm_lake import RELEASE, GeoLLMLake, canonical_digest
from services.rag.mapbiomas import INDEX


def migrate(lake, source, model_dir):
    if lake.release != RELEASE or lake.institution != "staging-cckp" or lake.objects.bucket != "sdss-storage-staging":
        raise ValueError("GEOLLM_STAGING_DESTINATION_MISMATCH")

    assets = {}

    def seal(dataset, purpose, path, expected=None, expected_size=None):
        path = source.safe_path(path)
        with path.open("rb") as handle:
            digest = file_digest(handle, "sha256").hexdigest()
        size = path.stat().st_size
        if (expected and digest != expected) or (expected_size is not None and size != expected_size):
            raise ValueError(f"GEOLLM_INPUT_PIN_MISMATCH: {purpose}")
        assets[(dataset, purpose)] = (path, digest, size)
        return path

    seal("mapbiomas", "workbook", WORKBOOK, WORKBOOK_SHA256)
    cover = json.loads(seal("mapbiomas", "coverage", OUTPUT, COVERAGE_SHA256).read_bytes())
    transitions = json.loads(seal("mapbiomas", "transitions", TRANSITIONS, TRANSITIONS_SHA256).read_bytes())
    audit = json.loads(seal("esri", "audit", REPORT, ESRI_AUDIT_SHA256).read_bytes())
    display = json.loads(seal("esri", "display-index", ESRI_INDEX).read_bytes())
    if audit["boundary_sha256"] != SNAPSHOT_SHA256:
        raise ValueError("GEOLLM_AUDIT_BOUNDARY_MISMATCH")
    rasters = {}
    for row in audit["annual"]:
        year = row["year"]
        raw_pin = row["source_pin"]
        seal("esri", f"raw-{year}", raw_pin["path"], raw_pin["sha256"], raw_pin["bytes"])
        record = json.loads(seal("esri", f"raster-index-{year}", RASTERS / str(year) / "land-cover.json").read_bytes())
        if record["source"]["sha256"] != raw_pin["sha256"]:
            raise ValueError("GEOLLM_DERIVED_SOURCE_MISMATCH")
        pin = record["raster"]
        seal("esri", f"raster-{year}", pin["path"], pin["sha256"], pin["bytes"])
        rasters[str(year)] = {"sha256": pin["sha256"], "source_sha256": raw_pin["sha256"]}
        pin = display["years"][str(year)]
        if pin["source_sha256"] != raw_pin["sha256"]:
            raise ValueError("GEOLLM_DISPLAY_SOURCE_MISMATCH")
        seal("esri", f"preview-{year}", ESRI_INDEX.parent / f"esri-{year}.png", pin["sha256"], pin["bytes"])

    from PIL import Image

    with Image.open(assets[("esri", "preview-2020")][0]) as image:
        display["shape"] = list(image.size)

    seal("banten-boundary", "source", f"{DIRECTORY}/boundary.geojson", SNAPSHOT_SHA256)
    boundary = admin_overlay(source, "banten")
    feature = next(item for item in boundary["geojson"]["features"] if item["properties"]["level"] == "province")

    catalog = json.loads(seal("landy", "index", INDEX).read_bytes())
    documents = catalog["documents"]
    if len(documents) != 14:
        raise ValueError("GEOLLM_MAPBIOMAS_CORPUS_INCOMPLETE")
    passages = []
    for doc in documents:
        seal("landy", doc["id"].lower(), doc["raw_path"], doc["raw_sha256"], doc["bytes"])
        passages.extend((f"{doc['id']}:{i:04}", chunk["text"]) for i, chunk in enumerate(doc["chunks"]))
    if not passages:
        raise ValueError("GEOLLM_MAPBIOMAS_CHUNKS_MISSING")
    model, vocabulary = (seal("landy", purpose, model_dir / filename, digest, length)
                         for purpose, (filename, length, digest) in MODEL_FILES.items())
    vectors = []
    for i in range(0, len(passages), 8):
        vectors.extend(embed([text for _, text in passages[i:i + 8]], model, vocabulary))
        if i % 48 == 0:
            print(f"Encoded {len(vectors)}/{len(passages)} real passages", flush=True)

    def upload(entry):
        (_, purpose), (path, digest, size) = entry
        lake.objects.put(lake.institution, path, digest, size)
        print(f"S3 verified {purpose} ({size} B)", flush=True)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(upload, assets.items()))

    data = {
        "mapbiomas": {"coverage": cover, "transitions": transitions},
        "esri": {"audit": audit, "display": display, "rasters": rasters},
        "banten-boundary": {"source": boundary["source"], "properties": feature["properties"]},
        "landy": {"documents": documents, "unavailable": catalog["unavailable"], "embedding_model": MODEL_ID,
                  "embedding_revision": MODEL_REVISION,
                  "structured_counts": {key: len(items) for key, items in catalog["structured_knowledge"].items()}},
    }
    with lake.store.transaction(lake.institution) as tx:
        for name, payload in data.items():
            coverage = feature["geometry"] if name == "banten-boundary" else None
            tx.put_node("dataset", lake.key(name), canonical_digest(payload), payload, coverage)
        for (dataset, purpose), (_, digest, size) in assets.items():
            tx.bind_asset("dataset", lake.key(dataset), purpose, digest, size)
        for (key, _), vector in zip(passages, vectors, strict=True):
            tx.put_vector(lake.key("landy"), key, MODEL_ID, vector)
    print(json.dumps({"release": lake.release, "datasets": len(data), "objects": len(assets),
                      "document_count": len(documents), "vector_count": len(vectors), "dimension": 768}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", action="store_true", required=True)
    parser.add_argument("--model-dir", required=True, type=Path)
    args = parser.parse_args()
    if os.getenv("SDSS_GEOLLM_LAKE_RELEASE") != RELEASE:
        parser.error("Expected approved Staging release is missing")
    migrate(GeoLLMLake.from_env(), EvidenceStore(ROOT, LOCK_PATH, LOCK_SHA256), args.model_dir)


if __name__ == "__main__":
    main()
