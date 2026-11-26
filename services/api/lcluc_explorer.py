"""Serve the fixed local Explorer observation pairs and their pinned source bundles."""

from datetime import date
from typing import Literal

from fastapi import HTTPException, Request, Response
from pydantic import Field, ValidationError

from services.results.catalog import Pin, Strict

from .evidence import EvidenceBlocked
from .results import check_local

INDEX = "data/curated/explorer/imagery-index.json"
SeriesName = Literal["sentinel-2", "landsat", "disaster"]
FrameName = Literal["earlier", "later"]
AssetName = Literal["preview", "bundle"]


class Observation(Strict):
    observed_on: date
    scene: str
    preview: Pin
    bundle: Pin
    preview_type: Literal["image/png", "image/jpeg"]


class Series(Strict):
    id: SeriesName
    region: str
    title: str
    attribution: str
    scope: str
    earlier: Observation
    later: Observation


class Index(Strict):
    series: list[Series] = Field(max_length=3)


def mount_explorer_imagery(app, store, read_asset):
    def series():
        path = store.safe_path(INDEX)
        try:
            with path.open("rb") as source:
                raw = source.read(65537)
            if len(raw) > 65536:
                raise ValueError("Index is too large")
            return Index.model_validate_json(raw).series
        except FileNotFoundError:
            return []
        except (OSError, ValidationError, ValueError) as error:
            raise HTTPException(409, detail="LCLUC_IMAGERY_INDEX_INVALID") from error

    @app.get("/api/lcluc/imagery")
    def inventory(request: Request):
        check_local(request)
        entries = []
        for item in series():
            entry = item.model_dump(mode="json", exclude={"earlier", "later"})
            for frame in ("earlier", "later"):
                observation = getattr(item, frame)
                prefix = f"/api/lcluc/imagery/{item.id}/{frame}"
                entry[frame] = {
                    "observed_on": observation.observed_on.isoformat(),
                    "scene": observation.scene,
                    "preview": prefix + "/preview",
                    "bundle": prefix + "/bundle",
                }
            entries.append(entry)
        return {"series": entries}

    @app.get("/api/lcluc/imagery/{series_id}/{frame}/{asset}")
    def imagery_asset(request: Request, series_id: SeriesName, frame: FrameName, asset: AssetName):
        check_local(request)
        entry = next((item for item in series() if item.id == series_id), None)
        if entry is None:
            raise HTTPException(404, detail="LCLUC_IMAGERY_NOT_REGISTERED")
        observation = getattr(entry, frame)
        pin = getattr(observation, asset)
        if pin.bytes > 24 * 1024**2:
            raise HTTPException(409, detail="LCLUC_IMAGERY_ASSET_TOO_LARGE")
        try:
            raw = read_asset(store, pin.model_dump())
        except (EvidenceBlocked, OSError) as error:
            raise HTTPException(409, detail="LCLUC_IMAGERY_ASSET_INTEGRITY") from error
        if asset == "preview":
            return Response(raw, media_type=observation.preview_type)
        filename = f"{series_id}-{observation.observed_on.isoformat()}.zip"
        return Response(raw, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        })
