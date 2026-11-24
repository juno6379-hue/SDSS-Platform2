import hashlib
import json

from services.vectorstore.build_stage_index import build_index
from services.vectorstore.sqlite_store import SqliteVectorStore


def test_builds_private_review_index_from_staged_span(tmp_path) -> None:
    text = "Indonesia climate report methodology"
    document_sha = hashlib.sha256(text.encode()).hexdigest()
    stage = {
        "document": {
            "id": "doc-1",
            "source_id": "worldbank-cckp-README.md",
            "source_uri": "https://example.org/report",
            "version": "commit-1",
            "sha256": document_sha,
            "authority": "World Bank",
            "text": text,
        },
        "receipt": {
            "acquired_at": "2026-11-24T00:00:00+00:00",
            "license": "NOT_VERIFIED",
            "retrieval_permitted": False,
        },
        "extraction": {"raw_sha256": document_sha},
        "spans": [{"start": 0, "end": len(text), "quote": text}],
    }
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "doc.stage.json").write_text(json.dumps(stage), encoding="utf-8")
    database = tmp_path / "vectors.sqlite3"
    manifest = tmp_path / "manifest.json"
    result = build_index(staged, database, manifest)
    assert result["chunk_count"] == 1
    assert result["public_search_enabled"] is False
    store = SqliteVectorStore(database, embedding_dimension=64)
    assert store.count() == 1
