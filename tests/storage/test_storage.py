import os
from hashlib import sha256
from pathlib import Path
from time import sleep
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen
from uuid import uuid4

import pytest

from services.storage.admin import export_objects, migrate_result, restore_objects
from services.storage.objects import ObjectStore, checked_endpoint, object_key
from services.storage.store import LineageStore, StorageError, vector_text

CCKP_RESULT = "318ad96f89c23875aa8927aa5adcd327132bb2a6e58d0819736803e5f7f65a27"
CCKP_PACKAGE = "f25d3f36c94b85251203a203910890f2c9b4d6ced683891b6142088b03845c21"
ROOT = Path(__file__).resolve().parents[2]


def test_identity_key_and_endpoint_reject_ambiguity():
    assert object_key("cckp", "a" * 64) == f"cckp/sha256/aa/{'a' * 64}"
    for institution in ("../cckp", "", "BIG", "cckp/a"):
        with pytest.raises(StorageError, match="STORAGE_IDENTIFIER_INVALID"):
            object_key(institution, "a" * 64)
    for endpoint in (
        "http://org.example",
        "https://name@org.example",
        "https://org.example/p?data=1",
    ):
        with pytest.raises(StorageError, match="STORAGE_ENDPOINT_INVALID"):
            checked_endpoint(endpoint)
    assert checked_endpoint("http://127.0.0.1:59082") == "http://127.0.0.1:59082"


def test_embedding_validation():
    assert vector_text([1] + [0] * 767).startswith("[1,0,")
    for vector in ([1, 0], [float("nan")] * 768, [0] * 768, [True] * 768):
        with pytest.raises(StorageError, match="STORAGE_VECTOR_INVALID"):
            vector_text(vector)


@pytest.mark.skipif(
    os.getenv("SDSS_STORAGE_TEST") != "1", reason="Separate disposable services required"
)
def test_postgis_vector_catalog_acl_and_object_restore(tmp_path):
    import psycopg
    from botocore.exceptions import ClientError
    from psycopg.conninfo import conninfo_to_dict

    local = {"127.0.0.1", "::1", "localhost"}
    assert urlsplit(os.environ["SDSS_STORAGE_S3_ENDPOINT"]).hostname in local
    assert conninfo_to_dict(os.environ["SDSS_STORAGE_DSN"]).get("host") in local
    store = LineageStore(os.environ["SDSS_STORAGE_DSN"])
    objects = ObjectStore.from_env()
    organisation = "dev-" + uuid4().hex[:12]
    other = "other-" + organisation
    source = ROOT / "data/curated/results/registry.sqlite3"
    selected_assets = ["report:cdd-verification", "report:cdd-grid-table"]
    result = migrate_result(
        store,
        objects,
        organisation,
        database=source,
        root=ROOT,
        result_id=CCKP_RESULT,
        assets=selected_assets,
    )
    assert result == migrate_result(
        store,
        objects,
        organisation,
        database=source,
        root=ROOT,
        result_id=CCKP_RESULT,
        assets=selected_assets,
    )
    assert result["objects_verified"] == 2
    assert result["package_sha256"] == CCKP_PACKAGE

    digest = sha256(b"synthetic lineage exercise").hexdigest()
    query = [1.0] + [0.0] * 767
    with store.transaction(organisation) as tx:
        row = tx.get_node("result", CCKP_RESULT)
        assert row["sha256"] == CCKP_PACKAGE
        assert row["document"]["package"]["sources"][0]["id"] == "world-bank-cckp"
        tx.put_node(
            "dataset",
            "synthetic-data",
            digest,
            {"scope": "fixture"},
            coverage={"type": "Point", "coordinates": [108, -6]},
        )
        tx.put_node("model", "model/0.1", digest, {"scope": "fixture"})
        tx.put_node("job", "job-1", digest, {"scope": "fixture"})
        tx.link("dataset", "synthetic-data", "model", "model/0.1")
        tx.link("model", "model/0.1", "job", "job-1")
        tx.put_node("result", "synthetic-result", digest, {"scope": "fixture"})
        tx.link("job", "job-1", "result", "synthetic-result")
        assert [entry["kind"] for entry in tx.ancestry("result", "synthetic-result")] == [
            "dataset",
            "job",
            "model",
        ]
        assert tx.get_node("dataset", "synthetic-data")["coverage"]["coordinates"] == [108, -6]
        with pytest.raises(StorageError, match="STORAGE_IMMUTABLE_NODE_CONFLICT"):
            tx.put_node("model", "model/0.1", digest, {"scope": "mutated"})
        tx.put_vector("synthetic-data", "chunk-1", "fixture/embed0", query)
        assert tx.search_vectors("fixture/embed0", query)[0]["cosine_distance"] == 0
        with pytest.raises(StorageError, match="STORAGE_LINK_TTL_INVALID"):
            objects.download_link(
                tx, "result", CCKP_RESULT, "report-cdd-verification", expires_in=901
            )
        link = objects.download_link(
            tx, "result", CCKP_RESULT, "report-cdd-verification", expires_in=60
        )
    with urlopen(link["url"], timeout=5) as response:
        downloaded = response.read()
    assert sha256(downloaded).hexdigest() == link["sha256"]
    assert parse_qs(urlsplit(link["url"]).query)["X-Amz-Expires"] == ["60"]
    with pytest.raises(HTTPError) as denied:
        urlopen(link["url"].split("?", maxsplit=1)[0], timeout=5)
    assert denied.value.code in {401, 403}

    with store.transaction(other) as tx:
        assert tx.get_node("result", CCKP_RESULT) is None
        assert not tx.search_vectors("fixture/embed0", query)
        assert not tx.inventory()
        with pytest.raises(StorageError, match="STORAGE_ASSET_NOT_FOUND"):
            objects.download_link(tx, "result", CCKP_RESULT, "report-cdd-verification")
        count = tx.connection.execute(
            "SELECT count(*) AS n FROM sdss_storage.lineage_node"
        ).fetchone()
        assert count["n"] == 0
    with psycopg.connect(os.environ["SDSS_STORAGE_DSN"]) as connection:
        assert (
            connection.execute("SELECT count(*) FROM sdss_storage.lineage_node").fetchone()[0] == 0
        )

    with store.transaction(organisation) as tx:
        expires = objects.download_link(
            tx, "result", CCKP_RESULT, "report-cdd-verification", expires_in=1
        )
    sleep(2)
    with pytest.raises(HTTPError) as expired:
        urlopen(expires["url"], timeout=5)
    assert expired.value.code in {400, 403}

    backup_dir = tmp_path / "backup"
    exported = export_objects(store, objects, organisation, backup_dir)
    assert exported["objects_exported"] == 2
    new_bucket = "sdss-storage-development-restore"
    assert objects.bucket != new_bucket
    try:
        objects.client.head_bucket(Bucket=new_bucket)
    except ClientError as error:
        if error.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
            raise
        objects.client.create_bucket(Bucket=new_bucket)
    destination = ObjectStore(objects.client, new_bucket)
    restored = restore_objects(store, destination, organisation, backup_dir)
    assert restored["objects_restored_and_verified"] == 2
    with store.transaction(organisation) as tx:
        restored_link = destination.download_link(
            tx, "result", CCKP_RESULT, "report-cdd-verification"
        )
    with urlopen(restored_link["url"], timeout=5) as response:
        assert response.read() == downloaded
