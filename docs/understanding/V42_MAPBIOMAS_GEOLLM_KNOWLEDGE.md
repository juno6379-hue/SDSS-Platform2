# MapBiomas Indonesia GeoLLM 지식 검색 이해자료

- updated_at: 2026-11-26 KST
- source_commit: `UNCOMMITTED_WORKTREE`
- evidence_paths:
  - `docs/lcluc/MAPBIOMAS_GEOLLM_KNOWLEDGE.md`
  - `services/rag/mapbiomas.py`
  - `frontend/src/MapbiomasKnowledge.tsx`
  - `tests/rag/test_mapbiomas.py`
  - `artifacts/lcluc/mapbiomas-knowledge.log`
  - `artifacts/lcluc/banten-models-knowledge-edge.log`
- overall_status: `VERIFIED_REAL`

## 1. 쉬운 설명

### 한 문장으로

MapBiomas Indonesia 공식 기술자료 14건을 원문 SHA와 페이지로 고정하고, 한국어·영어·인도네시아어 질문에서 관련 원문 문단과 출처 링크를 돌려주는 로컬 근거 검색을 구현했다.

### 현재 확인된 범위

- `VERIFIED_REAL`: R01~R14 14건의 원문·SHA·페이지를 보존했다. 이 중 P0 핵심 근거는 9건이다.
- `VERIFIED_REAL`: 286개 원문 청크와 44개 용어, 25개 참조 지도, 5개 특화 범례 코드를 구조화했다.
- `VERIFIED_REAL`: Edge에서 한글·영문 3질의를 실행하고 PDF 원문 페이지와 출처 링크를 확인했다.
- `VERIFIED_REAL`: 검색 시 원본 byte와 SHA를 다시 확인한다. 원본이 바뀌면 해당 인용을 반환하지 않는다.
- `BLOCKED`: 현재 mode는 로컬 어휘 근거 검색이다. 음성, embedding 의미검색, 생성형 답변과 공개 운영 색인은 제공 대기다.
- `BLOCKED`: R11은 인포그래픽 목록 HTML만 보존됐다. 동적 인포그래픽 내용과 OCR 해석은 미수집 범위다.
- `VERIFIED_REAL`: Collection 4.1 통계 XLSX와 반텐 1990~2024 35년·11클래스 발행 통계를 연결했다.
- `VERIFIED_REAL`: Collection 4.1 XLSX의 `TRANSITION`에서 반텐 레코드 113행과 2023→2024 등 발행 기간 열을 확인했다.
- `VERIFIED_REAL`: 정제된 전이 자료는 [GeoLLM 정형 GIS 질의](V42_LCLUC_GEOLLM_QUERY.md)의 산림 총전환과 방향 전이 수치 도구에 연결됐다.

## 2. 이론적 배경

### 2.1 근거 검색과 생성 답변의 분리

현재 검색은 질문의 핵심 용어를 원문 청크와 대조하고 관련도가 높은 최대 5개 인용을 반환한다. `answer`는 `null`이다. 따라서 사용자는 발췌문·문서명·페이지·원 URL을 직접 확인할 수 있고, 생성 모델이 문장을 재구성한 답변과 구분된다.

### 2.2 원문 pin과 페이지 인용

문서마다 URL, 버전, 언어, byte, SHA-256, 로컬 원문 경로를 저장한다. PDF 청크에는 페이지를, HTML 청크에는 위치를 기록한다. 검색 직전 byte와 SHA가 index의 pin과 일치하는지 검사하므로 변경된 파일의 인용을 fail-closed한다.

### 2.3 교차언어 어휘 검색

한국어 질의를 영어·인도네시아어 공식 용어와 연결하는 alias를 사용한다. 예를 들어 맹그로브 질문은 `mangrove`가 있는 범례·ATBD 청크를 찾는다. 의미 embedding 품질을 가정하지 않고 공식 용어와 원문 일치에 집중한다.

## 3. 코드·데이터 동작

1. `build()`가 고정 R01~R14 목록의 공식 원문을 제한 크기로 취득한다.
2. PDF와 HTML 형식을 검사하고 SHA가 포함된 immutable raw를 저장한다.
3. PDF는 페이지별 텍스트를 800~1,000자 청크로 나눈다.
4. ATBD·범례·용어집·참조 지도에서 44/25/5 구조화 항목을 만든다.
5. `search()`가 원문 pin을 재검증하고 한국어 alias와 질의 token으로 청크를 정렬한다.
6. UI는 발췌문, 문서 ID·제목·버전·페이지와 공식 출처 링크를 보여 준다.

| API | 역할 |
|---|---|
| `GET /api/rag/mapbiomas/catalog` | 14개 자료, P0 수, 구조화 수, unavailable 상태 조회 |
| `POST /api/rag/mapbiomas/search` | 로컬 어휘 검색과 pin 검증된 인용 반환 |
| `POST /api/rag/query` with `scope=mapbiomas-indonesia` | 같은 검색기를 공통 RAG 경로에서 호출 |

