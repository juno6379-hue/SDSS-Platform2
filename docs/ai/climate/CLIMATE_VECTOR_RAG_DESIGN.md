# Climate Knowledge Vector RAG 설계·구현·시험

상태: **TESTED_SYNTHETIC**. 외부 LLM/embedding key·네트워크·실제 기후 수치 조회·공식 문서의 신규 다운로드 없이 계약을 구현했다. 실제 운영 인덱스·임베딩 품질·기관별 인증·구조화 기후 도구 실행은 **IMPLEMENTED_UNVERIFIED / BLOCKED**이며 전체 플랫폼 완료가 아니다.

## 1. 소유 범위와 역할 분리

작업 루트는 `E:\SDSS-Platform2`다. `AGENTS.md`, `docs/architecture/V42_EXECUTION_PLAN.md`의 CLIM-06/07을 구현한다. 변경은 `services/rag/`, `tests/rag/`, 본 문서로 제한한다. UI/API·공통 계약·CI·다른 담당 소스는 수정하지 않았다.

```text
승인된 문서/메타데이터 receipt
 → SourceDocument 본문 SHA 확인
 → SourceSpan Unicode 문자 범위 고정
 → typed ontology/KG + ChunkMetadata
 → 질문 route 판정
   ├ 정량/모호한 변수 질문 → structured climate tool 요청만 반환
   └ 명시적 설명 질문 → ACL/라이선스/유효기간 필터
     → metadata/공간/연도/달력 필터
     → BM25 + 합성 hash-vector + metadata/공간/시간 순위
     → 원문 citation 재검증 → 인용문 목록만 반환
```

CCKP의 수치는 공식 API/Grid/Parquet/PostGIS에서 조회해야 한다. `HybridIndex.respond`는 모든 경우 `answer=None`을 반환한다. 정량 질문은 citations도 빈 목록이며, 도구가 없다고 RAG로 fallback하지 않는다. 설명 응답도 자유 생성 문장이 아닌 원문 그대로의 승인된 인용문이다.

## 2. 온톨로지·관계

`services/rag/ontology.py`가 다음 16개 타입을 정의한다.

Institution / Source / Collection / Dataset / DatasetVersion / Variable / Scenario / ClimateModel / TimePeriod / Geography / SpatialUnit / Document / Chunk / FeatureSet / Result / Policy.

| 관계 | 허용 domain → range 예시 |
|---|---|
| PUBLISHED_BY | Source·Collection·Dataset·Document·Policy → Institution |
| HAS_VERSION | Dataset → DatasetVersion |
| CONTAINS_VARIABLE | Collection·DatasetVersion·FeatureSet·Result → Variable |
| USES_SCENARIO | DatasetVersion·FeatureSet·Result → Scenario |
| PRODUCED_BY_MODEL | DatasetVersion·FeatureSet·Result → ClimateModel |
| COVERS_TIME | Collection·DatasetVersion·Document·Policy·FeatureSet·Result → TimePeriod |
| COVERS_GEOGRAPHY | 위 시간 domain → Geography·SpatialUnit |
| DERIVED_FROM | DatasetVersion·FeatureSet·Result → Source·DatasetVersion·FeatureSet |
| CITES | Document·Chunk·Result·Policy → Document·Chunk·Source·DatasetVersion |
| GOVERNS | Policy → Dataset·DatasetVersion·FeatureSet·Result·SpatialUnit |
| SUPERSEDES | DatasetVersion·Document·Policy → 동일 타입의 다른 버전 |

모든 노드·관계는 등록된 문서의 source_id/version/SHA/authority/start/end/quote를 요구한다. DatasetVersion은 별도 entity_version도 필수이며 출처 문서 버전으로 대신하지 않는다. SUPERSEDES 역시 같은 타입의 서로 다른 명시적 entity_version이 필요하다. dangling edge, 미등록 관계, 잘못된 domain/range, 자기 참조, 중복 ID·관계는 실패한다. 관계와 양 끝 노드의 authority 결속도 확인한다. 관계 타입표와 인덱스는 읽기 전용 mapping이고 개별 record는 frozen dataclass다.

**‘검증’의 범위**는 원문 SHA·문자 범위·타입·버전·authority 결속 검사다. 사람이 입력한 임의 문장이 과학적으로 참인지, 해당 authority가 실제 기관인지, 관계가 법적으로 승인되었는지를 인증하지 않는다. 실제 문서 등록 전의 기관/authority allowlist·원본 receipt·권한 검토는 Root의 ingestion/auth 계약과 연결해야 한다. 원문 없이 LLM이 추측한 관계는 등록하지 않는다. 전체 raw KG를 클라이언트에 노출하는 API는 구현하지 않았다.

