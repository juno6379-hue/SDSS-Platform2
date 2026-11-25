# v4.2 운영 경로 2~8: 기관 작업·원천·모델·저장소

- updated_at: 2026-11-25 KST
- source_commit: `UNCOMMITTED_WORKTREE` — 1번 결과 카탈로그 기준 커밋은 `c4a3954`
- 목표: 결과 카탈로그 다음 단계인 기관 작업, UI 연결, 기관 원천, 모델 버전 실행, 운영 저장소를 하나의 증거 경로로 설명한다.
- 실제 기관 endpoint·자격증명·승인 원본·학습 모델·운영 DB/버킷: `BLOCKED`
- 8번 SeaweedFS S3 객체 경로: `VERIFIED_REAL`; PostgreSQL RLS·복구와 Kubernetes 인수: `BLOCKED`
- 3번 API/Vite HTTP·build·실제 Edge 조회: `VERIFIED_REAL`

## 1. 쉬운 설명

1번은 기존 결과를 같은 ID로 지표·지도·보고서까지 보여 주는 카탈로그였다. 2~8번은 그 앞뒤를 연결한다.

```text
기관의 고정 승인
  → 2. 기관 작업 접수·진행·취소
  → 3. 기존 React에서 상태 확인
  → 4~6. 기관 원천과 공개 가능성 확인
  → 7. 승인된 모델 버전 선택·실행·롤백
  → 1. 같은 결과 ID의 카탈로그
  → 8. 기관별 저장소·계보·파일 접근
```

현재 상태를 가장 쉽게 말하면 다음과 같다.

| 번호 | 한 줄 설명 | 현재 판정 |
|---|---|---|
| 2 | 기관 작업 API와 worker 계약은 시험했지만 실제 공급자 설정은 없음 | 계약 `TESTED_SYNTHETIC`, 실운영 `BLOCKED` |
| 3 | 기존 React에 작업·모델·기관 자료를 연결하고 API/Vite HTTP·build를 확인했지만 최종 실클릭 전 | 연결 `VERIFIED_REAL`, 실브라우저 `PLANNED` |
| 4 | RTRW·Sentinel의 실제 로컬 증거를 읽되 현행성·미정산·공간 공백을 보존 | 로컬 무결성 `VERIFIED_REAL`, 공개·완료 `BLOCKED` |
| 5 | CCKP 원본과 CDD bbox 수치를 고정했지만 국가 행정평균·전체 catalog는 아님 | 제한 범위 `VERIFIED_REAL`, 확대 사용 `BLOCKED` |
| 6 | KLHK·비공개 문서 색인의 파일·행 수를 확인했지만 native 23·권리·공개 검색은 미확인 | 로컬 무결성 `VERIFIED_REAL`, 공개 `BLOCKED` |
| 7 | 실제 후보의 scene 누출은 제거했고 합성 ONNX 버전·롤백을 시험함 | 후보 `VERIFIED_REAL`, 실행계약 `TESTED_SYNTHETIC`, 실제 학습·배포 `BLOCKED` |
| 8 | 별도 SeaweedFS에 실제 검산 JSON을 저장·서명 조회했지만 PostgreSQL과 Kubernetes는 미확인 | S3 경로 `VERIFIED_REAL`, DB/클러스터 `BLOCKED` |

이 표에서 `VERIFIED_REAL`은 **해당 범위의 로컬 파일·수치가 실제였다는 뜻**이다. 기관 공개 승인, 현재 법적 효력, 독립 정확도 또는 운영 배포를 뜻하지 않는다.

## 2. 이론적 배경

### 2.1 제어면과 데이터면 분리

- 제어면: 어떤 승인으로 어떤 공급자·작업·모델 버전을 실행할지 결정한다.
- 데이터면: 원본·산출물·모델·보고서 바이트를 저장하고 전달한다.

작업 API가 승인 ID만 받는 이유는 사용자가 요청 본문에서 URL·명령·모델 버전을 바꾸지 못하게 하기 위해서다. 실제 파일은 SHA와 byte로 고정하고, 결과가 만들어진 뒤에야 공통 결과 ID에 연결한다.

### 2.2 멱등 작업과 복구

같은 승인·공급자 설정은 같은 작업 ID를 만든다. 공급자 제출에는 그 ID를 `Idempotency-Key`로 사용한다. 응답이 끊겨 성공 여부가 불명확해도 새 작업을 만들지 않고 같은 ID의 상태를 다시 확인한다. 로컬 queue와 workflow checkpoint가 일치하지 않을 때도 이미 등록된 결과를 중복 제출하지 않고 로컬 commit만 재생한다.

