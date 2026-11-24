"""A deterministic local persistent vector store for integration validation.

Production deployments use the accompanying PostgreSQL/pgvector schema. This
SQLite implementation provides persistent local evidence and UI/E2E behavior
without claiming production-scale semantic retrieval quality.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ChunkRecord(StrictModel):
    chunk_id: str = Field(min_length=1, max_length=256)
    document_id: str = Field(min_length=1, max_length=256)
    source_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source_uri: str = Field(pattern=r"^https://")
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    authority: str = Field(min_length=1)
    license: str = Field(min_length=1)
    access: Literal["public", "restricted", "private"]
    allowed_roles: tuple[str, ...] = ()
    valid_from: date
    valid_until: date | None = None
    language: Literal["ko", "id", "en"]
    text: str = Field(min_length=1)
    source_start: int = Field(ge=0)
    source_end: int = Field(gt=0)
    geography_ids: tuple[str, ...] = ()
    start_year: int | None = Field(default=None, ge=1800, le=2200)
    end_year: int | None = Field(default=None, ge=1800, le=2200)
    variable: str | None = None
    scenario: str | None = None
    model: str | None = None
    embedding: tuple[float, ...] = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    claim_authority: Literal["official_source", "methodology", "weak_reference"]

    @model_validator(mode="after")
    def validate_contract(self) -> "ChunkRecord":
        if self.source_end <= self.source_start:
            raise ValueError("source span must be ordered")
        if self.access != "public" and not self.allowed_roles:
            raise ValueError("non-public chunks require allowed_roles")
        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError("validity interval is reversed")
        if (self.start_year is None) != (self.end_year is None):
            raise ValueError("start_year and end_year must be supplied together")
        if self.start_year and self.end_year and self.end_year < self.start_year:
            raise ValueError("time coverage is reversed")
        if any(not math.isfinite(value) for value in self.embedding):
            raise ValueError("embedding values must be finite")
        return self


class SearchHit(StrictModel):
    chunk_id: str
    document_id: str
    text: str
    score: float
    vector_score: float
    lexical_score: float
    source_uri: str
    version: str
    document_sha256: str
    source_span: tuple[int, int]
    authority: str
    license: str


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimension mismatch")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


class SqliteVectorStore:
    def __init__(self, path: Path, *, embedding_dimension: int):
        if embedding_dimension < 1:
            raise ValueError("embedding_dimension must be positive")
        self.path = Path(path).resolve()
        self.embedding_dimension = embedding_dimension

    def _connect(self, *, readonly: bool = False) -> sqlite3.Connection:
        if readonly:
            if not self.path.exists():
                raise FileNotFoundError(self.path)
            connection = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if not readonly:
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    document_sha256 TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    license TEXT NOT NULL,
                    access TEXT NOT NULL,
                    allowed_roles_json TEXT NOT NULL,
                    valid_from TEXT NOT NULL,
                    valid_until TEXT,
                    language TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source_start INTEGER NOT NULL,
                    source_end INTEGER NOT NULL,
                    geography_ids_json TEXT NOT NULL,
                    start_year INTEGER,
                    end_year INTEGER,
                    variable TEXT,
                    scenario TEXT,
                    model TEXT,
                    embedding_json TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    claim_authority TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
                    chunk_id UNINDEXED, text, tokenize='unicode61'
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_filter
                    ON chunks(variable, scenario, model, start_year, end_year, access);
                """
            )

    def upsert(self, record: ChunkRecord) -> str:
        if len(record.embedding) != self.embedding_dimension:
            raise ValueError("embedding dimension mismatch")
        payload = record.model_dump(mode="json")
        record_sha = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
        values = (
            record.chunk_id,
            record.document_id,
            record.source_id,
            record.dataset_id,
            record.version,
            record.source_uri,
            record.document_sha256,
            record.authority,
            record.license,
            record.access,
            _canonical(record.allowed_roles),
            record.valid_from.isoformat(),
            record.valid_until.isoformat() if record.valid_until else None,
            record.language,
            record.text,
            record.source_start,
            record.source_end,
            _canonical(record.geography_ids),
            record.start_year,
            record.end_year,
            record.variable,
            record.scenario,
            record.model,
            _canonical(record.embedding),
            record.embedding_model,
            record.claim_authority,
            record_sha,
        )
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT record_sha256 FROM chunks WHERE chunk_id = ?", (record.chunk_id,)
            ).fetchone()
            if existing and existing["record_sha256"] != record_sha:
                raise ValueError("IMMUTABLE_CHUNK_ID_DRIFT")
            if existing:
                return record_sha
            connection.execute(
                """
                INSERT INTO chunks VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                """,
                values,
            )
            connection.execute(
                "INSERT INTO chunk_fts(chunk_id, text) VALUES (?, ?)",
                (record.chunk_id, record.text),
            )
        return record_sha

    def count(self) -> int:
        with self._connect(readonly=True) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    def search(
        self,
        *,
        query_text: str,
        query_embedding: tuple[float, ...],
        as_of: date,
        roles: frozenset[str] = frozenset(),
        geography_id: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        variable: str | None = None,
        scenario: str | None = None,
        model: str | None = None,
        limit: int = 10,
    ) -> tuple[SearchHit, ...]:
        if not query_text.strip():
            raise ValueError("query_text is required")
        if len(query_embedding) != self.embedding_dimension:
            raise ValueError("embedding dimension mismatch")
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        terms = {term.casefold() for term in query_text.split() if term.strip()}
        with self._connect(readonly=True) as connection:
            rows = connection.execute("SELECT * FROM chunks ORDER BY chunk_id").fetchall()
        candidates: list[SearchHit] = []
        for row in rows:
            if date.fromisoformat(row["valid_from"]) > as_of:
                continue
            if row["valid_until"] and date.fromisoformat(row["valid_until"]) < as_of:
                continue
            allowed_roles = set(json.loads(row["allowed_roles_json"]))
            if row["access"] != "public" and not allowed_roles.intersection(roles):
                continue
            geography_ids = set(json.loads(row["geography_ids_json"]))
            if geography_id and geography_id not in geography_ids:
                continue
            if variable and row["variable"] != variable:
                continue
            if scenario and row["scenario"] != scenario:
                continue
            if model and row["model"] != model:
                continue
            if (
                start_year is not None
                and row["end_year"] is not None
                and row["end_year"] < start_year
            ):
                continue
            if (
                end_year is not None
                and row["start_year"] is not None
                and row["start_year"] > end_year
            ):
                continue
            vector = tuple(float(item) for item in json.loads(row["embedding_json"]))
            vector_score = max(0.0, _cosine(query_embedding, vector))
            text_terms = {term.casefold().strip(".,:;()[]") for term in row["text"].split()}
            lexical_score = len(terms.intersection(text_terms)) / max(1, len(terms))
            score = 0.65 * vector_score + 0.35 * lexical_score
            candidates.append(
                SearchHit(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    text=row["text"],
                    score=score,
                    vector_score=vector_score,
                    lexical_score=lexical_score,
                    source_uri=row["source_uri"],
                    version=row["version"],
                    document_sha256=row["document_sha256"],
                    source_span=(row["source_start"], row["source_end"]),
                    authority=row["authority"],
                    license=row["license"],
                )
            )
        candidates.sort(key=lambda item: (-item.score, item.chunk_id))
        return tuple(candidates[:limit])
