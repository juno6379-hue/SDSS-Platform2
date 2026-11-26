# LCLUC 후처리 및 품질관리

GeoAI Toolbox의 **후처리 및 품질관리** 또는 LCLUC 워크스페이스 제목 옆의 바로가기로 연다. 이 화면은 분류 후보의 보정 결과를 검토하는 작업 공간이다. 기존 영상 품질검사와 학습·승인, 토지피복 분석은 [연차 처리 경로](ANNUAL_INTAKE.md)를 사용한다.

## MapBiomas 기술 검토

Collection 4.1 ATBD 3.4.6~3.4.7장은 결측 보완, 공간·시간·빈도·반복 전환 필터를 설명한다. Collection 4.0 결과를 개선하는 절에는 3·4·5년 시간 창, 수역·양식장 예외, 최소 전이 면적, GEDI 수관 높이 기반 정정, 조림지 안정화가 포함된다. 4장은 기본 분류와 주제별 분류의 픽셀 단위 우선순위를, 5장은 기존 지도와의 일치도 및 독립 표본 검증을 각각 설명한다. [Collection 4.1 ATBD](https://landy.mapbiomas.id/assets/files/ATBD%20Mapbiomas%20ID%20Col%204.1%20EN.pdf)

공개 Landy 저장소의 고정 커밋 `a957d72992d90ed5a4787ce13c8a36b7a1b48780`에서 `4.0/4.1 Filtering`의 Gap Fill과 Temporal 스크립트를 확인했다. Gap Fill 스크립트는 순방향 보완 뒤 남은 공백을 역방향으로 처리하며 참조 연도를 별도로 계산한다. 같은 커밋에는 내용이 비어 있는 `Saptial Filter.js`가 있다. SDSS 공간 필터는 자체 분류체계와 격자에 GDAL 연결 패치 방식을 적용한다. [공개 Gap Fill 코드](https://github.com/mapbiomas-indonesia/MapBiomas-Indonesia---Landy/blob/a957d72992d90ed5a4787ce13c8a36b7a1b48780/4.0/4.1%20Filtering/Gap%20filled%20filter.js) · [Temporal 코드](https://github.com/mapbiomas-indonesia/MapBiomas-Indonesia---Landy/blob/a957d72992d90ed5a4787ce13c8a36b7a1b48780/4.0/4.1%20Filtering/Temporal%20t1.js) · [공간 필터 파일](https://github.com/mapbiomas-indonesia/MapBiomas-Indonesia---Landy/blob/a957d72992d90ed5a4787ce13c8a36b7a1b48780/4.0/4.1%20Filtering/Saptial%20Filter.js)

| Toolbox 도구 | SDSS 적용 상태와 기준 |
| --- | --- |
| Spatial Filter | 반텐 2020 Landsat·Sentinel-2의 RF, Tiny U-Net, DeepLabv3+ 후보를 지원한다. 최소 2~30 연결 픽셀과 4·8방향을 선택한다. 수역·침수 식생·구름과 NoData를 보호한다. 현재 출력은 약 147m 표시 격자이며 국토 운영용 최소 면적 규칙은 별도 검증 대상이다. |
| Temporal Filter | `PLANNED`. 연속 3개년 이상 동일 격자·분류체계의 모델 분류에서 이웃 연도가 같은 단기 반전 후보를 검출한다. 고신뢰 산림 전환과 수역·양식장 급변은 별도 규칙으로 처리한다. |
| Gap Fill | `PLANNED`. 관측 결측과 영역 외부 값을 구분한다. 보완 출처 연도, 연도 차이, 보완 마스크를 저장하고 실측 기준 변화량은 동년 유효 관측으로 계산한다. |
| Frequency Filter | `PLANNED`. 클래스 출현 빈도를 유효 관측 연도 수로 계산한다. 희소 클래스와 최근 등장 클래스는 먼저 검토 대상으로 표시한다. |
| Incident Filter | `PLANNED`. 유효한 연속 연도 간 반복 전환 수와 공간적 연결을 함께 보고 경계부 후보를 표시한다. 장기 관측과 클래스별 기준이 필요하다. |
| Hierarchical Integration | `BLOCKED`. 동년 라벨·레이어의 입력 계약과 계층 마스크 통합은 구현했다. 승인된 동일연도 특화 레이어를 등록하면 우선순위와 경합 픽셀을 기록한다. [동년 특화 분류 접수](BANTEN_MODEL_TRIALS.md) |

## 메뉴와 결과

- 입력은 2020년 반텐 센서별 등록 원분류 후보다. 동일 투영·격자의 원분류와 보정본을 Swipe로 비교하고, 붉은 마스크로 실제 값이 바뀐 위치를 표시한다. 비교용 PNG 외에 파일 다운로드용 좌표가 있는 GeoTIFF를 보관한다.
- 클래스별 전·후 면적과 순증감은 WGS84 타원체 셀 면적을 합산한다. `corrections.tif` 값은 0 유지, 1 보정, 255 NoData다. 보정 위치 면적은 토지피복의 연차 변화 면적과 다른 지표다.
- 전·후 비교는 후보 센서에서 동일한 공간 홀드아웃과 동년 Esri v003 약한 참조를 사용한다. Landsat은 72,391픽셀, Sentinel-2는 76,230픽셀이다. 원본 혼동행렬이 등록된 증거와 일치해야 후처리 평가를 기록한다. 독립 정확도는 `REFERENCE_REQUIRED`로 표시한다. 운영 발행 전에는 같은 독립 표본의 전·후 정확도와 실제 변화 보존 여부를 평가하고 과학 검토와 공개 승인을 기록해야 한다.
- 실행은 알고리즘 버전, 파라미터, 원분류 근거 SHA-256으로 식별한다. 같은 입력·파라미터를 다시 제출하면 기존 이력을 재사용한다. 원본은 원래의 해시를 유지하고 보정·품질 파일은 별도 실행 폴더에 저장한다.

| 로컬 API | 기능 |
| --- | --- |
| `GET /api/lcluc/postprocess` | 실제 등록 입력과 완료된 최근 이력 |
| `POST /api/lcluc/postprocess/runs` | `candidate`, `minimum_pixels`, `connectivity`가 담긴 동기 시험 실행 |
| `GET /api/lcluc/postprocess/runs/{id}` | 전·후 지표, 변경 면적, 파일 해시, 파라미터와 평가 근거 |
| `GET /api/lcluc/postprocess/runs/{id}/assets/{file}` | 전·후·보정 PNG와 원본·보정본·보정 마스크 GeoTIFF. 다운로드 SHA-256 확인 |

완료 자료는 `data/curated/lcluc/postprocess/{id}/`에 저장한다. 입력 또는 해시가 준비되지 않으면 API는 409를 반환한다. 실자료 화면 시험 증거는 [Edge 실행 로그](../../artifacts/lcluc/lcluc-postprocess-edge.log), NoData·보호 클래스·연결 방향 시험은 [Python 테스트](../../tests/lcluc/test_postprocess.py)에 있다.

Edge 시험 `e8f1b2a963eeb08be8806f802612bb402edb0e3efd870e42c00be3aef21ad4a4`는 최소 4픽셀·4방향에서 61,274픽셀과 129,889.72ha의 분류 코드가 바뀌었다. 같은 공간 홀드아웃의 약한 참조 일치도는 71.42%에서 75.36%였다. 전·후 면적 합계 보존, 지도 Swipe와 보정 위치, 실행 이력 재조회, GeoTIFF 3개의 SHA-256을 확인했다. [실행 화면](../../artifacts/lcluc/lcluc-postprocess-browser.png)
