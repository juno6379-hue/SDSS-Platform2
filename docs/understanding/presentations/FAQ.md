# v4.2 발표 FAQ

**Q. 이제 실제 CCKP 수치를 답할 수 있습니까?**
제한적으로만 가능합니다. 실제 검증값은 1951–1980 CDD climatology의 개발 bbox 평균 40.91221481742199 days 한 건입니다. 다른 변수·기간·모델은 별도 검증 없이는 답하지 않습니다.

**Q. CCKP 연동에서 실제 검증한 범위는 무엇입니까?**
공개 S3 목록·HEAD에 이어 global ERA5 CDD NetCDF 4,209,592B를 Range 17개로 취득하고 SHA·CF·기간·단위와 개발 bbox 통계를 검증했습니다. 국가별 object나 공식 행정경계 통계는 아닙니다.

**Q. climate feature가 생성됐습니까?**
아닙니다. as-of·ACL·CF 달력·CRS·bbox 후보를 검사하는 계획기만 있습니다. 실제 공간 join·numeric feature·학습·배포는 0건이며 `execution_started=false`, `numeric_features=null`입니다.

**Q. 71 PASS가 과학 정확도를 뜻합니까?**
아닙니다. 71건은 schema·ACL·citation·routing 등의 합성 계약시험입니다. 별도 실원본 재현 2건도 CDD 계산 재현성이지 모델 독립 accuracy 검증은 아닙니다.

**Q. 문서에 있는 숫자를 RAG가 인용하면 되지 않습니까?**
수치 질문은 단위·달력·격자·모델·시나리오·집계 조건 검증이 필요합니다. 이 구현은 RAG numeric payload를 금지합니다.

**Q. authority가 같다고 검사했으니 공식 기관 인증입니까?**
아닙니다. 노드·관계와 source span의 authority 문자열 결속입니다. 실제 기관 소유권·법적 효력·승인은 별도입니다.

**Q. hybrid vector 검색은 운영 embedding입니까?**
아닙니다. 현재 vector는 합성 feature hashing이며 `TESTED_SYNTHETIC`입니다. 다국어 semantic 성능은 미검증입니다.

**Q. restricted 문서가 공개 검색에 섞입니까?**
코드상 ACL을 scoring 전에 적용하는 계약을 시험했습니다. 실제 로그인·토큰·role 발급과 timing side-channel은 후속입니다.

**Q. WorldCover 2021은 다른 연도 정확도 정답입니까?**
아닙니다. 약한 참조이며 기관 참조 일치도와 독립 현장 정확도를 구분해야 합니다.

**Q. UI와 실서비스까지 완료됐습니까?**
아닙니다. 현재 근거는 Python 내부 계약과 합성 시험입니다. API/UI·운영 배포는 별도 Gate입니다.

**Q. KLHK 2024·2025 layer는 23클래스 정답입니까?**

아닙니다. 연도와 metadata 접근은 실제 확인했지만 renderer가 25항목이고 native 23-class coded domain과 license는 확인되지 않았습니다.

**Q. 실제 원본 7개는 운영 RAG에 게시됐습니까?**

아닙니다. 122개 span과 KG sidecar까지 보존했지만 public index publication은 0입니다. 기관 authority·license·ACL·validity와 운영 embedding 검토가 남았습니다.

**Q. WorldCover 또는 KLHK 일치도가 배포 정확도입니까?**

항상 그렇지 않습니다. 약한 참조 일치도와 독립 지상정답 정확도를 분리해야 하며, WorldCover 2021은 다른 연도의 독립 정답이 아닙니다.

**Q. MLOps 6 PASS는 실제 모델 배포 성공입니까?**

아닙니다. Gate 규칙의 합성시험입니다. 현재 실측 공간피복 7.711080%는 학습을 차단하며 실제 학습·독립정확도·배포는 0건입니다.

상세 근거: [v4.2 기후 계약·RAG 이해자료](../V42_CLIMATE_FOUNDATION_AND_RAG.md)

추가 근거: [KLHK 문서 ingestion과 학습·배포 Gate](../V42_KLHK_RAG_MLOPS_GATES.md)

**Q. 40.91221481742199 days가 인도네시아 국가 평균입니까?**

아닙니다. `[95,-11,141,6]` bbox의 native full-cell 구면가중 평균이며 공식 행정경계 polygon, 해양 제외, 부분셀 clip을 적용하지 않았습니다.

**Q. 매년 또는 매월 CDD를 계산한 것입니까?**

아닙니다. 원본이 제공한 time 1개의 1951–1980 climatology 공간 평균입니다. 연별·월별 값을 추론하지 않습니다.

**Q. ERA5 결과로 독립 정확도를 검증했습니까?**

아닙니다. ERA5는 재분석이며 독립 현장 ground truth가 아닙니다. 별도의 공간 holdout·동년·라벨원천 분리 자료가 필요합니다.

**Q. climate.query가 실서비스에서 호출됩니까?**

아닙니다. 로컬 library/CLI와 증거 재현만 검증했습니다. HTTP/RAG live 등록, 학습, 배포는 0건입니다.

추가 근거: [CCKP Indonesia 개발 bbox 수치 도구](../V42_CCKP_INDONESIA_NUMERIC_TOOL.md)

**Q. 36/36 감사 통과는 공간 수집 완료입니까?**

아닙니다. 각 지역·연도 셀이 최소 28개 패치를 가진다는 뜻입니다. post-pilot paired 피복은 0.9773249834093871%, clear 피복은 0.890386955270514%라 약 99% 공간 공백이 남습니다.

**Q. CAS 6,125개·3.904GB는 새 Sentinel 다운로드입니까?**

아닙니다. 기존 로컬 산출물의 copy 이관이며 원격 다운로드와 ledger write는 0건입니다.

**Q. Edge에서 UI를 클릭했으니 운영 배포도 검증됐습니까?**

아닙니다. 이전 snapshot과 post-pilot 화면, 공통 결과 Gate를 로컬 Edge에서 확인했습니다. 이는 로컬 연결·상태·검토 흐름 증거이며 인증·다중 사용자·운영 가용성은 검증하지 않았습니다.

**Q. 모델 adapter와 오케스트레이터가 통과했으니 학습을 시작할 수 있습니까?**

아닙니다. 둘은 `TESTED_SYNTHETIC` 계약입니다. 23-class mapping, data readiness, 독립 평가자료, checkpoint, 재현 환경과 실제 adapter가 없어 학습·추론·배포를 차단합니다.

**Q. private VectorDB는 운영 semantic RAG입니까?**

