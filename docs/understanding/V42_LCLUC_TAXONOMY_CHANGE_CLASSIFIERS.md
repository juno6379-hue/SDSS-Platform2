# LCLUC 분류사전·변화 계산·기준 분류기 이해자료

- updated_at: 2026-11-26 KST
- overall_status: `TESTED_SYNTHETIC`
- `VERIFIED_REAL`: KLHK 공식 분류사전 23코드(토지피복 22 + 구름 품질코드 1)와 출처 원문 고정
- `VERIFIED_REAL`: 반텐 Esri v003 2020~2025 전역 6개 연도, 기존 React Workspace의 전역 비교·시계열·1km 변화지도·결정론적 보고서
- `VERIFIED_REAL`: 반텐 Snow/ice 실제 6점의 0~1ha 축·정확한 소수 label·총면적 대조를 Edge에서 확인
- `TESTED_SYNTHETIC`: 동일 격자 변화 계산 4 PASS, Random Forest·Tiny U-Net CPU 비교 및 모델 파일 해시 검증·복원 12 PASS
- `IMPLEMENTED_UNVERIFIED`: 보수적 KLHK→legacy-9 crosswalk
- `BLOCKED`: KLHK 연차 원본 코드 도메인·사용권·운영 승인, 실제 학습, 독립 정확도, 모델 게시·배포
- `TESTED_SYNTHETIC`: Edge A~D에서 스와이프, 전이 CSV 다운로드, 미등록 2023년 차단, 같은 결과 ID의 카탈로그 조회를 확인했다.

## 1. 쉬운 설명

이번 LCLUC 작업은 세 층으로 나뉜다.

1. **무엇을 분류할지 고정했다.** SIGAP 자료사전과 SK 398/2024 부속서를 근거로 KLHK 코드 23개를 고정했다. 이 중 22개는 토지피복 주제 클래스이고 `2500 Awan`은 구름 품질코드다. 배열의 구조적 NoData `65535`와도 다르다.
2. **두 시점 지도가 있으면 어떻게 변화를 계산할지 구현했다.** 같은 분류사전·격자·면적투영을 가진 두 GeoTIFF에서 공통 유효 픽셀만 비교해 전이행렬, 변화면적, 산림손실, 시가지 증가, hotspot, 구역별 통계를 만든다.
3. **두 기준 분류기를 비교하는 코드를 만들었다.** Sentinel-2 6밴드와 SCL을 입력으로 CPU Random Forest와 Tiny U-Net을 학습·평가하는 경로가 있다. 그러나 실제 승인 자료로 학습하거나 독립 정확도를 검증한 것은 아니다.

가장 중요한 구분은 다음과 같다.

- 공식 **분류사전**이 확인됐다고 해서 2024·2025 연차 레이어의 원본 코드와 사용권까지 승인된 것은 아니다.
- crosswalk가 있다고 해서 KLHK 클래스를 legacy-9로 손실 없이 바꿀 수 있는 것은 아니다.
- 합성 변화량과 합성 모델 지표는 계산 계약 증거이지 인도네시아의 실제 변화면적이나 배포 정확도가 아니다.
- WorldCover 2021은 2021년 약한 참조일 뿐 타연도 정답이 아니다. 참조 일치도는 독립 정확도와 다르다.

## 2. 이론적 배경

### 2.1 분류사전, 연차 자산, 운영 승인은 서로 다르다

분류사전은 코드와 뜻을 정의한다. 연차 자산은 특정 연도의 픽셀에 그 코드를 기록한 자료다. 운영 승인은 자산의 출처·원본 SHA·사용권·기관 판단을 확인해 실제 분석에 사용할 수 있게 하는 결정이다.

따라서 `klhk-23` 사전이 `VERIFIED_REAL`이어도 연차 레이어가 자동으로 승인되지는 않는다. 현재 2024·2025 metadata renderer에는 25항목이 보이지만, 원본 속성의 native 23-code domain과 재사용 권리는 확인되지 않았다. 이 부분은 `BLOCKED`다.

### 2.2 주제 클래스와 품질 코드를 섞지 않는다

`2500 Awan`은 공식 코드 집합에는 남기되 모델 출력과 토지피복 통계에서는 제외한다. NoData `65535`는 파일 구조상 값이 없는 셀이다. 구름과 NoData를 합치면 품질 문제와 자료 부재를 구분할 수 없으므로 별도 마스크로 관리한다.

### 2.3 crosswalk는 의미를 줄이는 변환이다

KLHK 23코드를 legacy-9에 대응시키면 세부 산림·농업·습지 의미가 사라질 수 있다. 그래서 잠정 crosswalk는 명확한 11개 원본 코드만 변환하고, 모호하거나 혼합된 12개 코드는 명시적으로 제외한다. 기본 호출은 잠정표 사용을 차단하며 `allow_provisional=True`를 명시해야 한다. 이는 승인 우회가 아니라 시험용 예외다.

### 2.4 변화량은 같은 비교 지지집합에서 계산한다

두 시점의 총 픽셀 수가 같아도 구름·NoData·외부 mask의 위치가 다를 수 있다. 변화율의 분모는 양쪽 모두 유효한 **공통 유효 픽셀 교집합**이어야 한다. 면적은 위경도 각도를 제곱미터로 오해하지 않도록 metre 단위 equal-area CRS에서 계산한다.

전이행렬의 행은 이전 연도, 열은 이후 연도다. 대각선은 유지, 비대각선은 변화다. hotspot은 연결된 변화 픽셀 집합을 최소 면적으로 거른 결과이며, 행정구역 통계는 입력 zone과 같은 공통 유효 지지집합을 사용한다.

### 2.5 모델 선택과 최종 평가는 분리한다

검증셋 mIoU로 후보 모델을 고르고 시험셋은 최종 평가에만 쓴다. 같은 scene, 원본 SHA, 공간 겹침 또는 라벨 원천이 train·validation·test를 넘나들면 누출이다. 동년이며 학습 라벨 생성과 독립된 지상·전문가 정답이 있어야 `independent_accuracy`를 말할 수 있다.

