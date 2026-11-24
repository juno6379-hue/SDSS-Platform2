"""Shared, versioned contracts used across SDSS Platform 2 services."""

from .climate import (
    AccessPolicy,
    AssetLineage,
    CanonicalResult,
    ClimateQuery,
    EvidenceCitation,
    ObservationKind,
    QueryRoute,
    SpatialCoverage,
    TimeCoverage,
)

__all__ = [
    "AccessPolicy",
    "AssetLineage",
    "CanonicalResult",
    "ClimateQuery",
    "EvidenceCitation",
    "ObservationKind",
    "QueryRoute",
    "SpatialCoverage",
    "TimeCoverage",
]
