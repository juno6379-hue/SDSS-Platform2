"""Publish Banten Landsat display composites and observation support."""

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry import mapping
from shapely.ops import transform

from services.lcluc.annual_rasters import atomic_output, raster_profile
from services.lcluc.banten_esri_preview import INDEX, WEB
from services.lcluc.banten_optical_layers import pinned_window
from services.lcluc.banten_optical_qa import complete_years
from services.lcluc.banten_sentinel_explorer import (
    display_grid,
    receipt,
    rgba_index,
    rgba_rgb,
    write_png,
)
from services.lcluc.province_esri import SNAPSHOT_SHA256, write_json
from services.lcluc.province_optical_plan import boundary

ROOT = Path("data/curated/explorer/banten-province/landsat-explore")
BANDS = ("blue", "green", "red", "nir08", "swir16", "swir22")
PROFILES = {
    "LT04": (1, 2, 3, 4, 5, 7), "LT05": (1, 2, 3, 4, 5, 7),
    "LE07": (1, 2, 3, 4, 5, 7), "LC08": (2, 3, 4, 5, 6, 7), "LC09": (2, 3, 4, 5, 6, 7),
}
RGB = {"natural": (2, 1, 0), "agriculture": (4, 3, 0), "urban": (5, 4, 2), "swir": (5, 3, 2)}
INDICES = {"ndvi": (3, 2), "ndmi": (3, 4), "mndwi": (1, 4)}
LAYERS = (*RGB, *INDICES)
NAMES = (*BANDS, "CLEAR_OBSERVATIONS")
SCALE, OFFSET = 0.0000275, -0.2


def validate_band_metadata(platform, name, uri, bands):
    number = PROFILES[platform][BANDS.index(name)]
    expected_suffix = f"_SR_B{number}.TIF"
    if not uri.endswith(expected_suffix) or not bands or (bands[0].get("scale"), bands[0].get("offset")) != (SCALE, OFFSET):
        raise ValueError("LANDSAT_RADIOMETRY_OR_BAND_MISMATCH")


def quality_mask(platform, qa, saturation=None):
    # Bits 0/1/3/4/5: fill, dilated cloud, cloud, cloud shadow and snow.
    reject = 0b111011 | (0b100 if platform.startswith("LC") else 0)
    clear = (qa & reject) == 0
    if saturation is not None:
        clear &= saturation == 0
    return clear


def normalize(platform, bands, qa, footprint, saturation=None):
    if platform not in PROFILES or bands.shape[0] != len(BANDS):
        raise ValueError("UNSUPPORTED_LANDSAT_SENSOR_OR_BANDS")
    valid = footprint & (bands > 0).all(axis=0) & quality_mask(platform, qa, saturation)
    return np.where(valid, bands.astype("float32") * SCALE + OFFSET, np.nan)


def composite(scenes):
    cube = np.stack(scenes)
    observations = np.isfinite(cube[:, 0]).sum(axis=0)
    valid = observations > 0
    reflectance = np.full_like(cube[0], np.nan)
    reflectance[:, valid] = np.nanmedian(cube[:, :, valid], axis=0)
    return np.concatenate((reflectance, observations[None].astype("float32")))


def index_values(first, second):
    total = first + second
    return np.divide(first - second, total, out=np.full_like(total, np.nan), where=total > 0)


def context():
    grid = display_grid()
    shape = mapping(transform(WEB.transform, boundary()))
    mask = geometry_mask([shape], (grid["height"], grid["width"]), grid["transform"], invert=True)
    bounds = json.loads(INDEX.read_bytes())["bounds"]
    return grid, mask, bounds


