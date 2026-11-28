# v4.2 그대로 읽는 1분·5분 발표

## 1분

“v4.2에서는 기후 설명과 숫자의 경로를 분리하고 실제 CCKP CDD 원본 한 건을 SHA로 고정해 계산했습니다. 1951년부터 1980년까지 제공된 climatology의 개발 bbox 12,765셀 구면가중 평균은 40.91221481742199일입니다. 하지만 인도네시아 행정경계 평균이나 연별·월별 값이 아니며 ERA5 재분석은 독립 ground truth가 아닙니다. live 서비스·학습·배포는 0건이므로 전체 완료는 아닙니다.”

## 5분

1. **문제** — 벡터 유사도는 숫자의 단위·달력·격자·시나리오나 기관 authority를 보증하지 않는다.
2. **공통 계약** — source/version/URI/SHA/license/acquired_at, 관측/전망, 모델/시나리오, 단위, CF 달력, 공간·시간, ACL, trace를 필수로 고정한다.

## 결과 카탈로그 Gate — 1분

“결과 카탈로그는 기존 공통 결과 ID에 수치, 원본 SHA, 지도 파일, 보고서와 불확실성 상태를 고정합니다. 실제 CCKP 결과에는 1951–1980 개발 bbox CDD 40.91221481742199일, 12,765개 격자점과 보고서 2개가 붙었습니다. BIG 결과에는 반텐 과거 폴리곤 1개가 붙었지만 현행 시기와 사용 권리는 미확인입니다. 두 결과 모두 불확실성은 미산정이고 과학 승인과 기관 게시 승인은 각각 대기 중입니다. 따라서 `CATALOG_READY`는 공개 승인이나 독립 정확도를 뜻하지 않습니다.”

## 결과 카탈로그 Gate — 5분

1. 기존 결과 ID와 패키지 SHA를 분리해 같은 결과를 찾으면서 패키지 변경도 감지한다.
2. 원본·라이선스 근거·layer·report의 byte와 SHA, 기간·CRS·nodata·단위를 fail-closed 검증한다.
3. CCKP 실제 원본을 replay해 `40.91221481742199 days`, 12,765개 bbox 격자 중심, 보고서 2개를 고정했다.
4. 이 값은 인도네시아 행정경계 평균이나 연별·월별 값이 아니며 ERA5 재분석은 독립 ground truth가 아니다.
5. BIG 자료는 2017 조례 표기의 반텐 역사 폴리곤 1개다. 현행 RTRW 6지역 확보로 확대하지 않는다.
6. 두 seed 모두 `NOT_REPORTED`이므로 불확실성이 0이 아니라 미산정 상태다.
7. 과학 검토와 기관 게시 결정을 서로 다른 authority·근거·revision으로 기록한다.
8. 게시 승인은 현재 과학 revision의 선승인과 게시 입력 완전성이 필요하다.
9. 실제 두 seed의 두 승인축은 모두 `PENDING`이며 실제 기관 authority·독립 정확도·학습·배포는 차단 상태다.

## 운영 경로 2~8 — 1분

“Platform2는 기존 React와 API를 Docker 5180과 로컬 Kubernetes 5181에 같은 이미지로 이식했습니다. 두 환경에서 공통 결과·jobs·기존 GeoAI 연결, 반텐 경계와 2020~2025 결과, 실제 Sentinel/Landsat 광학 레이어 12개를 확인했습니다. 개발 Compose의 PostGIS·pgvector와 S3에서는 CCKP 보고서 3,295바이트를 서명 읽기로 SHA 검증했고, 실제 PostgreSQL 작업 큐는 모의 기관 응답 10건을 통과했습니다. Worker는 승인된 대기 작업 0건을 안전 종료했습니다. 다만 기존 5175는 별도 실행이며 실제 기관 endpoint·권한·복구 인수와 반텐 과학 인수·독립 정확도는 여전히 별도 차단 상태입니다.”

## 운영 경로 2~8 — 5분