모델이 내는 최대확률과 정규화 entropy는 불확실성 보조값이지만 보정되지 않았다. 따라서 0.9 확률을 실제 90% 정확도로 해석하면 안 된다.

## 3. 코드와 데이터 동작

### 3.1 공식 분류사전 registry

- 코드: `services/lcluc/taxonomy.py`
- 사전: `services/lcluc/taxonomies/klhk-23.json`
- taxonomy ID: `klhk-23`
- version: `sk-398-2024-c1018ar-v1`
- 코드: 23개 = 토지피복 22개 + 품질코드 `2500`
- 구조적 NoData: `65535`
- 출처: SIGAP 자료사전 575, SK 398/2024 C1018AR
- 취득 metadata: 444,011B
- SHA-256: `abd45de2d17d9630e5b8cb72bcb1f2bc95566928c3a2ab203f149384559f81d5`
- license: `NOT_VERIFIED`
- approval: `BLOCKED`

loader는 ID·version·코드 중복·NoData 충돌·source/evidence를 검증하고 정규화된 taxonomy SHA를 만든다. 연차 metadata 검사는 코드명과 renderer를 비교하지만 수집·분석 승인은 별도 상태로 남긴다.

### 3.2 보수적 crosswalk

- 파일: `services/lcluc/taxonomies/klhk-23-to-legacy-9.json`
- ID: `klhk-23-to-legacy-9`
- version: `provisional-conservative-v1`
- 11개 원본 코드는 legacy-9 대상으로 대응
- 12개 원본 코드는 구름·혼합·모호성을 이유로 제외
- source taxonomy와 target taxonomy의 SHA를 모두 결속
- evidence: `IMPLEMENTED_UNVERIFIED`
- approval: `BLOCKED`

운영 승인 요구 시 차단하고, 잠정표 사용도 명시적 opt-in 없이는 차단한다. 변환 결과에는 매핑·제외 면적을 함께 남겨 의미 손실을 숨기지 않는다.

### 3.3 변화 엔진

- 코드: `services/lcluc/change.py`
- 입력: 서로 다른 연도의 single-band categorical GeoTIFF 2개, taxonomy, 선택적 품질 mask·CRS84 zone
- 필수 조건: content SHA, 관측일, source kind, taxonomy ID/SHA, NoData, 정수형, metre equal-area CRS, north-up, 동일 grid
- 제외: NoData, taxonomy QA 코드, 내부 mask, 외부 mask
- 출력: JSON report, hotspot GeoJSON, transition GeoTIFF
- 안전장치: 기존 출력 덮어쓰기 금지, 같은 raster 재사용 금지, 연도 역전·공통 유효 픽셀 0 차단

합성 2020→2025 사례는 12픽셀 중 공통 유효 7픽셀, 7ha를 비교해 변화 4ha, 산림손실 2ha, 시가지 증가 2ha, hotspot 1개·2ha를 재현한다. 이 숫자는 합성 시험값이다.

### 3.4 기준 분류기 비교

- 코드: `services/lcluc/classifiers.py`
- 입력 밴드: B02, B03, B04, B08, B11, B12
- clear SCL: 4, 5, 6
- 출력 도메인: KLHK 주제 클래스 22개; 구름 `2500`과 NoData `65535` 제외
- 후보: CPU Random Forest, Tiny U-Net
- 선택: 같은 train 정규화와 validation mIoU, 동률이면 모델 이름 순서
- 시험: 같은 test split에서 혼동행렬, 클래스별 F1·IoU, 평균 IoU
- artifact: pickle이 아닌 NPZ 배열과 JSON metadata, SHA와 배열 shape 검증

실제 non-fixture 실행은 승인된 taxonomy, DataReadiness, TrainingApproval, manifest SHA, materialized dataset fingerprint, split count를 요구한다. WorldCover v200/2021 참조는 2021년에만 허용한다.

분류기 전용 12건이 361.37초에 통과했다. 두 모델 모두 동일 합성 holdout 유효 252픽셀에서 mIoU 0.50 이상이며 SHA 고정 artifact의 저장·복원을 확인했다. 이는 `TESTED_SYNTHETIC` 회귀 증거이며 실제 승인 데이터 학습·독립 정확도·release는 모두 0이다.

### 3.5 workspace/API 합성 경로

합성 fixture는 명시적 `allow_fixture=True`일 때만 등록된다. exact 2020→2025 pair가 없으면 `EXACT_LCLUC_YEAR_PAIR_NOT_AVAILABLE`로 차단한다. 격리 GeoTIFF의 4ha 공통 유효면적, 1ha 변화, 25% 변화율은 API 계약 시험값이지 실제 지역 변화량이 아니다. 2023 pair 부재, 같은 SHA/연도 재사용 거부, 단일 결과 ID와 CSV 연결도 확인했다.

Root가 분류사전·변화·기존 등록시험을 포함한 Python 통합 묶음 37 PASS를 확인했다. 통합 묶음에 변화 엔진 4건이 포함된다. 별도 Edge 시험에서 A~D, CSV, 카탈로그와 연도 차단을 확인했다. 당시 운영 LCLUC 사례는 0건이었고, 이후 아래 Explorer 실제 사례 1건을 등록했다.

### 3.6 연도 비교 UI

현재 `frontend/src/VerifiedLclucWorkspace.tsx`의 `YearMapComparison`은 지도 두 장을 나란히 놓지 않는다. 한 지도 위에 기준·비교 래스터를 같은 위치로 겹치고, 기본 50:50 구분선의 왼쪽에는 기준 연도, 오른쪽에는 비교 연도만 각자 mask해 표시한다. 투명 range input이 지도 전체를 덮어 네이티브 포인터 드래그와 키보드 조작을 제공한다. 공통 유효 면적, 변화량, 변화율은 비교 제목 바로 아래·지도 위에 표시한다.

선택한 두 연도의 preview가 없으면 같은 지도 자리에 기존 geoBoundaries 2017 ADM1 주 경계를 보여 주고, 왼쪽·오른쪽에 각각 선택 연도와 `토지피복 미등록` 배지를 표시한다. 경계 출처는 화면에 geoBoundaries / OpenStreetMap·Wambacher / 2017 ADM1 / ODbL 1.0으로 명시한다. 다른 연도 영상을 대신 보여 주거나 변화 수치를 만들지 않는다.

