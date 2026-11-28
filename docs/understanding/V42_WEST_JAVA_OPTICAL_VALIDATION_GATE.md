# 서자바 광학자료·모델 검증 Gate 이해자료

- updated_at: 2026-11-28 KST
- Landsat 재수신 근거: [검증 보고서](../../evidence/westjava/native-collection-runtime/2025-landsat-redownload-verification.json) · [SHA-256 전수 검산](../../evidence/westjava/native-collection-runtime/2025-landsat-redownload-sha-audit.json)
- overall_status: `VERIFIED_REAL` 실자료 시험 범위와 `BLOCKED` 독립 정확도를 함께 관리
- 근거: `docs/lcluc/WEST_JAVA_OPTICAL_PILOT.md`, `docs/lcluc/WEST_JAVA_VALIDATION.md`, `docs/lcluc/WEST_JAVA_2020_TREE_RETRIAL.md`, `docs/lcluc/WEST_JAVA_CONTINUOUS_INTAKE.md`, `docs/architecture/REGIONAL_MLOPS_LIFECYCLE.md`, `docs/data/WESTJAVA_DATA_INVENTORY.md`, `evidence/westjava/native-collection-runtime/2020-tree-augmentation-comparison.json`

## 1. 쉬운 설명

서자바 Gate는 “자료가 실제로 있고 모델이 계산을 끝냈는가”와 “그 결과가 독립적으로 정확한가”를 분리한다. 2020 Sentinel-2는 10m 창 4개에서 실제 밴드와 SCL을 읽고 분류 시험을 수행했다. Landsat은 30m 겹침창에서 장면 2개를 합성하고 분류 미리보기를 만들었다. 이 부분은 `VERIFIED_REAL`이다. 지속입고 Worker는 새 원격 수집을 시작하지 않고 별도로 봉인된 영수증이 들어왔을 때만 보관 원본의 해시·범위·연도를 확인해 같은 처리를 재실행한다.

모델 수치는 모두 Esri v003과 비교한 **약한 참조 일치도**다. E0은 반텐 시험의 약 147m 표시 격자에서 70.39%, E1·E2·E3은 같은 서자바 745,043 시험 픽셀에서 각각 35.63%, 18.37%, 18.93%였다. E4는 별도 2023 창에서 63.10%였다. 시험 위치·연도·해상도가 다르므로 E0 또는 E4를 E1~E3과 단순 순위로 비교하지 않는다.

제품 B는 2021년 서부 창에서 Esri v003과 WorldCover v200을 같은 해 6개 대분류로 맞춘 지도 일치도 83.45%다. WorldCover는 2021년 제품 비교에만 사용한다. 제품 C인 승인 독립 참조 기반 정확도는 아직 측정하지 못해 `BLOCKED`다.

최초 Landsat 두 장면 결과는 실자료 분류 미리보기로만 사용한다. 두 장면이 기존 반텐 학습 자료와 겹치고 당시 `QA_RADSAT`가 없어 정량 성능 수치 게시를 차단했다. 현재는 별도 3개 장면과 보완된 QA로 새 2020 공간 RF 시험을 추가했다.

승인된 native 수집의 2020년분은 두 센서 모두 완료 영수증과 자동 입고 RF까지 이어졌다. Sentinel-2 11장면은 8,401,060,705B, Landsat 4장면은 2,027,444,484B다. 새 RF 결과는 각각 Esri 약한 참조 일치도 44.65%와 21.45%였고 Landsat 별도 validation은 0%였다. 이 값들은 창 단위 약한 참조 비교이며 독립 정확도는 미측정이다. 실제 운영 활성 모델은 0개이고, 원본 자산 120개와 산출물 52개의 SHA-256 재감사가 완료됐다.

기존 2020 RF에는 Esri 코드 2인 수목 학습 표본이 없었다. 센서별로 기존 평가 구역과 공간적으로 분리된 두 학습 창에서 수목 3,500픽셀을 추가하고, 원래 validation/test 모자이크·입력 SHA·유효 픽셀 마스크는 그대로 동결해 전후를 비교했다. 시험 구역의 약한 참조 일치도와 수목 재현율은 모두 상승했지만 독립 판독이나 사람 승인을 거친 정확도는 아니며 모델을 게시하거나 활성화하지 않았다.

## 2. 이론적 배경

### 2.1 해상도와 시험 단위

- Sentinel-2 시험은 10m 격자이며 B02·B03·B04·B08은 native 10m, B11·B12·SCL은 native 20m다.
- Landsat 시험은 30m 격자다.
- E0은 약 147m 표시 격자다.

픽셀 수와 공간 해상도가 다른 시험의 백분율은 같은 모집단의 직접 비교값이 아니다. 모델 비교는 같은 시험 모자이크와 같은 유효 마스크를 공유한 E1·E2·E3 내부에서 가장 안전하다.

### 2.2 약한 참조 일치도와 독립 정확도

Esri v003 또는 WorldCover와의 일치도는 두 지도의 분류가 얼마나 같은지를 나타낸다. 두 제품 자체의 오차가 있고 학습·평가 독립성이 보장되지 않으므로 독립 정확도로 부르지 않는다. 독립 정확도에는 동년 승인 참조, 독립 표본 설계, 판독·검토 기록과 과학 승인이 필요하다.

### 2.3 공간·시간 도메인 이동

반텐에서 학습한 E1이 서자바에서 35.63%였고 서자바의 다른 창에서는 E2·E3이 74%대였다. 이는 지역 안에서도 토지피복 구성, 대기, 계절, 장면과 참조 품질이 달라질 수 있음을 보여 준다. E4는 2023의 별도 창이고 2020 분할과 최소 21.06km 떨어졌지만 평가 영역도 바뀌었으므로 순수 시간 일반화 시험으로 해석하지 않는다.

### 2.4 QA와 누출 방지

Landsat `QA_PIXEL`은 구름·그림자·눈 등을 제외한다. 최초 두 장면 pilot 당시에는 `QA_RADSAT`가 없어 포화 여부를 검사하지 못했고 두 장면이 학습 자료와도 겹쳐 정량 평가를 차단했다. 이후 보유 16장면의 `QA_RADSAT`를 같은 grid로 보완하고 별도 3개 장면을 분리한 공간 RF 시험을 수행했다. 이전 pilot의 차단 기록은 당시 자료 품질 상태로 보존한다.

## 3. 코드·데이터 동작

### 3.1 실제 광학 창