1. 기관 작업은 사용자 URL·명령 대신 운영자가 고정한 승인 ID만 접수한다.
2. 같은 승인·공급자 설정에 같은 작업 ID와 idempotency key를 써 중복 제출을 줄인다.
3. 실제 provider 설정이 없어 현재 조회는 HTTP 200과 `JOB_PROVIDER_CONFIG_NOT_SET`, worker는 exit 1이다.
4. React에는 작업·취소·결과 ID, 모델 version·rollback, 기관 원천 상태를 같은 origin으로 읽는 화면이 구현됐다.
5. RTRW·CCKP·Lake·KLHK·private index·Sentinel 6종은 로컬 증거만 검증됐고 모두 공개 차단이다.
6. 실제 manifest의 누출 scene 전체를 격리해 1,751행·적격 1,382행·scene 충돌 0 후보를 만들었다.
7. 지리 중첩·피복·독립 라벨 검사가 남아 후보 학습과 배포는 허용하지 않았다.
8. 합성 ONNX는 11→12→11 rollback과 과학 승인 철회 후 실행 차단을 검증했다.
9. Docker 5180과 로컬 Kubernetes 5181에서 같은 이미지·읽기전용 원본·3 PVC·광학 12 layer를 확인했다. 기존 5175는 별도다.
10. 개발 PostGIS/pgvector·S3와 PostgreSQL jobs는 실증했지만 기관 endpoint·IAM/SSO·백업/복구·과학 인수는 차단 상태다.
3. **설명 경로** — ACL·license·유효기간 선필터 후 BM25·합성 hash vector·metadata로 찾고 원문 citation을 재검증한다.
4. **정량 경로** — `climate.query`는 고정 raw·receipt·CF·license가 맞는 한 CDD bbox 통계만 반환한다.
5. **source·lake·feature** — bounded discovery와 receipt, CF/as-of/ACL/bbox 계획은 fail-closed다. planner는 `execution_started=false`, `numeric_features=null`이다.
6. **시험 증거** — contract/RAG 23, source 24, lake/feature 24로 합성 71 PASS이며, 별도 climate.query는 합성 12 + 실원본 재현 2를 통과했다.
7. **정직한 한계** — 행정경계 통계, 연별/월별 시계열, 독립 정확도, live API/RAG 등록, 학습·배포는 검증하지 않았다.

상세 근거: [v4.2 기후 계약·RAG 이해자료](../V42_CLIMATE_FOUNDATION_AND_RAG.md)

## KLHK ingestion·MLOps 추가 1분

“KLHK·CCKP 문서는 원문과 SHA를 고정하고 검토 전에는 운영 RAG나 학습으로 넘기지 않도록 했습니다. 실제 metadata 원본 7개, 122개 span, 381,676바이트를 보존했고 SHA 불일치는 없었습니다. 그러나 KLHK renderer는 25항목이며 native 23클래스 domain과 license는 미확인입니다. ingestion/RAG 29건과 MLOps 6건의 합성시험은 통과했지만 실제 운영 index, 학습, 독립정확도, 배포는 모두 차단 상태입니다.”

추가 상세 근거: [KLHK 문서 ingestion과 학습·배포 Gate](../V42_KLHK_RAG_MLOPS_GATES.md)

## CCKP bbox 수치 도구 추가 1분

“실제 4,209,592바이트 ERA5 CDD NetCDF를 SHA로 고정하고 17개 Range chunk로 취득했습니다. 파일의 CF-1.6과 NETCDF3_CLASSIC, 1951년부터 1980년까지의 climatology를 직접 검사했으며, 개발 bbox의 12,765개 셀을 full-cell 구면 면적가중한 값은 40.91221481742199일입니다. 하지만 인도네시아 행정경계 평균이나 연별·월별 값이 아니며, ERA5 재분석은 독립 ground truth가 아닙니다. live 서비스 등록·학습·배포는 아직 0건입니다.”

추가 상세 근거: [CCKP Indonesia 개발 bbox 수치 도구](../V42_CCKP_INDONESIA_NUMERIC_TOOL.md)

## 최종 통합 상태 추가 1분

“36개 주·연도 셀이 최소 28개 패치 기준을 충족했습니다. 시험 영상 반영 후 6밴드와 SCL 동시 피복은 0.977325%, 유효 피복은 0.890387%입니다. 재감사 화면을 Edge에서 확인했고, CCKP 개발 시험 범위의 CDD 평균은 40.9122일로 재현했습니다. Sentinel 공간 공백, KLHK 클래스·라이선스, 독립 현장 정확도, 실제 학습·배포 및 공개 RAG는 미완료입니다.”

