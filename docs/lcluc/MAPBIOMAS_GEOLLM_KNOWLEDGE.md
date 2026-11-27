# GeoLLM MapBiomas Indonesia 공식 지식자료

GeoLLM Assistant의 **MapBiomas Indonesia 지식 검색**에서 한국어 교차 용어, 영어, 인도네시아어로 근거를 찾는다. 검색 결과는 고정 원문 SHA-256, 자료명, 발행 컬렉션, PDF 페이지 또는 HTML 추출 위치와 공식 링크를 표시한다. 일반 GeoLLM 업무와 별도 컬렉션 범위를 지정하는 검색이며, 원문 조회와 생성형 답변은 구분된다.

| 우선순위 | 수록 자산 |
| --- | --- |
| P0 | R01–R02 ATBD Collection 4.1 영어·인도네시아어, R03 Legend Description 4.1, R04 Legend Code, R05 Glossary, R06 Accuracy Assessment 설명, R07 Reference Maps, R08 Terms of Use, R09 Fact Sheet 4.1 |
| P1 | R10 FAQ, R11 인포그래픽 목록 HTML, R12 고정 GitHub Gap Fill 스크립트, R13 ATBD 3.0 비교본, R14 GEE 접근 안내 |

R04는 공식 4.1 메뉴가 연결하는 Collection 4 표이므로 파일 자체 버전을 기록한다. R06의 공식 웹 설명은 Collection 2.0을 다루며, Collection 4.1의 검증 방법은 R01/R02에서 확인한다. R07은 기관·레이어·연도의 공식 목록이다. R11 이미지 내부의 OCR과 R06 동적 통계 위젯은 현재 인덱스 범위 밖이다. [공식 범례](https://landy.mapbiomas.id/en/legendcode) · [공식 정확도 설명](https://landy.mapbiomas.id/en/accuracy-assessment) · [공식 Reference Maps](https://landy.mapbiomas.id/en/refmap)

원본은 `data/raw/knowledge/mapbiomas-indonesia/` 아래 파일 SHA를 이름에 포함해 보관한다. 정규화한 텍스트와 페이지별 청크, 용어 정의·참조지도 기관/연도·특화 범례 코드·색상 구조화 기록은 `data/curated/knowledge/mapbiomas-indonesia/index.json`에 있다. `python -m pip install -e '.[lcluc-knowledge]'` 뒤 `python -m services.rag.mapbiomas`로 생성한다. 로컬 검색은 문서 어휘와 교차언어 용어 대응을 사용하며 pgvector 임베딩과 생성형 응답은 이 경로의 평가 범위 밖이다. R08의 출처 표시 조건을 보존한다. [공식 이용조건](https://landy.mapbiomas.id/en/termsofuse)

2026-11-26 취득본은 14개 원문(P0 9개)과 PDF·웹 텍스트 청크 286개를 보존한다. 용어 44개, 참조 지도 25개, 5개 특화 범례 코드를 구조화했다. [취득 로그](../../artifacts/lcluc/mapbiomas-knowledge.log)

실제 Edge의 GeoLLM Assistant에서 `맹그로브 범례`, `참조 지도 oil palm concession`, `glossary mosaic`를 검색해 각각 공식 PDF 또는 웹 원문 링크를 확인했다. 문서명보다 검색어의 본문 근거를 우선하도록 조정한 뒤에도 클릭 시험을 통과했다. 인도네시아어 `tambak mangrove` API 검색도 성공했다. [Edge 검색 기록](../../artifacts/lcluc/banten-models-knowledge-final-edge.log)

- `GET /api/rag/mapbiomas/catalog`은 문서별 출처·버전·원본 해시와 구조화 레코드 수를 준다.
- 기존 GeoLLM 화면은 `POST /api/rag/mapbiomas/search`에 `question`을 보낸다. 새 Evidence API의 `POST /api/rag/search`에서도 `scope: "mapbiomas-indonesia"`를 선택할 수 있다. 두 경로 모두 원본 해시를 확인한 짧은 근거와 공식 링크를 반환한다.

## LANDY 자료 수집 현황

| 유형 | 확보·연결 범위 | 추가 확보 또는 확인 범위 |
| --- | --- | --- |
| 문서형 지식자료 | R01~R14 원본과 286개 청크. GeoLLM에서 원문과 인용을 검색한다. | 인포그래픽 이미지 자체와 OCR, 정확도 사이트의 동적 위젯 수치, Reference Maps에 열거한 원본 지도는 별도다. |
| 정량 통계자료 | Collection 4.1 공식 XLSX에 `COVERAGE` 면적과 `TRANSITION` 전이 원본이 있다. 반텐주 1990~2024·11개 클래스 면적을 LCLUC에 연결했다. GeoLLM은 반텐주 전이 레코드 113행과 발행 기간을 정형 GIS 도구로 조회한다. | 4.1 정확도 통계와 픽셀 원본 확보가 남았다. |
| 공간 분석자료 | Collection 4.1 지도, Landsat 모자이크, 전이 제품의 공식 안내 경로를 확보했다. | 반텐 4.1 연차 분류 GeoTIFF·전이 래스터·모자이크는 로컬 미확보다. 확인한 직접 GeoTIFF 링크는 3.0/2.0이며, 4.1 픽셀은 GEE 자산을 통해 필요한 영역을 확보한다. |

XLSX 원본은 `data/raw/explorer/banten/mapbiomas/4.1/statistics_lulc_indonesia.xlsx`, 반텐 추이와 전이는 `data/curated/explorer/banten-province/mapbiomas-4.1-trend.json`과 `mapbiomas-4.1-transitions.json`에 보존한다. 정량 질의 API와 브라우저 확인은 [GeoLLM 질의 계약](GEOLLM_QUERY.md)에 있다. [공식 통계](https://landy.mapbiomas.id/en/statistics) · [지도 다운로드 안내](https://landy.mapbiomas.id/en/collectionmap) · [GEE 접근 조건](https://landy.mapbiomas.id/en/gee) · [반텐 집계와 비교 기준](BANTEN_MAPBIOMAS_AREA_COMPARISON.md)
