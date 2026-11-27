# GeoLLM 반텐 토지피복 질의응답

기존 React **GeoLLM Assistant → GeoLLM 토지피복 질의응답**에서 한국어·인도네시아어·영어로 조회한다. `POST /api/lcluc/geollm/query`는 `{"question":"…"}`를 받는다. 정책·방법론·정의 질의는 MapBiomas 원문 색인에서 문서명·버전·페이지·인용 링크를 반환한다. 경계·면적·변화를 묻는 정량 질의는 지역·기간·제품·클래스로 구조화해 제품별 통계 도구에서만 답한다. 범위가 임의인 질문은 정형 도구의 입력으로 변환하거나 필요한 입력을 표시한다. 기존 MapBiomas RAG 전용 API도 정량 요청을 받으면 `NUMERIC_TOOL_REQUIRED`를 반환한다.

| 도구 | 읽는 근거와 지원 범위 |
| --- | --- |
| MapBiomas 면적·산림 순변화 | Collection 4.1 `COVERAGE`의 반텐 발행 1990~2024년 11개 클래스. 순변화는 종료 연도 면적에서 시작 연도 면적을 뺀 값이다. |
| MapBiomas 두 시점 전이·산림 총전환 | 공식 XLSX `TRANSITION`의 반텐 레코드 113행, 발행 기간 열 50개. 지정한 열의 출발·도착 클래스 면적을 사용한다. 반텐에 값이 없는 시기 또는 조합은 조회를 보류한다. 산림 총전환은 제품의 산림 범주에서 비산림으로 간 발행 레코드를 합산하고 산림 출발 면적을 `COVERAGE`와 대조한다. |
| Esri 면적·전이 | 2020~2025년 Esri v003 48M COG의 SHA-256과 반텐 등적 격자 집계를 검증한다. 동일 해 면적과 두 해 공통 유효 픽셀의 전이를 조회한다. Esri `Trees`로 질의할 수 있으며, 산림 감소에는 그 목적에 맞는 산림 분류가 필요하다. |
| 산림부 공식 자료·중첩 | 반텐의 동년 산림부 연차 자료나 중첩 대상 레이어의 승인된 원본이 없으면 결과 수치를 반환하지 않는다. 제품·버전이 모호하거나 달라도 조회를 보류한다. |

