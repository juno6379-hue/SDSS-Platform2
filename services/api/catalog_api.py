"""Read the scientific package by the existing result ID and record distinct decisions."""

import json
import os
from hashlib import sha256
from hmac import compare_digest
from typing import Literal

from fastapi import HTTPException, Request, Response
from pydantic import Field

from services.results.catalog import Pin, Strict, package_pins
from services.results.registry import RegistryError

from .evidence import EvidenceBlocked
from .results import check_local, verify_evidence

ASSET_TYPES = {
    "GeoJSON": ("application/geo+json", "geojson"),
    "GeoTIFF": ("image/tiff", "tif"),
    "PDF": ("application/pdf", "pdf"),
    "JSON": ("application/json", "json"),
    "CSV": ("text/csv", "csv"),
    "Markdown": ("text/markdown", "md"),
}


class Decision(Strict):
    decision: Literal["APPROVED", "REJECTED"]
    note: str = Field(min_length=1, max_length=2000)
    evidence: Pin
    expected_revision: int = Field(ge=0, strict=True)
    package_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def authority(request, axis):
    configured = {
        key: os.getenv(f"SDSS_CATALOG_{key.upper()}_TOKEN", "")
        for key in ("scientific", "publication")
    }
    actor = os.getenv(f"SDSS_CATALOG_{axis.upper()}_AUTHORITY", "").strip()
    if (
        not configured[axis]
        or not actor
        or (configured["scientific"] and configured["scientific"] == configured["publication"])
    ):
        raise HTTPException(503, detail="CATALOG_DECISION_AUTHORITY_NOT_CONFIGURED")
    prefix, _, token = request.headers.get("authorization", "").partition(" ")
    if prefix.lower() != "bearer" or not compare_digest(token.encode(), configured[axis].encode()):
        raise HTTPException(403, detail="CATALOG_DECISION_AUTHORITY_REQUIRED")
    return actor


def validate_entry(store, entry):
    if entry["package"] is not None:
        verify_evidence(store, package_pins(entry["package"]))
    pins = []
    for axis in ("scientific", "publication"):
        history = entry["governance"][axis]["history"]
        if history:
            pins.append(history[-1]["evidence"])
    verify_evidence(store, pins)


def expose_entry(entry):
    package = entry["package"]
    if package is None:
        return entry
    prefix = f"/api/results/{entry['result_id']}/catalog/assets/"
    return {
        **entry,
        "package": {
            **package,
            "sources": [
                {
                    **{
                        key: value
                        for key, value in item.items()
                        if key not in {"raw", "license_evidence"}
                    },
                    "sha256": item["raw"]["sha256"],
                    "bytes": item["raw"]["bytes"],
                }
                for item in package["sources"]
            ],
            **{
                group: [
                    {
                        **{key: value for key, value in item.items() if key != "file"},
                        "sha256": item["file"]["sha256"],
                        "bytes": item["file"]["bytes"],
                        "href": prefix + item["id"],
                    }
                    for item in package[group]
                ]
                for group in ("layers", "reports")
            },
        },
    }


def mount_catalog(app, store, repository):
    @app.get("/api/results/{result_id}/catalog")
    def catalog_entry(request: Request, result_id: str):
        check_local(request)
        entry = repository().catalog_entry(result_id)
        validate_entry(store, entry)
        return expose_entry(entry)

    @app.get("/api/results/{result_id}/catalog/assets/{asset_id}")
    def catalog_asset(request: Request, result_id: str, asset_id: str):
        check_local(request)
        entry = repository().catalog_entry(result_id)
        package = entry["package"]
        asset = (
            next(
                (
                    item
                    for item in [*package["layers"], *package["reports"]]
                    if item["id"] == asset_id
                ),
                None,
            )
            if package
            else None
        )
        if asset is None:
            raise HTTPException(404, detail="CATALOG_ASSET_NOT_FOUND")
        validate_entry(store, entry)
        pin = asset["file"]
        with store.safe_path(pin["path"]).open("rb") as handle:
            raw = handle.read(pin["bytes"] + 1)
        if len(raw) != pin["bytes"] or sha256(raw).hexdigest() != pin["sha256"]:
            raise EvidenceBlocked("CATALOG_ASSET_CHANGED_DURING_READ")
        media_type, extension = ASSET_TYPES[asset["format"]]
        return Response(
            raw,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{asset_id}.{extension}"'},
        )

    @app.post("/api/results/{result_id}/catalog/decisions/{axis}")
    def catalog_decision(
        request: Request, result_id: str, axis: Literal["scientific", "publication"], body: Decision
    ):
        check_local(request)
        actor = authority(request, axis)
        repo = repository()
        entry = repo.catalog_entry(result_id)
        if entry["package_sha256"] != body.package_sha256:
            raise RegistryError("PACKAGE_CONFLICT")
        validate_entry(store, entry)
        verify_evidence(store, [body.evidence.model_dump()])
        # Decision evidence is content-pinned and binds the role, scope and immutable package.
        evidence = store.safe_path(body.evidence.path).read_bytes()
        if (
            len(evidence) != body.evidence.bytes
            or sha256(evidence).hexdigest() != body.evidence.sha256
        ):
            raise EvidenceBlocked("CATALOG_DECISION_EVIDENCE_DRIFT")
        try:
            document = json.loads(evidence)
            bound = {
                "result_id": result_id,
                "package_sha256": body.package_sha256,
                "authority": actor,
                "axis": axis,
                "decision": body.decision,
                "scope": "INDEPENDENT_SCIENTIFIC"
                if axis == "scientific"
                else "INSTITUTIONAL_PUBLICATION",
            }
            if (
                any(document.get(key) != value for key, value in bound.items())
                or not isinstance(document.get("reference"), str)
                or not document["reference"].strip()
            ):
                raise ValueError("binding")
        except (ValueError, AttributeError) as error:
            raise EvidenceBlocked("CATALOG_DECISION_EVIDENCE_BINDING_INVALID") from error
        return expose_entry(
            repo.record_decision(result_id, axis=axis, actor=actor, **body.model_dump())
        )