아닙니다. 7개 문서·122개 chunk를 `synthetic-hash-64-v1`로 고정한 private review index이며 의미 검색 품질은 `IMPLEMENTED_UNVERIFIED`입니다. public search와 numeric answer는 비활성입니다.

**Q. weak agreement와 independent accuracy의 차이는 무엇입니까?**

weak agreement는 WorldCover나 KLHK 같은 참조와의 일치도입니다. independent accuracy는 모델·참조 생성과 분리된 지상정답과 평가 protocol로 측정해야 합니다. WorldCover 2021은 다른 연도의 정답이 아닙니다.

추가 근거: [최종 통합 상태](../V42_FINAL_INTEGRATION_STATUS.md)

**Q. reservation adapter와 scene pin은 아직 미구현입니까?**

아닙니다. East Java 2023 단일 pilot에서는 예약·exact scene/asset/window pin·bounded I/O·실측 정산을 실제 완료했습니다. 전체 36셀 반복 수집 승인과 예산은 별도입니다.

**Q. clear 100%는 East Java 전체 품질입니까?**

아닙니다. 고정 scene의 256×256 window 한 곳, 65,536 pixel에만 해당합니다.

**Q. pilot 후 기존 0.976741% coverage가 바뀌었습니까?**

예. 후속 exact geometry 재감사에서 0.9773249834093871%로 계산했습니다. 0.976741%는 pilot 이전 snapshot이며 둘 다 각 시점의 실제 감사값입니다.

**Q. 잔액 1,678,521,030B면 전체 공간을 채울 수 있습니까?**

확정할 수 없습니다. byte 잔액은 실제 확인했지만 전체 gap 비용과 BIG·수집 승인이 검증되지 않았습니다.

**Q. pilot 결과는 독립 정확도 또는 학습 준비 증거입니까?**

아닙니다. SCL clear QA일 뿐이며 `learning_ready=false`, `independent_ground_truth=false`입니다. WorldCover 2021도 타연도 ground truth로 사용할 수 없습니다.

추가 근거: [Sentinel 단일 실제 pilot](../V42_SENTINEL_SINGLE_PILOT.md)

**Q. clear coverage의 현재 재감사값은 무엇입니까?**

0.890386955270514%입니다. pilot 전 0.8898034032819104%보다 늘었지만 full spatial coverage는 false입니다.

**Q. 44,829,036B는 전체 남은 공간 수집량입니까?**

아닙니다. pilot 실측 7,471,506B짜리 창을 6개 추천 후보에 하나씩 적용한 산술 참고값입니다. 전체 gap 전송량, 비용, 승인과 예산 충분성은 미확정입니다.

**Q. 재감사에서 원격 수집이나 원장 변경이 발생했습니까?**

아닙니다. collector·remote download·ledger write 모두 0이며 실 저장 geometry를 읽어 계산했습니다.

**Q. post-pilot API/UI도 실제 검증됐습니까?**

예. 로컬 API와 실제 Edge에서 36행·6후보·42.75MiB 표시를 확인했습니다. 다만 운영 배포·인증·다중 사용자 검증은 아닙니다.

추가 근거: [Sentinel pilot 반영 36셀 재감사](../V42_SENTINEL_POST_PILOT_REAUDIT.md)

**Q. 후속 배치의 36개 창은 모두 완료됐습니까?**

아닙니다. 36개는 계획 수입니다. 11:44 KST의 3/36·QA 2는 역사적 snapshot이며, 12:05 KST 최신 reconciliation은 8/36·QA 5와 worker 종료를 확인했습니다.

**Q. 첫 East Java 창의 clear 49.47%는 전송 실패입니까?**

아닙니다. 동일 scene의 6밴드+SCL 7개와 계측이 완전하고 429·오류가 없는 품질 미달 관측입니다. quality gap으로 분리해 학습 적격에서 제외하고 다음 창을 계속합니다.

**Q. 어떤 경우 배치를 멈춥니까?**

HTTP 429 또는 asset 누락·불완전 계측 같은 실제 전송 실패에서 멈춥니다. 완전 전송 SCL 80% 미달은 별도 기록하고 계속합니다. 현재는 worker가 9번째 창 정산 전에 종료돼 pending transfer의 실제 byte를 확인할 때까지 차단됐습니다.

**Q. 배치 신규 면적이 전역 피복률에 반영됐습니까?**

아직 아닙니다. 8개 observation이 저장됐지만 최신 면적·byte는 9번째 pending transfer와 분리해 재감사해야 합니다. 후속 aggregate 재감사 전 전역값은 0.9773249834093871%와 0.890386955270514%입니다.

**Q. 수집된 창은 바로 학습자료입니까?**

아닙니다. 새 training-eligible patch는 0입니다. label source와 독립 ground truth가 없고 WorldCover 2021은 다른 연도 정답이 아닙니다.

추가 근거: [Sentinel 경계 내 후속 배치](../V42_SENTINEL_BACKGROUND_COVERAGE_BATCH.md)

**Q. 공통 결과 10개 등록은 10개 분석을 새로 실행한 것입니까?**

아닙니다. 기존 고정 증거 10개를 검증·등록하고 같은 ID로 다시 읽은 것입니다. 30단계는 source마다 verify/register/lookup 3단계이며 외부 수집·학습·배포는 0입니다.

**Q. 결과가 `ACCEPTED`면 과학적 차단도 해제됩니까?**

아닙니다. review status와 evidence state는 별도입니다. `BLOCKED + ACCEPTED`는 차단 사실을 검토자가 확인했다는 뜻이며 학습·배포 승인이 아닙니다.

**Q. Edge에서 남긴 검토 이력이 프로젝트 운영 결정입니까?**

아닙니다. 수정 요청·검토 완료 흐름은 격리 임시 DB에서 검증했습니다. 실제 프로젝트 8014의 10개 결과는 모두 `PENDING`입니다.

**Q. 공통 결과 화면은 실제로 검증됐습니까?**

예. 별도 실제 Edge 선택시험 5건과 DOM 계약 2건이 통과했고, 로컬 8014에서 10 result·PENDING 10·30단계 scope·One Map 상세 UX와 JavaScript 오류 0을 확인했습니다. 다만 운영 인증·다중 사용자·공용 DB/Lake 전환은 검증하지 않았습니다.

**Q. RTRW 결과가 등록됐으니 6개 지역 RTRW가 확보됐습니까?**

아닙니다. 현행 RTRW는 0/6입니다. Banten 역사 샘플과 BIG 93,340 record를 현행 6지역 RTRW 완료로 확대하지 않습니다.

**Q. MLOps 결과가 등록됐으니 split이 안전합니까?**

