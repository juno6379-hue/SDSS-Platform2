# v4.2 그대로 읽는 1분·5분 발표

## 1분

“v4.2에서는 기후 설명과 숫자의 경로를 분리하고 실제 CCKP CDD 원본 한 건을 SHA로 고정해 계산했습니다. 1951년부터 1980년까지 제공된 climatology의 개발 bbox 12,765셀 구면가중 평균은 40.91221481742199일입니다. 하지만 인도네시아 행정경계 평균이나 연별·월별 값이 아니며 ERA5 재분석은 독립 ground truth가 아닙니다. live 서비스·학습·배포는 0건이므로 전체 완료는 아닙니다.”

## 5분

1. **문제** — 벡터 유사도는 숫자의 단위·달력·격자·시나리오나 기관 authority를 보증하지 않는다.
2. **공통 계약** — source/version/URI/SHA/license/acquired_at, 관측/전망, 모델/시나리오, 단위, CF 달력, 공간·시간, ACL, trace를 필수로 고정한다.

## 결과 카탈로그 Gate — 1분

“결과 카탈로그는 기존 공통 결과 ID에 수치, 원본 SHA, 지도 파일, 보고서와 불확실성 상태를 고정합니다. 실제 CCKP 결과에는 1951–1980 개발 bbox CDD 40.91221481742199일, 12,765개 격자점과 보고서 2개가 붙었습니다. BIG 결과에는 반텐 과거 폴리곤 1개가 붙었지만 현행 시기와 사용 권리는 미확인입니다. 두 결과 모두 불확실성은 미산정이고 과학 승인과 기관 게시 승인은 각각 대기 중입니다. 따라서 `CATALOG_READY`는 공개 승인이나 독립 정확도를 뜻하지 않습니다.”

## 결과 카탈로그 Gate — 5분

1. 기존 결과 ID와 패키지 SHA를 분리해 같은 결과를 찾으면서 패키지 변경도 감지한다.
2. 원본·라이선스 근거·layer·report의 byte와 SHA, 기간·CRS·nodata·단위를 fail-closed 검증한다.
3. CCKP 실제 원본을 replay해 `40.91221481742199 days`, 12,765개 bbox 격자 중심, 보고서 2개를 고정했다.
4. 이 값은 인도네시아 행정경계 평균이나 연별·월별 값이 아니며 ERA5 재분석은 독립 ground truth가 아니다.
5. BIG 자료는 2017 조례 표기의 반텐 역사 폴리곤 1개다. 현행 RTRW 6지역 확보로 확대하지 않는다.
6. 두 seed 모두 `NOT_REPORTED`이므로 불확실성이 0이 아니라 미산정 상태다.
7. 과학 검토와 기관 게시 결정을 서로 다른 authority·근거·revision으로 기록한다.
8. 게시 승인은 현재 과학 revision의 선승인과 게시 입력 완전성이 필요하다.
9. 실제 두 seed의 두 승인축은 모두 `PENDING`이며 실제 기관 authority·독립 정확도·학습·배포는 차단 상태다.

## 운영 경로 2~8 — 1분

“카탈로그 다음 운영 경로는 고정 기관 승인으로 작업을 접수하고, 기관 원천을 확인하며, 승인된 모델 버전을 실행해 같은 결과 ID로 돌아오는 구조입니다. 작업 계약은 합성 8건을 통과했지만 실제 서버는 공급자 설정이 없어 HTTP 200 응답 안에서 차단을 보고합니다. 실제 원천 6종의 로컬 SHA는 확인했지만 모두 공개 차단입니다. Sentinel 후보는 누출 scene을 격리해 1,779행에서 1,751행, 적격 1,382행, scene 충돌 0으로 만들었지만 학습 허용은 false입니다. 별도 SeaweedFS의 3,295B 객체와 45초 서명 링크는 검증했지만 PostgreSQL과 Kubernetes는 차단됐고 실제 Edge 클릭은 아직 확정하지 않았습니다.”

## 운영 경로 2~8 — 5분

