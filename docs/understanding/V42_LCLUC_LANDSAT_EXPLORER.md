# 반텐 Landsat 장기 분석 Explorer 이해자료

- updated_at: 2026-11-26 KST
- source_commit: `UNCOMMITTED_WORKTREE`
- evidence_paths:
  - `docs/lcluc/LANDSAT_EXPLORER.md`
  - `services/lcluc/banten_landsat_explorer.py`
  - `services/lcluc/banten_landsat_history.py`
  - `services/lcluc/banten_landsat_baseline.py`
  - `services/api/lcluc_landsat_explorer.py`
  - `frontend/src/LclucLandsatExplorer.tsx`
  - `tests/lcluc/test_landsat_explorer.py`
  - `artifacts/lcluc/landsat-explorer-edge-final.log`
  - `data/curated/explorer/banten-province/landsat-explore/*/manifest.json`
  - `data/curated/explorer/banten-province/landsat-explore/rf-report.json`
- overall_status: `VERIFIED_REAL`

## 1. 쉬운 설명

### 한 문장으로

반텐 Landsat Explorer는 USGS Landsat Collection 2 Level-2 원본을 센서별 밴드와 품질 규칙으로 맞춘 뒤, 실제 영상 7종·관측 품질·NDVI 변화·장기 주 통계·시험 RF 근거를 기존 LCLUC Workspace에서 함께 보여 주는 읽기 전용 분석 화면이다.

### 현재 확인된 범위

- `VERIFIED_REAL`: 2020~2025 Landsat 24장면을 연차별 4장면씩 발행했다.
- `VERIFIED_REAL`: Natural Color, Agriculture, Urban, SWIR, NDVI, NDMI, MNDWI의 실제 PNG 7종을 API와 Edge에서 확인했다.
- `VERIFIED_REAL`: 2020~2022 합성은 반텐 격자의 97.86166884524681%에 맑은 관측이 한 번 이상 있고 90.57607397959761%에 두 번 이상 있다.
- `VERIFIED_REAL`: 2023~2025 합성은 맑은 관측 1회 이상 99.8192193811322%, 2회 이상 98.01073356606761%다.
- `VERIFIED_REAL`: 2020 RF는 실제 Landsat 6밴드와 동년 Esri v003 약한 참조를 사용했다. 공간 블록 홀드아웃 72,391픽셀의 약한 참조 일치도는 71.42048044646434%다.
- `VERIFIED_REAL`: MapBiomas Indonesia Collection 4.1의 반텐 발행 주 통계 1990~2024 35개년·11개 클래스를 장기 추세로 표시한다.
- `VERIFIED_REAL`: 1650px Edge에서 Landsat 지도 폭 886.95px, 실제 PNG 요청, 7개 preset, 품질·추세·변화 시기·RF 근거를 확인했다. 역사 구간은 1990→2020 Swipe와 1990·2000·2010·2020 Time-Series frame을 확인했고 자동재생은 시작점부터 순서대로 진행해 T2에서 정지했다.
- `VERIFIED_REAL`: 과거 단일 장면 시범은 1988 47.88%, 1990 50.83%, 2000 40.30%, 2010 32.14%의 반텐 맑은 관측을 발행했다. 네 Landsat 5 TM 원본의 합계는 1,257,798,910 bytes이며 manifest·API·원본 SHA를 대조했다.
- `TESTED_SYNTHETIC`: TM·ETM+·OLI 밴드 대응, 구름·권운·포화 QA, 관측 수, NoData 전파를 2개 단위시험으로 확인했다.
- `BLOCKED`: 독립 현장 정확도와 기관 승인 해석.
- `PLANNED`: 조밀한 픽셀 시계열의 변화 발생시점, LandTrendr·CCDC 비교.

## 2. 이론적 배경

### 2.1 센서 세대별 밴드 대응

Landsat 4/5 TM과 Landsat 7 ETM+는 Blue·Green·Red·NIR·SWIR1·SWIR2에 B1·B2·B3·B4·B5·B7을 사용한다. Landsat 8/9 OLI 계열은 B2·B3·B4·B5·B6·B7을 사용한다. 코드는 센서 ID별 대응표를 먼저 확인한 뒤 동일한 여섯 표준 역할로 배열한다.

Collection 2 Level-2 표면반사도는 다음 식으로 변환한다.

`reflectance = DN × 0.0000275 − 0.2`

### 2.2 품질 mask와 NoData

`QA_PIXEL`의 fill, dilated cloud, cloud, cloud shadow, snow를 제외한다. OLI 계열에는 cirrus bit를 적용하고 과거 단일 장면의 `QA_RADSAT`에는 포화·드롭 픽셀을 적용한다. 모든 밴드와 반텐 경계가 유효한 픽셀만 합성에 참여한다. 유효 관측이 0인 셀은 NoData로 유지한다.

### 2.3 합성과 지수

