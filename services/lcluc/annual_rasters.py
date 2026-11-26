"""Windowed annual reflectance, RF candidates, and matched-grid evaluation."""

from contextlib import ExitStack, contextmanager
from hashlib import sha256 as hash_bytes
from math import ceil, floor
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, transform
from shapely.errors import ShapelyError
from shapely.geometry import mapping, shape
from shapely.ops import transform as project

from services.datahub.connectors.onemap.boundary import sha256
from services.lcluc.annual_inputs import Bands, Quality
from services.lcluc.classifiers import (
    CLEAR_SCL,
    ClassificationDomain,
    _metrics,
    fit_annual_forest,
    load_artifact,
)
from services.lcluc.taxonomy import validate_class_codes

RESOLUTION = 30
BLOCK = 256


@contextmanager
def atomic_output(path):
    with TemporaryDirectory(dir=path.parent, prefix=".annual-") as folder:
        staged = Path(folder) / path.name
        yield staged
        staged.replace(path)


def annual_grid(bundle, folder):
    import json

    from pyproj import Transformer

    try:
        boundary = shape(json.loads(bundle.boundary.local(folder).read_bytes()))
    except (AttributeError, KeyError, TypeError, ShapelyError) as error:
        raise ValueError("BOUNDARY_GEOJSON_INVALID") from error
    if (
        boundary.is_empty or not boundary.is_valid or boundary.geom_type not in {"Polygon", "MultiPolygon"}
        or not 94 <= boundary.bounds[0] < boundary.bounds[2] <= 142
        or not -12 <= boundary.bounds[1] < boundary.bounds[3] <= 7
    ):
        raise ValueError("BOUNDARY_INVALID_FOR_INDONESIA")
    projected = project(Transformer.from_crs(4326, 6933, always_xy=True).transform, boundary)
    xmin, ymin, xmax, ymax = projected.bounds
    west, north = RESOLUTION * floor(xmin / RESOLUTION), RESOLUTION * ceil(ymax / RESOLUTION)
    width, height = ceil((xmax - west) / RESOLUTION), ceil((north - ymin) / RESOLUTION)
    if width * height > 200_000_000:
        raise ValueError("BOUNDARY_GRID_TOO_LARGE")
    return {
        "crs": "EPSG:6933", "transform": from_origin(west, north, RESOLUTION, RESOLUTION),
        "width": width, "height": height,
    }, mapping(projected)


def windows(grid):
    for y in range(0, grid["height"], BLOCK):
        for x in range(0, grid["width"], BLOCK):
            yield Window(x, y, min(BLOCK, grid["width"] - x), min(BLOCK, grid["height"] - y))


def raster_profile(grid, count, dtype, nodata):
    return {
        **grid, "driver": "GTiff", "count": count, "dtype": dtype, "nodata": nodata,
        "tiled": True, "blockxsize": BLOCK, "blockysize": BLOCK, "compress": "deflate",
        "BIGTIFF": "IF_SAFER",
    }


def warp(stack, path, grid, *, quality=False, nodata=0):
    source = stack.enter_context(rasterio.open(path))
    if source.count != 1 or not source.crs or np.dtype(source.dtypes[0]).kind not in "ui":
        raise ValueError("INTEGER_SINGLE_BAND_RASTER_WITH_CRS_REQUIRED")
    if source.nodata is not None and source.nodata != nodata:
        raise ValueError("UNEXPECTED_RASTER_NODATA")
    if quality and np.dtype(source.dtypes[0]).itemsize > 2:
        raise ValueError("QUALITY_DTYPE_INVALID")
    return stack.enter_context(WarpedVRT(
        source, **grid, src_nodata=nodata, nodata=nodata, resampling=Resampling.nearest,
    ))


def composite(scene_windows, sensor, window, aoi):
    present = np.zeros_like(aoi)
    selected = np.zeros_like(aoi)
    image = np.full((6, *aoi.shape), np.nan, dtype="float32")
    for scene, bands, qa, saturation in scene_windows:
        quality = qa.read(1, window=window)
        raw = np.stack([band.read(1, window=window) for band in bands])
        if sensor == "sentinel-2" and ((quality < 0) | (quality > 11)).any():
            raise ValueError("SCL_CLASS_INVALID")
        available = aoi & (raw > 0).all(axis=0)
        available &= (quality != 0) if sensor == "sentinel-2" else ((quality & 1) == 0)
        clear = np.isin(quality, CLEAR_SCL) if sensor == "sentinel-2" else ((quality & 63) == 0)
        if saturation is not None:
            clear &= saturation.read(1, window=window) == 0
        take = available & clear & ~selected
        image[:, take] = (
            raw[:, take].astype("float64") * np.asarray(scene.scale)[:, None] + np.asarray(scene.offset)[:, None]
        )
        if not np.isfinite(image[:, take]).all():
            raise ValueError("REFLECTANCE_NOT_FINITE")
        present |= available
        selected |= take
    return image, present, selected


