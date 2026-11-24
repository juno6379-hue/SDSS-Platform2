"""Build a private review-only VectorDB from verified staged source spans."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from services.rag.retrieval import synthetic_vector
from services.rag.routing import canonical_tokens

from .sqlite_store import ChunkRecord, SqliteVectorStore


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_index(
    staged_directory: Path,
    database_path: Path,
    manifest_path: Path,
) -> dict:
    staged_directory = Path(staged_directory).resolve()
    database_path = Path(database_path).resolve()
    manifest_path = Path(manifest_path).resolve()
    files = sorted(staged_directory.glob("*.stage.json"))
    if not files:
        raise ValueError("NO_STAGED_DOCUMENTS")
    store = SqliteVectorStore(database_path, embedding_dimension=64)
    store.initialize()
    source_pins: list[dict] = []
    chunk_count = 0
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        document = payload["document"]
        receipt = payload["receipt"]
        if payload["extraction"]["raw_sha256"] != document["sha256"]:
            raise ValueError("STAGE_DOCUMENT_SHA_DRIFT")
        acquired = datetime.fromisoformat(receipt["acquired_at"]).date()
        is_klhk = document["source_id"].startswith("klhk-")
        for index, span in enumerate(payload["spans"]):
            quote = span["quote"]
            record = ChunkRecord(
                chunk_id=f"{document['id']}:{index:04d}",
                document_id=document["id"],
                source_id=document["source_id"],
                dataset_id=document["source_id"],
                version=document["version"],
                source_uri=document["source_uri"],
                document_sha256=document["sha256"],
                authority=document["authority"],
                license=receipt["license"],
                access="private",
                allowed_roles=("data_steward",),
                valid_from=acquired,
                language="id" if is_klhk else "en",
                text=quote,
                source_start=span["start"],
                source_end=span["end"],
                geography_ids=("IDN",) if is_klhk else (),
                embedding=synthetic_vector(canonical_tokens(quote), 64),
                embedding_model="synthetic-hash-64-v1",
                claim_authority="weak_reference" if is_klhk else "methodology",
            )
            store.upsert(record)
            chunk_count += 1
        source_pins.append(
            {
                "stage_path": str(path),
                "stage_sha256": sha256(path),
                "document_id": document["id"],
                "document_sha256": document["sha256"],
                "chunk_count": len(payload["spans"]),
                "retrieval_permitted": receipt["retrieval_permitted"],
                "license": receipt["license"],
            }
        )
    if store.count() != chunk_count:
        raise ValueError("VECTOR_DB_COUNT_MISMATCH")
    result = {
        "schema_version": "climate-report-vector-index/1.0",
        "status": "VERIFIED_LOCAL_PRIVATE_REVIEW_INDEX",
        "database_path": str(database_path),
        "database_sha256": sha256(database_path),
        "document_count": len(files),
        "chunk_count": chunk_count,
        "embedding_model": "synthetic-hash-64-v1",
        "embedding_dimension": 64,
        "embedding_quality_verified": False,
        "access": "private",
        "allowed_roles": ["data_steward"],
        "public_search_enabled": False,
        "numeric_answers_enabled": False,
        "created_on": date.today().isoformat(),
        "sources": source_pins,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged-directory", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    arguments = parser.parse_args()
    result = build_index(arguments.staged_directory, arguments.database, arguments.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