이전 좌우 두 지도·68% 스와이프·1440/390px Edge 시험은 당시 구현의 역사적 증거로 보존한다. 단일 지도 교정도 Edge 5175와 build에서 확인했다. 당시 실제 실행 화면은 반텐 공개 경계 한 장·중앙 구분선·2020/2025 미등록 배지와 동자바 지역 전환을 보였고, 격리 합성에서는 기본 50% 양면 masking·동일 viewport, 390px 포인터 드래그, 2023 선택 시 연차 분류 이미지·수치 없음, JavaScript 오류 0을 확인했다. 이 기록은 `TESTED_SYNTHETIC`이며 이후 실제 Explorer 사례를 별도로 등록했다.

### 3.7 실제 Indonesia Explorer 고정 표본

반텐 고정 표본에 Esri / Impact Observatory Land Cover v003 2020·2025 쌍을 실제 API 사례로 등록했다. 결과 ID는 `f9f3824d49505e52a35989389140e2973b43efd852320145e44945484f4d605a`다. EPSG:6933 공통 유효 71,230픽셀, 712.30ha 중 변화 32.65ha, 변화율 4.58%를 계산했다. 이는 Esri 두 연차지도 사이의 고정 표본 변화이며 반텐주 전체 변화율, KLHK 변화, 독립 정확도가 아니다.

같은 고정 위치에는 Sentinel-2 L2A와 Landsat 8 Collection 2 Level-2를 각각 두 시점·6밴드+QA native 창으로 보존했다. 팔루 2018 사건 전후 NASA Earth Observatory JPEG 2장은 시각 판독 전용이며 피해 면적 계산 입력이 아니다. Annual NLCD는 미국 범위 제품이므로 인도네시아 입력에서 제외한다. 고정 COG Range와 NASA JPEG의 성공 수신 본문 합은 43,393,967B다. 센서 관측을 Esri 연차 합성의 생성 장면으로 간주하지 않으며 KLHK 연차 등록과 독립 정확도는 미산출이다.

독립 Explorer 화면의 최종 Edge 5175에서는 실제 Esri 단일뷰 50:50, 7개 분류 mask, 시점 선택·재생과 비중표를 확인했다. Sentinel-2·Landsat 8·팔루 실제 자료 전환과 각 ZIP 다운로드·구조, 2023 미등록 차단, JavaScript 오류 0도 확인했다. Python 회귀 37 PASS, imagery 무결성 1 PASS와 build가 통과했다. 이 기록은 당시 독립 화면의 역사적 `VERIFIED_REAL` 증거로 보존한다.

현재 인터페이스는 새 독립 화면을 제거하고 App의 공통 `ModelWorkspace` 진입으로 복원했다. 기존 `.mw` 필터, 7개 분석 탭, 지도 조작부와 4개 지표 카드는 유지하며, `ModelAnalysisWorkspace` 안에서 검증된 Esri·Landsat 8·Sentinel-2·팔루 원천과 결과 파일을 연결한다. 등록 결과가 없으면 합성 지표나 WorldCover 대체값을 만들지 않고 미등록 상태를 표시한다.

실제 Edge 5175에서 기존 7탭·4 KPI, 50:50 slider·Time-Series, 기존 범례 checkbox, Sentinel-2·Landsat 8·팔루 실제 preview와 ZIP, 시계열 비중표·전환행렬·내보내기, 2023 미등록과 JavaScript 오류 0을 확인했다. 따라서 복원된 현재 Workspace도 `VERIFIED_REAL`이다. 이 상태는 화면·실자료 연결 검증이며 반텐 고정 표본 밖의 과학 결과나 독립 정확도를 뜻하지 않는다.

### 3.8 One Map 6주·129개 군시 행정경계

`services/api/lcluc_boundaries.py`는 2026-11-24에 고정한 One Map / BIG snapshot을 read-only로 제공한다. 대상은 반텐 8개, 서자바 27개, 동자바 40개, 고론탈로 6개, 남술라웨시 25개, 남동술라웨시 23개로 합계 129개 군·시와 6개 주다. `GET /api/lcluc/boundaries`는 통합 지도용 GeoJSON·행정명·취득시각·근거 SHA를, 지역별 endpoint는 고정 원본 경계를 반환한다. 대상 밖 지역은 404, 증거 검증 실패는 409로 차단한다.

`frontend/src/adminBoundaryMap.ts`와 기존 LCLUC·WebGIS 지도는 양쪽 비교 지도에 같은 행정경계를 겹친다. 실제 Edge 로그에서 양쪽 지도 각각 Banten, Jawa Barat, Jawa Timur, Gorontalo, Sulawesi Selatan, Sulawesi Tenggara의 여섯 주 명칭을 확인했고, 확대 상태에서 Tangerang과 Kota Tangerang 군·시 명칭도 양쪽에 표시됨을 직접 확인했다. 클릭 선택은 이 로그로 검증하지 않았으므로 완료로 주장하지 않는다. 경계는 지도 참조용이며 사업통계 승인 상태는 `BLOCKED`다.

Esri v003 연차층은 원본 9색 팔레트를 사용한다. 8개 코드는 면적 통계 대상이고 code 10 `Clouds`는 품질 항목이다. 등록 입력에서 Clouds 픽셀은 두 시점 68/0으로 확인됐으며 유효 면적에서 제외한다. NoData 0은 투명하게 표시한다. Sentinel-2 6밴드+SCL과 Landsat 8 6밴드+QA_PIXEL은 화면 영상 비교용이고, 팔루는 발행 JPEG라 래스터 피해 통계 입력이 아니다.

### 3.9 반텐 전역 자료 확대

6개 주 경계와 Esri v003 tile을 대조한 결과 중복을 제거한 7개 tile×2020~2025년 6개 연도, 42개 원격 COG가 대상이다. 공급자 HEAD 42건의 합계 `3,537,430,071B`를 실제 확인했다. 이는 원격 객체 길이 inventory이며 전체 다운로드 완료량이 아니다.

