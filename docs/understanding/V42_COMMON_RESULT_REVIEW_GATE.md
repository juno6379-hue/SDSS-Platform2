# v4.2 공통 결과 등록·검토·조회 Gate

- updated_at: 2026-11-25 KST
- Gate 목표: 서로 다른 도메인의 고정 증거를 한 경로로 등록하고, 같은 ID로 다시 조회하며, 검토 이력을 덮어쓰지 않고 남긴다.
- 로컬 등록·조회·Edge 검토 흐름: `VERIFIED_REAL`
- 현재 로컬 제공: `VERIFIED_REAL` — `127.0.0.1:8014`, 운영 배포와는 별개
- registry 충돌·멱등성 계약: `TESTED_SYNTHETIC`
- 운영 다중 사용자·인증·공용 DB/Lake 전환: `BLOCKED`
- 과학 실행·학습·배포: 실행하지 않음

## 1. 쉬운 설명

이 Gate는 **결과를 만드는 엔진이 아니라, 이미 만들어진 증거를 같은 방식으로 접수하고 검토하는 창구**다.

예를 들어 Sentinel 피복 결과와 KLHK 문서 상태는 내용이 다르지만, 둘 다 다음 질문에는 같은 형식으로 답해야 한다.

1. 어떤 원본과 증거 파일에서 왔는가?
2. 증거의 SHA-256과 byte 수가 등록 시점과 같은가?
3. 등록 후 만들어진 결과 ID로 동일한 내용을 다시 읽을 수 있는가?
4. 검토자가 수정 요청 또는 검토 완료를 남겼는가?
5. 검토 상태와 과학적 증거 상태를 혼동하지 않았는가?

실제 프로젝트 로컬 registry에는 **10개 결과**를 등록했고, 각 결과마다 `증거 검증 → 등록 → ID 재조회`의 3단계를 수행해 **30단계 모두 성공**했다. 실제 Microsoft Edge에서는 임시 DB를 사용해 결과 등록, 수정 요청, 검토 완료, 새로고침 후 필터·상세 재열기를 확인했다. 별도로 현재 로컬 `127.0.0.1:8014`에서는 프로젝트 registry의 **10개 결과·PENDING 10개·30단계 scope**와 One Map 상세 UX를 확인했고 JavaScript 오류는 0이었다.

가장 중요한 점은 다음이다.

> `ACCEPTED`는 “검토자가 이 등록 결과의 검토를 마쳤다”는 뜻이지, `BLOCKED`인 데이터가 과학적으로 사용 가능해졌다는 뜻이 아니다.

따라서 KLHK 결과를 검토 완료로 바꾸더라도 공식 native 23-class·사용권한이 없으면 증거 상태는 계속 `BLOCKED`다. Sentinel 결과를 등록해도 종료된 worker, 9번째 창 미정산, 약 99% 공간 공백은 사라지지 않는다.

## 2. 이론적 배경

### 2.1 내용 기반 불변 ID와 멱등성

결과 ID는 `domain`과 `source_key`에서 결정적으로 만든다. 동일한 입력을 다시 등록하면 같은 결과를 돌려주는 멱등성을 갖는다. 반대로 같은 ID에 다른 payload를 넣으려 하면 충돌로 거절한다. 이 방식은 재시도 때문에 같은 결과가 여러 건 생기는 문제를 줄인다.

### 2.2 증거 상태와 검토 상태의 직교성

두 상태는 서로 다른 질문에 답한다.

| 상태 축 | 답하는 질문 | 예시 |
|---|---|---|
| evidence state | 근거가 실제로 검증됐고 사용 조건을 충족하는가? | `VERIFIED_REAL`, `BLOCKED` |
| review status | 사람이 이 등록 결과를 검토했는가? | `PENDING`, `CHANGES_REQUESTED`, `ACCEPTED` |