아닙니다. 실제 audit에서 동일 원본 scene 1건이 validation과 test에 겹쳐 scene split gate가 차단됐습니다. 독립 정답도 없습니다.

추가 근거: [공통 결과 등록·검토·조회 Gate](../V42_COMMON_RESULT_REVIEW_GATE.md)

**Q. `CATALOG_READY`면 결과를 바로 공개할 수 있습니까?**

아닙니다. 고정 패키지가 결과 ID에 붙었다는 뜻입니다. 현재 패키지에 대한 과학축과 게시축의 승인이 모두 있어야 `release_eligible`이 됩니다.

**Q. CCKP `40.91221481742199 days`는 인도네시아 국가 평균입니까?**

아닙니다. 개발 bbox `[95,-11,141,6]`의 0.25° full-cell 12,765개에 대한 1951–1980 climatology 구면가중 평균입니다. 행정경계 평균·연별·월별 값이 아닙니다.

**Q. GeoJSON 점 12,765개는 독립 관측소입니까?**

아닙니다. ERA5 재분석 격자의 중심점입니다. 독립 관측 ground truth나 행정구역 표본이 아닙니다.

**Q. 반텐 폴리곤 1개가 있으면 현행 RTRW를 쓸 수 있습니까?**

아닙니다. 2017 조례 표기의 역사 표본이며 현행 효력 기간·권리·반텐 전체성·위치 정확도가 확인되지 않았습니다.

**Q. 불확실성 `NOT_REPORTED`는 오차가 0이라는 뜻입니까?**

아닙니다. 신뢰구간·독립 관측 오차 또는 위치 정확도를 산정하지 않았다는 뜻입니다.

**Q. 공통 결과의 `ACCEPTED`와 과학축 `APPROVED`는 같은 상태입니까?**

아닙니다. 일반 업무 검토, 독립 과학 검토, 기관 게시 승인은 서로 다른 결정축입니다.

**Q. 과학·게시 승인 API가 구현됐으니 실제 기관 승인도 끝났습니까?**

아닙니다. API 계약은 합성시험 6건으로 검증했지만 실제 기관 authority·token·결정 근거와 승인은 아직 `BLOCKED`입니다. 두 실제 seed의 두 승인축은 모두 `PENDING`입니다.

추가 근거: [결과 카탈로그와 이중 승인 Gate](../V42_RESULT_CATALOG_AND_GOVERNANCE.md)

**Q. `/api/jobs`가 HTTP 200이면 기관 작업을 실행할 수 있습니까?**

아닙니다. 본문이 `BLOCKED`이고 `JOB_PROVIDER_CONFIG_NOT_SET`이면 조회 API가 차단 상태를 정상 설명한 것입니다. 실제 공급자 작업 성공이 아닙니다.

**Q. 기관 작업 시험 8건이 통과했으니 실제 기관 endpoint도 검증됐습니까?**

아닙니다. 멱등 제출·재개·취소·model pin·asset SHA·결과 등록을 격리 시험한 것입니다. 실제 endpoint·token·승인 원본·인수시험은 없습니다.

**Q. 기관 원천 6종이 `VERIFIED_REAL`이면 외부에 공개할 수 있습니까?**

아닙니다. 제한된 로컬 파일 SHA·byte가 실제라는 뜻입니다. RTRW·CCKP·Lake·KLHK·private index·Sentinel 모두 publication gate가 차단되고 public search는 false입니다.

**Q. KLHK 문서 7개는 토지피복 연차 원본 7개입니까?**

아닙니다. 기존 취득 보고서에 포함된 CCKP 문서 5개와 KLHK metadata 2개의 합입니다. native 23-class 검증은 0입니다.

**Q. scene 충돌 0이면 바로 학습해도 됩니까?**

아닙니다. 1,779행에서 충돌 scene 전체를 빼 1,751행·적격 1,382행을 만든 후보일 뿐입니다. 지리 중첩·피복·독립 라벨이 남았고 `training_allowed=false`입니다.

**Q. 합성 ONNX 출력 11→12→11은 실제 모델 성능 향상입니까?**

아닙니다. 입력 10에 상수 1 또는 2를 더하는 합성 그래프로 활성 버전 선택과 rollback을 확인한 것입니다.

**Q. 활성 모델의 과학 승인이 나중에 철회되면 계속 실행됩니까?**

아닙니다. 실행 직전에 카탈로그 승인과 증거를 다시 검사하므로 이후 실행을 차단합니다.

**Q. API 8014·Vite 5175 HTTP 200과 build 통과는 실제 Edge 클릭 증거입니까?**

아닙니다. 세 운영 경로와 138-module build의 연결 증거입니다. 실제 브라우저 E2E는 Root 확인이 끝날 때까지 `PLANNED`입니다.

**Q. SeaweedFS에서 실제 JSON을 읽었으니 운영 Lake 전환이 끝났습니까?**

아닙니다. 이후 개발 Compose에서 실제 PostGIS·pgvector schema, S3 projection과 CCKP 보고서 3,295B signed SHA readback, 무인증 403까지 확인했고 로컬 Kubernetes 이식도 완료했습니다. 그러나 기관 DB·버킷·IAM/SSO·백업/복구·RPO/RTO 인수는 없으므로 운영 Lake cutover는 `BLOCKED`입니다.

**Q. Docker 5180과 Kubernetes 5181에서 열리면 기관 운영 배포가 끝난 것입니까?**

아닙니다. 같은 이미지와 읽기전용 원본, 3 PVC, 공통 결과·jobs·반텐 결과와 실제 광학 12개 레이어를 로컬 환경에서 재현한 기술 이식 증거입니다. 실제 기관 provider·비밀값·운영 클러스터 인수와 과학 승인은 별도입니다. 기존 5175도 계속 별도로 실행됩니다.

**Q. PostgreSQL jobs 10 PASS는 실제 기관 작업 10건입니까?**

아닙니다. 실제 개발 PostgreSQL을 사용했지만 기관 응답은 모의입니다. 패키지 Worker `--once`도 승인된 대기 작업이 없어 `jobs_checked=0`으로 안전 종료했으며 무승인 작업을 실행하지 않았습니다.

추가 근거: [운영 경로 2~8](../V42_OPERATION_PATH_2_TO_8.md)

**Q. KLHK 공식 23클래스가 실제 확인됐습니까?**

코드 사전은 실제 확인했다. 정확히는 토지피복 22개와 구름 품질코드 `2500 Awan` 1개다. 그러나 2024·2025 연차 원본의 native coded domain·사용권·운영 승인은 별도이며 현재 `BLOCKED`다.

**Q. renderer 25항목과 공식 23코드가 왜 다릅니까?**