연차 영상은 맑은 장면의 밴드별 중앙값이다. 3~5년 기간 영상은 연차 합성들의 중앙값이며 `CLEAR_OBSERVATIONS`는 연차 관측 수의 합이다.

- NDVI = `(NIR − Red) / (NIR + Red)`
- NDMI = `(NIR − SWIR1) / (NIR + SWIR1)`
- MNDWI = `(Green − SWIR1) / (Green + SWIR1)`

NDVI 변화 layer는 두 연도 공통 유효 픽셀에서 `후기 NDVI − 기준 NDVI`를 계산한다. +0.20 이상은 증가, −0.20 이하는 감소 범주다.

### 2.4 공간 블록 홀드아웃과 약한 참조

시험 RF는 2020 Landsat 6밴드와 2020 Esri v003을 사용한다. 48×48 표시 격자 블록을 학습·홀드아웃 중 하나에 먼저 배정해 인접 픽셀 누출을 줄였다. 71.42%는 같은 해 Esri 지도와의 약한 참조 일치도다. 독립 현장 표본 정확도는 미측정이다.

### 2.5 장기 주 통계와 픽셀 변화 발생시점

현재 장기 추세는 MapBiomas 발행 반텐 주 전체 통계에서 클래스별 1990~2024 순변화와 연속 연도의 최대 증가·감소 구간을 계산한다. 이는 주 단위 면적 변화다. 픽셀별 변화 발생시점은 더 조밀한 관측 시계열과 LandTrendr·CCDC 같은 시계열 알고리즘 검증이 필요한 후속 단계다.

## 3. 코드·데이터 동작

### 3.1 발행 파이프라인

1. `banten_landsat_explorer.py`가 보존 receipt의 장면·연도·6밴드·QA를 검사한다.
2. 센서별 밴드 대응과 품질 mask를 적용한다.
3. 반텐 경계 안 공통 표시 격자에서 연차 또는 기간 중앙값을 계산한다.
4. 7개 PNG와 여섯 반사도 밴드·`CLEAR_OBSERVATIONS` GeoTIFF를 만든다.
5. manifest에 경계 SHA, 장면 receipt, 관측률, 자산 byte와 SHA-256을 고정한다.

### 3.2 과거 단일 장면 시범

`banten_landsat_history.py`는 Planetary Computer STAC에서 5~11월, 반텐 bbox, Tier 1 후보를 조회한다. 계획된 첫 장면의 여섯 밴드·`QA_PIXEL`·`QA_RADSAT`을 저장하고 같은 발행 함수로 PNG·GeoTIFF·manifest를 만든다.

현재 실제 발행 상태는 다음과 같다.

| 연도 | 센서 | 상태 | 반텐 맑은 관측 |
|---|---|---|---:|
| 1988 | Landsat 5 TM | `VERIFIED_REAL` | 47.8785% |
| 1990 | Landsat 5 TM | `VERIFIED_REAL` | 50.83% |
| 2000 | Landsat 5 TM | `VERIFIED_REAL` | 40.2987% |
| 2010 | Landsat 5 TM | `VERIFIED_REAL` | 32.1434% |

### 3.3 API

| 경로 | 역할 |
|---|---|
| `GET /api/lcluc/banten-landsat` | 연차·기간 catalog, 관측률, 장면, 과거 조회 상태 |
| `GET /products/{period}` | 경계·원본·합성·자산 SHA manifest |
| `GET /products/{period}/{layer}` | 7개 PNG 또는 반사도 GeoTIFF |
| `GET /change/{start}/{end}` | 공통 유효 픽셀의 NDVI 변화 PNG |
| `GET /baseline` | RF 입력·split·약한 참조 평가 근거 |
| `GET /baseline/classification` | 시험 RF 분류 GeoTIFF |

API는 로컬 same-origin 읽기를 적용하고 등록 byte와 SHA-256이 다르면 409로 차단한다.

### 3.4 UI

지도 자료에서 Landsat을 선택하면 다음 기능을 사용한다.

- 7개 영상 preset
- T1·T2 Swipe와 NDVI 변화 overlay
- Time-Series 연도 재생
- 연차·기간 관측 품질표와 PNG·GeoTIFF 연결
- MapBiomas 장기 추세와 최대 변화 구간
- 2020 RF 약한 참조 평가와 분류 GeoTIFF

Edge에서 Landsat과 연차 비교의 지도 폭을 886.95px로 유지하고, Landsat을 벗어나 Sentinel-2·연차 토지피복으로 돌아가는 조작부 복원도 확인했다.

## 4. 시험 증거와 상태