### LANDY 자료 세 범주

| 범주 | 상태 | 현재 범위 |
|---|---|---|
| 문서형 지식자료 | `VERIFIED_REAL` | R01~R14 원문·286청크와 GeoLLM 인용 검색 |
| 정량 통계자료 | `VERIFIED_REAL` | Collection 4.1 원본 XLSX, 반텐 1990~2024·11클래스 연차 통계 |
| 발행 전이 원본 | `VERIFIED_REAL` | XLSX의 `TRANSITION` 반텐 113행을 정제해 GeoLLM 총전환·방향 전이 도구에 연결 |
| 4.1 공간 원본 | `BLOCKED` | 반텐 분류·전이 GeoTIFF와 모자이크 미확보 |

## 4. 시험 증거와 상태

| 항목 | 상태 | 증거와 범위 |
|---|---|---|
| 공식 원문 보존 | `VERIFIED_REAL` | R01~R14 14건, P0 9건, 원문 SHA·페이지 |
| 구조화 index | `VERIFIED_REAL` | 286청크, 용어 44, 참조 지도 25, 범례 5 |
| 실제 Edge 검색 | `VERIFIED_REAL` | 한글·영문 3질의, PDF 페이지·원문·출처 링크 |
| pin 변경 보호 | `TESTED_SYNTHETIC` | 원문 byte 변경 뒤 citations 0 |
| 모델·RAG 관련 회귀 | `TESTED_SYNTHETIC` | 24 pytest PASS |
| 음성·embedding·생성 답변 | `BLOCKED` | 현재 로컬 어휘 근거 모드, `answer=null` |
| R11 인포그래픽 내용 | `BLOCKED` | 목록 HTML만 보존, 동적 내용·OCR 미확보 |
| 4.1 연차 통계 | `VERIFIED_REAL` | 원본 XLSX와 반텐 35년·11클래스 연결 |
| 4.1 전이 수치 도구 | `VERIFIED_REAL` | 공식 XLSX의 반텐 코드·기간과 SHA를 검사해 총전환·방향 전이를 조회. [GeoLLM 질의](V42_LCLUC_GEOLLM_QUERY.md) |

## 5. 발표 스크립트

### 1분

“GeoLLM 지식 검색은 MapBiomas Indonesia 공식 자료 14건을 원문 SHA와 페이지로 고정했습니다. P0 핵심 9건을 포함해 286개 청크, 44개 용어, 25개 참조 지도, 5개 특화 범례 코드를 구조화했습니다. Edge에서 한글과 영어 3질의를 검색해 PDF 원문 페이지와 공식 출처 링크를 확인했습니다. 검색 직전에 원본 SHA를 다시 확인하고 변경된 파일의 인용은 차단합니다. 현재는 생성 답변이 아니라 근거 발췌 검색이며 음성·embedding·공개 운영 색인은 후속 Gate입니다.”

### 5분 핵심 순서

1. 공식 자료 목록 R01~R14와 우선순위를 고정한다.
2. 원문 byte·SHA·버전·언어·페이지를 저장한다.
3. PDF 페이지와 HTML을 검색 가능한 286개 청크로 나눈다.
4. 용어·참조 지도·특화 범례를 별도 구조로 만든다.
5. 한국어 alias와 공식 영문·인도네시아어 용어를 연결한다.
6. 검색 직전 원문 pin을 재검증한다.
7. 최대 5개 발췌문과 원문 페이지 링크를 반환한다.
8. 생성 답변·embedding·음성·공개 배포는 현재 증거 범위와 분리한다.

## 6. Q&A

**Q. GeoLLM이 MapBiomas 질문에 생성형 답변을 합니까?**

현재 `answer=null`인 로컬 근거 검색이다. 원문 발췌문과 출처 링크를 제공한다.

**Q. 44·25·5는 무엇입니까?**

공식 원문에서 구조화한 용어 44개, 참조 지도 항목 25개, 특화 분류에 연결할 범례 코드 5개다.

**Q. 검색 결과가 바뀐 원문을 가리킬 수 있습니까?**

검색 전에 로컬 원문의 byte와 SHA를 index pin과 대조한다. 값이 달라지면 해당 문서의 인용을 반환하지 않는다.

**Q. 모든 인포그래픽 내용을 확보했습니까?**

R11은 목록 HTML을 보존했다. 동적 인포그래픽 내용과 OCR 해석은 `BLOCKED`다.

**Q. 이 검색이 MapBiomas 통계의 독립 정확도를 증명합니까?**

검색은 방법론·범례·출처를 찾는 기능이다. 지도나 모델의 독립 정확도는 독립 표본 평가에서 별도로 산출한다.
