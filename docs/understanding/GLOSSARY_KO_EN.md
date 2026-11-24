# v4.2 기후·RAG 용어집

- updated_at: 2026-11-24 KST
- status: `IMPLEMENTED_UNVERIFIED` 문서; 코드 계약과 용어를 대조했다.

| 한글 | 영문/약어 | 프로젝트 적용 의미 |
|---|---|---|
| 기후변화 지식포털 | Climate Change Knowledge Portal, CCKP | World Bank 기후 자료 원천. 현재 공개 S3 목록 일부와 HEAD 1건만 실제 확인했으며 Indonesia 수치는 미확인이다. |
| 제한형 탐색 | Bounded discovery | 반환된 prefix·key만 수량/본문 크기 상한 안에서 탐색하는 방식. 전역 sync와 국가 URL 추측 금지 |
| HEAD 요청 | HTTP HEAD | 객체 본문 없이 status/header를 확인한다. HEAD 200은 NetCDF 수치 검증이 아니다. |
| 원본 영수증 | RAW receipt | source URI·ETag·실제 SHA·bytes·취득시각·trace를 고정하는 기록. QC/curated 승인은 아님 |
| 계보 | Lineage | source/version/URI/SHA/license/time/space/derived_from/trace 추적 정보 |
| 관측값 | Observed | 실제 관측 기반 자료. 전망 시나리오와 혼합하지 않는다. |
| 전망값 | Projected | 모델·시나리오가 필수인 미래/모의 자료 |
| CF 달력 | Climate and Forecast calendar | standard, 360_day, noleap 등. 암묵 변환 금지 |
| 접근통제목록 | Access Control List, ACL | 검색 점수 계산 전에 문서 접근 가능성을 거르는 규칙 |
| 검색증강생성 | Retrieval-Augmented Generation, RAG | 문서 근거를 검색해 설명을 지원하는 방법. 수치 DB가 아니다. |
| 구조화 기후 도구 | Structured climate tool | 공식 grid/table/database에서 단위·달력·모델·시나리오를 검증해 숫자를 반환할 후속 도구 |
| 온톨로지 | Ontology | 노드 종류와 관계 domain/range를 명시한 의미 모델 |
| 지식그래프 | Knowledge Graph, KG | 출처 span에 결속된 노드와 관계 |
| 인용 | Citation | 원문 URI·버전·SHA·문자 범위·authority를 다시 검증한 근거 |
| BM25 | Best Matching 25 | 허용 문서에만 적용하는 어휘 기반 검색 점수 |
| 합성 hash vector | Synthetic feature-hash vector | 시험 재현성을 위한 64차원 벡터. 실제 semantic embedding 아님 |
| authority | Authority | 원문에 선언된 권위 주체 문자열. 실제 기관 인증·법적 승인을 자동 뜻하지 않음 |
| 약한 참조 | Weak reference | WorldCover 같은 보조 참조. 독립 정답·타 연도 정답 아님 |
| 독립 정확도 | Independent accuracy | 별도 현장/전문가 라벨로 평가한 정확도. 약한 참조 일치도와 구분 |
| fail-closed | Fail-closed | 필수 단위·기간·권한·출처가 불명확하면 추정하지 않고 차단하는 정책 |
| 기준시점 | As-of | 해당 시점에 실제 이용 가능했던 자료·경계만 사용하기 위한 시간 기준 |
| 미래 누출 | Future leakage | 학습 시점 이후 자료·경계·통계를 과거 학습행에 섞는 오류 |
| 수치 feature 없음 | `numeric_features=null` | planner가 실행 가능한 숫자 배열을 만들지 않았다는 명시적 상태 |
| 추적 ID | Trace ID | 요청·자료·결과를 연결하는 식별자 |
| 공간 bbox | Bounding box | WGS84 west/south/east/north. 과학적 면적과 동일하지 않음 |
