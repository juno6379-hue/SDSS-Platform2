# SDSS-Platform2 v4.2 이해자료 색인

- updated_at: 2026-11-24 KST
- source_commit: `UNCOMMITTED_BOOTSTRAP`
- status: 전체 플랫폼 `IMPLEMENTED_UNVERIFIED`; 아래 항목별 상태를 별도로 확인한다.

## 권장 학습 순서

1. [v4.2 기후 데이터 계약과 근거 추적형 RAG](V42_CLIMATE_FOUNDATION_AND_RAG.md) — 쉬운 설명, 이론, 코드 흐름, 시험, 발표, Q&A
2. [용어집](GLOSSARY_KO_EN.md) — 한글/영문/약어와 이 프로젝트의 정확한 의미
3. [1분·5분 발표 대본](presentations/1MIN_5MIN_SCRIPT.md)
4. [발표 FAQ](presentations/FAQ.md)
5. [변경 이력](CHANGELOG.md)

## 현재 상태 요약

| 영역 | 상태 | 설명 |
|---|---|---|
| 공통 기후 lineage 계약 | `TESTED_SYNTHETIC` | 5개 계약시험 통과 |
| Climate ontology/KG | `TESTED_SYNTHETIC` | 16노드·11관계와 exact source span 계약 |
| ACL·hybrid retrieval·citation | `TESTED_SYNTHETIC` | 합성 문서/hash vector 기반 18개 RAG 시험 |
| CCKP 제한형 discovery | `VERIFIED_REAL` | S3 목록 5페이지 5,289B와 listed NetCDF HEAD 1건만 |
| CCKP bounded source 계약 | `TESTED_SYNTHETIC` | 계획·receipt·재개·429 등 24 PASS; 실제 본문 0B |
| Indonesia CCKP 계획 | `BLOCKED` | 공식 식별자·국가 prefix 미확인, 추측 URL 생성 금지 |
| Climate lake·CF/QC 계약 | `TESTED_SYNTHETIC` | 12 PASS; 실제 numeric QA/curated publication 없음 |
| 시공간 feature planner | `TESTED_SYNTHETIC` | 12 PASS; 실제 join 0, execution_started=false, numeric_features=null |
| 구조화 기후 수치 도구 | `BLOCKED` | route/tool ID 계약만 있고 실제 도구 미연결 |
| 운영 semantic embedding | `PLANNED` | 합성 hash vector를 운영 embedding으로 보지 않음 |
| 기관 인증·authority | `BLOCKED` | 문자열 결속과 실제 기관 인증을 구분 |
| 독립 정확도 | `BLOCKED` | WorldCover 약한 참조와 분리; 독립 라벨 미검증 |
| API/UI·운영 배포 | `PLANNED` | 현재 근거 범위에 없음 |

합성 시험 합계는 71 PASS다. 이를 실제 CCKP 값, 공간 조인, 학습·배포, 독립 정확도, 기관 승인, 운영 서비스 완료로 확대하지 않는다.
