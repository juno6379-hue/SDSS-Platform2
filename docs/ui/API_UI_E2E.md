# 로컬 API·대시보드 통합 검증

작성일: 2026-11-24. 담당 범위: `services/api/`, `web/`, `tests/api_ui/`, 이 문서.

## 상태와 실행

2026-11-26 Edge 5175의 **연차 토지피복도 → Esri·MapBiomas 원본별 면적**에서 Esri 9행과 MapBiomas 11행, 차이 열 제거, 2020·2024 연도 전환을 확인했다. API에서 2024년 경계·분류 유효·발행 합계와 비공통연도 422를 확인했다. [Edge 시험](../../artifacts/lcluc/banten-native-area-edge.log) · [면적 계약과 공식 참조 조건](../lcluc/BANTEN_MAPBIOMAS_AREA_COMPARISON.md)

2026-11-26 Edge 5175에서 LCLUC 반텐의 **Landsat → AI 모델 비교**, **Sentinel-2 → AI 신규 분류**로 전환했다. 센서별 세 모델의 약한 참조 지표와 GeoTIFF 6개를 확인했다. Toolbox에서 두 DeepLabv3+ 후보의 후처리를 실행했고 각각 동일한 전·후 평가 표본을 확인했다. [Edge 시험](../../artifacts/lcluc/banten-deeplab-area-edge.log) · [모델 계약](../lcluc/BANTEN_MODEL_TRIALS.md)

2026-11-26 Edge 5175의 **GeoLLM Assistant → MapBiomas Indonesia 지식 검색**에서 P0 9건 포함 14개 원문의 검색 및 공식 PDF·웹 인용을 확인했다. **후처리 및 품질관리**에서 RF와 Tiny U-Net 동일 표본 비교, Tiny U-Net 공간 필터 Swipe, Sentinel-2 Siamese 전·후 결과, 계층 통합의 동년 라벨·레이어 대기 표기를 확인했다. [통합 Edge 실행](../../artifacts/lcluc/banten-models-knowledge-edge.log) · [GeoLLM 계약](../lcluc/MAPBIOMAS_GEOLLM_KNOWLEDGE.md) · [모델 계약](../lcluc/BANTEN_MODEL_TRIALS.md)

2026-11-26 **GeoAI Toolbox → 후처리 및 품질관리**와 기존 LCLUC 제목 바로가기에서 실제 반텐 Spatial Filter 시험을 실행했다. Edge에서 이력 조회, 원본·보정본 Swipe, 보정 마스크, 클래스 면적표, 같은 표본의 약한 참조 비교 및 GeoTIFF 3개의 SHA-256 일치를 확인했다. API는 후보·실행 ID 계약과 409 입력/무결성 오류를 제공한다. [UI·API 계약](../lcluc/POSTPROCESS_QUALITY.md) · [Edge 실행](../../artifacts/lcluc/lcluc-postprocess-edge.log)

2026-11-26 React Edge 5175의 기존 LCLUC **반텐 → 지도 자료 → Landsat**에서 분광 프리셋 7종과 두 시점 ΔNDVI의 실제 PNG 요청, 관측 품질표, MapBiomas 장기 통계, Random Forest 약한 참조 근거를 확인했다. 기존 지도 폭은 886.95px다. `GET /api/lcluc/banten-landsat`의 `annual`이 스와이프·재생 연도, `periods`가 다년 합성 자료를 공급한다. `LANDSAT_ARTIFACT_PENDING`은 아직 발행되지 않은 자료, `LANDSAT_ASSET_INTEGRITY_FAILURE`는 고정 파일 검증 실패다. React 5175에서 포트 8014 API를 조회해 1990↔2020 스와이프와 1990→2000→2010→2020 재생 프레임을 확인했다. [데이터·API 계약](../lcluc/LANDSAT_EXPLORER.md) · [Edge 시험](../../artifacts/lcluc/landsat-explorer-edge-final.log)

