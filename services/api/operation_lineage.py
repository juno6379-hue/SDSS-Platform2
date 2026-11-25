"""Authorized lineage and expiring file links for configured project storage."""

import os
from functools import cache
from hmac import compare_digest
from typing import Annotated, Literal

from fastapi import HTTPException, Path, Request

from services.storage.objects import ObjectStore
from services.storage.store import LineageStore, StorageError

from .results import check_local

EntityKind = Literal["dataset", "model", "job", "result"]
EntityKey = Annotated[
    str, Path(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")
]


@cache
def _connection_errors():
    failures = [StorageError, OSError, ImportError]
    try:
        from psycopg import Error as PsycopgError
    except ImportError:
        pass
    else:
        failures.append(PsycopgError)
    try:
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        pass
    else:
        failures.extend((BotoCoreError, ClientError))
    return tuple(failures)


def _principal(request):
    check_local(request)
    expected = os.getenv("SDSS_STORAGE_READ_TOKEN", "")
    institution = os.getenv("SDSS_STORAGE_INSTITUTION", "").strip()
    dsn = os.getenv("SDSS_STORAGE_DSN", "").strip()
    if not expected or not institution or not dsn:
        raise HTTPException(503, detail="STORAGE_AUTHORITY_NOT_CONFIGURED")
    prefix, _, value = request.headers.get("authorization", "").partition(" ")
    if prefix.lower() != "bearer" or not compare_digest(value.encode(), expected.encode()):
        raise HTTPException(403, detail="STORAGE_AUTHORITY_REQUIRED")
    return LineageStore(dsn), institution


def mount_operation_lineage(app):
    @app.get("/api/storage/status")
    def storage_status(request: Request):
        check_local(request)
        configured = all(
            os.getenv(name)
            for name in (
                "SDSS_STORAGE_DSN",
                "SDSS_STORAGE_BUCKET",
                "SDSS_STORAGE_READ_TOKEN",
                "SDSS_STORAGE_INSTITUTION",
            )
        )
        return {
            "status": "CONFIGURED_PROBE_REQUIRED" if configured else "BLOCKED",
            "blockers": [] if configured else ["PROJECT_STORAGE_AUTHORITY_NOT_CONFIGURED"],
        }

    @app.get("/api/storage/health")
    def storage_health(request: Request):
        store, institution = _principal(request)
        try:
            with store.transaction(institution) as transaction:
                inventory = transaction.inventory()
            objects = ObjectStore.from_env()
            objects.client.head_bucket(Bucket=objects.bucket)
            return {"status": "VERIFIED_PROJECT_STORAGE", "asset_count": len(inventory)}
        except _connection_errors():
            raise HTTPException(503, detail="PROJECT_STORAGE_PROBE_FAILED") from None

    @app.get("/api/lineage/{kind}/{key}")
    def lineage(request: Request, kind: EntityKind, key: EntityKey):
        store, institution = _principal(request)
        try:
            with store.transaction(institution) as transaction:
                node = transaction.get_node(kind, key)
                if node is None:
                    raise HTTPException(404, detail="LINEAGE_NOT_FOUND")
                return {
                    "node": {name: node[name] for name in ("kind", "node_key", "sha256")},
                    "ancestors": transaction.ancestry(kind, key),
                }
        except _connection_errors():
            raise HTTPException(503, detail="PROJECT_LINEAGE_UNAVAILABLE") from None

    @app.get("/api/lineage/{kind}/{key}/assets/{purpose}")
    def asset_link(request: Request, kind: EntityKind, key: EntityKey, purpose: EntityKey):
        store, institution = _principal(request)
        try:
            with store.transaction(institution) as transaction:
                if transaction.get_asset(kind, key, purpose) is None:
                    raise HTTPException(404, detail="LINEAGE_ASSET_NOT_FOUND")
                return ObjectStore.from_env().download_link(
                    transaction, kind, key, purpose, expires_in=300
                )
        except _connection_errors():
            raise HTTPException(503, detail="PROJECT_FILE_LINK_UNAVAILABLE") from None
