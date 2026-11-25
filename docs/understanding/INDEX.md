# SDSS-Platform2 v4.2 이해자료 색인

- updated_at: 2026-11-25 KST
- source_commit: `UNCOMMITTED_BOOTSTRAP`
- status: 전체 플랫폼 `IMPLEMENTED_UNVERIFIED`; 아래 항목별 상태를 별도로 확인한다.

## 권장 학습 순서

1. [v4.2 기후 데이터 계약과 근거 추적형 RAG](V42_CLIMATE_FOUNDATION_AND_RAG.md) — 쉬운 설명, 이론, 코드 흐름, 시험, 발표, Q&A
2. [KLHK 문서 ingestion과 학습·배포 Gate](V42_KLHK_RAG_MLOPS_GATES.md) — 실제 취득 범위, 운영 게시 차단, MLOps Gate
3. [CCKP Indonesia 개발 bbox 수치 도구](V42_CCKP_INDONESIA_NUMERIC_TOOL.md) — 실제 NetCDF·CDD 통계와 해석 한계
4. [최종 통합 상태: One Map·Sentinel·UI·모델·워크플로](V42_FINAL_INTEGRATION_STATUS.md) — 실제 감사와 남은 차단 조건
5. [Sentinel 단일 실제 pilot](V42_SENTINEL_SINGLE_PILOT.md) — East Java 2023 예약·pin·same-scene 6 band+SCL·정산
6. [Sentinel pilot 반영 36셀 재감사](V42_SENTINEL_POST_PILOT_REAUDIT.md) — exact geometry 현재값과 다음 6창 참고량
7. [Sentinel 경계 내 후속 배치](V42_SENTINEL_BACKGROUND_COVERAGE_BATCH.md) — 36창 계획, 중단 회로, 시점별 실제 진행
8. [공통 결과 등록·검토·조회 Gate](V42_COMMON_RESULT_REVIEW_GATE.md) — 증거 고정, 불변 ID, append-only 검토, 실제 Edge·프로젝트 등록 증거
9. [결과 카탈로그와 이중 승인 Gate](V42_RESULT_CATALOG_AND_GOVERNANCE.md) — 같은 결과 ID의 수치·지도·보고서 패키지와 과학/게시 승인 분리
10. [운영 경로 2~8](V42_OPERATION_PATH_2_TO_8.md) — 기관 작업·원천·React 연결·모델 버전·저장소와 남은 인수 조건
11. [용어집](GLOSSARY_KO_EN.md) — 한글/영문/약어와 이 프로젝트의 정확한 의미
12. [1분·5분 발표 대본](presentations/1MIN_5MIN_SCRIPT.md)
13. [발표 FAQ](presentations/FAQ.md)
14. [변경 이력](CHANGELOG.md)

## 현재 상태 요약

