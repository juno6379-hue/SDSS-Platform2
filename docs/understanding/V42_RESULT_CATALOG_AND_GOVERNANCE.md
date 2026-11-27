# v4.2 결과 카탈로그와 이중 승인 Gate

- updated_at: 2026-11-25 KST
- source_commit: `c4a3954` — GitHub push 확인
- Gate 목표: 기존 공통 결과 ID에 출처·수치·공간 산출물·보고서·불확실성을 해시 고정 패키지로 연결하고, 과학 검토와 기관 게시 결정을 분리한다.
- 실제 CCKP·BIG seed와 로컬 패키지 재검증: `VERIFIED_REAL`
- 카탈로그·자산·이중 승인 계약시험 6건: `TESTED_SYNTHETIC`
- 실제 기관 authority와 과학·게시 승인: `BLOCKED` — 두 seed 모두 두 승인축이 `PENDING`
- 독립 정확도·학습·배포: `BLOCKED`

Edge 실제 클릭에서 CCKP와 BIG 지도 미리보기 2건, 보고서 파일 3건과 두 축의 대기 상태를 확인했다.

## 1. 쉬운 설명

공통 결과 registry가 “어떤 결과가 등록됐는가”를 관리한다면, 결과 카탈로그는 **그 결과를 설명하고 다시 확인할 수 있는 파일 묶음**을 같은 결과 ID에 붙인다.

묶음에는 다음이 들어간다.

- 어느 기관·adapter가 만들었는지
- 어떤 기간·공간 범위인지
- 수치와 단위가 무엇인지
- 원본 URI·버전·라이선스·SHA-256·byte 수가 무엇인지
- 지도 layer와 보고서를 어떤 고정 파일로 내려받는지
- 불확실성을 실제로 산정했는지

이번 실제 seed는 두 건이다.

| 결과 | 실제 고정 내용 | 반드시 붙는 한계 | 현재 승인 |
|---|---|---|---|
| CCKP CDD | 1951–1980 climatology, 개발 bbox 구면가중 평균 `40.91221481742199 days`, 유효 격자 중심 12,765개 GeoJSON, 보고서 2개 | 인도네시아 행정경계 평균·연별/월별 값·독립 ground truth가 아님. 불확실성 미산정 | 과학 `PENDING`, 게시 `PENDING` |
| BIG 반텐 | 과거 용도지역 폴리곤 1개와 수신·조례 검토 보고서 1개 | 2017 조례 표기의 역사 표본. 현행 시기·법적 효력·사용 권리·반텐 전체성·위치 정확도 미확인. 불확실성 미산정 | 과학 `PENDING`, 게시 `PENDING` |

따라서 `CATALOG_READY`는 “패키지가 붙고 해시 검사를 통과했다”는 뜻이다. 과학적으로 승인됐거나 공개 가능한 상태라는 뜻이 아니다. 공개 적격은 과학축과 게시축이 모두 승인되고, 게시축 승인이 현재 과학 revision에 결속되어야 한다.

## 2. 이론적 배경

### 2.1 결과 ID와 패키지 digest

결과 자체의 ID와 결과 패키지의 SHA-256은 역할이 다르다.

- 결과 ID: 공통 결과 registry에서 결과를 다시 찾는 식별자
- `package_sha256`: 그 결과에 붙은 정규화 패키지 전체의 내용 digest

동일 결과 ID에 동일 패키지를 다시 붙이는 것은 멱등이다. 다른 패키지를 덮어쓰려 하면 `PACKAGE_CONFLICT`로 거절한다. 승인도 package SHA에 결속되므로, 패키지가 바뀌었는데 과거 승인이 자동 승계되는 문제를 막는다.

### 2.2 과학 검토와 게시 승인의 분리

두 결정축은 서로 다른 질문에 답한다.

| 축 | scope | 질문 |
|---|---|---|
| scientific | `INDEPENDENT_SCIENTIFIC` | 수치·방법·한계에 대해 독립 과학 검토를 했는가? |
| publication | `INSTITUTIONAL_PUBLICATION` | 기관이 이 고정 패키지를 게시해도 된다고 승인했는가? |

게시 승인은 과학 승인이 먼저 있어야 하며, 패키지의 기간·라이선스 증거 등 게시 입력도 완전해야 한다. 과학 결정이 이후 변경되면 이전 게시 승인만으로 `release_eligible`이 유지되지 않는다.

이 구조가 “과학적으로 검토됨”과 “기관이 배포를 허용함”을 같은 체크박스로 처리하는 위험을 줄인다. 다만 token과 actor 문자열을 분리한 코드 계약은 실제 기관 인증 자체가 아니다.

### 2.3 불확실성 미보고는 0이 아니다

