# LCLUC 후처리 및 품질관리 이해자료

- updated_at: 2026-11-26 KST
- source_commit: `UNCOMMITTED_WORKTREE`
- evidence_paths:
  - `docs/lcluc/POSTPROCESS_QUALITY.md`
  - `services/lcluc/postprocess.py`
  - `services/api/lcluc_postprocess.py`
  - `frontend/src/LclucPostprocess.tsx`
  - `tests/lcluc/test_postprocess.py`
  - `artifacts/lcluc/lcluc-postprocess-edge.log`
  - `data/curated/lcluc/postprocess/e8f1b2a963eeb08be8806f802612bb402edb0e3efd870e42c00be3aef21ad4a4/report.json`
- overall_status: `VERIFIED_REAL`

## 1. 쉬운 설명

### 한 문장으로

LCLUC 후처리 및 품질관리 화면은 고정된 반텐 2020 Landsat RF 후보에서 작은 고립 패치를 공간 필터로 보정하고, 전후 지도·면적·약한 참조 일치도·보정 위치·SHA 고정 파일을 한 실행 이력으로 검토하는 Toolbox다.

### 실제 확인 결과

- `VERIFIED_REAL`: 최소 4픽셀·4방향 연결로 실행 ID `e8f1b2…ad4a4`를 생성했다.
- `VERIFIED_REAL`: 147m 표시 격자에서 61,274픽셀, 129,889.72ha가 보정 후보로 바뀌었다.
- `VERIFIED_REAL`: 같은 공간 홀드아웃 72,391픽셀에서 Esri v003 약한 참조 일치도가 71.42%에서 75.36%로 바뀌었다.
- `VERIFIED_REAL`: Edge에서 전후 Swipe, 보정 위치, 클래스 면적, 품질 비교, 실행 이력, 원본·보정본·보정 mask GeoTIFF 3개 다운로드와 SHA, 새로고침 재조회, 기존 Workspace 바로가기를 확인했다.
- `TESTED_SYNTHETIC`: NoData와 보호 클래스 유지, 4방향·8방향 연결 차이를 2개 단위시험으로 확인했다.
- `BLOCKED`: 독립 정확도 상태는 `REFERENCE_REQUIRED`다. 운영 분류 보정 시험과 과학·공개 승인은 대기한다.
- `PLANNED`: Temporal Filter, Gap Fill, Frequency Filter, Incident Filter.
- `TESTED_SYNTHETIC`: Hierarchical Integration은 동년·동일 격자·우선순위·NoData 보호 계약과 파일 기반 11픽셀 통합을 확인했다. 실제 승인 특화층 접수는 `BLOCKED`다.

이 결과는 운영 지도 교체가 아니라 `REVIEW_CANDIDATE`다. 약한 참조 일치도 상승은 보조 지도와의 일치 변화이며 독립 정확도는 미측정이다.

## 2. 이론적 배경

### 2.1 공간 필터

분류 영상에는 주변 다수 클래스와 다른 작은 고립 패치가 생길 수 있다. 공간 sieve는 같은 값을 가진 연결 성분의 크기를 세고 최소 픽셀보다 작은 성분을 주변 분류로 보정한다.

- 4방향은 상·하·좌·우 연결을 사용한다.
- 8방향은 대각선까지 연결로 인정한다.
- 최소 연결 픽셀은 2~30 범위에서 선택한다.
- 수역 code 1, 침수 식생 code 4, 구름 code 10과 NoData는 보호한다.

이번 실자료 시험은 최소 4픽셀·4방향이다. 픽셀 크기는 약 147m이므로 운영용 최소 면적 규칙과 같은 의미로 확정하지 않는다.

### 2.2 전후 면적

클래스 면적은 Web Mercator 픽셀 수에 고정 면적을 곱하지 않는다. 각 행의 셀 모서리를 WGS84 타원체로 변환하고 geodesic 면적을 합산한다. `changed_ha`는 후처리로 값이 바뀐 위치의 면적이며 실제 연차 토지피복 변화면적과 역할이 다르다.

### 2.3 같은 표본의 전후 비교

후처리 효과는 원본 RF 평가에 사용한 72,391픽셀 공간 홀드아웃을 그대로 사용한다. 원본 혼동행렬이 고정 RF 보고서와 일치할 때만 전후 값을 기록한다. 이 계약은 평가 표본이 바뀌어 생기는 비교 착시를 막는다.

Esri / Impact Observatory v003은 동년 약한 참조다. 전 71.4205%, 후 75.3574%는 Esri 지도와의 일치도다. 독립 현장·전문가 표본 평가는 `REFERENCE_REQUIRED`다.

### 2.4 MapBiomas 기술 검토와 SDSS 구현 차이

