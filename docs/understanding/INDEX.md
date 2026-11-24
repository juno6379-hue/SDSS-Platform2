# SDSS-Platform2 v4.2 이해자료 색인

- updated_at: 2026-11-24 KST
- source_commit: `UNCOMMITTED_BOOTSTRAP`
- status: 전체 플랫폼 `IMPLEMENTED_UNVERIFIED`; 아래 항목별 상태를 별도로 확인한다.

## 권장 학습 순서

1. [v4.2 기후 데이터 계약과 근거 추적형 RAG](V42_CLIMATE_FOUNDATION_AND_RAG.md) — 쉬운 설명, 이론, 코드 흐름, 시험, 발표, Q&A
2. [KLHK 문서 ingestion과 학습·배포 Gate](V42_KLHK_RAG_MLOPS_GATES.md) — 실제 취득 범위, 운영 게시 차단, MLOps Gate
3. [CCKP Indonesia 개발 bbox 수치 도구](V42_CCKP_INDONESIA_NUMERIC_TOOL.md) — 실제 NetCDF·CDD 통계와 해석 한계
4. [최종 통합 상태: One Map·Sentinel·UI·모델·워크플로](V42_FINAL_INTEGRATION_STATUS.md) — 실제 감사와 남은 차단 조건
5. [Sentinel 단일 실제 pilot](V42_SENTINEL_SINGLE_PILOT.md) — East Java 2023 예약·pin·same-scene 6 band+SCL·정산
6. [용어집](GLOSSARY_KO_EN.md) — 한글/영문/약어와 이 프로젝트의 정확한 의미
7. [1분·5분 발표 대본](presentations/1MIN_5MIN_SCRIPT.md)
8. [발표 FAQ](presentations/FAQ.md)
9. [변경 이력](CHANGELOG.md)

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
| API/UI 연결 | `VERIFIED_REAL` | 실제 Edge 클릭 확인; API 자동시험 11 PASS, Playwright 3 SKIP; 운영 배포 아님 |
| KLHK/CCKP metadata 원본 | `VERIFIED_REAL` | 7개·122 span·381,676B, raw SHA mismatch 0 |
| KLHK native 23-class·license | `BLOCKED` | 2024/2025 renderer 25항목; native domain·사용허가 미확인 |
| 실제 문서 운영 RAG 게시 | `BLOCKED` | public index 0, quantitative answer 0, 기관 authority 미인증 |
| KLHK/RAG ingestion 계약 | `TESTED_SYNTHETIC` | 신규 11 + 기존 RAG 18 = 29 PASS |
| 학습·배포 MLOps Gate | `TESTED_SYNTHETIC` | 6 PASS; 실제 학습·독립정확도·배포 0 |
| Sentinel 36셀 수량 감사 | `VERIFIED_REAL` | 36/36 최소 28패치; full spatial coverage와 다름 |
| Sentinel 공간 피복 | `BLOCKED` | paired 0.976741%, clear 0.889803%; 약 99% 공백 |
| East Java 2023 단일 pilot | `VERIFIED_REAL` | same-scene 6 band+SCL, clear 65,536/65,536, 28요청·7,471,506B, 오류·429 0 |
| pilot 원장·postflight | `VERIFIED_REAL` | SHA `8e98...aa44a`→`b257...25de1`, 잔액 1,678,521,030B, 후속pilot·collector·locks 0 |
| Sentinel aggregate 재감사 | `BLOCKED` | pilot 미반영; 0.976741%는 이전 snapshot, 전체 승인·예산·BIG 승인 미확인 |
| 로컬 CAS 이관 | `VERIFIED_REAL` | 6,125객체·3,904,601,927B; 원격 다운로드 0 |
| 전문 모델 adapter | `TESTED_SYNTHETIC` | 14 PASS; 실제 모델 학습·추론·배포 아님 |
| 내구성 오케스트레이터 | `TESTED_SYNTHETIC` | 5개 계약시험; 실제 workflow state·학습 adapter 없음 |
| data follow-up 단일 pilot 경로 | `VERIFIED_REAL` | reservation·scene/asset/window pin·bounded I/O·실측 정산 한 건 완료; 전체 수집은 아님 |

앞선 climate 계약 합성 71 PASS와 ingestion/RAG 29·MLOps 6, 모델 14, 오케스트레이터 5, Sentinel pilot 계약 26의 범위는 중복 시험을 섞지 않고 개별 Gate별로 읽는다. 단일 pilot 성공과 36/36 최소 패치 셀을 공간 완료로, 남은 byte 잔액을 예산 충분으로, WorldCover/KLHK weak agreement를 independent accuracy로, Edge 로컬 클릭을 운영 배포로 확대하지 않는다.