따라서 `BLOCKED + ACCEPTED` 조합도 가능하다. 이는 “차단 사실과 근거를 검토자가 확인했다”는 뜻이다. `ACCEPTED`를 학습 승인·배포 승인·독립 정확도 통과로 번역하면 안 된다.

### 2.3 Append-only 검토 이력

검토는 기존 행을 덮어쓰지 않고 revision을 추가한다. 수정 요청 뒤 검토 완료를 남기면 두 사건이 모두 남는다. 예상 revision과 현재 revision이 다르면 낙관적 동시성 검사가 충돌을 막는다.

### 2.4 Fail-closed 증거 고정

등록 전 다음을 확인한다.

- 허용된 증거 경로인가?
- 실제 파일 SHA-256이 catalog와 같은가?
- 실제 byte 수가 catalog와 같은가?
- payload와 재조회 payload의 digest가 같은가?

하나라도 다르면 등록·다음 단계로 진행하지 않는다. 하지만 SHA 일치 자체는 데이터의 정확도·공간 대표성·라이선스를 보증하지 않는다.

## 3. 코드·데이터 동작

### 3.1 Registry

`services/results/registry.py`는 로컬 SQLite에 결과 snapshot과 검토 revision을 저장한다.

- 결과 snapshot은 불변으로 등록한다.
- 동일 payload 재등록은 같은 결과를 반환한다.
- 같은 ID의 다른 payload는 충돌 처리한다.
- 검토 상태는 `ACCEPTED` 또는 `CHANGES_REQUESTED` revision으로 추가한다.
- domain·review status·limit 필터로 목록을 조회한다.
- DB 기본 경로는 `data/curated/results/registry.sqlite3`다.

### 3.2 API

`services/api/results.py`는 loopback/local 요청만 허용하고 고정 source catalog와 증거 SHA·byte를 다시 확인한다.

| 동작 | 역할 |
|---|---|
| source 목록 | 등록 가능한 고정 증거와 현재 blocker를 보여 준다. |
| result 등록 | 증거 검증 후 불변 결과 snapshot을 등록한다. |
| result 목록·상세 | 등록 결과와 검토 상태·이력을 읽는다. |
| review 추가 | 수정 요청 또는 검토 완료 revision을 append한다. |
| workflow 조회 | 검증·등록·재조회 단계와 실행 여부를 보여 준다. |

이 API는 로컬 Gate이며 외부 과학 계산, 원격 수집, 학습, 배포를 호출하지 않는다.

결과가 등록된 뒤에는 같은 ID의 `GET /api/results/{id}/catalog`에서 수치·공간 layer·보고서·불확실성 패키지를 조회할 수 있다. 이 카탈로그의 scientific/publication 결정은 위의 일반 review status와 별개다. 실제 CCKP·BIG seed와 두 승인축의 현재 상태는 [결과 카탈로그와 이중 승인 Gate](V42_RESULT_CATALOG_AND_GOVERNANCE.md)를 따른다.

### 3.3 공통 Workflow

`services/api/result_workflow.py`는 모든 source에 대해 다음 순서를 강제한다.

1. 모든 증거를 먼저 검증한다.
2. 검증 단계가 모두 성공한 뒤 등록한다.
3. 등록 ID로 다시 조회한다.
4. 등록 payload와 재조회 payload digest가 같은지 확인한다.

실제 통합 증거 `evidence/results/result-registration-20261125-integrated.json`에는 10개 source와 30개 성공 단계가 고정돼 있다. 이는 **10개의 과학 작업이 실행됐다는 뜻이 아니라, 10개 기존 결과를 공통 경로로 등록하고 다시 읽었다는 뜻**이다.

### 3.4 UI 검토 흐름

`tests/api_ui/test_live_results.py`의 실제 Edge 검증은 격리된 임시 SQLite DB를 사용했다.

