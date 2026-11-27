# 이해자료 변경 이력

## 2026-11-27 — GeoLLM 반텐 토지피복 질의응답

- `V42_LCLUC_GEOLLM_QUERY.md` 신규 작성
- 한국어·인도네시아어·영어 질문을 공식 문서 RAG 또는 MapBiomas·Esri 정형 GIS 도구로 라우팅하는 흐름을 설명
- MapBiomas 2023→2024 산림 총전환 3,146.85ha와 산림 순변화 −1,265.58ha를 `TRANSITION`·`COVERAGE`의 서로 다른 지표로 기록
- MapBiomas 수치는 발행자 반텐 통계이며 One Map/BIG 경계는 위치 맥락임을 명시
- Esri 2023→2024 수목→시가지 3,561.79ha와 실제 v003 전이 PNG를 `VERIFIED_REAL`로 기록
- Kemenhut 원본·overlay·독립 정확도를 `BLOCKED`, 읽기 전용 `result_id=null`을 결과 registry 미연결로 구분
- 다국어 intent·총전환/순변화·margin·미발행 값·기간 차단 계약시험과 Edge RAG·GIS·출처·SHA 증거를 반영

## 2026-11-26 — 두 센서 3모델 비교와 토지피복 원본별 집계

- 기존 모델 시험 이해자료에 경량 DeepLabv3+와 센서별 RF·Tiny U-Net·DeepLabv3+ 동일 표본 비교를 추가
- Landsat 72,391픽셀에서 DeepLab 약한 참조 67.7584%→필터 뒤 67.9670%·1,865픽셀, Sentinel-2 76,230픽셀에서 63.7413%→63.8725%·1,360픽셀을 `VERIFIED_REAL`로 기록
- 두 센서 benchmark API, 여섯 분류 GeoTIFF SHA, Edge 센서 전환·DeepLab 후처리 실행을 분류기·API·브라우저 증거로 분리
- `V42_BANTEN_ESRI_MAPBIOMAS_AREA_COMPARISON.md`를 원본별 집계와 공식 비교 기준 문서로 정정
- 공통 연도 2020~2024에서 Esri 원본 9행과 MapBiomas 발행 11행을 별도로 표시하고 Edge 2020·2024 선택을 `VERIFIED_REAL`로 기록
- 2024 Esri 935,602.88ha를 유효 935,224.83ha·구름 378.05ha·NoData 0ha로 분해하고 MapBiomas 발행 935,005.55ha와 클래스 차이·전이 수치를 만들지 않도록 정정
- Kemenhut 동년 Penutupan Lahan 23클래스를 공식 비교 기준 `BLOCKED`, 독립 조사 표본 정확도를 별도 `BLOCKED`로 분리
- LANDY R01~R14 문서, 4.1 통계 XLSX·반텐 35년 11클래스와 `TRANSITION` 반텐 113행의 GeoLLM 정량 연결을 `VERIFIED_REAL`로 유지. 반텐 연차 분류·전이 GeoTIFF와 발행 집계 경계 도형은 `BLOCKED`로 분리

## 2026-11-26 — 반텐 모델 시험·특화 분류와 MapBiomas GeoLLM 지식

- `V42_LCLUC_MODEL_TRIALS_AND_SPECIALISTS.md`와 `V42_MAPBIOMAS_GEOLLM_KNOWLEDGE.md` 신규 작성
- 실제 2020 Landsat·동년 Esri에서 RF와 Tiny U-Net을 학습 19,647·같은 공간 홀드아웃 72,391로 비교하고 약한 참조 일치도 71.4205%·66.3356%를 `VERIFIED_REAL`로 기록
- 3픽셀·8방향 후처리의 RF 75.09%·31,658픽셀, Tiny 66.49%·1,885픽셀과 2020→2025 Siamese 64,658픽셀 변화 F1 0.288265→0.288352를 반영
- Edge에서 RF·Tiny 같은 표본, 전후 Swipe, Siamese 변화 지도와 동년 계층 입력 차단을 확인
- 특화 분류 우선순위·충돌·NoData 보호·타년 거부 계약과 별도 파일 기반 11픽셀 계층 통합을 `TESTED_SYNTHETIC`으로 기록
- MapBiomas 공식 원문 14건·P0 9건, 286청크, 용어 44·참조 지도 25·범례 5와 Edge 한글·영문 3질의·PDF 페이지·출처 링크를 `VERIFIED_REAL`로 기록
- 모델·RAG 관련 회귀 24 PASS와 별도 계층 통합 1 PASS를 구분
- 독립 정확도·운영 승인·실제 동년 특화층·GEE 권한과 음성·embedding·생성 답변을 `BLOCKED`로 유지

## 2026-11-26 — LCLUC 후처리 및 품질관리 이해자료

