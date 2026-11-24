# CCKP 소스 목록·제한형 원본 취득

검증일: 2026-11-24 KST. 작업 루트는 `E:\SDSS-Platform2`다. 과거 GeoAI 프로젝트의 원장·자료·실행기와 혼합하지 않는다.

## 현재 판정

| 범위 | 상태 | 인정 근거 |
|---|---|---|
| 공식 문서 저장소 | VERIFIED_REAL | World Bank 공식 GitHub README 확인 |
| 익명 S3 목록5페이지 | VERIFIED_REAL | 실제 XML 5,289B 및 각 SHA 보존 |
| 목록에 존재하는 NetCDF1건 HEAD | VERIFIED_REAL | HTTP200, size/ETag 일치, 본문0B |
| bounded planner·RAW receipt·재개·중복 방지 | TESTED_SYNTHETIC | 합성24시험 PASS |
| Indonesia 식별자/국가별 prefix | BLOCKED | 현재 확인한 목록에 국가 식별 근거 없음 |
| 실제 NetCDF 취득·CF QC·기후 수치 제공 | IMPLEMENTED_UNVERIFIED / BLOCKED | NetCDF GET0, unit/calendar/CRS 등 미확인 |

국가별 `/IND` 또는 `/IDN` URL을 만들지 않았다. 목록에서 국가 prefix가 확인되지 않으면 `confirm_country_scope`에서 차단한다. 확인되지 않은 국가 이름-코드 매핑도 만들지 않는다. 합성 fixture의 `country/IDN/`는 시험 전용이며 실제 CCKP 구조나 Indonesia 매핑의 증거가 아니다.

## 공식 근거와 실제 구조

- 공식 문서: https://github.com/worldbank/climateknowledgeportal
- 공식 문서 사이트: https://worldbank.github.io/climateknowledgeportal/
- 공식 공개 bucket: `s3://wbg-cckp/`

공식 README는 collection/variable/model-scenario/NetCDF 계층과 global gridded 자료를 설명한다. 실제 root 목록은 `data/`, `private/`를 반환했다. 따라서 README 예시를 국가별 다운로드 URL이나 bucket root 경로로 그대로 치환하지 않는다. `private/`, `data/devteam/`는 접근하지 않았다.

실제로 확인한 경로는 반환된 prefix만 이어서 탐색했다.

| 목록 prefix | max-keys | 응답XML B | truncated | 주요 결과 |
|---|---:|---:|---|---|
| 빈 root |10|374|false|data/, private/|
|data/|10|1,158|true|cmip6-x0.25/, cru-x0.5/, era5-x0.25/ 등|
|data/era5-x0.25/|5|876|true|arbovir/, cdd/, cdd22/, cdd65/|
|data/era5-x0.25/cdd/|5|585|false|era5-x0.25-historical/|
|data/era5-x0.25/cdd/era5-x0.25-historical/|5|2,296|true|기간1951-1980/1971-2000/1985-2014인 파일3건 및 기타 marker/prefix|

truncated 페이지를 전수 목록으로 보고하지 않는다. continuation은 기록하지만 자동 페이징하지 않는다. 0B의 폴더 marker는 기후 자료로 선택하지 않는다.

HEAD로만 확인한 정확한 객체:

```text
s3://wbg-cckp/data/era5-x0.25/cdd/era5-x0.25-historical/climatology-cdd-annual-max_era5-x0.25_era5-x0.25-historical_climatology_mean_1951-1980.nc
size: 4,209,592 B
ETag: "89a1fc4164f41e1db1e22e776918d4df"
NetCDF response body downloaded: 0 B
```

ETag를 SHA-256으로 간주하지 않는다. 파일명에 historical·기간·변수 문자열이 있어도 실제 CF metadata·물리단위·달력·관측/재분석 구분을 확인한 것으로 취급하지 않는다. 이 객체는 국가 범위가 확인되지 않아 Indonesia 다운로드 계획에 넣지 않았다.

저장소 문서/코드의 MPL-2.0 표시를 S3 데이터 라이선스로 전파하지 않는다. 데이터별 라이선스·권리·국가별 추출 방법은 추가 확인이 필요하다. 공통 ClimateAsset으로 정규화하기 전 `CLIM_METADATA_MISSING`을 유지한다.

## 구현·안전 계약

소유 구현: `services/datahub/connectors/cckp/source.py`, `__init__.py`, `__main__.py`.

