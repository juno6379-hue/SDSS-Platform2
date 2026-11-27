# 기관 저장소와 계보 운영 계약

## 서비스 범위

기관 결과의 원본 SHA-256, 선택한 지도·보고서 객체와 결과 ID를 PostgreSQL과 S3 연결로 보존한다. 기존 SQLite 결과 카탈로그를 읽기 전용으로 검증한다. 시험 중인 이관 경로는 기존 화면과 API 데이터 소스를 교체하지 않는다.

| 역할 | 구현 |
|---|---|
| PostgreSQL | 기관별 결과·데이터셋·모델·작업과 계보를 트랜잭션에 저장한다. 기존 노드와 파일 연결은 덮어쓰지 않는다. |
| PostGIS | CRS84 GeoJSON 지오메트리를 SRID 4326으로 저장하고 타당성, 경·위도 범위와 공간 인덱스를 적용한다. |
| pgvector | 768차원만 저장한다. 기관·임베딩 모델을 먼저 제한하고 정확 코사인 검색을 수행한다. 동일 모델과 차원을 쓰는 검증된 입력이 필요하다. |
| S3 | 기관과 SHA-256으로 키를 생성해 명시적으로 선택한 파일만 조건부 업로드한다. 저장 후 원격 본문과 크기·해시를 다시 대조한다. |
| 권한·파일 링크 | PostgreSQL RLS가 신뢰한 서버 세션의 기관 범위에 적용된다. 동일 기관의 등록 자산에만 HTTPS 서명 링크를 발행한다. TTL은 1–900초다. |

`services.storage.store.LineageStore(dsn).transaction(institution)`에서 `put_node`, `link`, `get_node`, `ancestry`, `bind_asset`, `get_asset`을 호출한다. 허용되는 방향은 데이터셋→모델/작업, 모델→작업, 작업→결과다. 파일을 올리고 해시를 확인한 뒤 메타데이터를 트랜잭션에서 등록한다. 재실행은 기존 객체를 검증하고 같은 결과를 재사용한다. 네트워크 성공 뒤 SQL이 실패하면 미참조 객체가 남을 수 있어서 정리 시 원장과 대조한다.

애플리케이션 로그인은 RLS를 우회하는 DB 역할을 사용하면 시작하지 않는다. 요청 본문에 나온 기관명을 세션에 적용하지 않으며, 서버에서 인증한 기관 주체를 전달한다. RLS GUC를 설정할 수 있는 앱 DB 역할은 서버 전용 신뢰 역할이다. 기관 사용자에게 SQL 연결권한을 주지 않는다. 운영에서는 앱 역할과 별개로 서명용 접근 키를 프로젝트 구성 서비스에게만 제공하고, AWS 표준 자격증명 공급자와 필요한 버킷·prefix 범위의 IAM 정책을 사용한다.

발행 링크는 TTL 동안 보유자가 사용할 수 있으므로 URL 전체를 로그·DB·공유 메시지에 남기지 않는다. 버킷에서 활성화한 버전 ID가 캡처되면 해당 객체 버전에 서명한다. 익명 읽기 정책은 사용하지 않는다. 공개 승인 기록과 기관 내부 파일 접근은 별개다.

## 격리 개발 환경

`deploy/storage/compose.yaml`의 PostgreSQL과 SeaweedFS는 독립 프로젝트명과 고유 볼륨을 사용하고 호스트에서는 loopback만 노출한다. 제공된 포트 기본값은 55482와 59082다. 기존 프로젝트의 DB/버킷을 대상으로 삼는 Compose 설정은 없다.

1. 저장소 외부에 임시 비밀 파일 디렉터리를 만든다. `pg-admin`, `pg-app`에 각기 다른 개발 비밀번호를 저장한다. `s3-config.json`에는 다음과 같이 익명 사용자가 없는 키를 전달한다. 여기에 적힌 변수명 대신 비밀 관리 서비스가 제공하는 값을 사용한다.

   ```json
   {
     "identities": [{
       "name": "storage-dev",
       "credentials": [{"accessKey": "DEV_ACCESS_KEY", "secretKey": "DEV_SECRET_KEY"}],
       "actions": ["Admin", "Read", "List", "Write"]
     }]
   }
   ```

2. `SDSS_STORAGE_SECRETS_DIR`를 해당 디렉터리로 설정한 뒤 실행한다.

   ```powershell
   docker compose -f deploy/storage/compose.yaml -p sdss-storage-dev up -d --wait --build
   ```

