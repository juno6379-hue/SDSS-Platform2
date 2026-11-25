# 이해자료 변경 이력

## 2026-11-24 — v4.2 공통 기후 계약·Climate RAG 초기 이해패키지

- `V42_CLIMATE_FOUNDATION_AND_RAG.md` 신규 작성
- `INDEX.md`, `GLOSSARY_KO_EN.md`, 발표 대본, FAQ 신규 작성
- contract 5개 + RAG 18개 = 23개 합성 시험 통과 근거 반영
- 실제 CCKP 수치·공식 문서 인덱스·기관 인증·semantic embedding·API/UI는 미검증/차단으로 구분
- WorldCover 약한 참조와 독립 정확도, authority 문자열 결속과 실제 기관 승인을 분리

## 2026-11-24 — CCKP source·climate lake·feature planner 인계 반영

- 실제 CCKP 검증 범위를 S3 목록 5페이지 5,289B와 NetCDF HEAD 1건으로 제한해 기록
- NetCDF 본문 0B, Indonesia 식별자/국가 prefix 미확인, 실제 download plan `BLOCKED` 반영
- CCKP source 합성 24 PASS와 receipt·재개·예산·429 fail-closed 계약 설명 추가
- climate lake 12 PASS와 feature planner 12 PASS 반영
- 실제 join·numeric feature·학습·배포 0건, `execution_started=false`, `numeric_features=null` 명시
- 전체 합성 증거를 contract/RAG 23 + source 24 + lake/feature 24 = 71 PASS로 갱신

## 2026-11-24 — KLHK/RAG ingestion·MLOps Gate 반영

- `V42_KLHK_RAG_MLOPS_GATES.md` 신규 작성
- `VERIFIED_REAL` 범위를 metadata 원본 7개·122 span·381,676B·raw SHA mismatch 0으로 제한
- KLHK 2024/2025 renderer 25항목과 native 23-class domain·license 미확인을 분리
- 실제 문서 운영 index 게시 0, quantitative RAG answer 0, 기관 authority 미인증 명시
- ingestion 신규 11 + 기존 RAG 18 = 29, MLOps 6 합성 PASS 반영
- WorldCover/KLHK 약한 참조와 독립 ground truth, 합성 READY와 실제 학습·배포를 분리

## 2026-11-24 — CCKP Indonesia 개발 bbox 수치 도구 반영

- `V42_CCKP_INDONESIA_NUMERIC_TOOL.md` 신규 작성
- 4,209,592B 원본 SHA pin, 승인된 Range 17 chunk 재개, `NETCDF3_CLASSIC`·CF-1.6 검증 반영
- bbox CSV 12,765행과 1951–1980 제공 CDD climatology 구면가중 평균 40.91221481742199 days 기록
- 합성 12 + 실원본 read-only 재현 2 = 14 PASS 반영
- 인도네시아 행정경계 평균·연별/월별 시계열·독립 ground truth가 아님을 명시
- HTTP/RAG live 등록, curated 등록, 학습, 배포 0건을 분리

## 2026-11-24 — One Map·Sentinel·UI·모델·워크플로 최종 통합 인계 반영

- `V42_FINAL_INTEGRATION_STATUS.md` 신규 작성
- Sentinel 36/36 최소 수량 감사와 paired 0.976741%·clear 0.889803% 공간 피복을 분리
- 약 99% 공간 공백, reservation adapter와 exact scene/asset/window pin 부재를 `BLOCKED`로 명시
- 로컬 CAS 6,125객체·3,904,601,927B 이관과 원격 download/write 0건 반영
- 실제 Edge 클릭 검증과 API 11 PASS·Playwright 3 SKIP을 서로 다른 증거로 기록
- 모델 adapter 14 PASS와 오케스트레이터 5개 합성 계약시험을 `TESTED_SYNTHETIC`으로 반영
- 모델 spec과 private `synthetic-hash-64-v1` VectorDB 의미 품질을 `IMPLEMENTED_UNVERIFIED`로 구분
- KLHK native23/license, 독립 ground truth/accuracy, 실제 학습·배포, public RAG를 `BLOCKED`로 유지
- WorldCover 2021은 타연도 정답이 아니며 weak agreement와 independent accuracy가 다름을 재강조
- 진행 중 data follow-up adapter는 완료 범위에서 제외

