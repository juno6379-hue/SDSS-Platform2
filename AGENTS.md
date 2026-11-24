# SDSS-Platform2 개발 에이전트 지침

## 공통 원칙

- 기준 설계는 `docs/architecture/V42_EXECUTION_PLAN.md`와 원본 v4.2 설계서의 이관본이다.
- 모든 기능은 코드, 시험, 운영·사용 문서를 같은 작업 단위로 완료한다.
- 상태는 `VERIFIED_REAL`, `TESTED_SYNTHETIC`, `IMPLEMENTED_UNVERIFIED`, `BLOCKED`, `PLANNED` 중 하나로 명시한다.
- CCKP의 수치값은 공식 API/Grid/Parquet/PostGIS에서만 조회한다. Vector RAG 유사도 결과를 수치 사실처럼 답하지 않는다.
- 관측값과 전망값, 모델·시나리오·단위·달력·격자 해상도를 분리하고 누락 시 fail-closed 한다.
- 원본은 불변 저장하고 receipt, 출처 URI, 버전, SHA-256, 라이선스, 취득 시각을 함께 보존한다.
- WorldCover 2021이나 다른 약한 참조는 다른 연도의 독립 정답으로 취급하지 않는다.

## 경로 소유권

- `services/datahub/connectors/cckp/`, `tests/datahub/`: climate_source_agent
- `services/datahub/climate/`, `tests/climate_lake/`: climate_lake_agent
- `services/geoai/features/`, `tests/climate_features/`: climate_feature_agent
- `services/rag/`, `tests/rag/`: climate_rag_agent
- `docs/understanding/`: understanding_agent
- 공통 계약·CI·루트 설정·통합은 root가 담당한다.

서로의 소유 경로를 동시에 수정하지 않는다. 공통 변경이 필요하면 root에 계약 변경안을 전달한다.

## 완료 Gate

- CLIM-01: 공통 메타데이터·lineage 계약
- CLIM-02: CCKP source inventory 및 bounded discovery
- CLIM-03: immutable raw receipt와 중복 방지
- CLIM-04: CF 달력·단위·관측/전망 QC
- CLIM-05: 시공간 feature join 및 leakage 방지
- CLIM-06: 온톨로지·지식그래프·ACL·인용 계약
- CLIM-07: hybrid retrieval과 structured numeric tool routing
- CLIM-08: 통합 수용시험·운영 인계
