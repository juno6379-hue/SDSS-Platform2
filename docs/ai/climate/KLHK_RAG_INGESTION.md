# KLHK 공식 metadata·CCKP 문서의 불변 RAG ingestion

상태: **실제 취득 VERIFIED_REAL / 운영 게시 BLOCKED / 인덱스 연결 TESTED_SYNTHETIC**. 전체 데이터 취득·기관 authority 인증·실제 embedding 품질 검증·수치 RAG 답변 완료가 아니다.

## 1. 경로와 이관 범위

작업 루트는 `E:\SDSS-Platform2`다. 변경 소유 경로는 `services/datahub/connectors/klhk/`, `services/rag/ingestion/`, `tests/klhk_rag_ingestion/`, 본 문서, `evidence/klhk_rag/`다. 기존 `E:\GeoAI–MLOps–SDSS\backend/app/data/official_spatial_connectors.py`는 후보 service/item/layer URL을 읽기만 했으며 수정·실행하지 않았다. 기존 RAG core·CCKP connector·공통 API/UI·루트 설정도 변경하지 않았다.

KLHK2021/2022 service, 2023 webmap item, 2024/2025 layer 후보를 별도 connector에 이관했다. 실제 요청은 2021·2024·2025만 수행했다. 미조회 연도와 item은 후보이며 확인된 실제 접근·연도·23클래스·라이선스로 표현하지 않는다. One Map·Esri·WorldCover fallback은 없다.

## 2. 실제 취득 결과

증거 기준은 `evidence/klhk_rag/verification-20261124.json`이다.

| 구분 | 실제 결과 | 해석 |
|---|---|---|
| World Bank 공식 GitHub repo metadata | 원본·receipt·SHA 보존 | repository 접근 확인, 모든 CCKP 자산의 사용허가 아님 |
| 공식 repo commit·root file list | 실제 API로 commit 및 파일 존재 확인 | 추정 branch/숨겨진 URL 사용 없음 |
| commit 고정 README.md | 실제 취득·문자 span staging | 문서 ingestion 성공, 운영 검색 게시 아님 |
| commit 고정 LICENSE | Mozilla Public License Version2.0 원문 취득 | README/개별 데이터/S3에 동일 적용된다고 자동 판정하지 않음 |
| KLHK2021 service | SOURCE_REQUEST_FAILED:URLError | BLOCKED |
| KLHK2024 layer metadata | 연도·Feature Layer·field 실제 확인 | native23 domain·license 미검증으로 BLOCKED |
| KLHK2025 layer metadata | 연도·Feature Layer·field 실제 확인 | native23 domain·license 미검증으로 BLOCKED |
| 공식 SIGAP 사전 HTML | 최초8초 timeout, 이후 단1회15초 상한 재시도에서 크기 초과 | BLOCKED, HTML 원본 취득 성공으로 기록하지 않음 |

CCKP 문서 commit은 **`ac98dd008f6d201361abf16d64d5b72bc8c6fbf2`**다. connector 실측 **10요청·381,676B 본문 계측**, 취득 원본 **7문서·122chunk**를 보존했다. 최초 묶음은9요청·119,531B다. 사전 재시도는 크기 초과 탐지용 한 byte를 포함해262,145B를 읽고 차단했으며 실패 본문을 정상 문서로 보존·게시하지 않았다. TLS·로그인·403/429 제한을 우회하지 않았다.

실제 KLHK2024 SHA는 `ea48c840a8669c53a0e9dab8d44c532c9c34f36844b2200be1087e9e2e0b56df`, 2025는 `37c48647d7295c9940d350fd37884263d49ccf1d16f8fa485aa2f59acdbf6332`다. 두 metadata의 native field는 각각 PL2024_ID_50K/PL2025_ID_50K이고 coded domain은 없으며 renderer는 **25항목**이다. 이를23개로 임의 trim·재분류하지 않았다.

