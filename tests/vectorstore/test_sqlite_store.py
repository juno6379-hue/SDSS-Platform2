from datetime import date

import pytest

from services.vectorstore import ChunkRecord, SqliteVectorStore


def chunk(**updates: object) -> ChunkRecord:
    values = {
        "chunk_id": "chunk-1",
        "document_id": "document-1",
        "source_id": "worldbank-cckp",
        "dataset_id": "cckp-documentation",
        "version": "commit-1",
        "source_uri": "https://github.com/worldbank/climateknowledgeportal",
        "document_sha256": "a" * 64,
        "authority": "World Bank",
        "license": "MPL-2.0-documentation-only",
        "access": "public",
        "allowed_roles": (),
        "valid_from": date(2026, 1, 1),
        "valid_until": None,
        "language": "en",
        "text": "Indonesia precipitation methodology and climate report",
        "source_start": 10,
        "source_end": 65,
        "geography_ids": ("IDN",),
        "start_year": 1951,
        "end_year": 1980,
        "variable": "pr",
        "scenario": "historical",
        "model": "era5",
        "embedding": (1.0, 0.0, 0.0),
        "embedding_model": "test-vector-v1",
        "claim_authority": "methodology",
    }
    values.update(updates)
    return ChunkRecord.model_validate(values)


def test_persistent_upsert_is_idempotent_and_drift_is_rejected(tmp_path) -> None:
    store = SqliteVectorStore(tmp_path / "vectors.sqlite3", embedding_dimension=3)
    store.initialize()
    first = store.upsert(chunk())
    assert store.upsert(chunk()) == first
    assert store.count() == 1
    with pytest.raises(ValueError, match="IMMUTABLE_CHUNK_ID_DRIFT"):
        store.upsert(chunk(text="changed source text"))


def test_acl_is_applied_before_scoring(tmp_path) -> None:
    store = SqliteVectorStore(tmp_path / "vectors.sqlite3", embedding_dimension=3)
    store.initialize()
    store.upsert(chunk())
    store.upsert(
        chunk(
            chunk_id="secret",
            access="restricted",
            allowed_roles=("researcher",),
            embedding=(1.0, 0.0, 0.0),
        )
    )
    public = store.search(
        query_text="precipitation methodology",
        query_embedding=(1.0, 0.0, 0.0),
        as_of=date(2026, 11, 24),
    )
    permitted = store.search(
        query_text="precipitation methodology",
        query_embedding=(1.0, 0.0, 0.0),
        as_of=date(2026, 11, 24),
        roles=frozenset({"researcher"}),
    )
    assert [item.chunk_id for item in public] == ["chunk-1"]
    assert {item.chunk_id for item in permitted} == {"chunk-1", "secret"}


def test_metadata_time_and_geography_filters(tmp_path) -> None:
    store = SqliteVectorStore(tmp_path / "vectors.sqlite3", embedding_dimension=3)
    store.initialize()
    store.upsert(chunk())
    assert (
        len(
            store.search(
                query_text="Indonesia climate",
                query_embedding=(1.0, 0.0, 0.0),
                as_of=date(2026, 11, 24),
                geography_id="IDN",
                start_year=1960,
                end_year=1970,
                variable="pr",
                scenario="historical",
                model="era5",
            )
        )
        == 1
    )
    assert (
        store.search(
            query_text="Indonesia climate",
            query_embedding=(1.0, 0.0, 0.0),
            as_of=date(2026, 11, 24),
            geography_id="KOR",
        )
        == ()
    )


def test_expired_and_future_chunks_are_hidden(tmp_path) -> None:
    store = SqliteVectorStore(tmp_path / "vectors.sqlite3", embedding_dimension=3)
    store.initialize()
    store.upsert(chunk(valid_from=date(2030, 1, 1)))
    assert (
        store.search(
            query_text="climate",
            query_embedding=(1.0, 0.0, 0.0),
            as_of=date(2026, 11, 24),
        )
        == ()
    )


def test_dimension_and_non_public_acl_fail_closed(tmp_path) -> None:
    with pytest.raises(ValueError, match="allowed_roles"):
        chunk(access="private", allowed_roles=())
    store = SqliteVectorStore(tmp_path / "vectors.sqlite3", embedding_dimension=3)
    store.initialize()
    with pytest.raises(ValueError, match="dimension"):
        store.upsert(chunk(embedding=(1.0, 0.0)))


def test_read_operations_do_not_mutate_database_bytes(tmp_path) -> None:
    database = tmp_path / "vectors.sqlite3"
    store = SqliteVectorStore(database, embedding_dimension=3)
    store.initialize()
    store.upsert(chunk())
    before = database.read_bytes()
    assert store.count() == 1
    store.search(
        query_text="climate",
        query_embedding=(1.0, 0.0, 0.0),
        as_of=date(2026, 11, 24),
    )
    assert database.read_bytes() == before