### 2.3 현행성·무결성·공개 권리는 다른 질문

파일의 SHA가 맞는지, 지금 효력이 있는지, 외부에 공개할 권리가 있는지는 별개다.

| 질문 | 예시 |
|---|---|
| 무결성 | 저장한 파일의 SHA·byte가 receipt와 같은가? |
| 현행성 | 반텐 2017 표본이 현재 조례와 일치하는가? |
| 권리 | 기관이 재사용·게시를 허용했는가? |
| 품질 | Sentinel SCL 기준과 공간 피복을 만족하는가? |
| 독립성 | 모델과 분리된 현장·전문가 정답으로 평가했는가? |

이번 6종 인벤토리는 첫 질문의 제한된 범위만 실증했다. 그래서 모든 `publication_gate`와 `public_search_enabled`를 차단한다.

### 2.4 격리 후보와 승인된 모델 실행

동일 원본 scene이 validation과 test에 동시에 있으면 평가 누출이다. 행 일부만 옮기면 같은 scene의 정보가 남을 수 있으므로 해당 scene 전체를 후보에서 격리한다. 그러나 scene 중복 0만으로 학습 준비가 끝나지는 않는다. 지리 중첩, 주·연도 피복, 독립 라벨을 추가로 확인해야 한다.

모델 실행은 다음을 다시 확인한다.

- dataset manifest와 readiness·training·evaluation SHA 결속
- 독립 accuracy reference인지
- 보안·rollback 시험
- 공통 결과 카탈로그의 과학 승인
- 활성 버전과 operator 승인 revision

과학 승인이 철회되면 이미 활성화된 합성 버전도 다음 실행에서 차단된다. 기관 공개 승인은 이 내부 실행 승인과 또 별개다.

### 2.5 기관 격리 저장소

저장소 설계는 기관별 PostgreSQL RLS, PostGIS geometry, 동일 모델의 768차원 pgvector, 기관+SHA 객체 key, 짧은 HTTPS 서명 링크를 사용한다. 요청 본문의 기관명을 신뢰하지 않고 인증된 서버 세션이 기관 scope를 정해야 한다. 이 설계가 코드에 있다는 것과 실제 기관 DB·버킷·IAM·SSO가 인수됐다는 것은 다르다.

## 3. 코드·데이터 동작

### 3.1 2번 — 기관 작업 provider

`services/jobs/contracts.py`, `providers.py`, `store.py`, `worker.py`와 `services/api/jobs_api.py`가 다음 경로를 만든다.

| API | 동작 |
|---|---|
| `GET /api/jobs` | 준비 상태·blocker·최근 작업 |
| `GET /api/jobs/approvals` | 서버에 고정된 유효 승인 목록 |
| `POST /api/jobs` | `approval_id`만 받아 202 접수 |
| `GET /api/jobs/{id}` | 상태·진행·이력·결과 ID |
| `POST /api/jobs/{id}/cancel` | 취소 요청 접수 |

공급자 base URL은 경로가 있는 HTTPS만 허용한다. redirect, 사용자 제공 URL, path traversal, query/fragment가 있는 provenance URI, 64MiB 초과 결과를 거절한다. 공급자 token은 서버 환경에서만 읽고 조회 응답에는 노출하지 않는다.

실제 개발 서버의 조회는 HTTP 200이지만 본문 상태는 `BLOCKED`, 사유는 `JOB_PROVIDER_CONFIG_NOT_SET`이다. worker CLI도 같은 상태에서 종료 코드 1로 시작을 거부했다. 따라서 **HTTP 200은 공급자 작업 가능을 뜻하지 않는다.**

### 3.2 3번 — 기존 React 운영 화면

`frontend/src/InstitutionOperations.tsx`와 `institutionOpsClient.ts`는 다음을 기존 화면에 연결한다.

- 기관 작업·승인 목록, 진행률, 취소 요청, 결과 ID 링크
- 모델 버전·활성 revision·rollback 이력의 조회 전용 화면
- 기관 원천 6종의 검증·공개·검색 상태