추가 상세 근거: [최종 통합 상태](../V42_FINAL_INTEGRATION_STATUS.md)

## Sentinel 단일 pilot 추가 1분

“East Java 2023의 고정 Sentinel-2 scene 한 건에서 예약, exact asset/window pin, same-scene 6 band와 SCL, bounded Range, 실측 정산을 실제 완료했습니다. 65,536개 pixel은 모두 clear였고 28개 요청에서 7,471,506바이트를 읽었으며 오류와 429는 0이었습니다. 후속 exact 재감사에서 전체 피복은 0.977325%와 0.890387%가 됐습니다. 전체 공간 완료, 예산 충분성, BIG 승인, 독립 정확도, 학습·배포는 여전히 차단 상태입니다.”

추가 상세 근거: [Sentinel 단일 실제 pilot](../V42_SENTINEL_SINGLE_PILOT.md)

## Sentinel post-pilot 재감사 추가 1분

“실 저장 geometry로 36셀과 72개 exact missing feature를 다시 계산했습니다. East Java 2023 pilot은 present와 clear 면적을 각각 6,556,514.48제곱미터 늘렸고 새 피복률은 0.9773249834%와 0.8903869553%입니다. 재감사 중 collector·remote download·ledger write는 모두 0이었습니다. 다음 6개 후보의 한 창 참고 합은 44,829,036바이트지만 전체 전송량이나 실행 승인은 아닙니다. 새 API/UI는 로컬 API와 실제 Edge에서 확인했지만 전체 공간 완료·BIG 승인·독립 정확도·학습·배포는 여전히 차단 상태입니다.”

추가 상세 근거: [Sentinel pilot 반영 36셀 재감사](../V42_SENTINEL_POST_PILOT_REAUDIT.md)

## Sentinel 경계 내 후속 배치 추가 1분

“후속 배치는 6개 주와 2020~2025년 36셀에 경계 내부 256×256 창 하나씩을 계획했습니다. 12시 5분 reconciliation에서 8창 수신·QA 통과 5를 확인했지만 worker PID가 사라졌고 9번째 West Java 2024 창은 32MiB 예약 뒤 실제 전송량이 미확정입니다. 429는 0이어도 정산 전 종료이므로 현재 상태는 차단입니다. pending transfer를 검증·정산하기 전 재개하지 않으며, 신규 창은 아직 전역 aggregate나 학습 적격에 반영하지 않습니다.”

추가 상세 근거: [Sentinel 경계 내 후속 배치](../V42_SENTINEL_BACKGROUND_COVERAGE_BATCH.md)

## 공통 결과 등록·검토·조회 Gate 추가 1분

“공통 결과 Gate는 고정 증거를 검증해 등록하고, 같은 ID로 다시 읽으며, 검토 이력을 남깁니다. 실제 프로젝트 registry의 10개 결과에 검증·등록·재조회 30단계를 모두 통과했고, 실제 Edge 선택시험 5건과 DOM 계약 2건도 통과했습니다. 현재 로컬 8014에는 10개 결과가 모두 PENDING으로 제공됩니다. 검토 완료와 증거 상태는 별도이므로 RTRW 0/6, Sentinel 8/36과 9번째 미정산, KLHK 23클래스·권한 미확보, scene split 중복은 그대로 차단됩니다. 학습·배포는 실행하지 않았습니다.”

추가 상세 근거: [공통 결과 등록·검토·조회 Gate](../V42_COMMON_RESULT_REVIEW_GATE.md)

## LCLUC 분류사전·변화·분류기 — 1분