| 자료 | 창 | AOI 픽셀 | 물리 피복 | 맑은 픽셀 | 상태 |
|---|---|---:|---:|---:|---|
| Sentinel-2 2020 | `g00` | 1,057,840 | 98.90% | 89.47% | `VERIFIED_REAL` |
| Sentinel-2 2020 | `g01` | 1,057,224 | 99.10% | 89.91% | `VERIFIED_REAL` |
| Sentinel-2 2020 | `boundary-00` | 753,105 | 99.14% | 98.93% | `VERIFIED_REAL` |
| Sentinel-2 2020 | `boundary-01` | 803,667 | 99.38% | 98.95% | `VERIFIED_REAL` |
| Landsat 2020 | overlap 2장면 | 109,820 | 100% | 100% | `VERIFIED_REAL` 처리, 정량 평가는 `BLOCKED` |

처리 순서는 경계와 원본 SHA 고정, 밴드·QA 정합, 유효 마스크 생성, 모델 추론, 약한 참조 비교, 증거 기록이다. 연속 밴드는 bilinear, SCL 같은 범주형 자료는 nearest 방식으로 정합한다.

### 3.2 E0~E4 시험

| 시험 | 학습·적용 개요 | 시험 픽셀 | 약한 참조 일치도 | 해석 상태 |
|---|---|---:|---:|---|
| E0 | 기존 반텐 RF, 약 147m 표시 격자 | 76,230 | 70.39% | `VERIFIED_REAL`, 별도 해상도 |
| E1 | 반텐 고정 RF → 서자바 10m | 745,043 | 35.63% | `VERIFIED_REAL` |
| E2 | 서자바 신규 RF → 동일 시험창 | 745,043 | 18.37% | `VERIFIED_REAL` |
| E3 | 반텐+서자바 통합 RF → 동일 시험창 | 745,043 | 18.93% | `VERIFIED_REAL` |
| E4 | 고정 E2 RF → 별도 2023 창 | 65,263 | 63.10% | `VERIFIED_REAL`, 별도 공간·연도 |

E1·E2·E3은 동일 시험 모자이크 SHA와 745,043픽셀을 사용한다. E2의 학습 픽셀은 19,043개, E3은 19,679개다. E2·E3의 별도 `g01` 검증은 각각 74.59%와 75.06%로 공간 변동성이 컸다. 역사적 1,779행 감사에서 일부 같은 장면 관계가 발견됐으므로, 신규 창 분할의 비중복 확인을 전체 역사 데이터의 완전한 독립성으로 확대하지 않는다.

### 3.3 제품 비교와 면적

- 제품 B `VERIFIED_REAL`: 2021 서부 창 10,572.72ha에서 Esri v003↔WorldCover v200 6대분류 지도 일치도 83.4537375%.
- 2020 서자바 native 면적 `VERIFIED_REAL`: Esri 유효 3,677,893.60ha, MapBiomas 발행 합계 3,704,306.95ha.
- 두 면적은 경계와 분류체계가 달라 차이나 일치도로 계산하지 않는다.
- 제품 C `BLOCKED`: 승인된 독립 참조와 최종 판독 라벨이 없다.

### 3.4 배포·복구 상태

- 실제 Staging PostgreSQL·S3에 E2 `2020-e2-680f9b62155d`와 E3 `2020-e3-fa7fa4a98e8f`를 등록했다. 두 후보 모두 A축 `VALIDATED`, revision 4, `active=false`이며 독립 검증과 과학 승인은 미등록이다. 등록·ID 재조회 범위는 `VERIFIED_REAL`이다.
- 격리 Compose와 kind에서 두 합성 ONNX 버전을 각각 활성화하고 `Serving`을 확인한 뒤 롤백했다. 재시작 이력과 PostgreSQL·SeaweedFS 단절·복구까지 확인한 범위는 `TESTED_SYNTHETIC`이다.
- Compose와 kind Staging UI에서 서자바 필터, E2·E3 버전, 타임라인과 세 검증 유형을 확인했다. kind Pod 재생성 이후 양 환경의 실제 원장과 비교 결과가 일치했다. 격리 Compose 화면에서는 합성 이력과 배포 근거를 확인했다.
- 배포 성공은 모델 과학 승인이나 독립 정확도를 의미하지 않는다.

### 3.5 봉인 영수증 지속입고

기존 30m 연차 Worker는 그대로 유지한다. 지역 광학 처리는 `SDSS_REGIONAL_INBOX`를 명시하거나 `--regional-only`로 실행한 경우에만 별도 봉인 영수증을 읽는다. 영수증 파일명은 본문 SHA-256과 같아야 하며 주·연도·창·센서·원본 pin이 일치하지 않으면 차단한다. 결과는 run ID 디렉터리에 원본 영수증, 창별 입력·mosaic, 후보·추론, SHA가 포함된 status를 보존한다.

- Windows 2020 run `9fc6d30…` `VERIFIED_REAL`: Sentinel-2 네 창과 Landsat 두 장면 한 창을 보관 원본에서 처리했다. Sentinel 후보 학습 19,043픽셀과 같은 745,043 시험 픽셀의 E1 35.63%→E2 18.37% 비교를 기록했다. `improved=false`이므로 모델 개선 증거로 사용하지 않는다.
- Landsat `VERIFIED_REAL` 처리: `QA_PIXEL` 유효 109,820픽셀에서 동결 RF 추론만 수행했다. `QA_RADSAT` 부재와 학습 장면 두 개 재사용 때문에 정량 일반화 평가는 차단한다.
- Docker `--network none` 2023 run `ab5b318…` `VERIFIED_REAL`: 원격 요청 없이 65,263픽셀, 2020 분할과 최소 21.06km 거리의 E4를 재실행했고 Esri 약한 참조 일치도 63.10%를 기록했다.
- 승인 전 읽기 전용 재점검 `VERIFIED_REAL`: 2026-11-27 20:48 KST 활성 수집기 0, HTTP 429 회로 비활성, 공유 원장 잔액 1,505,501,578B를 확인했다. 미정산 키 4개는 모두 `IDEMPOTENCY_KEY_ALREADY_PENDING`으로 차단됐고 원장 SHA `8b82affc…067d5`는 유지됐다. 이후 별도 native 승인을 받아 22:29 KST 새 collector를 시작했다.
- Worker·API 계약 `TESTED_SYNTHETIC`: 영수증 pin, 재실행, 차단, mock 429를 포함한 24건이 통과했다. mock 429는 실제 HTTP 429 관측이 아니다.
- Compose 5280 실제 앱에서 모델 & MLOps→서자바 실자료 비교표→AI 검증의 2020·2023 상세를 펼쳐 35.63%→18.37%, 63.10%, Landsat 유효 109,820픽셀과 평가 차단을 확인했다. 이 UI 조회 범위는 `VERIFIED_REAL`이다.
- kind Job `sdss-lake-staging/sdss-westjava-intake-2023`은 `Completed`다. Docker와 결과·자산 10개의 SHA·ID가 모두 같고 `finished_at`만 달라 컨테이너 재현 범위는 `VERIFIED_REAL`이다.

