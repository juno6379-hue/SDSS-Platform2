# 기관 Toolbox와 외부 모델 실행

Platform2의 작업 API는 고정된 승인 문서를 작업 큐로 접수한다. 워커는 등록된 WorkflowRunner 단계로 기관에 제출하고, 진행 상태를 확인한 뒤 결과와 검증 영수증을 공통 카탈로그에 등록한다.

## 상태와 접수 경로

| API | 내용 |
|---|---|
| `GET /api/jobs` | 준비 상태, 차단 사유, 최근 작업 목록 |
| `GET /api/jobs/approvals` | 현재 유효한 승인 ID, 공급자, 연산, 모델 고정 버전 |
| `POST /api/jobs` | `{"approval_id":"approved-job-1"}` 접수. 응답 202와 작업 ID |
| `GET /api/jobs/{job_id}` | 작업과 최근 상태·진행 이력 |
| `POST /api/jobs/{job_id}/cancel` | 취소를 요청하고 202를 반환. 기관 작업의 취소 완료는 이후 조회에서 확인 |

API는 기존 로컬 Host와 peer 검사를 적용한다. 제출·취소에는 서버에서 설정한 `SDSS_JOBS_OPERATOR_TOKEN`의 Bearer 인증이 필요하다. 조회에는 토큰이나 승인 파라미터를 반환하지 않는다. 다기관 SSO와 데이터 접근 정책은 운영 배포에서 별도 검증한다.

같은 승인·공급자 설정은 같은 작업 ID를 반환한다. 실제 제출 전 취소는 큐에서 끝난다. 제출이 시작된 작업은 공급자가 확인할 때까지 `CANCELLING`으로 표시한다. `FINALIZING`은 고정 산출물 검사가 끝나 카탈로그 등록을 시작했다는 뜻이다. 이 상태에서 취소를 요청하면 409를 반환한다. 공급자 호출의 성공 여부가 불명확한 로컬 실패는 차단 사유를 표시하며 공급자 측 조치 결과까지 확정하지 않는다.

## 설정과 운영 워커

`SDSS_JOBS_CONFIG`에서 읽는 운영자 설정 파일은 `schema_version: sdss-institution-jobs/1`, `providers`와 `approvals`를 포함한다. 설정 파일과 승인 디렉터리는 운영자만 쓸 수 있고 서비스에는 읽기 전용으로 제공한다.

- `providers.<키>`에 `kind` (`institution_toolbox`, `external_model`, `project_model`), `base_url` (경로를 포함한 HTTPS 주소), `operations`, `credential_env`를 기록한다. 실제 제공처가 발급한 토큰은 `SDSS_PROVIDER_*_TOKEN` 환경으로 주입한다.
- `approvals.<ID>`에는 프로젝트 상대경로 `path`, `bytes`, `sha256`을 기록한다. 그 고정 문서는 `schema_version: sdss-job-approval/1`, `approval_id`, `provider`, `operation`, `model`의 `name/version/artifact_sha256`, `approved_by`, 시간대 포함 `eligible_until`, 고정 `parameters`를 포함한다. 처리할 파일·입력은 승인 문서 자체에 고정하며 API 요청으로 URL·명령·모델 버전을 바꿀 수 없다.

```powershell
python -m services.jobs.worker --once
python -m services.jobs.worker --interval 5
```

API와 워커는 같은 설정, 영수증 루트, 로컬 결과 DB를 사용한다. 기본 위치는 `data/curated/jobs`이며 `SDSS_JOBS_STATE_DIR`로 프로젝트 루트 내에서 바꿀 수 있다. 설정이 없으면 읽기 API에 차단 사유가 나오며 워커는 시작하지 않는다. 워커는 OS가 회수하는 별도 SQLite 잠금으로 같은 공유 파일시스템에서 작업을 직렬화하고, 중단 시 stale WorkflowRunner 잠금을 복구한다. 재생성 가능한 테스트 SQLite 사용과 운영 다중 노드 저장소 요구를 구분한다.

`queue.sqlite3`에는 작업과 이벤트가 남고, `workflows/<job-id>/state.json`은 단계와 증거 SHA를 보존한다. `received/<job-id>/receipt.json`에는 승인 해시·공급자 식별자·모델 버전·자료 해시·저장 경로가 기록된다. 원본 승인 스냅샷과 정규화한 공급자 manifest의 고정 핀도 남긴다. 프로젝트 모델은 최초 제출 전 승인 문서의 버전과 아티팩트 SHA를 현재 활성 버전과 비교하고 manifest SHA와 활성화 revision도 고정한다.

## 공급자 확인 계약

사전에 합의한 공급자는 베이스 경로 아래 `POST /jobs`, `GET /jobs/{job_id}`, `POST /jobs/{job_id}/cancel`, `GET /jobs/{job_id}/result`, `GET /jobs/{job_id}/assets/{asset_id}`를 제공한다. 고정 작업 ID와 Idempotency-Key로 재제출 및 중복 취소를 처리해야 한다. 공급자는 응답이 끊긴 제출과 뒤이어 들어온 취소가 뒤바뀌어도, 취소 작업이 나중에 실행되지 않게 작업 ID 단위로 취소를 보존해야 한다. 공급자 응답의 작업 ID와 모델 핀을 대조하고 asset ID는 manifest 명세와 맞춘다. Redirect, 사용자 제공 URL, 파일 경로 순회와 자격정보가 담길 수 있는 출처 쿼리를 허용하지 않는다. 결과는 총 64 MiB로 제한한다. 각 파일 SHA·크기, 지리 좌표계·기간·단위·NoData를 공통 패키지 검사로 확인한다.

공급자 결과가 공통 원장에 등록되면 작업 조회에 `result_id`와 `package_sha256`이 표시된다. 과학 검증과 기관 공개 결정은 기존 카탈로그에 각각 남긴다.

## 검증 범위

- `TESTED_SYNTHETIC` 공급자 HTTP 응답 지연과 재개, 한 번의 논리 작업 제출, 중복 워커 잠금, 진행·취소, 모델 승인 버전 불일치, 자산 SHA 다름, 카탈로그 등록과 재조회를 격리 DB의 8개 시험에서 확인했다. 결과 등록을 끝낸 직후 프로세스가 중단된 경우, 공급자 추가 요청 없이 로컬 큐를 복구했다.
- `VERIFIED_REAL` 개발 서버 8017의 작업·승인 조회는 HTTP 200과 `JOB_PROVIDER_CONFIG_NOT_SET`을 반환했다. 같은 설정에서 워커 CLI는 종료 코드 1로 시작을 거부했다.
- `BLOCKED` 기관 실제 운영 endpoint·토큰·승인 문서, 계약 준수, 인수 테스트가 필요하다. 운영 기관 제출·취소·자료 이전 실적은 기록되지 않았다.