반텐 2020 tile `48M` 원본 `139,102,310B`와 2021 원본 `137,540,759B`를 비롯해 2020~2025 6개 연도 원천을 모두 실제 검증했다. 반텐 경계의 EPSG:6933 10m pixel-center 면적은 `935,602.88ha`다. 2020 파일 자료 존재율은 100%, 유효 토지피복 `99.9648%`, 구름 `329.35ha`다. 경계 승인 상태는 `PROJECT_STATISTICS_PENDING`이므로 이 수치를 승인된 사업통계 면적으로 표현하지 않는다.

실제 POST 재계산의 첫 전역쌍인 2020→2021은 공통 유효 `935,223.27ha`, 변화 `51,913.67ha`, 변화율 `5.55094%`와 전환행렬을 만들고 결과 ID `18c0…7beb`, HTML·CSV를 생성했다. `artifacts/lcluc/banten-full-pair-edge.log`가 PASS한 이 기록은 역사적 실증으로 보존한다.

현재 대표 비교인 2020→2025의 Windows 감사값은 공통 유효 `935,231.32ha`, 변화 `78,998.91ha`다. 기존 React Workspace의 실제 Edge 검증에서 반텐 전역 경계, 50:50 swipe, 6개 연도 면적 시계열, 전환행렬·KPI·실시간 원천 inventory를 확인했다. 10m 변화 자료를 1km 격자로 집계한 변화지도에는 변화 셀 `8,663개`와 상위 hotspot `20개`가 표시됐다. 결정론적 HTML·JSON·CSV는 evidence ID `0c62e0f1c6d06ca4aba4726b6e9f4ab7c0ba01a6c44b08fb976d0ca1d7e2dab6`로 연결됐고, `artifacts/lcluc/banten-feature-2025-edge.log`가 이를 확인했다.

Compose Linux의 명시 재계산 변화면적은 `78,998.94ha`였다. `compose-portable-browser.log`는 기존 감사값과 Linux 재계산값을 동시에 표시하고, 광학 레이어·10m 재계산·연차 추세·변화지도·20 hotspot·수집·KPI·비교·동일 ID HTML/CSV 흐름을 실제 Edge에서 PASS했다. 동일 원본과 Rasterio/GDAL을 썼지만 PROJ wheel 차이와 전환행렬 차이가 감지됐으므로 두 값을 하나로 덮어쓰지 않는다. 의미상 가까운 결과와 bit-for-bit·소수 둘째 자리 수치 동등성을 구분한다. `kube-browser.log`는 Kubernetes 기존 UI에서 두 센서 swipe를 실제 Edge로 PASS했다.

다만 Esri 연차 지도의 **동일 연도 참조 피복 확인**은 원천의 공간·연도 coverage를 뜻한다. 모델·참조 생성과 독립된 현장 또는 전문가 정답으로 계산한 `independent_accuracy`가 아니며, 6/6 연도가 있다는 사실도 정확도 승인을 뜻하지 않는다.

2026-11-26 KST 영수증 전량 대조에서 Sentinel-2 provider-native 원본은 `224/224 asset`, `32/32 scene`, `21,626,452,905B`로 수집 완료를 확인했다. 2020~2025 RGB 6개도 모두 HTTP 200 PNG로 확인했다. 원 수집 PID는 종료됐고 진행 JSON의 기록 오류는 실제 asset·scene 영수증 전량과 분리해 다룬다. 즉 진행 JSON 오류만으로 완료 원본을 누락으로 되돌리지 않지만, 오류 원인과 상태 파일 정합성은 별도 운영 결함으로 남긴다.

2026-11-26 10:47 KST 최종 영수증 대조에서 Landsat도 `168/168 asset`, `24/24 scene`, `11,700,363,947B`로 수집 완료됐다. 연차 감시 로그가 2024·2025 QA와 RGB를 자동 갱신했고, 계획한 2020~2025 6개 연도를 달성한 뒤 수집 프로세스가 종료됐다. Sentinel-2는 앞서 확인한 `224/224 asset`, `32/32 scene`, `21,626,452,905B` 상태를 유지한다. 두 센서 모두 6개 연도 전역 QA와 연차 RGB가 확보됐으므로 원본 수집·연차 materialization·QA 단계는 `VERIFIED_REAL`이다.

다만 최종 과학 인수 상태는 `COVERAGE_GAPS`다. Landsat 연차별 경계 미피복은 `10.35~274.32ha`, Sentinel-2의 2021~2025 경계 미피복은 `0.09~2.88ha`다. 수집 개수와 QA 연도 수가 계획을 충족해도 경계 전체가 완전히 덮였다는 뜻은 아니다. 기술 이식은 이 차단을 숨기지 않은 채 별도로 완료했다. Docker 5180과 로컬 Kubernetes 5181에서 같은 이미지가 읽기전용 원본, 반텐 경계·2020~2025 결과, 실제 광학 12개 레이어를 제공하는 것을 확인했다. 이는 `VERIFIED_REAL` 이식 증거이지 광학 과학 인수나 독립 정확도 승인이 아니다. 계획 밖 신규 연도 탐색, MLOps 실행, RF·Tiny U-Net 분류 비교, 독립 검증을 자동으로 시작하는 trigger도 아직 연결되지 않았다.

그중 Sentinel-2 2020년은 별도 연차 단계 증거가 확보됐다. 실제 장면 영수증 5개와 provider-native asset 35개를 검증했고, 30m 반텐 경계 `935,601.66ha`에서 6개 밴드 물리 피복률은 `100%`, SCL 맑은 픽셀 비율은 `87.53%`였다. 동년 Esri 유효 픽셀과 동시에 비교 가능한 공간 교집합은 `818,838.00ha`다. 이 값은 두 자료의 **공간 지원 영역**이며 클래스 의미 일치도나 독립 정확도가 아니다. `banten-sentinel-2020-edge.log`에서 기존 UI의 2020 전역 Sentinel 단일뷰와 inventory QA를 확인했다. 이후 6개 연도 수집·QA까지 완료됐지만, 위 경계 미피복 때문에 전체 광학 인수는 별도 `COVERAGE_GAPS` 상태다.