- `V42_LCLUC_POSTPROCESS_QUALITY.md` 신규 작성
- 반텐 2020 Landsat RF 후보의 Spatial Filter 실자료 실행 `e8f1b2…ad4a4`, 최소 4픽셀·4방향, 61,274픽셀·129,889.72ha를 `VERIFIED_REAL`로 기록
- 같은 72,391픽셀 공간 홀드아웃에서 Esri v003 약한 참조 일치도 71.4205%→75.3574%를 확인하고 독립 정확도 `REFERENCE_REQUIRED`를 분리
- Edge에서 메뉴·실행, 전후 Swipe, 보정 위치·면적·품질·이력, 원본·보정본·보정 mask GeoTIFF 3개 SHA 다운로드, 새로고침 재조회, 기존 Workspace 진입을 확인
- NoData·수역·침수 식생·구름 보호와 4·8방향 연결 차이 2건을 `TESTED_SYNTHETIC`으로 기록
- MapBiomas ATBD·고정 GitHub commit 검토와 Rasterio/GDAL sieve 자체 구현의 차이를 명시
- 약 147m 표시 격자의 `REVIEW_CANDIDATE`로 한정하고 운영 최소 면적·독립 평가를 `BLOCKED`, Temporal·Gap·Frequency·Incident·Hierarchical Integration을 `PLANNED`로 유지

## 2026-11-26 — 반텐 Landsat 장기 분석 Explorer 이해자료

- `V42_LCLUC_LANDSAT_EXPLORER.md` 신규 작성
- 2020~2025 실제 Landsat 24장면과 Natural Color·Agriculture·Urban·SWIR·NDVI·NDMI·MNDWI 7개 발행 layer를 `VERIFIED_REAL`로 기록
- 2020~2022 기간 합성의 맑은 관측 1회 이상 97.8617%, 2회 이상 90.5761%와 `CLEAR_OBSERVATIONS`의 의미를 분리
- 2023~2025 기간 합성의 맑은 관측 1회 이상 99.8192%, 2회 이상 98.0107%를 실제 manifest로 추가 확인
- 최종 Edge 로그에서 실제 PNG 요청, 7개 preset, 지도 폭 886.95px, 역사 구간 1990→2020 Swipe와 1990·2000·2010·2020 Time-Series, 시작점 자동재생·순차 진행·T2 정지, Sentinel·연차 조작부 복원을 확인
- 2020 RF 공간 블록 홀드아웃 72,391픽셀의 Esri v003 약한 참조 일치도 71.4205%를 기록하고 독립 정확도 미측정을 유지
- MapBiomas 1990~2024 35년·11클래스를 발행 반텐 주 통계로 설명
- Landsat 5 TM 단일 장면 1988·1990·2000·2010의 manifest·API·원본 SHA와 합계 1,257,798,910B, 맑은 관측 47.88%·50.83%·40.30%·32.14%를 `VERIFIED_REAL`로 기록
- 센서별 밴드·QA·NoData 단위시험 2건을 `TESTED_SYNTHETIC`, 픽셀 변화 발생시점과 LandTrendr·CCDC를 `PLANNED`, 독립 정확도를 `BLOCKED`로 구분

## 2026-11-26 — 반텐 Sentinel-2 Explore Gate 이해자료

