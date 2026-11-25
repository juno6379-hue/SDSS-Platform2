# SDSS-Platform2 운영 경로와 인수 기준

기존 React 화면에서 기관 작업과 지도를 열고, 고정된 공통 결과 ID로 돌아온다. 원본·데이터셋·모델·작업·결과의 증거는 생성 주체와 SHA-256으로 연결한다. 실제 운영 승인은 별도 기록하며 개발 환경의 검증 결과를 생산 권한으로 승격하지 않는다.

## 1~8번 담당과 완료 기준

| 번호 | 담당 | 사용자 경로와 상태 |
|---|---|---|
| 1 | root · web_ui · understanding_agent | 기존 React의 리포트 & RDTR에서 동일 ID 지표·지도·출처·보고서·불확실성과 두 승인축 조회. 실자료 2건을 Edge로 확인했고 `c4a3954`를 푸시했다. |
| 2 | jobs_provider | 기관 승인 작업을 제출하고 진행이나 취소를 조회한다. 고정 기관과 버전, 중복 요청, worker 재개, 결과 ID 등록을 시험한다. 기관 자격증명과 실제 승인 원본은 별도다. |
| 3 | web_ui · root | 기존 작업·알림, 데이터 카탈로그, 모델 & MLOps 메뉴에서 각각 API를 호출하고 작업 결과의 등록 ID를 리포트 & RDTR로 연결한다. |
| 4 | data_pipeline | BIG/RTRW와 Sentinel-2 인벤토리에서 과거 표본·현행성과 실제 관측·품질·미정산을 구분한다. 현행 RTRW는 0/6주이며 보존된 미정산 예약이 있다. |
| 5 | data_pipeline | CCKP 원본을 SHA와 기간으로 고정한다. 현재 공개된 로컬 검증 단위는 CDD 기후 평균 표본이다. 전체 변수·기간 인벤토리는 별도다. |
| 6 | data_pipeline | KLHK 연차 원본·분류 사전·권리와 보고서 색인을 구분한다. 고정 검토 색인 7문서·122청크의 공개 검색 및 운영 임베딩은 대기한다. |
| 7 | root | 승인된 ONNX 버전을 선택하는 실제 추론 실행과 버전 승격·롤백 이력을 연결한다. 합성 2버전에서 입력 10의 출력이 11→12→11로 바뀌었다. 실자료 학습 승인은 대기한다. |
| 8 | production_lake · root | 기관별 PostgreSQL/PostGIS·pgvector, 객체 저장소와 파일 접근, 이관·계보 및 시작·복구 절차를 제공한다. 실제 기관 소유 인프라와 인수시험은 별도다. |

## 모델 버전 실행과 롤백

`GET /api/model-releases`는 모델별 고정 버전과 현재 실행 적격, 활성 revision, 이력을 반환한다. `POST /api/model-releases`는 권한이 있는 운영자가 준비한 모델 매니페스트 핀을 등록한다. `POST /api/model-releases/{name}/activate`와 `/rollback`은 별도 승인 증거와 예상 revision을 요구한다. 운영자 인증은 `SDSS_MODEL_RELEASE_TOKEN`과 `SDSS_MODEL_RELEASE_AUTHORITY` 두 서버 설정에 연결한다.

실행 시 `ModelReleases.run_onnx`가 활성 버전의 SHA, 학습·독립 정확도 근거, 공통 결과 카탈로그의 과학 승인, 보안·롤백 시험을 다시 검사한다. ONNX CPU 추론에 사용한 모델, revision, 원본 데이터셋 SHA와 공통 결과 ID를 실행 추적에 반환한다. 모델의 과학 승인이 철회되면 이후 실행이 차단된다. 기관 공개는 결과 카탈로그의 별개 승인축이다.

격리한 실제 자료의 후보에는 이전 1,779행 중 1,751행과 품질 적격 1,382행이 있다. 동일 `scene_id`가 validation과 test에 걸친 28행을 보존 원본에서 제외하여 새 후보로 만들었다. 학습·독립 평가에 앞서 공간 중첩과 동년 독립 라벨, 주·연도 피복을 계속 검증한다. [고정 후보 보고서](../../evidence/models/scene-quarantine-candidate-20261125.json)

