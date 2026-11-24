# v4.2 발표 FAQ

**Q. 이제 실제 CCKP 수치를 답할 수 있습니까?**
아닙니다. 정량 질문을 구조화 도구로 보내는 계약만 있습니다. 공식 API/Grid/Parquet/PostGIS 연동과 검증 전에는 숫자를 답하지 않습니다.

**Q. CCKP 연동에서 실제 검증한 범위는 무엇입니까?**
공개 S3 목록 5페이지 5,289B와 목록에 있던 NetCDF 한 건의 HEAD 200뿐입니다. 본문은 0B이고 Indonesia 국가 prefix가 확인되지 않아 실제 국가 다운로드 계획은 `BLOCKED`입니다.

**Q. climate feature가 생성됐습니까?**
아닙니다. as-of·ACL·CF 달력·CRS·bbox 후보를 검사하는 계획기만 있습니다. 실제 공간 join·numeric feature·학습·배포는 0건이며 `execution_started=false`, `numeric_features=null`입니다.

**Q. 71 PASS가 과학 정확도를 뜻합니까?**
아닙니다. schema·ACL·citation·routing의 합성 계약시험입니다. 실제 수치·모델 전망·독립 accuracy 검증이 아닙니다.

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

상세 근거: [v4.2 기후 계약·RAG 이해자료](../V42_CLIMATE_FOUNDATION_AND_RAG.md)