MapBiomas XLSX의 지역 범위는 발행자 기준이다. 그 결과 화면의 One Map/BIG 반텐 경계는 위치 참고용이며 MapBiomas의 집계 경계는 XLSX에 수록되지 않는다. Esri에는 실자료에서 파생한 연차 분류 또는 선택 클래스의 전이 PNG를 표시한다. 이 이미지는 표시 격자이며 Esri 면적의 계산 근거는 별도의 10m 등적 집계다. 결과에는 수치·단위·연도·제품 버전·클래스 코드·출처 및 SHA-256과 제한사항이 포함된다. 현재 질의는 읽기 전용이며 해당 조회를 별도로 등록한 결과 ID는 없다. 제품 내 지도 값의 대조는 독립 정확도 평가와 별개다. [MapBiomas 공식 통계](https://landy.mapbiomas.id/en/statistics) · [MapBiomas 4.1 분류 정의](https://landy.mapbiomas.id/assets/files/Col%204.1%20-%20Legend%20Description%20EN.pdf) · [산림부 공식 자료사전](https://sigap.kehutanan.go.id/tema-kamus/575)

## 재현

원본 XLSX와 정확한 `COVERAGE`·`TRANSITION` 파생 산출물을 Data Lake에 연결한다. `.[lcluc-import]` 의존성을 갖춘 환경에서 보존한 원본으로 산출물을 만들 수 있다.

```powershell
py -3.11 -m services.lcluc.banten_historical_trend data/raw/explorer/banten/mapbiomas/4.1/statistics_lulc_indonesia.xlsx --acquired-on 2026-11-26 --include-transitions
```

공식 XLSX 및 파생 결과의 해시가 플랫폼에 고정한 값과 일치할 때 정량 응답을 제공한다. 파일을 변경하거나 새 판을 받을 경우 별도의 자료 검증과 버전 등록이 필요하다.

## STEP 03 반텐 GeoLLM Staging 릴리스

`SDSS_GEOLLM_LAKE_RELEASE=banten-geollm-20261127-v1`을 설정하면 기존 GeoLLM 화면과 LANDY 문서 API가 Staging 릴리스를 읽는다. 설정 없는 기존 환경은 로컬 검증 경로를 사용한다. 릴리스 설정이 있는 환경에서 자료나 저장소 검증이 실패하면 결과를 보류한다.

| 경로 | 읽는 자료와 책임 |
| --- | --- |
| PostgreSQL/PostGIS | 기관 RLS가 적용된 고정 릴리스의 MapBiomas 4.1 발행 `COVERAGE`·`TRANSITION`, Esri v003 반텐 10m 검증 집계와 PostGIS SRID 4326 반텐 위치 경계. 정량 계산 규칙과 제품별 정답 범위는 위의 도구 표를 따른다. |
| SeaweedFS | 비공개 버킷의 SHA-256 주소 객체. 원본 XLSX와 COG, 파생 검증 통계, Esri 6개년 미리보기·정합 TIFF, 경계 스냅샷, LANDY 원문·색인, 임베딩 모델과 토크나이저를 보존한다. Esri 전이는 두 해의 고정 TIFF에서 기존 미리보기 알고리즘으로 생성한다. |
| pgvector | LANDY 문서 14건의 본문 286개를 E5-base ONNX로 임베딩한다. 동일 모델로 질의 벡터를 생성하고 768차원 코사인 검색을 수행한다. 결과는 원문의 페이지·버전·SHA-256을 인용한다. |
| 기존 화면 | 같은 출처의 API에서 결과와 지도 파일을 조회한다. MapBiomas는 One Map/BIG 위치 경계를 제공하며, Esri는 연차 분류 또는 전이 지도를 제공한다. |

모델은 `intfloat/multilingual-e5-base`의 고정 리비전 `d128750597153bb5987e10b1c3493a34e5a4502a` CPU INT8 ONNX다. 모델·토크나이저를 배포자 SHA-256으로 검증한다. 문서에는 `passage: `, 질의에는 `query: `를 적용한 뒤 attention-mask 평균과 L2 정규화로 768차원 벡터를 얻는다. [모델 카드](https://huggingface.co/intfloat/multilingual-e5-base/tree/d128750597153bb5987e10b1c3493a34e5a4502a)

신규 릴리스 발행 환경은 Python `.[geo,storage,inference]` 의존성을 사용한다. 프로젝트 원본·정제·증거 폴더를 읽기 전용으로 묶은 Staging 일회 실행에서 다음 명령을 사용한다. 원본과 파생물 일치 및 객체 읽기 해시 확인 이후 4개 데이터셋·47개 파일 바인딩·문서 벡터를 하나의 PostgreSQL 트랜잭션에서 등록한다. `--staging`은 이 릴리스의 기관과 버킷을 확인한 후 이관한다.

```powershell
python -m services.lcluc.geollm_migrate --staging --model-dir data/raw/knowledge/models/multilingual-e5-base-d128750
```

Compose 5280과 로컬 kind 5281은 동일한 릴리스를 사용한다. API의 `/tmp`는 원격 다운로드를 검증한 후 사용하는 임시 캐시다. Staging API는 시작할 때 두 임베딩 파일을 내려받아 해시를 검증하고 세션을 준비한 뒤 HTTP를 수신한다. Compose 시작 유예는 180초다. kind의 API Pod에는 원본·정제·증거 볼륨이 없으며 1GiB 임시 공간만 연결한다. Staging API 이미지 `sdss-platform2-api:geollm-step03-r3`는 이전에 검증한 런타임에 토크나이저와 STEP 03 서비스 파일을 포함한다. 검증 근거는 실행 호스트의 `artifacts/deploy/geollm-step03/`에 있다.

2026-11-27 Staging 검증은 `VERIFIED_REAL`이다. Docker와 kind의 Edge에서 한국어·인도네시아어·영어 문서 인용과 정량 결과의 수치·단위·지도·출처·제품 버전을 확인했다. 양쪽 API 응답 13건(문서 3, 정량 8, 보류 2)과 대응 지도 자산의 SHA-256이 일치했다. 동등한 세 언어의 2024년 반텐 논 면적은 195,653.67ha였다. MapBiomas·Esri 수치와 제품 버전을 이전에 저장한 검증 기록과 대조했고 Esri 전이·배경 PNG는 기존 해시와도 일치했다. SQL 재조회에서 실제 벡터 286개가 모두 768차원이며 반텐 경계가 SRID 4326에서 유효함을 확인했다. 객체 바인딩 47개는 총 1,143,310,094바이트다.

호스트 기록은 `migration.log`, `sql-readback.log`, `kind-remote-source.log`, `edge-5280-final.log`, `edge-5281-final.log`, `cross-environment-results.json`이다. 검증 범위는 반텐의 지정 자료와 로컬 Staging이다.

## STEP 04 GeoLLM 저장소 모드

GeoLLM이 질문에서 지역·연도·클래스·제품을 판별하고, 앱 시작 시 정한 저장소 어댑터로 자료를 읽는다. GIS 수치 계산, 출처 필드와 제품 버전은 두 모드에서 같은 계약을 따른다. 기존 GeoLLM 화면의 GIS·RAG 제출, LANDY 목록 및 검색 API에도 같은 선택이 적용된다.

| `SDSS_GEOLLM_STORAGE_MODE` | 동작 |
| --- | --- |
| `local` | 개발 환경의 고정 원본·정제 파일과 기존 지도 API를 사용한다. LANDY 검색은 로컬 어휘 색인을 사용한다. |
| `lake` | `SDSS_GEOLLM_LAKE_RELEASE`의 발행 통계·PostGIS 경계, SeaweedFS 지도와 근거 파일, 같은 릴리스의 pgvector와 E5로 조회한다. 구성과 연결에 실패하면 해당 요청을 차단한다. |
| 미설정 | 기존 개발 배포의 호환 동작이다. 릴리스 변수가 없으면 `local`, 릴리스 변수가 존재하면 `lake`를 선택한다. 운영 배포에는 `lake`를 명시한다. |

GIS의 성공 응답은 기존 수치·단위·출처·제품 버전과 Data Lake 릴리스 식별자를 반환한다. 오류 메시지에는 접속 문자열 및 비밀값을 포함하지 않는다.

| 상황 | 질의 API 및 기존 화면 |
| --- | --- |
| 모드 오타 또는 필수 접속값 누락 | `BLOCKED`와 `GEOLLM_STORAGE_MODE_INVALID` 또는 `GEOLLM_STORAGE_CONFIG_REQUIRED` |
| PostgreSQL, pgvector, SeaweedFS 또는 요청한 릴리스 자료 접근 실패 | `BLOCKED`와 `GEOLLM_STORAGE_UNAVAILABLE`. 수치·출처·인용·지도 주소를 비운다. GeoLLM의 지도 파일·경계 자체 요청은 HTTP 503으로 응답한다. |
| 시작 직후 E5 초기화 중 | 문서 조회를 잠시 `GEOLLM_STORAGE_INITIALIZING`으로 표시한다. HTTP와 GIS 시작은 문서 모델을 기다리지 않는다. |

`lake`는 임시 캐시를 재사용할 때에도 지도·모델 객체의 SeaweedFS 바인딩을 확인한다. 저장소 오류를 로컬 파일 조회로 대체하지 않는다. GIS와 지도는 다음 요청에서 같은 릴리스를 다시 읽는다. 문서 모델 준비가 실패한 경우 다음 문서 요청이 같은 릴리스에서 백그라운드 재시도를 시작한다. 준비 중 요청은 상태를 그대로 표시한다. 기존 제품의 자료 미확보, 기간 및 분류 제한은 동일하게 적용한다.

2026-11-27 STEP 04 1차 실자료 시험에서 Compose 5280과 kind 5281의 한국어·인도네시아어·영어 화면을 확인했다. 두 환경의 API 13건과 조회한 경계·Esri 이미지의 해시가 일치했다. MapBiomas Collection 4.1의 2024년 반텐 논 면적은 세 언어 모두 195,653.67ha였다. Compose 별도 인스턴스에서는 동일한 로컬 원본을 읽기 전용으로 유지하며 `local` 정상 조회와 `lake` DB·S3 장애를 각각 시험했다. 장애마다 세 언어의 GIS 3건과 문서 3건이 차단됐고, 경계는 HTTP 503을 반환했다. [교차 검증](../../artifacts/deploy/geollm-step04/api-compare-warm.log) · [DB 장애](../../artifacts/deploy/geollm-step04/db-outage.log) · [S3 장애](../../artifacts/deploy/geollm-step04/s3-outage.log)

Docker Desktop의 E: 호스트 마운트가 실패해 정상 Staging의 GeoLLM은 애플리케이션의 로컬 원본 볼륨 없이 검증했다. 로컬·장애 비교에는 C:의 격리 복사본을 사용했다. 첫 kind 문서 시험 중 모델 다운로드가 게이트웨이 제한을 넘겼다. 어댑터에 원격 모델 초기화 실패 후 단일 백그라운드 재시도를 추가했다.

최종 API 이미지 `sdss-platform2-api:geollm-step04-r2`의 실자료 API 13건과 경계·지도 해시는 Compose 5280 및 kind 5281에서 일치했다. 양쪽 Edge에서 세 언어의 문서 인용과 GIS 7건의 수치·출처·버전·지도를 재검증했다. 로컬 모드 6건과 PostgreSQL·SeaweedFS 장애별 6건도 최종 이미지에서 확인했다. 어댑터 구성·재시도·기관 계보의 회귀시험은 18개를 통과했다. [최종 API 비교](../../artifacts/deploy/geollm-step04/api-compare-r2.log) · [Compose 화면](../../artifacts/deploy/geollm-step04/edge-5280-r2.log) · [kind 화면](../../artifacts/deploy/geollm-step04/edge-5281-r2.log) · [로컬](../../artifacts/deploy/geollm-step04/local-r2.log) · [DB 장애](../../artifacts/deploy/geollm-step04/db-outage-r2.log) · [S3 장애](../../artifacts/deploy/geollm-step04/s3-outage-r2.log)

## 운영 Data Lake 전환 상태

2026-11-27 사전 점검 당시 개발 Compose 5180과 로컬 Kubernetes 5181은 `PROJECT_STORAGE_AUTHORITY_NOT_CONFIGURED`였고 문서 질의는 `local_lexical_evidence`였다. [사전 점검 기록](../../artifacts/deploy/geollm-operational-preflight/cross-environment-results.json)

운영 배포에는 읽기 전용 데이터베이스 접속 정보, 기관 범위, 객체 저장소와 승인된 GeoLLM 릴리스가 필요하다. BIG 운영 연결과 운영 자료의 기관 검증은 `BLOCKED`다. 격리 Staging에서 사용할 값은 저장소 문서를 따른다. [접속 정보와 검증 범위](../architecture/PRODUCTION_STORAGE.md#2026-11-27-step-02-staging-접속-설정)

## Docker와 Kubernetes

GeoLLM은 기존 FastAPI와 React 이미지에서 동작하는 읽기 전용 질의 경로다. Nginx는 화면과 같은 출처의 `/api/lcluc/geollm/query`, 경계·전이 이미지 및 RAG API를 내부 `127.0.0.1:8014`로 전달한다. Docker Compose는 API와 Web에 같은 네트워크를, Kubernetes는 같은 Pod를 사용한다. 질의 처리는 별도 학습·수집 워커를 호출하지 않는다.

| 환경 | Data Lake 연결 |
| --- | --- |
| Docker Compose | `deploy/compose.yaml`의 API가 `SDSS_RAW_DIR` 또는 저장소의 `data/raw`를 `/srv/sdss/data/raw`에 읽기 전용으로 마운트한다. 정제 자료는 `/srv/sdss/data/curated`, 경계 증거는 `/srv/sdss/evidence`에서 읽는다. |
| Kubernetes 로컬 검증 | `deploy/kubernetes/local-validation.yaml`의 API에 사전 준비한 `sdss-raw` PVC를 읽기 전용으로 마운트한다. 기존 `sdss-curated`와 `sdss-evidence` PVC를 연결한다. 접근은 기존 포트포워드와 loopback 읽기 경로를 사용한다. |

배포 전에 MapBiomas 원본 XLSX와 문서, Esri 원본 COG, 경계 증거 및 고정한 반텐 파생 집계 파일을 해당 볼륨에 배치한다. 이미지와 Git 저장소에는 이 원본들이 포함되지 않는다. 실자료를 연결하지 못하거나 해시가 다르면 질의가 보류된다.

### 기본 이미지 재검증

기본 API `Dockerfile`에서 Debian `libexpat1`을 설치한다. `python:3.12-slim`에서 Rasterio가 사용하는 `libexpat.so.1`이 기본 빌드에 포함된다. API 시작 명령과 React 빌드 정의는 기존과 같다.

```powershell
docker build -t sdss-platform2-api:local .
docker build -f deploy/frontend/Dockerfile -t sdss-platform2-web:local .
```

Compose에는 이 API·Web 이미지를 연결하고, kind에서는 같은 이미지를 노드에 로드한 뒤 검증 Deployment에 지정한다. Data Lake는 기존 읽기 전용 원본·증거와 쓰기 가능한 검증용 정제 볼륨을 사용한다. Kubernetes에서는 원본·증거·정제 PVC 세 개를 연결한다.

2026-11-27 `b471bb3` 소스에 이 Dockerfile 변경만 더해 기본 API와 Web 이미지를 빌드했다. API 이미지 OCI 인덱스는 `sha256:f3607f88d4eb8f23ef231bbf58c3500084d07e0b361785c969f99f2164c3a756`이다. 두 컨테이너에서 Rasterio 1.5.2와 `libexpat.so.1` 로딩을 확인했다. Kubernetes API·Web은 같은 Pod에서 2/2 Ready였고 세 PVC는 모두 Bound였다.

두 Data Lake에서 MapBiomas 공식 XLSX, MapBiomas 전이 JSON, Esri 면적·변화 JSON의 SHA-256이 각각 일치했다. Edge에서 한국어·인도네시아어·영어 문서 인용과 아래 다섯 GIS 결과의 수치·단위·지도·출처·버전·SHA-256을 다시 확인했다. 양 환경에서 10건의 API 응답과 해당 지도 자산 해시가 일치했다. 산림부 원본·MapBiomas 구버전 미확보 및 RAG 정량 차단도 다시 확인했다. 화면 접속은 Compose `127.0.0.1:5180/#/view/7`과 로컬 kind 포트포워드 `127.0.0.1:5181/#/view/7`을 사용했다.

실행 호스트의 증거 폴더는 `artifacts/deploy/geollm-default-build/`이다. `docker-api-build.log`, `compose-edge.log`, `kube-edge.log`, `compose-data-lake.log`, `kube-data-lake.log`와 `cross-environment-results.json`을 보관했다. 교차 검증 JSON의 SHA-256은 `7b507fb25b61c70ce8b341182de556cebb7ab6b7be8f68ba1d6d13d555e292b8`이다.

### 이전 검증 기록 · `b471bb3`

2026-11-27에 커밋에서 직접 추출한 소스로 API와 React 이미지를 빌드했다. 원래 API 이미지는 두 환경 모두 `libexpat.so.1` 누락으로 Rasterio import 단계에서 종료됐다. 원래 이미지를 기반으로 Debian `libexpat1`만 추가한 `sdss-platform2-api:b471bb3-expat`를 사용했다. 실행된 API 소스의 SHA-256을 커밋 추출본과 대조했다. [Compose 시작 오류](../../artifacts/deploy/geollm-b471bb3/compose-api-original-error.log) · [Kubernetes 시작 오류](../../artifacts/deploy/geollm-b471bb3/kube-api-original-error.log) · [런타임 보완 빌드](../../artifacts/deploy/geollm-b471bb3/api-runtime-addon.log)

Compose의 격리 프로젝트와 kind의 `sdss-geollm-b471bb3` 네임스페이스에서 원본과 증거를 읽기 전용으로 마운트했다. 정제 볼륨은 검증용 복사본을 사용하고 공식 XLSX와 정제 전이 JSON의 SHA-256을 두 환경에서 확인했다. Esri 전이 미리보기를 재현하려면 두 연도의 정제 분류 래스터와 연차 지도 인덱스, 기준 표시 격자로 쓰는 `esri-2020.png`가 필요하다. [Compose 파일 검증](../../artifacts/deploy/geollm-b471bb3/compose-pins.log) · [Kubernetes 파일 검증](../../artifacts/deploy/geollm-b471bb3/kube-pins.log)

Docker Desktop 재시작 후 Compose `127.0.0.1:5180`과 kind 포트포워드 `127.0.0.1:5181`에서 기존 React 화면을 열었다. Edge에서 한국어·인도네시아어·영어 문서 인용, 아래 다섯 GIS 결과의 수치·지도·출처·버전·SHA-256을 각각 확인했다. 미보유 산림부 자료와 지원하지 않는 판은 수치가 보류됐고, RAG 전용 경로의 정량 질의도 차단됐다. 환경 간 JSON 응답 10개와 해당 지도 자산의 SHA-256이 일치했다. [Compose 브라우저 로그](../../artifacts/deploy/geollm-b471bb3/compose-geollm-edge-final.log) · [Kubernetes 브라우저 로그](../../artifacts/deploy/geollm-b471bb3/kube-geollm-edge.log) · [응답·지도 대조](../../artifacts/deploy/geollm-b471bb3/cross-environment-results.json)

## 실제 확인 질의

| 질문 | 확인한 결과 |
| --- | --- |
| `MapBiomas ATBD의 Gap Fill 방법은?` | RAG 문서 출처. 인도네시아어와 영어로 같은 방법을 물어도 원문 인용을 확인했다. |
| `Berapa luas sawah di Banten pada 2024 menurut MapBiomas?` | 195,653.67ha. `COVERAGE`, Collection 4.1, 반텐 경계 참고지도. |
| `MapBiomas 반텐 2023년부터 2024년까지 산림 감소량은?` | 3,146.85ha. `TRANSITION`에서 산림→비산림 총전환. |
| `MapBiomas 반텐 2023년부터 2024년까지 산림 순감소는?` | −1,265.58ha. `COVERAGE`에서 두 연도 면적 차. |
| `Show MapBiomas forest-to-urban transitions in Banten from 2023 to 2024` | 102.63ha. `TRANSITION`, Collection 4.1, 반텐 경계 참고지도. |
| `How much did Esri trees change to built-up in Banten from 2023 to 2024?` | 3,561.79ha. Esri v003, 실제 수목→시가지 전이 이미지. |

2026-11-27 로컬 Edge에서 질의·결과·지도·출처·버전·SHA를 검증했다. [Edge 검증 기록](../../artifacts/lcluc/geollm-edge.log)
