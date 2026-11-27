# 다음 작업 · GeoLLM 토지피복 질의응답

작업 위치는 `E:/SDSS-Platform2`, GitHub 브랜치는 `codex/next-gates-onemap-climate-klhk`입니다. 다음 접속에서 이 문서와 `CONTINUOUS_DEVELOPMENT.md`를 먼저 읽고 기존 React의 **GeoLLM Assistant**부터 확인합니다.

2026-11-27에 아래 첫 구현 단위의 반텐 면적·산림 총전환·순변화·전이와 브라우저 확인을 완료했다. 최신 사용법과 검증 수치는 [현행 질의 계약](GEOLLM_QUERY.md)에 있다. 원본 수집과 공간 중첩은 접수 상태에 따라 이어간다.

## 확인된 출발점

| 항목 | 상태와 확인 방법 |
| --- | --- |
| 문서형 지식 | `VERIFIED_REAL`. 공식 LANDY 원문 14건, P0 9건, 청크 286개를 확보했다. ATBD·Glossary·Legend·Fact Sheet·정책/출처를 `GET /api/rag/mapbiomas/catalog`과 `POST /api/rag/mapbiomas/search`에서 확인한다. 기존 화면은 `frontend/src/MapbiomasKnowledge.tsx`다. 현행 검색은 로컬 색인이다. |
| 정량 통계 | `VERIFIED_REAL`. Collection 4.1 공식 XLSX를 보존했다. `COVERAGE`의 반텐 1990~2024년 11개 분류가 `/api/lcluc/banten-sentinel-explorer/historical-trend`에 연결되어 있다. `TRANSITION`에서 `Indonesia / Jawa / Banten` 113행과 2023→2024 등 전이 구간을 원본에서 확인했다. 반텐 전이 정제·조회·UI는 작업 대기다. |
| 공간 참조 | `VERIFIED_REAL`. One Map/BIG 기존 프로젝트 경계와 LANDY Reference Maps 출처 목록을 보유한다. LANDY의 버전과 기존 경계 스냅샷 날짜를 각각 기록한다. `BLOCKED` 반텐 MapBiomas 4.1 분류·전이 GeoTIFF 및 공식 Kemenhut 동년 Penutupan Lahan 원본은 아직 접수되지 않았다. |
| 반텐 면적 표시 | `VERIFIED_REAL`. 연차 화면이 Esri 원본 9행과 MapBiomas 발행 11행을 구분한다. Esri 2024년 TIFF와 MapBiomas XLSX를 재검산했고, Edge에서 연도 선택과 API 응답을 확인했다. |

[LANDY 보유 현황](MAPBIOMAS_GEOLLM_KNOWLEDGE.md) · [반텐 집계 및 공식 참조 기준](BANTEN_MAPBIOMAS_AREA_COMPARISON.md) · [공식 Reference Maps](https://landy.mapbiomas.id/en/refmap)

## 다음 접속의 첫 구현 단위

1. 기존 GeoLLM 화면과 API에서 한국어·인도네시아어·영어 대표 질의를 확인한다. 기존 기후 수치 라우터와 정형 `/api/geo-query`는 호출 계약을 유지한다. 토지피복 질의는 **의도·지역·기간·클래스·제품**을 구조화한다. 복수 후보, 필수 값 누락 또는 미지원 범위는 필요한 입력을 명시한다.
2. 정의·분류 기준·방법론·정책 질의는 육안 검토 가능한 문서 근거와 함께 RAG로 제공한다. 면적·산림감소·전이·중첩 질의는 검증된 GIS 도구 결과로만 답한다. 문서와 수치를 함께 묻는 질의는 둘의 근거를 구분한다. 수치 소스가 없거나 무결성 검사에 실패하면 출처가 확인될 때까지 수치를 보류한다.
3. 먼저 반텐에 결과가 있는 도구를 연결한다. 면적은 MapBiomas `COVERAGE`와 Esri의 검증된 등적 격자 결과를 사용한다. 전이는 `TRANSITION`의 같은 기간 열을 해당 출발·도착 코드로 해석하고, 공란·미지원 기간을 0으로 채우지 않는다. 여러 연차를 더해 장기 전이를 만들지 않는다. 산림감소는 산림→비산림의 총전환과 산림 면적 순감소를 구분한다. Esri 수목 클래스와 Kemenhut의 산림 정의를 서로 바꾸어 쓰지 않는다.
4. 같은 응답에 숫자·단위, 지역·기간·제품 버전, 출처와 SHA, 분석 범위·제약, 제공 가능한 지도 레이어와 기존 Result ID를 넣는다. 조회 결과로부터 새 공식 등급·승인을 추정하지 않는다. PostGIS·Parquet·COG는 각 제품 자산의 성격에 맞는 읽기 도구로 사용하고, 확보되지 않은 레이어 링크나 결과 ID는 생성하지 않는다.
5. 첨부의 행정경계, IKN, Forest Estate, Watershed, Peat Swamp Area, Forest Moratorium, Indigenous Forest, Social Forestry, Forestry·Mining·Oil Palm Concession, National Park·KBA, 네 종의 서식지, Restoration Area를 기관별 출처로 확인한다. 우선 보유한 행정경계를 등록하고, 반텐에 해당하는 공간 원본 중 접근·이용 조건이 확인된 자료부터 요청·수신 영수증·버전·취득시각·SHA와 같이 보존한다. 참조 목록의 등재, 원본 다운로드, 공간연산 사용, 공개 승인은 각각 기록한다. IKN은 자체 경계를 사용한다.

## 첫 검증 질의

| 질의 | 기대 결과 |
| --- | --- |
| `MapBiomas ATBD의 Gap Fill 방법은?` | 공식 문서 근거와 인용 |
| `Berapa luas sawah di Banten pada 2024 menurut MapBiomas?` | MapBiomas 4.1 발행 반텐 면적과 ha, 원본 근거 |
| `Show MapBiomas forest-to-cropland transitions in Banten from 2023 to 2024` | 고정된 코드·기간으로 전이 시트 조회. 해석이 불명확한 클래스는 확인 |
| `반텐의 산림부 2024 공식 산림감소량은?` | 해당 공식 원본·기간이 없으면 대기와 원인 표시 |
| `Overlap oil palm concession with Banten forest loss` | 기간·제품·해당 레이어의 이용·공간 정합 여부를 확인. 미확보 레이어는 대기 |

## 로컬 재접속

8014 API와 5175 React가 이미 실행 중이면 그 프로세스를 사용한다. 중지된 경우 저장소 루트와 `frontend`의 별도 터미널에서 각각 실행한다.

```powershell
# 저장소 루트
py -3.11 -m uvicorn services.api.app:app --host 127.0.0.1 --port 8014
```

```powershell
# frontend
$env:VITE_OPERATIONS_PROXY_TARGET = 'http://127.0.0.1:8014'
npm run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

React 메뉴 **GeoLLM Assistant**에서 문서 질문을 입력하거나 `GET http://127.0.0.1:5175/api/rag/mapbiomas/catalog`로 카탈로그를 확인한다. 수정 후 프런트 빌드와 백엔드 계약 시험을 실행하고 실제 브라우저에서 문서, 정량, 미확보 세 흐름을 확인한다. 원본·모델·다운로드 파일·인증정보는 프로젝트 Data Lake에 보존한다. 새 체크아웃에서는 기존 Data Lake가 연결돼 있어야 실자료가 조회된다.