공식 사전의23클래스 정의는 별도 웹 열람에서도 확인했지만, 이는 runtime의 HTML 다운로드 receipt가 아니다. 기대 code표는 [공식 SIGAP 사전](https://sigap.kehutanan.go.id/tema-kamus/575)을 기준으로 하며 실제 연차 layer의 native domain 검증과 분리한다. 실제 파일들의 정확한 URI·버전·취득시각·SHA는 receipt가 권위 근거다.

## 3. bounded connector·불변 저장

`source.py`는 다음을 적용한다.

- HTTPS·정확한 공식 host allowlist, World Bank repository path pin, user/password·비밀 query 거부
- redirect를 따르지 않음. 비공개 API 탐색·URL 패턴 대량 추측·bucket sync 없음
- 기본 최대12요청·총2MiB·문서256KiB·요청8초. 생성자 상한16요청·총4MiB·문서512KiB·15초
- 429 이후 같은 transport의 모든 후속 요청 중지, 예산 초과 전 차단
- Content-Length 선확인, bounded stream read, 초과 탐지 byte까지 총 byte 예산 내 예약
- `.raw`와 receipt를 URL+본문SHA 식별자로 저장. fsync한 임시 파일의 hard-link 게시로 기존 파일을 덮지 않음
- 기존 원본 변조·receipt source/version/license/state 충돌은 실패. 첫 취득시각·원본 receipt 보존

KLHK metadata 판정은 layer 연도·23개 native code domain·licenseInfo·Feature Layer·Query capability를 별도 확인한다. copyrightText나 공개 화면이 있다는 이유로 라이선스·실 다운로드 권한을 승인하지 않는다. 판정 함수만 통과한 합성 payload는 IMPLEMENTED_UNVERIFIED이고, 실제 transport receipt가 있어야 실제 취득으로 분류한다. 모의 transport는 TESTED_SYNTHETIC이다.

본 connector는 metadata/document 전용이다. GeoJSON feature 대량 다운로드·Shapefile export·학습·모델 승인 기능은 구현하지 않았다.

## 4. RAW → source span → KG → index

1. receipt의 source_uri/source_id/version/raw SHA·byte수·취득시각을 읽는다.
2. `stage_document`는 trusted raw_root 내부의 `.raw`만 허용하고 최대512KiB 및 SHA를 검증한다.
3. UTF-8 strict decode. HTML은 script/style을 제외한 text를 별도 hash로 고정한다. parser_version과 raw→text SHA를 보존한다.
4. Unicode 문자 `[start,end)` 범위로 chunk를 만든다. HTML span은 추출 text의 offset이지 원본 HTML byte offset이 아니다.
5. 기존 SourceDocument/SourceSpan/KnowledgeGraph를 그대로 사용해 Document·Chunk·CITES를 만든다. 연차 면적·기후 수치나 기관 승인 관계를 생성하지 않는다.
6. stage JSON과 KG sidecar를 불변 보존한다. 원문 취득 및 구조적 KG 생성과 운영 검색 게시를 분리한다.
7. `ingest_curated`는 CurationReview(원본SHA·reviewer·license·license 근거URI·access/validity review)를 요구한다. 이후 기존 ChunkMetadata의 ACL/ko-id-en/authority/license/validity/spatial/time/variable/scenario/model/claim authority를 검증한다.
8. Encoder/Sink Protocol로 embedding·atomic upsert를 연결한다. 모든 span·메타데이터·벡터 수/차원/유한값 검증 후 한 번만 sink를 호출한다. 외부 network encoder는 거부한다.

기본 SyntheticHashEncoder와 MemoryVectorSink는 합성 검증용이다. 실제 embedding 성능이나 운영 vector DB가 아니다. plugin은 신뢰된 서버 코드에서 등록하고 atomic upsert를 보장해야 한다. 반환된 기존 HybridIndex는 현재 core의 합성 hash-vector 검색을 사용하며, 외부 vector DB의 검색 adapter 교체는 범위 밖이다.

## 5. 검토 Gate와 남은 차단

- 공식 host 접근·TLS 연결은 기관 authority 인증이 아니다. receipt는 HOST_PINNED_NOT_INSTITUTION_CERTIFIED다.
- LICENSE 원문 발견은 개별 문서·데이터 재사용 범위 승인과 다르다. 실제 취득 receipt의 license는 NOT_VERIFIED, retrieval_permitted=false를 유지한다.
- 일반 README에 verified 공간·시간·변수 범위가 없으면 임의 전지구 bbox나 전체 기간을 넣지 않는다. 현재 core는 spatial/time tuple을 요구하므로 검토 전 문서는 staging에 남는다. `not_applicable/unknown` 범위 지원이 필요하면 Root가 공통 계약을 별도 확정해야 한다.
- 실제 취득 문서의 metadata_factory를 임의 생성하지 않았다. 운영 공개 index 게시0, 외부 embedding/LLM 호출0, 숫자 RAG 답변0이다.
- KG span·관계 타입 검증은 문서 내용의 과학적 진실·법적 효력·기관 서명을 자동 인증하지 않는다.
- KLHK native23클래스/라이선스·익명 Query/실 다운로드 허용은 추가 확인 전 BLOCKED다. 25항목 renderer를 정답23클래스로 간주하지 않는다.

기존 RAG routing/citation verifier를 수정하지 않았다. 정량 질문은 climate.query adapter 경로로만 보내고 RAG answer=None을 유지한다. 현재 ingestion에서 실제 구조화 기후 도구를 실행하지 않는다.

## 6. 합성 시험과 실제 증거

```powershell
# 네트워크 없음: 계약·gate·ACL·원문·index 시험
python -m unittest discover -s tests/klhk_rag_ingestion -v
python -m unittest discover -s tests/rag
python -m compileall -q services/datahub/connectors/klhk services/rag/ingestion tests/klhk_rag_ingestion
python -m ruff check services/datahub/connectors/klhk services/rag/ingestion tests/klhk_rag_ingestion

# 계획만 출력하며 원격 호출0
python -m services.rag.ingestion.acquire --output evidence/klhk_rag/NEW_EMPTY_RUN
# 재취득이 필요할 때만 명시적으로 --execute. 기존 raw/receipt는 덮지 않음.
```

주요 시험: 공식 host/repo pin, 과대 Content-Length 본문 미읽기, budget/429 stop, immutable duplicate·변조, 연도/23클래스/라이선스 분리, 모의응답을 실제 검증으로 오표시하지 않음, RAW/path/취득시각 결속, HTML Unicode span, review 누락·라이선스 미검토·invalid vector·외부 encoder 차단, KG·벡터·ACL·인용 연결과 정량 답변 금지.

실제 증거:

- `evidence/klhk_rag/live-20261124-1/summary.json`: 최초9요청, 공식 원본/receipt/staging
- `.../klhk-metadata-ingestion.json`: 실제KLHK2024/25 metadata의 문서 staging 추가 기록
- `.../raw/`, `.../staged/`, `.../graphs/`: 원본 및 receipt, 122개 문자 span, Document/Chunk/CITES sidecar
- `evidence/klhk_rag/dictionary-20261124-bounded-retry/summary.json`: 사전1회 재시도·크기 차단
- `evidence/klhk_rag/verification-20261124.json`:10요청/381,676B·7문서/122chunk·게시0 통합 확인
- `evidence/klhk_rag/synthetic-tests.xml`: 네트워크 없는 합성 회귀 시험 기록

## 7. 통합·이해자료 인계

Root가 CLI/API에 연결할 때 caller가 임의로 reviewer/ACL 역할을 선언하게 두지 말고 인증된 curator principal과 라이선스/유효성 검토 기록을 결속해야 한다. 현재 CurationReview는 라이브러리 계약이며 로그인·권한 발급을 대체하지 않는다. 실제 취득 문서를 UI에 표시할 때 원문 보존 성공, metadata 검증, RAG 게시, 기관 authority 인증, embedding 품질을 각각 분리해야 한다.

완료 코드·합성 시험·실 취득 근거를 understanding_agent에 인계해 쉬운 설명/대본/FAQ/INDEX를 갱신한다. 공통 UI/API·이해자료 경로는 이 작업에서 수정하지 않았다. 전체 플랫폼 완료가 아니라 ingestion 계약과 제한된 실제 접근성 검증 단위다.

### 최종 검증 기록

합성 ingestion11개와 기존RAG18개, 합계 **29 tests PASS, failures0/errors0**를 pytest로 재검증하고 synthetic-tests.xml에 보존했다. ruff check PASS, format check6파일 PASS, compileall PASS다. git diff --check는 종료0이나 신규 untracked파일 검사를 대신하지 않으므로 별도 lint/format/compile/test를 근거로 삼는다. 실제7원본의SHA 불일치0·122span/KG 보존을 확인했다. HTTP10건/381,676B는 Python connector와사전단1회재시도 범위이고 공식출처 웹도구 조사 요청·전송량은 포함하지 않는다. 원격 추가실행·embedding key·수치답변·운영 index 게시0을 유지한다.