renderer의 심볼 항목과 원본 필드의 coded-value domain은 다른 층이다. renderer 개수만으로 연차 원본이 공식 23코드라고 승인하거나 반대로 사전이 틀렸다고 단정하지 않는다.

**Q. KLHK→legacy-9 crosswalk는 공식 대응표입니까?**

아니다. `IMPLEMENTED_UNVERIFIED` 잠정 보수표다. 명확한 11개 코드만 대응하고 12개는 제외하며, 명시적 opt-in과 별도 승인 없이는 적용을 차단한다.

**Q. 변화 엔진 4 PASS는 실제 KLHK 변화량 검증입니까?**

아니다. 동일 격자의 합성 2020→2025 GeoTIFF에서 공통 유효면적·전이행렬·hotspot·구역통계를 재현한 계약시험이다. 예시 4ha 변화는 실제 지역 수치가 아니다.

**Q. UI fixture의 25% 변화율은 실제 어느 지역 값입니까?**

어느 지역 값도 아니다. exact pair·preview·catalog 연결을 확인하는 합성 fixture 수치다.

**Q. LCLUC 최종 회귀 37 PASS는 실제 운영 분석 완료를 뜻합니까?**

아니다. 분류사전·변화·등록을 포함한 회귀시험 묶음이다. 4ha 공통 유효·1ha 변화·25%는 격리 합성 fixture 수치이며 실제 지역 변화가 아니다. 이후 별도 Esri 반텐 실제 표본 1건을 등록했지만 전국 운영 분석 완료는 아니다.

**Q. LCLUC A–D 화면은 실제 Edge에서 확인했습니까?**

이전 좌우 두 지도 구현은 실제 Edge에서 격리 합성 A–D 이미지와 68% 스와이프, 4ha 공통 유효·1ha 변화·25%, CSV, 2023 미등록 차단과 동일 결과 ID 카탈로그를 확인했다. 이후 단일 지도 50:50 교정과 기존 Workspace 복원도 별도 Edge에서 확인했으며, 가장 최근에는 반텐 Esri 전역 6개 연도와 대표 2020→2025 결과까지 실제 화면에서 검증했다. 합성 시험과 실제 전역 결과는 서로 다른 증거로 읽는다.

**Q. 현재 연도 비교 지도는 어떻게 동작합니까?**

한 지도에서 왼쪽은 기준 연도, 오른쪽은 비교 연도를 같은 위치에 mask해 보여 준다. 50:50 구분선은 네이티브 드래그와 키보드로 움직인다. 자료가 없으면 기존 geoBoundaries 2017 ADM1 주 경계 위에 두 선택 연도의 `토지피복 미등록` 배지를 표시한다. Edge 5175에서 실제 반텐 경계·2020/2025 미등록·동자바 전환과, 격리 합성 50% 양면 mask·390px 포인터 드래그·2023 이미지/수치 없음·JS 오류 0을 확인해 `TESTED_SYNTHETIC`이다.

**Q. 5175 화면에 KLHK 코드가 보이면 운영 연차자료가 등록된 것입니까?**

아니다. 구름 품질코드를 포함한 공식 KLHK 분류사전 표시를 확인한 것이다. 현재 실제 등록 사례는 Esri 반텐 고정 표본이며 KLHK 연차 native domain·license·기관 승인 자료는 0건이다. 실제 RF/U-Net 학습도 별도다.

**Q. Random Forest와 Tiny U-Net이 구현됐으면 실제 모델을 배포할 수 있습니까?**

아니다. 분류기 전용 시험 12건이 361.37초에 통과했고, 두 모델 모두 동일 합성 holdout 유효 252픽셀에서 mIoU 0.50 이상을 기록했으며 모델 SHA 저장·복원도 확인했다. 그러나 이는 `TESTED_SYNTHETIC` 증거다. 승인된 연차자료, 동년 독립 라벨, 22개 주제 클래스의 실제 표본, 과학·게시 승인이 없으며 독립 정확도는 산출하지 않았다.

**Q. 두 분류기의 합성 mIoU가 0.50 이상이면 독립 정확도 50%입니까?**

아니다. 같은 합성 holdout 252픽셀에서 계산한 회귀시험 지표다. 실제 현장·전문가 라벨과 분리된 동년 시험셋이 아니므로 `independent_accuracy`는 미산출이다.

**Q. 모델의 최대확률과 entropy는 신뢰구간입니까?**

아니다. 현재 출력은 calibration되지 않은 보조값이다. 실제 오류확률이나 독립 정확도로 해석할 수 없다.

**Q. WorldCover 2021로 2024·2025 정확도를 평가할 수 있습니까?**

없다. WorldCover 2021은 2021년 약한 참조일 뿐 타연도 독립 정답이 아니다. weak agreement와 independent accuracy를 분리한다.

**Q. LCLUC Edge A~D가 검증됐습니까?**

이전 좌우 두 지도 구현의 Edge A–D·CSV·차단 경로와 단일 지도 합성 비교는 `TESTED_SYNTHETIC` 역사로 남는다. 이후 실제 Esri 반텐 고정 표본과 센서 원천을 등록해 Explorer 실자료 흐름도 별도로 검증했다.

**Q. Explorer의 반텐 4.58%는 반텐주 전체 실제 변화율입니까?**

아니다. 이는 앞서 등록한 Esri v003 2020·2025 고정 표본의 공통 유효 712.30ha 중 32.65ha 변화율이다. 역사적 표본 결과 ID는 `f9f3824d49505e52a35989389140e2973b43efd852320145e44945484f4d605a`다. 이후 반텐 전역 6개 연도와 별도 대표 2020→2025 전역쌍을 검증했으며 두 결과를 섞지 않는다.

**Q. Explorer에 어떤 실제 영상이 있고 브라우저에서 확인했습니까?**

반텐 Sentinel-2와 Landsat 8의 두 시점씩 6밴드+QA native 창, 팔루 NASA 사건 전후 JPEG 2장을 보존했다. Edge 5175에서 Esri 50:50·7분류 mask·시점 선택/재생·비중표, 세 자료 전환과 ZIP 다운로드·구조, 2023 미등록 차단, JavaScript 오류 0을 확인했다. 팔루는 시각 판독 전용이고 NLCD는 미국 범위라 제외하며 KLHK는 미등록이다.

**Q. Explorer가 전국 임의 위치의 동적 변화통계를 계산합니까?**

아니다. 검증 범위는 반텐 전역 고정 AOI와 별도 팔루 영상까지 확장됐지만, 카메라 이동·확대에 따른 전국 임의 영역 서버 재집계는 아직 없다.