2026-11-26 React Edge 5175의 기존 LCLUC **반텐 → 지도 자료 → Sentinel-2 L2A**에서 기존 지도 폭, 오른쪽·하단의 여섯 카드와 상단 항목의 카드 이동을 검증했다. 스와이프 T1·T2는 상단 연도 필터, 양쪽 지도 및 AOI API·면적·전이에 반영된다. 전이 PNG는 표시용 해상도, 면적은 Esri 10m 기준이다. AI 신규 분류는 실자료 연차 작업과 GeoTIFF 링크를 연결한다. MapBiomas 발행 주 통계와 2021 Esri↔WorldCover 지도 일치도에는 각 범위와 연도가 표시된다. [조작과 API 계약](../lcluc/SENTINEL_EXPLORER.md) · [Edge 클릭 시험](../../artifacts/lcluc/sentinel-workspace-final-edge.log)

API와 정적 반응형 화면이 구현되었다. 2026-11-25 재감사 버전은 8011에서 Edge로 확인했다. TestClient와 브라우저 검증 근거는 아래에 별도로 기록한다.

2026-11-25 공통 결과 검토는 `http://127.0.0.1:8014/#results`의 **리포트 & RDTR → 결과 검토**에서 제공한다. 실제 Edge와 임시 SQLite에서 고정 증거 등록 → 수정 요청 → 검토 완료 → 필터·새로고침 후 재조회를 확인했다. 실제 프로젝트 원장에서는 10건이 검토 대기 상태다. [등록·검토 API와 병렬 담당](../architecture/COMMON_RESULT_PATH.md)

화면은 기존 GeoAI–MLOps–SDSS의 `SDSSChrome.tsx`, `PlatformShell.tsx`, `sdss-chrome.css` 기준으로 청색 헤더와 7개 업무 메뉴, 현재 위치와 세부 탭을 사용한다. `web/sdss-reference.png`는 원본 UI 참조 그림에서 헤더 로고와 사이드바 사진 구간만 CSS로 표시한다. 대시보드 건수와 결과 상세는 실제 8014 응답을 사용한다. 기존 해시 링크는 동일하며, 메뉴를 바꿀 때 활성 작업화면만 표시한다. 결과 검토의 왼쪽 목록에서 분야·검토 상태를 필터링하고, 아래 **고정 증거 등록**에서 등록한다. 오른쪽 상세에서 근거 SHA, 차단 사유, 검토 이력을 확인한다. 좁은 화면에서는 목록과 상세를 위아래로 배치한다.

화면 구조 반영 뒤 `tests/api_ui` 24건을 통과했다. 8014의 실제 결과 10건, RTRW 상세, 데이터 카탈로그 세부 탭을 Edge 1440px와 390px에서 확인했다. 5174는 응답하지 않아 레거시 비교는 해당 저장소 코드와 기존 참조 화면을 기준으로 했다.

Playwright를 설치한 환경에서 `SDSS_BROWSER_E2E=1`, `SDSS_BROWSER_CHANNEL=msedge`, `SDSS_UI_BASE=http://127.0.0.1:8014`를 설정해 `tests/api_ui/test_browser_e2e.py`, `test_results_browser.py`, `test_live_results.py`를 실행했다. 실제 Edge 5건과 DOM 계약 시험 2건이 통과했다.

프로젝트 루트 `E:\SDSS-Platform2`에서 실행한다.

```powershell
python -m uvicorn services.api.app:app --host 127.0.0.1 --port 8011
# 브라우저: http://127.0.0.1:8011/#sentinel
python -m pytest tests/api_ui -q --junitxml=tests/api_ui/results.xml
python -m ruff check services/api tests/api_ui
python -m ruff format --check services/api tests/api_ui
node --check web/app.js
```

정적 HTML/CSS/JavaScript이며 Node 빌드·패키지 다운로드가 필요 없다. FastAPI/uvicorn 및 프로젝트 Python 의존성은 공통 환경을 사용한다. 화면과 API는 동일 origin이다. API 응답은 no-store, 화면은 외부 리소스 없이 CSP self를 적용한다. 입력으로 파일 경로·원격 URL·사용자 역할을 받을 수 없다.

