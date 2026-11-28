"""Build pinned annual optical products on sensor-specific equal-area grids."""

import argparse
import json
from contextlib import ExitStack
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal
from warnings import catch_warnings, filterwarnings

import numpy as np
import rasterio
from pydantic import Field, model_validator
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.windows import transform
from shapely.geometry import mapping, shape
from shapely.ops import transform as project

from services.lcluc.annual_inputs import Bands, Input, Pin, Quality, Scene, Sensor
from services.lcluc.annual_rasters import equal_area_grid, raster_profile, warp, windows
from services.lcluc.classifiers import CLEAR_SCL
from services.lcluc.province_esri import SNAPSHOT_SHA256, digest, write_json
from services.lcluc.province_optical_plan import PROJECT, boundary

RESOLUTION = {"sentinel-2": 10, "landsat": 30}
NATIVE = {"sentinel-2": (10, 10, 10, 10, 20, 20, 20), "landsat": (30,) * 7}
CLOUD_MASK = 0b111111
LANDSAT_RADSAT_MASK = (0b111111 << 1) | (1 << 11)
INDICES = {"NDVI": (3, 2), "NDWI": (1, 3), "NDMI": (3, 4), "NDBI": (4, 3), "NBR": (3, 5)}


class RegionalScene(Scene):
    raw_root: Literal["platform", "legacy"]
    stac_item: Pin
    calibration: Pin | None = None


class MosaicInput(Input):
    schema_version: Literal["lcluc-regional-mosaic/1"]
    region: Literal["banten", "west_java"]
    year: int = Field(ge=1982, le=2100)
    sensor: Sensor
    evidence: Literal["real", "synthetic"]
    geometry: dict | None = None
    scenes: Annotated[list[RegionalScene], Field(min_length=1, max_length=64)]

    @model_validator(mode="after")
    def check_sources(self):
        expected = {*Bands[self.sensor], Quality[self.sensor]}
        if len({scene.source_id for scene in self.scenes}) != len(self.scenes):
            raise ValueError("DUPLICATE_MOSAIC_SOURCE_SCENE")
        for scene in self.scenes:
            if self.sensor == "landsat":
                keys = (expected, expected | {"QA_RADSAT"})
                if scene.scale != (0.0000275,) * 6 or scene.offset != (-0.2,) * 6:
                    raise ValueError("LANDSAT_C2_REFLECTANCE_SCALE_REQUIRED")
            else:
                keys = (expected,)
                if scene.calibration is None or self.year < 2015:
                    raise ValueError("SENTINEL_CALIBRATION_REQUIRED")
            if scene.assets.keys() not in keys:
                raise ValueError("MOSAIC_ASSETS_INCOMPLETE")
            if scene.observed_on.year != self.year or min(scene.scale) <= 0:
                raise ValueError("MOSAIC_OBSERVATION_YEAR_OR_SCALE_INVALID")
        return self


def open_provenance(scene, roots, sensor):
    root = roots[scene.raw_root]
    stac = json.loads(scene.stac_item.local(root).read_bytes())
    if stac.get("type") == "FeatureCollection":
        stac = next(
            (
                item
                for item in stac.get("features", [])
                if item.get("id", "").lower() == scene.source_id
            ),
            {},
        )
    expected_collection = "sentinel-2-l2a" if sensor == "sentinel-2" else "landsat-c2-l2"
    if (
        stac.get("id", "").lower() != scene.source_id
        or stac.get("collection") != expected_collection
        or str(stac.get("properties", {}).get("datetime", ""))[:10] != scene.observed_on.isoformat()
    ):
        raise ValueError("SCENE_STAC_ID_OR_DATE_MISMATCH")
    if sensor == "landsat":
        if stac["properties"].get("platform") not in {"landsat-8", "landsat-9"}:
            raise ValueError("LANDSAT_8_OR_9_BAND_CONTRACT_REQUIRED")
    else:
        calibration = json.loads(scene.calibration.local(root).read_bytes())
        if (
            calibration.get("verified") is not True
            or calibration.get("product_identity_verified") is not True
            or calibration.get("scale_offset_applied_to_image") is not False
            or calibration.get("product_id", "").lower() != scene.source_id
            or tuple(calibration.get("band_names", [])) != Bands[sensor]
            or tuple(calibration.get("scale", [])) != scene.scale
            or tuple(calibration.get("offset", [])) != scene.offset
        ):
            raise ValueError("SENTINEL_CALIBRATION_UNVERIFIED")
    return stac


