# 반텐 Sentinel-2 Explore

기존 LCLUC 화면에서 반텐·주 전체 참조를 고른 뒤 지도 우측 **지도 자료 → Sentinel-2 L2A**를 선택한다. 기준 연도와 비교 연도는 기존 필터에서 정한다. 2020~2025 보존 원본을 사용한다.

**Sentinel-2 레이어**를 접거나 펼칠 수 있다. 영상 조합은 비교 지도 양쪽에 적용하며, 중첩 네 가지는 스위치로 제어한다. **Sentinel-2 L2A**를 선택하면 기존 두 칸 구조의 지도 옆에 **클래스 면적·비율**과 **AI 신규 분류**가 배치된다. 지도 행 아래에는 **전이행렬**, **세부 변화탐지**, **장기 추세**, **제품 간 검증**이 각각 카드로 표시된다. 상단 분석 메뉴의 각 항목은 해당 지도 또는 카드로 스크롤과 키보드 초점을 옮긴다. **점 조회**와 **AOI 지정**은 지도 아래에 있다. **연차 토지피복도**를 선택하면 연차 메뉴와 기존 연차 카드가 표시된다.

| 화면 조작 | 결과 |
| --- | --- |
| 영상 조합 | 자연색 B04/B03/B02, 컬러 적외선 B08/B04/B03, NDVI, NDWI, NBR을 두 연도에 같은 조합으로 표시한다. Swipe 손잡이, Auto Play, 단일 보기, 시점 재생을 쓸 수 있다. |
| 스와이프 T1·T2 | 지도 하단에서 기준·비교 연도를 선택한다. 상단 연도 필터, 두 지도 및 선택 AOI의 면적과 전이 결과가 같은 연도쌍을 사용한다. 기준 연도보다 뒤의 비교 연도를 고를 수 있고, `50:50` 버튼은 두 지도의 분할을 중앙으로 맞춘다. |
| 토지피복 참조 | 각 시점의 Esri / Impact Observatory v003 분류도를 반투명으로 겹치고 클래스 색을 표시한다. |
| 연도쌍 변화탐지 | 두 해에 모두 유효하면서 Esri 분류 코드가 다른 위치를 분홍색으로 강조한다. Swipe에서는 비교 연도 쪽에서 확인한다. |
| 구름·그림자 마스크 | 합성 뒤에도 구름으로 남은 픽셀은 연한 노랑, 그림자는 보라, 기타 품질·관측 공백은 회색으로 표시한다. |
| 행정 경계 | 기존 One Map / BIG 행정경계와 지도 이름을 함께 조작한다. |
| 점 조회 | 지도 아래 **점 조회**를 누르고 지도 한 점을 클릭하면 두 연도의 NDVI·NDWI·NBR, 합성 QA, Esri 분류 코드를 조회한다. |
| AOI 지정 / 결과 다운로드 | 반텐 전체가 기본 AOI다. **AOI 지정**으로 지도에서 맞은편 두 모서리를 고르면 반텐 경계와의 교집합을 계산한다. 선택한 두 해의 클래스 면적·비율, 전이행렬과 연속 연도쌍 변화를 조회하고 지도 아래 **결과 다운로드**에서 내려받을 수 있다. |

## 결과 화면

**연차 토지피복 주요 지표**와 **연차 토지피복 주요 전이**는 선택한 연도쌍의 Esri v003 반텐주 전체 통계다. 각 카드에 출처, 범위, 연도쌍을 표시한다. **Sentinel-2 · AOI 분석**에서 영상·지수·품질은 Sentinel-2 L2A이고, 클래스 면적·비율과 전이행렬은 선택 AOI의 Esri v003 10m 분류에서 계산한다. 분홍색 변화 중첩도 두 연도의 Esri 분류에 근거한다.

