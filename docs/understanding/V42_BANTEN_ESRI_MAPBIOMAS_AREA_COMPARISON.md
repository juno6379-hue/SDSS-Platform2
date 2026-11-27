# 반텐 토지피복 원본별 집계와 공식 비교 기준 이해자료

- updated_at: 2026-11-26 KST
- source_commit: `UNCOMMITTED_WORKTREE`
- evidence_paths:
  - `docs/lcluc/BANTEN_MAPBIOMAS_AREA_COMPARISON.md`
  - `docs/lcluc/MAPBIOMAS_GEOLLM_KNOWLEDGE.md`
  - `services/api/lcluc_sentinel_explorer.py`
  - `frontend/src/LclucBantenAreaComparison.tsx`
  - `artifacts/lcluc/banten-native-area-edge.log`
- overall_status: `VERIFIED_REAL`

## 1. 쉬운 설명

### 한 문장으로

같은 반텐·같은 연도의 Esri 원본 9개 클래스와 MapBiomas 공식 발행 11개 클래스를 각각의 정의와 총계로 나란히 보여 주고, 공식 사업 비교는 Kemenhut 동년 23클래스 입고 뒤 수행한다.

### 현재 확인된 범위

- `VERIFIED_REAL`: 공통 발행 연도 2020~2024를 API에서 제공하고 Edge에서 2020과 2024 선택을 확인했다.
- `VERIFIED_REAL`: Esri 원본 9행과 MapBiomas 발행 11행을 별도 표로 표시한다. 클래스별 차이 열은 제공하지 않는다.
- `VERIFIED_REAL`: 2024 Esri TIFF 재집계 경계 격자는 935,602.88ha이며 분류 유효 935,224.83ha, 구름 378.05ha, NoData 0ha다.
- `VERIFIED_REAL`: 2024 MapBiomas Collection 4.1 공식 반텐주 발행 통계 합계는 935,005.55ha다.
- `BLOCKED`: Kemenhut 동년 Penutupan Lahan 23클래스 연차 원본의 발행판·범위·권리·SHA 입고가 공식 비교 시작 조건이다.
- `BLOCKED`: 독립 정확도는 학습과 기관 참조에서 분리한 현장·전문가 판독 표본이 필요하다.

## 2. 이론적 배경

### 2.1 원본 분류체계 보존

Esri는 One Map 반텐 경계 안 EPSG:6933 10m 픽셀 중심 집계이고, MapBiomas는 Collection 4.1 XLSX가 발행한 반텐 주 통계다. Esri 9개 코드와 MapBiomas 11개 클래스는 의미 범위가 다르므로 각 원본 표를 그대로 보존한다. Esri 수목과 MapBiomas 산림·맹그로브, Esri 초지·관목지와 MapBiomas 비산림 자연식생을 동일 클래스로 단정하지 않는다.

### 2.2 피복 구성과 총계

Esri 경계 격자 총면적은 분류 유효, 구름, NoData의 합이다.

`935,602.88 = 935,224.83 + 378.05 + 0.00 ha`

MapBiomas 935,005.55ha는 발행 XLSX의 11개 클래스 합계다. 두 총계는 경계·격자·분류 정의가 달라 동일 클래스나 토지전환 수치로 사용하지 않는다.

### 2.3 공식 비교 기준과 독립 정확도

사용자 결정에 따라 Kemenhut의 동년 Penutupan Lahan 23클래스를 공식 사업 비교 기준으로 사용한다. 공식 참조 비교는 승인된 One Map 경계, 같은 관측연도, 공통 등적 격자와 공통 유효 영역에서 수행한다. 독립 정확도는 Kemenhut 지도와 분리된 현장·전문가 판독 표본으로 산출한다.

## 3. 코드·데이터 동작

1. API가 Esri 연차 감사 JSON과 MapBiomas 발행 XLSX 파생 JSON을 읽는다.
2. 반텐 region, One Map 경계 SHA, Esri TIFF SHA, MapBiomas workbook SHA를 검사한다.
3. 공통 연도 2020~2024를 구하고 미지정 시 최신 2024를 선택한다.
4. Esri 9개 원본 행과 경계 격자·유효·구름·NoData를 계산한다.
5. MapBiomas 11개 발행 클래스와 합계를 원본 명칭으로 제공한다.
6. UI가 두 표를 별도로 표시하며 클래스 차이와 전이 수치를 만들지 않는다.