1. `Inventory`: bucket, exact prefix, 반환 prefix/객체 key·size·ETag·LastModified, 원본XML, 응답SHA, 조회URI·시각·truncation을 고정한다. XML DTD/entity, 경로 traversal, 중복·범위 이탈·응답 상한 위반을 거부한다.
2. root 이외 prefix는 부모 목록에 정확히 반환된 값만 조회한다. HTTPS exact host, timeout≤30초, redirect 금지, 자동 retry·sync·recursive pagination 없음. 페이지당≤100keys·256KiB다.
3. 국가 계획은 목록의 실제 국가 prefix와 일치하는 identifier가 필요하다. 현재 실제 목록은 그 요건을 충족하지 못했다. 변수 segment와 파일명의 명시 연도 구간이 요청 안에 들어오는 객체만 선택한다. 더 넓은 기간 파일을 받아 요청 기간을 충족했다고 주장하지 않는다.
4. 한 계획≤20파일·누적전송상한64MiB·객체≤32MiB. caller는 이보다 작은 한도를 명시한다. 라이선스 미확인/trace 누락은 차단한다. 현재 global 객체를 국가 객체로 속여 이 조건을 통과시킬 수 없다.
5. 실제 취득은 `download(..., execute=True)`만 수행한다. 기본은 파일·네트워크 write 없는 plan-only다. 실행 lock, 고정 plan ID, 영속 누적 예약으로 중복 실행·재시작 한도 초기화를 막는다.
6. `If-Match`와 Range/Content-Range/본문길이를 검증한다. 검증된 partial SHA가 있는 경우만 재개하며, 원본·receipt는 exclusive 생성한다. 완료물은 SHA/receipt pin을 재검증해 재다운로드 없이 재사용한다.
7. 429는 Retry-After와 영속 circuit을 기록하고 중지한다. timeout처럼 수신량을 모르는 실패는 요청 전 예약을 보수적으로 유지한다. 자동 환불·자동 재시도는 없다. 완성 크기 partial·orphan raw/receipt·pin drift·stale lock는 사람 검토가 필요하다.
8. receipt는 실제 원본SHA와 ETag·소스URI·listing/plan pin·취득시각·라이선스·trace를 보존한다. `RAW_NOT_QC_VALIDATED`; unit/calendar/grid/CRS/model/scenario 등 미확인 값은 null이다. `available_at=acquired_at`은 보수적 시스템 가용시각이며 과거 공개일을 추정하지 않는다.

전송 원장은 **계획/출력 root 단위**다. 여러 계획을 묶는 전역 승인·예산 조정은 root 담당의 후속 통합이며 이 커넥터가 구현했다고 주장하지 않는다. 재개하면서 root를 바꾸거나 상태를 삭제해 한도를 초기화하지 않는다. receipt 불변은 이 코드의 exclusive 생성·SHA 검증 계약이며 외부 관리자 삭제까지 막는 WORM 저장소는 아니다.

## 재현·검증

실제 네트워크 명령 예시(기존 output을 덮어쓰지 않으므로 재검증은 새 파일명 사용):

```powershell
python -X utf8 -m services.datahub.connectors.cckp --output services/datahub/connectors/cckp/evidence/root-listing-NEW.json --max-keys 10 --execute
python -X utf8 -m services.datahub.connectors.cckp --prefix data/ --parent services/datahub/connectors/cckp/evidence/root-listing-NEW.json --max-keys 10 --output services/datahub/connectors/cckp/evidence/data-listing-NEW.json --execute
python -X utf8 -m pytest tests/datahub -o addopts= -q --junitxml=services/datahub/connectors/cckp/evidence/synthetic-tests-20261124.xml
```

최종 시험 **24 PASS/1.12초**. 국가 URL 추측·global scope·XML entity·key traversal·객체/바이트/기간/파일 제한·원본/receipt변조·partial Range·누적예산·429 circuit·active lock·HEAD drift를 합성으로 검사했다. 실제 원본 재개·NetCDF 값 읽기·QC 성공의 증거가 아니다.

실제 근거는 `services/datahub/connectors/cckp/evidence/`의 `*-listing-20261124.json`5개와 `era5-cdd-head-20261124.json`, 시험 근거는 `synthetic-tests-20261124.xml`이다. 개별 목록에는 원본XML·SHA·URI·시각이 포함된다.

## 다음 단계와 경계

공식 국가 코드 목록/국가별 API 또는 검증된 global-grid 공간 추출 계약을 확보한 뒤 Indonesia 선택을 구현한다. 국가 binding을 파일명 문자열로 대신하지 않는다. 이 단계 전에는 실제 다운로드 plan이 BLOCKED다. 데이터 라이선스·CF 속성을 확인한 다음 lake 담당의 ClimateAsset으로 명시적 adapter를 작성하고 QC를 통과시킨다. Vector RAG를 기후 수치 조회로 사용하지 않는다. 내부 커넥터·CLI만 추가했으므로 UI/HTTP 서버 변경·실행 적용은 없다. Root에 lake·RAG·이해자료 인계를 전달한다.
