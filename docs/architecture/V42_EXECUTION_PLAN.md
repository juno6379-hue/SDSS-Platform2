# GreenBlue v4.2 병렬 실행 계획

상태: `IMPLEMENTED_UNVERIFIED`
기준일: 2026-11-24 (Asia/Seoul)

## 목표

One Map 경계·RTRW, KLHK 연차 토지피복, World Bank CCKP 기후 자료를 원본 보존형 Data Lake에 적재하고, 구조화 기후 feature와 근거 추적형 Climate Knowledge RAG를 분리 구축한다.

```text
공식 원천
  -> source discovery/planner
  -> bounded connector
  -> immutable RAW + receipt
  -> QC/staging
  -> (A) curated climate feature store -> GeoAI
  -> (B) ontology/KG + chunk index -> hybrid RAG
  -> canonical result + citations + trace
```

## 병렬 담당

| 담당 | 소유 경로 | 산출물 |
|---|---|---|
| climate_source_agent | `services/datahub/connectors/cckp/`, `tests/datahub/` | 공식 목록 탐색, 다운로드 계획, receipt, 중복·범위 방지 |
| climate_lake_agent | `services/datahub/climate/`, `tests/climate_lake/` | CF/달력/단위/관측·전망 검증, lake 계약 |
| climate_feature_agent | `services/geoai/features/`, `tests/climate_features/` | 경계·시간 as-of join, leakage 방지 feature |
| climate_rag_agent | `services/rag/`, `tests/rag/` | 온톨로지/KG, hybrid retrieval, ACL·인용·도구 라우팅 |
| understanding_agent | `docs/understanding/` | 쉬운 설명, 시험 증거, 발표 대본, FAQ, 상태 색인 |
| root | 공통 계약·통합 | 계약 조정, 전체 시험, GitHub 통합·인계 |

## 불변 규칙

1. 기후 수치 응답은 Vector RAG가 아니라 검증된 구조화 데이터 도구에서 생성한다.
2. `source_id`, `dataset_id`, `version`, `source_uri`, `sha256`, `license`, `acquired_at`, `observed_or_projected`, `model`, `scenario`, `variable`, `unit`, `spatial_coverage`, `time_coverage`, `grid`, `crs`, `derived_from`, `access`, `trace_id`를 lineage 핵심으로 유지한다.
3. `360_day`, `noleap` 등 CF 달력과 단위 변환은 명시적으로 검증하며 불명확하면 실패한다.
4. coarse climate grid를 Sentinel-2 10m 수준의 실제 관측으로 표현하지 않는다.
5. KG 관계는 확인된 source version과 authority에만 연결한다.
6. 국가 페이지가 보인다는 이유로 비공개 API나 URL 규칙을 추정하지 않는다.

## 온톨로지 최소 모델

노드: `Institution`, `Source`, `Collection`, `Dataset`, `DatasetVersion`, `Variable`, `Scenario`, `ClimateModel`, `TimePeriod`, `Geography`, `SpatialUnit`, `Document`, `Chunk`, `FeatureSet`, `Result`, `Policy`.

핵심 관계: `PUBLISHED_BY`, `HAS_VERSION`, `CONTAINS_VARIABLE`, `USES_SCENARIO`, `PRODUCED_BY_MODEL`, `COVERS_TIME`, `COVERS_GEOGRAPHY`, `DERIVED_FROM`, `CITES`, `GOVERNS`, `SUPERSEDES`.

문서 chunk는 source span, authority, 언어, ACL, 라이선스, 유효기간, 공간·시간 범위, 변수·시나리오·모델, claim authority를 보존한다.

## 초기 검증 기준

- 실제 네트워크 검증과 합성 시험을 구분한다.
- World Bank 공식 문서 저장소와 공개 S3 규칙까지만 현재 검증 근거로 사용한다.
- CCKP Indonesia 웹 페이지 본문 수집은 실행 환경의 403으로 `BLOCKED`; 공식 bulk 자산·메타데이터 기반 연동을 우선한다.
- 대용량 global bucket sync는 금지하고 국가·변수·기간·파일 수 제한을 가진 plan을 먼저 생성한다.