def prepare(bundle, folder, output, grid, geometry):
    totals = {}
    for sensor, scenes in bundle.sensors.items():
        path = output / f"{sensor}-reflectance.tif"
        counts = np.zeros(3, dtype=np.int64)
        with atomic_output(path) as staged, ExitStack() as stack:
            opened = []
            for scene in sorted(scenes, key=lambda item: (item.observed_on, item.source_id)):
                bands = [warp(stack, scene.assets[name].local(folder), grid) for name in Bands[sensor]]
                qa = warp(stack, scene.assets[Quality[sensor]].local(folder), grid, quality=True,
                          nodata=0 if sensor == "sentinel-2" else 1)
                saturation = scene.assets.get("QA_RADSAT")
                radsat = warp(stack, saturation.local(folder), grid, quality=True) if saturation else None
                opened.append((scene, bands, qa, radsat))
            dst = stack.enter_context(rasterio.open(staged, "w", **raster_profile(grid, 6, "float32", np.nan)))
            dst.descriptions = Bands[sensor]
            for window in windows(grid):
                aoi = geometry_mask([geometry], (int(window.height), int(window.width)),
                                    transform(window, grid["transform"]), invert=True)
                image, present, clear = composite(opened, sensor, window, aoi)
                counts += [aoi.sum(), present.sum(), clear.sum()]
                dst.write(image, window=window)
        area, present, clear = map(int, counts)
        if not area:
            raise ValueError("BOUNDARY_CONTAINS_NO_GRID_CELLS")
        totals[sensor] = {
            "boundary_pixels": area, "six_band_pixels": present, "clear_pixels": clear,
            "physical_fraction": present / area, "clear_fraction": clear / area,
            "scene_count": len(scenes), "qa_radsat_scenes": sum("QA_RADSAT" in scene.assets for scene in scenes),
            "reflectance_sha256": sha256(path),
        }
    return totals


def checked_labels(raster, window, taxonomy):
    values = raster.read(1, window=window)
    validate_class_codes(values, taxonomy, nodata=taxonomy.nodata)
    return values


def training_samples(image, labels, grid, taxonomy):
    rng = np.random.default_rng(42)
    cap = 5000
    reservoirs = {code: (np.empty(0), np.empty((0, 6), dtype="float32")) for code in taxonomy.thematic_codes}
    for window in windows(grid):
        reflectance = image.read(window=window)
        label = checked_labels(labels, window, taxonomy)
        valid = np.isfinite(reflectance).all(axis=0)
        for code in np.unique(label[valid]):
            if code not in reservoirs:
                continue
            samples = reflectance[:, valid & (label == code)].T
            old_keys, old_samples = reservoirs[code]
            keys = np.concatenate([old_keys, rng.random(len(samples))])
            values = np.concatenate([old_samples, samples])
            selected = np.argpartition(keys, cap - 1)[:cap] if len(keys) > cap else slice(None)
            reservoirs[code] = keys[selected], values[selected]
    counts = {code: len(values) for code, (_, values) in reservoirs.items() if len(values) >= 4}
    if len(counts) < 2:
        raise ValueError("TRAINING_CLASSES_INSUFFICIENT")
    features = np.concatenate([reservoirs[code][1] for code in counts])
    expected = np.repeat(list(counts), list(counts.values()))
    return features, expected, counts


