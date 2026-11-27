# v4.2 기후·RAG 용어집

- updated_at: 2026-11-26 KST
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
| aggregate 재감사 | Aggregate re-audit | 새 관측과 기존 exact geometry를 합집합해 36셀 수량·공간피복을 다시 계산하는 절차. 이번 pilot 후 완료 |
| 관측 창 참고량 | Observed-window reference bytes | 실제 한 COG 창의 byte를 후보 수만큼 단순 곱한 값. 전체 gap 견적이나 실행 승인이 아님 |
| Snapshot | 시점 고정 상태 | source pin과 계산 시점을 고정한 감사값. pilot 전·후 값을 섞어 쓰지 않음 |
| 주 균형 순회 | Province-balanced round-robin | 한 주를 재방문하기 전에 다른 주를 먼저 방문해 짧은 실행의 지역 편향을 줄이는 순서 |
| 품질 공백 | Quality gap | 7개 asset 전송은 완전하지만 SCL clear 기준에 미달한 관측. 전송 실패와 분리하고 학습 적격에서 제외 |
| 전송 실패 | Transfer failure | 429, asset 누락, 불완전 계측 등 완전 observation을 만들 수 없는 상태. 후속 요청을 중단 |
| 결과 registry | Result registry | 고정 증거에서 만든 불변 결과 snapshot과 append-only 검토 revision을 저장하는 로컬 SQLite 저장소 |
| 결정적 결과 ID | Deterministic result ID | domain·source key에서 반복 가능하게 만든 ID. 같은 payload는 멱등, 다른 payload는 충돌 |
| 증거 상태 | Evidence state | 근거 자체의 검증 수준. `VERIFIED_REAL`, `TESTED_SYNTHETIC`, `IMPLEMENTED_UNVERIFIED`, `BLOCKED`, `PLANNED` 중 하나 |
| 검토 상태 | Review status | 사람의 접수·검토 진행 상태. `PENDING`, `CHANGES_REQUESTED`, `ACCEPTED`; 증거 상태와 별도 |
| 검토 revision | Review revision | 기존 결정을 덮어쓰지 않고 순번으로 추가한 수정 요청·검토 완료 이력 |
| 낙관적 동시성 | Optimistic concurrency | 클라이언트가 본 revision과 현재 revision이 다르면 충돌로 거절해 검토 덮어쓰기를 막는 방식 |
| 결과 재조회 | Result readback | 등록 ID로 결과를 다시 읽고 payload digest와 ID가 등록 시점과 같은지 확인하는 단계 |
| 미정산 전송 | Unsettled transfer | 예약과 I/O 시작 기록은 있으나 receipt·실제 byte가 확정되지 않은 상태. 재개 전 검증·정산 필요 |
| 결과 카탈로그 | Result catalog | 기존 결과 ID에 출처·수치·공간 layer·보고서·불확실성을 내용 digest로 고정한 패키지와 결정 상태 |
| 패키지 digest | Package SHA-256 | 정규화된 결과 패키지 전체의 내용 해시. 결과 ID와 다르며 승인 근거를 특정 패키지 revision에 결속한다. |
| 과학 결정축 | Scientific decision axis | `INDEPENDENT_SCIENTIFIC` 범위의 승인·거절 이력. 일반 업무 검토나 기관 게시 승인과 별도 |
| 게시 결정축 | Publication decision axis | `INSTITUTIONAL_PUBLICATION` 범위의 기관 게시 승인·거절 이력. 실제 기관 인증·권리를 자동 뜻하지 않음 |
| 불확실성 미보고 | `NOT_REPORTED` uncertainty | 오차가 0이라는 뜻이 아니라 신뢰구간·독립 관측 오차·위치 정확도를 산정하지 않았다는 상태 |
| 공개 적격 | Release eligible | 현재 패키지에 대해 과학·게시축이 모두 승인되고 게시 결정이 현재 과학 revision에 결속된 상태 |
| 기관 작업 승인 | Institutional job approval | 공급자·연산·모델 버전·입력·만료시각을 운영자가 미리 고정한 문서. API 요청에서 URL·명령을 바꾸지 못하게 함 |
| 멱등 작업 ID | Idempotent job ID | 같은 승인·공급자 설정에 같은 ID를 사용해 응답 단절·재시도 때 중복 기관 작업을 줄이는 식별자 |
| 제어면 | Control plane | 승인·공급자·작업 상태·모델 버전과 실행 허용을 결정하는 경로. 실제 원본·산출물 전송과 구분 |
| 데이터면 | Data plane | 원본·모델·산출물·보고서 바이트를 저장하고 전달하는 경로. 제어면의 승인과 SHA 결속을 따라야 함 |
| scene 격리 후보 | Scene quarantine candidate | split을 넘나드는 원본 scene 전체를 제외해 scene 충돌을 없앤 새 불변 manifest. 학습 승인을 자동 뜻하지 않음 |
| 모델 release | Model release | model/version과 ONNX·dataset·training·evaluation·환경·보안·rollback·승인을 SHA로 결속한 실행 후보 |
| 기관별 행 보안 | Row-Level Security, RLS | 인증한 서버 세션의 기관 범위만 DB 행을 읽고 쓰게 하는 PostgreSQL 정책. 요청 본문의 기관명은 신뢰하지 않음 |
| 서명 다운로드 링크 | Presigned download URL | 등록 자산을 짧은 TTL 동안 읽는 URL. 링크 보유자는 만료 전 접근 가능하므로 로그·공유 금지 |
| 기술 이식 | Technical portability validation | 같은 이미지·API·고정 원본을 Docker 또는 Kubernetes 환경에서 재현하는 검증. 기관 운영 승인·과학 인수·독립 정확도와 별도 |
| 기관 운영 인수 | Institutional production acceptance | 기관 provider·권한·IAM/SSO·백업/복구·RPO/RTO·가용성을 승인하는 절차. 로컬 Compose/Kubernetes PASS가 자동 대체하지 않음 |
| 토지피복·토지이용 변화 | Land Cover/Land Use Change, LCLUC | 서로 다른 시점의 분류지도를 같은 분류·공간 지지집합에서 비교하는 분석. 합성 계산 성공이 실제 변화 검증은 아님 |
| 분류사전 | Taxonomy | 코드·명칭·주제/품질 역할·NoData·버전·출처 SHA를 고정한 정의. 특정 연차 자산의 승인과 별도 |
| 주제 클래스 | Thematic class | 모델 출력과 토지피복 통계의 대상. KLHK 23코드 중 22개이며 구름 품질코드는 제외 |
| 품질 코드 | Quality/QA code | 관측 품질을 표시하는 공식 코드. KLHK `2500 Awan`은 사전에 보존하지만 변화·학습 주제에서 제외 |
| 분류 대응표 | Crosswalk | 서로 다른 분류체계의 코드를 대응시키는 규칙. 의미 손실·제외를 기록하며 기관 승인 없이는 공식 변환이 아님 |
| 공통 유효 지지집합 | Common valid support | 두 시점 모두 NoData·구름·mask가 아닌 픽셀의 교집합. 변화율과 전이면적의 분모 |
| 전이행렬 | Transition matrix | 행은 이전 클래스, 열은 이후 클래스인 면적/픽셀 표. 대각선은 유지, 비대각선은 변화 |
| 변화 집중지역 | Change hotspot | 인접 변화 픽셀을 연결하고 최소 면적으로 거른 공간 객체. 독립 정확도나 원인 판정은 아님 |
| 보정되지 않은 불확실성 | Uncalibrated uncertainty | 최대확률·entropy가 실제 오류확률과 일치하도록 calibration되지 않은 상태. 확률을 독립 정확도로 해석하지 않음 |
| 연차 입고 번들 | Annual intake bundle | 지역·연도·revision별 원본 경로, byte, SHA, 출처, 분류사전과 두 센서 필수 밴드·QA를 고정한 `lcluc-annual-input/1` manifest 묶음 |
| 연차 run ID | Annual run ID | `bundle.json` 원본 byte의 SHA-256으로 만든 반복 가능한 식별자. 과학 승인이나 모델 release ID는 아님 |
| 물리 피복률 | Physical coverage fraction | 경계 안 픽셀 중 센서의 여섯 밴드가 모두 실제 존재하는 비율. clear 비율·분류 정확도와 다름 |
| 동년 센서 간 지도 일치도 | Same-year cross-sensor map agreement | 같은 해 Sentinel-2 RF 후보와 Landsat RF 후보의 공통 격자 분류 일치. 두 모델이 같은 오류를 낼 수 있어 독립 정확도가 아님 |
| 약한 지도 참조 일치도 | Weak-map reference agreement | WorldCover·Esri 같은 보조 지도와 후보 지도의 일치. 동년 진단값이며 독립 현장 정확도나 타연도 정답이 아님 |
| 방향 전이 | Directed transition | 기준 연도 클래스→비교 연도 클래스의 순서를 보존한 전이. 역방향과 다른 셀·지도임 |
| 발행자 주 통계 | Publisher province statistics | 공급자가 주 단위로 발행한 집계표. 사용자 AOI로 재계산한 통계나 다른 제품의 픽셀 집계가 아님 |
| 제품 간 지도 일치도 | Cross-product map agreement | 같은 연도·공통 격자·공통 crosswalk에서 두 지도 제품의 분류가 같은 비율. 독립 정확도가 아님 |
| 후보 RF | Candidate Random Forest | 승인된 동년 라벨로 센서별 생성하는 재현 가능한 후보 모델. production release·운영 활성화·보정된 확률을 뜻하지 않음 |
| 독립 검증 제외 완충 | Independent validation exclusion buffer | 학습 표본 위치와 인접 1셀을 독립 평가에서 제외해 공간 누출을 줄이는 규칙 |
| native 해상도 | Native resolution | 공급 원본 자체의 픽셀 크기. Sentinel-2 B02·B03·B04·B08은 10m, B11·B12·SCL은 20m이며 30m 분석격자와 구분 |
| 연차 광학 합성 | Annual optical composite | 같은 연도의 승인 장면을 날짜·scene ID 순서로 읽어 여섯 band와 QA를 만족하는 첫 유효 픽셀을 선택한 결정적 영상 |
| 화면용 PNG | Display PNG | Web Mercator에서 빠르게 보여 주는 파생 layer. 분석 GeoTIFF의 격자·band를 대신하지 않음 |
| 사각형-경계 교차 AOI | Rectangle-boundary intersection AOI | 사용자가 그린 bbox 중 반텐 경계와 겹치는 부분만 equal-area 픽셀 중심으로 집계하는 범위 |
| 맑은 관측 수 | Clear observations | QA와 경계·밴드 유효성 검사를 통과한 픽셀별 관측 횟수. 분류 정확도와 별도 |
| 공간 블록 홀드아웃 | Spatial block holdout | 인접 픽셀 누출을 줄이기 위해 공간 블록 전체를 학습 또는 평가 중 한쪽에 배정하는 분리 방식 |
| 변화 발생시점 | Change timing | 픽셀 시계열에서 변화가 시작되거나 확정된 시점을 추정한 값. 주 단위 연차 면적 차이와 별도 |
| 공간 sieve | Spatial sieve | 같은 값의 연결 성분 중 최소 픽셀보다 작은 패치를 주변 분류로 보정하는 공간 필터 |
| 보정 위치 면적 | Correction footprint area | 후처리 때문에 분류 값이 바뀐 픽셀의 면적 합계. 연차 토지피복 변화면적과 별도 |
| 쌍대 공간 홀드아웃 | Paired spatial holdout | 같은 고정 공간 평가 표본으로 처리 전후 지표를 계산해 표본 변경 효과를 차단하는 비교 방식 |
| Siamese U-Net | Siamese U-Net | 두 시점 입력을 공유 encoder로 처리하고 특징 차이에서 변화 후보를 분류하는 신경망. 이번 값은 Esri 연차 차이 약한 참조 기반 |
| 변화 클래스 F1 | Change-class F1 | 변화 클래스의 precision과 recall 조화평균. 전체 일치도와 독립 정확도와 별도 |
| 특화 분류층 | Specialist classification layer | 해안·논·플랜테이션처럼 특정 주제를 동년 승인 라벨로 분류한 mask와 provenance 묶음 |
| 계층 통합 | Hierarchical integration | 기본 분류 위에 승인된 특화층을 우선순위·적격 클래스·NoData 보호 규칙으로 합치는 절차 |
| 원문 pin 인용 | Source-pinned citation | 문서 byte·SHA·버전·페이지가 고정된 원문만 검색 결과에 인용하는 방식 |
| 로컬 어휘 근거 검색 | Local lexical evidence retrieval | 질의 token과 교차언어 alias로 원문 청크를 찾는 검색. embedding과 생성 답변을 사용하지 않음 |
| 경량 DeepLabv3+ | Compact DeepLabv3+ | 여섯 밴드 encoder, ASPP와 저수준 특징 decoder를 사용하는 CPU 시험 분류기. 이번 구현은 사전학습 가중치 없이 학습 |
| 원본별 면적 집계 | Native product area tabulation | 서로 다른 경계·격자·분류체계의 각 제품을 원래 클래스 표와 총계로 별도 표시하는 집계. 클래스 차이·전이·독립 정확도와 별도 |
