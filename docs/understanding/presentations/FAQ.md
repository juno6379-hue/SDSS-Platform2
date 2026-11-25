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

아닙니다. CCKP 검산 JSON 3,295B의 SHA·재시도, 익명 403, 45초 presigned GET과 만료 403만 검증했습니다. PostgreSQL fixture는 TCP timeout이었고 Kubernetes context도 없어 RLS·PostGIS·pgvector·복구·클러스터 인수는 `BLOCKED`입니다.

추가 근거: [운영 경로 2~8](../V42_OPERATION_PATH_2_TO_8.md)