### 3.10 Snow/ice 소면적 차트 해석

반텐 Esri v003 원본의 code 9 `Snow/ice` 집계는 2020~2025 순서로 `0.04, 0, 0.03, 0.05, 0, 0.12ha`이며, 10m 픽셀 수로는 `4, 0, 3, 5, 0, 12개`다. 이는 원본 분류 코드 집계가 실제로 존재한다는 뜻이지, 현지 적설·결빙을 별도 관측으로 검증했다는 뜻이 아니다.

기존 차트는 정수 천 단위 `0k` 표기와 자료 최솟값~최댓값 자동 확대 때문에 이 작은 값을 0처럼 보이게 하거나 변화를 과장할 수 있었다. `LclucRealChart`는 y축을 0ha에서 시작하고 축 최대를 최소 1ha로 두며, ha 눈금과 각 점의 정확한 소수 면적 tooltip을 사용하도록 수정됐다. Snow/ice 선택 시 “Esri 원본 분류 면적이며 실제 적설·결빙은 확인되지 않았다”는 근거 문구도 표시한다. `banten-snow-chart-edge.log`와 PNG에서 실제 6점·0~1ha 축·정확한 label·Total Valid Area 대조를 확인했다. 별도 전부 0인 6점 fixture가 수평 0 기준선에 놓이는 것도 확인했다.

### 3.11 Swipe Auto Play 조작

Swipe 비교 지도에는 한 번만 재생하는 5초 자동 이동이 구현됐다. 시작 위치 50%에서 85%로 이동한 뒤 15%를 거쳐 50%로 돌아오며, 화면은 남은 초와 `재생 완료`를 표시한다. 실행 중에는 Pause, 일시 정지 뒤에는 Resume이 가능하다. 사용자가 분할선을 직접 끌거나 비율 버튼·slider를 조작하고, 자료·레이어 또는 비교 모드를 바꾸면 기존 자동 재생을 취소한다. 따라서 자동 동작이 수동 선택을 덮어쓰지 않는다.

이 변경은 지도 비교 조작 편의 기능이며 원본·모델·기관 승인이나 분석 수치를 바꾸지 않는다. 최종 `swipe-autoplay-final-edge.log`에서 반텐 실브라우저 내부 시계 `5,098ms`, 5→1초와 `재생 완료`, 50% 복귀·고정, Pause/Resume, 수동 조작·모드 전환 취소를 확인했다. 기존 Time-Series 재생도 유지됐고 frontend build가 통과해 UI 범위는 `VERIFIED_REAL`이다.

## 4. 시험과 증거

