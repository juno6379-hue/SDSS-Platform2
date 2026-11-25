"""Read-only acquisition checklist for the six-province GeoAI project."""

import json
from hashlib import sha256

from services.datahub.connectors.onemap.boundary import PROVINCES

from .evidence import EvidenceBlocked

YEARS = range(2020, 2026)
SENTINEL = "evidence/onemap_sentinel/"
KLHK_REPORT = "evidence/klhk_rag/verification-20261124.json"
VECTOR_INDEX = "evidence/vectorstore/climate-report-index-pinned.json"
BOUNDARY = SENTINEL + "audit-20261124/boundary/boundary.geojson"
PROVINCE_LABELS = dict(
    zip(
        PROVINCES,
        ("반텐", "서자바", "동자바", "고론탈로", "남술라웨시", "남동술라웨시"),
        strict=True,
    )
)


def measure(unit, expected, verified):
    """A missing scope or missing proof propagates to the ratio and remaining count."""
    comparable = expected is not None and verified is not None
    if comparable and not 0 <= verified <= expected:
        raise EvidenceBlocked("COLLECTION_PROGRESS_OUTSIDE_SCOPE")
    return {
        "unit": unit,
        "expected": expected,
        "verified": verified,
        "remaining": expected - verified if comparable else None,
        "percent": 100 * verified / expected if comparable and expected else None,
    }


def item(label, unit, expected, verified, note):
    return {"label": label, "measure": measure(unit, expected, verified), "note": note}


def collection(label, status, unit, expected, verified, scope, items):
    return {
        **item(label, unit, expected, verified, scope),
        "status": status,
        "items": items,
    }


def _sentinel(coverage, held):
    scope = {(province, year) for province in PROVINCES for year in YEARS}
    cells = {(row["province"], row["year"]): row for row in coverage["province_year_cells"]}
    patches = {(row["province"], row["year"]): row for row in held["cells"]}
    if (
        cells.keys() != scope
        or patches.keys() != scope
        or len(coverage["province_year_cells"]) != len(scope)
        or len(held["cells"]) != len(scope)
    ):
        raise EvidenceBlocked("COLLECTION_PROGRESS_SENTINEL_SCOPE_MISMATCH")
    expected = sum(cell["boundary_area_m2"] for cell in cells.values()) / 1e6
    present = sum(cell["simultaneous_present_area_m2"] for cell in cells.values()) / 1e6
    clear = sum(cell["clear_joint_area_m2"] for cell in cells.values()) / 1e6
    items = [
        item("유효 피복", "km²", expected, clear, "SCL 품질 조건을 통과한 면적"),
        item(
            "패치 하한 충족",
            "주·연도",
            len(scope),
            sum(
                p["manifest_quality_eligible"] >= p["minimum_patch_threshold"]
                for p in patches.values()
            ),
            f"셀당 {min(p['minimum_patch_threshold'] for p in patches.values())}개. 공간피복 기준은 별도.",
        ),
        item(
            "manifest 품질 적격 패치",
            "패치",
            None,
            coverage["quality_eligible_patches"],
            "동일 주·연도 내 표본 수. 학습 승인은 별도.",
        ),
    ]
    for province in PROVINCES:
        for year in YEARS:
            cell, patch = cells[province, year], patches[province, year]
            items.append(
                item(
                    f"{PROVINCE_LABELS[province]} {year}",
                    "km²",
                    cell["boundary_area_m2"] / 1e6,
                    cell["simultaneous_present_area_m2"] / 1e6,
                    f"유효 {cell['clear_joint_area_m2'] / 1e6:,.2f}km² · "
                    f"적격 패치 {patch['manifest_quality_eligible']}개 "
                    f"(하한 {patch['minimum_patch_threshold']}개)",
                )
            )
    return collection(
        "Sentinel-2 6밴드 + SCL",
        "VERIFIED_REAL",
        "km²",
        expected,
        present,
        f"6개 주 × 2020~2025년 경계 면적 합계. 동일 장면 {', '.join(coverage['pilot']['bands'])}.",
        items,
    )


def _one_map(store, held):
    path = store.safe_path(BOUNDARY)
    if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise EvidenceBlocked("COLLECTION_PROGRESS_BOUNDARY_MISSING")
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != held["source_pins"]["boundary"]:
        raise EvidenceBlocked("COLLECTION_PROGRESS_BOUNDARY_SHA_DRIFT")
    boundary = json.loads(raw)
    provinces = [feature["properties"]["province_id"] for feature in boundary["features"]]
    if len(provinces) != len(PROVINCES) or set(provinces) != set(PROVINCES):
        raise EvidenceBlocked("COLLECTION_PROGRESS_BOUNDARY_SCOPE_MISMATCH")
    authority = boundary["authority"]
    return collection(
        "One Map / BIG 주 경계",
        "VERIFIED_REAL",
        "주",
        len(PROVINCES),
        len(provinces),
        "주별 경계 스냅샷 확보. 승인 여부는 아래에 별도로 표시.",
        [item(PROVINCE_LABELS[p], "주", 1, 1, "해시 검증된 경계 스냅샷") for p in PROVINCES]
        + [
            item(
                "공식 통계 사용 승인",
                "스냅샷",
                1,
                int(authority["approved_for_project_statistics"]),
                f"출처 {authority['organization']} · 취득 {boundary['retrieved_at']}",
            )
        ],
    )