### 3.6 QA 보완·전역 공백 계획·자동 입고

- `QA_RADSAT` 보완 `VERIFIED_REAL`: 보유 Landsat 8/9 장면 16개의 정확한 STAC 자산을 고정하고 3,577,164B를 실제 내려받았다. 16개 모두 해당 장면의 기존 `QA_PIXEL`과 CRS·grid·shape·30m 해상도가 일치한다. 기존 원본 영수증과 QA 보완 영수증은 분리 보존한다.
- Landsat 2020 자동 입고 `VERIFIED_REAL`: 승인 계획 SHA와 완료 파일의 장면 ID·byte·ETag를 대조한 뒤 3개 독립 장면을 합성했다. 학습 1,356픽셀, 시험 654픽셀, 최소 분할 이격 30.07km이며 Esri v003 약한 참조 일치도 72.78%, Macro F1 28.08%다. 독립 정확도는 아니다.
- Sentinel-2 2023 자동 발견 `VERIFIED_REAL`: 과거 완료 영수증의 계획 SHA·제품·7개 자산·교정 XML을 재검산해 10m 모자이크와 고정 E2 RF 평가를 자동 실행했다. 결과는 기존과 같은 65,263픽셀·Esri 약한 참조 63.10%이며 새 원격 전송은 0이다.
- 공백 계획 `VERIFIED_REAL`: One Map/BIG 경계와 250m 표본 격자에서 2020~2025의 물리·품질 공백을 센서별로 계산하고 공급자 후보 JSON을 고정했다. 공백 값은 전역 완료 증거가 아니라 추가 자료 필요량의 계획 근거다.
- 실행 범위: 지역 Worker는 기존 연차 Worker와 다른 경로에서 격리 1회 실행했다. 상시 배포와 2020~2025 미수집 자료 보완은 배치별 승인·byte 상한 전까지 `BLOCKED`다.
- 회귀 `TESTED_SYNTHETIC`: 177 PASS·1 SKIP. 실제 5280 브라우저에서는 새 Landsat 2020 자동 입고 결과와 Sentinel-2 2023 결과를 확인했다.

### 3.7 승인된 2020~2025 native 수집 실행

사용자가 Sentinel-2 59,900,000,000B와 Landsat 8,930,000,000B의 2020~2025 수집 한도를 센서별로 승인했다. 계획과 승인 SHA를 고정하고 전체 장면 HEAD 합계가 한도를 넘으면 다음 배치로 진행하지 않는 구조다.

- 기존 미정산 4건 `VERIFIED_REAL`: laneB 두 건은 `io_started`가 없고 pilot 두 건은 `io_started=true`와 부분 TIFF가 있다. 완결 계측 영수증이 없어 예약 203,423,744B를 그대로 유지했고 공유 원장 SHA `8b82affc…067d5`도 변하지 않았다.
- 최초 병렬 HEAD에서 실제 HTTP 429를 관측했으나 영상 본문 요청은 0이었다. 공급자 서명 cache 공유와 HEAD 시작 간격을 조정해 재개했다. 이 429는 앞선 mock 시험과 구분한다.
- 2020 HEAD `VERIFIED_REAL`: Sentinel-2 11장면 8,401,060,705B, Landsat 4장면 2,027,444,484B를 공급자 HEAD로 고정했다.
- 2026-11-27 22:35 KST runtime `VERIFIED_REAL`: Sentinel-2 원본 4파일 889,048,315B가 저장됐고 active collector와 intake Worker가 존재했다. 당시 연차 완료 영수증은 0건이었다. 이 항목은 뒤의 2020 완료 영수증보다 이른 역사적 실행 스냅샷이다.
- 완료 영수증→native 센서별 QA→연구 창 후보 RF→동년 Esri 약한 참조 시험 경로는 구현됐다. 수집 대상은 연구 창 후보이며 자동 운영 승격은 하지 않는다.
- 2020 신규 배치 종단 `VERIFIED_REAL`: 두 센서 모두 실제 완료 영수증에서 자동 입고·QA·RF·Esri 약한 참조 시험까지 이어졌다. 2021~2025 수집은 계속 진행 중이므로 전체 6개년 종단 완료로 확대하지 않는다.
- 원본·산출물 무결성 `VERIFIED_REAL` — 원본 120개와 산출물 52개의 SHA-256을 재계산했고 모든 기록값이 일치했다.
- 독립 표본·사람 판독·과학 승인·운영 배포는 계속 `BLOCKED`다.

### 3.8 2020 완료 영수증과 자동 RF

| 센서 | 완료 영수증 | 자동 run | 학습·시험 | Esri 약한 참조 | 별도 validation | 상태 |
|---|---|---|---|---:|---:|---|
| Sentinel-2 | 11장면·8,401,060,705B, 23:09:55 KST | `b4bc7d5034e2…`, 23:12:11 KST | 7,000·57,347픽셀 | 44.65% | 41.56% | `VERIFIED_REAL` |
| Landsat | 4장면·2,027,444,484B, 23:19:17 KST | `a4aee8309b5a…`, 23:20:36 KST | 5,890·6,400픽셀 | 21.45% | 0%, 2,420픽셀 | `VERIFIED_REAL` |

Sentinel-2와 Landsat 값은 각 run의 연구 창에서 Esri v003을 약한 참조로 비교한 결과다. Landsat validation 2,420픽셀은 참조가 모두 클래스 2였지만 모델 예측이 클래스 5와 7에 집중돼 일치도가 0%였다. 이는 해당 창에서 클래스 분포와 모델 예측이 맞지 않았다는 실패 증거이며 독립 정확도나 전체 서자바 성능을 뜻하지 않는다.

2021 Landsat 진행 로그는 당시 상태이며 이후 4장면 완료가 확인됐다. 초기 과거 HEAD 429 뒤에는 재발이나 정체 증거가 없다. Staging 활성 모델은 0개이며 자동 run 결과의 운영 승격은 `BLOCKED`다.

### 3.9 2020 수목 표본 보강 재시험