**Q. 복원된 기존 LCLUC Workspace도 실제 브라우저에서 확인했습니까?**

예. Edge 5175에서 기존 7개 탭·4개 KPI, 50:50 slider·Time-Series, 범례 checkbox, Sentinel-2·Landsat 8·팔루 preview와 ZIP, 시계열 비중표·전환행렬·내보내기, 2023 미등록과 JavaScript 오류 0을 확인했다.

**Q. One Map 경계는 몇 개이며 지도에서 무엇을 직접 확인했습니까?**

API 원본은 6개 주와 129개 군·시다. 양쪽 지도 각각에서 Banten, Jawa Barat, Jawa Timur, Gorontalo, Sulawesi Selatan, Sulawesi Tenggara의 주 이름과 Tangerang·Kota Tangerang 군시 이름을 직접 확인했다. 클릭 선택은 이 증거로 검증하지 않았고 사업통계 사용 승인은 대기다.

**Q. Esri 9색의 Clouds와 NoData도 변화면적에 포함됩니까?**

아니다. 8개만 면적 클래스다. code 10 Clouds는 두 시점 68/0픽셀로 품질 항목이며 유효 면적에서 제외한다. NoData code 0은 투명하게 표시한다. 이 구분은 독립 정확도 검증을 뜻하지 않는다.

**Q. 반텐 Snow/ice 차트가 0ha 가까이 나오면 실제 눈이 있었다는 뜻입니까?**

아니다. Esri v003 code 9 집계는 2020~2025년에 `0.04, 0, 0.03, 0.05, 0, 0.12ha`, 즉 10m 픽셀 `4, 0, 3, 5, 0, 12개`다. 이는 원본 분류 결과이며 현지 적설·결빙을 검증하지 않았다. Edge에서 실제 6점의 0~1ha 축·정확한 소수 label·Total Valid Area 대조와, 전부 0인 합성 6점의 수평 기준선을 확인했다. 시각화 검증이 현지 적설 검증을 대신하지는 않는다.

**Q. 반텐 Esri 2020~2025가 6/6이면 독립 정확도도 검증됐습니까?**

아니다. 6/6은 실제 원천 연도와 One Map 경계 `935,602.88ha`의 reference coverage를 확인했다는 뜻이다. 같은 공급자 연차도 사이 변화와 동년 reference 확인은 독립 현장·전문가 정답 평가가 아니므로 independent accuracy는 미산출이다.

**Q. 현재 반텐 전역 2020→2025 결과는 무엇입니까?**

공통 유효 `935,231.32ha`, 변화 `78,998.91ha`다. 10m 변화 결과를 1km 격자로 집계한 지도에는 변화 셀 `8,663개`와 상위 hotspot `20개`가 있다. 전환행렬·KPI·6개 연도 면적 시계열·원천 inventory도 기존 Workspace에서 확인했다. 이는 Esri 연차도 간 변화이지 KLHK 변화나 독립 정확도가 아니다.

**Q. Swipe Auto Play는 무엇을 바꿉니까?**

분석 결과가 아니라 비교 지도 조작만 바꾼다. 한 번 누르면 5초 동안 50→85→15→50%로 이동하고 남은 초·완료 상태를 표시하며 Pause/Resume할 수 있다. 반텐 Edge에서 내부 시계 5,098ms, 5→1초·완료, 50% 복귀, 일시정지·재개, 수동 조작·모드 전환 취소와 기존 Time-Series 재생을 확인했고 build도 통과했다. 기관·자료·모델 승인 상태는 바뀌지 않았다.

**Q. 1km 변화 셀 8,663개는 10m 원본 픽셀 수나 정확도입니까?**

아니다. 10m 변화 결과를 화면 표시와 우선순위 검토용 1km equal-area grid로 집계한 셀 수다. 상위 20개 hotspot도 검토 순위이며 정확도 지표가 아니다.

**Q. 보고서 HTML·JSON·CSV는 같은 결과를 가리킵니까?**

예. 같은 검증 payload에서 evidence ID `0c62e0f1c6d06ca4aba4726b6e9f4ab7c0ba01a6c44b08fb976d0ca1d7e2dab6`로 결정론적으로 생성된다. Edge에서 세 형식과 기존 Workspace 연결을 확인했지만, 이 ID가 기관 승인이나 독립 정확도를 부여하지는 않는다.

**Q. Sentinel-2·Landsat 반텐 전역 수집과 Docker/Kubernetes 이식도 완료됐습니까?**

원본·6개년 QA·RGB와 기술 이식은 완료됐다. Sentinel-2 224/224 asset·32/32 scene, Landsat 168/168 asset·24/24 scene이며 Docker 5180과 Kubernetes 5181에서 실제 광학 레이어 12개를 확인했다. 그러나 Landsat 10.35~274.32ha와 Sentinel-2 2021~2025 0.09~2.88ha 경계 미피복 때문에 과학 인수는 `COVERAGE_GAPS`다. 기술 이식 완료가 독립 정확도나 기관 운영 승인을 뜻하지 않는다.

추가 근거: [LCLUC 분류사전·변화 계산·기준 분류기](../V42_LCLUC_TAXONOMY_CHANGE_CLASSIFIERS.md)

## LCLUC 연차 입고 Gate

**Q. 2026 원본을 inbox에 복사하면 자동 학습합니까?**

아니다. 유효한 `bundle.json`, 원본 byte·SHA, 두 센서 필수 6밴드와 QA, 품질 Gate가 먼저 필요하다. 동년 라벨과 해당 bundle run에 결속된 학습 승인도 없으면 후보 RF를 만들지 않는다.

**Q. 기존 반텐 2020~2025 원본 완료가 새 연차 Gate 처리 완료를 뜻합니까?**

아니다. 기존 원본·QA 검증은 선행 증거이고, 새 `lcluc-annual-input/1` manifest와 승인·run 결과는 별도다. 소급해서 처리 완료라고 쓰지 않는다.

**Q. Sentinel-2와 Landsat 분류가 잘 맞으면 독립 정확도가 높습니까?**

아니다. 이는 동년 센서 간 지도 일치도다. 두 후보가 같은 오류를 낼 수 있으므로 독립 표본 정확도를 대신하지 않는다.

**Q. WorldCover 또는 Esri와 일치하면 독립 정확도입니까?**

아니다. 약한 지도 참조 일치도다. WorldCover 2021은 2021년 약한 참조일 뿐 다른 연도의 정답이 아니다.

**Q. 연차 Gate에서 독립 정확도라고 부를 수 있는 조건은 무엇입니까?**

