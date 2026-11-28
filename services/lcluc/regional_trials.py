"""Audit regional optical splits and execute the CPU weak-reference RF experiment."""

import argparse
import json
import re
from collections import Counter
from contextlib import ExitStack
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import rasterio
from shapely.geometry import shape

from services.lcluc.annual_inputs import Bands, Pin
from services.lcluc.annual_rasters import raster_profile, warp, windows
from services.lcluc.classifiers import (
    ClassificationDomain,
    _metrics,
    fit_annual_forest,
    load_artifact,
)
from services.lcluc.province_esri import DEST, SNAPSHOT_SHA256, digest, write_json
from services.lcluc.regional_mosaic import pin
from services.lcluc.taxonomy import load_taxonomy, validate_class_codes
from services.mlops.scene_split_audit import audit_scene_splits

SPLITS = frozenset({"train", "validation", "test"})
CAP = 3500
SEED = 2020
ESRI = "Esri / Impact Observatory v003"
LEGACY_S2 = re.compile(r"(s2[abc])_msil2a_(\d{8})t\d{6}_r\d+_t(\d{2}[a-z]{3})_")
EARTH_S2 = re.compile(r"(s2[abc])_(\d{2}[a-z]{3})_(\d{8})_\d+_l2a")


def scene_identity(source):
    value = source.lower()
    if match := LEGACY_S2.match(value):
        return str(match[1] + ":" + match[3] + ":" + match[2])
    if match := EARTH_S2.fullmatch(value):
        return str(match[1] + ":" + match[2] + ":" + match[3])
    return value


def split_audit(rows, split_sha, buffer_m):
    if set(row["split"] for row in rows) != SPLITS or not np.isfinite(buffer_m) or buffer_m < 30:
        raise ValueError("TRIAL_REQUIRED_SPLITS_AND_BUFFER")
    source_rows = [
        {
            "scene_id": scene_identity(src["source_id"]),
            "split": row["split"],
            "province": row["mosaic"]["region"],
            "source_group": row["window"],
        }
        for row in rows
        for src in row["mosaic"]["sources"]
    ]
    base = audit_scene_splits({"scenes": source_rows}, split_sha)
    checks = []
    for first, second in combinations(rows, 2):
        prior, later = first["mosaic"], second["mosaic"]
        a, b = shape(prior["analysis_geometry"]), shape(later["analysis_geometry"])
        if not a.is_valid or not b.is_valid or a.is_empty or b.is_empty:
            raise ValueError("TRIAL_FOOTPRINT_INVALID")
        gap = a.distance(b)
        source_assets = [
            {asset["sha256"] for scene in m["sources"] for asset in scene["assets"].values()}
            | {m["assets"]["reflectance"]["sha256"]}
            for m in (prior, later)
        ]
        different_splits = first["split"] != second["split"]
        blocker = []
        if different_splits:
            if gap < buffer_m:
                blocker.append("CROSS_SPLIT_SPATIAL_OR_TEMPORAL_REUSE")
            if source_assets[0] & source_assets[1]:
                blocker.append("CROSS_SPLIT_ASSET_HASH_REUSE")
            days = [{item["observed_on"] for item in m["sources"]} for m in (prior, later)]
            if days[0] & days[1]:
                blocker.append("CROSS_SPLIT_OBSERVATION_DATE_REUSE")
        checks.append(
            {
                "left": first["window"],
                "right": second["window"],
                "cross_split": different_splits,
                "separation_m": gap,
                "intersection_m2": a.intersection(b).area,
                "same_calendar_year": prior["year"] == later["year"],
                "blockers": blocker,
            }
        )
    blockers = sorted(
        set(base["blockers"] + [code for item in checks for code in item["blockers"]])
    )
    return {
        "status": "BLOCKED" if blockers else "VERIFIED_REAL",
        "scene_gate": base,
        "separation_m_required": buffer_m,
        "pairs": checks,
        "blockers": blockers,
        "source_product_family_reused": ESRI,
        "temporal_generalization_measured": False,
    }


def verified_rows(folder, index, sensor):
    rows = []
    for item in index:
        if item["sensor"] != sensor or item["split"] not in SPLITS:
            continue
        manifest = Pin.model_validate(item["mosaic"]).local(folder)
        mosaic = json.loads(manifest.read_bytes())
        if (
            mosaic["sensor"] != sensor
            or mosaic["boundary_sha256"] != SNAPSHOT_SHA256
            or (mosaic["grid"]["resolution_m"] != (10 if sensor == "sentinel-2" else 30))
        ):
            raise ValueError("TRIAL_MOSAIC_SCOPE_MISMATCH")
        path = Pin.model_validate(mosaic["assets"]["reflectance"]).local(manifest.parent)
        rows.append(
            {
                "window": item["window"],
                "split": item["split"],
                "mosaic": mosaic,
                "input_sha256": item["mosaic"]["sha256"],
                "path": path,
            }
        )
    return rows


