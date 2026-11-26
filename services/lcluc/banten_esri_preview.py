"""Create and serve display GeoTIFF derivatives of the Banten annual Esri layers."""

import json
from hashlib import sha256
from io import BytesIO
from math import ceil, floor
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling
from shapely.geometry import mapping
from shapely.ops import transform

from services.lcluc.province_esri import write_json

DIRECTORY = Path("data/curated/explorer/banten-province")
INDEX = DIRECTORY / "annual-display.json"
WEB = Transformer.from_crs(4326, 3857, always_xy=True)
WGS = Transformer.from_crs(3857, 4326, always_xy=True)


def publish_province_previews(geometry, sources, palette):
    """Build an aligned geographic preview without reducing analytical resolution."""
    web_geometry = transform(WEB.transform, geometry)
    minimum_x, minimum_y, maximum_x, maximum_y = web_geometry.bounds
    m = ceil(max(maximum_x - minimum_x, maximum_y - minimum_y) / 1280)
    x, y = m * floor(minimum_x / m), m * ceil(maximum_y / m)
    width, height = ceil((maximum_x - x) / m), ceil((y - minimum_y) / m)
    affine = from_origin(x, y, m, m)
    inside = geometry_mask(
        [mapping(web_geometry)], out_shape=(height, width), transform=affine, invert=True
    )
    west, south = WGS.transform(x, y - height * m)
    east, north = WGS.transform(x + width * m, y)
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    previous = json.loads(INDEX.read_bytes()) if INDEX.is_file() else {"years": {}}
    index = {
        "bounds": [west, south, east, north],
        "data_resolution_m": 10,
        "preview_resolution_map_m": m,
        "years": previous["years"],
    }
    for year, pin in sources.items():
        prior = index["years"].get(str(year))
        if prior and prior["source_sha256"] == pin["sha256"]:
            continue
        with (
            rasterio.open(pin["path"]) as src,
            WarpedVRT(
                src,
                crs="EPSG:3857",
                transform=affine,
                width=width,
                height=height,
                src_nodata=0,
                nodata=0,
                resampling=Resampling.nearest,
            ) as vrt,
        ):
            codes = vrt.read(1)
        img = np.zeros((height, width, 4), dtype=np.uint8)
        for code, color in palette.items():
            img[inside & (codes == code)] = tuple(bytes.fromhex(color[1:])) + (255,)
        content = BytesIO()
        Image.fromarray(img).save(content, format="PNG")
        data = content.getvalue()
        path = DIRECTORY / f"esri-{year}.png"
        tmp = path.with_suffix(".png.tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        index["years"][str(year)] = {
            "source_sha256": pin["sha256"],
            "bytes": len(data),
            "sha256": sha256(data).hexdigest(),
        }
    write_json(INDEX, index)