`NOT_REPORTED`는 오차가 없다는 의미가 아니다. 이번 두 seed는 모두 신뢰구간·독립 관측 오차·위치 정확도 범위를 계산하지 않았다. 그래서 lower/upper 값을 만들지 않고 이유만 기록한다.

### 2.4 Fail-closed 공간·파일 검증

패키지는 다음 조건을 추정으로 보완하지 않는다.

- 기간 순서와 bbox 순서·CRS 범위
- metric 단위와 값 범위
- source·layer·report ID 참조
- 원본·라이선스 증거·산출 파일의 SHA-256과 byte 수
- GeoJSON feature, geometry validity, bbox 포함, CRS84, metric 결측
- GeoTIFF CRS·extent·nodata
- JSON/PDF/CSV/Markdown 형식

하나라도 어긋나면 패키지를 붙이지 않는다. 그러나 형식·해시 검증은 독립 정확도나 기관 권리를 대신하지 않는다.

## 3. 코드·데이터 동작

### 3.1 패키지 계약과 실제 seed

`services/results/catalog.py`는 `sdss-result-package/1`을 검증한다. `services/api/result_catalog.py`는 기존 고정 증거를 읽어 실제 seed를 만든다.

CCKP adapter는 원본 NetCDF를 다시 계산해 기존 수치와 기간·유효 셀·provenance SHA를 비교한다. bbox CSV의 중복 좌표를 막고 12,765행을 GeoJSON Point 12,765개로 고정한다. 카탈로그에는 CDD 값, 유효/마스킹 셀 수, GeoJSON layer, 검산 JSON, 격자 CSV가 들어간다.

BIG adapter는 보존한 반텐 역사 GeoJSON과 receipt의 feature 수·속성·SHA·byte 및 `current_ordinance_match=false`를 다시 맞춘다. 패키지는 폴리곤 1개와 receipt 보고서를 제공하지만 기간은 비워 두고 미확인 사유를 기록한다. license evidence가 없어 게시 입력 완전성도 충족하지 않는다.

### 3.2 Registry 상태와 승인 revision

`services/results/registry.py`는 결과별 패키지를 한 번만 고정한다.

- 패키지가 없으면 `CATALOG_PENDING`
- 패키지가 있으면 `CATALOG_READY`
- 과학·게시축은 각각 `PENDING`에서 시작
- 결정은 revision과 history에 append
- 예상 revision이 다르면 충돌
- 두 축이 `APPROVED`이고 게시 승인에 결속된 과학 revision이 현재 revision과 같을 때만 `release_eligible=true`

공통 결과의 기존 사람 검토 상태 `PENDING/CHANGES_REQUESTED/ACCEPTED`와 이 과학·게시 결정축은 별개다. 일반 검토 완료를 과학 승인이나 기관 게시 승인으로 바꾸어 읽으면 안 된다.

### 3.3 API

| API | 역할 |
|---|---|
| `GET /api/results/{id}/catalog` | 같은 결과 ID의 패키지, 품질 검사, 두 승인축과 이력을 조회 |
| `GET /api/results/{id}/catalog/assets/{asset_id}` | layer/report를 SHA·byte 재검증한 뒤 올바른 media type으로 내려받음 |
| `POST /api/results/{id}/catalog/decisions/scientific` | 과학 authority의 별도 근거 파일과 결정을 기록 |
| `POST /api/results/{id}/catalog/decisions/publication` | 게시 authority의 별도 근거 파일과 결정을 기록 |

조회 응답은 원본의 로컬 경로를 직접 노출하지 않고 source SHA·byte, layer/report의 `href`를 제공한다. 승인 POST는 서로 다른 token·actor, 패키지 SHA, revision, 결정 근거 SHA, axis·scope·authority 결속을 모두 확인한다. 실제 기관 token·authority 운영 설정과 실제 승인은 아직 없다.

## 4. 테스트·증거

| 증거 | 확인 내용 | 상태 |
|---|---|---|
| CCKP 실제 seed | `40.91221481742199 days`, 12,765 Point GeoJSON, 보고서 2개, 원본 replay·SHA 재확인 | `VERIFIED_REAL` |
| BIG 실제 seed | 반텐 역사 폴리곤 1개, receipt 보고서, 현행 조례 불일치와 기간 미확인 보존 | `VERIFIED_REAL` |
| 실제 승인 상태 | 두 결과 모두 scientific/publication `PENDING`; 불확실성 모두 `NOT_REPORTED` | `VERIFIED_REAL` 현재 상태 |
| 실제 Edge 카탈로그 | 실제 seed 2건, 지도 layer 2개, 보고서 3개 조회 | `VERIFIED_REAL` — `c4a3954` 기준 |
| `tests/api_ui/test_result_catalog.py` | 같은 ID 결속, 멱등 attach, asset hash, 404, authority 분리, 과학 선승인, revision·release 취소, drift 차단 | `TESTED_SYNTHETIC` 6 PASS |
| 형식 fail-closed | 기간 역전, CRS 불일치, vector nodata 오류, 허용되지 않은 단위, SHA drift 거절 | `TESTED_SYNTHETIC` |
| 실제 기관 과학·게시 승인 | 기관 인증·권리 근거 미확보 | `BLOCKED` |
| 독립 정확도·학습·배포 | 독립 라벨·평가·실행 없음 | `BLOCKED` |

