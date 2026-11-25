# 기관 운영 화면 연계 (2026-11-25)

상태: IMPLEMENTED_UNVERIFIED(실제 API·브라우저 적용은 root 인계). 합성 클라이언트 계약시험은 TESTED_SYNTHETIC이다. 커밋/푸시·수집·기관 job 제출/취소·모델 활성/롤백을 실행하지 않았다.

- 기존 React step22 작업·알림에 InstitutionJobs를 추가하고 기존 ResourceList를 유지한다.
- step17/18 모델 운영에 ModelReleases 조회를 추가하고 기존 ModelMlopsWorkspace와 전문가 화면을 유지한다.
- 기존 step1 DataCatalogReference 내부에 InstitutionSources 조회 요약을 추가한다.
- GET /api/jobs 및 /api/jobs/approvals를 5초마다 읽는다. 실제 유효 승인 목록만 선택하고 POST /api/jobs {approval_id}, POST /api/jobs/{id}/cancel을 사용자 클릭으로만 보낸다. 자동 제출·재시도는 없다. 취소 요청과 실제 취소 완료는 구분한다. 서버 job.state/progress/blockers/result_id/package_sha256/model/updated_at을 표시한다.
- 운영 토큰은 password input과 useState 메모리에만 존재한다. URL·저장소·로그에 기록하지 않는다. GET에 토큰을 보내지 않고 승인 POST에만 Bearer로 전달한다. 성공 후 자동 삭제하고 수동 삭제도 지원하며 화면 이탈 시 컴포넌트와 함께 폐기한다. 헤더 오류에 토큰이 노출되지 않도록 형식 검사 및 일반화한 연결 오류만 표시한다.
- job 결과 링크는 안전한 ID를 검증한 #/reports/results?result_id=...이다. 기존 공통 결과 컴포넌트가 동일 ID만 조회하고 abort/generation 검사를 적용한다. URL은 결과 데이터·패키지 SHA·권한의 근거가 아니다.
- GET /api/model-releases의 버전·manifest SHA·활성버전·revision·execution_ready·이력을 조회한다. 데이터가 없으면 미지정/미제공으로 표시한다. 이력은 서버 최신순을 유지하며 승인 쓰기 UI는 추가하지 않는다. 서버는 실행 직전에 증거 drift·과학검증 gate를 재검증한다.
- GET /api/institution-sources의 public_summary만 표시한다. evidence verification과 publication gate/public_search를 구분하고 비공개 본문·현재 수집완료를 추정하지 않는다.

## 프록시·실행

VITE_OPERATIONS_PROXY_TARGET은 로컬 HTTP origin만 허용한다. 기본은 VITE_RESULTS_PROXY_TARGET 또는 http://127.0.0.1:8014이다. /api/jobs, /api/model-releases, /api/institution-sources 경로만 기존 broad /api 프록시보다 먼저 매칭한다. 기존 결과 프록시와 나머지 legacy 8002 대상 설정은 보존한다. Vite 설정 적용에는 root가 dev server를 재시작해야 한다. 본 담당은 활성 서버·collector를 종료하지 않았다.

```powershell
# E:\SDSS-Platform2\frontend
node tests/institution-operations.contract.cjs
.\node_modules\.bin\tsc.cmd -b --pretty false
npm run build
```

주요 testid: institution-jobs, ops-jobs-state, ops-token, ops-approval, ops-submit, ops-job, ops-cancel, ops-result-link, model-releases, release-status, institution-sources.

root 실제 클릭 검증: 작업·알림에서 서버 차단/승인 목록 조회 → 토큰 없이 제출 disabled 확인 → 승인된 격리 환경에서만 명시 토큰 입력/제출/취소 확인 → 실제 job 결과 링크에서 동일 공통 결과 ID 확인 → 모델 운영에서 활성/rollback/readiness 근거 조회 → Data Catalog 기관별 검증/공개승인 분리 확인. 운영 token·자격정보를 스크린샷·증거에 남기지 않는다. API가 미설정이면 BLOCKED를 성공으로 대체하지 않는다.

App의 경로 정규화도 검증된 result_id만 보존하도록 수정했다. 같은 결과 링크를 누른 뒤 query가 사라져 상세 선택을 잃는 문제를 방지한다. 응답 job ID와 승인 ID를 요청과 대조하고, 허용 job state/진행률 범위/모델·패키지 SHA 형식을 검증한다.
## 이번 담당 검증 결과

- `node tests/institution-operations.contract.cjs`: TESTED_SYNTHETIC PASS. 실제 클라이언트 함수를 Node에서 변환·실행하며 안전 ID/링크·응답 validator·GET 토큰 미전송·POST Bearer·경로 제한·legacy 목록 보존을 검증했다. fixture 토큰은 임의 합성 문자열이며 운영 자격정보가 아니다.
- `npm run build`: exit 0. TypeScript 검사 후 Vite 6.4.4가 138 modules를 빌드했다. Vite 출력 시간 3m7s, CSS 258.04 KB, JS 1,920.18 KB. 500 KB 초과 chunk 경고가 남으며 성능 최적화는 별도 범위다.
- 실행 중 Vite 재시작·기관 job 제출/취소·모델 쓰기·collector 중단·커밋/푸시는 하지 않았다.
- 읽기 전용 실제 HTTP 확인: API8014 및 기존 Vite5175를 통해 `/api/jobs`, `/api/model-releases`, `/api/institution-sources` 모두 HTTP200 (6요청) 확인했다. jobs는 `BLOCKED / JOB_PROVIDER_CONFIG_NOT_SET`, model-releases는 `BLOCKED / APPROVED_MODEL_VERSION_UNAVAILABLE`, sources는 `{schema_version,sources}`의 public summary다. HTTP200은 기관 운영 작업 준비 완료가 아니다. 제출·취소·승인 쓰기는 수행하지 않았다. 이것은 실제 Edge 렌더·클릭 검증과 별도다.
- 실제 Edge 5175에서 승인 작업 목록의 차단 상태와 새로고침, 모델 이력 조회, 기관 자료 6종의 상태 조회, 같은 결과 ID로 CCKP 지표 열기를 확인했다. 승인 쓰기와 실제 외부 공급자 제출은 수행 권한이 구성되면 별도 확인한다.