| 탭 | 범위 및 사용법 |
| --- | --- |
| 클래스 면적·비율 | 각 연도의 Esri 유효 분류 면적을 기준으로 비율을 계산한다. |
| 전이행렬 | 행은 시작 연도, 열은 종료 연도이고 대각선은 공통 유효 픽셀의 유지 면적이다. 전이 면적을 누르면 지도에서 해당 전이를 강조한다. |
| 세부 변화탐지 | 전이 면적 순위, 출발 클래스 필터, 전체 변화 면적 대비 비율, 연속 연도별 공통 유효·변화 면적을 조회한다. 지도 **전체 전이 표시**로 필터를 해제한다. |
| AI 신규 분류 | 운영 연차 API의 실자료만 읽는다. 후보 학습·추론, 독립 검증 상태 및 처리 증거는 실제 연차 작업에서 조회한다. 동년 학습 라벨·학습 승인·별도 독립 표본이 필요한 단계는 접수 상태로 표시한다. |
| 장기 추세 | MapBiomas Indonesia Collection 4.1 발행 주 통계의 반텐 35년(1990~2024)·11개 클래스를 조회한다. 발행 경계·분류체계를 사용하며 지도에서 지정한 사각형과 Esri 보고서 경계는 적용하지 않는다. |
| 제품 간 검증 | 반텐 전체에 대한 2021년 Esri v003↔ESA WorldCover v200의 6개 대분류 일치도와 면적 행렬, 2020~2025년 Sentinel-2 및 Landsat 맑은 관측의 Esri 유효 범위 겹침을 조회한다. 독립 표본 정확도는 미측정이다. |

