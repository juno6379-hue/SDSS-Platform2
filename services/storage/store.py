"""PostgreSQL transaction boundary for immutable, institution-owned snapshots."""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from math import isfinite

INSTITUTION = re.compile(r"[a-z][a-z0-9-]{0,62}")
NODE_KEY = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_/:.@-]{0,254}")
DIGEST = re.compile(r"[a-f0-9]{64}")
PURPOSE = re.compile(r"[a-z][a-z0-9_-]{0,127}")
KINDS = {"dataset", "model", "job", "result"}
EDGES = {("dataset", "model"), ("dataset", "job"), ("model", "job"), ("job", "result")}


class StorageError(ValueError):
    """Storage checks use stable codes that do not expose credentials or SQL."""


def checked(pattern, value):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise StorageError("STORAGE_IDENTIFIER_INVALID")
    return value


def node_id(kind, key):
    if kind not in KINDS:
        raise StorageError("STORAGE_NODE_KIND_INVALID")
    return kind, checked(NODE_KEY, key)


def vector_text(components):
    if (
        not isinstance(components, (tuple, list))
        or len(components) != 768
        or any(
            type(value) not in (int, float) or not isfinite(value) or abs(value) > 1e6
            for value in components
        )
        or not any(abs(value) >= 1e-30 for value in components)
    ):
        raise StorageError("STORAGE_VECTOR_INVALID")
    return json.dumps(components, allow_nan=False, separators=(",", ":"))


class LineageStore:
    def __init__(self, dsn):
        if not dsn:
            raise StorageError("STORAGE_DSN_REQUIRED")
        self.dsn = dsn

    @contextmanager
    def transaction(self, institution):
        """Only a service-authenticated organisation may be passed by the caller."""
        import psycopg
        from psycopg.rows import dict_row

        checked(INSTITUTION, institution)
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as connection:
            with connection.transaction():
                privileged = connection.execute(
                    "SELECT rolsuper OR rolbypassrls AS privileged FROM pg_roles WHERE rolname = current_user"
                ).fetchone()
                if not privileged or privileged["privileged"]:
                    raise StorageError("STORAGE_RLS_ROLE_REQUIRED")
                connection.execute(
                    "SELECT set_config('sdss_storage.institution', %s, true)", (institution,)
                )
                yield LineageTransaction(connection, institution)