| 항목 | 상태 | 증거와 해석 |
|---|---|---|
| KLHK 공식 23코드 분류사전 | `VERIFIED_REAL` | SIGAP·SK 398/2024 대조, metadata 444,011B와 SHA 고정. 22 thematic + cloud 1 |
| 연차 KLHK 자산 운영 사용 | `BLOCKED` | native source code domain, 원본 바이트, license, 기관 승인 미확보 |
| 보수적 crosswalk | `IMPLEMENTED_UNVERIFIED` | 11 mapping·12 exclusion, SHA 결속과 opt-in 차단 구현. 기관 승인 없음 |
| 변화 엔진 | `TESTED_SYNTHETIC` | Root 확인 4 PASS. 합성 2020→2025 계산과 fail-closed 검증 |
| workspace/API LCLUC | `TESTED_SYNTHETIC` | 분류사전·변화·기존 등록 포함 Python 통합 37 PASS. 4ha/1ha/25% fixture, 2023 없음·동일 SHA/연도 거부·단일 결과 ID/CSV 확인 |
| RF·Tiny U-Net 비교 | `TESTED_SYNTHETIC` | 분류기 시험 12건 완료. 같은 합성 시험 분할의 유효 252픽셀에서 두 모델 mIoU ≥ 0.50과 SHA 고정 모델 저장·복원 확인 |
| 실제 classifier accuracy | `BLOCKED` | 승인 연차자료·동년 독립 라벨·22개 클래스 표본·과학 승인 없음 |
| 실제 Explorer API 사례 | `VERIFIED_REAL` | Esri 반텐 고정 표본 2020→2025 결과 1건 등록. 합성 fixture와 별도 |
| 브라우저 Edge A~D | `TESTED_SYNTHETIC` | 지도 이미지·스와이프, 4ha/1ha/25%, 전이 CSV, 미등록 2023년, 동일 ID의 카탈로그 연결 |
| 이전 좌우 `YearMapComparison` UI | `TESTED_SYNTHETIC` | 역사적 시험: Edge 5175의 1440/390px 정렬·68% 스와이프·상단 4ha/1ha/25%·2023 이미지/수치 없음·JS 오류 0 |
| 현재 단일 지도 50:50 UI | `TESTED_SYNTHETIC` | Edge 5175/build 통과. 실제 화면은 반텐 공개 경계·2020/2025 미등록·동자바 전환, 격리 합성은 50% 양면 mask·동일 viewport·390px 드래그·2023 이미지/수치 없음·JS 오류 0 |
| Esri 반텐 2020→2025 실제 사례 | `VERIFIED_REAL` | 결과 `f9f3…605a`, 공통 712.30ha·변화 32.65ha·4.58%. 고정 표본의 Esri 연차 간 변화이며 반텐 전체·독립 정확도 아님 |
| Explorer 실제 센서 원천 | `VERIFIED_REAL` | S2·Landsat 8 두 시점씩 6밴드+QA native 창, 팔루 NASA JPEG 2장; 성공 본문 43,393,967B. NLCD는 범위 밖 |
| 독립 Explorer 역사 UI | `VERIFIED_REAL` | 당시 Edge 5175: Esri 50:50·7분류 mask·시점 선택/재생·비중표, S2/Landsat/팔루 전환·ZIP, 2023 차단, JS 오류 0. 이후 독립 화면 제거 |
| 현재 공통 ModelWorkspace 통합 | `VERIFIED_REAL` | Edge 5175에서 기존 7탭·4 KPI·50:50/Time-Series·범례 checkbox·실자료 preview/ZIP·비중표/행렬/내보내기·2023 미등록·JS 오류 0 확인 |
| One Map 6주·129군시 overlay | `VERIFIED_REAL` | API 원본 6주·129 군시. 양쪽 지도에서 6주 명칭, Tangerang·Kota Tangerang 직접 확인; 클릭은 미검증 |
| 행정경계 사업통계 사용 | `BLOCKED` | 현재 경계는 지도 참조용이며 사업통계 승인 대기 |
| Esri v003 9색 표시 | `VERIFIED_REAL` | 8개 면적 클래스+Clouds 품질. code 10은 68/0, 유효 면적 제외; NoData 0 투명 |
| Snow/ice code 9 연차 집계 | `VERIFIED_REAL` | 2020~2025 `0.04/0/0.03/0.05/0/0.12ha` = 10m 픽셀 `4/0/3/5/0/12`; 원본 분류 집계이며 현지 적설 검증 아님 |
| Snow/ice 소면적 차트 교정 | `VERIFIED_REAL` | Edge에서 실제 6점, 0~1ha 축, 정확한 소수 label, Total Valid Area 대조 확인 |
| Snow/ice 전부 0 차트 | `TESTED_SYNTHETIC` | 합성 6개 0값이 수평 0 기준선에 놓임을 Edge에서 확인 |
| 반텐 실제 적설·결빙 | `BLOCKED` | 현지 관측·독립 검증 없음 |
| Swipe Auto Play UI | `VERIFIED_REAL` | 반텐 Edge 5,098ms, 5→1초·완료, 50% 복귀, Pause/Resume, 수동·모드 취소와 Time-Series 유지, build PASS |
| 6주 Esri HEAD inventory | `VERIFIED_REAL` | 중복 제거 7 tile×6년=42 COG, 원격 Content-Length 합계 3,537,430,071B. 다운로드 완료량 아님 |
| 반텐 Esri 2020·2021 전역 | `VERIFIED_REAL` | 원본 139,102,310B·137,540,759B, SHA/격자 검증. 10m pixel-center 935,602.88ha; 사업통계 승인 대기 |
| 반텐 2020→2021 재계산 | `VERIFIED_REAL` | 실제 POST: 공통 935,223.27ha·변화 51,913.67ha·5.55094%, 전환행렬·결과 ID·HTML·CSV 생성 |
| Banten Province AOI 전역쌍 | `VERIFIED_REAL` | `banten-full-pair-edge.log` PASS. 두 실제 층 비교·보고서 확인; 2020 표시/2025 준비 중/Study 복귀·JS0 역사도 보존 |
| 반텐 Esri 2020~2025 전역 | `VERIFIED_REAL` | 실제 원천 6/6년, One Map 경계 935,602.88ha, 6개 연도 면적 시계열과 기존 React UI Edge 확인 |
| 반텐 Esri 2020→2025 대표쌍 | `VERIFIED_REAL` | 공통 935,231.32ha·변화 78,998.91ha, 전환행렬·KPI·1km 변화 셀 8,663개·hotspot 20개 |
| Linux 컨테이너 재계산 | `VERIFIED_REAL` | 같은 원본 변화 78,998.94ha. Windows 78,998.91ha와 별도 provenance로 표시; PROJ wheel·전환행렬 차이 보존 |
| 반텐 보고서 식별자 | `VERIFIED_REAL` | HTML·JSON·CSV evidence ID `0c62…dab6` 유지; Windows 감사값과 Linux 재계산값은 ID 안에서 별도 provenance로 표시 |
| Esri 나머지 5개 주 | `IMPLEMENTED_UNVERIFIED` | 반텐 전역 완료와 별개이며 안정된 전역 완료 증거 없음 |
| 반텐 Landsat 원본 수집 | `VERIFIED_REAL` | 2026-11-26 10:47 KST: 168/168 asset·24/24 scene·11,700,363,947B, 계획 6개년 달성 후 수집 종료 |
| 반텐 Landsat 연차 QA·RGB | `VERIFIED_REAL` | 연차 감시 로그가 2024·2025를 자동 갱신해 2020~2025 6개년 QA·RGB 확보 |
| 반텐 Sentinel-2 원본 수집 | `VERIFIED_REAL` | 영수증 전량 대조: 224/224 asset·32/32 scene·21,626,452,905B. 원 수집 PID 종료 |
| 반텐 Sentinel-2 연차 RGB | `VERIFIED_REAL` | 2020~2025 6개 PNG 모두 HTTP 200 확인 |
| 반텐 Sentinel-2 경계 QA | `VERIFIED_REAL` | 2020~2025 6개년 전역 QA 완료 |
| Sentinel 진행 JSON 정합성 | `BLOCKED` | 진행 JSON 기록 오류를 영수증 전량 대조와 분리. 원본 완료는 확인했으나 상태 파일 오류 원인·정합성 보완 필요 |
| 반텐 Sentinel-2 2020 연차 | `VERIFIED_REAL` | 장면 영수증 5개·native asset 35개, 30m 경계 935,601.66ha, 6밴드 100%, SCL clear 87.53%, Edge 2020 단일뷰·inventory QA 확인 |
| Sentinel-2 2020·Esri 동년 공간 지원 | `VERIFIED_REAL` | 동시 유효 교집합 818,838.00ha. 비교 가능 영역이며 semantic agreement·independent accuracy가 아님 |
| 반텐 Sentinel-2 2023 제한 창 | `VERIFIED_REAL` | guarded 추가 창 7 asset 수신, SCL clear 99.9878%. 전역 수집 증거 아님 |
| 반텐 광학 인수 Gate | `BLOCKED` | `COVERAGE_GAPS`: Landsat 연차 미피복 10.35~274.32ha, S2 2021~2025 미피복 0.09~2.88ha |
| 피복 공백 보완·과학 인수 | `BLOCKED` | 두 센서 6개년 QA는 완료했지만 `COVERAGE_GAPS` 해소 전 |
| Docker 5180·Kubernetes 5181 이식 | `VERIFIED_REAL` | Compose Edge 전체 재분석·보고서 PASS, K8s Edge 두 센서 swipe PASS. 과학 인수와 별도 |
| 신규 연도·MLOps·분류·독립검증 trigger | `PLANNED` | 계획 밖 신규 연도 탐색과 후속 학습·분류기 비교·독립 평가 자동 연결 없음 |
| 반텐 모델 독립 정확도 | `BLOCKED` | Esri 동일 연도 reference coverage·전환행렬은 확보했지만 독립 현장 라벨 평가는 없음 |
| 전국 카메라 기반 동적 통계 | `PLANNED` | 반텐 전역 고정 AOI와 별도 팔루 자료까지 확인. 지도 이동·확대에 따른 전국 임의 영역 재집계는 없음 |
| KLHK Explorer 등록·독립 정확도 | `BLOCKED` | KLHK 연차 쌍 미등록, 독립 지상정답 미산출 |
| 실제 학습·모델 게시·배포 | `BLOCKED` | 실행·승인·release 0 |