## 기관 저장소의 조회와 파일 링크

`GET /api/storage/status`는 기관 설정 유무만 반환한다. `GET /api/storage/health`는 권한이 있을 때 DB와 버킷을 확인한다. `GET /api/lineage/{kind}/{key}`는 고정 검사 증거와 상류 노드의 종류·키·SHA를 조회한다. `/assets/{purpose}`는 기관에 결속된 객체를 검증하고 300초 링크를 만든다.

승인 요청의 `dataset_manifest`에 프로젝트 상대 경로·크기·SHA를 고정하면 `python -m services.api.lineage_projection --result-id ID`가 작업 영수증과 결과 패키지를 대조하고 데이터·모델→작업→결과 계보를 한 트랜잭션에 기록한다. 객체 이관은 파일별 권리 확인을 거친다.

기관은 서버가 설정한 `SDSS_STORAGE_INSTITUTION`과 별도의 `SDSS_STORAGE_READ_TOKEN`으로 맵핑한다. 브라우저 요청에서 기관 값을 받지 않으며 DB 정책도 기관 범위를 적용한다. 현재 승인된 운영 DSN과 버킷 연결 전까지 개발 SQLite가 결과 원장이다. [저장소 권한과 이관](PRODUCTION_STORAGE.md)

독립 개발 S3에서 CCKP 검산 파일 3,295바이트를 저장하고 다른 버킷으로 복원해 원본 SHA를 확인했다. 45초 링크 만료와 익명 접근은 403을 반환했다. PostgreSQL 로컬 접속은 시간 초과로 RLS와 `pg_restore` 실증이 대기한다.

## 로컬 배포 재현

`deploy/compose.yaml`의 API와 React 컨테이너가 네트워크 네임스페이스를 공유한다. FastAPI는 컨테이너 내부 loopback에만 연결하고 React 프록시가 호스트 loopback 5180을 제공한다. 컨테이너는 UID 10001, 읽기 전용 루트 파일시스템, 권한 상승 금지를 사용한다. 기존 GeoAI API 8002가 필요한 기능은 Windows의 Vite 실행에서도 계속 쓸 수 있다. 플랫폼 단독 컨테이너에는 레거시 서비스를 포함하지 않았다.

```powershell
docker compose -f deploy/compose.yaml config --quiet
docker compose -f deploy/compose.yaml up -d --build api web
docker compose -f deploy/compose.yaml exec api python -m services.api.result_catalog --seed-verified --source cckp-cdd-1951-1980
```

기관 작업자가 고정 승인과 시크릿을 구성한 경우에만 worker 프로필을 활성화한다. `SDSS_JOBS_CONFIG_CONTAINER`에 읽기 전용 증거 볼륨에 있는 승인 목록의 컨테이너 경로를 준다. API 권한과 worker 공급자 자격정보는 각 컨테이너의 로컬 env 파일 또는 기관의 시크릿 전달체계에서 구성한다. 운영 DB와 버킷에는 운영 환경에서 승인한 연결만 사용한다.

`deploy/kubernetes/local-validation.yaml`은 같은 Pod에서 API와 React를 구동한다. 외부 공개 서비스와 자동 실행은 포함하지 않으며 worker 기본 replicas는 0이다. 기관 검증용 네임스페이스에서 읽기 전용 증거 PVC를 준비하고, 검증한 컨테이너 태그를 고정한 뒤 포트포워드로 인수시험한다. 실제 클러스터 인수에는 기관 계정·네트워크·시크릿·복구 시점이 필요하다.

관련 문서 [결과 카탈로그](COMMON_RESULT_PATH.md), [기관 원천](../data/INSTITUTION_SOURCE_HANDOFF.md), [학습 및 배포 Gate](../mlops/TRAINING_ACCURACY_DEPLOYMENT_GATES.md).