1. 기관 작업은 사용자 URL·명령 대신 운영자가 고정한 승인 ID만 접수한다.
2. 같은 승인·공급자 설정에 같은 작업 ID와 idempotency key를 써 중복 제출을 줄인다.
3. 실제 provider 설정이 없어 현재 조회는 HTTP 200과 `JOB_PROVIDER_CONFIG_NOT_SET`, worker는 exit 1이다.
4. React에는 작업·취소·결과 ID, 모델 version·rollback, 기관 원천 상태를 같은 origin으로 읽는 화면이 구현됐다.
5. RTRW·CCKP·Lake·KLHK·private index·Sentinel 6종은 로컬 증거만 검증됐고 모두 공개 차단이다.
6. 실제 manifest의 누출 scene 전체를 격리해 1,751행·적격 1,382행·scene 충돌 0 후보를 만들었다.
7. 지리 중첩·피복·독립 라벨 검사가 남아 후보 학습과 배포는 허용하지 않았다.
8. 합성 ONNX는 11→12→11 rollback과 과학 승인 철회 후 실행 차단을 검증했다.
9. API 8014·Vite 5175의 세 운영 경로와 138-module build는 확인했지만 실제 Edge 클릭은 대기한다.
10. 별도 SeaweedFS의 3,295B 객체·서명 링크는 검증했지만 PostgreSQL RLS·복구와 Kubernetes는 차단됐다.
3. **설명 경로** — ACL·license·유효기간 선필터 후 BM25·합성 hash vector·metadata로 찾고 원문 citation을 재검증한다.
4. **정량 경로** — `climate.query`는 고정 raw·receipt·CF·license가 맞는 한 CDD bbox 통계만 반환한다.
5. **source·lake·feature** — bounded discovery와 receipt, CF/as-of/ACL/bbox 계획은 fail-closed다. planner는 `execution_started=false`, `numeric_features=null`이다.
6. **시험 증거** — contract/RAG 23, source 24, lake/feature 24로 합성 71 PASS이며, 별도 climate.query는 합성 12 + 실원본 재현 2를 통과했다.
7. **정직한 한계** — 행정경계 통계, 연별/월별 시계열, 독립 정확도, live API/RAG 등록, 학습·배포는 검증하지 않았다.

상세 근거: [v4.2 기후 계약·RAG 이해자료](../V42_CLIMATE_FOUNDATION_AND_RAG.md)

## KLHK ingestion·MLOps 추가 1분

“KLHK·CCKP 문서는 원문과 SHA를 고정하고 검토 전에는 운영 RAG나 학습으로 넘기지 않도록 했습니다. 실제 metadata 원본 7개, 122개 span, 381,676바이트를 보존했고 SHA 불일치는 없었습니다. 그러나 KLHK renderer는 25항목이며 native 23클래스 domain과 license는 미확인입니다. ingestion/RAG 29건과 MLOps 6건의 합성시험은 통과했지만 실제 운영 index, 학습, 독립정확도, 배포는 모두 차단 상태입니다.”

추가 상세 근거: [KLHK 문서 ingestion과 학습·배포 Gate](../V42_KLHK_RAG_MLOPS_GATES.md)

## CCKP bbox 수치 도구 추가 1분

“실제 4,209,592바이트 ERA5 CDD NetCDF를 SHA로 고정하고 17개 Range chunk로 취득했습니다. 파일의 CF-1.6과 NETCDF3_CLASSIC, 1951년부터 1980년까지의 climatology를 직접 검사했으며, 개발 bbox의 12,765개 셀을 full-cell 구면 면적가중한 값은 40.91221481742199일입니다. 하지만 인도네시아 행정경계 평균이나 연별·월별 값이 아니며, ERA5 재분석은 독립 ground truth가 아닙니다. live 서비스 등록·학습·배포는 아직 0건입니다.”

추가 상세 근거: [CCKP Indonesia 개발 bbox 수치 도구](../V42_CCKP_INDONESIA_NUMERIC_TOOL.md)

## 최종 통합 상태 추가 1분

