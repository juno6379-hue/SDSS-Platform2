# 기후 Feature → GeoAI 모델 입력 매핑

상태: **PLANNED / 계약은 TESTED_SYNTHETIC**. 모델 학습·과학 결과·기관 승인을 수행한 문서가 아니다. 기준일 2026-11-24.

## 1. 소비자별 허용 입력

| 소비자 후보 | climate 변수/출처 | 명시적 변환·참조 | 금지·차단 |
|---|---|---|---|
| LCLUC의 기후 보조 feature | 관측 tas/pr 등의 과거 window | source version/SHA·CF calendar·단위·as-of·지역 boundary version | 토지피복 정답 대체, 미래 observation·최신 경계의 과거 역적용 |
| Flood & Drought 기관 모델 | 강수 amount/rate, 온도 등 계약된 변수 | 모델별 timestep·catchment grid·water-equivalent 가정·forcing/초기경계조건 버전 | 단위만 맞다고 재보정·물리모델 검증 완료 주장 |
| Climate Downscaling 기관 모델 | 명시적 CMIP model/scenario/native grid | bias-correction/fit 기간·독립 기간, actual downscaling artifact | coarse grid interpolation을 새로운10m 관측으로 표시 |
| Carbon/Biodiversity의 scenario 분석 | projected 기후 + 고정 시나리오 | observed와 분리, 모델·버전·기간·단위 보존 | 전망값을 관측 또는 독립 ground truth로 표시 |
| 구조화 numeric tool | 수치 QC 완료 Grid/Parquet/PostGIS artifact | 권한·source refs·단위·calendar·trace 보존 | Vector RAG 유사도/문서 임베딩에서 기후 수치 생성 |

기관별 변수 목록·공간/시간 집계·목표변수·독립 검증방법·책임은 TBD다. 이 표는 adapter 계획이며 실제 모델 호환·제공기관 동의 또는 계약상 R&R 확정이 아니다.

## 2. 실행 전 계약

1. source connector의 RAW receipt를 보존한다. calendar/unit/model/scenario/grid가 미확인되면 `CLIM_METADATA_MISSING`으로 중지한다.
2. 명시적인 정규화 adapter로 `ClimateAsset`을 구성한다. 핵심 lineage 필드와 available_at, temporal_method, grid 축 순서를 함께 검증한다.
3. blob 해시·좌표축·결측·CF 속성·물리 범위·cell_methods를 실제로 QC한다. 현재 metadata QC는 실제 numeric QA를 대신하지 않는다.
4. boundary의 유효기간/공개시점과 feature cutoff를 같은 as-of 정책으로 검사한다. 부모 feature/normalizer가 있으면 graph의 공개시점·fit window resolver가 필요하며 현재 차단한다.
5. grid/CRS/aggregation 계약을 고정한다. 현재 planner는 bbox candidate만 반환하고 numeric_features는 null이다.
6. 실제 feature artifact가 만들어진 다음에만 FeatureSet id/version/SHA, 부모 원본·경계·정책·코드 버전과 모델 run을 연결한다.

## 3. 모델·시나리오·시간 의미

observed는 scenario=not_applicable이며 관측 제품명/model을 명시한다. ERA5라는 폴더 이름만으로 단위·달력·사용시점을 채우지 않는다. 재분석도 현장 독립 정답이라고 자동 인정하지 않는다. projected는 model과 ssp/rcp/historical 같은 명시적 scenario가 필요하다. 모형 historical simulation은 observational ground truth가 아니다.

예를 들어 2010년 결과를 학습하는 feature에 2000~2020 평균을 넣거나, 2025년에 처음 공개된 revision을 2010 as-of에서 이용하면 미래 정보가 섞일 수 있다. window/end, available_at, boundary version 및 부모 normalizer fit 기간을 각각 검증해야 한다. scenario_analysis는 알려진 projection의 미래 기간을 허용할 수 있지만 미래 관측을 허용하는 우회 옵션이 아니다.

## 4. 공통 변경 제안과 차단 상태

root에게 제안하는 공통 계약 항목은 `ClimateAsset.model_json_schema()` 승격 여부, source receipt→정규화 adapter, 고정 source availability 증거, 부모 lineage as-of resolver, numeric-QA receipt verifier, 권한 principal 인증, polygon/area-weighted grid executor다. 공통 스키마·루트 설정·다른 담당 경로는 수정하지 않았다.

실제 국가별 NetCDF 자산/헤더·권한·라이선스·CF/단위 메타데이터가 확보되지 않으면 수치 feature 생성과 모델 입력 연결은 BLOCKED다. KLHK나 WorldCover/Esri 약한 참조도 독립 현장 라벨로 바꾸지 않는다. 독립 정확도·모델 승인·운영 배포는 별도 전문가·기관 Gate로 남긴다.

구현/검증 상세: `CLIMATE_METADATA_CONTRACT.md`, `CLIMATE_DATA_LAKE_FEATURES.md`. 합성시험24개 PASS이며 실제 numeric climate feature·모델 학습·배포는 수행하지 않았다.