학습·약한 참조와 source ID, provider, raster SHA가 다르고 승인된 protocol·authority가 있어야 한다. 학습 위치와 인접 1셀을 제외한 센서별 최소 100표본으로 OA·F1·IoU를 계산해야 한다. 합성 결과는 `synthetic_holdout`에만 둔다.

**Q. 후보 RF의 confidence 0.9는 정확도 90%입니까?**

아니다. 보정되지 않은 최대 클래스 확률이다. 독립 정확도나 실제 오류확률로 해석할 수 없다.

**Q. 현재 실제 2026 결과와 Docker·Kubernetes 실행이 확인됐습니까?**

Docker 5180과 kind Kubernetes 5181의 격리 합성 실행은 각각 확인했다. 두 센서 clear 1,023/1,024픽셀, 합성 holdout 256개, 네 GeoTIFF SHA와 Edge 상태 행·증거 링크까지 `TESTED_SYNTHETIC`이다. 그러나 실제 2026 원본·동년 라벨·독립 참조는 미확보고 `independent_accuracy`는 null이므로 실제 2026 결과는 아니다.

**Q. 실자료 전용 worker가 실행 중이면 2026 자료도 들어온 것입니까?**

아니다. Docker worker는 synthetic을 비활성화하고 실제 inbox를 60초 간격으로 감시 중이지만 운영 접수는 0건이다. 프로세스 실행과 자료 입고를 분리한다.

**Q. 독립 평가를 통과하면 자동으로 모델을 공개합니까?**

아니다. `production_release`는 `SEPARATE_APPROVAL_REQUIRED`이며 과학 검토, 기관 게시, 모델 활성화는 별도 승인이다.

추가 근거: [LCLUC 연차 원본 입고·후보 모델·검증 Gate](../V42_LCLUC_ANNUAL_INTAKE_GATE.md)

## 반텐 Sentinel-2 Explore

**Q. Sentinel-2를 30m로 수집했습니까?**

B02·B03·B04·B08은 native 10m, B11·B12·SCL은 native 20m 원본으로 보존한다. Explore 분석본만 30m EPSG:6933 공통 격자로 정합한다.

**Q. 자연색·NDVI PNG와 분석 GeoTIFF는 같은 것입니까?**

PNG는 화면용 Web Mercator 파생본이다. 30m GeoTIFF는 여섯 반사도 band, NDVI·NDWI·NBR과 QA를 10-band 순서로 보존한다.

**Q. 분홍색 변화탐지는 Sentinel 분류 변화입니까?**

분홍색 변화탐지는 두 Esri v003 연차 토지피복 코드가 다른 10m 픽셀이다. Sentinel 광학 영상은 함께 탐색하는 별도 자료다.

**Q. 사용자 사각형의 면적은 어떻게 계산합니까?**

사각형과 반텐 경계의 교집합만 10m equal-area 픽셀 중심 규칙으로 계산한다. 경계 밖은 제외한다.

**Q. 현재 Explorer 전체가 실제 검증됐습니까?**

발행·핵심 기능 범위는 그렇다. Sentinel 32장면·6/6년·PNG 36개·30m GeoTIFF 6개, Esri 6/6년·15/15쌍을 검산했다. Edge에서 영상 5조합·3중첩·점·53,155.27ha AOI·112행 CSV에 더해 layer 목록 접기·펼치기, 4 switch, 방향 지도·필터, AI 상태, 35년 다운로드, 2021 제품 행렬을 클릭 확인했다. 최종 결과 화면에서는 두 모서리 AOI 52,128.16ha 반환도 확인했다. 다만 독립 정확도와 사업통계 승인은 여전히 미확보다.

**Q. 전이행렬의 산림→시가지와 시가지→산림은 같은 변화입니까?**

행은 기준 연도, 열은 비교 연도로 방향을 보존한다. 선택한 방향 전이 PNG는 사용자 사각형 AOI가 있으면 면적표와 같은 범위로 잘린다.

**Q. MapBiomas 35년 표도 사용자 AOI 통계입니까?**

MapBiomas Indonesia Collection 4.1 발행자가 제공한 반텐 주 단위 1990~2024·11클래스 통계다. Esri 면적표와 사용자 사각형 통계는 별도로 표시한다.

**Q. Esri↔WorldCover 80.9456760515%는 정확도입니까?**

2021년 두 제품을 10m·6개 대분류로 맞춘 926,628.52ha의 지도 일치도다. WorldCover 적용 범위는 2021년이고 독립 정확도는 미측정이다.

**Q. AI 신규 분류 탭은 실제 운영 결과입니까?**

상태·증거 UI는 연결됐고 생산 연차 AI 실제 접수는 0건이다. 실제 신규 분류·독립 정확도·release 상태는 `BLOCKED`다.

**Q. Sentinel-2 상세 결과를 보려면 상단 결과 탭으로 이동해야 합니까?**

지도 자료에서 Sentinel-2를 선택하면 상단 7개 이동 항목이 지도 분석과 여섯 결과 제목으로 바뀐다. 각 항목은 해당 지도 또는 카드로 초점과 스크롤을 옮긴다. 지도 연도·AOI는 클래스 면적·비율·전이행렬·세부 변화탐지에 함께 적용된다. Edge 5175에서 7개 실제 경로와 여섯 실자료 카드 내용을 확인했다.

**Q. 지도 조작의 `상세 결과` 버튼은 무엇을 합니까?**

버튼은 지도 아래 상세 결과 위치로 초점과 스크롤을 옮긴다. 패널 표시 조건은 Sentinel-2 선택 상태가 담당한다.

**Q. Landsat·연차 Esri 선택 시 Sentinel 상세 결과는 어떻게 됩니까?**

Sentinel-2 선택 상태가 해제되면 패널 렌더링 조건도 해제된다. Landsat과 연차 Esri에서 패널 해제, Sentinel-2 재선택 시 AOI 복원, 2024→2025 재계산 표 갱신을 Edge에서 확인했다.

**Q. 오른쪽 `연차 토지피복 주요 지표`와 `주요 전이`의 출처는 무엇입니까?**

Esri / Impact Observatory v003 연차 토지피복의 반텐주 전체 집계다. 두 카드에 선택한 기준 연도와 비교 연도쌍을 함께 표시한다.

**Q. Sentinel 지도 아래 면적과 전이는 어떤 자료를 사용합니까?**

영상·지수·품질은 Sentinel-2 L2A 자료다. 클래스 면적·비율과 전이행렬은 선택 AOI의 Esri 연차 토지피복 집계다. 출처 문구를 개정했고 API와 산식은 기존 검증 범위를 유지한다.

