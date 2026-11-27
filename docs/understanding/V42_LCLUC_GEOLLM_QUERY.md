# GeoLLM 반텐 토지피복 질의응답 이해자료

- updated_at: 2026-11-27 KST
- source_commit: `b471bb3bf889315144625a57fa56fce4da7e9d0e`
- evidence_paths:
  - `docs/lcluc/GEOLLM_QUERY.md`
  - `services/api/lcluc_geollm.py`
  - `services/lcluc/question.py`
  - `tests/lcluc/test_geollm_query.py`
  - `artifacts/lcluc/geollm-edge.log`
  - `artifacts/deploy/geollm-b471bb3/compose-geollm-edge-final.log`
  - `artifacts/deploy/geollm-b471bb3/kube-geollm-edge.log`
  - `artifacts/deploy/geollm-b471bb3/cross-environment.log`
  - `artifacts/deploy/geollm-b471bb3/{compose,kube}-pins.log`
  - `artifacts/deploy/geollm-b471bb3/{compose,kube}-api-original-error.log`
  - `artifacts/deploy/geollm-default-build/compose-edge.log`
  - `artifacts/deploy/geollm-default-build/kube-edge.log`
  - `artifacts/deploy/geollm-default-build/cross-environment.log`
  - `artifacts/deploy/geollm-default-build/{compose,kube}-data-lake.log`
  - `artifacts/deploy/geollm-step03/edge-5280-final.log`
  - `artifacts/deploy/geollm-step03/edge-5281-final.log`
  - `artifacts/deploy/geollm-step03/api-compare.log`
  - `artifacts/deploy/geollm-step03/kind-remote-source.log`
  - `artifacts/deploy/geollm-step04/edge-5280.log`
  - `artifacts/deploy/geollm-step04/local.log`
  - `artifacts/deploy/geollm-step04/db-outage.log`
  - `artifacts/deploy/geollm-step04/s3-outage.log`
  - `artifacts/deploy/geollm-step04/api-compare-warm.log`
  - `artifacts/deploy/geollm-step04/edge-5281-warm.log`
  - `artifacts/deploy/geollm-step04/api-compare-r2.log`
  - `artifacts/deploy/geollm-step04/edge-5280-r2.log`
  - `artifacts/deploy/geollm-step04/edge-5281-r2.log`
  - `artifacts/deploy/geollm-step04/{local,db-outage,s3-outage}-r2.log`
- overall_status: `VERIFIED_REAL`

## 1. 쉬운 설명

### 한 문장으로

GeoLLM 토지피복 질의응답은 한국어·인도네시아어·영어 질문을 문서 근거 검색 또는 고정 수치·공간 도구로 보내고, 출처·버전·SHA·제한사항과 함께 답한다.

### 현재 확인된 범위

