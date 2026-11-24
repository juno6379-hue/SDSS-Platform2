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

아닙니다. 각 지역·연도 셀이 최소 28개 패치를 가진다는 뜻입니다. paired 피복은 0.976741%, clear 피복은 0.889803%라 약 99% 공간 공백이 남습니다.

**Q. CAS 6,125개·3.904GB는 새 Sentinel 다운로드입니까?**

아닙니다. 기존 로컬 산출물의 copy 이관이며 원격 다운로드와 ledger write는 0건입니다.

**Q. Edge에서 UI를 클릭했으니 운영 배포도 검증됐습니까?**

아닙니다. 실제 로컬 Edge 클릭은 API/UI 연결과 차단 표시를 검증합니다. 자동 API 11건은 통과했지만 Playwright 3건은 skip되었고 인증·다중 사용자·운영 가용성은 검증하지 않았습니다.

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

아직 알 수 없습니다. pilot 관측은 `used_in_aggregate_coverage=false`이며 aggregate를 재감사하지 않았습니다. 0.976741%는 pilot 이전 snapshot입니다.

**Q. 잔액 1,678,521,030B면 전체 공간을 채울 수 있습니까?**

확정할 수 없습니다. byte 잔액은 실제 확인했지만 전체 gap 비용과 BIG·수집 승인이 검증되지 않았습니다.

**Q. pilot 결과는 독립 정확도 또는 학습 준비 증거입니까?**

아닙니다. SCL clear QA일 뿐이며 `learning_ready=false`, `independent_ground_truth=false`입니다. WorldCover 2021도 타연도 ground truth로 사용할 수 없습니다.

추가 근거: [Sentinel 단일 실제 pilot](../V42_SENTINEL_SINGLE_PILOT.md)