시험 실행: `pytest -q tests/api_ui/test_result_catalog.py` → **6 passed**, warning 1건. warning은 TestClient/httpx 전환 안내이며 6개 assertion 실패는 없다.

WorldCover 2021은 다른 연도의 정답으로 쓰지 않는다. WorldCover·KLHK와의 weak agreement도 independent accuracy로 보고하지 않는다.

## 5. 발표 스크립트

### 1분

“결과 카탈로그는 기존 결과 ID에 수치, 원본 SHA, 지도 파일, 보고서와 불확실성 상태를 고정하는 기능입니다. 실제 CCKP seed에는 1951–1980 개발 bbox CDD 40.91221481742199일, 12,765개 격자점과 보고서 2개가 연결됐습니다. BIG seed에는 반텐 과거 폴리곤 1개가 연결됐지만 현행 시기와 사용 권리는 미확인입니다. 두 결과 모두 불확실성을 산정하지 않았고 과학 승인과 기관 게시 승인은 각각 대기 중입니다. 따라서 카탈로그 준비는 공개 승인이나 독립 정확도를 뜻하지 않습니다.”

### 5분

1. 공통 결과 ID와 패키지 SHA를 분리해 결과 조회와 패키지 변경 감지를 함께 보장한다.
2. 원본·라이선스 증거·layer·report를 byte와 SHA로 고정하고 CRS·기간·nodata·단위를 fail-closed 검증한다.
3. CCKP 실제 수치를 replay하고 12,765개 bbox 격자 중심을 GeoJSON으로 제공한다.
4. CCKP 값은 행정경계 평균이나 연별 값이 아니고 ERA5 재분석은 독립 정답이 아니다.
5. BIG 반텐 자료는 2017 조례 표기의 역사 폴리곤 1개이며 현행 6지역 RTRW가 아니다.
6. `NOT_REPORTED`는 불확실성 0이 아니라 미산정 상태다.
7. 과학 승인과 기관 게시 승인을 별도 authority·근거·revision으로 기록한다.
8. 게시 승인은 과학 선승인과 현재 과학 revision 결속이 필요하다.
9. 실제 두 seed의 두 승인축은 모두 대기 중이며 학습·배포도 시작하지 않았다.

## 6. Q&A

**Q. `CATALOG_READY`면 바로 공개해도 됩니까?**
아니다. 패키지가 붙고 파일 검사가 통과했다는 뜻이다. `release_eligible`은 과학·게시 두 축의 현재 승인이 모두 있어야 한다.

**Q. CCKP 40.91221481742199일은 인도네시아 국가 평균입니까?**
아니다. `[95,-11,141,6]` 개발 bbox에 포함된 0.25° full-cell 12,765개의 1951–1980 climatology 구면가중 평균이다. 행정경계 평균·연별·월별 값이 아니다.

**Q. 격자점 12,765개가 독립 관측소입니까?**
아니다. ERA5 재분석 격자의 중심점이다. 독립 관측 ground truth나 행정구역 샘플이 아니다.

**Q. 반텐 폴리곤이 있으니 현행 RTRW를 사용할 수 있습니까?**
아니다. 과거 표본 1개이며 현행 효력 기간·권리·전체성이 확인되지 않았다. 현행 6지역 RTRW 확보 증거도 아니다.

**Q. `NOT_REPORTED`는 오차가 없다는 뜻입니까?**
아니다. 신뢰구간·독립 관측 오차 또는 위치 정확도를 산정하지 않았다는 뜻이다.

**Q. 기존 공통 결과의 `ACCEPTED`와 scientific `APPROVED`는 같습니까?**
아니다. 일반 업무 검토, 독립 과학 검토, 기관 게시 승인은 서로 다른 축이다.

**Q. 승인 API가 있으니 실제 기관 승인이 끝났습니까?**
아니다. 계약과 합성시험만 통과했다. 실제 기관 authority·token·결정 근거와 승인은 `BLOCKED`다.

**Q. WorldCover나 KLHK와 맞으면 독립 정확도입니까?**
아니다. 약한 참조 일치도다. WorldCover 2021은 다른 연도의 정답이 아니며 독립 정확도는 분리된 현장·전문가 라벨로 평가해야 한다.
