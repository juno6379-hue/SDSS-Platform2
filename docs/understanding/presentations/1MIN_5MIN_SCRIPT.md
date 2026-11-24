# v4.2 그대로 읽는 1분·5분 발표

## 1분

“v4.2에서는 기후 설명과 숫자의 답변 경로를 분리하고 CCKP 자료를 추측 없이 제한적으로 탐색하도록 만들었습니다. 실제 확인은 공개 S3 목록 5페이지 5,289바이트와 NetCDF 한 건의 HEAD 200뿐이고 본문은 받지 않았습니다. source·lake·feature·RAG 계약은 합성 시험 71건을 통과했지만 Indonesia 국가 경로, 실제 수치 feature, 학습·배포, 기관 인증은 아직 차단되어 전체 완료는 아닙니다.”

## 5분

1. **문제** — 벡터 유사도는 숫자의 단위·달력·격자·시나리오나 기관 authority를 보증하지 않는다.
2. **공통 계약** — source/version/URI/SHA/license/acquired_at, 관측/전망, 모델/시나리오, 단위, CF 달력, 공간·시간, ACL, trace를 필수로 고정한다.
3. **설명 경로** — ACL·license·유효기간 선필터 후 BM25·합성 hash vector·metadata로 찾고 원문 citation을 재검증한다.
4. **정량 경로** — 한국어/인니어/영어 정량 질문은 `climate.query`를 요구하며 도구가 없으면 차단한다.
5. **source·lake·feature** — bounded discovery와 receipt, CF/as-of/ACL/bbox 계획은 fail-closed다. planner는 `execution_started=false`, `numeric_features=null`이다.
6. **시험 증거** — contract/RAG 23, source 24, lake/feature 24로 합성 71 PASS다. 실제 증거는 목록 5페이지와 HEAD 한 건뿐이다.
7. **정직한 한계** — Indonesia 경로, 실제 CCKP 본문/값, 공간 조인, 학습·배포, 기관 인증, 독립 정확도, API/UI 운영은 검증하지 않았다.

상세 근거: [v4.2 기후 계약·RAG 이해자료](../V42_CLIMATE_FOUNDATION_AND_RAG.md)