MapBiomas Indonesia Collection 4.1 ATBD는 Gap Fill, Spatial, Temporal, Frequency, Incident와 계층 통합 개념을 설명한다. 공개 Landy 저장소의 고정 commit `a957d72992d90ed5a4787ce13c8a36b7a1b48780`에서는 Gap Fill과 Temporal 스크립트를 확인했고 `Saptial Filter.js`는 내용이 비어 있다.

SDSS Spatial Filter는 공식 코드 복제가 아니라 Rasterio/GDAL 연결 성분 sieve를 Esri v003 분류체계와 고정 RF 격자에 적용한 자체 시험 구현이다. MapBiomas ATBD는 검토 근거이며 동일 구현·동일 운영 규칙을 의미하지 않는다.

## 3. 코드·데이터 동작

### 3.1 입력과 실행 ID

입력은 `banten-landsat-rf-2020` 후보와 고정 `rf-report.json`이다. 실행 계약은 다음 세 요소를 정규화해 SHA-256 실행 ID를 만든다.

1. 원본 RF 보고서 SHA-256
2. 알고리즘 `spatial-sieve/1`
3. 최소 픽셀·연결 방향·보호 클래스 파라미터

같은 입력과 파라미터를 다시 제출하면 기존 실행 폴더와 보고서를 재사용한다.

### 3.2 처리 순서

1. 원분류 TIFF와 Esri 참조 TIFF의 byte·SHA를 검증한다.
2. 원분류 taxonomy·CRS·격자·NoData 계약을 검사한다.
3. Esri 참조를 최근접 방식으로 원분류 격자에 맞춘다.
4. 공간 sieve를 실행하고 보호 클래스·NoData를 유지한다.
5. WGS84 타원체 셀 면적으로 클래스별 전후 면적과 보정 면적을 계산한다.
6. 동일 72,391픽셀의 전후 약한 참조 지표를 계산한다.
7. PNG 3개와 GeoTIFF 2개, 보고서 JSON을 실행 ID 폴더에 고정한다. 원본 GeoTIFF는 기존 pin을 그대로 제공한다.

### 3.3 산출물

| 산출물 | 역할 |
|---|---|
| `before.png` | 후처리 전 분류 화면 |
| `after.png` | 후처리 후 분류 화면 |
| `corrections.png` | 실제 보정 위치 overlay |
| `original.tif` | 기존 원분류 pin 다운로드 |
| `processed.tif` | 보정 분류 GeoTIFF |
| `corrections.tif` | 0 유지, 1 보정, 255 NoData mask |
| `report.json` | 파라미터·면적·전후 지표·파일 SHA·이력 |

### 3.4 API와 UI

| API | 기능 |
|---|---|
| `GET /api/lcluc/postprocess` | 등록 후보와 최근 실행 이력 최대 30건 |
| `POST /api/lcluc/postprocess/runs` | 후보·최소 픽셀·연결 방향으로 동기 시험 실행 |
| `GET /runs/{id}` | 전후 지표·면적·파라미터·파일 pin 조회 |
| `GET /runs/{id}/assets/{file}` | PNG·GeoTIFF를 SHA 검증 후 제공 |

UI는 GeoAI Toolbox의 `후처리 및 품질관리`와 기존 LCLUC Workspace 바로가기에서 연다. Spatial Filter는 실행 form을 제공하고 계획 도구는 필요한 입력 조건을 설명한다. 완료 실행은 Swipe, 보정 위치 checkbox, 면적표, 품질 비교, 이력 선택, 파일 다운로드로 검토한다.

## 4. 시험 증거와 상태

| 항목 | 상태 | 증거와 범위 |
|---|---|---|
| 공간 필터 실제 실행 | `VERIFIED_REAL` | 실행 `e8f1b2…ad4a4`, 4픽셀·4방향, 61,274픽셀·129,889.72ha |
| 전후 약한 참조 비교 | `VERIFIED_REAL` | 동일 72,391표본, Esri v003 71.4205%→75.3574% |
| Edge 검토 흐름 | `VERIFIED_REAL` | 메뉴·실행·Swipe·보정 위치·면적·품질·이력·재조회·Workspace 바로가기 |
| GeoTIFF 다운로드 | `VERIFIED_REAL` | 원본·processed·corrections 3개와 SHA-256 확인 |
| 공간 필터 계약시험 | `TESTED_SYNTHETIC` | NoData·보호 클래스, 4방향·8방향 연결 차이 2건 |
| 운영 최소 면적 규칙 | `BLOCKED` | 약 147m 표시 격자 시험, 운영 분류 격자·클래스별 기준 검토 필요 |
| 독립 정확도 | `BLOCKED` | `REFERENCE_REQUIRED`, 독립 표본·전후 정확도·변화 보존 평가 필요 |
| Temporal Filter | `PLANNED` | 연속 3개년 이상 동일 격자·분류체계 필요 |
| Gap Fill | `PLANNED` | 관측 결측·영역 외부 구분과 보완 출처 연도 기록 필요 |
| Frequency·Incident Filter | `PLANNED` | 장기 유효 관측과 클래스별 기준 필요 |
| Hierarchical Integration 계약 | `TESTED_SYNTHETIC` | 우선순위·충돌·타년 거부·NoData 보호, 같은 격자 GeoTIFF 11픽셀 통합·원본 SHA 유지 |
| Hierarchical Integration 실자료 | `BLOCKED` | 승인 동년 특화 layer·GEE 권한·운영 승인 필요 |