쓰기 token은 password input의 현재 컴포넌트 메모리에만 두고 요청 후 지운다. URL·local/session storage·상위 상태에 저장하지 않는다. 5초 polling은 이전 응답을 유지하지 않고 abort/generation으로 오래된 응답을 버린다. 결과 ID가 생기면 `#/reports/results?result_id=...`로 1번 카탈로그에 연결한다.

실제 API `8014`와 Vite `5175`를 통해 `/api/jobs`, `/api/model-releases`, `/api/institution-sources` 세 경로의 HTTP 200을 확인했고, 합성 UI 계약과 138-module build도 확인했다. Edge에서 작업·모델·기관 자료 화면을 열고 새로고침을 눌렀으며, 결과 ID가 포함된 링크에서 실제 CCKP 값을 확인했다. 본문의 작업·모델 차단 상태는 유지됐다.

### 3.3 4~6번 — 기관 원천 6종 인벤토리

`services/datahub/institution_sources.py`는 원격 요청·예약·원장 쓰기 없이 로컬 증거를 다시 pin한다.

| source | 실제 확인 범위 | 공개 차단 이유 |
|---|---|---|
| RTRW | 6주 역사 레이어 93,340 feature, 반텐 역사 표본 1 | 현행 0/6, 조례·권리 미확인 |
| CCKP | 4,209,592B 원본 SHA, 12,765셀, `40.91221481742199 days` | 국가 행정평균·연차 시계열·전체 변수 catalog 아님 |
| Lake | 6,175 objects·6,721 references와 catalog SHA | live PostGIS/object service cutover 미검증 |
| KLHK | 기존 취득 보고서의 metadata 문서 7개 | native 23 검증 0, renderer 25와 domain·권리 미해결 |
| private index | 7문서·122 chunk DB SHA | 합성 hash embedding, private, public search false |
| Sentinel | snapshot 8창·품질 5·추가 본문 50,597,002B | 9번째 미정산·공간 공백·독립 라벨 없음 |

여기서 KLHK 7은 연차 토지피복 원본 7개가 아니라 기존 취득 보고서의 CCKP 문서 5개와 KLHK metadata 2개를 합친 문서 수다. 공개 summary는 로컬 path·본문·수치를 제거하고 상태와 collection-progress 참조만 허용한다. 실제 inventory의 `remote_requests=0`, `ledger_writes=0`이다.

### 3.4 7번 — scene 격리 후보와 모델 release

`services/mlops/split_candidate.py`는 실제 보존 manifest에서 split을 넘나든 원본 scene 1개를 통째로 제외했다.

| 지표 | 이전 | 후보 |
|---|---:|---:|
| 물리 행 | 1,779 | 1,751 |
| 품질 적격 행 | 1,407 | 1,382 |
| 원본 scene 충돌 | 1 | 0 |
| train / val / test 적격 | - | 865 / 276 / 241 |

후보 SHA는 `2cab1cb03d043ce58e3fd8f318ac0162ca48e15688bb51e729c6f796738ca032`, 크기는 11,388,949B다. 보고서가 `training_allowed=false`, `deployment_allowed=false`를 명시한다. 남은 검사는 `GEOGRAPHIC_SPLIT_OVERLAP`, `SOURCE_COVERAGE`, `INDEPENDENT_LABELS`다.

`services/mlops/releases.py`는 evidence-bound ONNX 버전을 등록하고 활성화·rollback한다. 합성 ONNX에서 입력 10의 출력은 v1 활성화 11, v2 활성화 12, v1 rollback 11로 바뀌었다. 이후 카탈로그 과학 승인을 `REJECTED`로 바꾸자 활성 버전 조회·실행이 차단됐다. 이는 버전 선택 계약 증거이지 실제 LCLUC 모델의 학습·성능 증거가 아니다.

### 3.5 8번 — 기관 저장소

`services/storage/`는 다음 계약을 구현한다.

- PostgreSQL의 기관별 lineage node와 허용 방향 link
- CRS84 GeoJSON을 PostGIS SRID 4326으로 검증·저장
- 동일 기관·모델 범위의 768차원 pgvector 검색
- 기관과 SHA로 만든 S3 key, 조건부 업로드 뒤 원격 byte·SHA 재확인
- 동일 기관의 등록 asset만 1~900초 HTTPS 서명 링크 발행
- CCKP 결과에서 명시적으로 선택한 보고서만 이관
- 객체 export/restore와 manifest 재검증

