"""CCKP: 전역 sync 없이 목록에 존재하는 객체만 제한적으로 취급한다.

국가·변수·기간이 목록/메타데이터로 입증되지 않으면 원본 계획부터 차단한다.
이 모듈은 기후 수치 해석이나 CF/QC/관측-전망 분류를 수행하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

BUCKET = "wbg-cckp"
ENDPOINT = "https://wbg-cckp.s3.amazonaws.com"
OFFICIAL_DOCUMENTATION = "https://github.com/worldbank/climateknowledgeportal"
MAX_LIST_BYTES = 256 * 1024
MAX_FILES = 20
MAX_TRANSFER_BYTES = 64 * 1024 * 1024
MAX_OBJECT_BYTES = 32 * 1024 * 1024


class CckpError(ValueError):
    """범위·출처·원본 무결성을 만족하지 못한 요청."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def _key(value: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not empty) or len(value) > 1024:
        raise CckpError("INVALID_S3_KEY")
    if value.startswith("/") or "\\" in value or any(x in value for x in ("?", "#")):
        raise CckpError("INVALID_S3_KEY")
    if any(p in (".", "..") for p in value.split("/")) or any(ord(c) < 32 for c in value):
        raise CckpError("INVALID_S3_KEY")
    return value


def _integer(value: int, low: int, high: int, label: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise CckpError(label)
    return value


@dataclass(frozen=True)
class ObjectRecord:
    key: str
    size: int
    etag: str
    last_modified: str


@dataclass(frozen=True)
class Inventory:
    bucket: str
    prefix: str
    prefixes: tuple[str, ...]
    objects: tuple[ObjectRecord, ...]
    response_sha256: str
    source_uri: str
    acquired_at: str
    truncated: bool
    continuation_token: str | None
    response_xml: str

    @property
    def inventory_id(self) -> str:
        return digest(_canonical(asdict(self)))


@dataclass(frozen=True)
class CountryScope:
    # 식별자 이름만으로 Indonesia 매핑을 주장하지 않는다. 공식 국가명 매핑은 별도 Gate다.
    identifier: str
    exact_listed_prefix: str
    listing_inventory_id: str
    listing: Inventory


@dataclass(frozen=True)
class DownloadPlan:
    country_id: str
    country_scope: CountryScope
    variable: str
    start_year: int
    end_year: int
    max_files: int
    max_bytes: int
    inventory: Inventory
    objects: tuple[ObjectRecord, ...]
    license: str
    trace_id: str
    version: str = "cckp-bounded-raw/1.0"

    @property
    def plan_id(self) -> str:
        return digest(_canonical(asdict(self)))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CckpError("REDIRECT_NOT_ALLOWED")


class S3Transport:
    """정확한 공개 bucket host·TLS·timeout·본문 상한; redirect와 자동 retry 없음."""

    def __init__(self, timeout: float = 15):
        if not 0 < timeout <= 30:
            raise CckpError("INVALID_TIMEOUT")
        self.timeout = timeout

    def __call__(self, method: str, url: str, headers: dict, limit: int) -> tuple[int, dict, bytes]:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "wbg-cckp.s3.amazonaws.com"
            or parsed.fragment
        ):
            raise CckpError("SOURCE_HOST_NOT_ALLOWED")
        if method not in ("GET", "HEAD"):
            raise CckpError("METHOD_NOT_ALLOWED")
        _integer(limit, 0, MAX_TRANSFER_BYTES, "RESPONSE_LIMIT_INVALID")
        request = Request(url, method=method, headers={"User-Agent": "SDSS-CCKP/1.0", **headers})
        with build_opener(_NoRedirect()).open(request, timeout=self.timeout) as response:
            data = response.read(limit + 1)
            if len(data) > limit:
                raise CckpError("RESPONSE_BODY_LIMIT_EXCEEDED")
            return response.status, {k.lower(): v for k, v in response.headers.items()}, data


