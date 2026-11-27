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

## Docker와 Kubernetes

GeoLLM은 기존 FastAPI와 React 이미지에서 동작하는 읽기 전용 질의 경로다. Nginx는 화면과 같은 출처의 `/api/lcluc/geollm/query`, 경계·전이 이미지 및 RAG API를 내부 `127.0.0.1:8014`로 전달한다. Docker Compose는 API와 Web에 같은 네트워크를, Kubernetes는 같은 Pod를 사용한다. 질의 처리는 별도 학습·수집 워커를 호출하지 않는다.

| 환경 | Data Lake 연결 |
| --- | --- |
| Docker Compose | `deploy/compose.yaml`의 API가 `SDSS_RAW_DIR` 또는 저장소의 `data/raw`를 `/srv/sdss/data/raw`에 읽기 전용으로 마운트한다. 정제 자료는 `/srv/sdss/data/curated`, 경계 증거는 `/srv/sdss/evidence`에서 읽는다. |
| Kubernetes 로컬 검증 | `deploy/kubernetes/local-validation.yaml`의 API에 사전 준비한 `sdss-raw` PVC를 읽기 전용으로 마운트한다. 기존 `sdss-curated`와 `sdss-evidence` PVC를 연결한다. 접근은 기존 포트포워드와 loopback 읽기 경로를 사용한다. |

배포 전에 MapBiomas 원본 XLSX와 문서, Esri 원본 COG, 경계 증거 및 고정한 반텐 파생 집계 파일을 해당 볼륨에 배치한다. 이미지와 Git 저장소에는 이 원본들이 포함되지 않는다. 실자료를 연결하지 못하거나 해시가 다르면 질의가 보류된다.

이번 GeoLLM 변경의 Compose 렌더링과 Kubernetes 매니페스트의 마운트·Pod 연결을 확인했다. 최신 이미지의 컨테이너 통합시험은 Docker Linux 엔진과 Kubernetes 컨텍스트가 가용한 환경에서 수행한다. 기존 Edge 검증은 로컬 React 5175와 FastAPI 8014를 사용했다.

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