“LCLUC는 실제 반텐 Esri 2020~2025 여섯 연도와 Sentinel-2·Landsat 6개년 원본·QA·RGB를 확보했습니다. Sentinel-2는 224개 asset·32개 scene, Landsat은 168개 asset·24개 scene이며 Docker 5180과 Kubernetes 5181에서도 실제 광학 레이어 12개를 확인했습니다. 대표 Esri 2020→2025 비교는 공통 유효 935,231.32헥타르 중 78,998.91헥타르가 달랐습니다. 다만 최종 과학 인수는 COVERAGE_GAPS입니다. Landsat은 연차별 10.35~274.32헥타르, Sentinel-2는 2021~2025에 0.09~2.88헥타르가 경계 안에서 비어 있습니다. 기술 이식과 독립 정확도·기관 승인을 분리하고 WorldCover 2021도 타연도 정답으로 쓰지 않습니다.”

## LCLUC 분류사전·변화·분류기 — 5분

1. KLHK 공식 사전은 23코드지만 모델 주제 출력은 토지피복 22개다. 구름 `2500`과 NoData `65535`는 서로 다르다.
2. 분류사전 검증은 연차 레이어의 native code·license·기관 승인을 자동 보장하지 않는다.
3. 잠정 KLHK→legacy-9 crosswalk는 11개 mapping·12개 exclusion이며 source/target taxonomy SHA에 결속되고 기본 차단된다.
4. 변화 엔진은 서로 다른 연도, 같은 taxonomy·grid, metre equal-area CRS, content SHA와 provenance를 요구한다.
5. 양 시점 모두 유효한 픽셀 교집합으로 전이행렬·변화면적·hotspot·구역통계를 계산한다.
6. 실제 Esri 반텐 전역은 2020~2025 6/6년, One Map 경계 935,602.88ha다.
7. 대표 2020→2025는 공통 935,231.32ha·변화 78,998.91ha이며, 1km 변화 셀 8,663개와 hotspot 20개다.
8. 기존 Workspace의 swipe·6년 면적 시계열·전환행렬·KPI·원천 inventory와 결정론적 HTML·JSON·CSV를 Edge에서 확인했다.
9. Esri 동일 연도 reference coverage와 연차 변화는 independent accuracy가 아니다. 사업통계 승인·KLHK 연차 등록도 별도다.
10. 두 센서 6개년 원본·QA·RGB와 Docker 5180·Kubernetes 5181 기술 이식은 완료했지만, `COVERAGE_GAPS` 과학 인수·독립 정확도·자동 MLOps는 별도 차단이다.

추가 상세 근거: [LCLUC 분류사전·변화 계산·기준 분류기](../V42_LCLUC_TAXONOMY_CHANGE_CLASSIFIERS.md)

## LCLUC 연차 입고 Gate — 1분

“연차 Gate는 Sentinel-2와 Landsat 원본을 byte·SHA·출처·연도·필수 6밴드와 QA가 고정된 bundle로 접수합니다. Docker 5180과 kind Kubernetes 5181에서 격리 합성 2026 번들의 대기·승인·독립참조 대기·합성평가 전이를 각각 실행했고, 두 센서 1,023/1,024 clear 픽셀과 합성 holdout 256개, 네 GeoTIFF SHA를 확인했습니다. Edge에서도 기존 실제 Sentinel-2 2020 지도와 합성 2026 상태·증거 링크를 확인했습니다. 그러나 실제 2026 원본과 독립 참조는 없고 `independent_accuracy`는 null이므로 실제 정확도와 공공 배포는 차단 상태입니다.”

## LCLUC 연차 입고 Gate — 5분

1. `bundle.json`이 상대 경로·byte·SHA·출처·버전·라이선스·취득 시각을 고정한다.
2. Sentinel-2 B02·B03·B04·B08·B11·B12+SCL과 Landsat SR_B2~B7+QA_PIXEL을 모두 요구한다.
3. WGS84 경계를 30m EPSG:6933에 맞추고 날짜·scene ID 순서로 결정적 clear composite를 만든다.
4. 센서별 물리 피복 95%, clear 80% 미달은 `QUALITY_BLOCKED`다.
5. 동년 라벨과 bundle SHA에 결속된 승인 없이 학습하지 않는다.
6. 출력 RF·분류 TIFF·confidence TIFF는 후보이며 confidence는 보정된 오류확률이 아니다.
7. Sentinel 후보와 Landsat 후보 간 일치도는 독립 정확도가 아니다.
8. WorldCover·Esri와의 일치는 약한 참조이며 WorldCover 2021을 타연도 정답으로 쓰지 않는다.
9. 독립 평가는 출처 분리, protocol·authority·승인, 학습 위치 1셀 제외, 센서별 100표본을 요구한다. 합성은 `synthetic_holdout`에만 기록한다.
10. Docker·Kubernetes 합성 E2E와 회귀 45 PASS·1 SKIP은 확인했지만, 실제 2026 bundle·독립 참조·production release 승인이 없어 과학·공공 상태는 `BLOCKED`다.