- `VERIFIED_REAL`: MapBiomas 방법론 질문은 공식 RAG 원문과 페이지 인용을 반환한다.
- `VERIFIED_REAL`: MapBiomas 면적·순변화는 `COVERAGE`, 두 시점 전이·산림 총전환은 `TRANSITION` 발행 자료에서 계산한다.
- `VERIFIED_REAL`: Esri 면적·전이는 고정 v003 COG와 반텐 등적 격자 집계를 사용하고 실제 전이 PNG를 표시한다.
- `VERIFIED_REAL`: Edge에서 한국어·인도네시아어·영어 문서·수치 질의, 지도·출처·버전·SHA를 확인했다.
- `VERIFIED_REAL`: 기본 Dockerfile이 Debian `libexpat1`을 설치하도록 수정됐다. 보관된 `b471bb3` 소스와 이 Dockerfile 변경만으로 `sdss-platform2-api:geollm-libexpat1`을 새로 빌드했으며 파생 런타임 이미지를 사용하지 않았다.
- `VERIFIED_REAL`: 새 기본 이미지로 Compose 5180과 로컬 kind Kubernetes 5181에서 같은 다국어 RAG와 GIS 결과 5건을 확인했다. 두 환경의 JSON 응답 10개와 대응 지도 자산 해시가 일치했다.
- `VERIFIED_REAL`: 원본·evidence는 읽기 전용으로 마운트하고 정제 자료는 별도 복사본을 사용했다. API 소스, 원본 XLSX, 정제 전이 JSON의 SHA도 두 환경에서 같았다.
- `VERIFIED_REAL`: STEP 03 release `banten-geollm-20261127-v1`은 RLS 범위의 불변 PostgreSQL dataset 4개와 SeaweedFS binding 47개·1,143,310,094B를 실제 GeoLLM 출처로 사용한다.
- `VERIFIED_REAL`: LANDY 공식 문서 14건의 실제 passage 286개를 고정 `intfloat/multilingual-e5-base` INT8 ONNX로 768차원화해 pgvector dataset 범위 cosine 검색에 연결했다.
- `VERIFIED_REAL`: Compose 5280과 kind 5281의 기존 React 화면에서 3개 언어 인용과 GIS 결과를 확인했다. 3 RAG·8 GIS·2 차단 응답 13개와 PostGIS 경계·S3 지도 자산 해시가 일치했다.
- `VERIFIED_REAL`: kind는 raw·curated·evidence 또는 로컬 GeoLLM source mount 없이 PostGIS·SeaweedFS·pgvector에서 제공했다.
- `VERIFIED_REAL`: STEP 04의 Compose 5280 `lake` 모드에서 기존 React 화면의 한국어·인도네시아어·영어 원격 RAG와 반텐 2024 논 195,653.67ha를 확인했다.
- `VERIFIED_REAL`: 격리 복사본 27파일을 읽기 전용으로 연결한 명시 `local` 모드에서 GIS 3건·문서 3건을 확인했다.
- `VERIFIED_REAL`: 실제 PostgreSQL 또는 SeaweedFS 장애에서 GIS 3건·RAG 3건이 모두 차단되고 지도 HTTP 503, 빈 수치·출처·인용·지도 URL, 일반 health 유지를 확인했다. 같은 local 자료는 장애 fallback에 사용되지 않았다.
- `TESTED_SYNTHETIC`: 저장소 모드·필수 구성·S3 attestation·연결 실패 차단 계약 17건과 Ruff를 통과했다.
- `VERIFIED_REAL`: kind 5281 warm 경로에서 3개 언어 RAG와 GIS 화면, Compose와 같은 API 13개·지도 SHA를 확인했다.
- `VERIFIED_REAL`: 최초 kind E5 냉시작 재시도에서 nginx 504가 발생했다. warm 성공과 별개인 관측 실패로 보존한다.
- `VERIFIED_REAL`: R2에서 Compose 5280·kind 5281 Edge 전체와 API 13개·지도 SHA 동등성을 다시 확인했다. 정상화 뒤 첫 RAG는 각각 1.95초·1.39초에 `FOUND`였다.
- `TESTED_SYNTHETIC`: R2의 실패 뒤 단일 백그라운드 원격 초기화 재시작 순서는 재초기화 회귀를 포함한 18 PASS와 Ruff PASS로 확인했다.
- `BLOCKED`: BIG 운영 환경의 저장소 연결과 기관 검증은 미확인이다.
- `BLOCKED`: Dockerfile 보완 전 원본 `b471bb3` API 이미지는 Compose와 Kubernetes 모두 `libexpat.so.1` 누락으로 시작되지 않았다. 이전 `b471bb3-expat` 파생 이미지 검증은 원인과 해결책을 확인한 역사적 라운드다.
- `BLOCKED`: Kemenhut 동년 Penutupan Lahan 원본과 승인된 중첩 대상 자산은 미입고 상태다. 해당 질문은 수치를 만들지 않고 이유를 반환한다.
- `BLOCKED`: 독립 정확도는 미측정이다. 현재 제품 안의 면적·전이 조회는 독립 표본 평가와 별도다.
- `BLOCKED`: 조회 응답의 `result_id`는 `null`이다. 공통 결과 registry 등록·검토 흐름은 연결되지 않았다.

## 2. 이론적 배경

