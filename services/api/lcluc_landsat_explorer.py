"""Read-only access to Banten's verified Landsat display products."""

import json
from functools import lru_cache
from io import BytesIO
from re import fullmatch

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, Response

from .lcluc_sentinel_explorer import _digest, _thumbnail
from .results import check_local

PREFIX = "/api/lcluc/banten-landsat"
ROOT = "data/curated/explorer/banten-province/landsat-explore"
HISTORY = "data/raw/explorer/province/banten-optical/historical-stac"


@lru_cache(maxsize=12)
def ndvi_change(first, second, _first_sha256, _second_sha256):
    import numpy as np
    import rasterio
    from PIL import Image

    from services.lcluc.banten_landsat_explorer import index_values
    from services.lcluc.banten_sentinel_explorer import rgba_categories

    with rasterio.open(first) as left, rasterio.open(second) as right:
        if (left.crs, left.transform, left.shape) != (right.crs, right.transform, right.shape):
            raise ValueError("LANDSAT_DISPLAY_GRID_MISMATCH")
        before = index_values(left.read(4), left.read(3))
        after = index_values(right.read(4), right.read(3))
    delta = after - before
    categories = np.zeros(delta.shape, dtype="uint8")
    categories[delta <= -0.20] = 1
    categories[delta >= 0.20] = 2
    image = rgba_categories(categories, {1: (231, 76, 43, 215), 2: (31, 161, 108, 215)})
    buffer = BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return buffer.getvalue()


def mount_landsat_explorer(app, store):
    def read(path):
        file = store.safe_path(path)
        if not file.is_file():
            raise HTTPException(404, detail="LANDSAT_ARTIFACT_PENDING")
        return json.loads(file.read_bytes())

    def manifest(key):
        if not fullmatch(r"(?:19\d{2}|20\d{2})(?:-(?:19\d{2}|20\d{2}))?", key):
            raise HTTPException(422, detail="LANDSAT_PERIOD_INVALID")
        return read(f"{ROOT}/{key}/manifest.json")

    def checked(pin):
        path = store.safe_path(pin["path"])
        try:
            stat = path.stat()
            if stat.st_size != pin["bytes"] or _digest(path, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) != pin["sha256"]:
                raise ValueError("Landsat pin mismatch")
        except (OSError, ValueError) as error:
            raise HTTPException(409, detail="LANDSAT_ASSET_INTEGRITY_FAILURE") from error
        return path

    @app.get(PREFIX)
    def catalog(request: Request):
        check_local(request)
        from services.lcluc.banten_landsat_explorer import PROFILES

        result = {"region": "banten", "annual": [], "periods": [], "archive_checks": [], "band_profiles": PROFILES}
        for file in sorted(store.safe_path(ROOT).glob("*/manifest.json")):
            item = manifest(file.parent.name)
            row = {name: item[name] for name in (
                "period", "clear_pct", "two_observations_pct", "median_observations", "grid_spacing_m", "bounds",
            )}
            row["key"], row["scenes"] = file.parent.name, [entry["scene"] for entry in item["sources"] if "scene" in entry]
            result["annual" if row["period"][0] == row["period"][1] else "periods"].append(row)
        for file in sorted(store.safe_path(HISTORY).glob("*.audit.json")):
            audit = read(f"{HISTORY}/{file.name}")
            result["archive_checks"].append({key: audit[key] for key in ("year", "state", "items_on_first_page")})
        return result

    @app.get(PREFIX + "/baseline")
    def baseline(request: Request):
        check_local(request)
        return read(f"{ROOT}/rf-report.json")

    @app.get(PREFIX + "/baseline/classification")
    def baseline_classification(request: Request):
        check_local(request)
        pin = read(f"{ROOT}/rf-report.json")["classification"]
        return FileResponse(checked(pin), media_type="image/tiff", filename="banten-2020-landsat-rf.tif")

    @app.get(PREFIX + "/products/{key}")
    def product(request: Request, key: str):
        check_local(request)
        return manifest(key)

    @app.get(PREFIX + "/products/{key}/{layer}")
    def layer_asset(request: Request, key: str, layer: str, thumbnail: bool = False):
        check_local(request)
        item = manifest(key)
        pin = item["reflectance"] if layer == "reflectance" else item["layers"].get(layer)
        if pin is None:
            raise HTTPException(404, detail="LANDSAT_LAYER_UNKNOWN")
        path = checked(pin)
        headers = {"X-Artifact-Sha256": pin["sha256"]}
        if layer == "reflectance":
            return FileResponse(path, media_type="image/tiff", filename=f"banten-landsat-{key}.tif", headers=headers)
        if thumbnail:
            return Response(_thumbnail(path, pin["sha256"]), media_type="image/png",
                            headers={"Cache-Control": "private, max-age=300"})
        return FileResponse(path, media_type="image/png", headers=headers)

    @app.get(PREFIX + "/change/{start}/{end}")
    def change(request: Request, start: int, end: int):
        check_local(request)
        if not 1982 <= start < end <= 2099:
            raise HTTPException(422, detail="LANDSAT_PERIOD_INVALID")
        before, after = (manifest(str(year))["reflectance"] for year in (start, end))
        response = ndvi_change(checked(before), checked(after), before["sha256"], after["sha256"])
        return Response(response, media_type="image/png")
