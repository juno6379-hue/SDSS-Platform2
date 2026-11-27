# GeoLLM 반텐 토지피복 질의응답 이해자료

- updated_at: 2026-11-27 KST
- source_commit: `UNCOMMITTED_WORKTREE`
- evidence_paths:
  - `docs/lcluc/GEOLLM_QUERY.md`
  - `services/api/lcluc_geollm.py`
  - `services/lcluc/question.py`
  - `tests/lcluc/test_geollm_query.py`
  - `artifacts/lcluc/geollm-edge.log`
- overall_status: `VERIFIED_REAL`

## 1. 쉬운 설명

### 한 문장으로

GeoLLM 토지피복 질의응답은 한국어·인도네시아어·영어 질문을 문서 근거 검색 또는 고정 수치·공간 도구로 보내고, 출처·버전·SHA·제한사항과 함께 답한다.

### 현재 확인된 범위

- `VERIFIED_REAL`: MapBiomas 방법론 질문은 공식 RAG 원문과 페이지 인용을 반환한다.
- `VERIFIED_REAL`: MapBiomas 면적·순변화는 `COVERAGE`, 두 시점 전이·산림 총전환은 `TRANSITION` 발행 자료에서 계산한다.
- `VERIFIED_REAL`: Esri 면적·전이는 고정 v003 COG와 반텐 등적 격자 집계를 사용하고 실제 전이 PNG를 표시한다.
- `VERIFIED_REAL`: Edge에서 한국어·인도네시아어·영어 문서·수치 질의, 지도·출처·버전·SHA를 확인했다.
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

## 4. 시험 증거와 상태

| 항목 | 상태 | 증거와 범위 |
|---|---|---|
| 다국어 RAG | `VERIFIED_REAL` | Edge 한국어·인도네시아어·영어 공식 인용 |
| MapBiomas 논 면적 | `VERIFIED_REAL` | 2024 반텐 195,653.67ha, Collection 4.1 `COVERAGE` |
| 산림 총전환 | `VERIFIED_REAL` | 2023→2024 3,146.85ha, `TRANSITION` 산림→비산림 |
| 산림 순변화 | `VERIFIED_REAL` | 2023→2024 −1,265.58ha, `COVERAGE` 종료−시작 |
| MapBiomas 산림→시가지 | `VERIFIED_REAL` | 2023→2024 102.63ha |
| Esri 수목→시가지 | `VERIFIED_REAL` | 2023→2024 3,561.79ha, v003 실제 전이 PNG |
| 질문 계약시험 | `TESTED_SYNTHETIC` | 다국어 intent, 총전환·순변화 분리, margin 불일치·미발행 값·기간 차단 |
| Kemenhut 질의 | `BLOCKED` | `KEMENHUT_ASSET_NOT_READY` |
| 중첩 질의 | `BLOCKED` | `OVERLAY_ASSET_NOT_READY` |
| 독립 정확도 | `BLOCKED` | 독립 현장·전문가 판독 표본 미연결 |
| 결과 registry | `BLOCKED` | 응답 `result_id=null`, 등록·검토 흐름 미연결 |

## 5. 발표 스크립트

### 1분

“GeoLLM 토지피복 질의응답은 한국어·인도네시아어·영어 질문을 문서 근거 검색과 고정 수치·공간 도구로 나눕니다. MapBiomas 방법론은 원문 페이지를 인용하고, 면적과 전이는 Collection 4.1 XLSX의 SHA를 확인한 뒤 계산합니다. 2023→2024 산림 총전환은 3,146.85헥타르이고 산림 순변화는 마이너스 1,265.58헥타르로 서로 다른 지표입니다. Esri 수목→시가지 3,561.79헥타르는 실제 전이 PNG와 함께 확인했습니다. MapBiomas 화면 경계는 위치 맥락이고 발행 통계의 지리 범위와 구분합니다. Kemenhut·중첩·독립 정확도·결과 등록은 아직 차단 상태입니다.”

### 5분 핵심 순서

1. 질문에서 언어와 관계없이 지역·연도·제품·클래스·지표를 추출한다.
2. 방법론 질문은 SHA 고정 원문 RAG로 보낸다.
3. 수치 질문은 RAG가 아니라 제품별 정형 도구로 보낸다.
4. MapBiomas `COVERAGE`와 `TRANSITION`을 구분한다.
5. 총전환과 순변화를 서로 다른 지표로 보고한다.
6. Esri는 실제 COG·등적 격자·전이 PNG를 사용한다.
7. MapBiomas의 발행 경계와 One Map 맥락 경계를 구분한다.
8. Kemenhut·중첩·독립 정확도·result registry는 증거가 생길 때까지 차단한다.

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
