"""Read the immutable Banten release through PostgreSQL/PostGIS, pgvector and S3."""

import json
import os
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

from services.lcluc.geollm_embedding import MODEL_FILES, MODEL_ID, embed, encoder
from services.storage.objects import ObjectStore, object_key
from services.storage.store import LineageStore, StorageError

RELEASE = "banten-geollm-20261127-v1"
BASE = "/api/lcluc/geollm/map"
PRODUCT_YEARS = range(2020, 2026)


def canonical_digest(document):
    return sha256(json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def dataset_key(release, name):
    return f"{release}:{name}"


class GeoLLMLake:
    def __init__(self, release, dsn, institution, objects):
        self.release = release
        self.store = LineageStore(dsn)
        self.institution = institution
        self.objects = objects
        self._cache = TemporaryDirectory(prefix="sdss-geollm-")
        self._lock = Lock()

    @classmethod
    def from_env(cls):
        return cls(os.environ["SDSS_GEOLLM_LAKE_RELEASE"], os.environ["SDSS_STORAGE_DSN"],
                   os.environ["SDSS_STORAGE_INSTITUTION"], ObjectStore.from_env())

    def key(self, name):
        return dataset_key(self.release, name)

    def document(self, name):
        with self.store.transaction(self.institution) as tx:
            node = tx.get_node("dataset", self.key(name))
        if node is None:
            raise StorageError("GEOLLM_RELEASE_DATASET_MISSING")
        if canonical_digest(node["document"]) != node["sha256"]:
            raise StorageError("GEOLLM_RELEASE_DATASET_DIGEST_MISMATCH")
        return node

    def binding(self, name, purpose, expected=None):
        with self.store.transaction(self.institution) as tx:
            asset = tx.get_asset("dataset", self.key(name), purpose)
        if asset is None or (expected and asset["sha256"] != expected):
            raise StorageError("GEOLLM_RELEASE_ASSET_MISSING_OR_MISMATCH")
        return asset

    def attested(self, name, purpose, expected):
        self._attest_object(self.binding(name, purpose, expected))

    def _attest_object(self, asset):
        response = self.objects.client.head_object(
            Bucket=self.objects.bucket, Key=object_key(self.institution, asset["sha256"]),
        )
        if (response["ContentLength"] != asset["byte_count"]
                or response.get("Metadata", {}).get("sha256") != asset["sha256"]):
            raise StorageError("GEOLLM_RELEASE_OBJECT_MISMATCH")

    def file(self, name, purpose, expected=None, *, require_live=False):
        asset = self.binding(name, purpose, expected)
        with self._lock:
            target = Path(self._cache.name) / asset["sha256"]
            if not target.is_file():
                self.objects.export_asset(self.institution, asset["sha256"], asset["byte_count"], self._cache.name)
            elif require_live:
                self._attest_object(asset)
        return target

    def boundary(self):
        node = self.document("banten-boundary")
        data = node["document"]
        self.attested("banten-boundary", "source", data["source"]["snapshot_sha256"])
        if node["coverage"] is None:
            raise StorageError("GEOLLM_RELEASE_BOUNDARY_MISSING")
        feature = {"type": "Feature", "geometry": node["coverage"], "properties": data["properties"]}
        return {"region": "banten", "source": data["source"],
                "geojson": {"type": "FeatureCollection", "features": [feature]}}

    def cover(self, year):
        source = self.document("esri")["document"]
        return self.file("esri", f"preview-{year}", source["display"]["years"][str(year)]["sha256"],
                         require_live=True).read_bytes()

    def transition(self, start, end, origin, destination):
        from rasterio.transform import from_bounds

        from services.lcluc.banten_esri_preview import WEB
        from services.lcluc.banten_sentinel_statistics import render_transition

        source = self.document("esri")["document"]
        left, right = (self.file("esri", f"raster-{year}", source["rasters"][str(year)]["sha256"], require_live=True)
                       for year in (start, end))
        display = source["display"]
        west, south, east, north = display["bounds"]
        width, height = display["shape"]
        grid = {"crs": "EPSG:3857", "width": width, "height": height,
                "transform": from_bounds(*WEB.transform(west, south), *WEB.transform(east, north), width, height)}
        return render_transition(grid, left, right, origin, destination, None)

    def corpus(self):
        return self.document("landy")["document"]

    def model_paths(self):
        return tuple(self.file("landy", purpose, MODEL_FILES[purpose][2], require_live=True)
                     for purpose in ("encoder", "tokenizer"))

    def warm_model(self):
        if self.corpus()["embedding_model"] != MODEL_ID:
            raise StorageError("GEOLLM_RELEASE_EMBEDDING_MODEL_MISMATCH")
        encoder(*self.model_paths())

    def search(self, question):
        corpus = self.corpus()
        if corpus["embedding_model"] != MODEL_ID:
            raise StorageError("GEOLLM_RELEASE_EMBEDDING_MODEL_MISMATCH")
        vector = embed([question], *self.model_paths(), query=True)[0]
        with self.store.transaction(self.institution) as tx:
            hits = tx.search_vectors(MODEL_ID, vector, dataset_key=self.key("landy"), limit=30)
        docs = {doc["id"]: doc for doc in corpus["documents"]}
        citations, used = [], set()
        for item in hits:
            source_id, index = item["chunk_key"].split(":", 1)
            doc = docs[source_id]
            chunk = doc["chunks"][int(index)]
            page = chunk["page"]
            if (source_id, page) in used:
                continue
            if source_id not in {first for first, _ in used}:
                self.attested("landy", source_id.lower(), doc["raw_sha256"])
            used.add((source_id, page))
            citations.append({
                "id": source_id, "title": doc["title"], "version": doc["version"], "language": doc["language"],
                "page": page, "text_offset": chunk["offset"], "excerpt": chunk["text"][:180],
                "url": doc["url"] + (f"#page={page}" if page else ""), "source_sha256": doc["raw_sha256"],
            })
            if len(citations) == 5:
                break
        return {"status": "FOUND" if citations else "NO_MATCH", "mode": "staging_pgvector_e5", "answer": None,
                "embedding_model": MODEL_ID, "documents": len(docs),
                "p0_documents": sum(doc["priority"] == "P0" for doc in docs.values()),
                "unavailable": corpus["unavailable"], "citations": citations}

    def catalog(self):
        corpus = self.corpus()
        visible = ("id", "title", "language", "version", "url", "retrieved_at", "raw_sha256", "priority")
        return {"status": "INDEXED", "documents": [{key: doc[key] for key in visible} for doc in corpus["documents"]],
                "structured_counts": corpus["structured_counts"], "unavailable": corpus["unavailable"]}
