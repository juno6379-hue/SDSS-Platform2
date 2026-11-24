"""공식 CCKP 목록을 고정하고 제한된 원본 취득을 계획하는 커넥터."""

from .source import (
    CckpError,
    CountryScope,
    DownloadPlan,
    Inventory,
    ObjectRecord,
    S3Transport,
    confirm_country_scope,
    discover,
    download,
    plan_download,
)

__all__ = [
    "CckpError",
    "Inventory",
    "ObjectRecord",
    "CountryScope",
    "DownloadPlan",
    "S3Transport",
    "discover",
    "confirm_country_scope",
    "plan_download",
    "download",
]