def esri_held(root, year, taxonomy):
    result = []
    for tile in ("48M", "49M"):
        folder = root / DEST / str(year)
        receipt = next(folder.glob(f"{tile}_{year}0101-*.receipt.json"), None)
        if receipt is None:
            raise FileNotFoundError(f"Same-year Esri receipt required for {tile} {year}")
        row = json.loads(receipt.read_bytes())
        if (
            row["dataset"] != ESRI
            or row["year"] != year
            or row["tile"] != tile
            or row["taxonomy_sha256"] != taxonomy.sha256
            or row["boundary_sha256"] != SNAPSHOT_SHA256
        ):
            raise ValueError("ESRI_REFERENCE_IDENTITY_MISMATCH")
        path = Pin.model_validate({k: row[k] for k in ("path", "bytes", "sha256")}).local(root)
        result.append((path, {k: row[k] for k in ("year", "tile", "sha256", "uri")}))
    return result


def labels_at(sources, window, taxonomy):
    values = np.full((int(window.height), int(window.width)), taxonomy.nodata, dtype="uint16")
    for source in sources:
        label = source.read(1, window=window)
        validate_class_codes(label, taxonomy, nodata=taxonomy.nodata)
        # Prefer a thematic observation over QA-only classes at tile overlap.
        take = np.isin(label, taxonomy.thematic_codes) & ~np.isin(values, taxonomy.thematic_codes)
        values[take] = label[take]
    return values


def raster_grid(raster):
    return {
        "crs": raster.crs,
        "transform": raster.transform,
        "width": raster.width,
        "height": raster.height,
    }


def training_set(rows, references, taxonomy):
    rng = np.random.default_rng(SEED)
    samples = {code: [] for code in taxonomy.thematic_codes}
    for row in rows:
        if row["split"] != "train":
            continue
        with ExitStack() as stack:
            data = stack.enter_context(rasterio.open(row["path"]))
            grid = raster_grid(data)
            aligned = [warp(stack, item, grid, nodata=taxonomy.nodata) for item, _ in references]
            for window in windows(grid):
                bands = data.read(window=window)
                support = np.isfinite(bands).all(axis=0)
                labels = labels_at(aligned, window, taxonomy)
                for code in samples:
                    available = bands[:, support & (labels == code)].T
                    if len(available):
                        offsets = rng.choice(
                            len(available), min(CAP, len(available)), replace=False
                        )
                        samples[code].append(available[offsets])
    features, labels = [], []
    for code, values in samples.items():
        if not values:
            continue
        array = np.concatenate(values)
        if len(array) < 40:
            continue
        offsets = rng.choice(len(array), min(CAP, len(array)), replace=False)
        features.append(array[offsets])
        labels.append(np.full(len(offsets), code, dtype="uint16"))
    if len(features) < 2:
        raise ValueError("TRIAL_TRAINING_CLASSES_INSUFFICIENT")
    return np.concatenate(features), np.concatenate(labels)


def infer(row, references, taxonomy, model, stage, *, assess=True):
    matrices = {}
    codes = np.asarray(taxonomy.thematic_codes, dtype="uint16")
    classes = len(codes)
    assets = {name: stage / f"{row['window']}-{name}.tif" for name in ("cover", "confidence")}
    matrix = np.zeros((classes, classes), dtype="int64")
    with ExitStack() as stack:
        source = stack.enter_context(rasterio.open(row["path"]))
        grid = raster_grid(source)
        aligned = [warp(stack, item, grid, nodata=taxonomy.nodata) for item, _ in references]
        cover = stack.enter_context(
            rasterio.open(
                assets["cover"], "w", **raster_profile(grid, 1, "uint16", taxonomy.nodata)
            )
        )
        confidence = stack.enter_context(
            rasterio.open(assets["confidence"], "w", **raster_profile(grid, 1, "float32", np.nan))
        )
        for window in windows(grid):
            prediction, scores = model.predict_forest_reflectance(source.read(window=window))
            cover.write(prediction, 1, window=window)
            confidence.write(scores, 1, window=window)
            if assess and row["split"] != "train":
                expected = labels_at(aligned, window, taxonomy)
                eligible = np.isin(expected, codes) & np.isin(prediction, codes)
                a, b = (np.searchsorted(codes, layer[eligible]) for layer in (expected, prediction))
                matrix += np.bincount(a * classes + b, minlength=classes**2).reshape(
                    classes, classes
                )
    if assess and row["split"] != "train" and matrix.sum():
        matrices = _metrics(matrix, list(map(int, codes)))
    return {
        "window": row["window"],
        "split": row["split"],
        "input_mosaic_sha256": row["input_sha256"],
        "weak_reference_metrics": matrices or None,
        "comparison_pixels": int(matrix.sum()),
        "assets": {name: pin(path) for name, path in assets.items()},
    }