def open_scene(stack, scene, roots, sensor, grid):
    root = roots[scene.raw_root]
    expected = dict(zip((*Bands[sensor], Quality[sensor]), NATIVE[sensor], strict=True))
    if "QA_RADSAT" in scene.assets:
        expected["QA_RADSAT"] = 30
    paths = {name: pin.local(root) for name, pin in scene.assets.items()}
    for name, path in paths.items():
        with rasterio.open(path) as source:
            if (
                not source.crs
                or not source.crs.is_projected
                or (not np.allclose(source.res, expected[name], rtol=0, atol=0.01))
            ):
                raise ValueError(f"MOSAIC_NATIVE_GRID_MISMATCH:{name}")
    bands = [
        warp(stack, paths[name], grid, resampling=Resampling.bilinear) for name in Bands[sensor]
    ]
    qa = warp(
        stack, paths[Quality[sensor]], grid, quality=True, nodata=0 if sensor == "sentinel-2" else 1
    )
    saturation = (
        warp(stack, paths["QA_RADSAT"], grid, quality=True) if "QA_RADSAT" in paths else None
    )
    return scene, bands, qa, saturation


def observe(opened, sensor, window, inside):
    available = np.zeros(inside.shape, dtype="uint32")
    clear_count = np.zeros_like(available)
    selected = np.zeros_like(available)
    source_bits = np.zeros((2, *inside.shape), dtype="uint32")
    image = np.full((6, *inside.shape), np.nan, dtype="float32")
    observations = []
    for index, (scene, bands, qa, saturation) in enumerate(opened, 1):
        quality = qa.read(1, window=window)
        raw = np.stack([band.read(1, window=window) for band in bands])
        present = inside & (raw > 0).all(axis=0)
        if sensor == "sentinel-2":
            if (quality > 11).any():
                raise ValueError("MOSAIC_SCL_CLASS_INVALID")
            present &= quality != 0
            clear = present & np.isin(quality, CLEAR_SCL)
        else:
            present &= (quality & 1) == 0
            clear = present & ((quality & CLOUD_MASK) == 0)
            if saturation is not None:
                clear &= (saturation.read(1, window=window) & LANDSAT_RADSAT_MASK) == 0
        raw = raw * np.asarray(scene.scale, dtype="float32")[:, None, None]
        raw += np.asarray(scene.offset, dtype="float32")[:, None, None]
        available += present
        clear_count += clear
        source_bits[(index - 1) // 32][clear] |= np.uint32(1 << ((index - 1) % 32))
        if sensor == "sentinel-2":
            take = clear & (selected == 0)
            selected[take] = index
            image[:, take] = raw[:, take]
        else:
            raw[:, ~clear] = np.nan
            observations.append(raw)
    if observations:
        with catch_warnings():
            filterwarnings("ignore", message="All-NaN slice encountered", category=RuntimeWarning)
            image = np.nanmedian(np.stack(observations), axis=0)
    status = np.where(
        inside, 1 + (available > 0).astype("uint32") + (clear_count > 0).astype("uint32"), 0
    )
    return image, np.stack([status, available, clear_count, selected, *source_bits])


def normalized_indices(image):
    pairs = [(image[a], image[b]) for a, b in INDICES.values()]
    return np.stack(
        [
            np.divide(
                a - b, a + b, out=np.full_like(a, np.nan), where=np.isfinite(a + b) & (a + b != 0)
            )
            for a, b in pairs
        ]
    )


def pin(path):
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": digest(path)}


def produce_mosaic(config, roots, destination, manifest_sha):
    if destination.exists():
        raise FileExistsError(destination)
    official = boundary(roots["platform"], province=config.region)
    aoi = official
    if config.geometry is not None:
        geometry = shape(config.geometry)
        if (
            not geometry.is_valid
            or geometry.is_empty
            or geometry.geom_type not in {"Polygon", "MultiPolygon"}
        ):
            raise ValueError("MOSAIC_WINDOW_GEOMETRY_INVALID")
        aoi = aoi.intersection(geometry)
    if aoi.is_empty or aoi.area <= 0:
        raise ValueError("MOSAIC_WINDOW_OUTSIDE_REGION")
    aoi = project(PROJECT, aoi)
    province = project(PROJECT, official)
    grid = equal_area_grid(aoi, RESOLUTION[config.sensor])
    geometry = mapping(aoi)
    scenes = sorted(config.scenes, key=lambda scene: (scene.observed_on, scene.source_id))
    stac = [open_provenance(scene, roots, config.sensor) for scene in scenes]
    for entry in stac:
        footprint = shape(entry["geometry"])
        if not footprint.is_valid or not project(PROJECT, footprint).intersection(aoi).area > 0:
            raise ValueError("MOSAIC_SCENE_OUTSIDE_WINDOW")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".optical-mosaic-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "result"
        stage.mkdir()
        image_path, qa_path, indices_path = (
            stage / name for name in ("reflectance.tif", "support.tif", "indices.tif")
        )
        totals = np.zeros(3, dtype="int64")
        with ExitStack() as stack:
            opened = [open_scene(stack, scene, roots, config.sensor, grid) for scene in scenes]
            image = stack.enter_context(
                rasterio.open(image_path, "w", **raster_profile(grid, 6, "float32", np.nan))
            )
            image.descriptions = Bands[config.sensor]
            qa = stack.enter_context(
                rasterio.open(qa_path, "w", **raster_profile(grid, 6, "uint32", None))
            )
            qa.descriptions = (
                "cell_status",
                "physical_observations",
                "clear_observations",
                "selected_scene",
                "clear_scene_bits_1_32",
                "clear_scene_bits_33_64",
            )
            indices = stack.enter_context(
                rasterio.open(
                    indices_path, "w", **raster_profile(grid, len(INDICES), "float32", np.nan)
                )
            )
            indices.descriptions = tuple(INDICES)
            for window in windows(grid):
                inside = geometry_mask(
                    [geometry],
                    (int(window.height), int(window.width)),
                    transform(window, grid["transform"]),
                    invert=True,
                )
                data, support = observe(opened, config.sensor, window, inside)
                totals += [inside.sum(), (support[1] > 0).sum(), (support[2] > 0).sum()]
                image.write(data, window=window)
                qa.write(support, window=window)
                indices.write(normalized_indices(data), window=window)
        pixels, physical, clear = map(int, totals)
        if pixels == 0:
            raise ValueError("MOSAIC_GEOMETRY_NO_GRID_CELLS")
        blockers = []
        if config.geometry is not None:
            blockers.append("PILOT_WINDOW_ONLY")
        if physical / pixels < 0.95 or clear / pixels < 0.80:
            blockers.append("DEVELOPMENT_COVERAGE_THRESHOLDS_NOT_MET")
        if config.sensor == "landsat" and any("QA_RADSAT" not in scene.assets for scene in scenes):
            blockers.append("LANDSAT_SATURATION_UNCHECKED")
        method = (
            "chronological-first-clear-v1"
            if config.sensor == "sentinel-2"
            else "clear-bandwise-median-v1"
        )
        release = {
            "schema_version": "lcluc-regional-mosaic-result/1",
            "status": "VERIFIED_REAL" if config.evidence == "real" else "TESTED_SYNTHETIC",
            "input_sha256": manifest_sha,
            "region": config.region,
            "year": config.year,
            "sensor": config.sensor,
            "scope": "province" if config.geometry is None else "pilot_window",
            "method": method,
            "boundary_sha256": SNAPSHOT_SHA256,
            "analysis_geometry": geometry,
            "province_area_m2": province.area,
            "grid": {
                **grid,
                "transform": list(grid["transform"])[:6],
                "resolution_m": RESOLUTION[config.sensor],
            },
            "assets": {
                name: pin(item)
                for name, item in (
                    ("reflectance", image_path),
                    ("support", qa_path),
                    ("indices", indices_path),
                )
            },
            "sources": [
                scene.model_dump(mode="json") | {"index": index, "geometry": entry["geometry"]}
                for index, (scene, entry) in enumerate(zip(scenes, stac, strict=True), 1)
            ],
            "qa": {
                "total_pixels": pixels,
                "six_band_pixels": physical,
                "clear_pixels": clear,
                "physical_fraction": physical / pixels,
                "clear_fraction": clear / pixels,
                "missing_area_m2": (pixels - physical) * RESOLUTION[config.sensor] ** 2,
                "province_clear_fraction_upper_bound": clear
                * RESOLUTION[config.sensor] ** 2
                / province.area,
                "development_thresholds": {"physical_fraction": 0.95, "clear_fraction": 0.80},
            },
            "blockers": blockers,
            "production_ready": False,
            "independent_accuracy_measured": False,
        }
        write_json(stage / "mosaic.json", release)
        stage.rename(destination)
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--platform", type=Path, default=Path("."))
    parser.add_argument("--legacy", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.manifest.read_bytes()
    if sha256(raw).hexdigest() != args.expected_sha256:
        raise ValueError("MOSAIC_INPUT_SHA_MISMATCH")
    release = produce_mosaic(
        MosaicInput.model_validate_json(raw),
        {"platform": args.platform, "legacy": args.legacy},
        args.output,
        args.expected_sha256,
    )
    print(
        json.dumps(
            {key: release[key] for key in ("status", "sensor", "qa", "blockers")},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
