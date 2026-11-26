# 인도네시아 위성·토지피복 비교

[Esri Land Cover Explorer](https://livingatlas.arcgis.com/landcoverexplorer/)의 표시 방식과 [사용 가이드](https://www.esri.com/arcgis-blog/products/arcgis-living-atlas/imagery/global-land-cover-revealed)를 검토했다. SDSS에서는 기존 **LCLUC Workspace**의 지역·연도 필터, 7개 탭, 지도 조작부, 오른쪽 지표와 아래 결과 패널을 사용한다. 초기 선택 지역은 실제 비교가 등록된 반텐이다. 위성 자료 선택과 다운로드는 기존 지도 우측 범례에서 이용한다.

| 비교 기능 | SDSS 적용 |
|---|---|
| Swipe | 한 화면에서 같은 격자의 두 시점을 기본 50:50으로 표시한다. 중앙 손잡이를 이동하거나 Auto Play를 누른다. |
| Time-Series·Single View | 기존 시간 이동·재생으로 저장된 두 시점을 넘긴다. Single View는 기준 시점을 표시한다. |
| 클래스 필터 | Esri 연차층에는 원본 메타데이터의 9개 색을 적용한다. Clouds는 기본적으로 숨겨지며 별도로 표시할 수 있다. |
| 행정경계와 행정명 | Boundary 버튼으로 두 시점의 One Map / BIG 경계와 행정명을 함께 켜고 끈다. 6개 주 전체 버튼으로 사업 대상 전체를 보고 확대하면 군·시 행정명을 확인한다. 지도에서 클릭한 군·시 이름은 범례에 표시된다. |
| 통계·다운로드 | 고정 비교 구역의 공통 유효 면적을 분모로 분류 비중·전이·변화량을 표시한다. 검증 TIFF·CSV와 관측별 ZIP을 제공한다. |
| Imagery | 반텐 Sentinel-2·Landsat 8을 같은 범위에서 전환한다. 팔루 사건 모드에서는 자체 관측 날짜와 지역을 표시한다. |

지도에 등록된 영역은 고정 범위다. 지도 이동·확대에 따른 임의 영역의 서버 재집계와 한 해씩 이어지는 전 기간 재생은 후속 구현이다.

Sentinel-2 레이어에서는 반텐의 분광 영상 조합을 바꾸고 Esri 분류·연도쌍 변화와 품질 마스크를 겹쳐 볼 수 있다. 지도 클릭으로 위치 값을 조회하고 선택 사각형의 통계를 계산할 수 있다. [Sentinel-2 Explore 조작·자료·다운로드](SENTINEL_EXPLORER.md)

**Swipe → Auto Play**는 5초 동안 한 차례 재생한다. 분할선은 50%에서 시작해 85%, 15%를 지나고 50%에 도달하면 **재생 완료**가 표시된다. 버튼 옆에 남은 시간이 초 단위로 보인다. **Pause**는 분할선과 남은 시간을 함께 멈추며, **Resume**은 남은 구간을 이어서 재생한다. 분할선을 직접 조작하거나 표시 자료 및 모드를 바꾸면 진행 중인 재생이 중지된다. Edge 5175 반텐 실자료에서 브라우저 시계 5.10초와 각 조작을 확인했다. [시험 기록](../../artifacts/lcluc/swipe-autoplay-final-edge.log)

## 실제 확보 및 활용

| 자료 | 범위 | 보존 및 표시 |
|---|---|---|
| Esri / Impact Observatory v003 | 반텐 2020·2025의 공통 표본 | SHA가 있는 로컬 native crop 2개를 이관했다. 연차 합성 기간, 공개 배포 근거와 10m 등적 격자 파생본을 보존했다. 원본 코드에서 구름 10과 NoData 0을 제외한다. |
| Sentinel-2 L2A | 반텐 2020-06-28·2025-08-26 | Earth Search가 제공하는 동일 장면 B02·B03·B04·B08·B11·B12·SCL의 native crop 14개와 자산별 Range 영수증을 보존했다. |
| Landsat 8 Collection 2 Level-2 | 반텐 2020-08-28·2025-08-26 | Planetary Computer의 USGS 장면별 6밴드와 QA_PIXEL native crop 14개를 보존했다. 정렬 미리보기의 품질 통과 면적은 2020년 54.58%, 2025년 99.90%다. 마스크 제외 영역은 투명하다. |
| Disaster Imagery | 중앙술라웨시 팔루 2018-09-23·2018-10-02 | NASA Earth Observatory의 [사건 전후 JPEG](https://science.nasa.gov/earth/earth-observatory/devastation-in-palu-after-earthquake-tsunami-92836/) 두 장을 원본 바이트로 보존했다. 시각 판독에 사용한다. 지도 래스터나 피해 면적 측정 입력으로 등록하지 않는다. |
| Annual NLCD | 인도네시아 범위 없음 | [USGS NLCD](https://www.usgs.gov/centers/eros/science/annual-nlcd-data-access)의 미국 범위 제품이다. 인도네시아 연차 참조 자료는 Esri로 표시하며 KLHK 등록은 별도다. |

다운로드한 4개 관측의 TIFF는 원격 장면 전체 파일에서 네이티브 값과 위치를 유지해 자른 시험 창이다. Landsat와 Sentinel 관측의 미리보기는 같은 장소를 보기 위해 Esri 분석 격자로 정렬했으며 각 센서의 원래 공간 해상도는 native TIFF와 영수증에서 확인한다. 관측은 각 날짜의 영상이며 Esri 전역 연차 합성의 입력 장면을 재현하지 않는다.

- 원본·영수증 `data/raw/explorer/banten-2020-2025/`, `data/raw/explorer/palu-2018/`
- 정렬 미리보기·검증 ZIP `data/curated/explorer/`
- Esri 등록 입력 `data/raw/explorer/banten-2020-2025/esri/registered-pair.json`
- 고정 COG Range와 NASA JPEG의 성공 수신 본문 합계 43,393,967바이트. STAC 검색, 배포 근거와 예비 요청은 이 수치와 별도다.

## 행정경계와 레이어 확인

One Map / BIG의 2026-10-27 취득 스냅샷을 사용한다. 반텐 8개, 서자바 27개, 동자바 40개, 고론탈로 6개, 남술라웨시 25개, 남동술라웨시 23개로 6개 주와 군·시 129개를 표시한다. 지도 축척에 따라 주·군·시 이름을 표시하고 겹치는 이름은 지도 엔진의 충돌 처리로 일부 숨긴다. 6개 주 통합 화면은 지도를 그리기 위해 단순화한 경계를 사용한다. 주별 조회는 고정한 원본 경계와 해시를 반환한다. 행정경계는 지도 참조용이며 사업 통계 승인 상태는 대기다. 팔루 전후 비교는 위치 등록이 없는 발행 JPEG로 표시한다.

지도 범례의 **자료 및 사용처**와 **위성영상 수집현황 및 출처** 표에서 영상 장면과 용도를 확인한다. Esri 2020·2025 연차 GeoTIFF는 변화 면적과 전환행렬을 계산하는 데 사용한다. Sentinel-2 L2A와 Landsat 8 C2 L2의 PNG는 반텐 고정 시험 구역의 구름·결측 QA를 적용한 관측 미리보기다. 해당 ZIP에는 각 센서의 6밴드와 Sentinel-2 SCL 또는 Landsat QA_PIXEL, STAC, 취득 증거가 있다. 두 센서는 화면에서 원영상 관측을 비교한다.

Esri v003 표시는 8개 면적 클래스와 Clouds를 포함한 [원본 9개 팔레트](https://api.impactobservatory.com/stac-aws/collections/io-10m-annual-lulc/items/48M-2024)를 사용한다. Clouds는 보고서 유효 면적에서 제외하고 NoData는 투명으로 유지한다. 화면용 팔레트 PNG는 해시를 검증한 두 입력에서 렌더링한다. 결과 ID와 기록된 분석 파일은 그대로 조회한다.

## 결과와 API

2020→2025의 반텐 표본은 **공통 유효 712.30ha 중 32.65ha 변화, 변화율 4.58%**다. 분모는 등적 EPSG:6933 격자의 공통 유효 71,230픽셀이다. 이 값은 Esri 연차 지도 간 변화이고 독립 정확도나 반텐주 전체의 변화율은 미산출이다.

- 결과 ID `f9f3824d49505e52a35989389140e2973b43efd852320145e44945484f4d605a`
- `GET /api/lcluc/cases/{id}` 결과와 원본 출처. 기존 결과 카탈로그의 승인 상태를 사용한다.
- `GET /api/lcluc/boundaries` 6개 주 지도용 GeoJSON, 행정명, 취득 시각과 근거 해시. `GET /api/lcluc/boundaries/{region}` 고정한 지역 경계. 대상 외 지역은 HTTP 404, 증거 검증 실패는 HTTP 409다.
- `GET /api/lcluc/cases/{id}/esri-display/{earlier|later}` 고정 입력을 확인한 Esri 화면용 PNG. 자료가 Esri 연차 참조일 때만 결과 상세의 `esri_display`에 연결한다.
- `GET /api/lcluc/imagery` 비교 가능한 관측 목록과 날짜·출처
- `GET /api/lcluc/imagery/{id}/{earlier|later}/{preview|bundle}` 해시 검증 후 화면 또는 원본 묶음을 반환한다. 원본 파일명·스토리지 내부 경로와 서명 토큰을 응답에 포함하지 않는다.

직접 사용하려면 기존 LCLUC Workspace의 지역을 반텐, 연도를 2020·2025로 둔다. **지도 분석 → 지도 우측 범례 → 지도 자료**에서 연차 토지피복도, Sentinel-2, Landsat 8, 팔루 재난을 전환한다. 영상별 **T1 ZIP·T2 ZIP**에는 원본 창·취득 영수증과 관측 STAC을 담았다. 팔루 ZIP은 게시 JPEG와 영수증을 담았다. Esri의 통계·파일은 기존 **시계열 분석**, **전환 행렬**, **결과 내보내기**에서 확인한다.

Edge에서 실행 중인 5175의 기존 Workspace 7개 탭과 4개 지표 카드, MapLibre 스와이프, 영상 전환·ZIP, 전환 행렬·결과 내보내기 및 미등록 2023년 상태를 확인했다. 증거는 `artifacts/lcluc/existing-workspace-verified.log`다.

데스크톱 비교 지도는 오른쪽 지표 영역에 맞춰 늘어난 카드 높이를 채운다. Edge에서 화면 너비 1920px와 1440px의 지도 아래 여백이 제거되고 양쪽 지도 캔버스가 함께 늘어나는 것을 확인했다. 390px에서는 단일 열의 기존 높이를 유지한다.

## 2020~2025 전역 자료 확대

6개 주의 경계와 공식 Esri 제품 타일 격자를 대조했다. 반텐 48M, 서자바 48M·49M, 동자바 49L·49M·50L·50M, 고론탈로 51N, 남술라웨시 50M·51M, 남동술라웨시 51M이다. 공통 타일을 한 번만 받으면 7타일×6연도 42개다. 제공처 HEAD 42건에서 확인한 전체는 3,537,430,071바이트, 반텐 48M 6건은 781,705,561바이트다. 이 수치는 받아야 할 원본의 길이다. [Esri 연차 토지피복](https://livingatlas.arcgis.com/landcover/)

- Esri 공급자 원본 COG와 검증 영수증은 `data/raw/explorer/province/esri-v003/`에 연도별로 저장한다. `python -m services.lcluc.province_esri`는 겹치는 타일을 보여주며 `--execute`로 반텐 우선 순서로 저장한다. 각 파일의 길이·ETag·SHA·격자를 확인한다.
- 반텐 QA 계획 `data/raw/explorer/province/banten-optical/scene-plan.json`은 6~10월 획득 장면에서 경계를 덮는 조합을 기록한다. 6개 연도에 선택된 Sentinel-2 32장과 Landsat 8/9 24장의 장면 단위 footprint는 각각 경계를 덮는다. 같은 계절에 대한 1차 공간 확보 계획이며 맑은 픽셀 가용성은 TIFF·SCL/QA_PIXEL로 계산한다.
- Landsat의 표면반사율 6밴드와 QA_PIXEL 원본은 `data/raw/explorer/province/banten-optical/landsat-native/`에 장면·연도별로 저장한다. 장면별 일자, STAC SHA와 밴드 원본별 SHA를 보존한다. 읽는 데 쓰는 SAS는 메모리에만 둔다. [USGS Landsat Collection 2 Level-2](https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products)
- Sentinel-2 최신 원장 사전검사에는 활성 수집기가 없고 기존 실행 잠금이 남았다. 잔액은 1,594,369,596바이트이며 서자바 2024 미정산 창은 별도 검증 후 처리한다.
- 반텐 Esri 10m 연차 피복률·전환행렬 검산기는 원본 수신이 확인될 때 `data/curated/explorer/banten-province/esri-coverage-and-change.json`에 기록한다. 이 보고서는 같은 EPSG:6933 격자에서 경계 안의 픽셀을 세고, 구름·NoData를 공통 유효 면적에서 제외한다. 시범 구역 지표는 앞 절의 두 시점 시험 구역을 가리킨다. Province AOI에서는 받아 검증한 해당 연도 반텐 전체 색상층을 표시하고, 수신 전인 연도는 준비 중으로 보여준다.
- `python -m services.lcluc.banten_optical_qa --wait-for-collection`은 연도별 Landsat 수신 완료 후 30m 등적 격자에서 6밴드 동시 존재 면적·QA 맑은 면적·같은 연도 Esri 유효 면적의 교집합을 검산한다. 기존 반텐 시험 구역의 실제 2020·2025 원본에서 공통 유효 비율은 각각 54.56%, 99.91%였다. 전역 산출물은 `data/curated/explorer/banten-province/landsat-esri-support.json`에 기록한다.
- 최종 비교에는 Sentinel-2의 같은 관측 장면 6밴드+SCL과 Landsat의 6밴드+QA_PIXEL로 품질 마스크를 만들고, 동일 연도와 동일 경계의 공통 유효 픽셀을 사용한다. Esri 비교 지표는 동년 약한 참조 일치도로 기록한다. 별도로 확보한 전문가·현장 판독 표본이 있어야 독립 정확도를 계산할 수 있다.

지도 검증 근거는 `artifacts/lcluc/six-admin-labels-final.log`와 `artifacts/lcluc/esri-legend-edge.log`이다. 브라우저에서 지도에 주 이름이 각각 한 번씩 표시되고, 군·시 이름은 확대하면 나타난다. 범례에서 9개 Esri 색과 15px 행 간격을 확인했다.

반텐 2020년 원본 48M 파일 139,102,310바이트와 SHA-256을 검증했다. 경계 내 EPSG:6933 10m 격자 935,602.88ha 중 파일 자료 존재 100%, 유효 토지피복 99.9648%, 구름 329.35ha다. 반텐주 전체 PNG는 `GET /api/lcluc/banten-province-display`에서 연도 목록을 확인하고 `GET /api/lcluc/banten-province-display/{year}`로 읽는다. 화면 표시 PNG는 Web Mercator 축척에 맞춰 줄였으며, 통계는 10m에서 계산했다. 반텐 Landsat 2020의 첫 완전한 B2 원본도 83,167,494바이트와 해시를 확인했다.

Edge에서 기존 **Province AOI**를 누르고 반텐 전체 2020년 색상층과 2025년 준비 중 표시를 확인했다. **10m Study AOI**를 누르면 기존 시험 구역으로 돌아간다. 검증 기록은 `artifacts/lcluc/banten-province-edge.log`다.

## 반텐 전역 분석·보고서 실행

**세부 지역 (AOI) → 주 전체 참조**에서 기존 분석 버튼을 사용한다. **분석 실행**은 선택 연도의 전체 원본에서 10m 등적 전이 면적을 재계산한다. **비교 분석**은 저장된 동일 연도쌍 전역 비교를 열고, **리포트 생성**은 원본 COG의 길이와 SHA를 확인한 뒤 동일 결과 ID에 HTML·JSON·CSV 링크를 연결한다. Esri 2020–2021 전역 실자료를 Edge로 검증했다. 경계 935,602.88ha, 공통 유효 935,223.27ha, 변화 51,913.67ha, 변화율 5.55094%다. 결과는 지도 간 변화이며 과학 독립 정확도는 대기다. 증거는 `artifacts/lcluc/banten-full-pair-edge.log`다.

전역 Sentinel-2는 사용자가 2020~2025 후보 장면 32개, 원본 COG 224개, 총 21,626,452,905바이트의 다운로드를 명시 승인했다. `data/raw/explorer/province/banten-optical/sentinel-native/`에서 독립 승인 핀, 파일별 영수증, 부분 파일, 자료 진행을 기록한다. HTTP Range 이어받기는 출처 ETag와 바이트 시작점을 확인한다. 기존 공유 원장의 예산·미정산 기록은 보존한다. 반텐 전역 Landsat과 Sentinel-2 영상은 해당 연도의 모든 예정 장면 영수증을 확인한 뒤 QA 마스크를 적용해 등록한다. 표시 해상도와 30m 등적 원본 피복 검사 결과를 구분한다.

- 비교·분석 `GET /api/lcluc/banten-province-comparison`, `POST /api/lcluc/banten-province-analysis`
- 보고서 생성 `POST /api/lcluc/banten-province-reports`와 ID별 HTML·JSON·CSV 조회
- 원본 미확보 연도는 비교 API가 HTTP 409, 전역 미리보기는 HTTP 404를 반환한다.

반텐은 **주 전체 참조**로 기본 진입한다. 2020~2025 Esri 6개년 모두 One Map 경계 내 원본 픽셀이 존재한다. 구름을 제외한 연도별 토지피복 유효율은 99.9567~99.9953%다. **시계열 분석**에서는 6개년 등적 면적을 표시하고 **전환 행렬**에서는 선택한 두 연도의 공통 유효 픽셀만 집계한다. **변화 탐지**는 10m 픽셀을 1km 격자별 변화율로 표시한다. **핫스팟 분석**은 변화 면적 상위 20개 격자를 One Map 경계에 맞춰 보여준다. 2020–2025의 변화 격자는 8,663개이며 변화 면적 78,998.91ha는 전환행렬의 비대각합과 일치한다. 주요 지표는 선택 연도의 면적과 순변화를 표시하며 자료 수집 현황의 Esri 연도별 링크에서 원본과 유효율을 확인할 수 있다. 검산을 마친 광학 영상의 6밴드 피복률과 구름 등을 제외한 맑은 픽셀 비율도 별도로 표시한다.

- `GET /api/lcluc/banten-province-collection`은 반텐 Esri 연도별 원본과 유효율, Sentinel-2·Landsat의 파일 영수증 및 장면 수, 연도별 광학 검산 자료를 제공한다.
- `GET /api/lcluc/banten-province-change-preview/{start}/{end}`는 검산된 변화율 PNG를 제공한다. 공간 결과가 준비되지 않은 연도쌍은 분석 실행으로 계산한다.
- 전역 원본·장면 영수증, 연도별 6밴드와 QA 파일의 실제 픽셀 피복률, 지도·통계·보고서 클릭 시험을 모두 확인한 뒤 Docker·Kubernetes 이식 작업을 시작한다. 전역 참조 일치도와 독립 정확도는 자료와 검증 조건이 갖춰질 때 각각 산출한다.

Edge 전역 시험은 2020년·2025년 지도, 분석 재계산, 6개년 면적 표, 핫스팟 20개, 출처 링크, 보고서 HTML·CSV를 확인했다. CSV 전환행렬 합계는 공통 유효 면적 935,231.32ha와 일치한다. 재현 기록은 `artifacts/lcluc/banten-feature-2025-edge.log`, 리포트 ID는 `0c62e0f1c6d06ca4aba4726b6e9f4ab7c0ba01a6c44b08fb976d0ca1d7e2dab6`이다. Sentinel-2와 Landsat 전역 인수 상태는 `artifacts/lcluc/banten-full-acceptance.json`에서 확인한다.

15개 연도쌍 API의 원본 SHA와 면적 집계를 검산했다. 핫스팟 탭의 지도는 컨테이너의 실제 크기를 따라가며, Edge 1060×520 지도와 20개 순위 행을 `artifacts/lcluc/banten-hotspot-map.log`로 검증했다.

Sentinel-2 2020년 원본 35개와 장면 영수증 5개를 검증했다. 경계 내 30m 격자 935,601.66ha에서 6밴드 피복률은 100%, SCL 적용 후 맑은 픽셀은 87.53%, 동년 Esri 유효 픽셀과의 공통 면적은 818,838.00ha다. 이 교집합은 두 자료를 비교할 수 있는 영역을 뜻한다. 2020년 원본에서 만든 반텐 전역 RGB는 `GET /api/lcluc/banten-province-optical/sentinel-2/2020`으로 조회한다. Edge에서 2020년 레이어 단일 보기와 2025년 대기를 확인했다. 재현 기록은 `artifacts/lcluc/banten-sentinel-2020-edge.log`다.

2026-11-26 확인에서 Sentinel-2는 2020~2025 원본 224개와 장면 32개를 모두 검증했으며 연도별 RGB 표시층 6개가 준비됐다. Landsat은 2020~2023의 원본 112개와 장면 16개를 보존했다. 2024년 첫 파일 전송이 중간에 끊겨, 길이가 맞지 않거나 연결이 끊긴 파일에 제한 재시도를 추가하고 동일 수집 경로를 재개했다. 기존 영수증의 TIFF는 크기·SHA·출처를 다시 확인해 재사용한다. 최종 인수는 원본 수, 30m 경계 안의 미피복 면적, 지도 표시 시험을 각각 기록한다.

2026-11-26 10:47 KST 기준 Landsat 원본 168개, 장면 24개, 11,700,363,947바이트를 검증했다. 두 센서의 2020~2025년 연차 표시층과 30m 검산이 모두 준비됐다. Landsat 6밴드 미피복 면적은 2020년 112.77ha, 2021년 165.69ha, 2022년 73.98ha, 2023년 274.32ha, 2024년 10.35ha, 2025년 51.30ha다. Sentinel-2는 2020년 0ha, 2021년 0.18ha, 2022년 2.88ha, 2023년 0.09ha, 2024년 0.90ha, 2025년 2.52ha다. 전체 반텐 경계의 물리 피복 인수는 `COVERAGE_GAPS`로 기록했다.

반텐 Sentinel-2 32장면의 원본 GeoTIFF 헤더 224개를 다시 확인했다. B02·B03·B04·B08은 각각 10×10m 32개, B11·B12·SCL은 각각 20×20m 32개이고 모두 EPSG:32748이다. 원본 해상도는 자산 영수증에 기록된다. 반텐 광학 QA와 새 연차 워커는 두 센서 비교용 30m 등적 격자에 최근접 정합한다. 기존 화면의 연도별 RGB 합성은 SCL 4·5·6·7·11을, 새 연차 후보 학습용 반사도 합성은 SCL 4·5·6을 채택한다. 두 경로 모두 구름·구름 그림자를 제외한다. [Sentinel-2 밴드 규격](https://sentiwiki.copernicus.eu/web/s2-mission) · [L2A 및 SCL 제품 규격](https://sentiwiki.copernicus.eu/web/s2-products) · [신규 연차 입고](ANNUAL_INTAKE.md)

자동 작업은 고정 계획에서 연도별 장면 영수증이 모두 준비됐는지 주기적으로 확인한다. QA는 30m 등적 격자에서 6밴드 동시 피복, 맑은 픽셀, 동년 Esri와 공통으로 유효한 면적을 계산한다. 지도의 Web Mercator 표시층은 별도로 생성한다. 실제 Landsat 2024·2025 로그에 자동 갱신이 기록됐다. 이 계획의 6개년이 처리되면 감시 작업은 종료된다. 계획 밖의 신규 연도를 발견·등록하고 데이터셋 버전, 모델 실행, 분류 비교와 독립 검증으로 연결하는 운영 자동화는 후속이다. [학습·검증 조건](../mlops/TRAINING_ACCURACY_DEPLOYMENT_GATES.md)

## 연도별 면적 차트와 Snow/ice

면적 차트의 세로축은 0ha에서 시작하고 최상단이 최소 1ha다. 숫자는 ha 단위로 표시하고 개별 점의 툴팁에는 연도·클래스와 소수 면적을 표시한다. 반텐 Esri v003의 2020~2025 Snow/ice(코드 9) 집계는 0.04, 0, 0.03, 0.05, 0, 0.12ha다. 10m 분석 격자 기준 4, 0, 3, 5, 0, 12픽셀에 해당한다. 이 값은 지도 분류 결과이며 현지 적설·결빙 관측과는 별개의 증거다. 화면의 Snow/ice 지표에서 이 설명을 확인할 수 있다.

Edge 5175의 결과 화면에서 Snow/ice 실자료 6점, 0–1ha 눈금, 출처 설명, 전체 유효 면적 선택을 확인했다. 별도 합성 입력에서는 여섯 연도의 0ha 점이 모두 같은 높이의 수평선에 놓였다. [실제 화면 증거](../../artifacts/lcluc/banten-snow-chart-edge.png) · [시험 기록](../../artifacts/lcluc/banten-snow-chart-edge.log)
