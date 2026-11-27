"""Storage adapters for the GeoLLM GIS, map, and knowledge routes."""

import json
import os
from contextlib import contextmanager
from threading import Event, Lock, Thread

from services.lcluc.banten_historical_trend import OUTPUT, TRANSITIONS, WORKBOOK, WORKBOOK_SHA256
from services.lcluc.geollm_lake import BASE as LAKE_MAP
from services.lcluc.geollm_lake import GeoLLMLake
from services.rag.mapbiomas import catalog, search

from .evidence import EvidenceBlocked
from .lcluc_sentinel_explorer import PREFIX, PROVINCE, _digest
from .operation_lineage import _connection_errors

COVERAGE_SHA256 = "55314ca9ec7b8340811355a8016d89506634e8752d302a7071ccf6c9f7c84e82"
TRANSITIONS_SHA256 = "0f02a4e05d9628ef57770a3e631888898be6084dcbf8bb2f97c93098b1e9402c"
ESRI_AUDIT_SHA256 = "495c94ec9859e9c6b26f75a7592cc41004a2163fc35a87050ab59e358c2c621c"


class Unavailable(ValueError):
    """A valid query whose evidence or spatial scope is unavailable."""


class StorageBlocked(Unavailable):
    """A configured storage backend could not supply the requested evidence."""


class LocalGeoLLMStorage:
    boundary_url = "/api/lcluc/boundaries/banten"
    cover_url = "/api/lcluc/banten-province-display"
    transition_url = f"{PREFIX}/transition"

    def __init__(self, store):
        self.store = store

    @property
    def provenance(self):
        return {}

    def checked(self, path, expected):
        file = self.store.safe_path(path)
        stamp = file.stat()
        if _digest(file, stamp.st_size, stamp.st_mtime_ns, stamp.st_ctime_ns) != expected:
            raise Unavailable("SOURCE_INTEGRITY_FAILURE")
        return file

    def mapbiomas(self, needs_transition):
        self.checked(WORKBOOK, WORKBOOK_SHA256)
        cover = json.loads(self.checked(OUTPUT, COVERAGE_SHA256).read_bytes())
        table = json.loads(self.checked(TRANSITIONS, TRANSITIONS_SHA256).read_bytes()) if needs_transition else None
        return cover, table

    def esri_audit(self):
        return json.loads(self.checked(f"{PROVINCE}/esri-coverage-and-change.json", ESRI_AUDIT_SHA256).read_bytes())

    def attest_esri(self, year, pin):
        self.checked(pin["path"], pin["sha256"])

    def catalog(self):
        return catalog(self.store)

    def search(self, question):
        return search(self.store, question)


class DataLakeGeoLLMStorage:
    boundary_url = f"{LAKE_MAP}/boundary"
    cover_url = f"{LAKE_MAP}/cover"
    transition_url = f"{LAKE_MAP}/transition"

    def __init__(self, lake=None, *, config_issue=None):
        self._lake = lake
        self._lock = Lock()
        self._document_lock = Lock()
        self._document_preparation_failed = False
        self.warming_documents = Event()
        self.config_issue = config_issue

    @contextmanager
    def connected(self):
        if self.config_issue:
            raise StorageBlocked(self.config_issue)
        try:
            with self._lock:
                if self._lake is None:
                    self._lake = GeoLLMLake.from_env()
                lake = self._lake
            yield lake
        except (*_connection_errors(), EvidenceBlocked, KeyError, ValueError, RuntimeError):
            raise StorageBlocked("GEOLLM_STORAGE_UNAVAILABLE") from None

    @property
    def provenance(self):
        return {"data_backend": "staging_postgis_seaweedfs", "data_release": self._lake.release}

    def mapbiomas(self, needs_transition):
        with self.connected() as lake:
            lake.attested("mapbiomas", "workbook", WORKBOOK_SHA256)
            lake.attested("mapbiomas", "coverage", COVERAGE_SHA256)
            data = lake.document("mapbiomas")["document"]
            if needs_transition:
                lake.attested("mapbiomas", "transitions", TRANSITIONS_SHA256)
            return data["coverage"], data["transitions"] if needs_transition else None

    def esri_audit(self):
        with self.connected() as lake:
            lake.attested("esri", "audit", ESRI_AUDIT_SHA256)
            return lake.document("esri")["document"]["audit"]

    def attest_esri(self, year, pin):
        with self.connected() as lake:
            lake.attested("esri", f"raw-{year}", pin["sha256"])

    def catalog(self):
        with self.connected() as lake:
            return lake.catalog()

    def search(self, question):
        with self._document_lock:
            if self.warming_documents.is_set():
                raise StorageBlocked("GEOLLM_STORAGE_INITIALIZING")
            if self._document_preparation_failed:
                self.warming_documents.set()
                Thread(target=self.warm_documents, name="geollm-prepare-documents", daemon=True).start()
                raise StorageBlocked("GEOLLM_STORAGE_UNAVAILABLE")
        with self.connected() as lake:
            return lake.search(question)

    def warm_documents(self):
        prepared = False
        try:
            with self.connected() as lake:
                lake.warm_model()
            prepared = True
        except StorageBlocked:
            pass
        finally:
            with self._document_lock:
                self._document_preparation_failed = not prepared
                self.warming_documents.clear()

    def boundary(self):
        with self.connected() as lake:
            return lake.boundary()

    def cover(self, year):
        with self.connected() as lake:
            return lake.cover(year)

    def transition(self, start, end, origin, destination):
        with self.connected() as lake:
            return lake.transition(start, end, origin, destination)


def select_geollm_storage(store, lake=None):
    if lake is not None:
        return DataLakeGeoLLMStorage(lake)
    mode = os.getenv("SDSS_GEOLLM_STORAGE_MODE")
    release = os.getenv("SDSS_GEOLLM_LAKE_RELEASE")
    if mode is None:
        mode = "lake" if release is not None else "local"
    if mode == "local":
        return LocalGeoLLMStorage(store)
    if mode != "lake":
        return DataLakeGeoLLMStorage(config_issue="GEOLLM_STORAGE_MODE_INVALID")
    required = ("SDSS_GEOLLM_LAKE_RELEASE", "SDSS_STORAGE_DSN", "SDSS_STORAGE_INSTITUTION", "SDSS_STORAGE_BUCKET")
    issue = None if all(os.getenv(name, "").strip() for name in required) else "GEOLLM_STORAGE_CONFIG_REQUIRED"
    return DataLakeGeoLLMStorage(config_issue=issue)