def discover(
    prefix: str = "",
    *,
    max_keys: int = 10,
    parent: Inventory | None = None,
    transport: Callable | None = None,
) -> Inventory:
    """단일 delimiter 페이지만 조회한다. truncated이어도 자동 전역 순회하지 않는다."""
    prefix = _key(prefix, empty=True)
    if prefix and (parent is None or parent.bucket != BUCKET or prefix not in parent.prefixes):
        raise CckpError("PREFIX_NOT_PREVIOUSLY_LISTED")
    if parent is not None:
        _validate_inventory(parent)
    _integer(max_keys, 1, 100, "MAX_KEYS_OUT_OF_RANGE")
    url = (
        ENDPOINT
        + "/?"
        + urlencode({"list-type": "2", "prefix": prefix, "delimiter": "/", "max-keys": max_keys})
    )
    status, headers, raw = (transport or S3Transport())("GET", url, {}, MAX_LIST_BYTES)
    if status != 200 or len(raw) > MAX_LIST_BYTES:
        raise CckpError("LIST_RESPONSE_INVALID")
    # XML DTD/entity를 허용하지 않는다. 크기 제한은 transport와 parser 양쪽에서 검사한다.
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise CckpError("XML_ENTITY_NOT_ALLOWED")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise CckpError("LIST_XML_INVALID") from exc
    ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
    if root.tag != "{http://s3.amazonaws.com/doc/2006-03-01/}ListBucketResult":
        raise CckpError("LIST_ROOT_INVALID")
    if (
        root.findtext("s:Name", namespaces=ns) != BUCKET
        or (root.findtext("s:Prefix", namespaces=ns) or "") != prefix
    ):
        raise CckpError("LIST_SCOPE_MISMATCH")
    prefixes = tuple(
        _key(x.findtext("s:Prefix", namespaces=ns) or "")
        for x in root.findall("s:CommonPrefixes", ns)
    )
    records = []
    for item in root.findall("s:Contents", ns):
        key = _key(item.findtext("s:Key", namespaces=ns) or "")
        try:
            size = int(item.findtext("s:Size", namespaces=ns) or "-1")
        except ValueError as exc:
            raise CckpError("LIST_SIZE_INVALID") from exc
        if size < 0 or not key.startswith(prefix):
            raise CckpError("LIST_OBJECT_SCOPE_INVALID")
        records.append(
            ObjectRecord(
                key,
                size,
                item.findtext("s:ETag", namespaces=ns) or "",
                item.findtext("s:LastModified", namespaces=ns) or "",
            )
        )
    if len(prefixes) + len(records) > max_keys or len(set(prefixes)) != len(prefixes):
        raise CckpError("LIST_RESULT_LIMIT_OR_DUPLICATE")
    if len({r.key for r in records}) != len(records) or any(
        not p.startswith(prefix) for p in prefixes
    ):
        raise CckpError("LIST_OBJECT_SCOPE_INVALID")
    return Inventory(
        BUCKET,
        prefix,
        prefixes,
        tuple(records),
        digest(raw),
        url,
        datetime.now(timezone.utc).isoformat(),
        root.findtext("s:IsTruncated", namespaces=ns) == "true",
        root.findtext("s:NextContinuationToken", namespaces=ns),
        raw.decode("utf-8"),
    )


def _validate_inventory(listing: Inventory) -> None:
    """확인 목록을 수정한 뒤 확인된 것처럼 사용하는 계약 drift를 차단한다."""
    raw = listing.response_xml.encode("utf-8")
    if len(raw) > MAX_LIST_BYTES or digest(raw) != listing.response_sha256:
        raise CckpError("INVENTORY_RAW_PIN_MISMATCH")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise CckpError("XML_ENTITY_NOT_ALLOWED")
    root = ET.fromstring(raw)
    ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
    prefixes = tuple(
        x.findtext("s:Prefix", namespaces=ns) for x in root.findall("s:CommonPrefixes", ns)
    )
    records = tuple(
        ObjectRecord(
            x.findtext("s:Key", namespaces=ns),
            int(x.findtext("s:Size", namespaces=ns)),
            x.findtext("s:ETag", namespaces=ns) or "",
            x.findtext("s:LastModified", namespaces=ns) or "",
        )
        for x in root.findall("s:Contents", ns)
    )
    if (
        listing.bucket != BUCKET
        or root.findtext("s:Name", namespaces=ns) != BUCKET
        or (root.findtext("s:Prefix", namespaces=ns) or "") != listing.prefix
        or listing.prefixes != prefixes
        or listing.objects != records
    ):
        raise CckpError("INVENTORY_CONTENT_DRIFT")


def inventory_from_dict(value: dict) -> Inventory:
    """자체 receipt의 목록을 복원한다. 외부 CCKP 국가 API schema를 가정하지 않는다."""
    fields = {
        **value,
        "prefixes": tuple(value["prefixes"]),
        "objects": tuple(ObjectRecord(**x) for x in value["objects"]),
    }
    listing = Inventory(**fields)
    _validate_inventory(listing)
    return listing


