"""Persistent report vector stores and pgvector schema contracts."""

from .sqlite_store import ChunkRecord, SearchHit, SqliteVectorStore

__all__ = ["ChunkRecord", "SearchHit", "SqliteVectorStore"]