기존 모델·배치 영수증·동년 Esri v003 참조를 해시로 고정하고 센서별 수목 3,500픽셀을 추가했다. 각 센서는 한 장면 안의 공간적으로 분리된 두 학습 창에서 1,750픽셀씩 뽑았다. Sentinel-2의 평가 분할과 최소 이격은 65.31km, Landsat은 45.80km다. 한 센서당 신규 학습 장면이 하나라는 표본 한계를 함께 보존한다. 기존 validation/test의 반사도 모자이크 SHA와 픽셀 마스크 SHA는 전후에 일치한다.

| 센서·고정 구역 | 픽셀 | Esri 약한 참조 일치도 전→후 | 수목 재현율 전→후 | 상태 |
|---|---:|---:|---:|---|
| Sentinel-2 test | 57,347 | 44.65%→50.09% | 0.00%→95.27% | `VERIFIED_REAL` |
| Sentinel-2 validation | 41,714 | 41.56%→44.34% | 0.00%→45.15% | `VERIFIED_REAL` |
| Landsat test | 6,400 | 21.45%→38.95% | 0.00%→83.96% | `VERIFIED_REAL` |
| Landsat validation | 2,420 | 0.00%→99.55% | 0.00%→99.55% | `VERIFIED_REAL`, 단일 클래스 한계 |

Landsat validation은 참조 2,420픽셀이 모두 수목인 동질 구역이다. 2,409픽셀의 수목 일치는 해당 클래스 점유와 재현을 확인하지만 농경지·시가화가 섞인 운영 분포의 성능을 대표하지 않는다. 수목 예측 점유 확대도 실험 창의 분석 결과이며 운영 수목 면적·산림 통계로 게시하지 않는다. 혼합 클래스 test 6,400픽셀의 38.95%를 함께 본다.

Esri 2020~2025 원본 12개 파일과 재시험 산출물 32개의 SHA를 다시 계산해 기록과 일치함을 확인한 범위는 `VERIFIED_REAL`이다. 관련 회귀 13건과 ASCII Ruff 검사는 `TESTED_SYNTHETIC`이다. 재시험 산출물은 로컬 연구 후보이며 `production_release=BLOCKED`, `deployment_allowed=false`, 독립 정확도와 사람 승인은 모두 미등록이다. 재시험 실행 자체는 당시 API schema와 UI를 바꾸지 않았다.

후속 구현에서는 기존 정확도 검증센터의 서자바 AI 검증 패널에 이 비교를 연결했다. `GET /api/lcluc/west-java/tree-augmentation`은 SHA `40fc2bc3…bf6`으로 고정된 보고서를 읽고, 두 센서×test/validation×전/후의 권위 있는 PNG 8개를 각각 고정 해시로 제공한다. 보고서나 지도 해시가 다르면 HTTP 409로 차단한다. 5280 실제 브라우저에서 네 비교쌍·PNG 8개, 동일 alpha/support·grid, 페이지 오류 0과 Staging 활성 모델 0을 확인한 상태는 `VERIFIED_REAL`이다.

### 3.10 2023~2025 native 입고 현황

| 배치 | 완료 장면·바이트 | 자동 입고·RF | 시험창 Esri 약한 참조 | 상태 |
|---|---|---|---:|---|
| 2023 Sentinel-2 | 11장면·9,232,456,415B | 학습 7,087픽셀 | 48.52%·56,952픽셀 | `VERIFIED_REAL` |
| 2023 Landsat | 2장면·997,987,376B | 학습 6,333픽셀 | 0.00%·528픽셀 | `VERIFIED_REAL` |
| 2024 Sentinel-2 | 10장면·9,191,015,435B | 학습 7,158픽셀 | 38.29%·57,055픽셀 | `VERIFIED_REAL` |
| 2024 Landsat | 3장면·1,564,086,757B | 학습 5,500픽셀 | 28.58%·6,400픽셀 | `VERIFIED_REAL` |
| 2025 Sentinel-2 | 10장면·9,554,510,585B | 학습 7,312픽셀 | test 52.78%·57,497픽셀 | `VERIFIED_REAL` |

2023 Landsat 시험창의 Esri 참조 528픽셀은 모두 농경지였고 모델은 농경지를 예측하지 않아 0%였다. 네 결과는 각 연도의 native 완료 영수증과 RF 보고서 SHA를 대조한 역사적 실자료 결과이며 독립 정확도는 아니다.

2025 Sentinel-2는 기존 승인과 계획 pin을 유지해 12:32:32 KST에 10장면 완료 영수증을 발행했다. 10m train/test/validation 모자이크의 SCL 맑은 비율은 94.22%·99.82%·99.94%다. RF는 7,312픽셀로 학습했고 test 57,497픽셀에서 Esri 약한 참조 52.78%였다. validation 21,673픽셀은 참조가 모두 수목이며 56픽셀만 일치해 0.26%였다. 이 수치는 독립 정확도가 아니다.

2025 Landsat 전체 배치에는 1,507,487,085B가 필요해 당시 승인 잔액보다 343,105,303B가 부족했다. 이 부족분은 이후 정확한 보충 한도로 승인됐으며 현재 상태는 3.12절에 기록한다.

### 3.11 2025 기술 등록·복구

- 자동 등록 `VERIFIED_REAL`: 봉인된 실행 `c4494bb2…e0e0`의 26개 산출물 SHA를 대조한 뒤 후보 `c-7e89…806d`, version `2025-e2-672f7f8c7467`을 Staging PostgreSQL·SeaweedFS에 등록했다. A축 `VALIDATED` revision 4이며 `active=0`이다.
- 화면 조회 `VERIFIED_REAL`: 5280에서 후보 1·검증 1·승인 대기 1·차단/실패 1, 이벤트 4, 페이지 오류 0을 확인했다. 증거는 `artifacts/deploy/westjava-mlops/2025-staging-browser.json`, 화면은 `2025-staging-candidate.png`다.
- Release `BLOCKED`: 독립 과학검증과 사람 승인이 없어 실제 후보 Release 요청은 HTTP 409로 거부됐고 revision 4가 유지됐다.
- 격리 배포 `TESTED_SYNTHETIC`: Compose에서 합성 ONNX v1→v2 활성화, CPU 추론, v1 롤백과 출력 해시 복원을 확인했다. 이 시험은 실자료 후보 배포 승인이 아니다.
- 재시작 `VERIFIED_REAL`: Windows 재부팅 기록 뒤 기존 볼륨의 API·웹·PostgreSQL·객체 저장소를 복구하고 컨테이너에 `unless-stopped` 정책을 설정했다.
- 호스트 Worker 작업 등록 `VERIFIED_REAL`: 같은 Worker와 2025 S2 run SHA를 유지하는 Windows Task Scheduler 로그온 트리거를 구성했다.
- 실제 재부팅 복구 `IMPLEMENTED_UNVERIFIED`: 작업 정의와 로그온 트리거는 확인했지만 구성 뒤 실제 OS 재부팅은 아직 수행하지 않았다.