def head_object(inventory: Inventory, key: str, *, transport: Callable | None = None) -> dict:
    """목록에 실제 있는 객체의 HEAD만 허용한다. 이름 추측/본문 다운로드는 하지 않는다."""
    _validate_inventory(inventory)
    records = [x for x in inventory.objects if x.key == key]
    if len(records) != 1:
        raise CckpError("HEAD_KEY_NOT_LISTED")
    record = records[0]
    url = ENDPOINT + "/" + quote(_key(key), safe="/")
    status, headers, body = (transport or S3Transport())("HEAD", url, {"If-Match": record.etag}, 0)
    if (
        status != 200
        or body
        or headers.get("etag") != record.etag
        or headers.get("content-length") != str(record.size)
    ):
        raise CckpError("HEAD_LISTING_DRIFT")
    return {
        "status": "VERIFIED_REAL_HEAD_ONLY",
        "source_uri": "s3://" + BUCKET + "/" + key,
        "size": record.size,
        "etag": record.etag,
        "downloaded_body_bytes": 0,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "inventory_id": inventory.inventory_id,
    }


def confirm_country_scope(listing: Inventory, identifier: str, exact_prefix: str) -> CountryScope:
    """목록에 실제 반환된 국가 prefix만 고정한다. /IND 등의 문자열을 만들어 검색하지 않는다."""
    _validate_inventory(listing)
    if not re.fullmatch(r"[A-Z0-9_-]{2,16}", identifier) or exact_prefix not in listing.prefixes:
        raise CckpError("COUNTRY_IDENTIFIER_NOT_LISTED")
    if not exact_prefix.endswith("/") or exact_prefix.rstrip("/").rsplit("/", 1)[-1] != identifier:
        raise CckpError("COUNTRY_IDENTIFIER_NOT_LISTED")
    return CountryScope(identifier, exact_prefix, listing.inventory_id, listing)


def plan_download(
    inventory: Inventory,
    scope: CountryScope,
    *,
    country_id: str,
    variable: str,
    start_year: int,
    end_year: int,
    max_files: int,
    max_bytes: int,
    license: str,
    trace_id: str,
) -> DownloadPlan:
    """실제 country prefix·변수 segment·명시 기간 파일만 선택한다. global sync는 없다."""
    _integer(start_year, 1800, 2300, "YEAR_INVALID")
    _integer(end_year, start_year, 2300, "YEAR_INVALID")
    _integer(max_files, 1, MAX_FILES, "FILE_LIMIT_INVALID")
    _integer(max_bytes, 1, MAX_TRANSFER_BYTES, "BYTE_LIMIT_INVALID")
    if (
        inventory.bucket != BUCKET
        or not inventory.response_sha256
        or not scope.listing_inventory_id
    ):
        raise CckpError("INVENTORY_PROOF_REQUIRED")
    _validate_inventory(inventory)
    if confirm_country_scope(scope.listing, scope.identifier, scope.exact_listed_prefix) != scope:
        raise CckpError("COUNTRY_PROOF_DRIFT")
    if country_id != scope.identifier or not inventory.prefix.startswith(scope.exact_listed_prefix):
        raise CckpError("COUNTRY_SCOPE_UNVERIFIED_GLOBAL_SYNC_FORBIDDEN")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", variable):
        raise CckpError("VARIABLE_REQUIRED")
    if not license.strip() or license.upper() in ("UNKNOWN", "TBD") or not trace_id.strip():
        raise CckpError("LICENSE_AND_TRACE_REQUIRED")
    selected = []
    for item in inventory.objects:
        _key(item.key)
        if not item.key.startswith(scope.exact_listed_prefix) or variable not in item.key.split(
            "/"
        ):
            continue
        period = re.search(r"_(\d{4})-(\d{4})\.nc$", item.key)
        if not period:
            continue
        lo, hi = map(int, period.groups())
        # 요청보다 넓은 파일을 내려받아 국가/기간 제한을 만족했다고 가장하지 않는다.
        if not start_year <= lo <= hi <= end_year:
            continue
        if (
            type(item.size) is not int
            or not 0 < item.size <= MAX_OBJECT_BYTES
            or not re.fullmatch(r'"[A-Za-z0-9_-]+"', item.etag)
        ):
            raise CckpError("OBJECT_SIZE_OR_ETAG_INVALID")
        selected.append(item)
    if not selected:
        raise CckpError("NO_VERIFIED_SCOPED_OBJECTS")
    if len(selected) > max_files or sum(x.size for x in selected) > max_bytes:
        raise CckpError("PLAN_FILE_OR_BYTE_BUDGET_EXCEEDED")
    if len({x.key for x in selected}) != len(selected):
        raise CckpError("DUPLICATE_OBJECT_KEY")
    return DownloadPlan(
        country_id,
        scope,
        variable,
        start_year,
        end_year,
        max_files,
        max_bytes,
        inventory,
        tuple(selected),
        license,
        trace_id,
    )