## 2026-11-24 — East Java 2023 Sentinel 단일 실제 pilot 반영

- `V42_SENTINEL_SINGLE_PILOT.md` 신규 작성
- 고정 scene의 same-scene B02·B03·B04·B08·B11·B12+SCL 및 clear 65,536/65,536를 `VERIFIED_REAL`로 반영
- 28개 원격 요청·본문 7,471,506B·오류 0·관측 429 0 기록
- ledger SHA `8e98...aa44a`→`b257...25de1`, 잔액 1,678,521,030B와 후속 pilot·collector·locks 0 반영
- 기존 reservation/scene pin 미구현 설명을 단일 pilot 경로 구현·실행 완료로 정정
- pilot이 36셀 aggregate에 미반영되어 0.976741%는 이전 snapshot임을 명시
- 전체 공간 완료·전체 예산 충분성·BIG 승인·독립 정확도·학습·배포는 `BLOCKED` 유지
- WorldCover 2021 타연도 ground truth 금지와 weak agreement/independent accuracy 분리 유지

## 2026-11-25 — East Java pilot 반영 36셀 exact geometry 재감사

- `V42_SENTINEL_POST_PILOT_REAUDIT.md` 신규 작성
- 실 저장 geometry로 36셀과 72개 exact missing feature를 재산출한 결과를 `VERIFIED_REAL`로 반영
- East Java 2023 present·clear 면적 각각 +6,556,514.480755895m² 기록
- 현재 피복률 present 0.9773249834093871%, clear 0.890386955270514%로 갱신
- pilot 전 0.976741%·0.889803%는 역사적 snapshot으로 보존
- 재감사 중 collector·remote download·ledger write 0 명시
- 실측 7,471,506B×추천 6창=44,829,036B는 참고량이며 전체 전송량·실행 승인·예산 충분성이 아님을 명시
- 재감사 API/UI는 로컬 8011과 Edge 158 클릭으로 `VERIFIED_REAL`. 36행, 6후보, 예상 42.75MiB, 페이지 오류 0을 확인
- 전체 공간 완료·BIG 승인·독립 정확도·학습·배포 `BLOCKED` 유지

## 2026-11-25 — Sentinel 경계 내 36창 후속 배치 시작

- `V42_SENTINEL_BACKGROUND_COVERAGE_BATCH.md` 신규 작성
- 6개 주×2020~2025년 36창, 미계획 셀 0, 경계·exact missing geometry 내부, 기존 footprint overlap 0 계획 반영
- 창당 32MiB 예약과 주 round-robin 첫 6창 순서, 429·실제 전송 실패 정지 계약 기록
- 완전 전송 SCL 80% 미달은 quality gap으로 분리하고 다음 창을 계속하는 최종 구현 반영
- Root UTF-8 시험 20 PASS 반영
- 11:44 KST PID 37644, 3/36 수신·QA 통과 2·Southeast Sulawesi 2025 진행 상태 기록
- East Java clear 49.47%와 South Sulawesi clear 100%, 누계 18,351,282B·429 0·잔액 1,660,169,748B 반영
- 신규 present 약 19.640308km²·clear 약 16.327472km²와 학습 적격 0을 분리
- 전역 피복은 후속 aggregate 재감사 전 기존 0.9773249834093871%·0.890386955270514%로 유지

## 2026-11-25 — 공통 결과 등록·검토·조회 Gate 및 최신 blocker 반영

