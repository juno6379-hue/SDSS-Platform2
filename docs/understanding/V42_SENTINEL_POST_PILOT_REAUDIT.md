# v4.2 Sentinel pilot 반영 36셀 재감사

- updated_at: 2026-11-25 KST
- 재감사 산출물: `VERIFIED_REAL`
- API/UI 반영: `VERIFIED_REAL` — 로컬 8011과 Edge 158에서 조회 및 상세 펼치기 검증
- 전체 수집·학습 상태: `BLOCKED`

## 1. 쉬운 설명

East Java 2023 단일 pilot의 실제 footprint를 기존 36개 주·연도 셀에 넣고 공간피복을 다시 계산했다. 저장된 실제 geometry를 사용해 36셀과 72개 exact missing feature를 재산출했으며, 이 과정에서 collector를 시작하거나 원격 자료를 더 받거나 원장을 쓰지 않았다.

- pilot로 늘어난 simultaneous-present 면적: **6,556,514.480755895m²**
- pilot로 늘어난 clear 면적: **6,556,514.480755895m²**
- 새 simultaneous-present 피복률: **0.9773249834093871%**
- 새 clear 피복률: **0.890386955270514%**
- exact missing queue: **72개 feature**
- 재감사 중 collector·원격 다운로드·원장 쓰기: **모두 0**

이전 0.976741%와 0.889803%는 pilot 전 snapshot으로 역사적 기록에 남긴다. 현재 재감사 수치는 각각 약 0.000584%p 증가했지만, 여전히 전체 면적의 약 99%가 비어 있고 `full_spatial_coverage=false`, `learning_ready=false`다.

다음 후보 6개에 pilot에서 관측한 7,471,506B짜리 창을 하나씩 적용하면 단순 합은 **44,829,036B**다. 이는 “pilot과 같은 창 6개”의 참고값일 뿐 전체 gap 전송량, 비용 견적, 실행 승인, 예산 충분성을 뜻하지 않는다.

## 2. 이론적 배경

### 2.1 Exact geometry 재감사

패치 수나 bbox만 더하는 대신, 기존 present/clear WKB와 pilot의 native raster footprint를 같은 면적 좌표계에서 합집합한다. 이미 피복된 부분과 겹치면 중복 면적을 더하지 않기 때문에 실제 증가분을 계산할 수 있다.

### 2.2 Snapshot과 현재값

감사 지표에는 기준 시점과 source pin이 필요하다. pilot 전 값과 pilot 반영 후 값은 모두 실제 증거지만 서로 다른 snapshot이다. 따라서 과거 보고서를 고쳐 쓰지 않고 다음처럼 구분한다.

- pilot 전 held-audit: present 0.9767414314207837%, clear 0.8898034032819104%
- pilot 반영 재감사: present 0.9773249834093871%, clear 0.890386955270514%

### 2.3 한 창 추정과 전체 견적

`7,471,506B × 6 = 44,829,036B`는 실제 한 pilot 창의 관측량을 6개 우선순위에 단순 적용한 값이다. 전체 gap에는 필요한 창 수, scene 가용성, COG block 배치, 중복·구름·재시도 비용이 미정이므로 `full_gap_transfer_estimate_bytes=null`이다.

## 3. 코드·데이터 동작

`services/datahub/sentinel/reaudit.py`는 다음 순서로 fail-closed 재감사를 수행한다.

1. pilot result·observation·receipt·sealed plan·ledger SHA를 교차 검증한다.
2. 6 band와 native SCL 파일의 SHA와 경로 containment를 확인한다.
3. 기존 36셀 checkpoint와 WKB geometry가 baseline source pin과 일치하는지 확인한다.
4. East Java 2023의 pilot footprint를 기존 present/clear geometry와 합집합한다.
5. 36셀 면적과 72개 exact missing geometry를 다시 계산한다.
6. 주별 최대 missing area 셀을 6개 추천 창으로 정렬하되 `executable=false`로 둔다.
7. 새로운 collector, remote download, ledger write 없이 JSON과 queue를 고정한다.

`services/api/app.py`와 `web/index.html`, `web/app.js`는 새 재감사 지표·pilot delta·36셀 상세·추천 창을 읽기 전용으로 표시한다. 8011의 /api/sentinel HTTP 200과 Edge 158의 실제 조회·상세 펼치기에서 36행, 6후보, 42.75MiB, 페이지 오류 0을 확인했다.