### 2.1 RAG와 정형 수치 도구의 역할

방법론·범례·정의 질문은 검색증강생성 (Retrieval-Augmented Generation, RAG) 경로가 공식 문서 인용을 찾는다. 면적·연도·전이를 묻는 질문은 정형 수치 도구가 고정 XLSX·GeoTIFF·감사 JSON만 읽는다. 기존 MapBiomas RAG API에 수치 질문을 보내면 `NUMERIC_TOOL_REQUIRED`로 GeoLLM 수치 경로를 안내한다.

### 2.2 총전환과 순변화

산림 총전환은 지정 기간 `TRANSITION`에서 산림 범주가 비산림 범주로 이동한 모든 발행 레코드를 더한다. 산림 순변화는 `COVERAGE`의 종료 연도 산림면적에서 시작 연도 산림면적을 뺀 값이다.

- 2023→2024 산림 총전환: 3,146.85ha
- 2023→2024 산림 순변화: −1,265.58ha

총전환에는 밖으로 나간 흐름이, 순변화에는 산림 유입과 유출의 최종 차이가 반영되므로 두 수치는 같은 의미가 아니다.

### 2.3 지리 범위와 경계 지도

MapBiomas 수치는 발행자가 정의한 반텐 주 통계다. XLSX에는 그 집계 경계 도형이 포함되지 않는다. 화면의 One Map/BIG 반텐 경계는 위치 맥락을 위한 지도이며 MapBiomas 집계 경계와 동일하다고 확정하지 않는다. Esri는 One Map 반텐 경계와 10m 등적 격자를 실제 계산에 사용한다.

### 2.4 fail-closed 질문 처리

지역·연도·제품·클래스·방향·단위가 충분하지 않거나 자료 버전이 다르면 수치를 추정하지 않는다. 제품이 둘 이상인 질문, 반텐 밖 지역, 미발행 기간, 누락 전이값, Kemenhut·중첩 미입고는 `BLOCKED` 이유를 반환한다.

## 3. 코드·데이터 동작

### 3.1 질문 해석

`parse_question()`은 한국어·인도네시아어·영어에서 다음을 추출한다.

- 경로: 문서 `document`, 면적 `area`, 전이 `transition`, 산림 총전환 `forest_loss`, 산림 순변화 `forest_net_change`, 중첩 `overlap`
- 범위: 반텐, 연도 또는 순서가 있는 연도쌍
- 제품: MapBiomas, Esri, Kemenhut, Sentinel-2, Landsat, WorldCover
- 클래스: 산림·논·팜유·시가지·수역 등

### 3.2 응답 흐름

1. 문서 질문은 MapBiomas 원문 검색으로 보낸다.
2. 정량 질문은 region·product·year·class·direction 계약을 검사한다.
3. MapBiomas는 원본 workbook, `COVERAGE`, `TRANSITION` SHA를 검사한다.
4. 산림 총전환에서는 전이 출발 합이 시작 연도 산림 `COVERAGE`와 맞는지 검사한다.
5. Esri는 v003 연차 COG, 경계 SHA와 감사 JSON을 검사한다.
6. 성공 응답은 ha 수치, 원본 코드, 제품·버전·SHA, 제한사항과 맥락 지도를 반환한다.
7. 증거가 부족하면 빈 metrics와 구체적인 `BLOCKED` reason을 반환한다.

| API | 역할 |
|---|---|
| `POST /api/lcluc/geollm/query` | 문서 또는 GIS 질의 라우팅과 근거 결속 응답 |
| `POST /api/rag/mapbiomas/search` | 문서 근거 검색. 정량 요청은 `NUMERIC_TOOL_REQUIRED` |

### 3.3 지도 응답

- MapBiomas 수치 질의는 One Map/BIG 반텐 경계를 맥락 지도에 표시한다.
- Esri 단일 연도 면적 질의는 실제 연차 분류 이미지를 표시한다.
- Esri 방향 전이 질의는 실제 기준 클래스→비교 클래스 전이 PNG를 표시한다.
- 현재 응답은 읽기 전용이며 `result_id=null`이다.

