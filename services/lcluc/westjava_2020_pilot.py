"""Reproduce the real 2020 West Java optical trial from held, read-only assets."""

import argparse
import json
from pathlib import Path

from rasterio.warp import transform_bounds
from shapely.geometry import box, mapping, shape

from services.lcluc.annual_inputs import Bands
from services.lcluc.province_esri import digest, write_json
from services.lcluc.province_optical_plan import boundary
from services.lcluc.regional_mosaic import MosaicInput, produce_mosaic

YEAR = 2020
SENTINEL = {
    "g00": ("7eccb6eb87980d0b4385ba63", "train"),
    "g01": ("d0e90fd7a6cc585672fde9ef", "validation"),
    "boundary-00": ("ba99e17bfd284ede432efd7b", "test"),
    "boundary-01": ("97d491c5f4423ac1585527a4", "train"),
}
BANTEN_SENTINEL = {
    "banten-g00": ("57d7f3cf23be899c3f23f3de", "train"),
    "banten-boundary": ("3ce3e8c6767a62ef80b50d9d", "train"),
    "banten-holdout": ("52e2806f1af3458a7066d931", "test"),
}
LANDSAT = (
    "LC08_L2SP_122064_20200828_02_T1",
    "LC08_L2SP_122065_20200727_02_T1",
)
LANDSAT_NAMES = dict(
    zip(
        (*Bands["landsat"], "QA_PIXEL"),
        ("blue", "green", "red", "nir08", "swir16", "swir22", "qa_pixel"),
        strict=True,
    )
)
CHECKPOINTS = Path("evidence/onemap_sentinel/held-audit-20261124/native-checkpoints")


def input_pin(root, file, expected=None):
    return {
        "path": file.relative_to(root).as_posix(),
        "bytes": file.stat().st_size,
        "sha256": expected or digest(file),
    }


def read(file):
    return json.loads(file.read_bytes())


def scene_uri(stac):
    return next(row["href"] for row in stac["links"] if row.get("rel") == "self")


def sentinel_input(platform, legacy, checkpoint, region="west_java"):
    import rasterio

    audit = platform / CHECKPOINTS / f"{checkpoint}.json"
    evidence = read(audit)
    if (
        evidence["province"] != region
        or evidence["year"] != YEAR
        or not evidence["verified_patch_count"]
    ):
        raise ValueError("PILOT_AUDIT_SCOPE_MISMATCH")
    source = Path(evidence["parent_path"]).parent
    hashes = {Path(row["path"]): row["sha256"] for row in evidence["verified_files"]}
    item = source / "stac-item.json"
    if digest(item) != hashes[item]:
        raise ValueError("WEST_JAVA_STAC_AUDIT_DRIFT")
    stac = read(item)
    props = stac["properties"]
    calibration = source / "calibration.json"
    absolute_xml = source / "product-metadata.xml"
    optics = read(calibration)
    if digest(absolute_xml) != optics["source_xml_sha256"]:
        raise ValueError("WEST_JAVA_CALIBRATION_XML_DRIFT")
    paths = {name: source / f"raw-{name}.tif" for name in (*Bands["sentinel-2"], "SCL")}
    with rasterio.open(paths["B02"]) as raster:
        west, south, east, north = transform_bounds(raster.crs, "EPSG:4326", *raster.bounds)
    scene = {
        "source_id": stac["id"].lower(),
        "observed_on": props["datetime"][:10],
        "raw_root": "legacy",
        "provider": "planetary-computer",
        "uri": scene_uri(stac),
        "version": "sentinel-2-l2a-" + optics["baseline"],
        "license": "Copernicus Sentinel data terms",
        "acquired_at": props["datetime"],
        "assets": {name: input_pin(legacy, path, hashes[path]) for name, path in paths.items()},
        "scale": optics["scale"],
        "offset": optics["offset"],
        "stac_item": input_pin(legacy, item, hashes[item]),
        "calibration": input_pin(legacy, calibration),
    }
    return [scene], mapping(box(west, south, east, north))