## 불변 증거·실패 조건

`services/api/evidence-lock-v2.json`에 검토한 상대 경로·SHA·시각·7일 유효기간을 기록하고 `pinned.py`의 lock SHA와 대조한다. 매 요청마다 해당 그룹의 모든 파일을 재해시한다. 누락·변경·기한 만료·미래 시각·루트 밖 경로는 HTTP 409, BLOCKED, value=null로 반환한다. 기존 8010 프로세스는 이전 lock과 시험 전 집계를 읽고, 새 집계는 8011에서 제공한다.

재고 증거가 변경되면 자동으로 새 SHA를 신뢰하지 않는다. 변경 내용을 검토한 뒤에만 아래 명령으로 pin을 갱신하고 서버를 재시작한다.

```powershell
python -m services.api.evidence --pin-reviewed
```

이 명령 자체는 독립 정확도·기관 승인·라이선스 승인이 아니다. 시험의 actual_store는 검토 시각+1분으로 시계를 고정하여 역사적 snapshot을 재현한다. 운영 API는 현재 UTC 시각을 검사한다. 진행 중 Sentinel 최종 고정 증거가 변경되면 409가 올바른 동작이며 최종 결과를 자동 추정하지 않는다.

## 기능·API·클릭 계약

| 기능 | API | data-testid / 기대 동작 |
|---|---|---|
| 시스템 | GET /api/health | health-check, health-output, connection-state: 로컬 프로세스 범위만 정상 |
| 고정 CCKP | GET /api/cckp | cckp-load, cckp-output, cckp-value, cckp-unit: SHA 확인된 고정 값 표시; 실패 시 이전 숫자 제거 |
| 수치 재현 | GET /api/climate/contract, POST /api/climate/query | climate-contract, climate-request, climate-run, climate-output: typed JSON 검증 후 고정 NetCDF 로컬 재계산 |
| KLHK | GET /api/klhk | klhk-load, klhk-output: 실제 공식 metadata와 23-class/license blocker 분리 |
| RAG | POST /api/rag/search | rag-question, rag-search, rag-output: 익명 허용 curated index 없으면 BLOCKED, 인용 생성 안 함 |
| VectorDB | GET /api/vector | vector-status, vector-output: DB SHA·실제 count·dim/model/private 상태만 읽기 |
| 보고서 검색 | POST /api/reports/search | report-search, report-output: 인증 없는 private index 검색 금지 |
| Sentinel | GET /api/sentinel | sentinel-load, sentinel-output: 최종 BLOCKED_COLLECTION_NOT_COMPLETE; 감사·CAS 이관 완료와 수집 미완료 구분 |
| 수집 현황 | GET /api/collection-progress | collection-load: 출처별 목표·확보·미확보·진행률 및 상세. 미확정 목표나 누락 증거는 숫자 대신 상태 표시 |
| 모델 | GET /api/models | models-load, models-output: readiness 및 legacy checkpoint 감사, 실제 독립 성능 null |
| 실행 gate | GET /api/gates | gates-load, gates-output, training-blocker, deployment-blocker: 제안 정책과 차단 이유 |
| 학습·배포 | POST /api/actions/{action} | training-execute, deployment-execute: disabled; 직접 요청도 409, execution_started=false |
| Workflow | GET /api/workflow | workflow-load, workflow-output: 증거 검사 단계와 실제 persisted state 구분 |
| 공통 결과 | GET /api/results/sources, GET·POST /api/results, GET /api/results/{id}, POST /api/results/{id}/reviews | results-refresh, results-register, result-request-changes, result-accept: 증거와 검토 상태, 버전 충돌과 이력을 따로 표시 |

CCKP 예시 질문은 ERA5 observed CDD, 1951–1980, days, bbox [95,-11,141,6]의 면적 가중 격자 통계다. 고정 재현값 40.91221481742199 days는 공식 인도네시아 행정경계 평균·미래 전망·Sentinel 10m 관측이 아니다. 화면의 숫자는 서버 응답만 사용한다. RAG에 정량 기후 질문을 보내면 climate.query로 라우팅하고 answer=null/citations=[]를 유지한다.