- `V42_COMMON_RESULT_REVIEW_GATE.md` 신규 작성
- 실제 프로젝트 registry 10개 결과와 verify/register/lookup 30단계 성공·ID 재조회 일치 반영
- 실제 Edge 선택시험 5 PASS와 DOM 계약 2 PASS, 전체 pytest 235 PASS를 서로 구분해 기록
- 현재 로컬 8014의 10 result·PENDING 10·30단계 scope·One Map 상세 UX·JavaScript 오류 0 반영
- UI 수정 요청·검토 완료 이력은 임시 DB이며 프로젝트 registry의 10개 결과는 모두 PENDING임을 분리
- evidence state와 review status를 분리하고 `ACCEPTED`가 과학적 차단 해제·학습·배포 승인이 아님을 명시
- Sentinel 11:44 `RUNNING` 기록을 역사적 snapshot으로 보존하고, 12:05 worker 종료·8/36·QA 5·9번째 32MiB pending 미정산을 현재 `BLOCKED` 상태로 갱신
- 현행 RTRW 0/6, Banten 역사 샘플·BIG 93,340 record의 제한, KLHK native23/license 미확보를 반영
- private hash RAG 7문서·122 chunk, 원본 scene validation/test 중복, 운영 Lake cutover 미검증을 blocker로 반영
- WorldCover 2021 타연도 정답 금지와 weak agreement·independent accuracy 분리를 유지

## 2026-11-25 — 결과 카탈로그와 과학·게시 이중 승인 Gate 반영

- `V42_RESULT_CATALOG_AND_GOVERNANCE.md` 신규 작성
- 기존 공통 결과 ID에 출처·수치·공간 layer·보고서·불확실성을 SHA 고정 패키지로 연결하는 구조 설명
- 실제 CCKP seed의 `40.91221481742199 days`, 12,765 Point GeoJSON, 보고서 2개를 `VERIFIED_REAL`로 반영
- 실제 BIG 반텐 seed를 역사 폴리곤 1개로 제한하고 현행 시기·법적 효력·권리·전체성 미확인을 유지
- 두 seed 모두 불확실성 `NOT_REPORTED`, scientific/publication `PENDING`임을 명시
- 일반 업무 검토, 독립 과학 결정, 기관 게시 결정을 서로 다른 축으로 설명
- 카탈로그·asset·분리 승인·drift/fail-closed 계약시험 6 PASS 반영
- 실제 Edge 카탈로그 확인은 Root 최종 수치 전달 전 `PLANNED`로 유지
- WorldCover 2021 타연도 정답 금지와 weak agreement·independent accuracy 분리를 유지

## 2026-11-25 — 운영 경로 2~8 기관 작업·원천·모델·저장소 반영

- `V42_OPERATION_PATH_2_TO_8.md` 신규 작성
- 1번 결과 카탈로그의 `c4a3954` GitHub push와 실제 Edge seed 2·지도 2·보고서 3 확인 반영
- 기관 작업 provider의 멱등 제출·재개·취소·model pin·asset SHA·결과 등록 합성 8 PASS 반영
- 실제 개발 조회 HTTP 200과 본문 `JOB_PROVIDER_CONFIG_NOT_SET`, worker exit 1을 실운영 성공과 분리
- RTRW·CCKP·Lake·KLHK·private index·Sentinel 로컬 6종 pin을 `VERIFIED_REAL`로 제한하고 모두 publication/public search `BLOCKED` 유지
- 실제 scene 격리 후보 1,779→1,751행, 적격 1,382행, 원본 scene 충돌 1→0을 반영하되 학습 허용 false 유지
- 합성 ONNX 11→12→11 활성화·rollback 및 과학 승인 철회 뒤 실행 차단을 `TESTED_SYNTHETIC`으로 기록
- React 기관 운영 화면은 API 8014·Vite 5175 세 경로 HTTP 200, 합성 계약과 138-module build까지 `VERIFIED_REAL`; 실제 Edge 클릭은 `PLANNED`로 유지
- 별도 SeaweedFS 4.04에 실제 CCKP 검산 JSON 3,295B 저장, SHA·재시도, 익명 403, 45초 presigned GET·만료 403을 `VERIFIED_REAL`로 반영
- PostgreSQL fixture TCP timeout과 Kubernetes context 부재로 RLS·PostGIS·pgvector·복구·클러스터 인수는 `BLOCKED` 유지
- WorldCover 2021 타연도 정답 금지, weak agreement와 independent accuracy 분리를 유지