## 3. Chunk metadata·lineage

`ChunkMetadata`는 다음을 필수로 보존한다.

- 출처: source_span(document_id/source_id/version/document_sha256/authority/start/end/quote), authority
- 언어: ko / id / en
- 접근: public 또는 restricted, 명시적 allowed_roles 집합. restricted의 빈 역할은 오류
- 라이선스: license, retrieval_permitted 명시 bool. 라이선스 문자열만으로 사용 가능성을 추측하지 않음
- 유효성: valid_from, valid_until(명시적 open-ended None 허용), timezone이 있는 acquired_at
- 공간: WGS84 bbox. 날짜변경선 횡단은 암묵 보정하지 않고 분할 입력 필요
- 시간: 연도 start/end, calendar. 360_day/noleap을 Gregorian 날짜로 바꾸지 않음
- 기후 의미: variable, scenario, model, observed_or_projected, unit, grid
- 근거: claim_authority, dataset_id/dataset_version, trace_id

해당 없음도 누락시키지 않고 `not_applicable` 같은 명시적 값을 입력한다. 관측과 전망·단위·시나리오·모델·격자 의미를 서로 치환하지 않는다. RAG 계층은 수치 변환·보간·세밀화·calendar 계산을 하지 않는다. coarse grid를 Sentinel-2 10m 관측으로 표현하는 기능도 없다.

source_span은 UTF-8 byte가 아닌 Python Unicode 문자 인덱스 `[start,end)`다. 한글·인니어 혼합 인용도 원문과 정확히 일치해야 한다. 인용 반환에는 dataset/version, 변수·시나리오·모델·단위·달력·격자·공간/시간·source URI/SHA/authority/취득시각/Trace를 함께 보존한다.

## 4. 검색·순위

`SearchQuery`에 명시적 `as_of`를 요구해 오늘 날짜에 따른 비결정성을 없앴다. `roles` 기본값은 빈 집합(익명)이다. API adapter는 반드시 인증된 서버 principal에서 역할을 구성해야 하며 사용자 JSON의 임의 역할을 신뢰해서는 안 된다. 본 라이브러리는 로그인·토큰 검증·역할 발급을 구현하지 않는다.

순서는 다음과 같다.

1. ACL → 라이선스 허용 → 유효기간·UTC 취득일(as_of 이후 취득 문서 제외) 필터
2. 변수 alias, 모델, 시나리오, 관측/전망, 언어, 달력, bbox 교차, 연도 교차 hard filter
3. **허용된 문서만** BM25 IDF/평균 길이 계산
4. BM25 최대값 정규화 + SHA-256 feature-hash 벡터 cosine + metadata 점수
5. score 내림차순, 동일 score는 chunk ID 오름차순. 최대50건

가중치는 `0.45×BM25 + 0.35×vector + 0.20×metadata`다. metadata에는 변수 token 일치·명시 조건·공간 bbox IoU·연도 겹침 비율을 반영한다. bbox IoU는 순위용 도 단위 비율이며 과학적 면적·관측 피복률·정량 기후 값이 아니다.

벡터는 64차원 signed feature hashing으로 만든 **합성 시험용**이다. 실제 다국어 semantic embedding 성능을 검증했다고 주장하지 않는다. 외부 임베딩 키·모델 다운로드가 필요 없다. 향후 모델을 교체해도 ACL 선필터·인용 재검증·정량 라우팅은 그대로 유지해야 한다.

## 5. ACL·인용 검증

`verify_citation(chunk_id,quote,query,claim_kind)`는 현재 질의 principal·유효시점·라이선스·필터를 다시 검사하고, 원문 SHA/버전/authority/span과 quote를 대조한다. 유사한 문구로 원문을 바꾸거나 다른 chunk/버전의 인용을 가져오면 실패한다.

허용 claim authority는 descriptive_only / methodology_reference / policy_reference다. policy_reference는 정책 문맥 인용만 허용하며 정책 준수·기관 승인·법적 효력을 자동 판정하지 않는다. numeric claim은 항상 거부한다. 인용이 없으면 `BLOCKED_NO_AUTHORIZED_EVIDENCE`이며 자료가 있는 것처럼 채우지 않는다.

비공개 문서는 점수 통계 계산 전 제외하므로 공개 검색의 점수·순서가 숨겨진 문서 수에 따라 달라지지 않는다. 단, 실제 서비스의 timing side-channel·대용량 인덱스 격리·감사 로그·기관 인증은 후속 보안 검증 대상이다.

## 6. ko/id/en alias·정량 도구 라우팅

`services/rag/routing.py`의 alias:

