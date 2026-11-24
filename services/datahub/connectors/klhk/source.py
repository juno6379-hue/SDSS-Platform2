"""고정된 공식 URL만 제한적으로 읽고 원본·실패 근거를 보존한다."""

import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

HOSTS = frozenset(
    {
        "geoportal.menlhk.go.id",
        "spatial.phl.menlhk.go.id",
        "geoportal.planologi.kehutanan.go.id",
        "sigap.kehutanan.go.id",
        "api.github.com",
        "raw.githubusercontent.com",
    }
)
DICTIONARY = "https://sigap.kehutanan.go.id/tema-kamus/575"
KLHK_CODES = frozenset(
    {
        2001,
        2002,
        2004,
        20041,
        2005,
        20051,
        2006,
        2007,
        20071,
        20091,
        20092,
        20093,
        20094,
        20122,
        2010,
        2012,
        20121,
        2014,
        20141,
        5001,
        50011,
        3000,
        2500,
    }
)
YEAR_URLS = {
    2021: "https://geoportal.menlhk.go.id/server/rest/services/SIGAP_Interaktif/Penutupan_Lahan_2021/MapServer?f=pjson",
    2022: "https://geoportal.menlhk.go.id/server/rest/services/SIGAP_Interaktif/Penutupan_Lahan_2022/MapServer?f=pjson",
    2023: "https://spatial.phl.menlhk.go.id/portal/sharing/rest/content/items/bee8de9b99384ba2b66a911329d2fe98/data?f=json",
    2024: "https://geoportal.planologi.kehutanan.go.id/server/rest/services/Peta_Interaktif_2026/PL2024_AR_50K/MapServer/0?f=pjson",
    2025: "https://geoportal.planologi.kehutanan.go.id/server/rest/services/Peta_Interaktif_2026/PL_AR_250K/MapServer/0?f=pjson",
}


def now():
    return datetime.now(timezone.utc).isoformat()


class Blocked(ValueError):
    pass


def check_url(url):
    value = urlsplit(url)
    if (
        value.scheme != "https"
        or value.hostname not in HOSTS
        or value.username
        or value.password
        or value.port not in (None, 443)
        or value.fragment
    ):
        raise Blocked("URL_NOT_OFFICIAL_ALLOWLIST")
    prefix = "/repos/worldbank/climateknowledgeportal"
    if value.hostname == "api.github.com" and not (
        value.path == prefix or value.path.startswith(prefix + "/")
    ):
        raise Blocked("REPOSITORY_NOT_ALLOWLISTED")
    if value.hostname == "raw.githubusercontent.com" and not value.path.startswith(
        "/worldbank/climateknowledgeportal/"
    ):
        raise Blocked("REPOSITORY_NOT_ALLOWLISTED")
    if any(key in value.query.casefold() for key in ("token=", "key=", "password=")):
        raise Blocked("SECRET_QUERY_FORBIDDEN")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Blocked("REDIRECT_NOT_FOLLOWED")


class BoundedTransport:
    evidence_status = "VERIFIED_REAL"

    def __init__(
        self, max_requests=12, max_bytes=2 * 1024 * 1024, per_document=256 * 1024, timeout=8
    ):
        if not (
            1 <= max_requests <= 16
            and 1 <= per_document <= 512 * 1024
            and per_document <= max_bytes <= 4 * 1024 * 1024
            and 0 < timeout <= 15
        ):
            raise ValueError("요청·byte·timeout 상한 초과")
        self.max_requests, self.max_bytes, self.per_document, self.timeout = (
            max_requests,
            max_bytes,
            per_document,
            timeout,
        )
        self.requests = self.bytes = 0
        self.rate_limited = False

    def fetch(self, url):
        check_url(url)
        if self.rate_limited or self.requests >= self.max_requests or self.bytes >= self.max_bytes:
            raise Blocked("BUDGET_OR_RATE_LIMIT_STOP")
        self.requests += 1
        # 크기 초과 탐지용 한 byte도 총 전송 상한 안에 예약한다.
        limit = min(self.per_document, self.max_bytes - self.bytes - 1)
        if limit < 1:
            raise Blocked("TOTAL_BUDGET_EXHAUSTED")
        request = Request(
            url,
            headers={
                "User-Agent": "SDSS-Platform2-bounded-metadata/0.1",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=self.timeout) as response:
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > limit:
                    raise Blocked("DECLARED_DOCUMENT_TOO_LARGE")
                raw = response.read(limit + 1)
                self.bytes += len(raw)
                if len(raw) > limit:
                    raise Blocked("DOCUMENT_TOO_LARGE")
                return raw, {
                    key: response.headers.get(key)
                    for key in ("Content-Type", "ETag", "Last-Modified")
                }
        except HTTPError as error:
            self.rate_limited = error.code == 429
            raise Blocked(f"HTTP_{error.code}") from error
        except Blocked:
            raise
        except Exception as error:
            raise Blocked("SOURCE_REQUEST_FAILED:" + type(error).__name__) from error


class ImmutableStore:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)

    def _commit_once(self, path, blob):
        temporary = self.directory / (path.name + ".tmp-" + uuid4().hex)
        try:
            with temporary.open("xb") as stream:
                stream.write(blob)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)

    def preserve(
        self,
        url,
        raw,
        headers,
        *,
        version,
        source_id,
        license_status="NOT_VERIFIED",
        evidence_status="IMPLEMENTED_UNVERIFIED",
    ):
        check_url(url)
        if not raw or not version or not source_id:
            raise ValueError("원본·버전·source ID 필요")
        digest = sha256(raw).hexdigest()
        identity = sha256((url + "\n" + digest).encode()).hexdigest()
        raw_path = self.directory / (identity + ".raw")
        receipt_path = self.directory / (identity + ".receipt.json")
        receipt = dict(
            schema_version="source-document-receipt/1.0",
            source_id=source_id,
            source_uri=url,
            version=version,
            sha256=digest,
            byte_count=len(raw),
            acquired_at=now(),
            license=license_status,
            authority_status="HOST_PINNED_NOT_INSTITUTION_CERTIFIED",
            headers=headers,
            raw_path=str(raw_path),
            state=evidence_status,
            retrieval_permitted=False,
        )
        self._commit_once(raw_path, raw)
        if raw_path.read_bytes() != raw:
            raise Blocked("IMMUTABLE_RAW_MISMATCH")
        # raw가 먼저 보존되고 receipt는 한 번만 배타 생성한다. 불완전 raw-only는 ingestion하지 않는다.
        self._commit_once(receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2).encode())
        previous = json.loads(receipt_path.read_text(encoding="utf-8"))
        if any(
            previous.get(key) != receipt[key]
            for key in (
                "source_uri",
                "sha256",
                "version",
                "source_id",
                "byte_count",
                "license",
                "state",
            )
        ):
            raise Blocked("IMMUTABLE_RECEIPT_MISMATCH")
        return previous


