# v4.2 기후·RAG 용어집

- updated_at: 2026-11-24 KST
- status: `IMPLEMENTED_UNVERIFIED` 문서; 코드 계약과 용어를 대조했다.

| 한글 | 영문/약어 | 프로젝트 적용 의미 |
|---|---|---|
| 기후변화 지식포털 | Climate Change Knowledge Portal, CCKP | World Bank 기후 자료 원천. 한 ERA5 CDD global 원본과 개발 bbox 통계만 실제 검증했다. |
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
| 원문 고정 | Immutable raw | 최초 취득 원문과 receipt를 덮어쓰지 않고 SHA 충돌·변조를 차단하는 계약 |
| 원문 span | Source span | 원문의 정확한 Unicode 문자 `[start,end)` 범위. 내용 진실이나 기관 인증을 뜻하지 않음 |
| 큐레이션 검토 | Curation review | license 근거, ACL, 유효기간, reviewer와 원문 SHA를 확인하는 운영 게시 전 Gate |
| native 23-class | Native 23-class domain | 실제 연차 layer field의 23개 coded value가 공식 code 집합과 일치함을 뜻함. renderer 25항목과 다름 |
| 학습 Gate | Training gate | 데이터 완전성·공간피복·밴드/SCL·split·누출·SHA를 확인해 학습 허용 여부를 판단 |
| 배포 Gate | Deployment gate | 독립정확도·보안·rollback·registry·환경·운영승인을 확인해 배포 허용 여부를 판단 |
| 연속건조일 지수 | Consecutive Dry Days, CDD | 연간 1mm 미만 강수일의 최장 연속 길이 지수. 이번 결과 단위는 days |
| 기후평년/기후요약 | Climatology | 기준기간을 요약한 필드. 연별·월별 시계열과 다름 |
| 재분석 | Reanalysis | 관측과 모델을 자료동화한 기후 자료. 독립 현장 ground truth와 동일하지 않음 |
| bbox 면적가중 평균 | Bbox area-weighted mean | bbox 셀 중심으로 선택한 full cell의 구면 면적 비례 평균. 행정경계 평균이 아님 |
| 추적 ID | Trace ID | 요청·자료·결과를 연결하는 식별자 |
| 공간 bbox | Bounding box | WGS84 west/south/east/north. 과학적 면적과 동일하지 않음 |
| 약한 참조 일치도 | Weak agreement | WorldCover/KLHK 등 참조와의 일치 정도. 독립 정확도가 아님 |
| 수량 완전성 | Count completeness | 셀별 최소 패치 수 같은 개수 기준. 공간 완전성과 다름 |
| 공간 피복률 | Spatial coverage | 경계 면적 중 패치 footprint 합집합이 차지하는 비율 |
| paired-present 피복률 | Paired-present coverage | 비교 가능한 paired 자료가 동시에 존재하는 면적 비율. 이번 감사값은 0.976741% |
| 내용 주소 저장소 | Content-Addressed Storage, CAS | 파일 내용을 digest로 식별하는 저장 방식. 품질·라이선스·대표성을 보증하지 않음 |
| 장면·자산·기간 고정 | Scene/asset/window pin | 재수집 시 같은 scene·asset·time window를 가리키는 승인된 식별 정보 |
| 합성 해시 임베딩 | Synthetic hash embedding | 계약시험과 private review용 결정적 feature hashing. 운영 semantic 품질 증거가 아님 |
| 예약·실측 정산 | Reservation and measured settlement | 원격 I/O 전 최대 byte를 예약하고 완료 후 실제 읽은 byte로 원장을 정산하는 절차 |
| 단일 pilot | Single pilot | 봉인된 scene·asset·window 한 건만 실행한 검증. 전체 수집 승인을 뜻하지 않음 |
| aggregate 재감사 | Aggregate re-audit | 새 관측을 포함해 36셀 수량·공간피복을 다시 계산하는 절차. 이번 pilot 후 아직 수행하지 않음 |
