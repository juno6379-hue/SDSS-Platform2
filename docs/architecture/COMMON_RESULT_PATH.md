# 공통 결과 등록·검토·조회

판단할 자료를 고정한 다음 공통 원장에 등록하고, 같은 ID로 상세와 검토 이력을 조회한다. 자료 영역별 출처·버전·권한 검증은 그대로 적용한다.

## 병렬 작업과 완료 기준

| 번호 | 담당 | 완료 기준 | 2026-11-25 상태 |
|---|---|---|---|
| 1 | result_registry | 불변 결과와 검토 이력을 트랜잭션으로 저장하고 재시도·동시 기록을 검증 | `TESTED_SYNTHETIC` 저장소 회귀시험 통과. 고정 실자료 등록·재조회는 8번 증거에 기록 |
| 2 | root | SHA·크기가 맞는 허용 소스 등록, 검토 충돌 처리, 목록·상세 API 연결 | `VERIFIED_REAL` 로컬 API와 원장 연동 확인 |
| 3 | web_ui | 기존 화면에서 등록·필터·상세·수정 요청·검토 완료·새로고침 검증 | `VERIFIED_REAL` 실제 Edge와 격리 SQLite로 확인 |
| 4 | data_pipeline | One Map 6개 주 현행 Pola Ruang의 조례·원본·공간 범위 및 Sentinel 후속 상태 검증 | `BLOCKED` 현행 RTRW 벡터 0/6. BIG 공개 집계와 반텐 과거 벡터 표본 확보. Sentinel 8/36 수신, 5개 품질 통과 후 종료, 9번째 정산 대기 |
| 5 | data_pipeline | 공식 CCKP 수치·원본 lineage와 로컬 Data Lake 이관을 확인하고 운영 저장소 인계 | `VERIFIED_REAL` CDD 표본 및 로컬 카탈로그 6,175개 객체 확인. 전체 CCKP 인벤토리와 운영 DB·객체 저장소 전환은 대기 |
| 6 | web_ui | KLHK 연차 원본·클래스·권한 검증과 기후 보고서 원본·색인·수치 라우팅 검사 | `BLOCKED` 승인 23종과 원본·라이선스 미확보. 비공개 로컬 검토 색인 7문서·122청크 확인, 공개 검색과 운영 임베딩 대기 |
| 7 | ml_pipeline | 불변 split·원본 장면 누수·독립 정확도·사람 승인·배포 근거 검증 | `BLOCKED` 서로 다른 split에서 같은 원본 장면 1개 확인. 실제 학습·독립 평가·운영 승인과 배포 대기 |
| 8 | result_registry, root | 기존 오케스트레이터로 고정 증거 검증→등록→재조회 후 상태를 API/UI에 게시 | `VERIFIED_REAL` 결과 10건의 검증·등록·재조회 30단계를 실행했다. 전체 과학 워크플로는 별도 Gate |

## 사용 흐름

**리포트 & RDTR → 결과 검토**를 열면 목록이 조회된다. **고정 증거 등록**을 펼쳐 등록 가능한 증거를 조회하고 항목을 선택한다. 왼쪽 목록에서 분야와 검토 상태를 필터링한다. 오른쪽 상세에서 근거 경로·SHA-256·바이트 수와 차단 사유를 확인한다. 이름과 검토 내용을 입력한 뒤 **수정 요청** 또는 **검토 완료**를 누른다. 버전이 충돌하면 최신 상세를 다시 읽고 재검토한다.

| 요청 | 사용 방법 |
|---|---|
| `GET /api/results/sources` | 등록할 수 있는 출처 키와 기본 설명을 조회한다. |
| `POST /api/results` | `{"source":"cckp-cdd-1951-1980"}`처럼 지정된 출처를 등록한다. 동일 출처 버전과 같은 페이로드의 재전송은 같은 ID를 반환한다. |
| `GET /api/results?domain=climate&review_status=PENDING` | 목록을 조회한다. `limit`은 1~100개다. |
| `GET /api/results/{id}` | 개별 근거와 검토 이력을 읽는다. |
| `POST /api/results/{id}/reviews` | `decision`, `reviewer`, `note`, `expected_revision`을 보낸다. 결정은 `ACCEPTED`와 `CHANGES_REQUESTED` 중 하나다. |
| `GET /api/workflow` | `result_registration`에서 고정한 로컬 등록 워크플로 실행과 범위를 확인한다. |

로컬 DB는 `data/curated/results/registry.sqlite3`이며 결과 본문과 검토 이벤트를 보존한다. 고정 카탈로그는 `evidence/results/source-catalog.json`이다. 등록과 검토 저장 전에 근거 파일의 크기·SHA-256을 다시 확인한다. 수정된 증거를 등록하려면 해당 버전을 구분하는 새 출처 키와 고정 핀이 필요하다. 잘못된 출처는 404, 본문 검증은 422, 버전 충돌과 증거 불일치는 409로 반환한다. 저장소 장애는 503이다.

결과 API는 loopback 연결과 로컬 호스트를 확인한다. 이름은 로컬 검토자가 입력한 값이다. 기관 인증과 운영 다중 사용자 권한은 별도 구현이 필요하다. 과학적 증거 상태, 로컬 검토 상태, 독립 정확도와 운영 승인을 각각 추적한다.

## 오케스트레이터와 재현