def run(platform, index, expected_sha, destination, buffer_m, *, experiment="E2", sensor="sentinel-2"):
    raw = index.read_bytes()
    if sha256(raw).hexdigest() != expected_sha:
        raise ValueError("TRIAL_INDEX_SHA_MISMATCH")
    rows = verified_rows(index.parent, json.loads(raw), sensor)
    regions = {row["mosaic"]["region"] for row in rows if row["split"] == "train"}
    expected_regions = {"west_java"} if experiment == "E2" else {"banten", "west_java"}
    if regions != expected_regions:
        raise ValueError("TRIAL_TRAINING_REGION_SCOPE_MISMATCH")
    quality_blocked = [
        row["window"]
        for row in rows
        if (
            row["mosaic"]["qa"]["clear_fraction"] < 0.8
            or row["mosaic"]["qa"]["physical_fraction"] < 0.95
            or (sensor == "landsat" and any("QA_RADSAT" not in scene["assets"]
                                            for scene in row["mosaic"]["sources"]))
        )
    ]
    audit = split_audit(rows, expected_sha, buffer_m)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".regional-trial-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "result"
        stage.mkdir()
        common = {
            "schema_version": "sdss-regional-lcluc-trial/1",
            "experiment": experiment,
            "sensor": sensor,
            "input_index_sha256": expected_sha,
            "weak_reference": ESRI,
            "independent_accuracy_measured": False,
            "scientific_approval": "BLOCKED",
            "deployment_allowed": False,
            "split_audit": audit,
        }
        if audit["blockers"] or quality_blocked:
            report = common | {
                "status": "BLOCKED",
                "blockers": audit["blockers"]
                + (["PILOT_WINDOW_QA_BELOW_GATE"] if quality_blocked else []),
                "quality_blocked_windows": quality_blocked,
            }
        else:
            taxonomy = load_taxonomy("esri-io-v003")
            years = {row["mosaic"]["year"] for row in rows}
            if len(years) != 1:
                raise ValueError("TRIAL_SAME_YEAR_REQUIRED")
            year = years.pop()
            references = esri_held(platform, year, taxonomy)
            data_path = stage / "dataset.json"
            write_json(
                data_path,
                {
                    "schema_version": "sdss-regional-lcluc-dataset/1",
                    "input_index_sha256": expected_sha,
                    "year": year,
                    "sensor": sensor,
                    "taxonomy_sha256": taxonomy.sha256,
                    "reference_kind": "weak_reference",
                    "references": [row for _, row in references],
                    "split_audit": audit,
                    "windows": [
                        {
                            "window": row["window"],
                            "split": row["split"],
                            "mosaic_sha256": row["input_sha256"],
                            "source_pins": row["mosaic"]["sources"],
                            "geometry": row["mosaic"]["analysis_geometry"],
                        }
                        for row in rows
                    ],
                },
            )
            features, labels = training_set(rows, references, taxonomy)
            fingerprint = digest(data_path)
            domain = ClassificationDomain.from_taxonomy(taxonomy)
            fixture = any(row["mosaic"]["status"] == "TESTED_SYNTHETIC" for row in rows)
            candidate = fit_annual_forest(features, labels, domain, fingerprint, fixture=fixture)
            model_path = stage / "candidate.npz"
            model_path.write_bytes(candidate.artifact_bytes())
            model = load_artifact(model_path.read_bytes(), digest(model_path))
            outputs = [infer(row, references, taxonomy, model, stage) for row in rows]
            report = common | {
                "status": "TESTED_SYNTHETIC" if fixture else "VERIFIED_REAL",
                "region": "west_java",
                "training_regions": sorted(regions),
                "scope": "pilot windows; scene-distinct geographic splits",
                "year": year,
                "stage": "CANDIDATE_WEAK_REFERENCE",
                "method": "Random Forest",
                "dataset": pin(data_path),
                "dataset_sha256": fingerprint,
                "feature_names": list(Bands[sensor]),
                "taxonomy_sha256": taxonomy.sha256,
                "training_pixels": len(labels),
                "seed": SEED,
                "training_counts": {int(code): count for code, count in Counter(labels).items()},
                "sources": [row for _, row in references],
                "model": pin(model_path),
                "evaluations": outputs,
                "blockers": [
                    "PILOT_WINDOW_ONLY",
                    "INDEPENDENT_REFERENCE_NOT_REGISTERED",
                    "SCIENTIFIC_APPROVAL_NOT_RECORDED",
                ],
            }
        write_json(stage / "trial.json", report)
        stage.rename(destination)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--platform", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--buffer-m", default=300, type=float)
    parser.add_argument("--experiment", choices=["E2", "E3"], default="E2")
    args = parser.parse_args()
    result = run(
        args.platform,
        args.index,
        args.expected_sha256,
        args.output,
        args.buffer_m,
        experiment=args.experiment,
    )
    print(result["status"], result["blockers"])
    for row in result.get("evaluations", []):
        print(
            row["window"],
            row["split"],
            row["comparison_pixels"],
            (row["weak_reference_metrics"] or {}).get("overall_accuracy"),
        )


if __name__ == "__main__":
    main()