### 3.12 2025 수목 표본 보강·Landsat 추가 승인

2025 Sentinel-2도 기존 test·validation 모자이크와 정확한 평가 support를 동결한 채 분리 학습 창의 수목 3,500픽셀을 추가했다.

| 고정 구역 | 픽셀 | Esri 약한 참조 일치도 전→후 | 수목 재현율 전→후 | 상태 |
|---|---:|---:|---:|---|
| test | 57,497 | 52.78%→57.08% | 17.23%→86.43% | `VERIFIED_REAL` |
| validation | 21,673 | 0.26%→91.47% | 56→19,825 일치 | `VERIFIED_REAL`, 단일 수목 한계 |

validation 참조는 모두 수목이므로 91.47%를 혼합 클래스 운영 정확도로 해석하지 않는다. 재시험 산출물 16개의 SHA가 기록과 일치하지만 독립 판독·사람 승인·운영 승격은 `BLOCKED`다.

2025 Landsat은 추가 승인 뒤 3장면·1,507,487,085B를 완료했다. 원본 자산 24개의 SHA와 장면별 `QA_RADSAT`, 산출물 26개의 SHA를 검증했다. RF는 5,437픽셀로 학습했고 test 6,400픽셀의 Esri 약한 참조 일치도는 50.34%, validation 4,729픽셀은 27.83%다. 후보 `2025-e2-0e7bfcf99aaa`는 revision 4·active false이며 독립 과학검증 부재로 운영 Release는 `BLOCKED`다.

별도 재다운로드 검증도 `VERIFIED_REAL`이다. 같은 3장면·24개 자산·1,507,487,085B를 격리 경로로 다시 전송했고, 기존 원본과 새 원본의 24개 쌍을 각각 로컬에서 다시 해시해 48회 모두 일치했다. 모든 장면의 `QA_RADSAT`, 30m 창·학습 자료·test/validation 예측이 유지됐으며 RF test 50.34%와 validation 27.83%도 같았다. 공유 원장 SHA는 전후 `8b82affc…067d5`로 유지됐다. 이는 전송·재현 무결성 증거이며 독립 정확도와 운영 배포 승인은 계속 `BLOCKED`다.

Task Scheduler 감시를 확인하기 위해 자식 Worker를 의도적으로 종료했으며 PID 29868에서 32812로 자동 재기동됐다. 재기동 Worker는 같은 입력 해시를 재사용했고 같은 부팅 안의 timestamp 차이는 정규화했다. 이 프로세스 복구는 `VERIFIED_REAL`이지만 실제 OS 부팅 복구는 사용자 승인 전까지 `IMPLEMENTED_UNVERIFIED`다.

## 4. 테스트 증거