1. 고정 source 목록을 읽는다.
2. `BLOCKED` KLHK source를 등록한다.
3. 초기 review status `PENDING`을 확인한다.
4. `CHANGES_REQUESTED`를 남긴다.
5. 다음 revision으로 `ACCEPTED`를 남긴다.
6. evidence state가 여전히 `BLOCKED`인지 확인한다.
7. 새로고침 후 목록 필터와 상세·검토 이력을 다시 연다.
8. 학습·배포 버튼이 비활성인지 확인한다.

임시 DB의 검토 이력은 프로젝트 registry에 쓴 운영 결정이 아니다. 그래서 실제 프로젝트 `8014` 조회의 10개 결과는 모두 `PENDING`이다. UI 검토 시나리오와 실제 프로젝트 10개 결과 등록은 서로 다른 증거다.

### 3.5 현재 결과가 그대로 보존하는 blocker

| 도메인 | 현재 사실 | 판정 |
|---|---|---|
| RTRW | 현행 6개 지역 RTRW 0/6. Banten은 역사 샘플이며 BIG 93,340 record는 현행 6지역 RTRW 완료 증거가 아님 | `BLOCKED` |
| Sentinel | worker 종료, 8/36 수신·5 QA 통과, 9번째 West Java 2024 예약 32MiB 미정산, 429 0 | `BLOCKED` |
| KLHK | 공식 native 23-class domain·license·권한 미확보 | `BLOCKED` |
| RAG | 7문서·122 chunk private `synthetic-hash-64-v1`; public/운영 semantic 품질 미검증 | `IMPLEMENTED_UNVERIFIED` / public `BLOCKED` |
| MLOps | 원본 scene 1건이 validation과 test에 중복, 독립 정답 없음 | `BLOCKED` |
| Lake | 로컬 catalog·증거는 있으나 운영 DB/object store cutover 미검증 | `BLOCKED` |

WorldCover 2021은 약한 참조일 뿐 다른 연도의 정답이 아니다. WorldCover 또는 KLHK와의 weak agreement를 independent accuracy로 보고하지 않는다.

## 4. 테스트·증거

| 증거 | 확인한 내용 | 상태 |
|---|---|---|
| 실제 프로젝트 등록 증거 | 10개 result, verify/register/lookup 30단계 성공, 등록 ID와 재조회 ID 일치 | `VERIFIED_REAL` |
| 실제 Edge 선택시험 | 5 PASS; 임시 DB 등록 → 수정 요청 → 검토 완료 → 새로고침·필터·상세 재열기, page error 0 | `VERIFIED_REAL` |
| 실제 8014 프로젝트 조회 | 10 results, PENDING 10, 30단계 scope, One Map 상세 UX, JS error 0 | `VERIFIED_REAL` 로컬 제공 |
| registry/API 계약시험 | 멱등성, 충돌, revision, 상태·필터 계약 | `TESTED_SYNTHETIC` |
| 전체 pytest | 235 passed, 선택 browser 5건 기본 미실행 | 코드 회귀 증거; 별도 실제 Edge 5 PASS와 분리 |
| DOM 계약 | 2 PASS | UI 구조 계약; 실제 Edge와 분리 |
| Sentinel reconciliation | PID 종료, 8/36·QA 5, 9번째 pending reservation·미정산 | `VERIFIED_REAL` blocker 증거 |
| scene split audit | 원본 scene 1건이 validation/test에 중복, gate false | `VERIFIED_REAL` blocker 증거 |

검증되지 않은 것은 다음과 같다.

- 운영 다중 사용자 인증·권한과 외부 공개 API
- 공용 운영 DB/Lake cutover와 복구·가용성
- KLHK 공식 23-class·license·기관 승인
- public semantic RAG 품질
- 독립 ground truth와 독립 정확도
- 실제 모델 학습·추론·배포

## 5. 발표 스크립트

### 1분

