# SDSS-Platform2 지속 개발 원장

## 2026-11-26 반텐 집계 재검토와 LANDY 자료 현황

- `VERIFIED_REAL` 반텐 제품 면적 화면은 Esri 원본 9클래스와 MapBiomas 발행 11클래스를 각각 표시한다. 이전 클래스 대응 차이 열은 제거했다. 2024년 Esri TIFF를 재집계해 경계 격자 935,602.88ha, 분류 유효 935,224.83ha·구름 378.05ha·NoData 0ha를 확인했다. [집계 계약](docs/lcluc/BANTEN_MAPBIOMAS_AREA_COMPARISON.md) · [Edge 실행](artifacts/lcluc/banten-native-area-edge.log)
- `BLOCKED` 인도네시아 산림부의 동년 23클래스 Penutupan Lahan을 공식 비교 기준으로 채택한다. 반텐 전역 원본·권한·버전 확인 이후 공통 경계·격자·분류표에서 다른 지도를 비교한다. 지도 일치도와 독립 정확도는 별도 증거로 기록한다.
- LANDY 문서 14건과 Collection 4.1 연차 면적·전이 시트가 포함된 XLSX를 보유한다. 반텐 35개년 11개 클래스 면적을 발행했다. 4.1 전이 시트는 연결 전이고 반텐 4.1 픽셀 자료는 미입고다. [문서·통계·공간 현황](docs/lcluc/MAPBIOMAS_GEOLLM_KNOWLEDGE.md#landy-자료-수집-현황)

## 2026-11-26 반텐 DeepLabv3+ 비교와 제품별 면적 대조

- `VERIFIED_REAL` 2020 반텐 Landsat과 Sentinel-2의 RF·Tiny U-Net·경량 DeepLabv3+를 센서별 동일 평가 표본으로 비교했다. DeepLabv3+의 Esri 약한 참조 일치도는 Landsat 67.76%, Sentinel-2 63.74%다. 기존 LCLUC 카드, GeoTIFF 6개와 Toolbox 전·후 시험을 검증했다. `BLOCKED` 독립 표본 평가와 전 연도 모델 운영 승인은 별도다. [모델 근거](docs/lcluc/BANTEN_MODEL_TRIALS.md)
- `VERIFIED_REAL` 기존 연차 레이어에 2020~2024 Esri·MapBiomas 발행 면적 조회를 연결했다. 최초 근사 대응 표는 같은 날짜의 반텐 집계 재검토에서 원본별 두 표로 교체했다. [현행 면적 계약](docs/lcluc/BANTEN_MAPBIOMAS_AREA_COMPARISON.md)

## 2026-11-26 반텐 실자료 모델·GeoLLM MapBiomas 지식

- `VERIFIED_REAL` 2020 반텐 Landsat과 동년 Esri에서 RF·Tiny U-Net을 동일 학습 표본과 72,391픽셀 공간 홀드아웃으로 비교했다. 약한 참조 일치도는 각각 71.42%, 66.34%다. [반텐 모델과 특화 분류 접수](docs/lcluc/BANTEN_MODEL_TRIALS.md)
- `VERIFIED_REAL` 같은 공간 필터에서 RF 71.42→75.09%, Tiny U-Net 66.34→66.49%를 확인했다. 2020→2025 Sentinel-2 Siamese 후보의 동일 64,658픽셀 변화 클래스 F1은 0.288265→0.288352다. Edge에서 비교표, Tiny U-Net 실행·Swipe, 변화 결과, 계층 통합 입력 차단을 확인했다. [클릭 시험](artifacts/lcluc/banten-models-knowledge-edge.log)
- `VERIFIED_REAL` MapBiomas 공식 원문 R01~R14를 취득했고 자료명·버전·페이지·SHA-256을 저장했다. P0 핵심 9건과 용어집·출처 지도·범례 구조화는 [GeoLLM 지식자료](docs/lcluc/MAPBIOMAS_GEOLLM_KNOWLEDGE.md)를 참조한다.
- `BLOCKED` 인도네시아 특화 모델은 승인된 동년 픽셀 라벨과 출력 레이어 접수가 필요하다. 기본 모델과 동년·동일 격자에 대한 계층 통합 계약과 우선순위 적용을 구현했다.

## 2026-11-26 반텐 LCLUC 후처리 및 품질관리

- `VERIFIED_REAL` GeoAI Toolbox의 독립 메뉴와 LCLUC 바로가기에서 2020년 반텐 Landsat RF 후보에 Spatial Filter를 적용했다. Edge로 전·후 Swipe, 보정 위치, 클래스 면적 증감, 약한 참조 비교, 파라미터·이력과 원본·후처리·보정 GeoTIFF 해시를 확인했다.
- `VERIFIED_REAL` 4픽셀·4방향 시험은 61,274픽셀을 보정했다. 같은 공간 홀드아웃 72,391픽셀에서 Esri 약한 참조 일치도는 71.42→75.36%다. `TESTED_SYNTHETIC` NoData·보호 클래스·연결 방향을 검사했다. `BLOCKED` 독립 정확도는 독립 표본이 필요하다. `PLANNED` 시간·결측·빈도·반복·계층 통합 도구를 구분해 표기했다. [공식 방법론과 구현·시험](docs/lcluc/POSTPROCESS_QUALITY.md)

## 2026-11-26 반텐 Landsat 장기 분석

- `VERIFIED_REAL` 반텐 Landsat C2 L2 보존 원본 2020~2025년 24장면에서 영상 조합 7종, 연차 선명 관측 수와 GeoTIFF를 발행했다. 2020~2022년과 2023~2025년 합성의 맑은 관측 1회 이상은 각각 97.86%, 99.82%다. 실제 Edge에서 지도 폭 886.95px와 레이어·ΔNDVI·품질·통계·모델 카드 연결을 확인했다.
- `VERIFIED_REAL` 1988·1990·2000·2010년 Landsat 5 TM 단일 장면과 원본 32파일을 확보했다. 반텐 안의 선명 관측 1회 이상은 각각 47.88%, 50.83%, 40.30%, 32.14%다. 각 연차의 발행과 API 노출, 실브라우저 1990↔2020 스와이프와 1990→2000→2010→2020 재생 프레임을 확인했다.
- `VERIFIED_REAL` MapBiomas Collection 4.1 1990~2024년 반텐주 발행 통계에서 11개 클래스의 누적·연평균 변화와 변화율, 세 분석 그룹의 증가·감소 연도 구간을 계산한다. 2020년 Landsat Random Forest 실험은 분리된 공간 검증 블록에서 같은 해 Esri 약한 참조와 71.42% 일치했다.
- `TESTED_SYNTHETIC` TM·ETM+·OLI 밴드 대응, 스케일·구름·포화, 유효 관측 수·NoData 시험을 통과했다. `BLOCKED` 장기 픽셀별 변화 시점과 독립 정확도는 장기간 유효 관측 및 독립 참조 확보가 필요하다. [데이터·API·UI 시험](docs/lcluc/LANDSAT_EXPLORER.md)

## 2026-11-26 Sentinel-2 지도 폭·카드 메뉴·스와이프 연도 선택

- `VERIFIED_REAL` 연차 토지피복도와 Sentinel-2의 지도 너비를 Edge 1650px에서 각각 886.95px로 확인했다. Sentinel-2에서 우측 2개·하단 4개 결과 카드와 상단 7개 이동 항목을 검증했다. 920px에서 하단 카드는 세로로 배치됐다. 연차 레이어로 돌아가 기존 메뉴와 카드를 확인했다.
- `VERIFIED_REAL` 지도 하단 T1·T2로 2022→2024를 선택해 상단 필터, 양쪽 지도, AOI API·면적표·전이행렬이 갱신되는 것을 확인했다. 50:50 중앙 복귀, 결과 다운로드 링크, 간소화된 Sentinel 범례와 지도 아래 점 조회 버튼도 확인했다. [Edge 클릭 시험](artifacts/lcluc/sentinel-workspace-final-edge.log)

## 2026-11-26 반텐 지도 자료별 상세 카드 배치

- `VERIFIED_REAL` Sentinel-2 선택 시 연차 지표·전이 요약·수집현황 및 연차 하단 카드를 숨긴다. 지도와 상세를 전체 폭으로 표시하고 기본 결과에서 클래스 면적·비율과 전이행렬을 좌우에 정렬한다. Edge 1650px의 카드·표 상단 정렬과 920px의 세로 배치를 확인했다. 연차 토지피복도의 카드 복원, Sentinel-2 재선택 시 63,176.20ha AOI 유지, 2024→2025 결과 갱신도 확인했다. [클릭 시험](artifacts/lcluc/sentinel-layer-card-layout-edge.log) · [두 카드 화면](artifacts/lcluc/sentinel-aligned-results.png)

## 2026-11-26 반텐 토지피복 지표 출처 표기

- `VERIFIED_REAL` 지도 오른쪽 두 카드에 Esri v003 연차 토지피복, 반텐주 전체, 비교 연도쌍을 표시했다. 지도 아래 Sentinel-2 AOI 상세에는 영상·지수·품질의 Sentinel-2 L2A 출처와 선택 AOI의 Esri 면적·전이 출처를 표시했다. Edge에서 연차 토지피복도에서 Sentinel-2로 전환해 두 카드의 실제 집계값을 대조했다. [클릭 시험](artifacts/lcluc/sentinel-esri-source-edge.log)

## 2026-11-26 Sentinel-2 지도와 하단 상세 결과 연결

- `VERIFIED_REAL` Edge 5175의 기존 반텐 LCLUC에서 지도 자료를 Sentinel-2로 고르면 상세 결과 6개가 지도 바로 아래 자동으로 열린다. Landsat과 연차 토지피복도에서 패널이 닫히고 Sentinel-2 재선택 시 같은 AOI가 돌아왔다. 52,128.16ha 선택 AOI를 유지한 채 비교를 2024→2025로 바꿔 API와 면적표 갱신을 확인했다. [Edge 클릭 기록](artifacts/lcluc/sentinel-layer-bound-details-edge.log)

## 2026-11-26 반텐 Sentinel-2 레이어 목록과 결과 화면

- `VERIFIED_REAL` 기존 LCLUC Edge 5175에서 접이식 영상 5종·중첩 4종, 클래스 면적·비율, 방향별 전이 레이어, 전이 순위·필터, AI 실자료 상태, 장기 추세·다운로드, 제품 행렬을 클릭했다. 결과 화면에서 지도에 지정한 52,128.16ha AOI가 같은 결과표로 돌아옴을 확인했다. Esri 전이의 AOI 마스크와 면적 합계는 실제 API 응답과 대조했다.
- `VERIFIED_REAL` MapBiomas Indonesia Collection 4.1 반텐 발행 통계 1990~2024년 35개년·11개 클래스를 원본 XLSX와 해시로 보존했다. Esri↔WorldCover 비교는 2021년의 926,628.52ha에서 80.95% 지도 일치도다. 제품별 6개 대분류의 행렬과 센서별 2020~2025 동년 관측 지원 범위를 제공한다.
- `BLOCKED` 신규 실자료 연차 분류는 접수 0건이다. 실제 독립 정확도는 독립 참조가 등록되기 전까지 미측정이다. [사용·데이터·API·시험 근거](docs/lcluc/SENTINEL_EXPLORER.md)

## 2026-11-26 반텐 Sentinel-2 Explore

- `VERIFIED_REAL` 보존 원본 32장면에서 2020~2025 Sentinel‑2 30m 밴드·지수·QA GeoTIFF 6개와 지도 PNG 36개를 발행했다. 같은 반텐 경계의 Esri 10m 참조 분류 6개년과 15개 변화쌍은 기존 면적·공통 유효 픽셀·변화 픽셀 검산을 통과했다.
- `VERIFIED_REAL` Edge 5175에서 자연색·적외선·NDVI·NDWI·NBR, 지도 중첩, 클래스 범례, 경계, Swipe, 두 시점 Explore, 지도 사각형 AOI와 연차 변화·CSV 다운로드를 확인했다. API에서는 30m 반사도·지수와 10m 참조 변화 GeoTIFF, 선택 AOI의 분류·면적·비율을 검증했다.
- `TESTED_SYNTHETIC` 흐린 픽셀의 다른 장면 대체 시 동일 관측의 6밴드를 유지하는지와 공통 유효 전이에서 구름·NoData가 빠지는지 확인했다. 2건 통과. [처리 모듈·사용 방법·검증 증거](docs/lcluc/SENTINEL_EXPLORER.md)

## 2026-11-26 스와이프 자동 재생·Sentinel-2 원본 해상도

- `VERIFIED_REAL` 기존 Swipe Auto Play가 5초 한 차례 재생 후 50:50에서 종료한다. 반텐 Edge 5175에서 5→1초와 완료, 실제 5.10초, 일시 정지·재개, 수동·모드 변경 취소, Time-Series 재생을 확인했다. 증거는 `artifacts/lcluc/swipe-autoplay-final-edge.log`다.
- `VERIFIED_REAL` 반텐 2020~2025의 Sentinel-2 원본 GeoTIFF 224개에서 B02·B03·B04·B08은 10m, B11·B12·SCL은 20m로 확인했다. 현재 두 센서 비교·연차 워커의 정합 격자는 30m다. [조작·해상도·품질 마스크](docs/lcluc/INDONESIA_EXPLORER.md)

## 2026-11-26 반텐 연도별 면적 차트 검산

- `VERIFIED_REAL` Esri v003 반텐 Snow/ice 값은 2020~2025년 0.04, 0, 0.03, 0.05, 0, 0.12ha다. 0ha 기준축, ha 눈금과 소수 값 툴팁을 기존 차트에 적용했다. Edge 5175에서 6개 실제 값, 출처 설명과 전체 유효 면적 전환을 확인했다.
- `TESTED_SYNTHETIC` 여섯 연도 값이 전부 0ha일 때 모든 점이 수평 기준선에 놓이는 것을 확인했다. 근거는 `artifacts/lcluc/banten-snow-chart-edge.log`다. [차트 표시와 출처](docs/lcluc/INDONESIA_EXPLORER.md#연도별-면적-차트와-snowice)

## 2026-11-26 연차 LCLUC 자동 처리

- `VERIFIED_REAL` 실자료 전용 Docker 연차 워커가 60초 간격으로 `data/raw/annual-lcluc`를 검사한다. 12:39 KST 운영 접수 번들은 0건이다. 기존 개발 UI의 5175에서 같은 출처 연차 API와 기존 GeoAI 프록시를 확인했다.
- `TESTED_SYNTHETIC` Docker Compose 5180과 로컬 kind Kubernetes 5181에서 2026 반텐 시험 번들을 격리 입고했다. 밴드 대기, 승인 대기, 동년 분류·비교, 독립 검증자료 대기, 합성 홀드아웃 검증까지 각각 진행했다. 두 센서의 맑은 픽셀 1,023/1,024, 합성 독립 표본 256개씩, 분류·확률 GeoTIFF 4개 SHA 대조를 확인했다.
- `TESTED_SYNTHETIC` 양쪽 Edge에서 기존 2020 Sentinel-2 레이어와 새 연차 상태, 처리 증거 링크를 확인했다. 약한 참조 일치도와 합성 홀드아웃을 별도 표시했고, 실제 독립 정확도 값은 비워 뒀다. 회귀시험 45건 통과, 1건 건너뜀. [입고·운영·시험 절차](docs/lcluc/ANNUAL_INTAKE.md)
- `BLOCKED` 운영 접수 경로의 실제 2026 원본·동년 학습 라벨·독립 참조·승인 증거는 입고 대기다. 이번 워커는 내부 후보 모델을 생성한다. 운영 모델 활성화는 기존 승인 절차에 따른다.

## 2026-11-26 Docker·Kubernetes 이식

- `VERIFIED_REAL` 기존 React를 빌드한 Docker Compose가 loopback 5180에서 실행된다. 기존 GeoAI 8002를 동일 출처로 연결하고, 반텐 수집 현황(224·168개), Sentinel-2·Landsat 12개 표시층, 공통 결과와 작업 API를 실제로 읽었다. 반텐 원본과 증거는 읽기 전용이고 정제 자료는 별도 사본을 사용했다.
- `VERIFIED_REAL` 최종 Docker 이미지에서 Edge로 Esri·광학 스와이프, 10m 원본 재분석, 시계열·전환행렬·변화지도·핫스팟 20개, 출처·KPI, HTML·CSV 보고서를 확인했다. 동일 원본의 Windows 검산 78,998.91ha를 유지하고 Linux 재계산 78,998.94ha를 별도 표시한다. 기존 보고서 ID도 일치한다. 증거는 `artifacts/deploy/compose-portable-browser.log`다.
- `VERIFIED_REAL` Docker PostgreSQL/PostGIS·pgvector와 S3 호환 버킷을 연결해 기존 CCKP 보고서 1건을 등록하고 서명 읽기의 3,295바이트 SHA-256을 대조했다. 인증 없는 링크 발급 요청은 HTTP 403이다.
- `TESTED_SYNTHETIC` 실제 PostgreSQL 큐에서 모의 기관 응답을 사용해 작업 중복 방지·재개·취소를 시험했다. 기존 SQLite 경로도 같은 회귀 시험을 통과했다. 큐는 선택한 DB에 지속되며 기존 작업의 전환은 운영 절차에서 별도 수행한다.
- `VERIFIED_REAL` 로컬 Kubernetes 시험에서 매니페스트 서버 검증, API·React Deployment 1/1 롤아웃, 증거·원본·정제 자료 PVC 결속을 확인했다. 포트포워드에서 기존 GeoAI와 플랫폼 API, 반텐 분석 조회, 행정경계, 12개 광학 레이어의 SHA-256을 확인했다. Edge에서 기존 화면과 두 센서의 스와이프를 검증했다. 증거는 `artifacts/deploy/kube-http.log`와 `artifacts/deploy/kube-browser.log`다. 기관 운영 승인, 반텐 과학 인수와 독립 정확도는 별도다. [실행 절차](docs/architecture/PLATFORM2_OPERATION_PATH.md)

## 2026-11-26 10:47 KST 반텐 원본 수집 완료와 전역 검증

- `VERIFIED_REAL` Landsat 2020~2025 승인 장면 24/24개, 원본 168/168개, 11,700,363,947바이트를 확보했다. Sentinel-2는 장면 32/32개, 원본 224/224개다. 두 센서의 계획 수집기와 연차 처리 작업은 종료됐다.
- `VERIFIED_REAL` 연차 장면 영수증 감시가 Landsat 2024년과 2025년 수신 완료를 감지해 30m 피복·맑은 픽셀·동년 Esri 공통 유효 영역을 검산하고 RGB 표시층을 갱신했다. Sentinel-2도 2025년을 포함한 6개년 검산을 마쳤다.
- `VERIFIED_REAL` 기존 Edge 화면에서 Landsat과 Sentinel-2 2025년 레이어의 실제 응답, 2020·2025 스와이프 슬라이더와 50:50 복귀를 확인했다. 화면 시험 근거는 `artifacts/lcluc/banten-optical-ui-20261126.log`다.
- `BLOCKED` 광학 전역 인수 결과는 `COVERAGE_GAPS`다. Landsat의 연도별 6밴드 미피복은 10.35~274.32ha이며 Sentinel-2는 2021~2025년 0.09~2.88ha다. 원본 수집 완료와 전역 피복 인수를 별도로 기록한다. Docker·Kubernetes 이식 대기 상태를 유지한다.
- `PLANNED` 고정한 2020~2025 계획의 연차 QA와 표시층 등록까지 자동화했다. 계획 밖 연도 탐색과 데이터 연차 등록을 학습 후보 생성·추론·분류 비교·독립 검증으로 연결하는 운영 트리거는 후속이다. [수집·검산 기준](docs/lcluc/INDONESIA_EXPLORER.md) · [학습 및 모델 배포 기준](docs/mlops/TRAINING_ACCURACY_DEPLOYMENT_GATES.md)

## 2026-11-26 반텐 광학 수집 상태

- `VERIFIED_REAL` Sentinel-2 2020~2025 원본 224/224개, 장면 32/32개, 21,626,452,905바이트를 영수증으로 검증했다. 6개년 표시층을 게시했다. 기존 수집 프로세스는 종료됐다. 진행 JSON 기록에서 발생한 Windows 파일 교체 오류와 원본 전송 완료는 영수증으로 구분했다. 2025년까지의 30m 경계 피복 종합 검산은 다시 실행 중이다.
- `VERIFIED_REAL` Landsat 2020~2023 원본 112/168개와 장면 16/24개를 확보했다. 2024년 첫 응답의 본문 길이 불일치로 이전 실행이 종료됐다. 비교용 원본과 영수증을 유지하고, 동일 수집기로 2024~2025년 누락 원본을 재시도하도록 복구했다. 429 응답은 중단 대상이다. 연차 QA·표시층·최종 인수 점검도 이어진다. [범위·시험 문서](docs/lcluc/INDONESIA_EXPLORER.md)

## 2026-11-25 반텐 6개년 Esri와 Sentinel-2 전역 전송

- `VERIFIED_REAL` 반텐 2020~2025 Esri 원본 6/6, 781,705,561B를 검증했다. One Map 경계 안의 10m 격자는 935,602.88ha로 6개년도 원본 픽셀 존재율이 모두 100%이며 유효율은 99.9567~99.9953%다. 15개 연도쌍의 전이를 계산했다.
- `VERIFIED_REAL` 첫 2020–2021 전역쌍의 실제 UI 실행·비교·HTML/JSON/CSV 리포트를 검증했다. 공통 유효 935,223.27ha, 변화 51,913.67ha다. 2020–2025 전역 감사의 공통 유효 935,231.32ha, 변화 78,998.91ha, 8.44699%는 Esri 지도 간 변화다. 독립 정확도 미측정 상태다.
- `VERIFIED_REAL` 2020–2025 전역 비교를 기존 React 화면에 기본 연결했다. Edge에서 시계열 6개년, 변화 격자 8,663개, 상위 20개 핫스팟, 주요 지표, 수집 현황·원본, 전환행렬, 보고서 생성과 조회를 실제로 확인했다. 원본을 다시 읽어 분석을 실행했으며 HTML·JSON·CSV 보고서 ID는 `0c62e0f1c6d06ca4aba4726b6e9f4ab7c0ba01a6c44b08fb976d0ca1d7e2dab6`이다.
- `VERIFIED_REAL` 종료한 PID 37644와 19832의 고아 실행 잠금을 보존했다. 각 부분 RAW와 공유 원장의 미정산 전액을 유지했다. 반텐 후속 제한 배치에서 유효 창 추가와 일시적인 시간 초과를 기록했다.
- `VERIFIED_REAL` 승인된 반텐 Sentinel-2 전역 원본 224건, 21,626,452,905B의 전용 수집기가 PID 149980으로 실행 중이다. 기존 잠금 프로토콜로 중복 실행을 방지한다. 원본은 `data/raw/explorer/province/banten-optical/sentinel-native/` 아래에 받는다.
- `VERIFIED_REAL` Sentinel-2 2020년 5개 장면·35개 원본을 검산했다. 반텐 30m 등적 경계 안에서 6밴드 물리 피복 100%, SCL 적용 맑은 픽셀 87.53%, 동년 Esri와 공통 유효 영역 818,838ha다. 기존 Edge 화면에서 2020년 전역 RGB 조회, 2025년 대기 표시와 자료 현황의 피복률을 확인했다.
- `VERIFIED_REAL` 6개 주 Esri 수집에서 49M 2021 응답 본문이 중간에 끊겼다. 해시 검증을 마친 원본 13개를 유지하고 429에서는 중단하는 제한 재시도로 미완료 타일을 복구 중이다. 반텐 48M 6개 원본과 Sentinel-2·Landsat 수집 프로세스는 그대로 유지했다.
- `IMPLEMENTED_UNVERIFIED` 반텐 연차 Landsat·Sentinel-2 전부 수신 후 연차 QA, 공간 범위, 두 연도 전역 영상을 검증하는 자동 인수시험을 준비했다. 전체 광학 자료 수신·반텐 경계 검증 후 API·Worker 컨테이너 이식을 시작한다. Docker 엔진과 Kubernetes 컨텍스트 연결은 대기한다. [범위·시험 문서](docs/lcluc/INDONESIA_EXPLORER.md)


## 2026-11-25 LCLUC 행정경계와 반텐 전역 자료 확대

- `VERIFIED_REAL` One Map/BIG 2026-10-27 스냅샷의 6개 주·군시 129개를 검증했다. Edge에서 좌우 지도에 6개 주 이름과 Tangerang·Kota Tangerang, Sentinel-2·Landsat 레이어 전환, 변화·핫스팟 지도, WebGIS, 대시보드를 확인했다. Esri 9색과 행 간격 15px, 시가지·Clouds 필터를 확인했다.
- `VERIFIED_REAL` Esri v003 7타일×6연도(2020~2025) 전체 42개 원본을 HEAD로 확인했다. 예상 본문은 3,537,430,071B이며 반텐 48M 6개는 781,705,561B다. 반텐 파일을 먼저 받고 있다. 2020년 48M 원본의 139,102,310B와 SHA를 확인했고 1/6년을 확보했다.
- `VERIFIED_REAL` 반텐 경계 기준 후보 장면 계획은 각 연도에 Sentinel-2 5~7장, Landsat 8/9 4장을 찾았다. 연도별 100%는 STAC 장면 기하의 피복률이다. 6밴드와 품질 파일의 실제 유효 픽셀 피복률은 받는 중이며 QA 통과율은 미산출이다.
- `BLOCKED` Sentinel-2 공유 원장 잔여 1,594,369,596B, 활성 수집기 0, 이전 배치 실행 잠금 유지. 기존 서자바 2024의 실제 전송량과 정산 상태 확인이 필요하다. 새 Sentinel-2 원본 전송은 차단되어 있다.
- `VERIFIED_REAL` 반텐 2020년 One Map 경계 안의 10m 분석 격자는 935,602.88ha다. NoData 0ha, 구름 329.35ha, 토지피복 유효 99.9648%다. 연도 쌍 확보 후 전환 결과를 계산한다. [범위·원본·검증](docs/lcluc/INDONESIA_EXPLORER.md)


## 2026-11-25 LCLUC 분류 사전과 연차 변화 연결

- `VERIFIED_REAL` 기존 LCLUC Workspace의 지역·연도 필터, 7개 탭과 지도 조작부, 지표 카드에 Esri·Sentinel-2·Landsat·팔루 자료와 파일 다운로드를 연결했다. Edge에서 실제 5175 경로, 50:50, 원본 ZIP, 전환 행렬·결과 내보내기, 2023년 미등록을 확인했다. [사용·검증](docs/lcluc/INDONESIA_EXPLORER.md)
- `VERIFIED_REAL` 반텐 공통 구역의 Esri v003 2020·2025 연차 참조 1건을 공통 결과에 등록했다. 공통 유효 712.30ha 중 32.65ha, 4.58%의 지도상 변화를 계산했다. 해당 구역 Landsat 8·Sentinel-2 두 시점의 6밴드와 품질 원본 창, 팔루 재난 전후 NASA JPEG 2장까지 로컬 원본과 ZIP에 보존했다. NLCD는 인도네시아 범위가 없다. [비교 화면·출처·검증](docs/lcluc/INDONESIA_EXPLORER.md)
- `VERIFIED_REAL` 실행 화면의 비교 지도를 한 뷰포트와 중앙 구분선으로 변경했다. Edge에서 5175 반텐의 공개 참조 경계와 두 연도 미등록 배지, 동자바 전환을 확인했다. `TESTED_SYNTHETIC` 두 연도 레이어를 같은 위치에서 각각 절반씩 표시하고 390px에서 구분선을 드래그했다. [사용·검증 방법](docs/lcluc/WORKSPACE.md)
- `TESTED_SYNTHETIC` 이전 두 지도 비교 화면은 Edge 1440px와 390px에서 지도 정렬, 스와이프 전환, 공통 유효 면적·변화율, 미등록 연도 차단을 검증했다. 5175 실행 화면에 등록된 실제 사례는 0건이다. [사용·검증 방법](docs/lcluc/WORKSPACE.md)
- `VERIFIED_REAL` 정부 자료 두 경로에서 KLHK 코드·명칭 23개를 대조하고 버전·SHA로 고정했다. 품질 코드 2500(구름)은 분석 유효 면적에서 제외한다. 보존된 2024·2025 서비스 메타데이터의 원본 코드 도메인과 이용 권한은 대기한다.
- `TESTED_SYNTHETIC` 고정된 두 GeoTIFF, 동일 등적 격자·유효 마스크에서 전이행렬·집중지역·구역 통계를 계산한다. 합성 결과 공통 4ha, 변화 1ha, 25%를 검증했다. 회귀시험 37건과 Edge A~D, 전이 CSV, 동일 결과 ID 카탈로그 조회를 확인했다. 실행 중인 5175는 연도 정확 일치 자료만 표시하며 등록 사례는 0건이다.
- `TESTED_SYNTHETIC` Sentinel-2 6밴드와 SCL 품질 마스크를 사용하는 Random Forest와 Tiny U-Net을 동일한 합성 시험 252픽셀에서 학습·비교했다. 두 모델의 mIoU ≥ 0.50과 SHA 고정 모델 저장·복원 등 분류기 시험 12건을 통과했다. 실제 모델은 동년 독립 라벨·권리·승인·검증을 거쳐야 한다. [실행 계약](docs/lcluc/WORKSPACE.md)

## 2026-11-25 기관 실행·MLOps·저장소 연결

- `VERIFIED_REAL` Git 체크아웃 재현에서 CCKP 원본의 바이트 보존을 검사했다. `146fb5e` 이후 새 작업본에서도 기존 결과 ID와 패키지 SHA가 일치한다.
- `TESTED_SYNTHETIC` 기관 승인 작업의 제출·진행·취소, 재개 워커와 결과 ID 등록을 8건으로 검증했다. 신규 API와 React 프록시는 HTTP 200이며 Edge에서 운영 메뉴 세 곳과 결과 ID 직접 조회를 확인했다. 운영 공급자와 승인 문서가 없어 실제 제출은 대기한다.
- `VERIFIED_REAL` 기관 자료 6종 증거를 재검사했고, 1,779행에서 분할을 넘은 원본 장면 1개의 28행을 격리해 후보 1,751행과 적격 1,382행을 확보했다. 지리적 겹침과 독립 라벨 검사, 실제 학습은 별도다.
- `TESTED_SYNTHETIC` 실제 ONNX CPU 실행에서 모델 활성 버전을 바꾸고 롤백한 결과 11→12→11을 확인했다. 과학 검증 철회가 이후 실행을 차단한다.
- `VERIFIED_REAL` 격리 S3에 CCKP 검산 파일 3,295바이트를 저장하고 별도 버킷으로 복원해 SHA를 재검증했다. 익명·만료 접근을 차단했다.
- `BLOCKED` PostgreSQL/PostGIS·pgvector 통합 접속과 DB 복원 시험은 로컬 Docker에서 접속하지 못했다. 운영 클러스터·기관 권한·인수시험은 대기한다. [운영 연결과 인수 기준](docs/architecture/PLATFORM2_OPERATION_PATH.md)

## 2026-11-25 단일 ID 결과 카탈로그

- `VERIFIED_REAL` 기존 결과 ID에 CCKP CDD(40.91221481742199일, 12,765개 격자)와 반텐의 과거 RTRW 표본 1건을 연결했다. 출처·레이어·보고서·불확실성·검토 상태를 같은 ID로 조회한다.
- `TESTED_SYNTHETIC` 좌표계·기간·단위·NoData·원본 해시 및 과학 검증과 기관 공개 승인 저장·선후를 검증했다. 두 실자료의 과학 검증·공개 승인은 대기 상태다. [계약과 실행](docs/architecture/COMMON_RESULT_PATH.md)

## 2026-11-25 결과 검토 화면의 기존 SDSS 체계 반영

- `VERIFIED_REAL` 8014 작업화면에 기존 GeoAI–MLOps–SDSS의 청색 헤더·브랜드·업무 메뉴 7개·현재 위치·세부 탭을 반영했다. **리포트 & RDTR → 결과 검토**에서 기존 결과 10건과 RTRW 근거를 실제 Edge로 열었다.
- 1440px와 390px에서 메뉴 이동과 목록·상세 표시를 확인했다. 결과 등록과 검토 저장은 분리된 시험 원장에서 검증한다. [화면 구조와 시험 근거](docs/ui/API_UI_E2E.md)

## 2026-11-25 공통 결과 등록·검토·조회

- `VERIFIED_REAL` 증거 검증 → 공통 SQLite 결과 등록 → ID 재조회 30단계를 실행했다. 10건을 로컬 원장에 등록했으며 `/api/results`와 `/api/workflow`에서 범위를 조회할 수 있다. 실제 Edge에서 임시 DB로 결과 등록·수정 요청·검토 완료·필터·새로고침 후 재조회를 확인했다.
- `BLOCKED` 6개 주의 현행 RTRW 원본은 0/6이며 BIG 레이어 집계 93,340건과 반텐 과거 버전 벡터 표본을 고정했다. KLHK 공식 연차자료·23종과 권한, 실제 승인 embedding·공개 RAG, 운영 Data Lake 전환은 대기한다. 원본 장면 1개가 validation/test에 동시에 있어 모델 분할 재구성이 필요하다. 독립 정확도와 사람·배포 승인은 대기한다.
- `BLOCKED` 후속 Sentinel-2는 36개 중 8개 수신·5개 SCL 통과 후 프로세스가 사라졌다. 서자바 2024 아홉 번째 창은 전송 시작 상태이며 정산 영수증을 찾지 못했다. 기존 진행 파일에는 `RUNNING`이 남아 있고 실제 프로세스는 종료돼 있다. 원장 예약은 보존했다.
- 병렬 작업 1~8의 담당·완료 기준과 실행 방법은 [공통 결과 경로](docs/architecture/COMMON_RESULT_PATH.md)에 기록했다.

## 2026-11-25 Sentinel-2 경계 내 후속 수집

- `VERIFIED_REAL` One Map/BIG 개발용 경계와 정확한 동시 관측 미수집 도형 안에서 6개 주 × 2020~2025년 36개 조합에 256×256 창을 하나씩 고정했다. 첫 순회는 동자바 2023, 남술라웨시 2024, 서자바 2023, 남동술라웨시 2025, 고론탈로 2023, 반텐 2023 순이다.
- `VERIFIED_REAL` 동자바 2023의 동일 장면 B02/B03/B04/B08/B11/B12와 SCL 자산 7개를 받았다. 29요청, 7,471,504B, 429 0, SCL 유효 비율 49.47%다. 동시 관측은 6.553964km², 유효 관측은 3.242726km² 늘었다. 첫 창을 품질 미달로 기록했고 11:42 KST에 단일 백그라운드 수집기(PID 37644)가 남술라웨시 2024를 수집 중임을 확인했다. 첫 창 재수집은 없었다. 첫 정산 잔여 1,671,049,526B이며 36개 창의 예약 상한 합계는 1,207,959,552B다. 진행 기록은 `evidence/onemap_sentinel/coverage-batches/20261125-pass01/progress.json`에 남긴다.
- `VERIFIED_REAL` 11:45 KST에는 36개 중 4개를 받았다. 남술라웨시 2024의 SCL 유효 비율은 100%, 서자바 2023은 99.98%로 통과했다. 남동술라웨시 2025는 52.61%로 품질 공백이며 고론탈로 2023을 수집 중이다. 429는 0건이며 직전 정산 잔여는 1,653,877,886B다.
- `TESTED_SYNTHETIC` 계획 순서, 공유 원장, 창 고정, 수집기 시험 20건을 UTF-8 모드에서 통과했다. 7개 자산을 모두 받은 창은 SCL 유효 비율 80% 미달 시 품질 공백으로 기록하고 다음 창을 수집한다. 전송 실패 또는 429 발생 시 중단한다.
- `PLANNED` 배치 완료 뒤 관측 면적을 재감사한다. 기존 UI는 이전에 검증한 36셀 스냅샷을 표시하며, 배치 기록에서 실시간 진행을 확인할 수 있다. 새 관측 창은 독립 라벨과 학습 적격 심사를 별도로 거친다. 공식 BIG 경계 승인과 전체 공간 피복은 계속 대기한다.

## 2026-11-25 수집 현황과 Data Lake 로컬 이전

- `VERIFIED_REAL` 8012의 수집 현황에서 6개 자료군을 목표·확보·미확보·진행률로 확인했다. 기존 메뉴 순서와 Sentinel-2 화면을 유지했다. Edge에서 상세 펼치기와 390px 너비를 확인했다.
- `VERIFIED_REAL` 기존 SHA 객체 6,125개를 재검증했다. 레거시 참조 파일 26개와 프로젝트의 고정 원본을 합쳐 새 내용 주소 객체 35개(377,564,224B)를 썼다. 새 카탈로그에 객체 6,175개와 출처 참조 6,721건을 등록했다.
- `VERIFIED_REAL` 레거시 SQLite를 29개 레코드의 보존본으로 복사하고 기존 검토용 VectorDB의 122개 청크를 등록했다. 이전 영수증은 `evidence/data_lake/local-handoff-20261125.json`이다.
- `BLOCKED` 운영 DB·버킷의 프로젝트 소유 원본·대상이 확인되지 않아 실제 PostGIS/pgvector 및 S3 호환 서비스 전환은 대기한다. CCKP 전체 변수·기간·시나리오와 보고서 전체 목록은 미확정이다.

## 2026-11-25 Sentinel-2 시험 반영 재감사

- `VERIFIED_REAL` 보유한 36셀 관측 도형과 동자바 2023 시험 원본을 재검증했다. 동자바 2023의 동시·유효 피복에 각각 6.556514km²를 추가했다. 36셀 동시 피복률은 0.977325%, 유효 피복률은 0.890387%이며 미수집 면적의 주·연도 합계는 1,112,571.999km²다. 72개 미수집·품질 공백 도형은 EPSG:6933 정확 차집합으로 저장했다.
- `PLANNED` 주별 최대 미수집 면적 기준 다음 검토 순서는 동자바 2023, 남술라웨시 2024, 서자바 2023, 남동술라웨시 2025, 고론탈로 2023, 반텐 2023이다. 256×256 창을 후보별 하나씩 받는 시나리오의 응답 본문 예상 합계는 44,829,036B다. 전체 공백 전송량은 미산정이며 원격 창 고정과 BIG 경계·목표·예산 승인이 남았다.
- `VERIFIED_REAL` 로컬 API 8011과 실제 Edge 158에서 재감사 지표, 36셀 상세 펼치기, 후보 6개와 42.75MiB를 확인했다. 페이지 JavaScript 오류는 0건이다. 재감사에서 원격 전송 0, 원장 쓰기 0, 신규 수집기 0이다. 품질 적격 패치는 1,407개이며 학습 준비·독립 정확도·배포 승인은 미충족이다.
- `BLOCKED` 지속 워크플로 상태 파일은 현재 누락되어 API가 `EVIDENCE_SOURCE_MISSING:workflow`를 반환한다. 모델 계약과 합성 시험 결과는 보존돼 있다. KLHK 공식 23개 클래스와 라이선스 검증, 기후 보고서 인덱스의 승인된 embedding·접근 권한 검증이 남았다.

## 2026-11-24 시험 직후 상태

상태 라벨은 `VERIFIED_REAL`, `TESTED_SYNTHETIC`, `IMPLEMENTED_UNVERIFIED`, `BLOCKED`, `PLANNED`만 사용한다.

- `VERIFIED_REAL` One Map 6개 주 x 2020~2025년 36셀 감사 완료. 1,779개 패치, 1,407개 품질 적격 패치, 119개 parent frame을 검증했다.
- `VERIFIED_REAL` 6밴드와 같은 장면 SCL 동시 공간피복은 0.976741%, clear 피복은 0.889803%다. 전체 공간수집 완료는 `false`다.
- `VERIFIED_REAL` 검증 자료 6,125개 객체, 3,904,601,927바이트를 `data/raw/migrated/{sha256}`에 독립 복사했다. 원본 CAS와 기존 manifest는 불변이다.
- `VERIFIED_REAL` 공유 전역원장 adapter, 고정 scene/asset/window planner, 제한 Range 전송기를 구현하고 East Java 2023 한 창의 동일 장면 6밴드+SCL pilot을 수행했다. QA clear 65,536/65,536, 본문 7,471,506바이트, 28요청, 오류·관측된 429는 0건이다.
- `VERIFIED_REAL` pilot 정산 뒤 전역원장 SHA는 `b257db2925e5c4eac99081c5539216314c972d49dd6741f38f5780da7dd25de1`, 잔여 예산은 1,678,521,030바이트다. 후속 pilot·collector·lock은 모두 0이다.
- `BLOCKED` exact 누락 큐는 72개 feature이며 pilot 뒤 36셀 공간피복 aggregate는 아직 재감사하지 않았다. 기존 0.976741%는 pilot 전 snapshot이고, 한 창 성공은 전체 수집 완료가 아니다.
- `VERIFIED_REAL` CCKP CDD 표본의 Indonesia 개발 bbox 면적가중 평균은 40.9122148174 days다. 행정경계 평균·전망·독립 정답이 아니다.
- `IMPLEMENTED_UNVERIFIED` 기후 보고서 로컬 검토 VectorDB는 7문서/122청크다. hash embedding 품질, 라이선스 공개 범위, steward 인증이 미완료다.
- `BLOCKED` KLHK native 23개 클래스 domain·라이선스, 독립 지상 정답, 실제 모델 학습·독립 정확도·사람 승인·운영 배포가 미완료다.
- `VERIFIED_REAL` 로컬 API/UI를 Edge에서 기능별로 클릭 검증했다. 읽기 전용 화면이며 collector·학습·배포를 시작하지 않는다.

## 시험 수집 직후 대기열 (2026-11-24 기록)

1. 완료된 단일 pilot의 evidence를 API/UI evidence lock과 `docs/understanding/`에 인계한다.
2. pilot 관측을 포함해 36셀 공간피복 aggregate를 재감사하는 별도 Gate를 준비한다.
3. 전체 누락 큐 317,455,915바이트는 계획 메타데이터 기준이고 실제 원격 COG 전송량과 다르므로, 잔여 1,678,521,030바이트로 전체 수집 가능하다고 가정하지 않는다.
4. 추가 원격 수집은 BIG 권한·공간피복 목표·예산 승인을 받은 뒤 공유 원장 예약을 통해서만 수행한다.

## 다음 Gate

1. BIG 경계의 권한·시점·통계 사용 승인.
2. 6개 주 x 6개 연도의 6밴드+SCL 공간피복 목표와 현실적인 예산 승인.
3. KLHK 연차 원본의 23개 클래스 domain, 라이선스, 버전·취득시각 고정.
4. immutable dataset/split, leakage 0, 독립 정답을 이용한 실제 학습·평가.
5. 약한 참조 일치도와 독립 정확도를 분리한 사람 승인·rollback·배포.
6. 승인된 embedding과 ACL을 적용한 운영 VectorDB 및 공개/비공개 검색 경계.

## 보고 원칙

- 실제 프로세스, 에이전트, 예약 상태를 구분한다.
- 패치 개수만으로 공간수집 완료를 주장하지 않는다.
- WorldCover 2021을 다른 연도의 정답으로 사용하지 않는다.
- 실제 독립 정확도와 약한 참조 일치도를 분리한다.
- UI·문서·단일 Gate 완료를 전체 프로젝트 완료로 보고하지 않는다.