별도 개발 SeaweedFS 4.04 S3에는 실제 CCKP 검산 JSON **3,295B**를 저장했다. 업로드 원본 SHA가 유지되고 같은 입력 재시도가 기존 객체를 검증·재사용하는지 확인했다. 버킷 원주소의 익명 GET은 HTTP 403으로 거절됐고, 45초 presigned URL은 본문을 반환했으며 만료 뒤 HTTP 403이 됐다.

반면 PostgreSQL fixture는 TCP timeout으로 연결되지 않아 실제 RLS·PostGIS·pgvector·lineage transaction·`pg_restore`를 검증하지 못했다. Kubernetes context도 없어 클러스터 인수시험은 실행하지 않았다. 따라서 **S3 객체·링크 경로만 `VERIFIED_REAL`**이며 기관 저장소 전체나 운영 cutover로 확대하면 안 된다.

## 4. 테스트·증거

| 대상 | 증거 | 상태 |
|---|---|---|
| 1번 카탈로그 | GitHub `c4a3954`, 실제 Edge 실자료 2·지도 2·보고서 3 | `VERIFIED_REAL` |
| 기관 작업 계약 | 지연·재개·멱등 제출·worker lock·취소·model pin·asset SHA·결과 등록 8 PASS | `TESTED_SYNTHETIC` |
| 기관 작업 실상태 | 개발 API 조회 HTTP 200 + `JOB_PROVIDER_CONFIG_NOT_SET`; worker exit 1 | `VERIFIED_REAL` blocker |
| 실제 기관 작업 | endpoint·token·승인 원본·인수시험 없음 | `BLOCKED` |
| 기관 원천 | 실제 로컬 6종 pin, 원격 요청 0·원장 쓰기 0 | `VERIFIED_REAL` 제한 범위 |
| 기관 원천 계약 | 누락·손상·경로 이탈·SHA drift·공개 필드 redaction 5 PASS | `TESTED_SYNTHETIC` |
| 공개 가능성 | 6종 모두 publication `BLOCKED`, public search false | `VERIFIED_REAL` 현재 상태 |
| scene 격리 후보 | 1,779→1,751, 적격 1,382, original scene 충돌 0 | `VERIFIED_REAL` local candidate |
| 모델 release | weak reference 거절, 버전·rollback·승인 철회 차단, 합성 ONNX 11→12→11 | `TESTED_SYNTHETIC` |
| 실제 모델 | 학습·독립평가·실 ONNX·배포 0 | `BLOCKED` |
| React API/Vite 연결 | API 8014·Vite 5175의 세 운영 경로 HTTP 200, 합성 계약·138 modules build | `VERIFIED_REAL` 연결 범위 |
| React 실제 Edge 클릭 | 작업·모델·기관 자료 6종 조회, 결과 ID로 CCKP 재조회 | `VERIFIED_REAL` |
| SeaweedFS S3 | CCKP 검산 JSON 3,295B, SHA·재시도, 익명 403, 45초 presigned GET·만료 403 | `VERIFIED_REAL` 개발 격리환경 |
| PostgreSQL 저장소 | fixture TCP timeout으로 RLS·PostGIS·pgvector·lineage·restore 실검증 실패 | `BLOCKED` |
| Kubernetes | context 없음, 클러스터 인수시험 0 | `BLOCKED` |
| 운영 저장소 | 기관 DB·버킷·IAM·SSO·RPO/RTO 인수 없음 | `BLOCKED` |

WorldCover 2021은 다른 연도의 정답으로 쓰지 않는다. Esri IO 또는 KLHK/WorldCover와의 weak agreement도 independent accuracy로 보고하지 않는다.

## 5. 발표 스크립트

### 1분

“Platform2의 운영 경로는 고정 기관 승인으로 작업을 접수하고, 로컬 원천 증거를 확인하고, 승인된 모델 버전을 실행해 같은 결과 ID로 돌아오는 구조입니다. 기관 작업 계약은 합성시험 8건을 통과했지만 실제 서버는 공급자 설정이 없어 HTTP 200 응답 안에서 차단 상태를 보고합니다. 실제 원천 6종의 로컬 해시는 확인했지만 모두 공개 차단입니다. Sentinel 후보는 누출 scene을 격리해 1,779행에서 1,751행, 적격 1,382행, scene 충돌 0으로 만들었지만 학습 허용은 false입니다. 별도 SeaweedFS에서 3,295바이트 객체 저장·복원과 서명 링크를 검증했습니다. Edge에서 운영 화면을 눌러 결과 ID로 다시 열었습니다. PostgreSQL과 Kubernetes 운영 시험은 대기합니다.”

