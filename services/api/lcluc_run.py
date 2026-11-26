"""Compute an LCLUC year pair and register the pinned maps and report under one ID."""

import argparse
import csv
import json
import os
from datetime import date
from hashlib import file_digest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from pydantic import Field, model_validator

from services.results.catalog import AssetID, Pin, Strict, prepare_package
from services.results.registry import ResultRegistry

from .evidence import LOCK_PATH, ROOT, EvidenceStore
from .lcluc_cases import CASE_KEY
from .pinned import LOCK_SHA256
from .result_catalog import metric, report, verified_json
from .results import DATABASE, verify_evidence

OUTPUT = "data/curated/lcluc"
PALETTE = (
    "#145738",
    "#308348",
    "#396b6b",
    "#74a580",
    "#21714c",
    "#5b8b78",
    "#76a425",
    "#a59850",
    "#b3a85e",
    "#e69c46",
    "#c37754",
    "#9b424e",
    "#daba91",
    "#326c9a",
    "#6aa9b0",
    "#968778",
    "#7d9db4",
    "#bb9f57",
    "#b8c846",
    "#845965",
    "#4d667b",
    "#afb99f",
    "#707070",
)


class Frame(Strict):
    raster: Pin
    original_raster: Pin | None = None
    observed_on: date
    dataset_id: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=160)
    uri: str = Field(min_length=1, max_length=2000)
    valid_mask: Pin | None = None
    source_receipt: Pin | None = None
    nodata: int | None = None


class Zones(Strict):
    file: Pin
    version: str = Field(min_length=1, max_length=160)


class Pair(Strict):
    schema_version: Literal["sdss-lcluc-pair/1"]
    region: AssetID
    title: str = Field(min_length=1, max_length=180)
    institution: str = Field(min_length=1, max_length=180)
    taxonomy_id: AssetID
    taxonomy_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_kind: Literal["official_reference", "research_reference", "synthetic_fixture"]
    license: str = Field(min_length=1, max_length=128)
    license_evidence: Pin | None = None
    earlier: Frame
    later: Frame
    zones: Zones | None = None
    min_hotspot_pixels: int = Field(default=1, ge=1, le=100000)

    @model_validator(mode="after")
    def valid_pair(self):
        if self.later.observed_on.year <= self.earlier.observed_on.year:
            raise ValueError("LCLUC_YEAR_ORDER_INVALID")
        if self.earlier.raster.sha256 == self.later.raster.sha256:
            raise ValueError("LCLUC_SAME_SOURCE_BYTES_FOR_DIFFERENT_YEARS")
        if self.source_kind == "synthetic_fixture":
            if self.license_evidence is not None or self.license != "UNVERIFIED":
                raise ValueError("LCLUC_FIXTURE_CANNOT_HAVE_PUBLICATION_LICENSE")
        elif not self.license_evidence or self.license in {"UNKNOWN", "UNVERIFIED", "RESTRICTED"}:
            raise ValueError("LCLUC_SOURCE_USE_EVIDENCE_REQUIRED")
        if self.source_kind != "synthetic_fixture":
            if self.earlier.source_receipt is None or self.later.source_receipt is None:
                raise ValueError("LCLUC_YEAR_SOURCE_RECEIPTS_REQUIRED")
        return self

    def pins(self):
        pins = [self.earlier.raster, self.later.raster]
        return [
            pin.model_dump()
            for pin in (
                *pins,
                self.earlier.original_raster,
                self.later.original_raster,
                self.earlier.valid_mask,
                self.earlier.source_receipt,
                self.later.valid_mask,
                self.later.source_receipt,
                self.license_evidence,
                self.zones.file if self.zones else None,
            )
            if pin is not None
        ]


def file_pin(store, path):
    with path.open("rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
    return Pin(
        path=path.relative_to(store.root).as_posix(),
        bytes=path.stat().st_size,
        sha256=digest,
    ).model_dump()


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8"
    )


def frame_preview(store, frame, colors, default_nodata):
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling

    with rasterio.open(store.safe_path(frame.raster.path)) as src:
        ratio = min(1, 720 / max(src.width, src.height))
        shape = max(1, round(src.height * ratio)), max(1, round(src.width * ratio))
        data = src.read(1, out_shape=shape, masked=True, resampling=Resampling.nearest)
    valid = (~np.ma.getmaskarray(data)) & (
        data.data != (frame.nodata if frame.nodata is not None else default_nodata)
    )
    if frame.valid_mask:
        with rasterio.open(store.safe_path(frame.valid_mask.path)) as src:
            valid &= src.read(1, out_shape=shape, resampling=Resampling.nearest) == 1
    rgba = np.zeros((*shape, 4), dtype=np.uint8)
    for code, color in colors.items():
        rgba[valid & (data.data == code)] = tuple(bytes.fromhex(color[1:])) + (255,)
    return data.data, rgba