**Q. Sentinel-2 결과 카드는 어떻게 배치됩니까?**

지도는 연차 비교와 같은 2열 폭을 사용한다. 오른쪽에는 클래스 면적·비율과 AI 신규 분류, 아래에는 전이행렬·세부 변화탐지·장기 추세·제품 간 검증이 놓인다. 1650px Edge에서 두 모드 지도 폭은 각각 886.95px였고 920px에서는 카드가 세로로 쌓였다.

**Q. Swipe의 T1과 T2는 어느 결과에 적용됩니까?**

T1 기준 연도와 T2 비교 연도는 상단 필터·지도·AOI 표와 클래스 면적·비율·전이행렬·세부 변화탐지에 함께 적용된다. AI 신규 분류는 반텐 연차 작업 상태, 장기 추세는 MapBiomas 1990~2024 반텐 전체, 제품 간 검증은 2021 반텐 전체를 제공한다. 비교 연도는 기준 연도보다 뒤인 선택지로 제공되고 연도 변경 뒤 구분선은 50:50으로 정렬된다. 2022→2024 실제 갱신을 Edge에서 확인했다.

**Q. 점 조회와 행정경계 조작은 어디에 있습니까?**

점 조회는 지도 아래 AOI 도구에서 제공한다. 행정경계 표시는 Sentinel 범례의 switch가 조절한다. 최종 Edge 통합에서 두 control의 DOM과 화면 배치를 확인했다.

추가 근거: [반텐 Sentinel-2 Explore Gate](../V42_LCLUC_SENTINEL_EXPLORER.md)

## 반텐 Landsat 장기 분석 Explorer

**Q. RF 71.42%는 독립 정확도입니까?**

2020 Landsat RF와 동년 Esri v003의 약한 참조 일치도다. 공간 블록 홀드아웃 72,391픽셀을 사용했고 독립 현장 표본 정확도는 미측정이다.

**Q. 2020~2022의 97.86%는 무엇입니까?**

반텐 격자에서 QA를 통과한 맑은 Landsat 관측이 한 번 이상 존재하는 비율이다. 두 번 이상 관측된 비율은 90.5761%다.

**Q. Landsat Explorer에서 어떤 영상을 볼 수 있습니까?**

Natural Color, Agriculture, Urban, SWIR, NDVI, NDMI, MNDWI의 7개 preset을 제공한다. Edge에서 각 control이 실제 PNG 요청을 바꾸는 것을 확인했다.

**Q. MapBiomas 장기 추세는 사용자 AOI 통계입니까?**

MapBiomas Indonesia Collection 4.1 발행 반텐 주 전체의 1990~2024 35년·11클래스 통계다. Landsat 영상·지수와 RF 평가는 별도 근거로 표시한다.

**Q. 1988·1990·2000과 2010은 모두 발행됐습니까?**

네 연도 모두 Landsat 5 TM 단일 장면 manifest·API·원본 SHA를 확인했다. 맑은 관측은 각각 47.88%, 50.83%, 40.30%, 32.14%이고 원본 합계는 1,257,798,910B다. 최종 Edge에서 1990→2020 Swipe, 1990·2000·2010·2020 frame, 시작점 자동재생·순차 진행·T2 정지를 확인했다.

**Q. LandTrendr와 CCDC 결과가 있습니까?**

현재 화면은 MapBiomas 주 단위 연차 면적 변화와 최대 증감 구간을 제공한다. 픽셀 변화 발생시점과 LandTrendr·CCDC 비교는 `PLANNED`다.

추가 근거: [반텐 Landsat 장기 분석 Explorer](../V42_LCLUC_LANDSAT_EXPLORER.md)

## LCLUC 후처리 및 품질관리

**Q. Spatial Filter 뒤 75.36%는 독립 정확도입니까?**

동일 공간 홀드아웃 72,391픽셀에서 후처리 결과와 Esri v003을 비교한 약한 참조 일치도다. 독립 정확도 상태는 `REFERENCE_REQUIRED`다.

**Q. 129,889.72ha는 실제 토지피복 변화입니까?**

2020 후보 분류에서 공간 필터가 값을 바꾼 위치의 면적 합계다. 연차 토지피복 변화량은 서로 다른 연도 자료로 별도 계산한다.

**Q. 실제 화면에서 무엇을 확인했습니까?**

실행 ID `e8f1b2…ad4a4`의 전후 Swipe, 보정 위치, 클래스 면적, 전후 품질, 파라미터 이력, 원본·보정본·보정 mask GeoTIFF의 SHA 다운로드, 새로고침 재조회와 기존 Workspace 바로가기를 확인했다.

**Q. Spatial Filter는 MapBiomas 공식 코드를 그대로 사용합니까?**

MapBiomas ATBD와 공개 Gap Fill·Temporal 코드를 검토했다. 고정 공개 저장소의 `Saptial Filter.js`는 내용이 비어 있어 SDSS는 Rasterio/GDAL 연결 성분 sieve 기반 자체 시험 구현을 사용한다.

**Q. Temporal·Gap·Frequency·Incident·계층 통합도 실행할 수 있습니까?**

현재 UI는 필요한 입력 조건을 설명한다. Temporal·Gap·Frequency·Incident는 `PLANNED`다. 계층 통합은 우선순위·충돌·NoData·타년 거부와 파일 기반 11픽셀 통합을 합성 시험으로 확인했고 실제 승인 동년 특화층 접수는 `BLOCKED`다.

**Q. 같은 입력과 파라미터를 다시 보내면 새 결과가 생깁니까?**

원본 보고서 SHA·알고리즘·파라미터가 같으면 같은 실행 ID를 사용하고 기존 보고서를 재조회한다.

추가 근거: [LCLUC 후처리 및 품질관리](../V42_LCLUC_POSTPROCESS_QUALITY.md)

## 반텐 모델 시험과 특화 분류 계층 통합

**Q. RF 71.42%와 Tiny U-Net 66.34%는 독립 정확도입니까?**

2020 Landsat 후보를 동년 Esri v003과 비교한 약한 참조 일치도다. 두 모델은 같은 72,391픽셀 공간 홀드아웃을 사용했고 독립 정확도는 미측정이다.

**Q. Spatial Filter 뒤 어떤 변화가 있었습니까?**

3픽셀·8방향에서 RF는 75.09%로 바뀌고 31,658픽셀이 보정됐다. Tiny U-Net은 66.49%로 바뀌고 1,885픽셀이 보정됐다. 두 값 모두 Esri 약한 참조 일치도다.

**Q. 두 센서의 DeepLabv3+ 결과는 어떻게 다릅니까?**