### 3.4 Compose·Kubernetes 실행 경로

1. Dockerfile 보완 전 `b471bb3` API 이미지는 Rasterio import 단계에서 `libexpat.so.1`을 찾지 못해 Compose와 Kubernetes에서 같은 오류로 중단됐다.
2. 첫 검증에서는 애플리케이션 소스를 바꾸지 않고 `libexpat1`만 추가한 `b471bb3-expat` 파생 이미지를 사용했다. 이 라운드는 역사적 원인 검증으로 보존한다.
3. 현재 기본 Dockerfile에 Debian `libexpat1` 설치 단계를 넣었다. 보관된 `b471bb3` 소스와 정확히 이 Dockerfile 변경만으로 `sdss-platform2-api:geollm-libexpat1`을 새로 빌드했으며 별도 파생 런타임 이미지는 없다.
4. Compose는 5180, 로컬 kind Kubernetes는 5181에서 새 기본 이미지와 같은 소스·자료 pin을 사용했다.
5. 원본과 evidence는 읽기 전용이며 정제 자료는 별도 쓰기 가능 복사본으로 공급했다. 두 환경 모두 `evidence ro`, `raw ro`, `curated rw`를 확인했다.
6. 두 환경에서 한국어·인도네시아어·영어 Edge 질의를 수행했다. RAG와 GIS 결과 5건, JSON 응답 10개, 대응 지도 자산 해시의 동일성을 확인했다.

이 검증은 컨테이너 런타임 이식성과 재현성을 확인한 것이다. Kemenhut 원본, 중첩 자료, 독립 정확도, 결과 registry의 과학·운영 Gate 상태는 바뀌지 않는다.

### 3.5 STEP 03 Staging source 전환

1. release `banten-geollm-20261127-v1`이 MapBiomas `COVERAGE`·`TRANSITION`, Esri audit, 반텐 경계와 LANDY corpus를 PostgreSQL dataset 4개로 고정한다.
2. PostGIS 반텐 경계는 SRID 4326 valid이며 dataset·기관 RLS 범위로 조회한다.
3. SeaweedFS binding 47개·1,143,310,094B에는 Esri COG·preview·clipped raster, 모델, corpus가 포함된다.
4. LANDY 공식 문서 14건의 passage 286개를 로컬 pin `intfloat/multilingual-e5-base` `d128750` INT8 ONNX로 768차원화하고 pgvector dataset 범위 cosine 검색에 사용한다.
5. E5 warmer가 cold proxy 504를 방지한다. kind는 원본·정제·evidence mount와 로컬 GeoLLM source file 없이 PostGIS·SeaweedFS·pgvector에서 응답한다.
6. Compose 5280과 kind 5281에서 한국어·인도네시아어·영어 RAG, 2024 논 195,653.67ha, 2023→2024 산림 총전환 3,146.85ha, Esri 수목→시가지 3,561.79ha를 확인했다.
7. 최종 API 비교는 3 RAG·8 GIS·2 차단 응답 13개와 경계·지도 자산 해시가 두 환경에서 같음을 확인했다.

Staging source 전환은 실제 저장소·vector 검색 경로의 재현성 증거다. 공식 Kemenhut 동년 원본, 독립 정확도, 결과 registry와 기관 운영 승인은 별도 Gate다.

### 3.6 STEP 04 저장소 어댑터

`SDSS_GEOLLM_STORAGE_MODE`는 앱 시작 시 자료 경로를 선택한다.

| 모드 | 동작 |
|---|---|
| `lake` | 고정 release의 PostgreSQL/PostGIS·pgvector·SeaweedFS에서 GIS·지도·문서 근거를 읽는다. 운영 모드 연결 실패는 로컬로 우회하지 않고 차단한다. |
| `local` | 개발용 고정 파일과 기존 어휘 검색을 사용한다. |
| 미설정 | release 변수가 있으면 `lake`, 없으면 `local` 호환 동작을 사용한다. 운영 배포는 `lake`를 명시한다. |

