"""Migrate selected SQLite catalog assets and back up an institution's object inventory."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from contextlib import closing
from hashlib import sha256
from pathlib import Path

from .objects import ObjectStore
from .store import DIGEST, INSTITUTION, LineageStore, StorageError, checked

PORTABLE_LICENSES = {"CC-BY-4.0", "CC-BY-SA-4.0", "CC0-1.0"}
BACKUP_FORMAT = "sdss-storage-object-backup/1"


def read_result(database, result_id):
    checked(DIGEST, result_id)
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only = ON")
        row = conn.execute(
            """
            SELECT r.payload, r.created_at, p.sha256, p.payload
              FROM result_packages p JOIN results r ON r.id = p.result_id WHERE r.id = ?
            """,
            (result_id,),
        ).fetchone()
    if row is None:
        raise StorageError("STORAGE_CATALOG_RESULT_ABSENT")
    record, created_at, digest, payload = row
    if sha256(payload.encode()).hexdigest() != digest:
        raise StorageError("STORAGE_CATALOG_PACKAGE_DRIFT")
    value = json.loads(payload)
    if value.get("schema_version") != "sdss-result-package/1":
        raise StorageError("STORAGE_CATALOG_PACKAGE_SCHEMA_INVALID")
    return digest, {"result": json.loads(record), "created_at": created_at, "package": value}


def verified_local_path(root, pin):
    from services.results.catalog import Pin

    entry = Pin.model_validate(pin)
    target = (root / entry.path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise StorageError("STORAGE_CATALOG_PIN_MISSING")
    return target


def migrate_result(store, objects, institution, *, database, root, result_id, assets):
    root = Path(root).resolve()
    digest, document = read_result(database, result_id)
    package = document["package"]
    sources = {entry["id"]: entry for entry in package["sources"]}
    available = {f"source:{key}": (entry, entry["raw"]) for key, entry in sources.items()} | {
        f"{kind}:{entry['id']}": (sources[entry["source_id"]], entry["file"])
        for kind, field in (("report", "reports"), ("layer", "layers"))
        for entry in package[field]
    }
    if not assets or len(set(assets)) != len(assets) or set(assets) - available.keys():
        raise StorageError("STORAGE_MIGRATION_REQUIRES_DISTINCT_EXPLICIT_ASSETS")
    verified = []
    for name in assets:
        source, pin = available[name]
        evidence = source.get("license_evidence")
        if source["license"] not in PORTABLE_LICENSES or not evidence:
            raise StorageError("STORAGE_SOURCE_REUSE_UNVERIFIED")
        rights_path = verified_local_path(root, evidence)
        raw_rights = rights_path.read_bytes()
        if (
            len(raw_rights) != evidence["bytes"]
            or sha256(raw_rights).hexdigest() != evidence["sha256"]
            or json.loads(raw_rights).get("license") != source["license"]
        ):
            raise StorageError("STORAGE_SOURCE_LICENSE_EVIDENCE_DRIFT")
        verified.append((name, pin, verified_local_path(root, pin)))

    for _, pin, path in verified:
        objects.put(institution, path, pin["sha256"], pin["bytes"])
    with store.transaction(institution) as tx:
        tx.put_node("result", result_id, digest, document)
        for name, pin, _ in verified:
            tx.bind_asset(
                "result", result_id, name.replace(":", "-", 1), pin["sha256"], pin["bytes"]
            )
    return {"result_id": result_id, "package_sha256": digest, "objects_verified": len(verified)}


def export_objects(store, objects, institution, directory):
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=False)
    with store.transaction(institution) as tx:
        inventory = tx.inventory()
    for entry in inventory:
        objects.export_asset(institution, entry["sha256"], entry["byte_count"], target)
    manifest = {"schema_version": BACKUP_FORMAT, "institution": institution, "objects": inventory}
    (target / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return {"institution": institution, "objects_exported": len(inventory)}


def restore_objects(store, objects, institution, directory):
    source = Path(directory).resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    with store.transaction(institution) as tx:
        expected = tx.inventory()
    if manifest != {
        "schema_version": BACKUP_FORMAT,
        "institution": institution,
        "objects": expected,
    }:
        raise StorageError("STORAGE_BACKUP_INVENTORY_MISMATCH")
    for entry in expected:
        digest, size = entry["sha256"], entry["byte_count"]
        path = (source / digest).resolve()
        if not path.is_relative_to(source):
            raise StorageError("STORAGE_BACKUP_PIN_OUTSIDE_ROOT")
        objects.put(institution, path, digest, size)
    return {"institution": institution, "objects_restored_and_verified": len(expected)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--institution", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("health")
    migrate = commands.add_parser("migrate-result")
    migrate.add_argument("--database", type=Path, required=True)
    migrate.add_argument("--root", type=Path, required=True)
    migrate.add_argument("--result-id", required=True)
    migrate.add_argument("--asset", action="append", required=True)
    for name in ("export-objects", "restore-objects"):
        commands.add_parser(name).add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        checked(INSTITUTION, args.institution)
        store = LineageStore(os.getenv("SDSS_STORAGE_DSN"))
        objects = ObjectStore.from_env()
        if args.command == "migrate-result":
            status = migrate_result(
                store,
                objects,
                args.institution,
                database=args.database,
                root=args.root,
                result_id=args.result_id,
                assets=args.asset,
            )
        elif args.command == "export-objects":
            status = export_objects(store, objects, args.institution, args.directory)
        elif args.command == "restore-objects":
            status = restore_objects(store, objects, args.institution, args.directory)
        else:
            with store.transaction(args.institution) as tx:
                versions = tx.connection.execute(
                    "SELECT extname, extversion FROM pg_extension WHERE extname IN ('postgis', 'vector')"
                ).fetchall()
                if len(versions) != 2:
                    raise StorageError("STORAGE_DATABASE_EXTENSIONS_MISSING")
                inventory = tx.inventory()
            objects.client.head_bucket(Bucket=objects.bucket)
            status = {
                "extensions": versions,
                "tenant_assets": len(inventory),
                "object_bucket": "reachable",
            }
        print(json.dumps(status, ensure_ascii=False))
    except StorageError as error:
        parser.exit(1, f"{error}\n")
    except Exception as error:
        parser.exit(1, f"STORAGE_REQUEST_FAILED:{type(error).__name__}\n")


if __name__ == "__main__":
    main()