## 5. 발표 스크립트

### 1분

“후처리 및 품질관리 Toolbox는 고정된 반텐 2020 Landsat RF 후보의 작은 고립 패치를 공간 필터로 보정하고 전후를 같은 근거로 비교합니다. 최소 4픽셀·4방향 실자료 실행에서 61,274픽셀, 129,889.72헥타르가 바뀌었습니다. 동일 공간 홀드아웃 72,391픽셀에서 Esri v003 약한 참조 일치도는 71.42%에서 75.36%로 변했습니다. Edge에서 전후 Swipe, 보정 위치·면적·품질·이력, 세 GeoTIFF의 SHA 다운로드와 재조회를 확인했습니다. 이 값은 약한 참조 일치도이고 독립 정확도는 `REFERENCE_REQUIRED`입니다. Temporal·Gap·Frequency·Incident는 계획 단계이며 계층 통합 계약은 합성 시험을 통과했습니다.”

### 5분 핵심 순서

1. 고정 RF 보고서 SHA, 알고리즘, 파라미터로 결정적 실행 ID를 만든다.
2. taxonomy·격자·NoData와 원본·참조 SHA를 먼저 검사한다.
3. 최소 연결 크기보다 작은 공간 패치를 sieve로 보정한다.
4. 수역·침수 식생·구름·NoData를 보호한다.
5. 타원체 셀 면적으로 보정 위치와 클래스별 전후 면적을 계산한다.
6. 원본 RF와 같은 72,391픽셀로 전후 약한 참조 지표를 비교한다.
7. 71.42%→75.36%는 Esri v003 일치도이며 독립 정확도는 미측정이다.
8. 원본·보정본·보정 mask와 실행 JSON을 SHA로 고정한다.
9. 현재 결과는 `REVIEW_CANDIDATE`이고 운영 최소 면적·독립 평가·승인을 기다린다.

## 6. Q&A

**Q. 약한 참조 일치도 75.36%가 독립 정확도입니까?**

동일 72,391픽셀에서 후처리 결과와 Esri v003을 비교한 값이다. 독립 정확도 상태는 `REFERENCE_REQUIRED`다.

**Q. 129,889.72ha는 실제 토지피복 변화면적입니까?**

공간 필터가 2020 후보 분류 값을 바꾼 위치의 셀 면적 합계다. 서로 다른 연도의 토지피복 변화면적은 연차 변화 분석에서 계산한다.

**Q. 어떤 클래스가 보호됩니까?**

현재 실행 계약은 수역 code 1, 침수 식생 code 4, 구름 code 10과 NoData를 보호한다.

**Q. 4방향과 8방향은 무엇이 다릅니까?**

4방향은 상·하·좌·우, 8방향은 대각선까지 같은 패치의 연결로 인정한다. 대각선 두 픽셀 유지 차이는 합성시험으로 확인했다.

**Q. MapBiomas 공식 Spatial Filter를 그대로 실행합니까?**

MapBiomas ATBD의 후처리 개념과 공개 Gap Fill·Temporal 코드를 검토했다. 고정 공개 저장소의 `Saptial Filter.js`는 내용이 비어 있어 SDSS는 Rasterio/GDAL sieve 기반 자체 시험 구현을 사용한다.

**Q. Temporal Filter와 Gap Fill을 지금 실행할 수 있습니까?**

UI는 계획 상태와 필요한 입력 조건을 보여 준다. Temporal·Gap·Frequency·Incident는 `PLANNED`다. Hierarchical Integration은 합성 계약시험을 통과했고 실제 승인 동년 특화층은 `BLOCKED`다.

**Q. 같은 파라미터로 다시 실행하면 어떻게 됩니까?**

원본 보고서 SHA·알고리즘·파라미터가 같으면 같은 실행 ID를 사용하고 기존 보고서를 재조회한다.
