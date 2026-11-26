# LCLUC 연차 자료 자동 처리

수집·이관 단계가 원본과 접수 명세를 게시하면 연차 워커가 지역·연도를 찾아 처리한다. 연도별 고정 목록을 수정할 필요가 없다. 기존 반텐 2020~2025 비교 데이터와 수집기, 지도 선택, 분석 탭은 기존 경로를 사용한다. 연차 워커의 결과는 현재 LCLUC의 **위성영상 수집현황 및 출처** 카드의 **연차 자동 처리** 행에서 볼 수 있다.

## 자료 접수

운영자 또는 수집·이관 시스템이 읽기 전용 intake에 다음 구조를 게시한다. 접수 명세 없는 임의 파일은 출처·연도·품질 밴드를 판정할 수 없으므로 접수되지 않는다. 각 파일은 임시 이름으로 완전히 기록한 뒤 최종 이름으로 교체한다. 새 장면, 학습자료 또는 경계가 필요하면 새 revision 디렉터리에 완성된 명세를 게시한다.

| 파일 | 계약 |
| --- | --- |
| `annual-lcluc/<지역>/<연도>/<revision>/bundle.json` | `lcluc-annual-input/1`. 지역 ID, 관측연도, 실자료/시험 구분, 분류체계와 SHA-256, WGS84 경계 GeoJSON 기하와 출처, 센서별 장면 목록, 동년 학습 래스터. 접수 파일 바이트의 SHA-256이 실행 ID다. |
| 원본 | Sentinel-2 L2A B02/B03/B04/B08/B11/B12와 SCL. Landsat 8/9 Collection 2 Level 2 SR_B2~SR_B7와 QA_PIXEL 및 확보 시 QA_RADSAT. 한 자산은 상대경로·바이트·SHA-256으로 고정한다. 장면마다 관측일, 방사 스케일·오프셋, 출처 ID, 제공 기관, URI, 버전, 이용 조건, 시간대 포함 취득 시각을 기록한다. |
| `training-approval.json` | `lcluc-annual-training/1`. 승인된 파일 게시 주체가 `input_sha256`, `approval_id`, `authority`를 제출한다. 실제 자료의 라벨·이용 권한 및 실험 목적 확인 책임은 승인 주체에 있다. |
| `verification.json` | `lcluc-annual-verification/1`. `input_sha256`와 동년 약한 참조 및/또는 독립 참조. 독립 평가에는 승인 ID·기관과 표본 설계·공간 독립성 검토 문서의 파일 pin이 필요하다. |

계약 모델은 [annual_inputs.py](../../services/lcluc/annual_inputs.py)에 있다. 시험 입고 패키지는 `python tests/lcluc/test_annual_pipeline.py <격리된-폴더>`로 만든다. 생성된 `staged` 아래 원본 1개, 후보 학습 승인, 검증 승인 파일을 해당 번들 폴더에 순서대로 넣으면 단계별 상태를 확인할 수 있다.

## 동작과 지표