시험 결과를 읽을 때 다음을 지킨다.

- 4 PASS는 변화 계산 계약의 합성시험이며 실제 KLHK 변화 검증이 아니다.
- fixture 25%는 API 샘플이며 어느 주의 실제 변화율도 아니다.
- Python 통합 37 PASS는 분류사전·변화·기존 등록을 포함한다. Edge 시나리오는 실제 브라우저에서 합성 자료로 별도 확인했다.
- 합성 mIoU는 pipeline 회귀 증거일 뿐 independent accuracy가 아니다.
- WorldCover/KLHK 참조 일치도는 weak agreement이며 독립 정확도가 아니다.
- Esri 6개 연도 reference coverage와 전환행렬도 independent accuracy가 아니다.

## 5. 발표 스크립트

### 1분

“LCLUC에서는 실제 Esri v003 반텐 전역 2020~2025 여섯 연도와 Sentinel-2·Landsat 여섯 연도 광학자료를 확보했습니다. Sentinel-2는 224개 asset·32개 scene·21,626,452,905바이트, Landsat은 168개 asset·24개 scene·11,700,363,947바이트이며 두 센서의 6개년 QA와 RGB도 완료했습니다. 그러나 최종 인수는 COVERAGE_GAPS입니다. Landsat은 연차별 10.35~274.32헥타르, Sentinel-2는 2021~2025에 0.09~2.88헥타르가 경계 안에서 비어 있습니다. 또한 자동 MLOps·분류기 비교·독립 검증은 연결되지 않았습니다. 따라서 수집 완료를 독립 정확도나 배포 준비로 확대하지 않습니다.”

### 5분

1. 분류사전은 23코드로 실제 고정했지만 연차 자산 승인과는 분리했다.
2. 구름 `2500`은 품질코드, `65535`는 구조적 NoData, 나머지 22개만 주제 클래스다.
3. 잠정 crosswalk는 의미 손실을 숨기지 않고 11개 mapping·12개 exclusion을 기록하며 기본 차단한다.
4. 변화 엔진은 동일 taxonomy·grid·equal-area CRS·서로 다른 연도·content SHA를 요구한다.
5. 양 시점 모두 유효한 교집합만 분모로 써 전이행렬·변화면적·hotspot·zone 통계를 계산한다.
6. 실제 Esri 반텐 전역은 2020~2025 6/6년과 935,602.88ha 경계를 확인했다.
7. 대표 2020→2025는 공통 935,231.32ha·변화 78,998.91ha이며 1km 변화 셀 8,663개와 hotspot 20개다.
8. 기존 React Workspace의 swipe·6년 시계열·전환행렬·KPI·원천 inventory와 결정론적 HTML·JSON·CSV를 Edge에서 확인했다.
9. 동일 연도 참조 coverage와 전환행렬은 독립 정확도가 아니다. 실제 학습·release·배포도 차단 상태다.
10. S2 224/224·32/32와 Landsat 168/168·24/24, 양 센서 6개년 QA·RGB를 Docker 5180·Kubernetes 5181에서 재현했지만 `COVERAGE_GAPS` 과학 인수는 별도 차단이다.

## 6. Q&A

**Q. KLHK 공식 23클래스가 확보됐습니까?**

분류사전의 23코드와 명칭은 `VERIFIED_REAL`이다. 다만 22개가 토지피복이고 한 개 `2500 Awan`은 구름 품질코드다. 연차 원본의 native 코드·사용권·운영 승인은 `BLOCKED`다.

**Q. renderer 25항목이면 23클래스가 틀린 것입니까?**

그렇게 단정하지 않는다. renderer 심볼 수와 원본 coded-value domain은 다른 층이다. 원본 필드의 23코드와 기관 사용권을 별도로 확인해야 한다.

**Q. crosswalk로 모두 legacy-9로 변환할 수 있습니까?**

아니다. 잠정표는 명확한 11개만 대응시키고 12개는 제외한다. 승인되지 않은 보수적 제안이며 운영 기본값은 차단이다.

**Q. 합성 변화 4ha가 실제 지역 변화입니까?**

아니다. 1ha 픽셀 12개로 만든 계산 시험값이다. 실제 지역명·면적·변화율로 인용하면 안 된다.

**Q. 분류기 비교가 구현됐으니 모델이 준비됐습니까?**

아니다. 전용 12 PASS에서 RF와 Tiny U-Net 모두 동일 합성 holdout 252픽셀의 mIoU 0.50 이상과 SHA 저장·복원을 확인했지만, 실제 승인 자료·동년 독립 라벨·전 클래스 표본·과학·배포 승인이 없다. 독립 정확도는 미산출이다.

**Q. 확률과 entropy가 있으면 불확실성이 검증된 것입니까?**

아니다. 현재 출력은 보정되지 않았다. calibration과 독립 검증 없이는 확률을 실제 정확도로 해석할 수 없다.

**Q. WorldCover 2021로 2024·2025 정확도를 검증할 수 있습니까?**

없다. WorldCover 2021은 2021년 약한 참조일 뿐 타연도 독립 정답이 아니다. weak agreement와 independent accuracy를 별도 지표로 유지한다.