| 항목 | 상태 | 확인 범위 |
|---|---|---|
| Sentinel-2 2020 네 창 | `VERIFIED_REAL` | 10m 광학·SCL, 물리·clear 통계와 분류 시험 |
| Landsat overlap | `VERIFIED_REAL` | 30m 두 장면 처리와 분류 미리보기 |
| 최초 Landsat 두 장면 정량 성능 | `BLOCKED` | 학습 장면 겹침과 당시 `QA_RADSAT` 부재 |
| E0~E4 | `VERIFIED_REAL` | 고정 시험 픽셀·SHA·약한 참조 지표 |
| 제품 B | `VERIFIED_REAL` | 2021 서부 창 Esri↔WorldCover 지도 일치도 |
| 제품 C 독립 정확도 | `BLOCKED` | 승인 독립 참조 미등록 |
| E2·E3 실후보 등록 | `VERIFIED_REAL` | Staging PostgreSQL·S3, A축 VALIDATED revision 4, inactive |
| Compose·kind 활성화·롤백·복구 | `TESTED_SYNTHETIC` | 격리 환경의 ONNX 실행, 이력 보존과 DB·SeaweedFS 장애 복구 |
| Compose 5280 실제 앱 조회 | `VERIFIED_REAL` | 2020·2023 상세, 35.63→18.37%, 63.10%, Landsat 109,820과 평가 차단 확인 |
| Windows 2020 지속입고 | `VERIFIED_REAL` | run `9fc6d30…`, S2 4창·Landsat 2장면/1창·학습 19,043·시험 745,043픽셀 |
| network-none 2023 지속입고 | `VERIFIED_REAL` | run `ab5b318…`, 원격 요청 0·65,263픽셀·21.06km 이상·약한 참조 63.10% |
| 지속입고 계약시험 | `TESTED_SYNTHETIC` | mock 429 포함 24 PASS, 실제 429 관측 아님 |
| 지속입고 kind Job·동등성 | `VERIFIED_REAL` | Job Completed, Docker와 10개 결과·자산 SHA/ID 동일, `finished_at`만 다름 |
| Landsat QA_RADSAT 보완 | `VERIFIED_REAL` | 16개·3,577,164B, 기존 QA_PIXEL과 같은 CRS·grid·shape·30m |
| Landsat 2020 자동 입고 RF | `VERIFIED_REAL` | 3개 독립 장면, 학습 1,356·시험 654픽셀, 약한 참조 72.78%·Macro F1 28.08% |
| Sentinel-2 2023 자동 발견 | `VERIFIED_REAL` | 완료 영수증 7자산·교정 고정, 65,263픽셀·약한 참조 63.10%, 새 전송 0 |
| 서자바 2020~2025 native 승인 | `VERIFIED_REAL` | S2 59.90GB·Landsat 8.93GB 센서별 승인과 SHA 고정 |
| native 2020 HEAD | `VERIFIED_REAL` | S2 11장면 8,401,060,705B·Landsat 4장면 2,027,444,484B |
| native runtime 22:35 KST | `VERIFIED_REAL` | 역사적 스냅샷: S2 4파일 889,048,315B, collector·intake 활성, 당시 연차 완료 0 |
| native 2020 S2 종단 | `VERIFIED_REAL` | 11장면·8,401,060,705B 완료, run `b4bc…`, 학습 7,000·시험 57,347, 약한 참조 44.65%·validation 41.56% |
| native 2020 Landsat 종단 | `VERIFIED_REAL` | 4장면·2,027,444,484B 완료, run `a4ae…`, 학습 5,890·시험 6,400, 약한 참조 21.45%·validation 0% |
| 2020 수목 보강 S2 | `VERIFIED_REAL` | 수목 3,500 추가, 고정 test 44.65→50.09%·수목 recall 0→95.27%, validation 41.56→44.34%·0→45.15% |
| 2020 수목 보강 Landsat | `VERIFIED_REAL` | 수목 3,500 추가, 고정 test 21.45→38.95%·수목 recall 0→83.96%, 단일 수목 validation 0→99.55% |
| 수목 보강 무결성 | `VERIFIED_REAL` | Esri 12파일·산출물 32개 SHA 일치 |
| 수목 보강 회귀 | `TESTED_SYNTHETIC` | 13 PASS·ASCII Ruff PASS |
| 수목 보강 후보 운영 | `BLOCKED` | 독립 판독·사람 승인 없음, Staging 활성 0·모델 미게시 |
| 수목 전후 API·화면 패널 | `VERIFIED_REAL` | 5280 네 비교쌍·PNG 8개, 동일 alpha/support·grid, 오류 0·활성 모델 0 |
| 2023·2024 native 입고·RF | `VERIFIED_REAL` | S2/Landsat 각 연도 완료 영수증·RF 보고서 SHA와 약한 Esri 지표 검증 |
| 2025 Sentinel-2 입고·RF | `VERIFIED_REAL` | 10장면·9,554,510,585B, 10m QA, 학습 7,312, test 57,497·52.78%, 단일 수목 validation 21,673·0.26% |
| 2025 기술 등록·화면 | `VERIFIED_REAL` | 후보 `c-7e89…806d`, revision 4·active 0, 5280 페이지 오류 0 |
| 2025 Release | `BLOCKED` | 독립·사람 승인 없음, HTTP 409·revision 4 유지 |
| 격리 Compose ONNX 전환 | `TESTED_SYNTHETIC` | 합성 v1→v2→v1, CPU 추론·출력 해시 복원 |
| 2025 Lifecycle 회귀 | `TESTED_SYNTHETIC` | 13 PASS·변경 파일 Ruff PASS |
| 컨테이너 재시작 정책 | `VERIFIED_REAL` | 기존 볼륨 복구, `unless-stopped` 설정 |
| Windows Worker 로그온 작업 | `VERIFIED_REAL` | 같은 Worker·2025 S2 run SHA, Task Scheduler 로그온 트리거 구성 |
| Windows Worker 재부팅 복구 | `IMPLEMENTED_UNVERIFIED` | 구성 뒤 실제 OS 재부팅 미수행 |
| 2025 S2 수목 보강 | `VERIFIED_REAL` | 수목 +3,500, 고정 test 52.78→57.08%·recall 17.23→86.43%, 단일 수목 validation 0.26→91.47% |
| 2025 S2 보강 무결성 | `VERIFIED_REAL` | 산출물 16개 SHA 일치 |
| 2025 S2 보강 운영 | `BLOCKED` | 독립 판독·사람 승인 없음, 후보 미승격 |
| 2025 Landsat 추가 승인 | `VERIFIED_REAL` | 부족분 343,105,303B 정확한 보충 한도 승인 |
| 2025 Landsat 종단 | `VERIFIED_REAL` | 3장면·1,507,487,085B, 원본 24·산출물 26 SHA, QA_RADSAT, 학습 5,437·test 50.34%·validation 27.83% |
| 2025 Landsat 재다운로드 | `VERIFIED_REAL` | 같은 3장면·24자산·1,507,487,085B 재전송, 기존↔신규 24쌍·48회 로컬 SHA 일치, 같은 30m RF 예측·원장 SHA 불변 |
| 2025 Landsat 후보 | `VERIFIED_REAL` | `2025-e2-0e7bfcf99aaa`, revision 4·active false |
| 2025 Landsat 운영 | `BLOCKED` | 독립 과학검증·사람 승인 없음 |
| Worker 자식 프로세스 복구 | `VERIFIED_REAL` | 의도적 종료 PID 29868→32812 자동 재기동, 같은 입력 해시·timestamp 정규화 |
| 2021~2025 native 수집 | `VERIFIED_REAL` | 2021~2025 S2·Landsat 완료 기록과 2025 양 센서 end-to-end 증거 확인 |
| 원본·산출물 최종 재감사 | `VERIFIED_REAL` | 원본 120개와 자동 실행 산출물 52개의 SHA-256 일치 |
| 자동 입고 회귀 | `TESTED_SYNTHETIC` | 177 PASS·1 SKIP |

추가로 19:19 KST strict inventory는 Sentinel-2 13장면, Landsat 16장면, Esri 서자바 원본 12개를 확인했고 stage report API는 HTTP 200이었다. 연도별 주 면적 피복은 Sentinel-2 약 14.65%, Landsat 약 59.40~61.32%다. 이는 서자바 전역 6개년 완전 피복을 뜻하지 않는다. 경계 snapshot의 발행판·효력일·기관 승인은 미확정이며, 원격 수집을 새로 실행하지 않고 보유 파일을 감사했다.

## 5. 발표 스크립트

### 1분

“서자바 Gate에서는 승인된 native 수집의 2020년분을 두 센서 모두 완료했습니다. Sentinel-2는 11장면 8.401기가바이트, Landsat은 4장면 2.027기가바이트입니다. 기존 RF에 빠진 수목을 센서별 3,500픽셀 보강하고 평가 자료를 동결한 재시험에서 test 약한 참조는 S2 44.65%→50.09%, Landsat 21.45%→38.95%로 상승했습니다. Landsat validation 99.55%는 수목만 있는 2,420픽셀의 결과입니다. 독립 정확도와 사람 승인은 없고 모델은 게시하지 않았습니다.”

### 5분

