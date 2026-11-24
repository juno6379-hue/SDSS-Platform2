# Climate API·내부 커넥터 카탈로그

기준일: 2026-11-24. 이 문서는 실제 원격 서비스와 내부 Python 함수를 구분한다. 프로젝트 HTTP API 서버·기후 numeric endpoint는 이 담당 범위에서 만들지 않았다.

## 실제 확인된 공개 원천

| 인터페이스 | 범위·입력 | 현재 상태 |
|---|---|---|
| World Bank 공식 GitHub 문서 | https://github.com/worldbank/climateknowledgeportal | VERIFIED_REAL 문서 확인, 수치 API 아님 |
| S3 ListObjectsV2 | `https://wbg-cckp.s3.amazonaws.com/?list-type=2&prefix=...&delimiter=/&max-keys=...` | VERIFIED_REAL, 반환 prefix만 다음 조회 허용 |
| S3 HEAD | 정확히 listing에 존재하는 key의 HTTPS 객체 URI, If-Match | VERIFIED_REAL 1건, 본문0B |
| S3 GET/Range | 고정 plan의 실제 listed key만 | TESTED_SYNTHETIC, 실제 NetCDF GET0 |
| CCKP Indonesia 국가 API/국가별 file URI | 공식 국가 코드·schema·범위 근거 필요 | BLOCKED, `/IND`·`/IDN` URL 생성 없음 |
| 구조화 numeric tool | QC된 CF/Grid/Parquet/PostGIS 필요 | PLANNED; RAG 유사도로 수치 응답 금지 |

S3 URL은 객체 목록 계층을 관찰하는 transport이며 country API라고 부르지 않는다. 글로벌 자료의 country clipping/reprojection/통계는 별도 모듈과 검증이 필요하다. 탐색한 실제 구조·증거·라이선스 한계는 [소스 목록](CCKP_SOURCE_INVENTORY.md)을 참조한다.

## 내부 Python 계약

모듈: `services.datahub.connectors.cckp.source`. 표준 라이브러리만 사용하며 외부 CLI·boto credential·bucket sync를 호출하지 않는다.

| 함수/모델 | 입력→출력·오류 |
|---|---|
| `discover(prefix='', max_keys=10, parent=None, transport=None)` | 단일 XML 목록→frozen Inventory. root 이외는 parent가 반환한 정확한 prefix만 허용. 최대100keys/256KiB, 자동 다음 페이지 없음 |
| `inventory_from_dict(value)` | 자체 목록 receipt를 복원하고 원본XML SHA/필드 일치 검사. CCKP의 외부 JSON API schema를 가정하지 않음 |
| `confirm_country_scope(listing, identifier, exact_prefix)` | 실제 반환 prefix의 마지막 segment가 identifier와 같아야 CountryScope 생성. 국가명-코드 매핑을 추론하지 않음 |
| `plan_download(inventory, scope, country_id, variable, start_year, end_year, max_files, max_bytes, license, trace_id)` | 국가·변수·기간·수량·바이트 제한의 frozen DownloadPlan. 미확인 범위·초과는 CckpError |
| `download(plan, root, execute=False, transport=None)` | 기본PLANNED. 명시 실행 시 bounded RAW+immutable receipt; 중복 SHA 확인·ETag/Range·누적예약·lock·429 circuit |
| `head_object(inventory, key, transport=None)` | 실제 listed key의 HEAD만. size/ETag drift 또는 본문 반환 거부 |

예외는 `CckpError`, 잘못된 JSON/XML·파일 I/O·HTTP/timeout 예외가 상위로 전달될 수 있다. 호출자는 임의 재시도하지 않고 trace와 원장 상태를 보고해야 한다. HTTP API adapter가 추가될 경우 root가 오류 상태·보안·승인을 별도 매핑해야 한다. 현재 웹 endpoint 경로를 추측해 문서화하지 않는다.

## RAW receipt와 lake 인계

`cckp-raw-receipt/1.0`은 `source_id`, `dataset_id`, `version=ETag`, `source_uri`, `sha256`, `etag`, `etag_is_sha256=false`, `bytes`, `license`, `acquired_at`, `available_at`, `trace_id`, `inventory_id`, `listing_sha256`, `plan_id`, country/variable/요청기간을 보존한다. `transfer-state.json`이 receipt 파일의 SHA pin도 보관한다.

unit/calendar/관측-전망/model/scenario/grid/crs가 미확인일 때 null이고 `next_gate=CLIM_METADATA_MISSING`다. 이는 ClimateAsset을 충족한 레코드가 아니므로 lake/feature/RAG numeric 경로가 duck-cast해 통과시키면 안 된다. 완전한 공통계약 adapter·dataset version registry·접근제어·CF/QC·전역 다중계획 budget은 후속 통합 범위다.

## 운영 금지·시험 상태

`aws s3 sync`, 재귀 bucket download, 임의prefix/국가코드 추측, 라이선스 UNKNOWN 취득, 새로운 root로 예산 초기화, source ETag 변경 무시, 범위 밖 파일을 국가 자료로 등록하는 행위를 금지한다. 원본은 code-level 불변·pin 검증이며 외부 WORM 보장은 별도다.

합성 **24 PASS**, 실제 목록5페이지 **5,289B**, 실제 HEAD1건 **NetCDF 본문0B**. 실제 국가 NetCDF 다운로드·수치 조회·CF QC는 미검증이다. 내부 기능이므로 UI 변경·브라우저 검증·서버 적용은 이번에 수행하지 않았다.