def classify_metadata(payload, year):
    """접근성·연도·native domain·라이선스를 각각 확인하고 하나라도 없으면 차단한다."""
    errors = []
    if not isinstance(payload, dict) or payload.get("error"):
        return {"status": "BLOCKED", "reasons": ["INVALID_OR_DENIED_METADATA"]}
    name = str(payload.get("name", ""))
    year_verified = str(year) in name and ("PL" in name.upper() or "LAHAN" in name.upper())
    if not year_verified:
        errors.append("YEAR_NOT_VERIFIED_IN_LAYER_METADATA")
    fields = payload.get("fields", [])
    fields = fields if isinstance(fields, list) else []
    domains = [
        field
        for field in fields
        if isinstance(field, dict)
        and str(year) in str(field.get("name", ""))
        and isinstance(field.get("domain"), dict)
        and isinstance(field["domain"].get("codedValues"), list)
    ]
    domain = next((field for field in domains if len(field["domain"]["codedValues"]) == 23), None)
    codes = domain["domain"]["codedValues"] if domain else []
    class_verified = (
        len(codes) == 23
        and all(
            isinstance(v, dict)
            and type(v.get("code")) is int
            and isinstance(v.get("name"), str)
            and v["name"].strip()
            for v in codes
        )
        and {v.get("code") for v in codes} == KLHK_CODES
    )
    if not class_verified:
        errors.append("NATIVE_23_CLASS_DOMAIN_NOT_VERIFIED")
    license_value = payload.get("licenseInfo")
    if not isinstance(license_value, str) or not license_value.strip():
        errors.append("LICENSE_NOT_VERIFIED")
    if payload.get("type") != "Feature Layer":
        errors.append("FEATURE_LAYER_NOT_VERIFIED")
    if "Query" not in str(payload.get("capabilities", "")).split(","):
        errors.append("QUERY_CAPABILITY_NOT_VERIFIED")
    return {
        "status": "BLOCKED" if errors else "IMPLEMENTED_UNVERIFIED",
        "metadata_contract_valid": not errors,
        "year": year,
        "year_verified": year_verified,
        "native_23_class_schema_verified": class_verified,
        "class_field": domain["name"] if domain else None,
        "class_codes": codes,
        "license": license_value,
        "license_use_approved": False,
        "reasons": errors,
        "download_access_verified": False,
        "institution_authority_certified": False,
    }


def discover(year, transport, store):
    if year not in YEAR_URLS:
        return {"status": "BLOCKED", "year": year, "reasons": ["YEAR_ENDPOINT_NOT_DISCOVERED"]}
    url = YEAR_URLS[year]
    try:
        raw, headers = transport.fetch(url)
        receipt = store.preserve(
            url,
            raw,
            headers,
            version="metadata-sha256:" + sha256(raw).hexdigest(),
            source_id=f"klhk-landcover-{year}",
            evidence_status=transport.evidence_status,
        )
        result = classify_metadata(json.loads(raw), year)
        payload = json.loads(raw)
        candidates = []
        payload = payload if isinstance(payload, dict) else {}
        for layer in payload.get("operationalLayers") or []:
            if not isinstance(layer, dict):
                continue
            candidate = layer.get("url")
            if candidate:
                check_url(candidate)
                candidates.append(
                    {"url": candidate, "basis": "explicit_webmap_metadata", "queried": False}
                )
        for layer in payload.get("layers") or []:
            if not isinstance(layer, dict):
                continue
            if type(layer.get("id")) is int and layer["id"] >= 0:
                parsed = urlsplit(url)
                candidate = urlunsplit(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path + "/" + str(layer["id"]),
                        "f=pjson",
                        "",
                    )
                )
                candidates.append(
                    {
                        "url": candidate,
                        "name": layer.get("name"),
                        "basis": "explicit_service_layer_id",
                        "queried": False,
                    }
                )
        result["discovered_layers"] = candidates
        result.update(source_uri=url, receipt=receipt)
        if result.get("metadata_contract_valid"):
            result["status"] = receipt["state"]
        return result
    except (Blocked, ValueError, UnicodeError) as error:
        return {"status": "BLOCKED", "year": year, "source_uri": url, "reasons": [str(error)]}