### 5분

1. 기관 작업 요청은 URL·명령이 아니라 사전에 고정된 승인 ID만 받는다.
2. 작업 ID와 공급자 idempotency key를 같게 해 재시도·복구에서 중복 실행을 줄인다.
3. 실제 provider 설정이 없으므로 API는 HTTP 200과 함께 blocker를 반환하고 worker는 시작을 거부한다.
4. React는 작업·승인·취소·결과 ID, 모델 version·rollback, 기관 원천 상태를 같은 origin API로 조회하도록 구현됐다.
5. RTRW·CCKP·Lake·KLHK·private index·Sentinel 6종은 로컬 증거만 검증됐고 모두 공개 차단이다.
6. CCKP 수치는 bbox climatology, KLHK 7은 metadata 보고서 문서 수, private index는 합성 hash임을 확대 해석하지 않는다.
7. 실제 manifest에서 누출 scene 전체를 격리해 1,751행·적격 1,382행·scene 충돌 0 후보를 만들었다.
8. 지리 중첩·피복·독립 라벨이 남아 있어 후보의 학습·배포는 허용하지 않았다.
9. 합성 ONNX는 11→12→11 rollback과 과학 승인 철회 후 실행 차단을 검증했다.
10. 별도 SeaweedFS의 실제 객체·45초 서명 링크는 검증했지만 PostgreSQL RLS·복구와 Kubernetes는 차단됐다.
11. 기관 인프라·권한·복구 인수 뒤에만 전체 저장소를 실운영으로 승격한다.

## 6. Q&A

**Q. `/api/jobs`가 HTTP 200이면 기관 작업을 실행할 수 있습니까?**
아니다. 본문이 `BLOCKED`이고 `JOB_PROVIDER_CONFIG_NOT_SET`이면 조회 API가 정상적으로 차단 상태를 설명한 것이다. 실제 공급자 작업 성공이 아니다.

**Q. 합성시험 8건이 통과했으니 기관 endpoint 계약도 확인됐습니까?**
아니다. 지연·재개·취소·결과 등록 계약을 격리 시험한 것이다. 실제 endpoint·token·승인 문서·인수시험은 없다.

**Q. 기관 원천 6종이 `VERIFIED_REAL`이면 공개해도 됩니까?**
아니다. 로컬 파일 SHA·byte의 제한 범위가 실제라는 뜻이다. 6종 모두 publication gate와 public search가 차단됐다.

**Q. KLHK 문서 7개는 연차 토지피복 원본 7개입니까?**
아니다. CCKP 문서 5개와 KLHK metadata 2개를 포함한 기존 취득 보고서 문서 수다. native 23-class 검증은 0이다.

**Q. scene 충돌이 0이면 바로 학습할 수 있습니까?**
아니다. 지리 중첩, 주·연도 피복, 독립 라벨 검사가 남았고 후보 자체가 `training_allowed=false`다.

**Q. ONNX 출력 11→12→11은 실제 모델 정확도가 좋아졌다는 뜻입니까?**
아니다. 입력 10에 상수 1 또는 2를 더하는 합성 그래프의 버전 선택·rollback 시험이다.

**Q. 활성 버전이면 과학 승인이 철회돼도 계속 실행됩니까?**
아니다. 실행 직전에 증거와 과학 승인을 다시 검사하므로 승인 철회 뒤에는 차단된다.

**Q. React HTTP 200과 build가 통과하면 실제 UI 클릭도 검증된 것입니까?**
HTTP와 빌드 시험은 서버 연결과 컴파일을 확인한다. 실제 Edge 검증에서는 작업·모델·기관 자료 화면과 같은 결과 ID CCKP 조회를 추가로 확인했다.

**Q. SeaweedFS 검산 JSON을 읽었으니 운영 Lake cutover가 끝난 것입니까?**
아니다. 3,295B 객체의 SHA·재시도·익명 403·45초 서명 링크만 실제 검증했다. PostgreSQL fixture는 TCP timeout, Kubernetes context는 없음이므로 RLS·lineage·복구·클러스터 인수는 `BLOCKED`다.

**Q. WorldCover 2021과 맞으면 독립 정확도입니까?**
아니다. 약한 참조 일치도다. 다른 연도의 정답으로 쓰지 않으며 독립 현장·전문가 라벨로 별도 평가해야 한다.