| API | 역할 |
|---|---|
| `GET /api/lcluc/banten-sentinel-explorer/mapbiomas-area-comparison` | 최신 공통연도의 두 원본별 집계 |
| `GET .../mapbiomas-area-comparison?year=2020` | 지정 공통연도의 두 원본별 집계 |
| 공통연도 밖 요청 | HTTP 422 |

## 4. LANDY 확보 범위와 시험 증거

### LANDY 자료 세 범주

| 범주 | 상태 | 현재 범위 |
|---|---|---|
| 문서형 지식자료 | `VERIFIED_REAL` | R01~R14 원문, P0 9건, 286청크, 원문 SHA·페이지 인용 |
| 정량 통계자료 | `VERIFIED_REAL` | Collection 4.1 원본 XLSX와 반텐 1990~2024 35년·11클래스 연결 |
| 발행 전이 원본 | `VERIFIED_REAL` | Collection 4.1 XLSX의 `TRANSITION`에서 반텐 113행과 발행 기간 열을 확인했다. 정제·API 연결은 다음 작업이다. |
| 공간 분석자료 | `BLOCKED` | 반텐 4.1 분류·전이 GeoTIFF와 모자이크는 미입고다. |

### 기능별 증거

| 항목 | 상태 | 증거와 범위 |
|---|---|---|
| 실제 API | `VERIFIED_REAL` | Esri 원본 9행, MapBiomas 발행 11행, 2024 피복 구성과 source SHA |
| 실제 Edge | `VERIFIED_REAL` | 별도 두 표, 차이 열 없음, 2020·2024 연도 선택 |
| 2024 Esri 피복 | `VERIFIED_REAL` | 935,602.88ha = 유효 935,224.83ha + 구름 378.05ha + NoData 0ha |
| 2024 MapBiomas 발행 통계 | `VERIFIED_REAL` | 935,005.55ha, 11개 발행 클래스 합계 |
| Kemenhut 동년 23클래스 | `BLOCKED` | 연차 원본·범위·발행판·허용범위·SHA 입고 대기 |
| 독립 정확도 | `BLOCKED` | 독립 현장·전문가 판독 표본 미확보 |

## 5. 발표 스크립트

### 1분

“반텐의 Esri 원본 9개 클래스와 MapBiomas 공식 발행 11개 클래스를 공통 연도 2020~2024에서 각각 표시합니다. 2024 Esri 경계 격자 935,602.88헥타르는 분류 유효 935,224.83헥타르와 구름 378.05헥타르로 구성되며 NoData는 0입니다. MapBiomas 발행 통계 합계는 935,005.55헥타르입니다. 두 제품은 경계·격자·분류 정의가 달라 클래스 차이와 토지전환 수치로 제시하지 않습니다. 공식 사업 비교 기준은 Kemenhut 동년 Penutupan Lahan 23클래스이고, 독립 정확도는 별도 현장·전문가 표본으로 평가합니다.”

### 5분 핵심 순서

1. Esri 9행과 MapBiomas 11행을 원본 분류체계로 보존한다.
2. 공통 발행 연도 2020~2024만 선택한다.
3. Esri 경계 격자를 유효·구름·NoData로 분해한다.
4. MapBiomas는 XLSX 발행 11개 클래스와 총계를 제공한다.
5. 두 표 사이에 임의 crosswalk 차이 또는 전이 값을 만들지 않는다.
6. Kemenhut 동년 23클래스를 공통 격자로 입고한 뒤 공식 비교를 수행한다.
7. 독립 정확도는 별도 조사 표본으로 평가한다.

## 6. Q&A

**Q. 935,602.88ha와 935,005.55ha의 차이를 정확도 오차로 볼 수 있습니까?**

각각 Esri 경계 격자와 MapBiomas 발행 통계의 총계다. 경계·격자·분류 정의가 달라 정확도 오차나 토지전환 수치로 사용하지 않는다.

**Q. 왜 Esri 9행과 MapBiomas 11행을 합치지 않습니까?**

원본 클래스의 의미와 범위가 다르다. 각 제품의 원래 코드를 보존하고, 공식 crosswalk는 Kemenhut 동년 자료 입고 뒤 검토한다.

**Q. 공식 비교 기준은 무엇입니까?**

Kemenhut의 같은 해 Penutupan Lahan 23클래스다. 반텐 전역·APL 포함 여부, 발행판, 이용 권리와 SHA를 입고 시 확인한다.

**Q. 독립 정확도는 무엇으로 측정합니까?**

학습과 Kemenhut 공식 참조에서 분리된 현장 조사 또는 독립 전문가 판독 표본을 사용한다.