두 모드는 같은 질문 해석, GIS 수치·단위·출처·제품 버전 계약을 사용한다. 원격 모델이 임시 cache에 있어도 SeaweedFS binding과 SHA attestation을 다시 확인한다. 연결 실패는 `GEOLLM_STORAGE_UNAVAILABLE`, 구성 누락은 `GEOLLM_STORAGE_CONFIG_REQUIRED`, 잘못된 모드는 `GEOLLM_STORAGE_MODE_INVALID`로 차단하며 비밀값을 응답에 포함하지 않는다. E5 초기화 중 문서 질의는 `GEOLLM_STORAGE_INITIALIZING`으로 표시하고 GIS 시작은 계속 허용한다.

## 4. 시험 증거와 상태

| 항목 | 상태 | 증거와 범위 |
|---|---|---|
| 다국어 RAG | `VERIFIED_REAL` | Edge 한국어·인도네시아어·영어 공식 인용 |
| MapBiomas 논 면적 | `VERIFIED_REAL` | 2024 반텐 195,653.67ha, Collection 4.1 `COVERAGE` |
| 산림 총전환 | `VERIFIED_REAL` | 2023→2024 3,146.85ha, `TRANSITION` 산림→비산림 |
| 산림 순변화 | `VERIFIED_REAL` | 2023→2024 −1,265.58ha, `COVERAGE` 종료−시작 |
| MapBiomas 산림→시가지 | `VERIFIED_REAL` | 2023→2024 102.63ha |
| Esri 수목→시가지 | `VERIFIED_REAL` | 2023→2024 3,561.79ha, v003 실제 전이 PNG |
| 기본 Dockerfile 빌드 | `VERIFIED_REAL` | 보관 `b471bb3` 소스+`libexpat1` Dockerfile 변경만으로 `geollm-libexpat1` 새 빌드, 파생 런타임 이미지 없음 |
| Compose·kind 실행 | `VERIFIED_REAL` | 새 기본 이미지로 Compose 5180·kind 5181, 양쪽 다국어 RAG와 GIS 5건 Edge 통과 |
| 환경 간 동일성 | `VERIFIED_REAL` | JSON 응답 10개와 대응 지도 자산 해시 일치, API·XLSX·정제 JSON SHA 동일 |
| 자료 마운트 | `VERIFIED_REAL` | 양쪽 raw·evidence `ro`, curated 별도 복사본 `rw` |
| 보완 전 원본 이미지 | `BLOCKED` | Dockerfile 보완 전 `b471bb3`이 양쪽에서 `libexpat.so.1` 누락으로 시작 실패. 파생 이미지 검증은 역사로 보존 |
| STEP 03 release | `VERIFIED_REAL` | `banten-geollm-20261127-v1`, RLS dataset 4개, SeaweedFS 47 bindings·1,143,310,094B |
| 실제 E5·pgvector RAG | `VERIFIED_REAL` | LANDY 14문서·286 passage, 고정 E5 INT8 ONNX·768D dataset-scoped cosine |
| STEP 03 Compose·kind Edge | `VERIFIED_REAL` | 5280·5281의 3개 언어 RAG·GIS, API 13개·경계·지도 자산 동등 |
| kind 원격 source | `VERIFIED_REAL` | source mount 없이 PostGIS 경계·SeaweedFS 자산 제공 |
| STEP 03 단위 회귀 | `TESTED_SYNTHETIC` | 14 PASS, optional live storage 1건 skip. live Staging은 별도 Edge로 검증 |
| STEP 04 어댑터 계약 | `TESTED_SYNTHETIC` | `lake|local`, 구성·attestation·fail-closed 17 PASS와 Ruff PASS |
| STEP 04 Compose lake Edge | `VERIFIED_REAL` | 5280 원격 RAG 3개 언어와 반텐 2024 논 195,653.67ha |
| STEP 04 local Edge | `VERIFIED_REAL` | 읽기 전용 격리 복사본 27파일, GIS 3건·문서 3건 정상 |
| STEP 04 DB/S3 장애 Edge | `VERIFIED_REAL` | 각 GIS 3·RAG 3 차단, 지도 503·빈 evidence URL, health 유지·local fallback 0 |
| STEP 04 kind warm Edge | `VERIFIED_REAL` | 5281 세 언어 RAG·GIS 화면, Compose와 API 13개·지도 SHA 동등 |
| 최초 kind cold 재시도 | `VERIFIED_REAL` | nginx 504 관측. warm 정상 경로와 분리해 실패 기록 보존 |
| STEP 04 R2 Edge/API | `VERIFIED_REAL` | 5280·5281 전체 Edge, API 3 RAG·8 GIS·2 보류 13개·지도 SHA 동등 |
| STEP 04 R2 첫 RAG | `VERIFIED_REAL` | 정상화 뒤 5280 1.95초·5281 1.39초 `FOUND` |
| STEP 04 R2 재초기화 계약 | `TESTED_SYNTHETIC` | 단일 background 원격 초기화 순서, 재초기화 포함 18 PASS·Ruff PASS |
| BIG 운영 저장소 | `BLOCKED` | 운영 연결·기관 검증 미수행 |
| 질문 계약시험 | `TESTED_SYNTHETIC` | 다국어 intent, 총전환·순변화 분리, margin 불일치·미발행 값·기간 차단 |
| Kemenhut 질의 | `BLOCKED` | `KEMENHUT_ASSET_NOT_READY` |
| 중첩 질의 | `BLOCKED` | `OVERLAY_ASSET_NOT_READY` |
| 독립 정확도 | `BLOCKED` | 독립 현장·전문가 판독 표본 미연결 |
| 결과 registry | `BLOCKED` | 응답 `result_id=null`, 등록·검토 흐름 미연결 |