1. 최초 Sentinel-2 네 창과 Landsat 겹침창의 해상도·QA·약한 참조 조건을 역사적 기준으로 설명한다.
2. Landsat 16장면의 QA_RADSAT 3,577,164B를 같은 grid로 보완한 현재 상태를 구분한다.
3. Landsat 2020 자동 입고는 3개 독립 장면, 학습 1,356·시험 654픽셀이다.
4. 72.78%와 Macro F1 28.08%는 Esri 동년 약한 참조 비교다.
5. Sentinel-2 2023은 기존 완료 영수증의 7개 자산·교정을 자동 발견해 63.10%를 재현했다.
6. WorldCover는 2021 동년 제품 비교에만 사용하고 다른 연도 정답으로 사용하지 않는다.
7. 5280 실제 화면과 격리 Worker 결과를 확인했으며 새 원격 전송은 0이다.
8. 현재 native 승인은 Sentinel-2 59.90GB와 Landsat 8.93GB이며 기존 미정산 203,423,744B는 원장에 유지한다.
9. 2020 완료 영수증은 S2 11장면 8,401,060,705B와 Landsat 4장면 2,027,444,484B다.
10. 자동 RF의 약한 참조는 S2 44.65%, Landsat 21.45%이고 Landsat validation은 0%다.
11. 센서별 수목 3,500픽셀을 분리 학습 창에서 추가한 뒤 고정 test의 일치도는 S2 50.09%, Landsat 38.95%로 상승했다.
12. Landsat validation 99.55%는 수목만 있는 2,420픽셀의 결과라 운영 분포를 대표하지 않는다.
13. 정확도 검증센터에서 네 비교쌍·PNG 8개와 동일 alpha/support·grid, 페이지 오류 0을 실제 확인했다.
14. 2023·2024 두 센서와 2025 S2의 완료 영수증·RF 보고서를 검증했다.
15. 2025 S2는 test 52.78%, 단일 수목 validation 0.26%이며 후보는 revision 4·active 0이다.
16. 독립·사람 승인 부재로 Release 409를 확인했고 합성 ONNX 전환 시험과 구분한다.
17. 2025 S2 수목 보강 test는 57.08%, 단일 수목 validation은 91.47%이며 독립 정확도는 아니다.
18. 2025 Landsat은 3장면·1,507,487,085B와 RF test 50.34%·validation 27.83%까지 종단 검증했다.
19. 같은 24개 자산을 별도 경로로 재다운로드해 기존↔신규 24쌍의 SHA와 같은 30m RF 예측을 확인했다.
20. 자식 Worker 종료 뒤 PID 29868→32812 자동 재기동과 같은 입력 해시를 확인했다.
21. Task Scheduler 로그온 작업은 구성했고 실제 OS 부팅 복구 시험은 사용자 승인 뒤 수행한다.
22. 독립 표본 검증과 사람 승인을 운영 배포 조건으로 둔다.

## 6. Q&A

**Q. E0 70.39%와 E2 18.37% 중 어느 모델이 더 정확한가요?**

해상도와 시험 공간이 다르므로 이 두 숫자만으로 순위를 정할 수 없다. 같은 745,043 시험 픽셀을 쓴 E1·E2·E3 내부 비교와 각 시험의 공간 조건을 함께 본다.

**Q. E4 63.10%는 2023 시간 일반화 정확도인가요?**

2020 분할과 파일·장면 SHA가 겹치지 않는 별도 2023 창의 약한 참조 일치도다. 평가 위치도 달라졌으므로 순수 시간 일반화 정확도로 확정하지 않는다.

**Q. WorldCover 83.45%는 모델 정확도인가요?**

2021 서부 창에서 Esri v003과 WorldCover v200을 6대분류로 맞춘 동년 제품 지도 일치도다. 독립 정확도는 별도 제품 C에서 측정해야 한다.

**Q. 최초 Landsat 두 장면이 100% clear인데 왜 정량 평가를 막나요?**

그 pilot 창의 `QA_PIXEL` 기준 clear 비율은 100%지만 두 장면이 기존 학습 자료와 겹치고 당시 `QA_RADSAT`가 없어 포화 픽셀 검사가 빠졌다. 이후 보완 QA와 별도 3개 장면을 사용한 새 시험은 별도 결과로 표시한다.

**Q. 서자바 2020 Esri와 MapBiomas 면적 차이를 변화량으로 볼 수 있나요?**

경계와 분류체계가 다른 각 제품의 native 면적이다. Esri 3,677,893.60ha와 MapBiomas 3,704,306.95ha를 각각 출처 범위와 함께 표시한다.

**Q. Compose와 kind에서 두 ONNX가 동작했으면 운영 승인 모델인가요?**

E2·E3 실후보 등록과 양 환경의 활성화·Serving·롤백·장애 복구를 실제 확인했다. 두 후보는 `active=false`이고 독립 검증·과학 승인이 없으므로 운영 승인 모델은 아니다. Compose 5280의 실제 조회도 후보 상태를 바꾸지 않았다.

**Q. 지속입고 Worker가 Sentinel-2를 새로 내려받았나요?**

Windows 2020과 network-none 2023 자동 입고 실증은 새 원격 수집을 시작하지 않았고 `remote_requests`가 0이었다. 이후 별도 사용자 승인으로 2020~2025 native collector를 시작했으므로 두 시점을 구분한다.

**Q. E1 35.63%에서 E2 18.37%로 바뀐 것을 개선으로 볼 수 있나요?**

같은 745,043픽셀에서 후보 일치도가 낮아졌고 run도 `improved=false`로 기록했다. 둘 다 Esri 약한 참조 비교이며 모델 개선이나 독립 정확도를 입증하지 않는다.

**Q. 시험의 429가 실제 수집 장애였나요?**

24개 계약시험의 429는 중단 회로를 검증한 mock이다. 실제 실행에서 HTTP 429는 관측되지 않았고 회로는 비활성 상태였다.

**Q. Landsat `QA_RADSAT` 부재 문제는 해결됐나요?**

보유 16장면에 대해서는 3,577,164B를 실제 취득하고 기존 `QA_PIXEL`과 같은 grid임을 확인했다. 최초 두 장면 pilot의 부재 기록은 당시 상태이며, 새 2020 자동 입고 시험은 3개 독립 장면과 보완된 QA를 사용한다.

**Q. 새 Landsat 72.78%는 독립 정확도인가요?**

동년 Esri v003와 비교한 654픽셀의 약한 참조 일치도다. 장면 분리와 30.07km 공간 이격은 확인했지만 승인된 독립 표본·사람 판독을 대신하지 않는다.

**Q. 공백 계획이 있으면 2020~2025 전역 수집을 바로 시작하나요?**

공백과 공급자 후보를 고정한 계획 근거다. 이후 Sentinel-2 59.90GB와 Landsat 8.93GB의 센서별 한도가 승인돼 수집이 시작됐다. 22:35 KST에는 연차 완료가 0이므로 전역 완료로 해석하지 않는다.

**Q. 22:35 KST 수신량은 전역 수집 완료를 뜻하나요?**

Sentinel-2 4파일 889,048,315B를 저장한 당시 실행 중 스냅샷이다. 이후 2020년은 S2 11장면과 Landsat 4장면의 완료 영수증과 자동 RF까지 확인했다. 전체 2020~2025 수집 완료를 뜻하지 않는다.