| 항목 | 상태 | 증거와 범위 |
|---|---|---|
| 2020~2025 연차 발행 | `VERIFIED_REAL` | 24장면, 6개 연도, 연차별 7 PNG·GeoTIFF manifest |
| 2020~2022 기간 합성 | `VERIFIED_REAL` | 맑은 관측 1회 이상 97.8617%, 2회 이상 90.5761% |
| 2023~2025 기간 합성 | `VERIFIED_REAL` | 맑은 관측 1회 이상 99.8192%, 2회 이상 98.0107% |
| 7개 영상 preset·실 PNG | `VERIFIED_REAL` | API distinct PNG 7종과 Edge 실제 map request |
| Swipe·Time-Series | `VERIFIED_REAL` | 역사 구간 1990→2020 Swipe, 4개 재생 frame, 시작점 재실행·순차 진행·T2 정지 |
| Workspace 폭·복귀 | `VERIFIED_REAL` | 1650px 지도 886.95px, Sentinel·연차 조작부 복원 |
| MapBiomas 장기 추세 | `VERIFIED_REAL` | 발행 반텐 주 통계 1990~2024 35년·11클래스 |
| 2020 RF | `VERIFIED_REAL` | 학습 19,647, 공간 홀드아웃 72,391, 약한 참조 일치도 71.4205% |
| 1988·1990·2000·2010 시범 발행 | `VERIFIED_REAL` | Landsat 5 TM 각 1장면, 합계 1,257,798,910B, manifest·API·원본 SHA 검증 |
| 센서·QA·NoData 단위시험 | `TESTED_SYNTHETIC` | `tests/lcluc/test_landsat_explorer.py` 2건 |
| 픽셀 변화 발생시점 | `PLANNED` | 조밀한 시계열과 LandTrendr·CCDC 비교 필요 |
| 독립 정확도 | `BLOCKED` | 승인된 현장·전문가 독립 표본 미확보 |

## 5. 발표 스크립트

### 1분

“반텐 Landsat Explorer는 2020~2025 실제 24장면을 센서별 밴드와 QA 규칙으로 맞춰 Natural Color부터 MNDWI까지 7개 지도로 제공합니다. 2020~2022 합성은 맑은 관측 97.86%, 2023~2025 합성은 99.82%를 한 번 이상 확보했습니다. Edge에서 7개 preset, 886.95픽셀 지도 폭, 1990→2020 Swipe와 역사 Time-Series의 순차 재생·T2 정지를 확인했습니다. 2020 RF의 71.42%는 공간 블록 홀드아웃에서 Esri v003과 비교한 약한 참조 일치도이며 독립 정확도는 미측정입니다. 1988·1990·2000·2010 단일 장면은 manifest·API·원본 SHA 검증을 완료했습니다. MapBiomas는 1990~2024 반텐 주 발행 통계이며 픽셀 변화 발생시점과 LandTrendr·CCDC는 후속 단계입니다.”

### 5분 핵심 순서

1. TM·ETM+와 OLI의 밴드 번호를 여섯 표준 역할로 맞춘다.
2. Collection 2 Level-2 scale·offset과 QA_PIXEL·QA_RADSAT을 적용한다.
3. 연차 중앙값과 `CLEAR_OBSERVATIONS`로 관측 밀도를 함께 보존한다.
4. 7개 PNG는 화면 탐색, GeoTIFF는 수치·재현 근거 역할을 맡는다.
5. 2020~2025 24장면과 두 기간 합성의 맑은 관측 97.86%·99.82%를 실제 manifest로 확인했다.
6. RF는 공간 블록을 분리했고 71.42%를 약한 참조 일치도로 보고한다.
7. MapBiomas 35년 표는 발행 반텐 주 통계다.
8. 1988·1990·2000·2010 단일 장면 시범은 실제 발행·API·SHA 검증을 마쳤다.
9. 픽셀 변화 발생시점·LandTrendr·CCDC·독립 정확도는 후속 Gate다.

## 6. Q&A

**Q. 71.42%는 Landsat 분류의 독립 정확도입니까?**

2020 Landsat RF와 동년 Esri v003의 약한 참조 일치도다. 공간 블록 홀드아웃 72,391픽셀을 사용했고 독립 현장 표본 정확도는 미측정이다.

**Q. 97.86%는 분류 정확도입니까?**

2020~2022 기간 합성에서 맑은 관측이 한 번 이상 존재하는 반텐 격자 비율이다. 관측 피복 품질을 나타낸다.

**Q. MapBiomas 35년 표는 Landsat 픽셀을 다시 계산한 결과입니까?**

MapBiomas Indonesia Collection 4.1 발행자가 제공한 1990~2024 반텐 주 전체 통계다. Explorer의 Landsat 지수와 RF 결과는 별도 근거로 표시한다.

**Q. 1988·1990·2000·2010 자료는 반텐 전역 합성입니까?**

각 연도의 Landsat 5 TM 단일 장면 시범이다. 반텐 경계 안 맑은 관측 비율은 각각 47.88%, 50.83%, 40.30%, 32.14%이며 관측 공백은 NoData로 유지한다. 네 장면의 원본 합계는 1,257,798,910B다.

**Q. LandTrendr와 CCDC 결과를 볼 수 있습니까?**

현재 장기 표는 주 단위 연속 연도 면적 차이를 제공한다. 픽셀별 변화 발생시점과 LandTrendr·CCDC 비교는 `PLANNED`다.