def _rtrw():
    return collection(
        "One Map / RTRW 용도지역",
        "BLOCKED",
        "주",
        len(PROVINCES),
        0,
        "6개 주별 유효 버전과 전체 공간범위를 검증한 원본 목록. SDSS-Platform2에서 검증된 원본 0건.",
        [
            item(PROVINCE_LABELS[p], "주", 1, 0, "지역 전체 원본·유효 버전·취득 근거 등록 필요")
            for p in PROVINCES
        ],
    )


def _klhk(store):
    report, _ = store.read_json("klhk", KLHK_REPORT)
    layers = {
        row["year"]: row
        for row in report["acquired_documents"]
        if row.get("year_verified") is True
        and row["source_id"].startswith("klhk-landcover-")
        and row["year"] in YEARS
    }
    return collection(
        "KLHK 연차 토지피복 원본",
        "BLOCKED",
        "연도",
        len(YEARS),
        0,
        "2020~2025 추적 목록. 23개 클래스 원본·재사용 허가를 검증한 연도 기준.",
        [
            item(
                "공식 연도 메타데이터 확인",
                "연도",
                len(YEARS),
                len(layers),
                "원본 확보 집계와 별도",
            )
        ]
        + [
            item(
                str(year),
                "연도",
                1,
                0,
                f"공식 메타데이터 확보 · {layers[year]['version']} · 원본·라이선스 미검증"
                if year in layers
                else "공식 연도 메타데이터와 원본 미확인",
            )
            for year in YEARS
        ],
    )


def _cckp(store, climate):
    query, _ = store.read_json("cckp", "evidence/cckp_indonesia/query-request.json")
    if climate["status"] != "VERIFIED_REAL":
        raise EvidenceBlocked("COLLECTION_PROGRESS_CLIMATE_SAMPLE_NOT_VERIFIED")
    return collection(
        "World Bank CCKP 기후 격자",
        "IMPLEMENTED_UNVERIFIED",
        "원본",
        None,
        1,
        "프로젝트 전체 변수·기간·시나리오별 취득 목록이 미확정.",
        [
            item(
                "검증된 개발 표본",
                "원본",
                1,
                1,
                f"{query['model'].upper()} {query['variable'].upper()} · "
                f"{query['time']['start'][:4]}~{query['time']['end'][:4]} · "
                "Indonesia 개발 bbox에서 재현한 NetCDF 격자",
            )
        ],
    )


def _reports(store, vector):
    report, _ = store.read_json("vector", VECTOR_INDEX)
    staged, _ = store.read_json("klhk", KLHK_REPORT)
    sources = {row["document_sha256"]: row for row in report["sources"]}
    documents = [row for row in staged["acquired_documents"] if row["sha256"] in sources]
    if len(documents) != len(sources) or len(sources) != vector["document_count"]:
        raise EvidenceBlocked("COLLECTION_PROGRESS_DOCUMENT_LIST_MISMATCH")
    return collection(
        "기후 문서 / VectorDB",
        "IMPLEMENTED_UNVERIFIED",
        "문서",
        None,
        len(documents),
        "전체 문서 목록 미확정. 확보 목록은 World Bank 문서·메타데이터와 KLHK 메타데이터.",
        [
            item(
                "로컬 검토 인덱스",
                "청크",
                None,
                vector["chunk_count"],
                "의미 검색 검증·접근 권한·라이선스 심사 대기",
            )
        ]
        + [
            item(
                row["source_id"],
                "문서",
                1,
                1,
                f"{sources[row['sha256']]['chunk_count']}청크 · {row['version']}",
            )
            for row in documents
        ],
    )


def snapshot(store, *, sentinel, climate, vector):
    """Return each source independently so a missing index cannot hide Sentinel metrics."""

    def held():
        return store.read_json("sentinel", SENTINEL + "held-audit-20261124/completeness.json")[0]

    sources = (
        ("sentinel", "Sentinel-2 6밴드 + SCL", "km²", None, lambda: _sentinel(sentinel(), held())),
        ("big", "One Map / BIG 주 경계", "주", len(PROVINCES), lambda: _one_map(store, held())),
        ("rtrw", "One Map / RTRW 용도지역", "주", len(PROVINCES), _rtrw),
        ("klhk", "KLHK 연차 토지피복 원본", "연도", len(YEARS), lambda: _klhk(store)),
        ("cckp", "World Bank CCKP 기후 격자", "원본", None, lambda: _cckp(store, climate())),
        ("documents", "기후 문서 / VectorDB", "문서", None, lambda: _reports(store, vector())),
    )
    datasets = []
    for source_id, label, unit, expected, read in sources:
        try:
            result = read()
        except EvidenceBlocked as error:
            result = collection(label, "BLOCKED", unit, expected, None, "증거를 확인할 수 없음", [])
            result["evidence_error"] = str(error)
        datasets.append({"id": source_id, **result})
    return {
        "status": "BLOCKED"
        if any("evidence_error" in row for row in datasets)
        else "VERIFIED_REAL",
        "scope": {"provinces": list(PROVINCES), "years": list(YEARS)},
        "datasets": datasets,
        "metrics_scope": "LOCAL_VERIFIED_EVIDENCE",
        "execution_started": False,
        "training_ready": False,
        "independent_accuracy_measured": False,
        "worldcover_2021_reference_year": 2021,
    }
