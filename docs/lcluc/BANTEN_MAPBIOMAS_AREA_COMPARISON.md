# 반텐 토지피복 원본별 집계와 공식 비교 기준

## 현재 표시 범위

`GET /api/lcluc/banten-sentinel-explorer/mapbiomas-area-comparison?year=2024`는 공통 발행 연도 2020~2024의 원본별 집계를 제공한다. 연도 생략 시 최신 공통연도를 사용하고, 비공통 연도는 422다. 기존 LCLUC **연차 토지피복도 → 위성영상 수집현황 및 출처 → Esri·MapBiomas 원본별 면적**에서 조회한다.

`scope`는 `native_statistics_separate_boundaries`, `comparison_status`는 `COMMON_BOUNDARY_AND_REVIEWED_CROSSWALK_REQUIRED`다. `esri`의 9개 원본 클래스는 One Map 반텐 경계 안의 EPSG:6933 10m 픽셀 중심 집계다. 경계 격자 면적, 분류 유효 면적, 구름 코드 10, NoData를 구분한다. `mapbiomas`는 Collection 4.1 공식 XLSX의 반텐주 발행 클래스 11개와 그 합계다. 응답은 Esri 연차 TIFF, 경계와 MapBiomas XLSX의 SHA-256을 제공한다.

2024년 Esri 경계 격자는 935,602.88ha이며, 분류 유효 935,224.83ha·구름 378.05ha·NoData 0ha로 구성된다. MapBiomas 발행 통계 합계는 935,005.55ha다. 이전 597.33ha는 Esri 경계 격자와 MapBiomas 발행 합계의 차이였다. Esri ‘수목’과 MapBiomas ‘산림·맹그로브’, Esri ‘초지·관목지’와 MapBiomas ‘비산림 자연식생’은 정의와 범위가 달라 이전에 표시한 클래스별 차이 열을 제거했다. MapBiomas 비산림 자연식생은 습지·침수 식생·회복 중인 식생도 포함한다. [MapBiomas 4.1 분류 정의](https://landy.mapbiomas.id/assets/files/Col%204.1%20-%20Legend%20Description%20EN.pdf) · [Esri 원본 서비스](https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer)

## 공식 비교 기준과 정밀 검증 조건

`BLOCKED` 인도네시아 산림부(Kemenhut, 기존 KLHK 자료 계열)의 동년 **Penutupan Lahan 23개 클래스 연차 원본**을 공식 사업 비교 기준으로 채택한다. 반텐 전역을 평가하려면 산림구역과 비산림 이용구역(APL)을 함께 제공하는 레이어인지 확인한다. 기존 SIGAP 커넥터와 원본 보존 방식을 사용하고, 연도·발행판·취득시각·허용범위·해시 및 코드 도메인을 입고 시 확인한다. [SIGAP 공식 자료사전](https://sigap.kehutanan.go.id/tema-kamus/575) · [SIGAP 2024년 통계 안내](https://sigap.kehutanan.go.id/dok-elektronik) · [분류 계약](TAXONOMY.md)

원본이 입고되면 승인된 One Map 경계, 같은 관측연도, 공통 등적 격자, 공통 유효 영역에서 산림부 지도와 Esri·MapBiomas·자체 분류를 비교한다. 각 제품의 원래 코드는 보존하고, 검토한 공통 분류표의 미대응·혼합 분류 면적을 보고한다. 구름, NoData, 경계 불일치로 빠진 면적을 먼저 공개한 뒤 면적·공간 불일치와 혼동행렬을 산출한다. 산림부 지도는 공식 참조이며 독립 정확도에는 학습에 사용하지 않은 현장·판독 표본을 별도로 사용한다. [동년 검증 계약](ANNUAL_INTAKE.md)