## 실제·합성·차단 증거의 구분

- VERIFIED_REAL: 고정 CCKP 원본·receipt·license evidence SHA 확인과 로컬 수치 재현. 외부 요청 0.
- VERIFIED_REAL(무결성 범위): 공식 bounded 문서 receipt 및 VectorDB 파일/행 개수 확인. 기관 authority 인증이나 embedding 품질 인증은 아니다.
- VectorDB: `data/curated/vector/climate_reports_pinned.sqlite3`, manifest `evidence/vectorstore/climate-report-index-pinned.json`, SHA `2400a6e7e1cf4eef73a6d4aa07c1f1aee77a2e5d829ae0a09396de20ddc2a4e4`; 7 docs/122 chunks, dim64, synthetic-hash-64-v1. readonly immutable SQLite로 개수만 조회한다. pgvector SQL은 존재하지만 실제 PostgreSQL 배포는 미검증이다.
- BLOCKED: private data_steward 문서의 license/retrieval 미승인, public_search=false, steward 인증 미구현. 역할 문자열을 클라이언트가 보내도 권한 상승하지 않는다. 실제 문서 ingestion과 합성 hash-vector 품질을 분리한다.
- BLOCKED: KLHK 공식 endpoint 접근 성공과 별개로 renderer 25종을 검증된 23-class 코드 domain으로 대체하지 않는다. license/publication/기관 인증 미완료.
- BLOCKED: `evidence/models/readiness.json`과 `legacy-checkpoint-audit.json`. 기존 체크포인트 SHA 검사가 성공해도 3밴드/9클래스와 6밴드/23클래스 계약 차이, 독립 정확도·재현 환경 미충족으로 실행 불가다. weak reference는 독립 accuracy가 아니다.
- VERIFIED_REAL(감사·로컬 이관 범위): 최종 감사 4개 및 pilot 3개 JSON을 고정한다. 36/36 셀 exact 감사, physical 1779 / quality eligible 1407 / parent 119, 동시 6밴드+동일 scene SCL 피복 0.9767414314%, clear 0.8898034033%. 최소 패치 수 충족과 전체 공간피복은 다르다. 전체 수집 completion=false, 상태 BLOCKED_COLLECTION_NOT_COMPLETE이다. CAS 6125개/3,904,601,927 bytes 이관은 기존 로컬 파일 복사이며 신규 수집이 아니다. pilot 이전 감사·이관의 원격 다운로드는 0이다. 이후 검증된 단일 pilot의 원격 요청량은 별도 pilot 항목으로 표시한다. 전역 수집 승인과 별도로 bounded pilot만 수행되었으며 후속 pilot은 0이다. 현재 실행 중 프로세스 실시간 조회는 아니다.
- BLOCKED: persisted workflow `evidence/workflows/current-state.json`이 없다. workflow schema 구현과 합성 시험은 실제 adapter run 상태가 아니다. API는 Runner를 실행하거나 state를 만들어내지 않는다.
- TESTED_SYNTHETIC: 임시 디렉터리의 누락/해시변경/기간만료/경로탈출·허용되지 않은 입력·차단 gate 시험. 운영 결과 파일을 합성 결과로 덮어쓰지 않는다.

## 시험과 실제 브라우저 인계

`tests/api_ui/test_api.py`는 evidence 무결성·기한·경로, CSP/static, 입력 검증, numeric RAG 차단, 학습/배포 강제 차단, 실제 CCKP 재현, private VectorDB, 모델 감사, workflow missing을 검사한다. 결과 XML은 `tests/api_ui/results.xml`이다.

`tests/api_ui/test_browser_e2e.py`에는 3개 선택 Playwright 시나리오가 있다. 기본 실행은 skip이며 Playwright/Chromium 미설치 상태에서 브라우저 성공을 주장하지 않는다. 설치된 별도 환경에서 아래와 같이 실행할 수 있다.