**Q. 기존 미정산 4건은 새 승인으로 정산됐나요?**

완결 계측 영수증이 없어 203,423,744B 예약을 유지했다. laneB 두 건과 pilot 두 건의 부분 파일 상태를 보존했고 기존 공유 원장 SHA도 바뀌지 않았다.

**Q. Landsat validation 0%는 무엇을 뜻하나요?**

해당 validation 2,420픽셀의 Esri 약한 참조는 모두 클래스 2였지만 모델은 클래스 5와 7을 예측했다. 해당 창의 분포·모델 불일치를 드러낸 실패 증거이며 독립 정확도나 전체 서자바 성능은 미측정이다.

**Q. 2020 완료 영수증으로 6개년 자동 입고가 끝났나요?**

2020년 두 센서의 완료 영수증→QA→RF→약한 참조 시험 범위가 끝났다. 이후 2021~2025 두 센서 완료 기록과 2025 Landsat end-to-end 증거까지 확인해 native 종단은 `VERIFIED_REAL`이다. 각 RF 수치는 창 단위 Esri 약한 참조이며 독립 정확도와 운영 승격은 계속 차단된다.

**Q. 원본과 자동 run 산출물의 최종 감사도 끝났나요?**

원본 자산 120개와 자동 실행 산출물 52개의 SHA-256을 다시 계산해 모든 기록값과 일치함을 확인했다. 무결성 재감사는 `VERIFIED_REAL`이다.

**Q. 수목 표본 보강으로 모델이 운영 가능한 수준이 됐나요?**

고정 test에서 S2 일치도는 44.65%→50.09%, Landsat은 21.45%→38.95%로 상승했고 수목 재현율도 개선됐다. 동년 Esri 약한 참조 시험 결과이며 독립 표본·사람 승인이 없어 운영 모델은 게시하지 않았다.

**Q. Landsat validation 99.55%를 모델 정확도로 발표할 수 있나요?**

참조 2,420픽셀이 모두 수목인 동질 구역의 수목 재현 결과다. 혼합 클래스 test는 38.95%이며 전역·운영 분포의 독립 정확도는 미측정이다.

**Q. 보강 전후 비교에서 평가 자료도 바뀌었나요?**

기존 validation/test 모자이크 SHA와 정확한 픽셀 마스크를 동결했다. 바뀐 것은 공간적으로 분리된 학습 창에서 센서별로 추가한 수목 3,500픽셀과 그 후보 모델뿐이다. 각 센서의 두 학습 창은 한 장면에서 나왔으므로 장면 다양성 한계도 남아 있다.

**Q. 정확도 검증센터에서 전후 지도를 실제로 확인했나요?**

보고서와 PNG 8개의 SHA pin, API 경로와 해시 불일치 409 차단을 구현했다. 5280에서 네 비교쌍과 실제 PNG 8개, 동일 alpha/support·grid, 페이지 오류 0과 활성 모델 0을 확인해 `VERIFIED_REAL`이다.

**Q. 2023·2024 결과가 있으면 연도 일반화가 검증됐나요?**

각 연도의 완료 영수증과 RF 보고서, 동년 Esri 약한 참조 지표가 검증됐다. 독립 사람 판독이 없으므로 연도 일반화 정확도나 운영 승인으로 해석하지 않는다.

**Q. 2025 수집은 어디까지 진행됐나요?**

Sentinel-2는 10장면·9,554,510,585B 완료 영수증, 10m QA·RF·수목 보강까지 확인했다. Landsat은 추가 승인 뒤 3장면·1,507,487,085B를 완료했고 원본 24개·산출물 26개 SHA, 전 장면 `QA_RADSAT`, RF test 50.34%·validation 27.83%를 확인했다. 두 센서 후보 모두 독립 정확도와 운영 승격은 차단 상태다.

**Q. 2025 Sentinel-2 RF 성능은 어떤가요?**

test 57,497픽셀의 동년 Esri 약한 참조 일치도는 52.78%다. validation 21,673픽셀은 모두 수목 참조인데 56픽셀만 일치해 0.26%다. 단일 클래스 검증 한계를 포함한 약한 참조 결과이며 독립 정확도는 아니다.

**Q. 자동 등록되면 바로 Release할 수 있나요?**

봉인 산출물로 Staging 후보를 등록해 A축 `VALIDATED` revision 4까지 기록했지만 active는 0이다. 독립 과학검증과 사람 승인이 없어 Release는 HTTP 409로 차단됐다.

**Q. 재부팅 뒤 자동으로 모든 처리가 복구되나요?**

API·웹·PostgreSQL·객체 저장소 컨테이너는 기존 볼륨으로 복구하고 `unless-stopped`를 설정했다. 같은 Worker와 2025 S2 run SHA를 쓰는 Task Scheduler 로그온 작업도 구성했지만 실제 OS 재부팅 복구 시험은 아직 수행하지 않았다.

**Q. 2025 S2 수목 보강 결과는 어떻게 달라졌나요?**

고정 test의 약한 참조 일치도는 52.78%→57.08%, 수목 재현율은 17.23%→86.43%였다. 모두 수목인 validation은 56→19,825/21,673 일치로 0.26%→91.47%가 됐다. 독립 정확도와 운영 승격 근거는 아니다.

**Q. 2025 Landsat 부족분은 해결됐나요?**

343,105,303B 추가 승인 뒤 3장면·1,507,487,085B를 완료했다. 24개 원본 SHA·전 장면 QA_RADSAT·26개 산출물 SHA와 RF test 50.34%·validation 27.83%를 end-to-end 증거로 확인했다.

**Q. 같은 Landsat 원본을 실제로 다시 내려받아도 결과가 같았나요?**

같은 3장면·24개 자산·1,507,487,085B를 격리 경로로 다시 전송했다. 기존 원본과 새 원본의 24쌍을 독립적으로 다시 해시한 48회 계산이 모두 일치했고, QA_RADSAT·30m 창·RF test 50.34%·validation 27.83%도 유지됐다. 전송 재현성은 확인됐지만 Esri 약한 참조이므로 독립 정확도나 운영 승인을 뜻하지 않는다.

**Q. Task Scheduler가 Worker를 실제로 다시 띄웠나요?**

같은 Windows 부팅 안에서 자식 Worker를 의도적으로 종료하자 PID 29868에서 32812로 자동 재기동했고 같은 입력 해시를 재사용했다. 실제 OS 재부팅 후 자동 복구는 사용자 승인 전이라 아직 미검증이다.