**Q. Python 통합 37 PASS면 운영 LCLUC 사례도 있습니까?**

37 PASS는 분류사전·변화·기존 등록을 포함한 격리 Python 통합시험 결과다. 그 뒤 실제 Esri 반텐 고정 표본 사례 1건을 별도 등록했지만, 회귀 PASS 자체가 운영 분석 완료를 뜻하지 않는다.

**Q. 브라우저 Edge A~D 시나리오가 완료됐습니까?**

`TESTED_SYNTHETIC`이다. Edge에서 연차 지도·스와이프, 전이·집중지역, 다운로드, 공통 결과 카탈로그 및 연도 차단을 확인했다.

**Q. 새 연도 비교 UI도 브라우저에서 다시 확인됐습니까?**

예. Edge 5175에서 실제 반텐 공개 경계·중앙 구분선·2020/2025 미등록 배지와 동자바 전환을 확인했다. 격리 합성에서는 기본 50% 좌우 mask·동일 viewport, 390px 포인터 드래그, 2023 선택 시 이미지·수치 없음과 JavaScript 오류 0을 확인했고 build도 통과했다. 비교 자료는 합성이므로 상태는 `TESTED_SYNTHETIC`이다.

**Q. 실제 Indonesia Explorer도 브라우저에서 검증됐습니까?**

예. Edge 5175에서 실제 Esri 2020·2025 단일뷰 50:50, 7개 분류 mask, 시점 선택·재생, 비중표와 Sentinel-2·Landsat 8·팔루 전환 및 ZIP 구조를 확인했다. 2023 미등록 차단과 JavaScript 오류 0, imagery 무결성 1 PASS와 build도 확인했다. 다만 범위는 반텐 고정 표본과 별도 팔루 영상이며 전국 동적 통계나 독립 정확도 검증은 아니다.

**Q. Explorer의 반텐 4.58%는 실제 반텐주 전체 변화율입니까?**

아니다. Esri v003 2020·2025 고정 표본의 공통 유효 712.30ha 중 32.65ha가 달라진 비율이다. 반텐주 전체·KLHK 변화·독립 정확도는 미산출이다.

**Q. 복원된 기존 LCLUC Workspace도 실제 검증됐습니까?**

예. Edge 5175에서 기존 7개 탭·4개 KPI, 50:50·Time-Series, 범례 checkbox, Sentinel-2·Landsat 8·팔루 preview와 ZIP, 비중표·전환행렬·내보내기, 2023 미등록과 JavaScript 오류 0을 확인했다. 이는 반텐 고정 표본 중심의 UI·실자료 연결 증거다.

**Q. 6개 주 경계와 군·시 이름이 실제 지도에 보입니까?**

예. API는 6개 주와 129개 군·시를 반환한다. Edge에서 양쪽 지도 각각 여섯 주 이름과 Tangerang·Kota Tangerang 이름을 직접 확인했다. 다만 클릭 선택은 해당 로그로 검증하지 않았고, 경계의 사업통계 사용 승인은 대기다.

**Q. Esri 9색에서 Clouds와 NoData도 토지피복 면적입니까?**

아니다. 8개만 면적 클래스다. code 10 `Clouds`는 품질 항목으로 두 시점 68/0픽셀이며 유효 면적에서 제외한다. NoData 0은 투명하다.

**Q. 반텐 Esri 2020~2025가 6/6이면 독립 정확도도 검증됐습니까?**

아니다. 6/6은 각 연도의 실제 원천과 반텐 경계 coverage를 확인했다는 뜻이다. 같은 공급자 연차도 사이 변화와 동일 연도 참조 확인은 모델·참조 생성과 분리된 현장 정답 평가가 아니므로 `independent_accuracy`는 여전히 `BLOCKED`다.

**Q. 1km 변화 셀 8,663개는 10m 원본 픽셀 수 또는 정확도입니까?**

아니다. 10m 변화 결과를 화면과 우선순위 검토용 1km equal-area grid로 집계한 셀 수다. 상위 20개 hotspot도 검토 순위이며 독립 정확도나 전체 변화 픽셀 수가 아니다.

**Q. Sentinel-2와 Landsat 전역 취득도 끝났습니까?**

원본 수집과 6개년 QA·RGB는 끝났다. Sentinel-2는 224/224 asset·32/32 scene·`21,626,452,905B`, Landsat은 168/168 asset·24/24 scene·`11,700,363,947B`다. Docker 5180과 로컬 Kubernetes 5181에서도 12개 광학 레이어를 확인했다. 그러나 Landsat은 연차별 10.35~274.32ha, Sentinel-2는 2021~2025에 0.09~2.88ha의 경계 미피복이 있어 과학 인수 상태는 `COVERAGE_GAPS`다. 기술 이식 완료가 이 차단을 해제하지 않는다.

**Q. 수집이 끝나면 새 연도 탐색과 모델 학습이 자동으로 시작됩니까?**

아니다. 계획 밖 신규 연도 탐색, MLOps 실행, RF·Tiny U-Net 비교, 독립 정확도 평가를 시작하는 trigger는 아직 연결되지 않았다. 수집·QA 완료는 학습 승인이나 독립 검증 완료가 아니다.

**Q. Windows 78,998.91ha와 Linux 78,998.94ha는 모순입니까?**

같은 원본의 환경별 재계산 결과이며 둘 다 provenance와 함께 보존한다. 동일 Rasterio/GDAL이어도 PROJ wheel 차이가 있고 전환행렬 차이가 감지됐다. 0.03ha 차이를 숨기거나 한 값을 다른 값으로 덮어쓰지 않으며, 과학적 수치 동등성과 bit-for-bit 재현성을 구분한다.

**Q. Sentinel-2 2020의 818,838ha는 Esri와 일치한 면적입니까?**

아니다. Sentinel-2 SCL이 맑고 Esri 주제값도 유효해서 두 자료를 함께 비교할 수 있는 공간 교집합이다. 클래스가 같다는 semantic agreement나 독립 정확도를 계산한 값이 아니다. 2020 연차 단계는 실제 검증됐지만 전체 6개 연도 광학 Gate는 아직 대기다.
