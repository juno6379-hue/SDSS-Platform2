# 반텐 Landsat 장기 분석

기존 LCLUC의 **반텐 → 지도 자료 → Landsat**에서 Natural Color, Agriculture, Urban, SWIR, NDVI, NDMI, MNDWI를 선택한다. 스와이프의 T1·T2에는 반텐 경계 안에서 합성 영상을 발행한 연도가 나타난다. **Time-Series**는 선택 범위 안의 발행 연도를 순서대로 재생하고 마지막 연도에서 멈춘다. **NDVI 변화**는 두 연도에 유효한 관측이 겹치는 픽셀의 ΔNDVI를 표시한다. 녹색은 +0.20 이상, 주황색은 −0.20 이하이다.

## 센서와 관측 품질

| 표준 역할 | Landsat 4/5 TM, 7 ETM+ | Landsat 8/9 OLI 계열 |
| --- | --- | --- |
| Blue, Green, Red | B1, B2, B3 | B2, B3, B4 |
| NIR, SWIR1, SWIR2 | B4, B5, B7 | B5, B6, B7 |

Collection 2 Level-2 표면반사도는 `DN × 0.0000275 − 0.2`로 계산한다. `QA_PIXEL`로 채움값, 팽창 구름, 구름, 그림자, 눈을 제거하고 OLI 계열에서는 권운 비트도 적용한다. `QA_RADSAT`이 포함된 과거 장면은 포화·드롭 픽셀 등의 비트가 설정된 픽셀을 제외한다. 보존된 2020~2025년 자료는 `QA_PIXEL`을 사용했으며 개별 장면 기록에 `qa_radsat=false`가 남는다. 이 처리는 센서별 밴드 대응과 USGS 보정값 적용까지 포함한다. 센서 간 분광 응답 차이의 경험적 보정은 추가 검증 대상이다. [USGS 표면반사도](https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-reflectance) · [USGS 스케일과 오프셋](https://www.usgs.gov/faqs/how-do-i-use-a-scale-factor-landsat-level-2-science-products) · [USGS QA 밴드](https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands)

연간 합성은 맑은 관측의 밴드별 중앙값을 쓴다. 3~5년 합성은 연간 합성의 중앙값과 맑은 관측 수의 합계를 제공한다. 2020~2022년 합성의 맑은 관측 1회 이상·2회 이상 비율은 97.86%·90.58%, 2023~2025년 합성은 99.82%·98.01%다. 품질표와 GeoTIFF의 `CLEAR_OBSERVATIONS` 밴드에서 관측 밀도를 확인한다. 보존 분광 원본의 픽셀 크기는 30m다. 지도와 시험 RF는 약 147m 간격의 EPSG:3857 공통 표시 격자를 사용한다.

과거 시험은 Planetary Computer STAC에서 연도별 5~11월과 반텐 경계의 외접 범위를 조회하고, 경계와 겹치는 Tier 1 장면을 고른다. 해당 연도의 단일 장면과 품질이 적용된 발행 범위는 API와 관측 품질표에 표시된다. 단일 장면 시험의 관측 공백은 지도에서 투명하다. 1984년의 조회 결과는 해당 조회 조건과 범위에만 적용한다. [Planetary Computer Landsat 카탈로그](https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2)

| 발행 연도 | 맑은 관측 1회 이상 | 원본 장면 |
| --- | ---: | --- |
| 1988 | 47.88% | Landsat 5 TM `LT05_L2SP_123064_19880811_02_T1` |
| 1990 | 50.83% | Landsat 5 TM `LT05_L2SP_123064_19900614_02_T1` |
| 2000 | 40.30% | Landsat 5 TM `LT05_L2SP_123064_20000609_02_T1` |
| 2010 | 32.14% | Landsat 5 TM `LT05_L2SP_123064_20100707_02_T1` |
| 2020~2025 | 80.61~96.42% | Landsat 8/9 OLI 계열, 연간 4장면 |

과거 4장면의 원본 파일 32개·1,257,798,910바이트를 영수증과 함께 보존했다. 실물 원본으로 Landsat 5·8·9를 처리했다. Landsat 4/7 센서 라우팅은 단위시험에서 검사했다.

재현하려면 저장소 루트에서 연도별 원본을 `python -m services.lcluc.banten_landsat_history 1988 1990 2000 2010`으로 처리한다. 이미 수신한 원본은 영수증과 SHA-256을 검증하여 재사용한다. 2020~2025년 보존 원본의 연차 합성은 `python -m services.lcluc.banten_landsat_explorer --local 2020 2021 2022 2023 2024 2025`, 기간 합성은 `--period 2020 2022` 등으로 처리한다. 모델 실행은 학습 의존성이 설치된 환경에서 `python -m services.lcluc.banten_landsat_baseline`을 사용한다.

## 분석 결과와 검증 범위

- **장기 변화탐지**는 MapBiomas Indonesia Collection 4.1의 반텐 발행 자료에서 산림·맹그로브, 농경지, 시가화의 1990~2024년 순변화 및 연속 연도 기준 최대 증가·감소 구간을 계산한다. 연도 구간은 주 단위 면적 변화이며 픽셀별 발생 시점 추정은 LandTrendr·CCDC 비교를 위한 조밀한 관측 시계열 확보가 필요하다. [MapBiomas 공식 통계](https://landy.mapbiomas.id/en/statistics)
- **시계열 통계**는 발행 자료 35개년·11개 클래스에서 시작/종료 면적, 누적 순변화, 연평균 순변화, 시작 면적 대비 변화율을 표시한다. 시작 면적이 0인 변화율은 공란으로 표시한다. 전체 시계열 CSV를 받을 수 있다.
- **Random Forest**는 2020년 반텐 실영상 6밴드와 동년 Esri v003 약한 참조를 사용했다. 학습 19,647픽셀, 분리된 공간 블록 검증 72,391픽셀에서 충분한 표본을 얻은 6개 클래스를 비교했다. 약한 참조 일치도는 71.42%, 평균 IoU는 36.27%다. 분류 GeoTIFF 및 근거가 연결돼 있고 독립 정확도는 미측정 상태다. 후속 모델 비교는 동년 독립 참조와 센서별 시기·공간 검증을 확보한 뒤 수행한다.

## API와 원본 보존

| GET 경로 | 응답 |
| --- | --- |
| `/api/lcluc/banten-landsat` | 발행 연도·기간, 관측률, 장면, 과거 아카이브 조회 상태 |
| `/api/lcluc/banten-landsat/products/{period}` | Banten 경계 해시, 원본 매니페스트, 합성 방식, 래스터 및 PNG 해시 |
| `/api/lcluc/banten-landsat/products/{period}/{layer}` | 검증한 PNG 또는 6밴드와 관측 수가 든 GeoTIFF (`reflectance`) |
| `/api/lcluc/banten-landsat/change/{start}/{end}` | 공통 격자 유효 픽셀의 ΔNDVI PNG |
| `/api/lcluc/banten-landsat/baseline` 및 `/baseline/classification` | 약한 참조 RF 평가 기록 및 분류 GeoTIFF |

원본은 `data/raw/explorer/province/banten-optical/landsat-native/` 및 `historical-native/`에, STAC 조회와 발행 근거는 같은 부모의 `historical-stac/`에 있다. 재현용 매니페스트와 산출물은 `data/curated/explorer/banten-province/landsat-explore/`에 있다. API는 등록한 자산 크기와 SHA-256을 검사한 뒤 파일을 반환한다.

## 시험

- 밴드 매핑, 구름·권운·포화, 반사도 변환, 관측 수 집계, NoData 전파는 `tests/lcluc/test_landsat_explorer.py`에 있다.
- 실제 Edge에서 일곱 영상 조작과 지도 응답, ΔNDVI, 품질·통계·모델 카드, 1990↔2020 스와이프와 1990→2000→2010→2020 Time-Series를 확인했다. 마지막 연도에서의 자동 정지, 첫 연도부터 다시 재생, 기존 연차·Sentinel-2 메뉴 복귀도 시험했다. [로컬 시험 스크립트](../../artifacts/lcluc/check_landsat_explorer.py) · [브라우저 실행 기록](../../artifacts/lcluc/landsat-explorer-edge-final.log)