## 4. 테스트·증거

| 항목 | 결과 | 상태 |
|---|---|---|
| 36셀 actual geometry 재산출 | 36/36 | `VERIFIED_REAL` |
| exact missing queue | 72 features, 116,206,625B | `VERIFIED_REAL` |
| East Java 2023 delta | present·clear 각각 +6,556,514.480755895m² | `VERIFIED_REAL` |
| 새 전체 피복률 | present 0.9773249834093871%, clear 0.890386955270514% | `VERIFIED_REAL` |
| 재감사 외부 부작용 | collector 0, remote download 0, ledger write 0 | `VERIFIED_REAL` |
| 추천 창 참고 합 | 7,471,506B × 6 = 44,829,036B | `VERIFIED_REAL` 산술; 전체 견적 아님 |
| API endpoint 변경 | HTTP 200, 합산 및 차단 계약 회귀시험 | `VERIFIED_REAL` |
| 새 UI 화면 | Edge 158 실제 조회와 상세 펼치기 | `VERIFIED_REAL` |
| 전체 공간 완료 | `full_spatial_coverage=false` | `BLOCKED` |
| 전체 전송량·실행 승인 | 미확정 | `BLOCKED` |
| BIG 승인·독립 정확도·학습·배포 | 미확정/미실행 | `BLOCKED` |

WorldCover 2021은 다른 연도의 ground truth가 아니다. SCL clear 품질, KLHK/WorldCover weak agreement와 independent accuracy를 분리한다.

## 5. 발표 스크립트

### 1분

“동자바 2023 시험 영상으로 36개 주·연도 셀을 다시 감사했습니다. 동시·유효 관측이 각각 6.56km² 늘어 전체 피복률은 0.977325%와 0.890387%가 됐습니다. 미수집 및 품질 공백 도형 72개를 재산출했고, 원격 다운로드와 원장 쓰기는 0건입니다. 주별 후보 6곳에서 한 창씩 받을 때의 예상 전송량 44,829,036바이트를 Edge 화면에서 확인했습니다. 전체 공백의 전송량과 독립 정확도는 미측정이며 BIG 승인, 학습, 배포 조건은 미충족입니다.”

### 5분

1. pilot 전 held-audit와 pilot 반영 후 재감사를 서로 다른 snapshot으로 고정했다.
2. 저장된 36셀 WKB와 East Java pilot native footprint를 exact union했다.
3. present와 clear가 각각 6,556,514.480755895m² 증가했다.
4. 새 비율은 0.9773249834093871%와 0.890386955270514%다.
5. 72개 exact missing feature를 생성했으며 full coverage는 false다.
6. 재감사는 읽기 전용으로 수행되어 collector·download·ledger write가 0이다.
7. 44,829,036B는 한 실측 창을 6개 후보에 복제한 참고값이고 full-gap 견적은 null이다.
8. 로컬 API와 Edge에서 36개 상세행과 전송 예상량을 확인했다.

## 6. Q&A

**Q. 기존 0.976741%는 틀린 값입니까?**
아니다. pilot 전 snapshot의 실제 값이다. pilot 반영 후 현재 재감사 값은 0.9773249834093871%다.

**Q. clear coverage는 얼마나 바뀌었습니까?**
0.8898034032819104%에서 0.890386955270514%로 늘었다. 여전히 전체 공간 완료와는 멀다.

**Q. 44,829,036B면 다음 수집 전체 비용입니까?**
아니다. 실측 한 창 7,471,506B를 6개 추천 후보에 한 번씩 적용한 산술 참고값이다. 전체 gap 전송량은 미확정이다.

**Q. 재감사하면서 새 자료를 받았습니까?**
아니다. collector·원격 다운로드·원장 쓰기 모두 0이며 저장된 자료만 읽었다.

**Q. 새 API/UI도 검증 완료입니까?**
로컬 8011에서 API와 Edge 화면을 검증했다. 전체 수집과 모델 운영은 별도 승인 단계에 있다.

**Q. 이제 학습을 시작할 수 있습니까?**
아니다. `learning_ready=false`이며 전체 공간·승인·KLHK native23/license·독립 ground truth가 남아 있다.