- `V42_LCLUC_SENTINEL_EXPLORER.md` 신규 작성
- native 10m B02·B03·B04·B08과 20m B11·B12·SCL의 원본 SHA 검사, 30m EPSG:6933 최근접 정합과 결정적 연차 합성을 설명
- 자연색·CIR·NDVI·NDWI·NBR·QA PNG와 반사도 6band+지수 3+QA의 10-band GeoTIFF 역할을 분리
- 원본 수집, 장면 선정, 광학 처리, Esri 10m 분석, read-only API/UI 모듈을 서로 다른 단계로 기록
- 초기 단계에서 실제 2020 API의 서로 다른 PNG 6종과 30m GeoTIFF를 먼저 `VERIFIED_REAL`로 확인
- 후속 Edge에서 2020↔2025 자연색·CIR·NDVI·NDWI·NBR, Esri·QA·변화 3중첩, 범례·경계·swipe와 두 날짜 Explore를 `VERIFIED_REAL`로 확인
- 사용자 사각형과 반텐 교차 AOI 53,155.27ha, 연차 전이 5개, CSV 112행 다운로드를 실제 확인
- Esri 참조 2020~2025 6/6년과 가능한 변화 15/15쌍을 발행·audit했으나 Sentinel 중간 2021~2024 분광 파생은 CPU 처리 중으로 6/6 완료를 선반영하지 않음
- 최종 발행 검산에서 Sentinel 32장면·2020~2025 6/6년·화면 PNG 36개·30m 10-band GeoTIFF 6개를 `VERIFIED_REAL`로 갱신. Esri 6년·15쌍 유지
- API에서 주 전체 pin 합계와 사용자 AOI 39,631.96ha, 비율·전이행렬·점·지수 공식·GeoTIFF 다운로드를 확인하고 단위시험 2 PASS·frontend build PASS 반영
- 최종 Edge/HTTP exit 0: 53,155.27ha AOI·112행 CSV와 시작 연도 2024 변경 뒤 NBR 선택 유지·정확한 2024→2025 변화 layer 연결을 `VERIFIED_REAL`로 반영
- AOI 전이행렬 합계와 `기준→비교` 방향 전이 PNG를 사각형·반텐 경계로 함께 절단하는 API를 `VERIFIED_REAL`, 방향·AOI 절단 fixture를 `TESTED_SYNTHETIC`으로 반영
- MapBiomas Indonesia Collection 4.1 발행 반텐 주 통계 1990~2024 35년·11클래스를 `VERIFIED_REAL`로 추가하되 사용자 AOI·Esri 통계와 분리
- 2021 Esri v003↔WorldCover v200을 10m·6대분류로 비교한 926,628.52ha·지도 일치도 80.9456760515%를 반영. 적용 범위는 2021년이고 독립 정확도는 미측정
- Edge 5175에서 면적표, layer 목록 접기·펼치기, 5영상·4 switch, 방향 지도·순위 필터, 실제 AI 접수 상태, 35년 다운로드, 2021 제품 행렬을 클릭 확인
- 최종 재실행에서 결과 화면 `AOI 지정`의 두 모서리 클릭→52,128.16ha 표 반환과 14px switch 첨부형 목록을 확인하고, LCLUC 회귀 `44 passed, 2 skipped`를 기록
- 이전 UI 단계에서 Sentinel-2 선택 시 결과 5탭·기능 6개를 지도 바로 아래에 배치한 Edge 5175 경로를 역사로 기록. 연도·AOI 결속 범위는 클래스 면적·비율·전이행렬·세부 변화탐지로 현행화
- 최종 Edge 전환·회귀에서 지도 다음 형제 위치의 패널 한 개와 AOI 52,128.16ha가 실제 결과·보고서 상단 탭 이동 중 유지됨을 확인. Landsat·연차 Esri 선택 시 해제, Sentinel-2 재선택 시 AOI 복원, `상세 결과` 포커스 이동, 2024→2025 재계산 표 갱신을 모두 `VERIFIED_REAL`로 기록
- 오른쪽 두 카드를 `연차 토지피복 주요 지표 (Banten)`과 `연차 토지피복 주요 전이`로 명명하고 Esri / Impact Observatory v003·반텐주 전체·선택 연도쌍을 함께 표시하는 출처 코드를 반영
- 지도 아래 Sentinel 패널에 영상·지수·품질은 Sentinel-2 L2A, 클래스 면적·비율과 전이행렬은 선택 AOI의 Esri 연차 토지피복 집계라고 표시. Edge에서 두 카드의 Esri v003·반텐주 전체·2020→2025, Sentinel-2 전환 후 수치 유지, AOI 출처 문구를 확인해 `VERIFIED_REAL`로 기록. frontend build 통과, API와 산식은 기존 범위 유지
- 이전 전체 폭·기본 2카드 단계의 Edge 검증 기록을 역사로 보존
- 최종 Edge 회귀에서 연차 카드 복원, Sentinel-2 재선택, AOI 63,176.20ha와 2024→2025 두 카드 공유, 다른 4탭·swipe 관련 데이터와 버튼 클릭을 `VERIFIED_REAL`로 기록
- 현행 Sentinel Workspace를 연차 비교와 같은 2열 지도 구조로 개정. 1650px에서 두 모드 지도 폭 886.95px, 오른쪽 클래스 면적·비율·AI 신규 분류 2카드, 하단 전이행렬·세부 변화탐지·장기 추세·제품 간 검증 4카드, 920px 세로 배치를 `VERIFIED_REAL`로 기록
- Sentinel 선택 시 상단 7개 항목을 지도 분석과 6개 결과 제목으로 바꾸고 실제 클릭의 스크롤·초점 이동과 여섯 실자료 카드 내용을 확인
- Swipe T1/T2를 2022→2024로 바꿔 API·상단 필터·지도·AOI 표의 동시 갱신, 유효 연도 선택지, 50:50 복귀를 확인. 범례 보조 영역 정리, AOI 도구 점 조회, 행정경계 switch, 연차 화면 복원도 최종 Edge 통합에 반영
- Sentinel/Landsat QA 지원표를 제품 지도 일치도와 분리하고, 생산 연차 AI 실제 접수 0건·독립 검증 미산출을 `BLOCKED`로 유지
- 단위시험 2 PASS(8.46초)와 frontend build PASS(대형 chunk 경고만)를 기록
- Esri 면적·비율·전이는 같은 공급자 참조 분석이며 `independent_accuracy_measured=false`, One Map 경계 사업통계 승인도 `BLOCKED` 유지

## 2026-11-26 — LCLUC 연차 입고·후보 모델·검증 Gate 이해자료

- `V42_LCLUC_ANNUAL_INTAKE_GATE.md` 신규 작성
- `lcluc-annual-input/1` 번들의 상대 경로·byte·SHA·출처·연도·분류사전 결속과 Sentinel-2/Landsat 필수 6밴드+QA 계약을 설명
- 30m EPSG:6933 결정적 합성, 물리 피복 95%·clear 80% 품질 Gate, 동년 라벨과 bundle run 결속 승인이 있어야 센서별 RF 후보를 만드는 흐름을 설명
- 동년 센서 간 지도 일치도, 약한 지도 참조 일치도, 독립 정확도, 합성 holdout을 서로 다른 평가축으로 분리
- 독립 검증은 학습·약한 참조와 source/provider/SHA 분리, protocol·authority·승인, 학습 위치와 인접 1셀 제외, 센서별 최소 100표본을 요구함을 명시
- Docker 5180과 kind Kubernetes 5181에서 격리 합성 반텐 2026 번들을 독립 실행해 `WAITING_INPUT→WAITING_TRAINING_APPROVAL→WAITING_INDEPENDENT_REFERENCE→TESTED_SYNTHETIC` 전이를 확인
- 양 환경의 두 센서 clear 1,023/1,024픽셀, 합성 holdout 256개, cover·confidence 4 GeoTIFF SHA 재대조와 `independent_accuracy=null`을 `TESTED_SYNTHETIC`으로 기록
- Docker·Kubernetes worker 재시작 뒤 마지막 검사 시각 갱신과 동일 완료 상태 재조회를 확인. 격리 시험 worker 종료 뒤에도 증거 조회 UI는 유지되고 실자료 전용 60초 watcher만 활성 상태임을 분리
- 양 환경 실제 Edge에서 기존 Sentinel-2 2020 지도와 합성 2026 상태 행·증거 링크 클릭을 확인하고, 회귀 45 PASS·1 SKIP을 반영
- 실자료 전용 Docker watcher가 synthetic 비활성으로 실제 inbox를 60초 간격 감시 중이며 운영 접수 0건임을 `VERIFIED_REAL`로 분리
- 실제 2026 원본·동년 라벨·독립 참조가 없어 실제 후보·일치도·독립 정확도·공공 배포는 계속 `BLOCKED`
- WorldCover 2021 타연도 정답 금지, 후보 RF confidence가 독립 정확도나 production release가 아님을 INDEX·용어집·발표·FAQ에 반영

