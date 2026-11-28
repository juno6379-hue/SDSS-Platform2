"""Immutable intake contracts for the annual optical pipeline."""

from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from services.datahub.connectors.onemap.boundary import sha256

Sensor = Literal["sentinel-2", "landsat"]
Sha = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Name = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")]
Bands = {
    "sentinel-2": ("B02", "B03", "B04", "B08", "B11", "B12"),
    "landsat": ("SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"),
}
Quality = {"sentinel-2": "SCL", "landsat": "QA_PIXEL"}
REGIONAL_OUTPUT = "data/curated/lcluc/regional-v1"
REGIONAL_RUN_SCHEMA = "sdss-regional-optical-run/1"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Pin(Input):
    path: str
    bytes: int = Field(gt=0)
    sha256: Sha

    def source_path(self, folder: Path) -> Path:
        path = PurePosixPath(self.path)
        if (
            path.is_absolute() or not path.parts or ".." in path.parts
            or "\\" in self.path or ":" in self.path
        ):
            raise ValueError("UNSAFE_ASSET_PATH")
        local = folder.joinpath(*path.parts).resolve()
        if not local.is_relative_to(folder.resolve()):
            raise ValueError("UNSAFE_ASSET_PATH")
        if not local.is_file() or local.stat().st_size < self.bytes:
            raise FileNotFoundError(self.path)
        if local.stat().st_size != self.bytes:
            raise ValueError("ASSET_LENGTH_MISMATCH")
        return local

    def local(self, folder: Path) -> Path:
        local = self.source_path(folder)
        if sha256(local) != self.sha256:
            raise ValueError("ASSET_PIN_MISMATCH")
        return local


class Provenance(Input):
    source_id: Name
    provider: Name
    uri: str = Field(min_length=1, max_length=500)
    version: str = Field(min_length=1, max_length=120)
    license: str = Field(min_length=1, max_length=160)
    acquired_at: datetime

    @model_validator(mode="after")
    def acquisition_timezone(self):
        if self.acquired_at.utcoffset() is None:
            raise ValueError("ACQUISITION_TIMEZONE_REQUIRED")
        return self


class Scene(Provenance):
    observed_on: date
    assets: dict[str, Pin]
    scale: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
    offset: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]


class Reference(Provenance):
    year: int = Field(ge=2017, le=2100)
    taxonomy_sha256: Sha
    raster: Pin


class AnnualBundle(Input):
    schema_version: Literal["lcluc-annual-input/1"]
    region: Name
    year: int = Field(ge=2017, le=2100)
    evidence: Literal["real", "synthetic"]
    taxonomy: Name
    taxonomy_sha256: Sha
    boundary: Pin  # WGS84 Polygon or MultiPolygon GeoJSON geometry.
    boundary_source: Provenance
    sensors: dict[Sensor, Annotated[list[Scene], Field(min_length=1, max_length=64)]]
    training: Reference | None = None

    @model_validator(mode="after")
    def same_year_products(self):
        if self.sensors.keys() != Bands.keys():
            raise ValueError("BOTH_OPTICAL_SENSORS_REQUIRED")
        for sensor, scenes in self.sensors.items():
            if len({scene.source_id for scene in scenes}) != len(scenes):
                raise ValueError("DUPLICATE_SCENE")
            for scene in scenes:
                expected = {*Bands[sensor], Quality[sensor]}
                if scene.assets.keys() not in (expected, expected | {"QA_RADSAT"}) or (
                    sensor != "landsat" and "QA_RADSAT" in scene.assets
                ):
                    raise ValueError("REQUIRED_BANDS_OR_QUALITY_MISSING")
                if scene.observed_on.year != self.year or min(scene.scale) <= 0:
                    raise ValueError("OBSERVATION_YEAR_OR_SCALE_INVALID")
                if sensor == "landsat" and (
                    scene.scale != (0.0000275,) * 6 or scene.offset != (-0.2,) * 6
                ):
                    raise ValueError("LANDSAT_C2_REFLECTANCE_SCALE_REQUIRED")
        if self.training:
            self.check_reference(self.training)
        return self

    def check_reference(self, reference: Reference):
        if reference.year != self.year or reference.taxonomy_sha256 != self.taxonomy_sha256:
            raise ValueError("REFERENCE_YEAR_OR_TAXONOMY_MISMATCH")


class TrainingAuthorization(Input):
    schema_version: Literal["lcluc-annual-training/1"]
    input_sha256: Sha
    approval_id: Name
    authority: Name


class Verification(Input):
    schema_version: Literal["lcluc-annual-verification/1"]
    input_sha256: Sha
    weak_reference: Reference | None = None
    independent_reference: Reference | None = None
    independent_protocol: Pin | None = None
    approval_id: Name | None = None
    authority: Name | None = None

    def check_independent(self, bundle: AnnualBundle):
        independent = self.independent_reference
        bundle.check_reference(independent)
        others = [reference for reference in (bundle.training, self.weak_reference) if reference]
        if (
            self.independent_protocol is None or self.approval_id is None or self.authority is None
            or any(
                independent.source_id == other.source_id or independent.provider == other.provider
                or independent.raster.sha256 == other.raster.sha256
                for other in others
            )
            or independent.provider in {
                "esri", "worldcover", "esa-worldcover", "impact-observatory", "dynamic-world"
            }
        ):
            raise ValueError("INDEPENDENT_REFERENCE_ATTESTATION_INVALID")


def receipt_bytes(path: Path) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("RECEIPT_EXCEEDS_SIZE_LIMIT")
    return data