“36개 주·연도 셀이 최소 28개 패치 기준을 충족했습니다. 시험 영상 반영 후 6밴드와 SCL 동시 피복은 0.977325%, 유효 피복은 0.890387%입니다. 재감사 화면을 Edge에서 확인했고, CCKP 개발 시험 범위의 CDD 평균은 40.9122일로 재현했습니다. Sentinel 공간 공백, KLHK 클래스·라이선스, 독립 현장 정확도, 실제 학습·배포 및 공개 RAG는 미완료입니다.”

추가 상세 근거: [최종 통합 상태](../V42_FINAL_INTEGRATION_STATUS.md)

## Sentinel 단일 pilot 추가 1분

“East Java 2023의 고정 Sentinel-2 scene 한 건에서 예약, exact asset/window pin, same-scene 6 band와 SCL, bounded Range, 실측 정산을 실제 완료했습니다. 65,536개 pixel은 모두 clear였고 28개 요청에서 7,471,506바이트를 읽었으며 오류와 429는 0이었습니다. 후속 exact 재감사에서 전체 피복은 0.977325%와 0.890387%가 됐습니다. 전체 공간 완료, 예산 충분성, BIG 승인, 독립 정확도, 학습·배포는 여전히 차단 상태입니다.”

추가 상세 근거: [Sentinel 단일 실제 pilot](../V42_SENTINEL_SINGLE_PILOT.md)

## Sentinel post-pilot 재감사 추가 1분

“실 저장 geometry로 36셀과 72개 exact missing feature를 다시 계산했습니다. East Java 2023 pilot은 present와 clear 면적을 각각 6,556,514.48제곱미터 늘렸고 새 피복률은 0.9773249834%와 0.8903869553%입니다. 재감사 중 collector·remote download·ledger write는 모두 0이었습니다. 다음 6개 후보의 한 창 참고 합은 44,829,036바이트지만 전체 전송량이나 실행 승인은 아닙니다. 새 API/UI는 로컬 API와 실제 Edge에서 확인했지만 전체 공간 완료·BIG 승인·독립 정확도·학습·배포는 여전히 차단 상태입니다.”

추가 상세 근거: [Sentinel pilot 반영 36셀 재감사](../V42_SENTINEL_POST_PILOT_REAUDIT.md)

## Sentinel 경계 내 후속 배치 추가 1분

“후속 배치는 6개 주와 2020~2025년 36셀에 경계 내부 256×256 창 하나씩을 계획했습니다. 12시 5분 reconciliation에서 8창 수신·QA 통과 5를 확인했지만 worker PID가 사라졌고 9번째 West Java 2024 창은 32MiB 예약 뒤 실제 전송량이 미확정입니다. 429는 0이어도 정산 전 종료이므로 현재 상태는 차단입니다. pending transfer를 검증·정산하기 전 재개하지 않으며, 신규 창은 아직 전역 aggregate나 학습 적격에 반영하지 않습니다.”

추가 상세 근거: [Sentinel 경계 내 후속 배치](../V42_SENTINEL_BACKGROUND_COVERAGE_BATCH.md)

## 공통 결과 등록·검토·조회 Gate 추가 1분

“공통 결과 Gate는 고정 증거를 검증해 등록하고, 같은 ID로 다시 읽으며, 검토 이력을 남깁니다. 실제 프로젝트 registry의 10개 결과에 검증·등록·재조회 30단계를 모두 통과했고, 실제 Edge 선택시험 5건과 DOM 계약 2건도 통과했습니다. 현재 로컬 8014에는 10개 결과가 모두 PENDING으로 제공됩니다. 검토 완료와 증거 상태는 별도이므로 RTRW 0/6, Sentinel 8/36과 9번째 미정산, KLHK 23클래스·권한 미확보, scene split 중복은 그대로 차단됩니다. 학습·배포는 실행하지 않았습니다.”

추가 상세 근거: [공통 결과 등록·검토·조회 Gate](../V42_COMMON_RESULT_REVIEW_GATE.md)