def _write(path: Path, value: dict, *, exclusive: bool = False) -> None:
    if path.is_symlink():
        raise CckpError("ARTIFACT_SYMLINK_NOT_ALLOWED")
    data = _canonical(value) + b"\n"
    if exclusive:
        with path.open("xb") as handle:
            handle.write(data)
    else:
        tmp = path.with_suffix(path.suffix + ".tmp")
        if tmp.is_symlink():
            raise CckpError("ARTIFACT_SYMLINK_NOT_ALLOWED")
        with tmp.open("wb") as handle:
            handle.write(data)
        os.replace(tmp, path)


def download(
    plan: DownloadPlan, root: Path, *, execute: bool = False, transport: Callable | None = None
) -> dict:
    """원본 취득 opt-in. immutable receipt, ETag 조건부 재개, 중복·누적 예산을 강제한다."""
    validated = plan_download(
        plan.inventory,
        plan.country_scope,
        country_id=plan.country_id,
        variable=plan.variable,
        start_year=plan.start_year,
        end_year=plan.end_year,
        max_files=plan.max_files,
        max_bytes=plan.max_bytes,
        license=plan.license,
        trace_id=plan.trace_id,
    )
    if validated != plan:
        raise CckpError("PLAN_CONTENT_DRIFT")
    if not execute:
        return {
            "status": "PLANNED",
            "plan_id": plan.plan_id,
            "files": len(plan.objects),
            "listed_bytes": sum(x.size for x in plan.objects),
            "download_executed": False,
        }
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    state_path, lock_path = root / "transfer-state.json", root / ".execution.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        state = (
            json.loads(state_path.read_text(encoding="utf-8"))
            if state_path.exists()
            else {"plan_id": plan.plan_id, "charged_upper_bound_bytes": 0, "partial": {}}
        )
        if state["plan_id"] != plan.plan_id:
            raise CckpError("DIFFERENT_PLAN_REQUIRES_SEPARATE_LEDGER")
        _integer(state["charged_upper_bound_bytes"], 0, plan.max_bytes, "PERSISTED_BUDGET_INVALID")
        if state.get("rate_limit_active"):
            raise CckpError("PERSISTED_RATE_LIMIT_CIRCUIT_ACTIVE")
        receipts = []
        for item in plan.objects:
            name = digest(item.key.encode())
            final, part, receipt_path = (
                root / (name + ".nc"),
                root / (name + ".part"),
                root / (name + ".receipt.json"),
            )
            if any(path.is_symlink() for path in (final, part, receipt_path)):
                raise CckpError("ARTIFACT_SYMLINK_NOT_ALLOWED")
            if final.exists() and receipt_path.exists():
                if state.get("receipt_pins", {}).get(name) != digest(receipt_path.read_bytes()):
                    raise CckpError("IMMUTABLE_RECEIPT_PIN_MISMATCH")
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                expected = {
                    "plan_id": plan.plan_id,
                    "source_uri": "s3://" + BUCKET + "/" + item.key,
                    "etag": item.etag,
                    "country_id": plan.country_id,
                    "variable": plan.variable,
                    "license": plan.license,
                    "trace_id": plan.trace_id,
                }
                if (
                    any(receipt.get(k) != v for k, v in expected.items())
                    or receipt["sha256"] != digest(final.read_bytes())
                    or final.stat().st_size != item.size
                ):
                    raise CckpError("EXISTING_RECEIPT_OR_RAW_DRIFT")
                receipts.append(receipt)
                continue
            if final.exists() or receipt_path.exists():
                raise CckpError("ORPHAN_RAW_OR_RECEIPT_REQUIRES_REVIEW")
            prior = state["partial"].get(name)
            offset = part.stat().st_size if part.exists() else 0
            if offset and (
                not prior or prior["sha256"] != digest(part.read_bytes()) or prior["size"] != offset
            ):
                raise CckpError("PARTIAL_PIN_MISMATCH")
            if offset >= item.size:
                raise CckpError("PARTIAL_SIZE_REQUIRES_REVIEW")
            remaining = item.size - offset
            if state["charged_upper_bound_bytes"] + remaining > plan.max_bytes:
                raise CckpError("PERSISTENT_TRANSFER_BUDGET_EXCEEDED")
            # 측정할 수 없는 중단은 예약액을 남긴다. 재시작했다고 원장을 초기화하지 않는다.
            state["charged_upper_bound_bytes"] += remaining
            _write(state_path, state)
            url = ENDPOINT + "/" + quote(item.key, safe="/")
            try:
                status, headers, body = (transport or S3Transport())(
                    "GET",
                    url,
                    {"If-Match": item.etag, "Range": f"bytes={offset}-{item.size - 1}"},
                    remaining,
                )
            except HTTPError as exc:
                state["last_http_status"] = exc.code
                state["retry_after"] = exc.headers.get("Retry-After") if exc.headers else None
                state["rate_limit_active"] = exc.code == 429
                _write(state_path, state)
                raise
            if status == 429:
                state.update(
                    rate_limit_active=True,
                    last_http_status=429,
                    retry_after=headers.get("retry-after"),
                )
                _write(state_path, state)
                raise CckpError("HTTP_429_STOPPED")
            if headers.get("etag") != item.etag or len(body) != remaining:
                raise CckpError("OBJECT_ETAG_OR_BODY_LENGTH_MISMATCH")
            if status == 206:
                if headers.get("content-range") != f"bytes {offset}-{item.size - 1}/{item.size}":
                    raise CckpError("CONTENT_RANGE_MISMATCH")
            elif status != 200 or offset != 0:
                raise CckpError("RANGE_IGNORED_OR_HTTP_ERROR")
            running = hashlib.sha256(part.read_bytes() if offset else b"")
            with part.open("ab" if offset else "xb") as handle:
                for start in range(0, len(body), 64 * 1024):
                    block = body[start : start + 64 * 1024]
                    handle.write(block)
                    handle.flush()
                    running.update(block)
                    state["partial"][name] = {"size": handle.tell(), "sha256": running.hexdigest()}
                    _write(state_path, state)
            raw_sha = running.hexdigest()
            # link는 기존 원본을 덮어쓰지 않는다. crash orphan은 위에서 자동 차단한다.
            os.link(part, final)
            receipt = {
                "schema_version": "cckp-raw-receipt/1.0",
                "plan_id": plan.plan_id,
                "dataset_id": "cckp-object:" + name,
                "source_id": BUCKET,
                "source_uri": "s3://" + BUCKET + "/" + item.key,
                "inventory_id": plan.inventory.inventory_id,
                "listing_sha256": plan.inventory.response_sha256,
                "etag": item.etag,
                "etag_is_sha256": False,
                "sha256": raw_sha,
                "bytes": item.size,
                "country_id": plan.country_id,
                "variable": plan.variable,
                "requested_period": [plan.start_year, plan.end_year],
                "license": plan.license,
                "version": item.etag,
                "acquired_at": datetime.now(timezone.utc).isoformat(),
                "trace_id": plan.trace_id,
                "raw_path": str(final),
                "status": "RAW_NOT_QC_VALIDATED",
                "observed_or_projected": None,
                "model": None,
                "scenario": None,
                "unit": None,
                "calendar": None,
                "grid": None,
                "crs": None,
                "derived_from": [],
            }
            receipt["available_at"] = receipt["acquired_at"]
            receipt["next_gate"] = "CLIM_METADATA_MISSING"
            _write(receipt_path, receipt, exclusive=True)
            state.setdefault("receipt_pins", {})[name] = digest(receipt_path.read_bytes())
            _write(state_path, state)
            part.unlink()
            receipts.append(receipt)
        return {
            "status": "RAW_RECEIPTS_WRITTEN_NOT_QC_VALIDATED",
            "receipts": receipts,
            "charged_upper_bound_bytes": state["charged_upper_bound_bytes"],
        }
    finally:
        os.close(fd)
        lock_path.unlink()