```powershell
python -X utf8 -m services.api.result_workflow --workflow-id result-cckp-local --source cckp-cdd-1951-1980 --execute
python -X utf8 -m uvicorn services.api.app:app --host 127.0.0.1 --port 8014
```

`--execute`를 생략하면 실행 계획과 현재 상태만 읽는다. 실행 상태는 `data/curated/results/workflows/<ID>/state.json`에 기록된다. 최초 6건과 통합 10건의 실행은 각각 `evidence/results/result-registration-20261125-base.json`과 `evidence/results/result-registration-20261125-integrated.json`에 보존한다. 검토 UI 시험은 별도 임시 DB로 실행했으며 프로젝트 원장의 검토 결정을 생성하지 않았다.

2026-11-25 검증에서 UTF-8 모드 전체 시험은 235건을 통과했다. 기본 미실행된 5개 브라우저 시험도 별도 실행에서 실제 Edge로 모두 통과했다. 8014 서버는 결과 10건과 등록 워크플로 30단계를 반환했다.
## 단일 ID 카탈로그

기존 React의 **리포트 & RDTR → 공통 결과 검토**에서 결과를 선택하면 지표, 지도 레이어, 출처, 보고서, 불확실성과 두 승인 이력을 읽는다. GeoJSON은 기존 MapLibre 기반 미리보기와 파일 조회를 제공한다. GeoTIFF는 해시가 검증된 파일로 조회한다. 패키지가 없는 결과는 준비 대기로 표시한다.

| API | 응답과 제약 |
|---|---|
| `GET /api/results/{id}/catalog` | `CATALOG_READY` 또는 `CATALOG_PENDING`, 패키지 SHA-256, 결과별 승인 이력 |
| `GET /api/results/{id}/catalog/assets/{key}` | 같은 결과의 검증된 지도·보고서 파일. 등록된 근거와 파일의 해시 재검사 |
| `POST /api/results/{id}/catalog/decisions/{scientific\|publication}` | 결정, 근거 파일 핀, 패키지 SHA-256, 해당 승인 축의 예상 revision을 검증하고 추가 기록 |

`python -X utf8 -m services.api.result_catalog --seed-verified`를 실행하면 CCKP와 BIG 기존 ID에 실제 패키지를 연결한다. CCKP만 새 작업본에 적재할 때는 `--source cckp-cdd-1951-1980`를 추가한다. 공개 권리가 확인되지 않은 BIG 표본 본문은 프로젝트 로컬 보관본에서 사용한다. 동일 원본으로 재실행하면 같은 결과 ID와 패키지 SHA가 나오며, 변경본은 새 출처 버전으로 등록한다. 외부 기관에서 정규화한 manifest는 `--result-id ID --manifest PATH --manifest-sha256 SHA256`로 로컬에서 등록한다. manifest에는 `schema_version: sdss-institution-result/1`, 같은 `result_id`, `package`가 필요하다. `services/results/catalog.py`에서 필드와 허용 형식을 확인할 수 있다. `pip install -e ".[geo,climate]"` 후 적재한다.

- **World Bank CCKP**. 1951~1980년 ERA5 개발용 경위도 사각형 CDD 40.91221481742199일과 12,765개 격자 중심. 원본 NetCDF 검산과 격자 CSV를 연결했다. 인도네시아 행정경계 통계와 독립 정확도는 별도다.
- **BIG One Map**. 2017년 조례 표기가 있는 반텐 과거 폴리곤 1건과 실제 수신 영수증. 현행 효력 기간과 공개 권리는 미확인이다.
- 두 결과의 독립 불확실성 구간은 미산정이다. 카탈로그에 근거 있는 상태와 이유를 저장한다.

과학 검증과 기관 공개 승인에는 각각 별도의 `SDSS_CATALOG_SCIENTIFIC_TOKEN`/ `SDSS_CATALOG_PUBLICATION_TOKEN` 및 `SDSS_CATALOG_SCIENTIFIC_AUTHORITY`/ `SDSS_CATALOG_PUBLICATION_AUTHORITY`가 필요하다. 권한 토큰은 React에 전달하지 않는다. 승인 증거 JSON의 ID, 패키지 SHA, 승인 축, 결정, 기관, 참조와 범위를 검사한다. 기관 공개는 현재 유효한 과학 승인, 기간, 고정 라이선스 근거를 필요로 한다. 이 API는 로컬 조회용이며 기관 SSO, ACL, 공개·만료 링크 전환은 운영 단계에 속한다.

## React 화면 실행과 검증

`frontend/`는 기존 GeoAI–MLOps–SDSS React 화면의 `90c0302f` 기준 소스와 이번 결과 검토 연결을 포함한다. 기존 기능에는 8002 API를, 카탈로그에는 8014 API를 사용한다.

```powershell
cd frontend
npm ci
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8002'
$env:VITE_RESULTS_PROXY_TARGET = 'http://127.0.0.1:8014'
npm run build
npm run preview -- --port 5176 --strictPort
```

[리포트 & RDTR → 공통 결과 검토](http://127.0.0.1:5176/#/reports/results)에서 Edge로 CCKP와 RTRW 결과를 열고 지표, 출처, 불확실성, 두 승인 상태, 두 지도 레이어의 미리보기와 보고서 3개 파일의 HTTP 200을 확인했다. Python 등록·카탈로그 회귀시험 24건과 135 모듈 React 빌드를 통과했다.
