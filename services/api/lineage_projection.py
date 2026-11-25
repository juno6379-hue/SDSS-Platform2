"""Project a verified institutional job receipt into the authorized lineage store."""

import argparse
import os

from services.jobs.contracts import Approval, digest
from services.results.catalog import Pin
from services.results.registry import ResultRegistry
from services.storage.admin import read_result
from services.storage.store import LineageStore, StorageError

from .catalog_api import validate_entry
from .evidence import LOCK_PATH, ROOT, EvidenceStore
from .pinned import LOCK_SHA256
from .result_catalog import verified_json
from .results import DATABASE, verify_evidence


def _project(output, institution, job, result_id, package_sha, result_document, receipt, dataset):
    job_id = job["job_id"]
    model = job["model"]
    model_key = f"{model['name']}:{model['version']}:{model['artifact_sha256']}"
    dataset_key = dataset["sha256"]
    with output.transaction(institution) as transaction:
        transaction.put_node("dataset", dataset_key, dataset["sha256"], {"bytes": dataset["bytes"]})
        transaction.put_node(
            "model",
            model_key,
            model["artifact_sha256"],
            {"name": model["name"], "version": model["version"]},
        )
        transaction.put_node(
            "job",
            job_id,
            receipt["sha256"],
            {
                "provider": job["provider"],
                "operation": job["operation"],
                "receipt_sha256": receipt["sha256"],
            },
        )
        transaction.put_node(
            "result",
            result_id,
            package_sha,
            result_document,
        )
        transaction.link("dataset", dataset_key, "job", job_id)
        transaction.link("model", model_key, "job", job_id)
        transaction.link("job", job_id, "result", result_id)
        return transaction.ancestry("result", result_id)


def project_job(output, institution, evidence_store, registry, result_id):
    record = registry.get(result_id)
    entry = registry.catalog_entry(result_id)
    validate_entry(evidence_store, entry)
    candidates = [item for item in record["evidence"] if item["path"].endswith("/receipt.json")]
    if entry["package"] is None or len(candidates) != 1:
        raise StorageError("JOB_RESULT_RECEIPT_REQUIRED")
    receipt_pin = candidates[0]
    job = verified_json(evidence_store, receipt_pin)
    if job.get("schema_version") != "sdss-provider-receipt/1":
        raise StorageError("JOB_RESULT_RECEIPT_SCHEMA_INVALID")
    approval = Approval.model_validate(
        verified_json(evidence_store, Pin.model_validate(job["approval"]).model_dump())
    )
    if (
        approval.provider != job["provider"]
        or approval.operation != job["operation"]
        or approval.model.model_dump() != job["model"]
        or digest(approval.parameters) != job["approval_parameters_sha256"]
    ):
        raise StorageError("JOB_LINEAGE_APPROVAL_BINDING_MISMATCH")
    dataset = Pin.model_validate(approval.parameters.get("dataset_manifest")).model_dump()
    verify_evidence(evidence_store, [dataset])
    package_sha, document = read_result(registry.path, result_id)
    if package_sha != entry["package_sha256"]:
        raise StorageError("JOB_RESULT_CATALOG_BINDING_MISMATCH")
    return _project(
        output, institution, job, result_id, package_sha, document, receipt_pin, dataset
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-id", required=True)
    args = parser.parse_args()
    dsn = os.getenv("SDSS_STORAGE_DSN", "").strip()
    institution = os.getenv("SDSS_STORAGE_INSTITUTION", "").strip()
    if not dsn or not institution:
        parser.error("Storage target and institution must be configured by the operator.")
    rows = project_job(
        LineageStore(dsn),
        institution,
        EvidenceStore(ROOT, LOCK_PATH, LOCK_SHA256),
        ResultRegistry(DATABASE),
        args.result_id,
    )
    print(f"Verified result ancestry entries: {len(rows)}")


if __name__ == "__main__":
    main()