3. 객체 관리 역할로 새 비공개 `sdss-storage-dev` 버킷을 생성한다. 앱 연결에는 권한을 한정한 S3 자격증명과 `sdss_storage_app` DB 역할을 사용한다. 로컬 링킹 시험에만 동일 주소를 쓰고, 사내 환경에서는 검증된 공개 HTTPS 서명 호스트를 구성한다.

   | 설정 | 개발 예 |
   |---|---|
   | `SDSS_STORAGE_DSN` | PostgreSQL 앱 역할의 127.0.0.1:55482 / sdss 연결 문자열을 비밀 관리 서비스로 주입 |
   | `SDSS_STORAGE_S3_ENDPOINT` | `http://127.0.0.1:59082` |
   | `SDSS_STORAGE_S3_SIGN_ENDPOINT` | 내부 접근 URL과 브라우저 주소가 다른 경우에만 별도 설정 |
   | `SDSS_STORAGE_BUCKET` | `sdss-storage-dev` |
   | S3 자격증명 | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` 혹은 표준 AWS 프로필 |

   ```powershell
   python -m pip install 'psycopg[binary]>=3.2,<4' 'boto3>=1.38,<2'
   python -m services.storage.admin --institution dev-health health
   ```

## 기존 결과의 선택 이관

```powershell
python -m services.storage.admin --institution dev-cckp migrate-result `
  --database data/curated/results/registry.sqlite3 --root . `
  --result-id 318ad96f89c23875aa8927aa5adcd327132bb2a6e58d0819736803e5f7f65a27 `
  --asset report:cdd-verification --asset report:cdd-grid-table
```

SQLite 패키지 원본 문자열의 SHA-256과 보존한 라이선스 파일의 크기·SHA를 확인한다. 파일 종류는 `source:<ID>`, `layer:<ID>`, `report:<ID>`로 지정한다. 권한 확인이 끝나지 않은 반텐 과거 벡터는 이 경로에서 제외된다. 수집 원장, 기존 SQLite와 원본 파일의 수정이 필요 없다. 과학 검토·기관 공개 승인 및 기관 역할의 운영 이전은 별도로 적용한다.

## 백업 및 복구

1. 백업 대상 기관에 쓰는 워커/API의 쓰기를 일시 정지한다. PostgreSQL의 `pg_dump -Fc`로 스키마·데이터·RLS를 기록하고 같은 기준 시점의 기관 객체를 `export-objects`로 별도 디렉터리에 저장한다. DB 덤프와 manifest의 해시와 보존 시각을 암호화된 저장소에 함께 기록한다.

   ```powershell
   docker compose -f deploy/storage/compose.yaml -p sdss-storage-dev exec -T postgres pg_dump -U sdss_admin -d sdss -Fc -f /tmp/sdss-storage.bak
   docker compose -f deploy/storage/compose.yaml -p sdss-storage-dev cp postgres:/tmp/sdss-storage.bak artifacts/sdss-storage.bak
   python -m services.storage.admin --institution dev-cckp export-objects artifacts/dev-cckp-objects
   ```

2. 대상 DB에 필요한 로그인 역할과 두 확장을 설치할 수 있는 서버가 있는지 확인한다. 실제 운영 데이터베이스와 분리된 빈 DB에 `pg_restore --exit-on-error`로 복원한다. 애플리케이션 연결은 복원된 DB의 일반 역할을 사용한다.
3. 비어 있는 전용 복구 버킷의 이름으로 환경 변수를 설정한다. `restore-objects`는 복원된 DB의 기관별 객체 목록이 백업 manifest와 일치할 때만 한 건씩 해시를 확인해 보낸다. 역할에 따른 조회, 계보, 만료 파일 링크와 서비스 결과를 재시험한다.

## 시험 범위와 다음 운영 확인

`python -m pytest tests/storage`는 오프라인 계약 시험이다. 실 서비스 시험은 `SDSS_STORAGE_TEST=1`과 폐기 가능한 개발 DB·비공개 버킷이 준비된 환경에서만 활성화한다. 기관 승인된 DB·버킷·IAM·SSO 및 복구 RPO/RTO 검증은 `BLOCKED`다. 임베딩 검색 구현은 실제 보고서 임베딩 검증과 별개이며 외부 운영 Kubernetes 인수는 해당 클러스터 승인 뒤 진행한다.

