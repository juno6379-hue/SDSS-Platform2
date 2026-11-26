"""Pinned LCLUC class definitions, raster validation and reviewed crosswalk contracts."""

import json
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from numbers import Real
from pathlib import Path
from typing import Literal
from unicodedata import normalize

from services.datahub.connectors.klhk.source import KLHK_CODES, classify_metadata

_DATA_DIR = Path(__file__).with_name("taxonomies")
_TAXONOMY_DIGESTS = {
    "klhk-23": "bf4eb70aeb2572dacad95410edad68e74376f82408437244514799370db183bc",
    "legacy-9": "3429335b49cf3566a826dd4c69351b02bcddac5951d414c9f0e4a75a159c82df",
    "esri-io-v003": "2e2084401ffc7830c3b567fce99eca2d29f37df8d98f1e0cfa36c3cbb25ab76c",
}
_CROSSWALK_DIGESTS = {
    "klhk-23-to-legacy-9": "c624582ededebd8e0eddb713d91ca483f6903bdd92f836ded734e80300e37f74",
}


class TaxonomyError(ValueError):
    """Stable failure for an unrecognized or unpinned LCLUC class definition."""


@dataclass(frozen=True, slots=True)
class LandCoverClass:
    code: int
    label: str
    name_ko: str
    role: Literal["land_cover", "quality_mask"]


@dataclass(frozen=True, slots=True)
class TaxonomySource:
    uri: str
    verification_uri: str | None
    authority: str
    checked_on: str
    license: str
    raw_metadata_sha256: str
    raw_metadata_bytes: int


@dataclass(frozen=True, slots=True)
class Taxonomy:
    id: str
    version: str
    sha256: str
    classes: tuple[LandCoverClass, ...]
    nodata: int
    evidence_status: str
    approval_status: str
    source: TaxonomySource
    _analysis_groups: tuple[tuple[str, tuple[int, ...]], ...]

    @property
    def codes(self) -> tuple[int, ...]:
        return tuple(entry.code for entry in self.classes)

    @property
    def thematic_codes(self) -> tuple[int, ...]:
        return tuple(entry.code for entry in self.classes if entry.role == "land_cover")

    @property
    def qa_codes(self) -> tuple[int, ...]:
        return tuple(entry.code for entry in self.classes if entry.role == "quality_mask")

    @property
    def analysis_groups(self) -> dict[str, tuple[int, ...]]:
        """Return a copy of the registered project interpretation of grouped classes."""
        return dict(self._analysis_groups)


@dataclass(frozen=True, slots=True)
class Crosswalk:
    id: str
    version: str
    sha256: str
    source: Taxonomy
    target: Taxonomy
    entries: tuple[tuple[int, int | None], ...]
    evidence_status: str
    approval_status: str

    @property
    def excluded_codes(self) -> tuple[int, ...]:
        return tuple(
            source_code for source_code, target_code in self.entries if target_code is None
        )


def _load_pinned(identifier, digests, expected_sha256, schema_version):
    digest = digests.get(identifier) if isinstance(identifier, str) else None
    if digest is None:
        raise TaxonomyError("LCLUC_CLASS_DEFINITION_UNREGISTERED")
    if expected_sha256 is not None and digest != expected_sha256:
        raise TaxonomyError("LCLUC_CLASS_DEFINITION_SHA256_MISMATCH")
    try:
        data = (_DATA_DIR / f"{identifier}.json").read_bytes()
    except OSError as error:
        raise TaxonomyError("LCLUC_CLASS_DEFINITION_FILE_UNAVAILABLE") from error
    if sha256(data).hexdigest() != digest:
        raise TaxonomyError("LCLUC_CLASS_DEFINITION_FILE_TAMPERED")
    document = json.loads(data)
    if (document.get("id"), document.get("schema_version")) != (identifier, schema_version):
        raise TaxonomyError("LCLUC_CLASS_DEFINITION_SCHEMA_INVALID")
    return document, digest


def load_taxonomy(
    taxonomy_id: str = "klhk-23",
    expected_sha256: str | None = None,
    *,
    require_approved: bool = False,
) -> Taxonomy:
    """Read an immutable definition. Annual asset approval stays separate from its class names."""
    document, digest = _load_pinned(
        taxonomy_id, _TAXONOMY_DIGESTS, expected_sha256, "land-cover-taxonomy/1"
    )
    entries = tuple(LandCoverClass(**entry) for entry in document["classes"])
    codes = tuple(entry.code for entry in entries)
    if (
        tuple(sorted(set(codes))) != codes
        or (taxonomy_id == "klhk-23" and frozenset(codes) != KLHK_CODES)
        or document["nodata"] in codes
        or any(entry.role not in ("land_cover", "quality_mask") for entry in entries)
    ):
        raise TaxonomyError("LCLUC_CLASS_DEFINITION_DOMAIN_INVALID")
    if require_approved and document["approval_status"] != "APPROVED":
        raise TaxonomyError("LCLUC_TAXONOMY_OPERATIONAL_APPROVAL_REQUIRED")
    return Taxonomy(
        id=taxonomy_id,
        version=document["version"],
        sha256=digest,
        classes=entries,
        nodata=document["nodata"],
        evidence_status=document["evidence_status"],
        approval_status=document["approval_status"],
        source=TaxonomySource(**document["source"]),
        _analysis_groups=tuple(
            (group, tuple(group_codes))
            for group, group_codes in document["analysis_groups"].items()
        ),
    )