| 영역 | 상태 | 설명 |
|---|---|---|
| 공통 기후 lineage 계약 | `TESTED_SYNTHETIC` | 5개 계약시험 통과 |
| Climate ontology/KG | `TESTED_SYNTHETIC` | 16노드·11관계와 exact source span 계약 |
| ACL·hybrid retrieval·citation | `TESTED_SYNTHETIC` | 합성 문서/hash vector 기반 18개 RAG 시험 |
| CCKP 제한형 discovery | `VERIFIED_REAL` | S3 목록 5페이지 5,289B와 listed NetCDF HEAD 1건만 |
| CCKP bounded source 계약 | `TESTED_SYNTHETIC` | 계획·receipt·재개·429 등 24 PASS; 별도 global tool에서 한 원본 실제 취득 |
| Indonesia CCKP 계획 | `BLOCKED` | 공식 식별자·국가 prefix 미확인, 추측 URL 생성 금지 |
| Climate lake·CF/QC 계약 | `TESTED_SYNTHETIC` | 12 PASS; 실제 numeric QA/curated publication 없음 |
| 시공간 feature planner | `TESTED_SYNTHETIC` | 12 PASS; 실제 join 0, execution_started=false, numeric_features=null |
| CCKP CDD bbox 수치 도구 | `VERIFIED_REAL` | 4,209,592B SHA pin, Range 17개, CF-1.6/NETCDF3_CLASSIC, 12,765셀, 40.91221481742199 days |
| CCKP live 수치 서비스 | `BLOCKED` | 행정경계·다른 변수/기간·HTTP/RAG 등록·학습·배포 0 |
| private hash VectorDB | `IMPLEMENTED_UNVERIFIED` | 7문서·122 chunk·64차원 index; 의미 검색 품질 미검증 |
| 기관 인증·authority | `BLOCKED` | 문자열 결속과 실제 기관 인증을 구분 |
| 독립 정확도 | `BLOCKED` | WorldCover 약한 참조와 분리; 독립 라벨 미검증 |
| API/UI 이전 snapshot | `VERIFIED_REAL` | 이전 Edge 클릭·API 11 PASS; 새 재감사 UI 검증으로 재사용하지 않음 |
| 재감사 API/UI | `VERIFIED_REAL` | 로컬 8011 및 Edge 158에서 36행·6후보·42.75MiB 확인 |
| KLHK/CCKP metadata 원본 | `VERIFIED_REAL` | 7개·122 span·381,676B, raw SHA mismatch 0 |
| KLHK native 23-class·license | `BLOCKED` | 2024/2025 renderer 25항목; native domain·사용허가 미확인 |
| 실제 문서 운영 RAG 게시 | `BLOCKED` | public index 0, quantitative answer 0, 기관 authority 미인증 |
| KLHK/RAG ingestion 계약 | `TESTED_SYNTHETIC` | 신규 11 + 기존 RAG 18 = 29 PASS |
| 학습·배포 MLOps Gate | `TESTED_SYNTHETIC` | 6 PASS; 실제 학습·독립정확도·배포 0 |
| Sentinel 36셀 수량 감사 | `VERIFIED_REAL` | 36/36 최소 28패치; full spatial coverage와 다름 |
| Sentinel 공간 피복 | `BLOCKED` | post-pilot paired 0.9773249834093871%, clear 0.890386955270514%; 약 99% 공백 |
| East Java 2023 단일 pilot | `VERIFIED_REAL` | same-scene 6 band+SCL, clear 65,536/65,536, 28요청·7,471,506B, 오류·429 0 |
| pilot 원장·postflight | `VERIFIED_REAL` | SHA `8e98...aa44a`→`b257...25de1`, 잔액 1,678,521,030B, 후속pilot·collector·locks 0 |
| Sentinel aggregate 재감사 | `VERIFIED_REAL` | 36셀·72 exact features, present/clear 각각 +6,556,514.480755895m²; 외부 I/O 0 |
| 다음 6창 참고량 | `PLANNED` | 7,471,506B×6=44,829,036B; 전체 전송량·실행 승인·예산 충분성 미확정 |
| 로컬 CAS 이관 | `VERIFIED_REAL` | 6,125객체·3,904,601,927B; 원격 다운로드 0 |
| 전문 모델 adapter | `TESTED_SYNTHETIC` | 14 PASS; 실제 모델 학습·추론·배포 아님 |
| 내구성 오케스트레이터 | `TESTED_SYNTHETIC` | 5개 계약시험; 실제 workflow state·학습 adapter 없음 |
| data follow-up 단일 pilot 경로 | `VERIFIED_REAL` | reservation·scene/asset/window pin·bounded I/O·실측 정산 한 건 완료; 전체 수집은 아님 |
| 경계 내 후속 배치 계획 | `VERIFIED_REAL` | 6주×2020~2025 36창, 경계·missing geometry 내부, 창당 32MiB |
| 경계 내 후속 배치 역사 snapshot | `VERIFIED_REAL` | 11:44 KST 당시 3/36·QA 2·429 0; 현재 실행 상태가 아님 |
| 경계 내 후속 배치 현재 상태 | `BLOCKED` | 12:05 KST worker 종료, 8/36·QA 5, 9번째 West Java 2024 32MiB pending·실제 byte 미확정 |
| 배치 신규 관측 | `VERIFIED_REAL` | 8개 observation이 저장됐지만 최신 면적·byte는 미정산 9번째 창과 분리; aggregate 재감사 전 전역 피복에 미반영 |
| 배치 학습 적격 | `BLOCKED` | 새 training-eligible 0; label·독립 ground truth 없음 |
| 공통 결과 registry·workflow | `VERIFIED_REAL` | 실제 프로젝트 10개 결과, verify/register/lookup 30단계 성공, ID 재조회 일치 |
| 공통 결과 Edge 검토 | `VERIFIED_REAL` | 선택시험 5 PASS·DOM 2 PASS; 임시 DB 등록·수정 요청·검토 완료·새로고침 확인 |
| 공통 결과 로컬 제공 | `VERIFIED_REAL` | 8014에서 10 result·PENDING 10·30단계 scope·One Map 상세, JS 오류 0 |
| 공통 결과 운영 전환 | `BLOCKED` | local/loopback 한정; 다중 사용자 인증·공용 DB/Lake cutover·복구 미검증 |
| 결과 카탈로그 실제 seed | `VERIFIED_REAL` | CCKP `40.91221481742199 days`·12,765 Point·보고서 2개, BIG 반텐 역사 폴리곤 1개·보고서 1개 |
| 결과 카탈로그 Edge | `VERIFIED_REAL` | `c4a3954` GitHub push, 실제 seed 2·지도 2·보고서 3 조회 |
| 결과 카탈로그 계약 | `TESTED_SYNTHETIC` | 동일 ID 결속·asset SHA·형식 fail-closed·분리 승인 6 PASS |
| 실제 과학·게시 승인 | `BLOCKED` | 두 seed 모두 scientific/publication `PENDING`; 기관 authority·결정 근거 미확보 |
| 카탈로그 불확실성 | `BLOCKED` | 두 seed 모두 `NOT_REPORTED`; 0 오차나 독립 정확도를 뜻하지 않음 |
| 기관 작업 provider 계약 | `TESTED_SYNTHETIC` | 멱등 제출·재개·취소·model pin·asset 검증·결과 등록 8 PASS |
| 기관 작업 실운영 | `BLOCKED` | 조회 HTTP 200이지만 `JOB_PROVIDER_CONFIG_NOT_SET`; worker exit 1, 실제 endpoint·token·승인 0 |
| 기관 운영 React 연결 | `VERIFIED_REAL` | API 8014·Vite 5175 세 경로 HTTP 200, 합성 계약·138 modules build; 실제 Edge 클릭은 `PLANNED` |
| 기관 원천 인벤토리 | `VERIFIED_REAL` | RTRW·CCKP·Lake·KLHK·private index·Sentinel 로컬 6종 pin, 원격 요청·원장 쓰기 0 |
| 기관 원천 공개 | `BLOCKED` | 6종 모두 publication gate 차단·public search false |
| 현행 6지역 RTRW | `BLOCKED` | 0/6; Banten 역사 샘플과 BIG 93,340 record는 현행 6지역 완료 증거가 아님 |
| MLOps scene 격리 후보 | `VERIFIED_REAL` | 1,779→1,751행, 적격 1,382행, 원본 scene 충돌 1→0; 학습 허용은 false |
| 모델 release·rollback | `TESTED_SYNTHETIC` | 합성 ONNX 입력 10의 출력 11→12→11, 과학 승인 철회 뒤 실행 차단 |
| 실제 모델 학습·배포 | `BLOCKED` | 지리 중첩·피복·독립 라벨 미검증, 실제 학습·평가·실모델 배포 0 |
| SeaweedFS S3 개발 경로 | `VERIFIED_REAL` | 실제 CCKP 검산 JSON 3,295B, SHA·재시도, 익명 403, 45초 presigned GET·만료 403 |
| PostgreSQL/Kubernetes 저장소 | `BLOCKED` | PostgreSQL fixture TCP timeout, Kubernetes context 없음; RLS·PostGIS·pgvector·복구·클러스터 인수 미검증 |
| 기관 저장소 운영 인수 | `BLOCKED` | 기관 DB·버킷·IAM·SSO·RPO/RTO 인수 미검증 |

앞선 climate 계약 합성 71 PASS와 ingestion/RAG 29·MLOps 6, 모델 14, 오케스트레이터 5, Sentinel pilot 계약 26, 후속 배치 계약 20, 결과 카탈로그 계약 6 PASS의 범위는 중복 시험을 섞지 않고 개별 Gate별로 읽는다. 후속 배치는 실행 중이 아니며 12:05 KST 기준 정산 전 worker 종료로 차단됐다. 공통 결과 10건 등록은 기존 증거의 접수·재조회이지 과학 실행 10건이 아니다. 카탈로그 `CATALOG_READY`도 과학·게시 승인 완료가 아니다. 신규 면적은 후속 aggregate 재감사 전 전역 피복으로 합산하지 않으며, QA 통과·검토 완료도 독립 정확도·학습 적격을 뜻하지 않는다.