## 5. 발표 스크립트

### 1분

“STEP 04 R2는 Compose 5280과 kind 5281 전체 Edge, API 13개와 지도 SHA 동등성을 확인했습니다. 정상화 뒤 첫 RAG는 1.95초와 1.39초에 응답했습니다. 격리 local과 실제 DB/S3 장애 차단도 재검증했습니다. 최초 R1 kind 냉시작 재시도의 nginx 504는 실패 기록으로 보존합니다. 단일 백그라운드 재초기화 순서는 18개 합성 회귀로 확인했고 BIG 운영 연결은 남아 있습니다.”

### 5분 핵심 순서

1. 질문에서 언어와 관계없이 지역·연도·제품·클래스·지표를 추출한다.
2. 방법론 질문은 SHA 고정 원문 RAG로 보낸다.
3. 수치 질문은 RAG가 아니라 제품별 정형 도구로 보낸다.
4. MapBiomas `COVERAGE`와 `TRANSITION`을 구분한다.
5. 총전환과 순변화를 서로 다른 지표로 보고한다.
6. Esri는 실제 COG·등적 격자·전이 PNG를 사용한다.
7. MapBiomas의 발행 경계와 One Map 맥락 경계를 구분한다.
8. Kemenhut·중첩·독립 정확도·result registry는 증거가 생길 때까지 차단한다.
9. 보완 전 이미지의 `libexpat.so.1` 누락, 역사적 파생 이미지 검증, 기본 Dockerfile `libexpat1` 반영을 구분하고 Compose·Kubernetes의 응답·지도 자산 동일성을 제시한다.
10. STEP 03의 PostgreSQL dataset·SeaweedFS binding·E5 pgvector 검색을 설명하고 kind 무마운트 source 증거를 제시한다.
11. STEP 04 `lake|local` 선택과 운영 모드 fail-closed·S3 attestation을 설명하고 검증 완료 환경을 구분한다.

## 6. Q&A

**Q. 산림 총전환 3,146.85ha와 순변화 −1,265.58ha가 왜 다릅니까?**

총전환은 산림에서 비산림으로 나간 흐름의 합이다. 순변화는 종료 산림면적에서 시작 산림면적을 뺀 값으로 산림 유입과 유출의 최종 차이를 반영한다.