def previews(store, manifest, analysis, directory, taxonomy):
    import numpy as np
    from PIL import Image

    colors = {item["code"]: PALETTE[i % len(PALETTE)] for i, item in enumerate(analysis["classes"])}
    for item in analysis["classes"]:
        item["color"] = colors[item["code"]]
    before, first = frame_preview(store, manifest.earlier, colors, taxonomy.nodata)
    after, second = frame_preview(store, manifest.later, colors, taxonomy.nodata)
    Image.fromarray(first).save(directory / "earlier.png")
    Image.fromarray(second).save(directory / "later.png")
    shared = (first[:, :, 3] > 0) & (second[:, :, 3] > 0)
    change = np.zeros_like(first)
    change[shared] = (206, 219, 227, 255)
    change[shared & (before != after)] = (192, 45, 50, 255)
    Image.fromarray(change).save(directory / "change.png")


def write_matrix(directory, analysis):
    with (directory / "matrix.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        classes = [item["code"] for item in analysis["classes"]]
        writer.writerow(["from_code/to_code", *classes])
        writer.writerows(
            [code, *cells]
            for code, cells in zip(classes, analysis["transition_matrix_ha"], strict=True)
        )


def create_artifacts(store, manifest, manifest_pin, taxonomy):
    from services.lcluc.change import (
        MaskPin,
        RasterPin,
        ZonePin,
        analyze_change,
        write_change_assets,
    )

    def raster(frame):
        return RasterPin(
            path=store.safe_path(frame.raster.path),
            sha256=frame.raster.sha256,
            observed_on=frame.observed_on,
            taxonomy_sha256=taxonomy.sha256,
            source_kind=manifest.source_kind,
            dataset_id=frame.dataset_id,
            version=frame.version,
            nodata=frame.nodata,
            valid_mask=(
                MaskPin(path=store.safe_path(frame.valid_mask.path), sha256=frame.valid_mask.sha256)
                if frame.valid_mask
                else None
            ),
        )

    zones = (
        ZonePin(
            path=store.safe_path(manifest.zones.file.path),
            sha256=manifest.zones.file.sha256,
            version=manifest.zones.version,
        )
        if manifest.zones
        else None
    )
    groups = getattr(taxonomy, "analysis_groups", {})
    result = analyze_change(
        raster(manifest.earlier),
        raster(manifest.later),
        taxonomy,
        zones=zones,
        forest_codes=groups.get("natural_forest", ()),
        settlement_codes=groups.get("settlement", ()),
        min_hotspot_pixels=manifest.min_hotspot_pixels,
    )
    analysis = result.report
    analysis["source_kind"] = manifest.source_kind
    analysis["source_use_scope"] = "LOCAL_REVIEW"
    parent = store.safe_path(OUTPUT)
    parent.mkdir(parents=True, exist_ok=True)
    case_dir = parent / manifest_pin["sha256"]
    with TemporaryDirectory(prefix="pair-", dir=parent) as work:
        candidate = Path(work) / "assets"
        write_change_assets(result, candidate)
        previews(store, manifest, analysis, candidate, taxonomy)
        write_json(candidate / "report.json", analysis)
        write_matrix(candidate, analysis)
        filenames = (
            "earlier.png",
            "later.png",
            "change.png",
            "report.json",
            "matrix.csv",
            "hotspots.geojson",
            "transition.tif",
        )
        if case_dir.exists():
            for filename in filenames:
                if (candidate / filename).read_bytes() != (case_dir / filename).read_bytes():
                    raise ValueError("LCLUC_PUBLISHED_ASSET_VERSION_CONFLICT")
        else:
            os.replace(candidate, case_dir)
    return analysis, {name: file_pin(store, case_dir / name) for name in filenames}


def package_for(manifest, analysis, assets):
    source_ids = ("earlier-land-cover", "later-land-cover")
    sources = [
        {
            "id": key,
            "title": f"{frame.observed_on.year} {frame.dataset_id}",
            "uri": frame.uri,
            "version": frame.version,
            "license": manifest.license,
            "raw": (frame.original_raster or frame.raster).model_dump(),
            "license_evidence": manifest.license_evidence.model_dump()
            if manifest.license_evidence
            else None,
        }
        for key, frame in zip(source_ids, (manifest.earlier, manifest.later), strict=True)
    ]
    earlier = source_ids[0]
    values = analysis["major_changes"]
    layers = []
    if analysis["hotspot_count"]:
        layers.append(
            {
                "id": "change-hotspots",
                "title": "변화 집중지역",
                "source_id": earlier,
                "format": "GeoJSON",
                "crs": "OGC:CRS84",
                "nodata": {"kind": "not_applicable"},
                "file": assets["hotspots.geojson"],
            }
        )
    return {
        "institution": manifest.institution,
        "adapter": "lcluc-pinned-change/1",
        "period": {
            "start": manifest.earlier.observed_on.isoformat(),
            "end": manifest.later.observed_on.isoformat(),
            "kind": "observation",
        },
        "spatial": {"crs": "OGC:CRS84", "bbox": analysis["grid"]["bounds_crs84"]},
        "metrics": [
            metric(
                "common-valid-area",
                "공통 유효 면적",
                analysis["coverage"]["common_valid_area_ha"],
                "ha",
                earlier,
            ),
            metric("changed-area", "변화 면적", values["changed_area_ha"], "ha", earlier),
            metric(
                "change-rate",
                "공통 유효 면적 대비 변화율",
                values["change_rate_pct"],
                "percent",
                earlier,
            ),
        ],
        "layers": layers,
        "sources": sources,
        "reports": [
            report("lcluc-analysis", "LCLUC 변화·공간 분석 보고서", assets["report.json"], earlier),
            report("lcluc-matrix", "토지피복 전이행렬", assets["matrix.csv"], earlier, "CSV"),
        ],
        "uncertainty": {
            "status": "NOT_REPORTED",
            "reason": "두 고정 지도에서 계산한 면적입니다. 동년 독립 표본에 의한 지도 분류 오차·변화 신뢰구간은 별도 검증이 필요합니다.",
        },
    }


def validate_source_years(store, manifest):
    for frame in (manifest.earlier, manifest.later):
        if frame.source_receipt is None:
            continue
        receipt = verified_json(store, frame.source_receipt.model_dump())
        expected = {
            "schema_version": "sdss-lcluc-source/1",
            "observed_on": frame.observed_on.isoformat(),
            "dataset_id": frame.dataset_id,
            "version": frame.version,
            "source_uri": frame.uri,
            "sha256": frame.raster.sha256,
            "source_kind": manifest.source_kind,
            "license": manifest.license,
        }
        if not isinstance(receipt, dict) or any(receipt.get(k) != v for k, v in expected.items()):
            raise ValueError("LCLUC_SOURCE_RECEIPT_YEAR_OR_HASH_MISMATCH")
        name = f"{frame.uri} {frame.dataset_id} {frame.version}".lower()
        if "worldcover" in name and (
            frame.observed_on.year not in (2020, 2021)
            or ("v200" in name and frame.observed_on.year != 2021)
            or ("v100" in name and frame.observed_on.year != 2020)
        ):
            raise ValueError("LCLUC_WORLDCOVER_SOURCE_YEAR_MISMATCH")


def register_pair(store, registry, manifest_pin, *, allow_fixture=False):
    from services.lcluc.taxonomy import load_taxonomy

    manifest_pin = Pin.model_validate(manifest_pin).model_dump()
    manifest = Pair.model_validate(verified_json(store, manifest_pin))
    if manifest.source_kind == "synthetic_fixture" and not allow_fixture:
        raise ValueError("LCLUC_FIXTURE_REGISTRATION_REQUIRES_EXPLICIT_OPT_IN")
    verify_evidence(store, manifest.pins())
    validate_source_years(store, manifest)
    taxonomy = load_taxonomy(manifest.taxonomy_id, expected_sha256=manifest.taxonomy_sha256)
    analysis, files = create_artifacts(store, manifest, manifest_pin, taxonomy)
    package = prepare_package(
        package_for(manifest, analysis, files),
        safe_path=store.safe_path,
        verify_pins=lambda pins: verify_evidence(store, pins),
        adapter_checks=("EXACT_DISTINCT_YEAR_GRID_AND_TAXONOMY", "COMMON_VALID_CLASSIFIED_AREA"),
    )
    assets = {
        "earlier-preview": files["earlier.png"],
        "later-preview": files["later.png"],
        "change-preview": files["change.png"],
        "report": files["report.json"],
        "matrix": files["matrix.csv"],
        "hotspots": files["hotspots.geojson"],
        "transition": files["transition.tif"],
        "earlier": manifest.earlier.raster.model_dump(),
        "later": manifest.later.raster.model_dump(),
    }
    result = registry.register(
        domain="lcluc",
        source_key=CASE_KEY + manifest_pin["sha256"],
        title=manifest.title,
        evidence_status="TESTED_SYNTHETIC"
        if manifest.source_kind == "synthetic_fixture"
        else "VERIFIED_REAL",
        summary={
            "region": manifest.region,
            "from_year": analysis["from_year"],
            "to_year": analysis["to_year"],
            "taxonomy_id": manifest.taxonomy_id,
            "source_kind": manifest.source_kind,
            "report": files["report.json"],
            "inputs": [manifest_pin, *manifest.pins()],
            "assets": assets,
        },
        evidence=[manifest_pin, *manifest.pins(), *files.values()],
        blockers=[
            "LCLUC_INDEPENDENT_ACCURACY_NOT_ESTABLISHED",
            "LCLUC_PUBLICATION_APPROVAL_REQUIRED",
        ],
    )
    registry.attach_package(result["id"], package)
    return registry.catalog_entry(result["id"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    store = EvidenceStore(ROOT, LOCK_PATH, LOCK_SHA256)
    path = store.safe_path(args.manifest)
    entry = register_pair(
        store,
        ResultRegistry(DATABASE),
        {
            "path": args.manifest,
            "sha256": args.sha256,
            "bytes": path.stat().st_size,
        },
    )
    print(json.dumps({key: entry[key] for key in ("result_id", "status", "package_sha256")}))


if __name__ == "__main__":
    main()