추가 상세 근거: [LCLUC 연차 원본 입고·후보 모델·검증 Gate](../V42_LCLUC_ANNUAL_INTAKE_GATE.md)

## 반텐 Sentinel-2 Explore — 1분

“Sentinel-2 Explore는 기존 연차 비교와 같은 2열 지도 폭을 사용합니다. 오른쪽에는 클래스 면적·비율과 AI 신규 분류, 아래에는 전이행렬·세부 변화탐지·장기 추세·제품 간 검증이 놓입니다. 상단 지도 분석과 여섯 결과 제목은 해당 카드로 초점과 스크롤을 옮깁니다. Swipe의 T1·T2는 상단 필터·지도·AOI 표와 같은 연도쌍을 사용하고 구분선은 50:50으로 정렬됩니다. 영상·지수·품질은 Sentinel-2 L2A이며 면적·비율·전이는 선택 AOI의 Esri 연차 토지피복 집계입니다. 독립 정확도는 미측정이고 생산 연차 AI 실제 접수는 0건입니다.”

추가 상세 근거: [반텐 Sentinel-2 Explore Gate](../V42_LCLUC_SENTINEL_EXPLORER.md)

## 반텐 Landsat 장기 분석 Explorer — 1분

“반텐 Landsat Explorer는 2020~2025 실제 24장면을 센서별 밴드와 QA 규칙으로 맞춰 7개 지도로 제공합니다. 2020~2022 합성은 맑은 관측 97.86%, 2023~2025 합성은 99.82%를 한 번 이상 확보했습니다. Edge에서 실제 PNG, 886.95픽셀 지도 폭, 1990→2020 Swipe와 역사 Time-Series의 순차 재생·T2 정지를 확인했습니다. 2020 RF의 71.42%는 Esri v003 약한 참조 일치도이며 독립 정확도는 미측정입니다. 1988·1990·2000·2010 단일 장면은 총 1,257,798,910바이트의 manifest·API·원본 SHA를 확인했습니다. MapBiomas는 1990~2024 반텐 주 발행 통계이며 픽셀 변화 발생시점과 LandTrendr·CCDC는 후속 단계입니다.”

추가 상세 근거: [반텐 Landsat 장기 분석 Explorer](../V42_LCLUC_LANDSAT_EXPLORER.md)

## LCLUC 후처리 및 품질관리 — 1분

“후처리 및 품질관리 Toolbox는 고정된 반텐 2020 Landsat RF 후보의 작은 고립 패치를 공간 필터로 보정하고 같은 근거로 전후를 비교합니다. 최소 4픽셀·4방향 실행에서 61,274픽셀, 129,889.72헥타르가 바뀌었습니다. 동일 공간 홀드아웃 72,391픽셀에서 Esri v003 약한 참조 일치도는 71.42%에서 75.36%로 변했습니다. Edge에서 전후 Swipe, 보정 위치·면적·품질·이력, 세 GeoTIFF SHA 다운로드와 재조회를 확인했습니다. 이 결과는 약 147미터 표시 격자의 검토 후보이며 독립 정확도는 `REFERENCE_REQUIRED`입니다. Temporal·Gap·Frequency·Incident는 계획 단계이고 계층 통합 계약은 합성 시험을 통과했습니다.”

추가 상세 근거: [LCLUC 후처리 및 품질관리](../V42_LCLUC_POSTPROCESS_QUALITY.md)

## 반텐 모델 시험과 특화 분류 계층 통합 — 1분