개발 이미지와 설정을 확인한 1차 출처는 [PostGIS 이미지 저장소](https://github.com/postgis/docker-postgis), [SeaweedFS 4.04 서버 옵션](https://github.com/seaweedfs/seaweedfs/blob/4.04/weed/command/server.go)이다.
## 2026-11-25 로컬 검증 결과

- `VERIFIED_REAL` 공식 SeaweedFS 4.04 Windows ZIP의 SHA-256 `0c834aa9052276543f8a11b35d26f547a271ad3005ac7f0bdba1f54bf3e3b090`을 릴리스 메타데이터와 대조했다. loopback 59083에서 보존 CCKP 검산 JSON 3,295바이트를 PUT하고 SHA-256 `6fdd91a87592c0f4bcbb0fccc37e367052e677e4dead2f25cb9fb29c548bcbbf`을 읽어 확인했다. 같은 핀을 다시 업로드했다. 서명 GET은 200, 익명 GET과 만료된 GET은 각각 403을 반환했다. [SeaweedFS 릴리스](https://github.com/seaweedfs/seaweedfs/releases/tag/4.04)
- `VERIFIED_REAL` 검산 JSON 1건을 manifest와 함께 백업했고, 새로 구동한 별도 S3 서비스(loopback 59084)의 빈 버킷으로 복원해 본문 크기·SHA-256을 확인했다. 이 시험은 고정한 기관 인벤토리 1건을 사용했다. PostgreSQL 복원과 실제 기관 권한 검증은 별도로 대기한다.
- `TESTED_SYNTHETIC` 단일 기관 식별자·객체 키·TLS endpoint 및 768차원 검증 시험 2건이 통과했다.
- `IMPLEMENTED_UNVERIFIED` Docker 개발 스택 PostgreSQL 컨테이너 생성 대기와 loopback 연결 timeout을 관찰했다. DB의 라이브 이관 및 `pg_restore` 통합 여부는 별도 확인이 필요하다.

## 2026-11-27 STEP 01 격리 Staging

`fc596cb`의 기존 저장소 Compose를 `sdss-storage-staging` 프로젝트로 구동했다. API·Web은 별도 `sdss-lake-staging` 프로젝트에서 저장소 네트워크에 연결했다. DB 55486, S3 59086, SDSS 5280은 호스트 loopback으로 제한했다. 비밀은 저장소 외부에 둔다.

| 확인 | 결과 |
| --- | --- |
| PostgreSQL/PostGIS | `VERIFIED_REAL`. PostGIS 3.4.3, 반텐 One Map/BIG geometry SRID 4326·유효성 확인, 다른 기관 범위에서 동일 레코드 조회 차단. |
| pgvector | `TESTED_SYNTHETIC`. 0.8.6에서 앱 저장소의 768차원 시험 벡터 2건 등록과 코사인 검색(거리 0·1)을 확인하고 시험 자료를 롤백했다. GeoLLM 문서 원본 임베딩은 아직 게시되지 않았다. |
| SeaweedFS | `VERIFIED_REAL`. 비공개 버킷에서 원본 One Map 스냅샷 5,255,501바이트의 SHA-256 일치. 무서명 GET은 403. |
| SDSS | `VERIFIED_REAL`. 토큰이 있는 저장소 API는 `VERIFIED_PROJECT_STORAGE`, 기관 계보 및 서명 다운로드가 동작했다. 무인증 상태 확인은 403. |

증거는 실행 호스트 `artifacts/deploy/sdss-storage-staging/`의 `backend-readback.log`, `api-readback.json`, `pgvector-roundtrip.log`에 있다. STEP 01의 범위는 Docker 저장소와 SDSS의 저장소·계보 API 연결이다. GeoLLM 본 질의의 데이터 소스 전환과 Kubernetes Staging 연결은 별도 검증 경로다.

## 2026-11-27 STEP 02 Staging 접속 설정

저장소 Docker 프로젝트는 `sdss-storage-staging`, SDSS 프로젝트와 kind 검증 네임스페이스는 `sdss-lake-staging`이다. Compose API는 격리 Compose 디렉터리의 `deploy/api.local.env`에서 값을 받는다. kind의 `storage-api-validation` API는 같은 네임스페이스의 Secret `sdss-api-local`을 필수로 읽는다. 두 API 모두 같은 PostgreSQL·SeaweedFS Staging 인스턴스를 조회한다.

| 설정 | Compose 컨테이너 | kind 검증 Pod |
| --- | --- | --- |
| SDSS 화면 접속 | `http://127.0.0.1:5280` | 포트포워드 `http://127.0.0.1:5281` |
| `SDSS_STORAGE_DSN` | `postgres:5432/sdss` | `postgres:55486/sdss` |
| DB 로그인·기관 | `sdss_storage_app`, `staging-cckp` | 동일 |
| `SDSS_STORAGE_S3_ENDPOINT` | `http://objects:8333` | `http://objects:59086` |
| `SDSS_STORAGE_BUCKET`·`AWS_DEFAULT_REGION` | `sdss-storage-staging`, `us-east-1` | 동일 |
| `SDSS_STORAGE_S3_SIGN_ENDPOINT` | 검증 호스트에서 여는 `http://127.0.0.1:59086` | 동일 |

kind의 `postgres`와 `objects`는 Docker Desktop의 Staging 포트로 연결하는 `ExternalName` Service다. 호스트에서 DB를 관리할 때는 `127.0.0.1:55486`을 사용한다. 서명 주소는 브라우저가 파일을 받을 때 사용하는 주소다. API에서 객체를 조회할 때는 각 환경의 S3 Service 주소를 사용한다. 다른 클러스터에 배포할 때는 해당 인프라의 실제 DB·객체 저장소 Service와 HTTPS 서명 주소를 지정한다.

DSN 비밀번호, `SDSS_STORAGE_READ_TOKEN`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`는 로컬 비밀 파일과 Kubernetes Secret에 보관한다. Secret을 만들 때는 비밀 파일을 직접 읽는 `kubectl create secret generic ... --from-env-file=...` 방식을 사용한다. 로컬 환경 파일과 Secret 값은 Git에 포함하지 않는다.

두 환경에서 토큰을 넣은 저장소 상태 확인은 `VERIFIED_PROJECT_STORAGE`였다. 같은 반텐 원본 5,255,501바이트를 서명 다운로드해 일치하는 SHA-256을 검증했다. 토큰 없는 API와 서명 없는 객체 요청은 각각 HTTP 403이었다. 증거는 실행 호스트 `artifacts/deploy/sdss-storage-staging/step02-api-readback.json`에 있다. 이 검증은 저장소·계보 API 경로에 적용된다. GeoLLM 정량 결과와 pgvector 문서 검색의 Staging 자료 전환은 별도 작업이다.

## 2026-11-27 STEP 03 GeoLLM Staging 자료 전환

`VERIFIED_REAL` STEP 02의 동일 Staging에서 `banten-geollm-20261127-v1`을 게시했다. 정량 및 경계·미리보기 API와 실제 pgvector 문서 검색을 기존 GeoLLM UI에 연결했다. 운영 승인 범위는 기존 계약을 따른다. [릴리스·검증 근거](../lcluc/GEOLLM_QUERY.md#step-03-반텐-geollm-staging-릴리스)

## 2026-11-27 STEP 04 GeoLLM 운영 조회 경로

Compose의 API 환경 파일과 Kubernetes의 API 컨테이너 환경에 `SDSS_GEOLLM_STORAGE_MODE=lake`와 승인된 `SDSS_GEOLLM_LAKE_RELEASE`를 명시한다. Staging 릴리스는 `banten-geollm-20261127-v1`이다. API 런타임에는 `SDSS_STORAGE_DSN`, `SDSS_STORAGE_INSTITUTION`, `SDSS_STORAGE_BUCKET`, 실제 저장소 서비스 접속 주소 및 읽기 자격 증명을 제공한다. 개발 환경에서 로컬 원본을 읽을 때는 `SDSS_GEOLLM_STORAGE_MODE=local`을 설정한다.

GeoLLM 어댑터는 플랫폼의 기관 범위 RLS와 객체 해시 계약을 사용한다. `SDSS_STORAGE_READ_TOKEN`은 기관 계보 HTTP API의 조회 인증 설정이다. GeoLLM의 데이터 접근에는 서버가 보유한 읽기 권한을 사용한다. API가 임베딩 모델과 지도에 쓰는 `/tmp`는 쓰기 가능한 임시 공간으로 연결한다. 운영 모드 연결 실패 시 GeoLLM은 해당 질의를 `BLOCKED`로 반환한다. [모드·오류 계약](../lcluc/GEOLLM_QUERY.md#step-04-geollm-저장소-모드)