```powershell
$env:SDSS_BROWSER_E2E='1'
$env:SDSS_UI_BASE='http://127.0.0.1:8010'
python -m pytest tests/api_ui/test_browser_e2e.py -q
```

root 실제 브라우저 확인 순서: health → 고정 CCKP → 기본 JSON 로컬 재현 → scenario를 ssp585로 바꿔 차단 확인 → KLHK → VectorDB 상태 → 서술 질문 보고서 검색 차단 → 정량 질문 climate.query 라우팅 → Sentinel 최종 감사·수집 차단 상태 → 모델 차단 이유 → 학습/배포 disabled → workflow missing → 작은 화면에서 메뉴/JSON 영역 확인. 실제 서버 실행 세션과 브라우저 스크린샷/시각은 root 통합 증거로 남긴다. 본 담당은 실제 브라우저를 실행하지 않았다.

2026-11-24 담당 검증 결과: pytest 10 passed / 3 skipped (Playwright 미실행), Ruff check 통과, Python 포맷 확인 및 Node 구문 검사 통과. Starlette TestClient의 httpx 사용에 관한 deprecation warning 1건이며 실제 API 실패는 아니다. 정적 화면은 별도 production bundle build가 없다. 실제 서버·브라우저 적용은 root 검증 대기다.


## 최종 Sentinel 증거 갱신 (2026-11-24)

진행 중 runtime-checkpoint pin을 아래 네 문서로 교체했다.

- `evidence/onemap_sentinel/handoff-summary-20261124.json`
- `evidence/onemap_sentinel/held-audit-20261124/completeness.json`
- `evidence/onemap_sentinel/migration-receipt-20261124.json`
- `evidence/onemap_sentinel/post-migration-state-20261124.json`

API는 감사 셀 수와 CAS 문서 간 합계를 확인하고 제한된 요약만 반환한다. migration receipt는 약 4.9 MB이므로 명시적인 8 MiB 읽기 한도를 적용하고 객체 목록을 응답하지 않는다. 기본 JSON 증거 한도 2 MiB는 다른 호출에 유지된다. `exact-missing-queue.geojson` 317,455,915 bytes / 72 features는 lock에도 넣지 않고 열지도 않는다. completeness에 기록된 SHA `16a79b666322a1115883fb908762bf077b60b54834005bb2da2f8ff30bd32f3e`와 summary의 크기만 표시하며 geometry_included=false이다. 이 GeoJSON 자체를 API가 재해시 검증했다고 주장하지 않는다.

이전 evidence-lock SHA: `dc15389fc37a1f39cbe4445cd26173a0bd9f606be61d31ad8c9624e7bea53a49` (아래 pilot 추가 pin으로 대체).

최종 회귀시험은 감사 완료와 수집 미완료, 실제 피복률, CAS 합계, 원격 0, 저장된 runtime/lock, 대형 geometry 제외 및 응답 20 KB 미만을 검증한다. 새 pin 적용에는 실행 중 API 재시작이 필요하며 실제 브라우저 확인은 root 담당이다.

최종 갱신 검증: pytest tests/api_ui 11 passed / 3 skipped, Ruff check/format 통과, node --check 통과. 결과는 tests/api_ui/results.xml에 갱신했다. 서버 재시작·브라우저 확인은 이번 담당 실행 범위 밖이다.


## 검증된 단일 pilot 추가 (2026-11-24)

추가 pin 경로는 `evidence/onemap_sentinel/pilot-unit-20261124/run-01/result.json`, `final-state.json`, `postflight-integrity.json`이다. Sentinel 그룹은 총 7개 JSON이며 대형 GeoJSON 자체는 여전히 제외한다.