def _checked_nodata(nodata, taxonomy) -> int:
    import numpy as np

    # Rasterio supplies integer raster NoData as a float. Fractional and nonfinite values
    # have no defined class semantics in this contract.
    if (
        isinstance(nodata, (bool, np.bool_))
        or not isinstance(nodata, Real)
        or not isfinite(nodata)
        or not -(2**31) <= nodata < 2**31
        or int(nodata) != nodata
        or nodata in taxonomy.codes
    ):
        raise TaxonomyError("LCLUC_NODATA_INVALID_OR_COLLIDES_WITH_CLASS")
    return int(nodata)


def validate_class_codes(values, taxonomy: Taxonomy, *, nodata=None):
    """Validate visible values and return their Boolean presence mask.

    A declared QA class is present here. Apply a separate QA exclusion to thematic analysis.
    An input NumPy mask or explicit, non-conflicting NoData is respected.
    """
    import numpy as np

    data = np.ma.getdata(values)
    if data.dtype.kind not in "iuf":
        raise TaxonomyError("LCLUC_CLASS_VALUES_MUST_BE_NUMERIC")
    valid = ~np.ma.getmaskarray(values)
    if nodata is not None:
        valid = valid & (data != _checked_nodata(nodata, taxonomy))
    if not np.isin(data[valid], taxonomy.codes).all():
        raise TaxonomyError("LCLUC_CLASS_CODE_UNREGISTERED")
    return valid


def load_crosswalk(
    crosswalk_id: str = "klhk-23-to-legacy-9",
    expected_sha256: str | None = None,
    *,
    require_approved: bool = False,
) -> Crosswalk:
    """Read a crosswalk bound to both class dictionary hashes."""
    document, digest = _load_pinned(
        crosswalk_id, _CROSSWALK_DIGESTS, expected_sha256, "land-cover-crosswalk/1"
    )
    source = load_taxonomy(document["source_taxonomy_id"], document["source_taxonomy_sha256"])
    target = load_taxonomy(document["target_taxonomy_id"], document["target_taxonomy_sha256"])
    entries = tuple((row["source_code"], row["target_code"]) for row in document["mapping"])
    if (
        tuple(code for code, _ in entries) != source.codes
        or any(
            target_code is not None and target_code not in target.thematic_codes
            for _, target_code in entries
        )
        or any(code in source.qa_codes and target_code is not None for code, target_code in entries)
    ):
        raise TaxonomyError("LCLUC_CROSSWALK_INVALID_OR_INCOMPLETE")
    if require_approved and document["approval_status"] != "APPROVED":
        raise TaxonomyError("LCLUC_CROSSWALK_OPERATIONAL_APPROVAL_REQUIRED")
    return Crosswalk(
        id=crosswalk_id,
        version=document["version"],
        sha256=digest,
        source=source,
        target=target,
        entries=entries,
        evidence_status=document["evidence_status"],
        approval_status=document["approval_status"],
    )


def apply_crosswalk(
    values,
    crosswalk: Crosswalk,
    *,
    source_nodata=None,
    target_nodata=None,
    allow_provisional: bool = False,
):
    """Convert to analysis codes using a pinned mapping; explicit exclusions become NoData."""
    import numpy as np

    if crosswalk.approval_status != "APPROVED" and not allow_provisional:
        raise TaxonomyError("LCLUC_CROSSWALK_OPERATIONAL_APPROVAL_REQUIRED")
    valid = validate_class_codes(values, crosswalk.source, nodata=source_nodata)
    missing = _checked_nodata(
        crosswalk.target.nodata if target_nodata is None else target_nodata, crosswalk.target
    )
    dtype = np.int32 if missing < 0 else np.min_scalar_type(max(missing, *crosswalk.target.codes))
    result = np.full(valid.shape, missing, dtype=dtype)
    remapped = np.array(
        [missing if target is None else target for _, target in crosswalk.entries], dtype=dtype
    )
    result[valid] = remapped[np.searchsorted(crosswalk.source.codes, np.ma.getdata(values)[valid])]
    return result


def _semantic_label(text: str) -> str:
    return " ".join(normalize("NFKC", text).casefold().replace("/", " ").split())


def inspect_klhk_annual_metadata(payload, year: int) -> dict:
    """Assess published annual layer metadata without setting use or license approval."""
    if type(year) is not int or not 1900 <= year <= 2100:
        raise TaxonomyError("LCLUC_ANNUAL_YEAR_INVALID")
    taxonomy = load_taxonomy()
    inspected = classify_metadata(payload, year)
    expected = {entry.code: _semantic_label(entry.label) for entry in taxonomy.classes}
    labels_match = (
        inspected.get("native_23_class_schema_verified", False)
        and {entry["code"]: _semantic_label(entry["name"]) for entry in inspected["class_codes"]}
        == expected
    )
    reasons = list(inspected["reasons"])
    if inspected.get("native_23_class_schema_verified") and not labels_match:
        reasons.append("KLHK_ANNUAL_CODE_LABEL_MISMATCH")
    reasons.append("KLHK_ANNUAL_LAYER_OPERATIONAL_APPROVAL_UNVERIFIED")
    return {
        **inspected,
        "status": "BLOCKED",
        "metadata_contract_valid": inspected.get("metadata_contract_valid", False) and labels_match,
        "taxonomy_sha256": taxonomy.sha256,
        "official_label_match": labels_match,
        "approval_status": "BLOCKED",
        "reasons": reasons,
    }