def publish(key, data, grid, mask, bounds, sources, period):
    folder = ROOT / str(key)
    folder.mkdir(parents=True, exist_ok=True)
    raster = folder / "reflectance.tif"
    with atomic_output(raster) as staged, rasterio.open(
        staged, "w", **raster_profile(grid, len(NAMES), "float32", np.nan) | {"predictor": 3},
    ) as handle:
        handle.descriptions = NAMES
        handle.write(data)
    layers = {name: write_png(folder / f"{name}.png", rgba_rgb(data[list(channels)])) for name, channels in RGB.items()}
    layers.update({name: write_png(folder / f"{name}.png", rgba_index(index_values(data[a], data[b])))
                   for name, (a, b) in INDICES.items()})
    count = data[-1, mask]
    document = {
        "region": "banten", "boundary_sha256": SNAPSHOT_SHA256, "period": period, "bounds": bounds,
        "crs": str(grid["crs"]), "grid_spacing_m": [grid["transform"].a, -grid["transform"].e],
        "composite": "median_clear_scenes" if period[0] == period[1] else "median_of_annual_composites",
        "source": "USGS Landsat Collection 2 Level-2",
        "sources": sources, "clear_pct": 100 * float((count > 0).mean()),
        "two_observations_pct": 100 * float((count >= 2).mean()), "median_observations": float(np.median(count)),
        "layers": layers, "reflectance": receipt(raster),
    }
    write_json(folder / "manifest.json", document)
    print(key, round(document["clear_pct"], 2), "clear coverage %", flush=True)


def annual_local(year, entries, grid, mask, bounds):
    from contextlib import ExitStack

    expected_bands = set(BANDS) | {"qa_pixel"}
    scenes, sources = [], []
    vrt_grid = {key: value for key, value in grid.items() if key != "crs"}
    for path, _ in entries:
        scene = json.loads(path.read_bytes())
        scene_id = scene["scene"]
        platform = scene_id[:4]
        assets = scene["assets"]
        if set(assets) != expected_bands or not scene["observed_at"].startswith(str(year)):
            raise ValueError("LANDSAT_RECEIPT_SCOPE_MISMATCH")
        for name in BANDS:
            pin = assets[name]
            validate_band_metadata(platform, name, pin["uri"], pin["raster_bands"])
        with ExitStack() as stack:
            bands = np.stack([pinned_window(stack, assets[name], vrt_grid) for name in BANDS])
            qa = pinned_window(stack, assets["qa_pixel"], vrt_grid)
        scenes.append(normalize(platform, bands, qa, mask))
        sources.append({"scene": scene_id, "observed_at": scene["observed_at"], "receipt": receipt(path),
                        "band_numbers": PROFILES[platform], "qa_radsat": False})
    publish(year, composite(scenes), grid, mask, bounds, sources, [year, year])


def period_composite(start, end, grid, mask, bounds):
    sources, images, counts = [], [], []
    for year in range(start, end + 1):
        folder = ROOT / str(year)
        manifest = json.loads((folder / "manifest.json").read_bytes())
        pin = manifest["reflectance"]
        raster = Path(pin["path"])
        if receipt(raster) != pin:
            raise ValueError("LANDSAT_ANNUAL_ARTIFACT_CHANGED")
        with rasterio.open(raster) as handle:
            images.append(handle.read(list(range(1, 7))))
            counts.append(handle.read(7))
        sources.append({"year": year, "manifest": receipt(folder / "manifest.json")})
    data = composite(images)
    data[-1] = np.sum(counts, axis=0)
    publish(f"{start}-{end}", data, grid, mask, bounds, sources, [start, end])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", nargs="+", type=int)
    parser.add_argument("--period", nargs=2, type=int)
    args = parser.parse_args()
    grid, mask, bounds = context()
    if args.local:
        ready = complete_years()
        for year in args.local:
            annual_local(year, ready[year], grid, mask, bounds)
    if args.period:
        start, end = args.period
        if not 3 <= end - start + 1 <= 5:
            parser.error("a composite period must contain 3–5 annual years")
        period_composite(start, end, grid, mask, bounds)


if __name__ == "__main__":
    main()