`GET /api/sentinel`의 `pilot`은 East Java 2023 단일 장면의 B02/B03/B04/B08/B11/B12+SCL만 나타낸다. QA PASS, clear 65,536/65,536 (100%), 동일 scene 확인, 실제 측정 원격 body 7,471,506 bytes/28 requests, HTTP 오류 0, 관측된 HTTP429 없음이다. API는 event 수·body 합계·result/final/integrity의 ledger SHA 일치를 확인한다. HTTP 이벤트 전체 및 원격 asset URL은 응답하지 않는다. QA는 독립 정확도가 아니며 `independent_accuracy_measured=false`, `learning_ready=false`와 BIG authority/independent GT blocker를 유지한다.

ledger SHA는 `8e98e9ba033f015e4e289860166b87f67d81a10e12fee66c9b45481296caa44a` → `b257db2925e5c4eac99081c5539216314c972d49dd6741f38f5780da7dd25de1`, 잔액 1,678,521,030 bytes이다. 저장된 final/postflight 기준 후속 pilot 0, collector 0, 실행·ledger lock false이다. 이는 저장된 관측이며 실시간 프로세스 조회가 아니다.

전역 피복 집계는 pilot 이후 **재계산되지 않았다**. 기존 0.976741%/0.889803%는 PRE_PILOT_HELD_AUDIT_NOT_RECOMPUTED로 명시하고, completion=false 및 full_spatial_coverage=false를 유지한다. 기존 원격 0은 `pre_pilot_audit_remote_downloads`로 범위를 좁혔다. 새 pilot 요청을 0으로 숨기지 않는다. 단일 pilot 예약·settlement 검증을 일반 연속 수집 승인으로 확대하지 않는다.

현재 evidence-lock SHA: `56b2f604a632a7f232fc9e9cba9c6469ec0775c6a8d6375f822f5c09ab9fcc3b`. 새 pin을 읽으려면 API 프로세스를 재시작한다. 응답 20 KB 미만 제한 회귀시험을 유지했다. 실제 브라우저·서버 적용은 root 인계 범위이다.

Pilot 추가 검증: API 시험 12 passed / 선택 Playwright 3 skipped, Ruff check/format 및 node --check 통과. 최신 시험 결과: tests/api_ui/results.xml. 실제 브라우저는 이번 담당 미실행.

## 시험 자료 반영 재감사 UI 검증 (2026-11-25)

`GET /api/sentinel`에 `coverage_basis=POST_PILOT_EXACT_NATIVE_GEOMETRY`, `province_year_cells`, `pilot_coverage_delta`, `missing_area_m2`, `next_collection`을 추가했다. 셀 면적은 m², 전송 추정은 응답 본문 byte 단위다. `full_gap_transfer_estimate_bytes=null`은 원격 창 미확정 상태를 뜻한다. GeoJSON 본문은 응답에서 제외하며 전체 수집 상태는 `BLOCKED_COLLECTION_NOT_COMPLETE`다. 증거 pin을 읽을 수 없으면 409와 차단 사유를 반환한다.

Edge 158.0.4370.33의 격리 세션에서 로컬 8011의 페이지를 열어 **05 공간피복·이관**, **재감사 결과 조회**, **36개 주·연도별 피복 상세**를 클릭했다. /api/sentinel HTTP 200, 피복 0.9773%·0.8904%, 동자바 2023 1위, 예상 42.75MiB, 상세 36행, 페이지 JavaScript 오류 0을 확인했다. 화면 캡처는 `artifacts/sentinel-post-pilot-ui.png`다. Sentinel/API 회귀시험은 UTF-8 모드에서 71 통과, 선택 브라우저 시나리오 3건 건너뜀이다.

## 수집 현황 추가 (2026-11-25)

기존 메뉴 순서와 스타일을 유지하며 **수집 현황** 항목을 추가했다. 로컬 8012의 Edge에서 수집 목록 조회, 자료군 6개, Sentinel-2 질·수량 지표 3행 및 36개 주·연도 상세, CCKP 목표 미확정, 기존 공간피복 화면을 확인했다. HTTP 200, 페이지 JavaScript 오류 0, 390px 너비에서 문서 가로 넘침 없음. 화면 캡처는 `artifacts/collection-progress-ui.png`다.