## 2026-11-24 — v4.2 공통 기후 계약·Climate RAG 초기 이해패키지

- `V42_CLIMATE_FOUNDATION_AND_RAG.md` 신규 작성
- `INDEX.md`, `GLOSSARY_KO_EN.md`, 발표 대본, FAQ 신규 작성
- contract 5개 + RAG 18개 = 23개 합성 시험 통과 근거 반영
- 실제 CCKP 수치·공식 문서 인덱스·기관 인증·semantic embedding·API/UI는 미검증/차단으로 구분
- WorldCover 약한 참조와 독립 정확도, authority 문자열 결속과 실제 기관 승인을 분리

## 2026-11-24 — CCKP source·climate lake·feature planner 인계 반영

- 실제 CCKP 검증 범위를 S3 목록 5페이지 5,289B와 NetCDF HEAD 1건으로 제한해 기록
- NetCDF 본문 0B, Indonesia 식별자/국가 prefix 미확인, 실제 download plan `BLOCKED` 반영
- CCKP source 합성 24 PASS와 receipt·재개·예산·429 fail-closed 계약 설명 추가
- climate lake 12 PASS와 feature planner 12 PASS 반영
- 실제 join·numeric feature·학습·배포 0건, `execution_started=false`, `numeric_features=null` 명시
- 전체 합성 증거를 contract/RAG 23 + source 24 + lake/feature 24 = 71 PASS로 갱신

## 2026-11-24 — KLHK/RAG ingestion·MLOps Gate 반영

- `V42_KLHK_RAG_MLOPS_GATES.md` 신규 작성
- `VERIFIED_REAL` 범위를 metadata 원본 7개·122 span·381,676B·raw SHA mismatch 0으로 제한
- KLHK 2024/2025 renderer 25항목과 native 23-class domain·license 미확인을 분리
- 실제 문서 운영 index 게시 0, quantitative RAG answer 0, 기관 authority 미인증 명시
- ingestion 신규 11 + 기존 RAG 18 = 29, MLOps 6 합성 PASS 반영
- WorldCover/KLHK 약한 참조와 독립 ground truth, 합성 READY와 실제 학습·배포를 분리

## 2026-11-24 — CCKP Indonesia 개발 bbox 수치 도구 반영

- `V42_CCKP_INDONESIA_NUMERIC_TOOL.md` 신규 작성
- 4,209,592B 원본 SHA pin, 승인된 Range 17 chunk 재개, `NETCDF3_CLASSIC`·CF-1.6 검증 반영
- bbox CSV 12,765행과 1951–1980 제공 CDD climatology 구면가중 평균 40.91221481742199 days 기록
- 합성 12 + 실원본 read-only 재현 2 = 14 PASS 반영
- 인도네시아 행정경계 평균·연별/월별 시계열·독립 ground truth가 아님을 명시
- HTTP/RAG live 등록, curated 등록, 학습, 배포 0건을 분리

## 2026-11-24 — One Map·Sentinel·UI·모델·워크플로 최종 통합 인계 반영

- `V42_FINAL_INTEGRATION_STATUS.md` 신규 작성
- Sentinel 36/36 최소 수량 감사와 paired 0.976741%·clear 0.889803% 공간 피복을 분리
- 약 99% 공간 공백, reservation adapter와 exact scene/asset/window pin 부재를 `BLOCKED`로 명시
- 로컬 CAS 6,125객체·3,904,601,927B 이관과 원격 download/write 0건 반영
- 실제 Edge 클릭 검증과 API 11 PASS·Playwright 3 SKIP을 서로 다른 증거로 기록
- 모델 adapter 14 PASS와 오케스트레이터 5개 합성 계약시험을 `TESTED_SYNTHETIC`으로 반영
- 모델 spec과 private `synthetic-hash-64-v1` VectorDB 의미 품질을 `IMPLEMENTED_UNVERIFIED`로 구분
- KLHK native23/license, 독립 ground truth/accuracy, 실제 학습·배포, public RAG를 `BLOCKED`로 유지
- WorldCover 2021은 타연도 정답이 아니며 weak agreement와 independent accuracy가 다름을 재강조
- 진행 중 data follow-up adapter는 완료 범위에서 제외

## 2026-11-24 — East Java 2023 Sentinel 단일 실제 pilot 반영