**Q. MapBiomas 답변에 보이는 반텐 경계가 수치 계산 경계입니까?**

One Map/BIG 경계는 위치 맥락 지도다. 수치는 MapBiomas 발행 반텐 통계이며 XLSX에 집계 경계 도형이 포함되지 않아 두 경계가 동일하다고 확정하지 않는다.

**Q. Esri 전이 답변은 실제 지도와 연결됩니까?**

연결된다. 2023→2024 수목→시가지 3,561.79ha 응답에서 실제 v003 전이 PNG를 Edge로 확인했다.

**Q. Kemenhut 질문은 어떻게 처리합니까?**

동년 Penutupan Lahan 원본이 준비될 때까지 `KEMENHUT_ASSET_NOT_READY`로 차단한다.

**Q. 조회 결과가 공통 결과 registry에 저장됩니까?**

현재 읽기 전용 응답의 `result_id`는 `null`이다. 증거 패키지 등록·검토 흐름은 아직 연결되지 않았다.

**Q. 현재도 `b471bb3-expat` 파생 이미지를 사용합니까?**

현재 기본 경로는 파생 이미지가 아니다. 기본 Dockerfile이 Debian `libexpat1`을 설치하며, 보관 `b471bb3` 소스와 이 Dockerfile 변경만으로 `sdss-platform2-api:geollm-libexpat1`을 새로 빌드했다. 이전 `b471bb3-expat` 검증은 원인과 최소 해결책을 확인한 역사적 라운드다.

**Q. Compose와 Kubernetes 결과가 같다는 근거는 무엇입니까?**

API 소스·원본 XLSX·정제 전이 JSON의 SHA가 같고, 실제 질의 JSON 10개와 대응 지도 자산 해시도 일치했다. Compose와 Kubernetes 모두 raw·evidence는 읽기 전용, curated 복사본은 쓰기 가능 상태였다.

**Q. 컨테이너 이식 검증이 독립 정확도나 운영 승인을 의미합니까?**

컨테이너 이식성과 응답 재현성을 검증한 결과다. Kemenhut 동년 원본, 승인 중첩 자료, 독립 표본 정확도, 공통 결과 등록은 기존 `BLOCKED` 상태를 유지한다.

**Q. STEP 03은 실제 문서 embedding을 사용합니까?**

LANDY 공식 문서 14건의 실제 passage 286개를 고정 E5 INT8 ONNX로 768차원화해 pgvector에서 dataset 범위로 검색한다. 합성 fixture가 아니라 Staging release의 실제 corpus 경로다.

**Q. kind가 로컬 파일을 읽은 것은 아닙니까?**

`kind-remote-source.log`에서 source mount 없이 PostGIS 경계가 제공됨을 확인했다. 지도·문서·모델은 고정 PostgreSQL·SeaweedFS binding으로 조회한다.

**Q. Compose와 kind 결과는 몇 개까지 비교했습니까?**

3 RAG·8 GIS·2 차단 응답 13개, PostGIS 경계, S3 지도 자산 해시를 비교해 모두 일치했다.

**Q. STEP 04의 `lake` 연결이 끊기면 자동으로 local 파일을 읽습니까?**

운영 `lake` 모드는 연결 실패를 `GEOLLM_STORAGE_UNAVAILABLE`로 차단하고 수치·인용·지도 주소를 비운다. 로컬 fallback으로 오류를 숨기지 않는다.

**Q. 원격 E5 모델이 cache에 있으면 S3 검증을 생략합니까?**

생략하지 않는다. 검증된 cache를 재사용할 때도 release의 SeaweedFS binding과 SHA attestation을 확인한다.

**Q. STEP 04는 어디까지 실제 화면에서 확인했습니까?**

R2의 Compose 5280·kind 5281 전체 Edge와 API 13개·지도 SHA 동등성, 격리 local 6건, 실제 DB/S3 장애 각 6건 차단을 확인했다. 최초 R1 kind cold 재시도 504는 관측 실패로 보존하며 재초기화 순서는 18 PASS의 `TESTED_SYNTHETIC` 범위다.