def landsat_inputs(platform):
    directory = platform / "data/raw/explorer/province/banten-optical/landsat-native" / str(YEAR)
    results = []
    overlap = boundary(platform, province="west_java")
    for source_id in LANDSAT:
        receipt = read(directory / source_id / "scene-receipt.json")
        if receipt["scene"] != source_id or receipt["collection"] != "landsat-c2-l2":
            raise ValueError("LANDSAT_HELD_RECEIPT_MISMATCH")
        page = receipt["stac_page"]
        source = platform / page["path"]
        if digest(source) != page["sha256"] or source.stat().st_size != page["bytes"]:
            raise ValueError("LANDSAT_HELD_STAC_MISMATCH")
        scene = next(item for item in read(source)["features"] if item["id"] == source_id)
        overlap = overlap.intersection(shape(scene["geometry"]))
        entries = receipt["assets"]
        assets = {
            key: {k: entries[name][k] for k in ("path", "bytes", "sha256")}
            for key, name in LANDSAT_NAMES.items()
        }
        if "qa_radsat" in entries:
            assets["QA_RADSAT"] = {k: entries["qa_radsat"][k] for k in ("path", "bytes", "sha256")}
        results.append(
            {
                "source_id": source_id.lower(),
                "observed_on": receipt["observed_at"][:10],
                "raw_root": "platform",
                "provider": "planetary-computer",
                "uri": scene_uri(scene),
                "version": "landsat-c2-l2",
                "license": "USGS Landsat open data",
                "acquired_at": entries["blue"]["received_at"],
                "assets": assets,
                "scale": [0.0000275] * 6,
                "offset": [-0.2] * 6,
                "stac_item": page,
            }
        )
    focus = overlap.representative_point()
    if focus.is_empty:
        raise ValueError("LANDSAT_PROVINCE_OVERLAP_MISSING")
    geometry = overlap.intersection(
        box(focus.x - 0.045, focus.y - 0.045, focus.x + 0.045, focus.y + 0.045)
    )
    return results, mapping(geometry)


def run(platform, legacy, output, sensors, *, integration=False):
    output.mkdir(parents=True, exist_ok=True)
    result = []
    windows = {
        name: (*sentinel_input(platform, legacy, checkpoint), split)
        for name, (checkpoint, split) in SENTINEL.items()
    }
    batches = (
        [
            ("west_java", "sentinel-2", name, scenes, geometry, split)
            for name, (scenes, geometry, split) in windows.items()
        ]
        if "sentinel-2" in sensors
        else []
    )
    if integration:
        batches.extend(
            (
                "banten",
                "sentinel-2",
                name,
                *sentinel_input(platform, legacy, checkpoint, "banten"),
                split,
            )
            for name, (checkpoint, split) in BANTEN_SENTINEL.items()
        )
    if "landsat" in sensors:
        scenes, geometry = landsat_inputs(platform)
        batches.append(("west_java", "landsat", "overlap", scenes, geometry, "mosaic-only"))
    for region, sensor, key, scenes, geometry, split in batches:
        target = output / (sensor + "-" + key)
        config = {
            "schema_version": "lcluc-regional-mosaic/1",
            "region": region,
            "year": YEAR,
            "sensor": sensor,
            "evidence": "real",
            "scenes": scenes,
            "geometry": geometry,
        }
        manifest = target.with_suffix(".inputs.json")
        if manifest.exists() and read(manifest) != json.loads(json.dumps(config)):
            raise ValueError("PILOT_INPUT_CHANGED")
        if not manifest.exists():
            write_json(manifest, config)
        expected = digest(manifest)
        if target.exists():
            old = read(target / "mosaic.json")
            if old["input_sha256"] != expected or not all(
                digest(target / pin["path"]) == pin["sha256"] for pin in old["assets"].values()
            ):
                raise ValueError("PILOT_MOSAIC_CHANGED")
        else:
            produce_mosaic(
                MosaicInput.model_validate(config),
                {"platform": platform, "legacy": legacy},
                target,
                expected,
            )
        mosaic = target / "mosaic.json"
        result.append(
            {"window": key, "sensor": sensor, "split": split, "mosaic": input_pin(output, mosaic)}
        )
        print(sensor, key, read(mosaic)["qa"], flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", type=Path, default=Path("."))
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sensor", choices=["sentinel-2", "landsat", "both"], default="both")
    parser.add_argument("--integration", action="store_true")
    args = parser.parse_args()
    results = run(
        args.platform.resolve(),
        args.legacy.resolve(),
        args.output.resolve(),
        args.sensor,
        integration=args.integration,
    )
    name = "joint" if args.integration else "westjava"
    write_json(args.output / f"{name}-{args.sensor}-mosaics.json", results)


if __name__ == "__main__":
    main()