“반텐 2020 실자료에서 두 센서별로 RF, Tiny U-Net, 경량 DeepLabv3+를 같은 공간 표본에서 비교했습니다. Landsat 홀드아웃 72,391픽셀의 약한 참조 일치도는 71.42%, 66.34%, 67.76%이고 Sentinel-2 홀드아웃 76,230픽셀에서는 70.39%, 57.88%, 63.74%입니다. DeepLab 공간 필터 뒤 Landsat은 67.97%, Sentinel-2는 63.87%였습니다. Edge에서 여섯 분류 GeoTIFF와 후처리 실행을 확인했습니다. Siamese 변화 후보와 특화층 계층 계약도 별도 검증했습니다. 이 수치는 Esri 약한 참조 기반이며 독립 정확도와 운영 승인은 별도 Gate입니다.”

추가 상세 근거: [반텐 모델 시험과 특화 분류 계층 통합](../V42_LCLUC_MODEL_TRIALS_AND_SPECIALISTS.md)

## 반텐 원본별 면적과 공식 비교 기준 — 1분

“반텐 Esri 원본 9개 클래스와 MapBiomas 공식 발행 11개 클래스를 공통 연도 2020~2024에서 각각 표시합니다. Edge에서 2020과 2024를 선택했습니다. 2024 Esri 경계 격자 935,602.88헥타르는 유효 935,224.83헥타르와 구름 378.05헥타르로 구성되며 NoData는 0입니다. MapBiomas 발행 통계 합계는 935,005.55헥타르입니다. 두 제품의 클래스 차이와 토지전환 수치는 제시하지 않습니다. 공식 비교 기준은 Kemenhut 동년 Penutupan Lahan 23클래스이며 독립 정확도는 별도 조사 표본으로 평가합니다.”

추가 상세 근거: [반텐 원본별 면적과 공식 비교 기준](../V42_BANTEN_ESRI_MAPBIOMAS_AREA_COMPARISON.md)

## MapBiomas Indonesia GeoLLM 지식 검색 — 1분

“MapBiomas Indonesia 공식 자료 14건을 원문 SHA와 페이지로 고정했고 P0 핵심 9건을 포함해 286개 청크, 44개 용어, 25개 참조 지도, 5개 특화 범례 코드를 구조화했습니다. Edge에서 한글·영문 3질의를 검색해 PDF 원문 페이지와 공식 출처 링크를 확인했습니다. 검색 직전에 원본 SHA를 검사해 변경된 문서의 인용을 차단합니다. 현재는 생성 답변이 아닌 로컬 어휘 근거 검색이며 음성·embedding·공개 운영 색인은 후속 Gate입니다.”

추가 상세 근거: [MapBiomas Indonesia GeoLLM 지식 검색](../V42_MAPBIOMAS_GEOLLM_KNOWLEDGE.md)

## GeoLLM 반텐 토지피복 질의응답 — 1분

“GeoLLM 토지피복 질의응답은 한국어·인도네시아어·영어 질문을 공식 문서 검색과 고정 수치·공간 도구로 나눕니다. MapBiomas 방법론은 원문 페이지를 인용하고 면적과 전이는 Collection 4.1 XLSX의 SHA를 확인한 뒤 계산합니다. 2023→2024 산림 총전환은 3,146.85헥타르이고 산림 순변화는 마이너스 1,265.58헥타르로 서로 다른 지표입니다. Esri 수목→시가지 3,561.79헥타르는 실제 전이 PNG와 함께 검증했습니다. 기본 Dockerfile에 `libexpat1`을 포함해 새로 빌드한 이미지로 Compose와 Kubernetes에서 같은 소스·자료 pin, 다국어 RAG·GIS, JSON 10개와 지도 자산 해시 동일성을 확인했습니다. Kemenhut·중첩·독립 정확도·결과 등록은 차단 상태입니다.”

추가 상세 근거: [GeoLLM 반텐 토지피복 질의응답](../V42_LCLUC_GEOLLM_QUERY.md)

## 1분 설명 — 서자바 2025 Landsat 재수신

“같은 3장면을 공급자에서 별도로 다시 받았습니다. 원본 해시 24쌍이 일치했고 같은 30m 연구 창의 Random Forest 분류도와 신뢰도 해시도 재현했습니다. 동년 Esri 약한 참조 일치도는 시험창 50.34%, 검증창 27.83%였습니다. 독립 검증과 사람 승인 전까지 운영 배포는 차단됩니다.”