def predict_year(bundle, folder, output, grid, taxonomy, qc, input_sha):
    models = {}
    label_pin = bundle.training.raster
    label_path = label_pin.local(folder)
    domain = ClassificationDomain.from_taxonomy(taxonomy)
    for sensor in Bands:
        raw_sha = qc[sensor]["reflectance_sha256"]
        reflectance_path = output / f"{sensor}-reflectance.tif"
        if sha256(reflectance_path) != raw_sha:
            raise ValueError("NORMALIZED_REFLECTANCE_PIN_MISMATCH")
        fingerprint = hash_bytes(f"{input_sha}:{sensor}:{raw_sha}:{label_pin.sha256}".encode()).hexdigest()
        artifact = output / f"{sensor}-candidate.npz"
        classified = output / f"{sensor}-cover.tif"
        confidence = output / f"{sensor}-confidence.tif"
        with ExitStack() as stack:
            raster = stack.enter_context(rasterio.open(reflectance_path))
            labels = warp(stack, label_path, grid, nodata=taxonomy.nodata)
            samples, label_values, counts = training_samples(raster, labels, grid, taxonomy)
            fitted = fit_annual_forest(samples, label_values, domain, fingerprint, fixture=bundle.evidence == "synthetic")
            raw = fitted.artifact_bytes()
            artifact_sha = hash_bytes(raw).hexdigest()
            with atomic_output(artifact) as staged:
                staged.write_bytes(raw)
            fitted = load_artifact(artifact.read_bytes(), artifact_sha)
            # Close both GeoTIFFs before moving their staged files into place.
            cover_staged = stack.enter_context(atomic_output(classified))
            confidence_staged = stack.enter_context(atomic_output(confidence))
            cover = stack.enter_context(rasterio.open(cover_staged, "w", **raster_profile(grid, 1, "uint16", taxonomy.nodata)))
            uncertain = stack.enter_context(rasterio.open(confidence_staged, "w", **raster_profile(grid, 1, "float32", np.nan)))
            for window in windows(grid):
                labels, scores = fitted.predict_forest_reflectance(raster.read(window=window))
                cover.write(labels, 1, window=window)
                uncertain.write(scores, 1, window=window)
        models[sensor] = {
            "model": "random_forest", "samples": counts, "dataset_sha256": fingerprint,
            "model_sha256": artifact_sha, "cover_sha256": sha256(classified),
            "confidence_sha256": sha256(confidence),
        }
    return models


def compare(output, grid, taxonomy, geometry, *, reference=None, training=None):
    codes = taxonomy.thematic_codes
    encode = np.full(65536, -1, dtype=np.int32)
    encode[list(codes)] = np.arange(len(codes))
    matrices = {}
    available = 0
    with ExitStack() as stack:
        maps = {sensor: stack.enter_context(rasterio.open(output / f"{sensor}-cover.tif")) for sensor in Bands}
        if training:
            truth = stack.enter_context(rasterio.open(reference))
            if (truth.count != 1 or truth.crs != rasterio.crs.CRS.from_string(grid["crs"])
                or truth.transform != grid["transform"] or truth.nodata != taxonomy.nodata
                or truth.shape != (grid["height"], grid["width"])
                or np.dtype(truth.dtypes[0]).kind not in "ui"):
                raise ValueError("INDEPENDENT_GRID_MISMATCH")
        else:
            truth = warp(stack, reference, grid, nodata=taxonomy.nodata) if reference else None
        train = warp(stack, training, grid, nodata=taxonomy.nodata) if training else None
        for window in windows(grid):
            values = {sensor: raster.read(1, window=window) for sensor, raster in maps.items()}
            if truth:
                expected = checked_labels(truth, window, taxonomy)
                aoi = geometry_mask([geometry], expected.shape, transform(window, grid["transform"]), invert=True)
                eligible = np.isin(expected, codes) & aoi
                expected[~eligible] = taxonomy.nodata
                available += int(eligible.sum())
                if train and eligible.any():
                    validate_separation(train, eligible, window, grid, codes)
                pairs = {sensor: (expected, value) for sensor, value in values.items()}
            else:
                pairs = {"landsat_vs_sentinel-2": (values["sentinel-2"], values["landsat"])}
            for name, (left, right) in pairs.items():
                a, b = encode[left], encode[right]
                valid = (a >= 0) & (b >= 0)
                n = len(codes)
                matrix = matrices.setdefault(name, np.zeros((n, n), dtype=np.int64))
                matrix += np.bincount(a[valid] * n + b[valid], minlength=n * n).reshape(n, n)
    return {name: _metrics(matrix, codes) for name, matrix in matrices.items()}, available


def validate_separation(train, eligible, window, grid, codes):
    # A one-cell buffer checks neighbours across window borders without loading the full raster.
    row, col = int(window.row_off), int(window.col_off)
    bottom, right = row + int(window.height), col + int(window.width)
    top, left = max(0, row - 1), max(0, col - 1)
    padded = Window(left, top, min(grid["width"], right + 1) - left,
                    min(grid["height"], bottom + 1) - top)
    values = np.isin(train.read(1, window=padded), codes)
    padded_values = np.pad(values, 1)
    a, b = row - top + 1, col - left + 1
    h, w = eligible.shape
    if any((eligible & padded_values[a + dy:a + dy + h, b + dx:b + dx + w]).any()
           for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
        raise ValueError("INDEPENDENT_SAMPLES_OVERLAP_TRAINING_BUFFER")