class LineageTransaction:
    def __init__(self, connection, institution):
        self.connection = connection
        self.institution = institution

    def put_node(self, kind, key, sha256, document, coverage=None):
        kind, key = node_id(kind, key)
        checked(DIGEST, sha256)
        if not isinstance(document, dict):
            raise StorageError("STORAGE_NODE_DOCUMENT_INVALID")
        if coverage is not None and (
            not isinstance(coverage, dict)
            or "crs" in coverage
            or coverage.get("type") in {"Feature", "FeatureCollection"}
        ):
            raise StorageError("STORAGE_CRS84_GEOMETRY_REQUIRED")
        body = json.dumps(document, ensure_ascii=False, allow_nan=False)
        geometry = json.dumps(coverage, allow_nan=False) if coverage is not None else None
        self.connection.execute(
            """
            INSERT INTO sdss_storage.lineage_node (institution, kind, node_key, sha256, document, coverage)
            VALUES (%s, %s, %s, %s, %s::jsonb,
                    public.ST_SetSRID(public.ST_Force2D(public.ST_GeomFromGeoJSON(%s::text)), 4326))
            ON CONFLICT DO NOTHING
            """,
            (self.institution, kind, key, sha256, body, geometry),
        )
        matches = self.connection.execute(
            """
            SELECT sha256 = %s AND document = %s::jsonb AND coverage IS NOT DISTINCT FROM
                   public.ST_SetSRID(public.ST_Force2D(public.ST_GeomFromGeoJSON(%s::text)), 4326) AS same
              FROM sdss_storage.lineage_node
             WHERE institution = %s AND kind = %s AND node_key = %s
            """,
            (sha256, body, geometry, self.institution, kind, key),
        ).fetchone()
        if not matches or not matches["same"]:
            raise StorageError("STORAGE_IMMUTABLE_NODE_CONFLICT")

    def get_node(self, kind, key):
        kind, key = node_id(kind, key)
        return self.connection.execute(
            """
            SELECT kind, node_key, sha256, document,
                   public.ST_AsGeoJSON(coverage)::jsonb AS coverage
              FROM sdss_storage.lineage_node
             WHERE institution = %s AND kind = %s AND node_key = %s
            """,
            (self.institution, kind, key),
        ).fetchone()

    def link(self, source_kind, source_key, target_kind, target_key):
        source = node_id(source_kind, source_key)
        target = node_id(target_kind, target_key)
        if (source_kind, target_kind) not in EDGES:
            raise StorageError("STORAGE_LINEAGE_DIRECTION_INVALID")
        self.connection.execute(
            "INSERT INTO sdss_storage.lineage_edge VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (self.institution, *source, *target),
        )

    def ancestry(self, kind, key):
        kind, key = node_id(kind, key)
        return self.connection.execute(
            """
            WITH RECURSIVE upstream(kind, node_key) AS (
                SELECT source_kind, source_key FROM sdss_storage.lineage_edge
                 WHERE institution = %s AND target_kind = %s AND target_key = %s
                UNION
                SELECT e.source_kind, e.source_key
                  FROM sdss_storage.lineage_edge e JOIN upstream u
                    ON e.target_kind = u.kind AND e.target_key = u.node_key
                 WHERE e.institution = %s
            )
            SELECT n.kind, n.node_key, n.sha256 FROM upstream u
              JOIN sdss_storage.lineage_node n USING (kind, node_key)
             WHERE n.institution = %s ORDER BY n.kind, n.node_key
            """,
            (self.institution, kind, key, self.institution, self.institution),
        ).fetchall()

    def bind_asset(self, kind, key, purpose, digest, byte_count):
        kind, key = node_id(kind, key)
        checked(PURPOSE, purpose)
        checked(DIGEST, digest)
        if type(byte_count) is not int or not 0 <= byte_count < 2**63:
            raise StorageError("STORAGE_ASSET_SIZE_INVALID")
        self.connection.execute(
            "INSERT INTO sdss_storage.asset_object VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (self.institution, digest, byte_count),
        )
        self.connection.execute(
            "INSERT INTO sdss_storage.asset_binding VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (self.institution, kind, key, purpose, digest),
        )
        if self.get_asset(kind, key, purpose) != {"sha256": digest, "byte_count": byte_count}:
            raise StorageError("STORAGE_IMMUTABLE_ASSET_CONFLICT")

    def get_asset(self, kind, key, purpose):
        kind, key = node_id(kind, key)
        checked(PURPOSE, purpose)
        return self.connection.execute(
            """
            SELECT o.sha256, o.byte_count FROM sdss_storage.asset_binding b
              JOIN sdss_storage.asset_object o USING (institution, sha256)
             WHERE b.institution = %s AND b.kind = %s AND b.node_key = %s AND b.purpose = %s
            """,
            (self.institution, kind, key, purpose),
        ).fetchone()

    def inventory(self):
        return self.connection.execute(
            "SELECT sha256, byte_count FROM sdss_storage.asset_object WHERE institution = %s ORDER BY sha256",
            (self.institution,),
        ).fetchall()

    def put_vector(self, dataset_key, chunk_key, model, components):
        _, dataset_key = node_id("dataset", dataset_key)
        checked(NODE_KEY, chunk_key)
        checked(NODE_KEY, model)
        embedding = vector_text(components)
        self.connection.execute(
            """
            INSERT INTO sdss_storage.document_vector (institution, node_key, chunk_key, embedding_model, embedding)
            VALUES (%s, %s, %s, %s, %s::public.vector) ON CONFLICT DO NOTHING
            """,
            (self.institution, dataset_key, chunk_key, model, embedding),
        )
        stored = self.connection.execute(
            """
            SELECT embedding = %s::public.vector AS same FROM sdss_storage.document_vector
             WHERE institution = %s AND node_key = %s AND chunk_key = %s AND embedding_model = %s
            """,
            (embedding, self.institution, dataset_key, chunk_key, model),
        ).fetchone()
        if not stored or not stored["same"]:
            raise StorageError("STORAGE_IMMUTABLE_VECTOR_CONFLICT")

    def search_vectors(self, model, components, *, limit=10, dataset_key=None):
        checked(NODE_KEY, model)
        if dataset_key is not None:
            checked(NODE_KEY, dataset_key)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise StorageError("STORAGE_VECTOR_LIMIT_INVALID")
        return self.connection.execute(
            """
            SELECT node_key, chunk_key, embedding OPERATOR(public.<=>) %s::public.vector AS cosine_distance
              FROM sdss_storage.document_vector
             WHERE institution = %s AND embedding_model = %s
               AND (%s::text IS NULL OR node_key = %s)
             ORDER BY cosine_distance, node_key, chunk_key LIMIT %s
            """,
            (vector_text(components), self.institution, model, dataset_key, dataset_key, limit),
        ).fetchall()