- `V42_SENTINEL_SINGLE_PILOT.md` 신규 작성
- 고정 scene의 same-scene B02·B03·B04·B08·B11·B12+SCL 및 clear 65,536/65,536를 `VERIFIED_REAL`로 반영
- 28개 원격 요청·본문 7,471,506B·오류 0·관측 429 0 기록
- ledger SHA `8e98...aa44a`→`b257...25de1`, 잔액 1,678,521,030B와 후속 pilot·collector·locks 0 반영
- 기존 reservation/scene pin 미구현 설명을 단일 pilot 경로 구현·실행 완료로 정정
- pilot이 36셀 aggregate에 미반영되어 0.976741%는 이전 snapshot임을 명시
- 전체 공간 완료·전체 예산 충분성·BIG 승인·독립 정확도·학습·배포는 `BLOCKED` 유지
- WorldCover 2021 타연도 ground truth 금지와 weak agreement/independent accuracy 분리 유지

## 2026-11-25 — East Java pilot 반영 36셀 exact geometry 재감사

- `V42_SENTINEL_POST_PILOT_REAUDIT.md` 신규 작성
- 실 저장 geometry로 36셀과 72개 exact missing feature를 재산출한 결과를 `VERIFIED_REAL`로 반영
- East Java 2023 present·clear 면적 각각 +6,556,514.480755895m² 기록
- 현재 피복률 present 0.9773249834093871%, clear 0.890386955270514%로 갱신
- pilot 전 0.976741%·0.889803%는 역사적 snapshot으로 보존
- 재감사 중 collector·remote download·ledger write 0 명시
- 실측 7,471,506B×추천 6창=44,829,036B는 참고량이며 전체 전송량·실행 승인·예산 충분성이 아님을 명시
- 재감사 API/UI는 로컬 8011과 Edge 158 클릭으로 `VERIFIED_REAL`. 36행, 6후보, 예상 42.75MiB, 페이지 오류 0을 확인
- 전체 공간 완료·BIG 승인·독립 정확도·학습·배포 `BLOCKED` 유지

## 2026-11-25 — Sentinel 경계 내 36창 후속 배치 시작

- `V42_SENTINEL_BACKGROUND_COVERAGE_BATCH.md` 신규 작성
- 6개 주×2020~2025년 36창, 미계획 셀 0, 경계·exact missing geometry 내부, 기존 footprint overlap 0 계획 반영
- 창당 32MiB 예약과 주 round-robin 첫 6창 순서, 429·실제 전송 실패 정지 계약 기록
- 완전 전송 SCL 80% 미달은 quality gap으로 분리하고 다음 창을 계속하는 최종 구현 반영
- Root UTF-8 시험 20 PASS 반영
- 11:44 KST PID 37644, 3/36 수신·QA 통과 2·Southeast Sulawesi 2025 진행 상태 기록
- East Java clear 49.47%와 South Sulawesi clear 100%, 누계 18,351,282B·429 0·잔액 1,660,169,748B 반영
- 신규 present 약 19.640308km²·clear 약 16.327472km²와 학습 적격 0을 분리
- 전역 피복은 후속 aggregate 재감사 전 기존 0.9773249834093871%·0.890386955270514%로 유지

## 2026-11-25 — 공통 결과 등록·검토·조회 Gate 및 최신 blocker 반영

- `V42_COMMON_RESULT_REVIEW_GATE.md` 신규 작성
- 실제 프로젝트 registry 10개 결과와 verify/register/lookup 30단계 성공·ID 재조회 일치 반영
- 실제 Edge 선택시험 5 PASS와 DOM 계약 2 PASS, 전체 pytest 235 PASS를 서로 구분해 기록
- 현재 로컬 8014의 10 result·PENDING 10·30단계 scope·One Map 상세 UX·JavaScript 오류 0 반영
- UI 수정 요청·검토 완료 이력은 임시 DB이며 프로젝트 registry의 10개 결과는 모두 PENDING임을 분리
- evidence state와 review status를 분리하고 `ACCEPTED`가 과학적 차단 해제·학습·배포 승인이 아님을 명시
- Sentinel 11:44 `RUNNING` 기록을 역사적 snapshot으로 보존하고, 12:05 worker 종료·8/36·QA 5·9번째 32MiB pending 미정산을 현재 `BLOCKED` 상태로 갱신
- 현행 RTRW 0/6, Banten 역사 샘플·BIG 93,340 record의 제한, KLHK native23/license 미확보를 반영
- private hash RAG 7문서·122 chunk, 원본 scene validation/test 중복, 운영 Lake cutover 미검증을 blocker로 반영
- WorldCover 2021 타연도 정답 금지와 weak agreement·independent accuracy 분리를 유지

## 2026-11-25 — 결과 카탈로그와 과학·게시 이중 승인 Gate 반영

- `V42_RESULT_CATALOG_AND_GOVERNANCE.md` 신규 작성
- 기존 공통 결과 ID에 출처·수치·공간 layer·보고서·불확실성을 SHA 고정 패키지로 연결하는 구조 설명
- 실제 CCKP seed의 `40.91221481742199 days`, 12,765 Point GeoJSON, 보고서 2개를 `VERIFIED_REAL`로 반영
- 실제 BIG 반텐 seed를 역사 폴리곤 1개로 제한하고 현행 시기·법적 효력·권리·전체성 미확인을 유지
- 두 seed 모두 불확실성 `NOT_REPORTED`, scientific/publication `PENDING`임을 명시
- 일반 업무 검토, 독립 과학 결정, 기관 게시 결정을 서로 다른 축으로 설명
- 카탈로그·asset·분리 승인·drift/fail-closed 계약시험 6 PASS 반영
- 실제 Edge 카탈로그 확인은 Root 최종 수치 전달 전 `PLANNED`로 유지
- WorldCover 2021 타연도 정답 금지와 weak agreement·independent accuracy 분리를 유지