1. 각 원본의 길이와 SHA-256, 관측연도, 자료형과 CRS를 확인한다. 경계를 30m EPSG:6933 등적 격자에 맞추고 256픽셀 창 단위로 반사도를 처리한다. Sentinel-2는 장면별 스케일·오프셋과 SCL 4·5·6, Landsat은 Collection 2 보정 계수와 QA_PIXEL 0~5번 불량 비트를 적용한다. QA_RADSAT을 지급받은 장면은 포화·가림을 추가로 제외한다. 날짜와 장면 ID 순서로 첫 유효 픽셀을 채택한다. 관측 계절 대표성은 별도 검토 대상이다. [Copernicus Sentinel-2 제품](https://sentiwiki.copernicus.eu/web/s2-products) · [USGS 반사도 보정](https://www.usgs.gov/faqs/how-do-i-use-a-scale-factor-landsat-level-2-science-products) · [USGS 품질 비트](https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands)
2. 센서별 경계 내 물리 피복률 95%와 맑은 픽셀 80%를 요구한다. 동년 학습 라벨과 명세에 묶인 승인이 도착하면 센서별 Random Forest를 학습한다. 클래스별 최소 4픽셀, 상한 5,000픽셀을 적용하며 학습에 들어간 클래스와 분류체계 SHA를 기록한다. NoData를 보존한 분류 TIFF, 보정 전 최대 클래스 확률 TIFF, 비실행형 NPZ와 각 SHA를 정제 Data Lake에 저장한다.
3. 동일 연도·공통 유효 픽셀에서 센서 간 지도 일치도를 계산한다. 동년 지도 참조가 있으면 두 센서 결과의 약한 참조 일치도도 각각 산출한다. 두 경우 모두 독립 정확도와 다른 지표다.
4. 독립 참조는 학습·약한 참조와 출처 ID·기관·래스터 해시가 달라야 한다. 독립 표본 래스터는 30m 분석 격자 그대로 제출한다. 분석 경계 안에서 학습 위치 및 인접 1셀을 제외하고, 센서별 최소 100개 유효 표본에서 혼동행렬·전체 정확도·F1·IoU를 계산한다. 지표는 입고한 표본에 대한 값이다. 모집단 대표성·기관 공개 판단은 별도 승인에 따른다. 합성 결과는 `synthetic_holdout`에만 기록한다.

QA와 후보 산출물, 검증 증거를 실행 ID별로 저장한다. 파일이나 승인으로 인한 대기 상태는 자동으로 다시 확인한다. 같은 실행에 독립 참조가 추가되어도 후보 모델은 재학습하지 않는다. 승인 교체·파일 누락·해시 불일치는 상태와 원인으로 확인한다. 이 경로는 기관 공개나 운영 모델 활성화를 실행하지 않는다. [별도 학습·배포 기준](../mlops/TRAINING_ACCURACY_DEPLOYMENT_GATES.md)

## 운영과 조회

- Docker는 `docker compose -f deploy/compose.yaml --profile annual up -d annual-worker`로 연차 워커를 실행한다. 이미지가 아직 없으면 `docker compose -f deploy/compose.yaml build api`로 만든다. `SDSS_ANNUAL_RAW_DIR`는 `annual-lcluc/` 상위 디렉터리다. 미설정 시 기존 raw 경로를 읽는다. `SDSS_CURATED_DIR`는 API와 워커가 공유한다.
- Kubernetes는 `deploy/kubernetes/annual-worker.yaml`을 사용한다. 운영자가 준비한 `sdss-annual-input` PVC를 읽기 전용으로, API와 공유하는 `sdss-curated` PVC를 쓰기 가능으로 마운트한다. 단일 Deployment 워커가 OS 잠금으로 중복 처리와 비정상 종료 후 재개를 지원한다. 이 구성에서는 파일 잠금과 원자 교체를 제공하는 스토리지가 필요하다. 승인 파일을 게시하는 경로는 기관별 ACL로 보호한다.
- `SDSS_ANNUAL_POLL_SECONDS` 기본값은 60초다. `SDSS_ANNUAL_ALLOW_SYNTHETIC=1`은 격리된 검증 환경에만 설정한다. 운영 기본값은 합성 접수를 차단한다.
- `GET /api/lcluc/annual-runs?region=banten`은 진행 상태·지표 요약과 마지막 워커 완료 검사 시각을 제공한다. `GET /api/lcluc/annual-runs/{run_id}`로 모델·검증 승인·원본 출처·해시·혼동행렬과 분류·확률 GeoTIFF 링크를 함께 조회한다. 기존 같은 출처·loopback API를 사용한다.

## 2026-11-26 검증

| 범위 | 확인한 결과 | 로컬 증거 |
| --- | --- | --- |
| Docker Compose 5180 | 원본 1개를 나중에 전달해 처리 재개, 승인 도착 후 두 모델 학습·추론, 독립자료 도착 후 합성 홀드아웃 보고. 두 센서 분류·확률 TIFF 네 개의 SHA-256 대조. Edge에서 연차 행과 증거 링크, 기존 2020 Sentinel-2 지도 조회. | `artifacts/deploy/annual-docker-e2e.log`, `annual-docker-browser-final.log`, `annual-docker-browser.png` |
| 로컬 kind Kubernetes 5181 | 별도 입고 PVC에서 같은 시험 단계를 실행했다. 기존 React API와 연차 워커가 공유 정제 PVC를 읽고 쓰며, Edge에서 연차 행·증거 링크·기존 지도를 조회했다. | `artifacts/deploy/annual-kube-start.log`, `annual-kube-e2e.log`, `annual-kubernetes-browser.png` |
| Python 회귀시험 | 45건 통과, 1건 건너뜀. 원본 지연 입고, 2021년 참조의 2026년 검증 차단, 독립 표본 겹침 차단, 합성 입력이 기본 차단되는 경우를 포함한다. | `artifacts/deploy/annual-regression.log` |

두 환경에서 워커 재시작 후 마지막 검사 시각이 갱신됐고, 저장된 후보 모델과 완료 상태는 동일했다. 증거는 `artifacts/deploy/annual-docker-restart.log`와 `annual-kube-restart.log`다. 기존 실자료 지도 조회를 확인했고, 학습 및 독립 평가 검증에는 합성 시험자료를 사용했다. 실제 원본과 승인된 동년 라벨·독립 기준자료가 운영 접수되면 실자료 워커가 처리한다.