Landsat은 72,391픽셀에서 67.7584%, Sentinel-2는 76,230픽셀에서 63.7413%의 Esri 약한 참조 일치도다. 각 센서 내부에서 RF·Tiny·DeepLab이 같은 표본을 사용하며 센서 간 유효 픽셀 집합은 다르다.

**Q. DeepLabv3+ Spatial Filter도 실제 화면에서 확인했습니까?**

확인했다. 3픽셀·8방향에서 Landsat은 67.9670%·1,865픽셀, Sentinel-2는 63.8725%·1,360픽셀이고 평가 표본 수가 유지되는 것을 Edge에서 확인했다.

**Q. Siamese U-Net을 운영 변화 탐지로 사용할 수 있습니까?**

현재 2020→2025 Sentinel-2 후보의 변화 클래스 F1은 64,658픽셀에서 0.288265, 필터 뒤 0.288352다. 독립 변화 정답과 운영 승인 모델 release는 `BLOCKED`다.

**Q. 해안·논·플랜테이션 특화층은 실제로 통합됐습니까?**

합성 파일 시험에서 같은 격자의 11픽셀을 통합하고 원본 SHA와 NoData를 유지했다. 실제 승인 동년 라벨과 mask 접수는 대기한다. 타년 라벨은 계약에서 거부한다.

추가 근거: [반텐 모델 시험과 특화 분류 계층 통합](../V42_LCLUC_MODEL_TRIALS_AND_SPECIALISTS.md)

## 반텐 원본별 면적과 공식 비교 기준

**Q. Esri 935,602.88ha와 MapBiomas 935,005.55ha를 빼서 정확도 오차로 볼 수 있습니까?**

두 값은 각 원본의 경계·격자·분류 정의에 따른 총계다. 화면은 차이 열을 제공하지 않으며 동일 클래스·토지전환·독립 정확도 수치로 사용하지 않는다.

**Q. 화면에는 어떤 표가 표시됩니까?**

Esri 원본 9행과 MapBiomas 발행 11행을 별도 표로 표시한다. 2024 Esri 경계는 유효 935,224.83ha, 구름 378.05ha, NoData 0ha로 분해한다.

**Q. 어떤 연도를 실제 화면에서 확인했습니까?**

공통 발행 연도는 2020~2024이고 Edge에서 2020과 2024 선택, Esri 9행·MapBiomas 11행, 차이 열이 없는 것을 확인했다.

**Q. 공식 비교와 독립 정확도의 기준은 무엇입니까?**

공식 비교는 Kemenhut 동년 Penutupan Lahan 23클래스를 사용한다. 독립 정확도는 학습과 기관 참조에서 분리한 현장·전문가 판독 표본으로 산출한다.

추가 근거: [반텐 원본별 면적과 공식 비교 기준](../V42_BANTEN_ESRI_MAPBIOMAS_AREA_COMPARISON.md)

## MapBiomas Indonesia GeoLLM 지식 검색

**Q. GeoLLM이 생성한 답변을 제공합니까?**

현재는 `answer=null`인 로컬 어휘 근거 검색이다. 원문 발췌문, 문서 버전, PDF 페이지와 공식 링크를 제공한다.

**Q. 확보한 지식 범위는 무엇입니까?**

공식 자료 R01~R14 14건, P0 핵심 9건, 286청크, 용어 44개, 참조 지도 25개, 특화 범례 5개다. R11은 인포그래픽 목록 HTML 범위다.

**Q. 원문이 바뀌면 기존 인용이 계속 나옵니까?**

검색 전에 원문 byte와 SHA를 index pin과 대조한다. 값이 달라진 문서의 인용은 반환하지 않는다.

추가 근거: [MapBiomas Indonesia GeoLLM 지식 검색](../V42_MAPBIOMAS_GEOLLM_KNOWLEDGE.md)

## GeoLLM 반텐 토지피복 질의응답

**Q. 산림 총전환 3,146.85ha와 순변화 −1,265.58ha가 왜 다릅니까?**

총전환은 `TRANSITION`에서 산림이 비산림으로 나간 흐름의 합이다. 순변화는 `COVERAGE`의 종료 산림면적에서 시작 산림면적을 뺀 값으로 유입과 유출의 최종 차이를 반영한다.

**Q. MapBiomas 답변의 반텐 경계가 수치 계산 경계입니까?**

One Map/BIG 경계는 위치 맥락 지도다. 수치는 발행자 기준 반텐 통계이며 XLSX에 집계 경계 도형이 포함되지 않아 두 경계가 동일하다고 확정하지 않는다.

**Q. Esri 전이 질문은 실제 지도를 보여 줍니까?**

보여 준다. 2023→2024 수목→시가지 3,561.79ha 응답에서 v003 실제 전이 PNG를 Edge로 확인했다.

**Q. Kemenhut 또는 중첩 질문은 어떻게 처리합니까?**

동년 Penutupan Lahan 원본은 `KEMENHUT_ASSET_NOT_READY`, 승인된 중첩 자산은 `OVERLAY_ASSET_NOT_READY`로 차단한다.

**Q. GeoLLM 조회가 결과 registry에 저장됩니까?**

현재 읽기 전용 응답의 `result_id`는 `null`이다. 공통 결과 등록·검토 흐름은 연결되지 않았다.

**Q. 현재 GeoLLM API는 파생 런타임 이미지를 사용합니까?**

현재 검증 경로는 기본 Dockerfile이 Debian `libexpat1`을 설치한다. 보관 `b471bb3` 소스와 이 Dockerfile 변경만으로 `sdss-platform2-api:geollm-libexpat1`을 새로 빌드했으며 별도 파생 런타임 이미지는 없다. 이전 `b471bb3-expat` 라운드는 최소 해결책을 확인한 역사적 검증이다.

**Q. 두 컨테이너 환경에서 같은 결과가 재현됐습니까?**

Compose 5180과 로컬 kind 5181에서 한국어·인도네시아어·영어 RAG와 GIS 결과 5건을 확인했다. API 소스·원본 XLSX·정제 JSON의 SHA가 같았고 JSON 응답 10개와 대응 지도 자산 해시도 일치했다. 양쪽 raw·evidence는 `ro`, curated 복사본은 `rw`였다.

**Q. 이식 검증으로 GeoLLM의 과학적 승인도 끝났습니까?**

검증 범위는 컨테이너 실행과 응답 재현성이다. Kemenhut 원본, 중첩 자산, 독립 정확도, 결과 registry는 기존 `BLOCKED` 상태를 유지한다.

추가 근거: [GeoLLM 반텐 토지피복 질의응답](../V42_LCLUC_GEOLLM_QUERY.md)