MapBiomas는 발행처의 `COVERAGE` 시트에서 `Indonesia / Jawa / Banten`인 11개 행을 취했다. 원본 SHA-256, 버전, 취득일과 35년 값은 결과 JSON에 들어 있다. 원본은 `data/raw/explorer/banten/mapbiomas/4.1`에 보존했다. [MapBiomas 발행 통계](https://landy.mapbiomas.id/en/statistics) · [발행처 이용 조건](https://landy.mapbiomas.id/en/termsofuse)

WorldCover 2021 v200 원본은 `data/raw/explorer/banten/worldcover/2021`에 두 개 타일로 보존했다. Esri 2021과 같은 EPSG:6933 10m 격자에서 WorldCover를 최근린으로 정합했다. 공통 유효 분류 면적 935,545.90ha 가운데 같은 대응표를 쓸 수 있는 926,628.52ha를 비교했다. 습지·맹그로브·눈 또는 얼음·이끼/지의류가 포함된 대응표 제외 면적은 8,917.38ha다. 계산은 2021년 한 해의 지도 일치도이며 분류 정확도는 별도 독립 참조가 필요하다. [ESA WorldCover 2021 v200](https://doi.org/10.5281/zenodo.7254221)

## 자료와 격자

- **Sentinel-2 영상과 지수**는 읽기 전용 보존 원본 32장면에서 B02·B03·B04·B08(10m), B11·B12·SCL(20m)의 SHA를 확인한 뒤 30m EPSG:6933 격자에 최근접 정합해 산출한다. 출처 STAC의 스케일·오프셋으로 반사도를 만들고 SCL 4·5·6과 6밴드 동시 유효 조건을 적용한다. 같은 연도의 승인 장면을 날짜와 장면 ID 순서로 읽어 픽셀별 첫 유효 관측을 쓴다. [Copernicus L2A 규격](https://sentiwiki.copernicus.eu/web/s2-products) · [밴드 조합과 식생·수체 지수](https://sentiwiki.copernicus.eu/web/s2-applications)
- NDVI는 (B08−B04)/(B08+B04), NDWI는 (B03−B08)/(B03+B08), NBR은 (B08−B12)/(B08+B12)다. 음수 반사도나 분모가 0인 픽셀의 지수는 공백으로 표시한다. NBR은 해당 날짜의 분광 지수다. [USGS NBR 정의](https://burnseverity.cr.usgs.gov/glossary)
- **토지피복·변화**는 Esri / Impact Observatory v003의 해당 연도 분류 결과다. 10m EPSG:6933 격자에서 One Map 경계 안의 픽셀 중심을 사용하며 구름·NoData를 분모에서 제외한다. 클래스 비율의 분모는 해당 연도의 유효 면적이고 변화율의 분모는 두 연도 공통 유효 면적이다. 화면의 반투명 겹침은 광학 영상 위의 참조 표시다. 독립 정확도는 미측정으로 표시한다.
- 지도 PNG는 화면용 Web Mercator 파생본이다. GeoTIFF는 분석용 격자이며 반텐 전체 범위로 내려받는다. 사용자가 그린 AOI의 수치 결과와 전이행렬은 CSV·JSON에 들어간다.

## 처리 모듈

| 단계 | 구현 |
| --- | --- |
| 장면 선정·원본 보존 | [관측 후보와 AOI](../../services/lcluc/province_optical_plan.py)가 장면·밴드를 고정한다. [Sentinel-2 수집기](../../services/lcluc/banten_sentinel_native.py)는 원본과 네이티브 CRS·해상도·SHA 영수증을 보존한다. |
| 품질·정합·연차 합성 | [파생본 발행기](../../services/lcluc/banten_sentinel_explorer.py)의 `scene_inputs`, `read_vrt`, `spectral_block`이 핀 검증, 정합, SCL 기준 합성과 지수 계산을 맡는다. [연차 워커의 래스터 도구](../../services/lcluc/annual_rasters.py)에서 창 단위 처리·저장 도구를 공유한다. |
| 참조 분석 | [AOI 통계·위치 조회](../../services/lcluc/banten_sentinel_statistics.py)는 Esri 10m 분류판독, 비율·전이 계산과 두 시점 위치 조회를 처리한다. |
| 조회·화면 | [Explore API](../../services/api/lcluc_sentinel_explorer.py)가 파생물 해시를 확인하고 제공한다. [Sentinel-2 화면 컴포넌트](../../frontend/src/LclucSentinelExplorer.tsx)는 기존 지도에서 사용자 도구와 API를 연결한다. |

## API와 결과 파일

기존 로컬 same-origin API의 `/api/lcluc/banten-sentinel-explorer`에서 준비된 연도·변화쌍을 조회한다. `/years/{year}/layers/{layer}`는 PNG·GeoTIFF, `/years/{year}/metadata`는 원본·셀 크기·QA·SHA-256, `/change/{start}/{end}/{kind}`는 지도 중첩 PNG 또는 변화 TIFF를 제공한다. `/statistics`는 기준·비교 연도와 선택 `bbox=west,south,east,north`를 받아 JSON·CSV를 반환한다. `/point`는 같은 위치의 두 연도 값을 조회한다.

분광 GeoTIFF의 밴드 순서는 B02·B03·B04·B08·B11·B12·NDVI·NDWI·NBR·QA다. QA는 0 유효 합성, 1 잔여 구름, 2 잔여 그림자, 3 기타 관측 공백이며 분석 경계 밖은 NaN이다. 변화 GeoTIFF는 0 공통 유효 범위 밖, 1 분류 유지, 2 분류 변화를 나타낸다.

파생본은 `data/curated/explorer/banten-province/sentinel-explore`에 저장한다. 프로젝트 루트의 로컬 보존 원본으로 `python -m services.lcluc.banten_sentinel_explorer spectral`, `reference`, `change` 순서로 발행한다. `spectral`과 `reference`는 독립 실행할 수 있으며 `change`는 분류 파일을 사용한다.

같은 경로 접두어 아래 `/years/{year}/layers/{layer}?thumbnail=1`은 72×48 이내 미리보기, `/transition/{start}/{end}?from_class=…&to_class=…&bbox=…`는 선택 전이의 지도 PNG를 반환한다. 두 해의 고정 Esri 10m TIFF에서 최근린으로 지도 표시 격자에 투영하며, 면적은 원래 10m 값에서 계산한다. `/historical-trend?download=1`은 MapBiomas JSON, `/product-support`는 동년 제품의 범위와 일치도 증거다.

장기·제품 비교 증거의 재발행 명령은 다음과 같다.

```powershell
python -m pip install ".[geo,lcluc-import]"
python -m services.lcluc.banten_historical_trend data/raw/explorer/banten/mapbiomas/4.1/statistics_lulc_indonesia.xlsx --acquired-on 2026-11-26
python -m services.lcluc.banten_product_agreement data/raw/explorer/banten/worldcover/2021 --acquired-on 2026-11-26
```

## 검증 근거

- `VERIFIED_REAL` Edge 1650px에서 연차 토지피복과 Sentinel-2 지도의 폭은 각각 886.95px였다. 상단 지도 분석과 각 결과 카드의 이동·키보드 초점을 확인했다. 920px에서는 하단 카드가 세로로 놓였다. 스와이프 T1·T2에서 2022→2024를 선택해 상단 필터, 양쪽 지도, AOI API·면적표·전이행렬 및 50:50 복귀를 검증했다. Sentinel-2 범례의 행정경계 스위치와 지도 아래 점 조회 버튼을 확인했다. [최종 Edge 시험](../../artifacts/lcluc/sentinel-workspace-final-edge.log) · [지도·카드 화면](../../artifacts/lcluc/sentinel-map-side-cards.png)
- `VERIFIED_REAL` Edge 5175에서 Sentinel-2로 전환하자 기존 연차 카드가 사라지고 면적·비율과 전이행렬 카드가 함께 열렸다. 1650px에서는 두 카드와 표의 상단을 나란히 맞췄고 920px에서는 위아래로 배치했다. 연차 토지피복도에서 기존 카드가 다시 표시됐다. Sentinel-2 재선택 시 63,176.20ha AOI를 유지했고 2024→2025 선택으로 표를 갱신했다. [레이어별 카드 시험](../../artifacts/lcluc/sentinel-layer-card-layout-edge.log) · [두 카드 화면](../../artifacts/lcluc/sentinel-aligned-results.png)
- `VERIFIED_REAL` **입력·Expert**에서 지도 자료를 Sentinel-2 L2A로 선택하자 지도 바로 아래에 상세 결과가 나타났다. **실제 결과·보고서**에서도 같은 패널 하나와 선택 AOI를 표시한다. Landsat·연차 토지피복도로 전환하면 패널이 닫힌다. Sentinel-2를 다시 선택하자 52,128.16ha AOI가 복원됐으며 연도를 2024→2025로 바꾸면 면적표가 새 연도로 바뀌었다. [레이어 전환 검증](../../artifacts/lcluc/sentinel-layer-bound-details-edge.log) · [지도 하단 상세 결과](../../artifacts/lcluc/sentinel-auto-details.png)
- `VERIFIED_REAL` Edge 5175에서 레이어 목록 접기·펴기, 5개 조합의 실제 PNG 응답, 중첩 4종, 면적표, 전이 셀의 지도 요청, 클래스 필터, 연차 AI 운영 상태, 35년 원본 해시가 포함된 다운로드, 2021 제품 일치 행렬을 확인했다. 결과 화면의 **AOI 지정**에서 지도에 표시한 52,128.16ha가 결과표에도 반영됐다. 화면과 API에서 2021년의 80.95%를 대조했다. [최종 API·Edge 시험 기록](../../artifacts/lcluc/sentinel-results-final.log) · [최종 레이어 목록](../../artifacts/lcluc/sentinel-layer-list-detail.png)
- `TESTED_SYNTHETIC` 방향이 반대인 전이와 NoData를 제외하고 사각형 안의 픽셀만 선택하는 회귀시험을 추가했다. [회귀 시험](../../tests/lcluc/test_banten_sentinel_explorer.py)
- Sentinel‑2 실자료 32장면으로 6개 연도의 분광 GeoTIFF와 PNG 36개를 발행했다. GeoTIFF는 EPSG:6933, 30m, 10채널이며 6개년의 QA 영역 픽셀 수를 대조했다. 실제 API 응답에서 PNG의 SHA-256, 지수 공식과 지점값, 사각형 면적·분류 비율·전이 합계, 변화 TIFF 해시와 10m 격자를 확인했다. [발행 검산 로그](../../artifacts/lcluc/sentinel-explore-published.log) · [API·Edge 시험 기록](../../artifacts/lcluc/sentinel-explore-final-e2e.log)
- Esri 10m 분류 6개년을 연도별 감사 면적에 맞춰 확인했다. 15개 변화 GeoTIFF 각각의 공통 유효 픽셀 수와 변화 픽셀 수를 기존 검산값에 대조했다. 2020→2025 변화는 78,998.91ha이고 2024→2025 변화는 52,005.52ha다. [변화 발행 로그](../../artifacts/lcluc/sentinel-explore-change.log)
- Edge 5175에서 2020↔2025 영상 조합 5종, 참조·변화·품질 중첩, 클래스 범례·행정경계 및 Swipe 조작을 확인했다. 두 연도의 Explore 값, 지도에서 선택한 53,155.27ha 사각형 AOI, 연속 연도쌍 변화 5건과 112행 CSV 다운로드를 확인했다. 시작 연도를 2024년으로 바꿔 NBR 선택과 정확한 2024→2025 변화 연결도 확인했다. [Edge 시험 기록](../../artifacts/lcluc/sentinel-explore-final-e2e.log) · [지도 화면](../../artifacts/lcluc/sentinel-explore-swipe.png) · [AOI 화면](../../artifacts/lcluc/sentinel-explore-aoi.png)
- 합성 단위 시험 두 건에서 구름 픽셀 대체와 동일 관측의 6밴드 유지, 두 연도 사이 구름·NoData 전이 제외를 확인했다. [회귀 시험 코드](../../tests/lcluc/test_banten_sentinel_explorer.py)