| ID | 한국어 | 인니어 | 영어 |
|---|---|---|---|
| tas | 기온·평균 기온 | suhu·suhu rata-rata | temperature·mean temperature |
| pr | 강수·강수량 | curah hujan·presipitasi | precipitation·rainfall |
| tasmax | 최고 기온 | suhu maksimum | maximum temperature |
| tasmin | 최저 기온 | suhu minimum | minimum temperature |
| sfcWind | 풍속 | kecepatan angin | wind speed |
| hurs | 상대 습도 | kelembapan relatif | relative humidity |

긴 alias부터 정규화해 최고 기온을 평균 기온으로 오인하지 않는다. 정량 의도·연도·숫자/단위·현재값 요청 등을 감지한다. 변수가 확인된 모호한 질문은 명시적 설명/방법론/정의 의도가 없으면 보수적으로 도구로 보낸다. 따라서 일부 단순 개념 질문도 차단될 수 있으며, 설명 질문은 ‘방법론/definition/metodologi’처럼 의도를 명확히 한다. 완전한 자연어 intent 모델이 아니다.

정량 도구 ID는 **adapter용 제안 `climate.query`**다. 실제 API endpoint나 검증된 실행 서비스가 존재한다고 주장하지 않는다. 필요한 context는 variable/unit/observed_or_projected/model/scenario/time_period/geography/calendar/grid/aggregation이다. 누락 시 BLOCKED·missing_fields를 반환하고, 모두 있으면 TOOL_REQUIRED다. 필드가 있다는 것만 검사할 뿐 context의 과학적 적격성을 인증하지 않으며 실제 도구가 enum/단위·달력·출처·버전을 추가 검증해야 한다.

```python
from datetime import date
from services.rag.routing import route_question
from services.rag.retrieval import SearchQuery

decision = route_question('2050년 강수량 알려줘')
assert decision.kind == 'structured_climate_tool'
assert decision.status == 'BLOCKED'
# 이 결정으로 RAG 인용이나 숫자 답변을 생성하지 않는다.
q = SearchQuery(text='강수량 방법론', as_of=date(2026, 11, 24))
```

`RouteDecision`은 frozen dataclass이며 JSON adapter가 필요하면 `dataclasses.asdict`를 사용한다. Tool routing은 도구 **실행**이 아니다. Lake/feature 담당의 미완료 산출물과 자동 연결하지 않았다.

## 7. 시험·재현

작업 루트에서 실행한다.

```powershell
python -m unittest discover -s tests/rag -v
python -m compileall -q services/rag tests/rag
git diff --check -- services/rag tests/rag docs/ai/climate/CLIMATE_VECTOR_RAG_DESIGN.md
```

현재 합성 시험 **18 PASS/0 FAIL, 0.044초**다. 16종 노드·11종 관계, domain/range·SUPERSEDES·위조 span/SHA/authority·dangling edge, 필수 metadata·ACL, 비공개 통계 격리, 라이선스/만료, 공간·시간·CF 달력 필터, 순위 재현성·tie-break, 공간/시간 점수, 인용 재검증, 3개 언어 alias, 정량 질문의 무조건 도구 경로와 빈 RAG 답변을 검사했다.

상태를 분리한다: 코드 계약은 TESTED_SYNTHETIC, 실제 문서 ingestion/권한 검토·semantic embedding 평가·실서비스 role binding·structured climate tool 연동은 BLOCKED/후속 Gate다. 외부 요청·LLM/embedding 호출·수치 분석·기관 승인·과학적 검증 실행은0이다.

## 8. 통합·이해자료 인계

Root 인계 파일: `services/rag/{ontology,routing,retrieval}.py`, `tests/rag/test_climate_rag.py`, 본 설계서. API/UI 공통 파일은 변경하지 않았다. UI에 아직 연결되지 않은 Python 내부 계약이므로 화면 검증은 수행하지 않았다. 향후 API가 연결되면 tool-only 차단·ACL·인용 오류 계약을 web_ui에 별도 인계해야 한다.

이해 담당은 쉬운 설명→배경→코드 흐름→합성 시험→발표→FAQ에 ‘문서 설명 검색과 기후 숫자 조회의 분리’, ‘source authority의 선언과 기관 검증의 차이’, ‘합성 hash-vector와 실제 embedding의 차이’를 포함해야 한다. 이해자료 공통 경로는 직접 수정하지 않는다.

최종 확인: unittest18 PASS, compileall 종료0. git diff --check 종료0이나 현재 신규 파일은 untracked이므로 이 명령만으로 신규 파일 전체 검증을 주장하지 않는다. 원본/권한 계약과 합성 시험을 구분해 Root에 인계했다.