“공통 결과 Gate는 서로 다른 도메인의 증거를 같은 형식으로 등록하고, 같은 ID로 다시 조회하며, 검토 이력을 남기는 기능입니다. 실제 프로젝트 registry에 10개 결과를 등록해 증거 검증·등록·ID 재조회 30단계를 모두 통과했고, 실제 Edge에서는 임시 DB로 등록·수정 요청·검토 완료·새로고침을 확인했습니다. 현재 로컬 8014는 프로젝트 결과 10개를 모두 PENDING으로 보여 줍니다. 하지만 검토 완료는 과학적 차단 해제가 아닙니다. 현재 RTRW는 0/6, Sentinel은 worker 종료 후 8/36과 9번째 미정산, KLHK 공식 23클래스·권한은 미확보, scene split에는 validation/test 중복이 있습니다. 학습·배포는 실행하지 않았습니다.”

### 5분

1. 목표는 결과 생성이 아니라 고정 증거의 접수·조회·검토 표준화다.
2. 결과 ID는 결정적이며 같은 payload 재등록은 멱등, 다른 payload는 충돌이다.
3. 검토 revision은 append-only이고 낙관적 동시성으로 충돌을 막는다.
4. evidence state와 review status를 분리해 `BLOCKED + ACCEPTED`를 정확히 표현한다.
5. 실제 프로젝트 10개 결과에 verify/register/lookup 30단계를 수행했고 ID 재조회를 확인했다.
6. 실제 Edge는 임시 DB에서 수정 요청·검토 완료·새로고침을 확인했으며 프로젝트 registry의 운영 결정과 분리한다.
7. 실제 8014 조회는 프로젝트 결과 10개·PENDING 10개·30단계 scope·One Map 상세를 오류 없이 보여 준다.
8. RTRW·Sentinel·KLHK·RAG·MLOps·Lake blocker는 등록 후에도 그대로다.
9. WorldCover 2021 약한 참조를 타연도 정답으로 쓰지 않으며 독립 정확도는 별도 평가자료로 측정해야 한다.

## 6. Q&A

**Q. 결과 10개가 등록됐으니 10개 분석이 새로 실행됐습니까?**
아니다. 기존 고정 증거 10개를 공통 경로에 등록하고 ID로 다시 읽었다. 외부 요청·학습·배포 실행은 0이다.

**Q. `ACCEPTED`면 학습에 써도 됩니까?**
아니다. `ACCEPTED`는 검토 이력 상태다. evidence state가 `BLOCKED`면 학습·배포는 계속 차단된다.

**Q. Edge에서 검토 완료한 내용이 프로젝트 운영 DB에 저장됐습니까?**
아니다. UI 검증은 격리된 임시 SQLite DB를 사용했다. 실제 프로젝트 registry 등록과 UI 검토 이력은 분리된 증거다.

**Q. RTRW가 등록됐으니 6개 지역 자료가 확보됐습니까?**
아니다. 현행 RTRW는 0/6이다. Banten 역사 샘플과 BIG 93,340 record를 현행 6지역 RTRW 완료로 확대하지 않는다.

**Q. Sentinel 배치는 계속 실행 중입니까?**
아니다. 12:05 KST reconciliation에서 worker PID가 사라진 것을 확인했다. 8/36 수신, 5 QA 통과이며 9번째 창은 예약 32MiB의 실제 전송량이 미확정이다.

**Q. 429가 없으면 Sentinel 배치는 성공한 것 아닙니까?**
아니다. 429는 0이지만 worker가 정산 전에 종료됐다. pending transfer를 검증·정산하기 전 재개하거나 완료로 처리하면 안 된다.

**Q. MLOps Gate가 있으면 학습을 시작할 수 있습니까?**
아니다. 동일 원본 scene이 validation과 test에 겹치고 독립 정답이 없다. scene split gate는 `BLOCKED`다.

**Q. WorldCover 2021과 일치하면 정확도입니까?**
아니다. 약한 참조 일치도이며 타연도 독립 정답이 아니다. independent accuracy는 분리된 현장·전문가 라벨로 평가해야 한다.