## 2026-11-25 — 운영 경로 2~8 기관 작업·원천·모델·저장소 반영

- `V42_OPERATION_PATH_2_TO_8.md` 신규 작성
- 1번 결과 카탈로그의 `c4a3954` GitHub push와 실제 Edge seed 2·지도 2·보고서 3 확인 반영
- 기관 작업 provider의 멱등 제출·재개·취소·model pin·asset SHA·결과 등록 합성 8 PASS 반영
- 실제 개발 조회 HTTP 200과 본문 `JOB_PROVIDER_CONFIG_NOT_SET`, worker exit 1을 실운영 성공과 분리
- RTRW·CCKP·Lake·KLHK·private index·Sentinel 로컬 6종 pin을 `VERIFIED_REAL`로 제한하고 모두 publication/public search `BLOCKED` 유지
- 실제 scene 격리 후보 1,779→1,751행, 적격 1,382행, 원본 scene 충돌 1→0을 반영하되 학습 허용 false 유지
- 합성 ONNX 11→12→11 활성화·rollback 및 과학 승인 철회 뒤 실행 차단을 `TESTED_SYNTHETIC`으로 기록
- React 기관 운영 화면은 API 8014·Vite 5175 세 경로 HTTP 200, 합성 계약과 138-module build까지 `VERIFIED_REAL`; 실제 Edge 클릭은 `PLANNED`로 유지
- 별도 SeaweedFS 4.04에 실제 CCKP 검산 JSON 3,295B 저장, SHA·재시도, 익명 403, 45초 presigned GET·만료 403을 `VERIFIED_REAL`로 반영
- PostgreSQL fixture TCP timeout과 Kubernetes context 부재로 RLS·PostGIS·pgvector·복구·클러스터 인수는 `BLOCKED` 유지
- WorldCover 2021 타연도 정답 금지, weak agreement와 independent accuracy 분리를 유지

## 2026-11-25 — LCLUC 공식 분류사전·변화 계산·기준 분류기 이해자료

- Swipe Auto Play 5초 단일 재생(50→85→15→50), 남은 초·완료, Pause/Resume, 수동 분할·자료·모드 변경 시 취소를 반텐 Edge에서 `VERIFIED_REAL`로 확인. 최종 로그의 내부 시계 5,098ms·5→1초·완료·50% 복귀, Time-Series 유지와 frontend build PASS 반영. 승인 상태 변경 없음
- 반텐 Esri v003 code 9 `Snow/ice` 2020~2025 집계 `0.04/0/0.03/0.05/0/0.12ha`와 10m 픽셀 `4/0/3/5/0/12`를 실제 원본 분류값으로 기록하되 현지 적설 검증은 `BLOCKED`로 분리
- 소면적 차트를 0ha 시작·축 최대 최소 1ha·ha 눈금·점별 소수 tooltip과 Snow/ice 증거 문구로 교정. Edge에서 실제 6점·0~1ha 축·정확한 label·Total Valid Area 대조를 `VERIFIED_REAL`, 전부 0인 합성 6점의 수평 기준선을 `TESTED_SYNTHETIC`으로 확인
- 두 시점 비교를 좌우 지도 두 장에서 단일 지도 50:50 구분선으로 교정: 왼쪽 기준·오른쪽 비교 동일 위치 mask, 네이티브 드래그/키보드, 자료 없을 때 geoBoundaries 2017 ADM1와 두 연도 미등록 배지. 이전 1440/390px·68% 시험은 역사로 보존. 새 Edge 5175/build에서 실제 반텐 경계·2020/2025 미등록·동자바 전환과 격리 합성 50% mask·390px 드래그·2023 이미지/수치 없음·JS 오류 0을 확인해 `TESTED_SYNTHETIC`으로 기록.
- 실제 Indonesia Explorer 등록·검증: Esri v003 반텐 2020·2025 결과 `f9f3…605a`의 공통 712.30ha·변화 32.65ha·4.58%, S2·Landsat 8 두 시점 6밴드+QA native 창, 팔루 NASA JPEG 2장. Edge 5175에서 Esri 50:50·7분류 mask·시점 선택/재생·비중표, 실자료 전환·ZIP, 2023 차단·JS 오류 0 확인. 회귀 37 PASS·imagery 무결성 1 PASS·build 통과. 반텐 고정 표본+별도 팔루 범위이며 NLCD 범위 밖·KLHK/독립 정확도/전국 동적 통계 미산출.
- 사용자 지시에 따라 독립 Explorer 화면을 제거하고 공통 `ModelWorkspace`로 복원: Edge 5175에서 기존 `.mw` 필터·7탭·4 KPI·50:50/Time-Series·범례 checkbox·실제 Sentinel/Landsat/Palu preview와 ZIP·비중표/행렬/내보내기·2023 미등록·JS 오류 0을 확인해 `VERIFIED_REAL`. 합성 지표·WorldCover 대체 없음.
- One Map / BIG 2026-11-24 snapshot의 6개 주·129개 군시 overlay를 `VERIFIED_REAL`로 반영. 양쪽 지도에서 여섯 주 이름과 Tangerang·Kota Tangerang을 직접 확인했으나 클릭은 미검증이며 사업통계 승인은 `BLOCKED`.
- Esri v003 원본 9색을 8개 면적 클래스와 Clouds 품질로 구분. code 10 Clouds 68/0은 유효 면적에서 제외하고 NoData 0은 투명. 독립 정확도 미측정 유지.
- 반텐 전역 확대 근거 반영: 6주 대상 Esri 42 COG HEAD 합계 3,537,430,071B, 실제 반텐 2020 원본 139,102,310B와 SHA·격자, 10m pixel-center 935,602.88ha·유효 99.9648%·구름 329.35ha를 `VERIFIED_REAL`로 기록. 사업통계 승인은 대기.
- `banten-province-edge.log` PASS로 기존 Province AOI의 실제 Esri 2020 전역 표시·2025 준비 중·Study AOI 복귀·JS 오류 0을 `VERIFIED_REAL`로 반영.
- Esri 2021~2025·나머지 주는 진행 중, Landsat 24후보·168파일 중 첫 B2 83,167,494B만 확인, Sentinel-2 32후보는 공유 원장 잠금 때문에 `BLOCKED`. 반텐 전역 전환행렬·독립 정확도 미산출 유지.
- 반텐 실제 Esri 2020·2021 전역쌍과 POST 재계산을 `VERIFIED_REAL`로 반영: 경계 935,602.88ha, 공통 유효 935,223.27ha, 변화 51,913.67ha, 5.55094%, 전환행렬·결과 ID `18c0…7beb`·HTML·CSV 생성. `banten-full-pair-edge.log` PASS로 브라우저 비교 확인.
- Sentinel-2 전역 계획 224 asset HEAD 합계 21,626,452,905B와 2023 guarded 7-asset 창 SCL clear 99.9878%를 실제 증거로 기록. 이전 lock은 보존하고 현재 전역 수집은 예산 제한으로 `BLOCKED`.
- Esri 2022~2025·나머지 주 및 Landsat 24후보·168파일 전체는 미완료. 전역 6년·센서 QA E2E와 Docker/Kubernetes 이식은 `PLANNED`, 모델 독립 정확도는 `BLOCKED` 유지.
- 후속 완료 증거로 반텐 Esri v003 2020~2025 원천 6/6년을 `VERIFIED_REAL`로 갱신. One Map 경계 935,602.88ha와 기존 React Workspace의 swipe·6년 면적 시계열·전환행렬·KPI·실시간 원천 inventory를 Edge에서 확인.
- 대표 2020→2025 전역쌍은 공통 유효 935,231.32ha·변화 78,998.91ha, 1km 변화 셀 8,663개·상위 hotspot 20개이며, 결정론적 HTML·JSON·CSV evidence ID `0c62e0f1c6d06ca4aba4726b6e9f4ab7c0ba01a6c44b08fb976d0ca1d7e2dab6`를 `banten-feature-2025-edge.log`에서 확인.
- Esri 6개 연도의 동일 연도 reference coverage와 전환행렬은 독립 정확도가 아님을 명시. Sentinel-2 32 scene·224 native asset과 Landsat 24 scene·168 native asset은 계속 취득 중이며, `21,626,452,905B`는 Sentinel-2 승인 상한이지 소비량·완료량이 아님.
- Docker/Kubernetes 이식은 반텐 전역 광학자료 완전성·QA 인수 뒤의 `PLANNED` 단계로 유지하고, 독립 현장정답 평가·실제 학습·배포는 `BLOCKED` 유지.
- Sentinel-2 2020 연차를 `VERIFIED_REAL`로 추가: 장면 영수증 5개·provider-native asset 35개, 30m 반텐 경계 935,601.66ha, 6밴드 물리 피복 100%, SCL clear 87.53%. Edge에서 2020 단일뷰·2025 준비 중·inventory QA를 확인.
- Sentinel-2 clear와 동년 Esri 유효 주제값의 공간 교집합 818,838.00ha는 비교 가능 지원 영역이며 semantic agreement·independent accuracy가 아님을 명시. 2020 연차 단계와 별개로 6개 연도 Sentinel/Landsat 광학 Gate는 `WAITING` 유지.
- 2026-11-26 KST 영수증 전량 대조로 반텐 Sentinel-2 원본 `224/224 asset`·`32/32 scene`·`21,626,452,905B` 수집 완료와 2020~2025 RGB 6개 HTTP 200 PNG를 `VERIFIED_REAL`로 갱신. 원 수집 PID 종료.
- 진행 JSON 기록 오류는 원본 영수증 전량 완료와 분리해 `BLOCKED` 운영 정합성 항목으로 유지. Sentinel 경계 QA는 2020~2024 기존 검산, 2025 포함 최종 검산 PID 116788 실행 관측으로 아직 최종 인수 전.
- Landsat은 112/168 asset·16/24 scene을 실제 확인. 2024 첫 응답 중단 후 기존 방식 재시도 경로를 추가해 PID 158732로 재개한 2026-11-26 KST 스냅샷을 기록하고, 광학 인수와 Docker/Kubernetes 이식 Gate는 유보 유지.
- 2026-11-26 10:47 KST 최종 상태로 Landsat `168/168 asset`·`24/24 scene`·`11,700,363,947B` 수집 완료를 `VERIFIED_REAL`로 갱신. 연차 감시 로그가 2024·2025 QA와 RGB를 자동 갱신하고 계획 6개년 달성 후 종료.
- Sentinel-2 `224/224 asset`·`32/32 scene`·`21,626,452,905B`를 유지하고 두 센서 모두 2020~2025 전역 QA·RGB 6개년 완료로 갱신.
- 최종 인수는 `COVERAGE_GAPS`: Landsat 연차별 10.35~274.32ha, Sentinel-2 2021~2025 0.09~2.88ha 경계 미피복. 원본·QA 완료와 광학 인수 승인을 분리하고 Docker/Kubernetes 이식은 유보 유지.
- 계획 밖 신규 연도 탐색 및 MLOps 실행·RF/Tiny U-Net 비교·독립 검증 trigger가 아직 미연결임을 `PLANNED`로 기록. 수집 완료를 학습·독립 정확도·배포 완료로 확대하지 않음.
- Docker Compose 5180 이식을 `VERIFIED_REAL`로 반영: health·공통 결과·jobs·기존 GeoAI health·반텐 원본 count와 Sentinel/Landsat 실제 광학 레이어 12개 HTTP 확인. 기존 5175는 별도 실행 유지.
- 로컬 Kubernetes 5181 이식을 `VERIFIED_REAL`로 반영: 같은 이미지, 읽기전용 evidence/raw, 3 PVC, 경계·2020~2025 결과·광학 12개 레이어와 해시 확인. 기관 운영 클러스터 인수와 구분.
- Compose 개발 PostGIS·pgvector schema와 S3 projection, CCKP 보고서 3,295B signed SHA readback·무인증 403을 실제 검증. 과거 PostgreSQL timeout·Kubernetes context 부재 기록은 역사로 보존하되 현재 개발 이식 상태로 갱신.
- 실제 개발 PostgreSQL 작업 큐에서 모의 기관 응답 10 PASS를 확인하고, 패키지 Worker `--once`는 승인 작업 0건을 `jobs_checked=0`으로 안전 종료. 실제 기관 endpoint 작업 10건으로 해석하지 않음.
- 기술 이식 완료와 기관 운영·반텐 과학 인수를 분리. `COVERAGE_GAPS`, 독립 정확도, 실제 provider·IAM/SSO·백업/복구·RPO/RTO는 계속 `BLOCKED`.
- `kube-browser.log` PASS로 로컬 Kubernetes 기존 LCLUC UI의 Sentinel-2·Landsat 두 센서 swipe를 실제 Edge에서 확인.
- `compose-portable-browser.log` PASS로 Docker Compose 실제 Edge 전체 흐름을 확인: 광학 레이어, 10m 명시 재계산, 연차 면적·추세, 변화지도·20 hotspot, 수집·KPI, 비교, 기존 ID `0c62…dab6`의 HTML·CSV 보고서.
- Windows 감사 변화 `78,998.91ha`와 Linux 컨테이너 재계산 `78,998.94ha`를 같은 원본의 환경별 결과로 별도 표시. 전환행렬 차이와 동일 Rasterio/GDAL 내 PROJ wheel 차이를 기록하고 bit-for-bit·소수 둘째 자리 완전 동등성을 주장하지 않음.
- `V42_LCLUC_TAXONOMY_CHANGE_CLASSIFIERS.md` 신규 작성
- SIGAP·SK 398/2024 대조 공식 23코드를 `VERIFIED_REAL`로 반영하되 토지피복 22개와 구름 품질코드 1개를 분리
- 분류사전 metadata 444,011B와 SHA를 기록하고 연차 native code domain·license·기관 승인은 `BLOCKED` 유지
- 잠정 KLHK→legacy-9 대응표를 11개 mapping·12개 exclusion의 `IMPLEMENTED_UNVERIFIED` 보수표로 기록
- 동일 taxonomy·grid·equal-area CRS의 합성 변화 엔진 4 PASS를 `TESTED_SYNTHETIC`으로 반영
- 합성 변화면적·fixture 25%를 실제 지역 변화량으로 해석하지 않도록 제한
- 최종 회귀 37 PASS와 격리 합성 fixture 4ha 공통 유효·1ha 변화·25%, 2023 없음·동일 SHA/연도 거부·단일 결과 ID/CSV 연결을 반영
- 실제 Edge에서 격리 합성 A–D 이미지·스와이프, CSV 다운로드, 2023 미등록 차단, 동일 결과 ID의 공통 카탈로그 조회를 확인해 UI 흐름은 `VERIFIED_REAL`, 분석 수치는 `TESTED_SYNTHETIC`으로 분리
- 실행 중인 5175 화면에는 운영 자료 0건과 구름 품질코드 표시를 확인했으며 이를 실제 LCLUC 운영 사례나 독립 정확도로 확대하지 않음
- CPU Random Forest·Tiny U-Net 분류기 전용 12 PASS(361.37초)를 `TESTED_SYNTHETIC`으로 반영
- 두 모델 모두 동일 합성 holdout 유효 252픽셀에서 mIoU 0.50 이상이며, 모델 SHA 저장·복원 시험을 완료했지만 독립 정확도는 산출하지 않았음을 명시
- 실제 학습·동년 독립 라벨·과학 승인·모델 release·배포를 `BLOCKED`로 유지
- Edge A~D는 실제 브라우저 수치 전달 전 `PLANNED` 유지
- WorldCover 2021 타연도 정답 금지와 weak agreement·independent accuracy 분리를 INDEX·용어집·발표 대본·FAQ에 반영
