# v4.2 Sentinel 경계 내 후속 배치

- updated_at: 2026-11-25 12:05 KST
- 계획·진행 파일: `VERIFIED_REAL`
- 현재 실행 상태: `BLOCKED` — 저장된 상태는 `RUNNING`이지만 PID 37644가 사라졌고 worker가 응답하지 않음
- 코드 계약시험: Root 확인 20 PASS
- 학습 준비·전체 공간 완료: `BLOCKED`

## 1. 쉬운 설명

pilot 한 건으로 검증한 예약·동일 장면 6밴드+SCL·bounded Range 경로를 6개 주, 2020~2025년의 36개 주·연도 셀에 한 창씩 적용하는 제한 배치를 시작했다.

계획은 다음과 같다.

- 6개 주 × 6개 연도 = **36개 창**, 미계획 셀 0
- 각 창 256×256, BIG 경계와 exact missing geometry 안에 포함
- 기존 보유·시도 footprint와 계획 시점 중첩 0m²
- 같은 scene의 B02·B03·B04·B08·B11·B12와 SCL
- 창당 최대 **32MiB** 예약, 전체 최대 예약 합 **1,207,959,552B**
- 첫 6개는 East Java → South Sulawesi → West Java → Southeast Sulawesi → Gorontalo → Banten으로 서로 다른 주를 방문
- HTTP 429 또는 실제 전송 실패면 다음 창을 보내지 않음
- 7개 asset 전송이 완전하지만 SCL clear가 80% 미달이면 품질 공백으로 기록하고 다음 창을 계속 시도

2026-11-25 11:43 KST 중간 실측에서 PID 37644가 실행 중이며 세 번째 West Java 2023 창이 active였다. 첫 East Java 2023 창은 같은 scene의 6밴드+SCL 7개를 정상 수신했고 SCL clear 32,422/65,536 = **49.47%**로 품질 공백에 기록됐다. 두 번째 South Sulawesi 2024 창은 SCL clear **100%**로 품질 기준을 통과했다. 두 창 모두 429가 없었다. 이는 역사적 중간 snapshot이다.

첫 구현은 품질 미달에서 멈췄지만, 전송 완료와 전송 실패를 구분하도록 수정한 뒤 이미 받은 첫 창을 재다운로드하지 않고 observation으로 복구하고 다음 창을 계속했다. 11:44 KST에는 West Java 2023까지 완료해 3/36 수신, QA 통과 2/3, present 증가 19,640,308.346606173m², clear 증가 16,327,471.607276801m², 누적 사용 18,351,282B, 원장 잔액 1,660,169,748B였다. 429와 학습 적격 수는 0이었다.

그러나 12:05 KST reconciliation에서는 worker PID가 더 이상 살아 있지 않았다. 저장된 progress는 8/36 수신·QA 통과 5를 기록했고, 9번째 West Java 2024 창은 `pending`, `io_started=true`, 32MiB 예약 상태지만 receipt가 없어 실제 전송량을 확정할 수 없다. 관측 HTTP 429는 0이다. 따라서 현재 상태는 `RUNNING`이 아니라 **정산 전 worker 종료로 인한 `BLOCKED`**이며, pending transfer 검증·정산 전에는 재개·완료로 처리하지 않는다.

## 2. 이론적 배경

### 2.1 주 균형 순회

한 지역만 연속 수집하면 짧은 실행에서도 지역 편향이 커진다. 이 구현은 주별 missing area가 큰 연도를 정렬한 뒤 round-robin으로 다른 주를 먼저 방문한다. 첫 여섯 창이 여섯 주를 한 번씩 방문한 뒤 다음 연도로 넘어간다.

### 2.2 경계·missing geometry 포함

후보 창은 단순 bbox 중심이 아니라 BIG 개발 경계와 exact missing geometry 안에 모두 들어가야 한다. 이미 보유했거나 원장에 pending/charged로 기록된 footprint와 겹치는 창도 제외한다. 이는 중복 전송을 줄이지만 BIG 공식 사용 승인을 뜻하지 않는다.

### 2.3 예약과 중단 회로

각 창은 원격 I/O 전 32MiB를 예약하고 실제 읽은 byte로 정산한다. HEAD에서 ETag·size를 고정한 후 Range GET을 수행한다. 429 또는 asset 누락·불완전 계측 같은 실제 전송 실패에서는 fail-closed로 멈춘다. 반면 7개 asset 전송이 완전한 SCL 80% 미달은 관측 자체를 버리지 않고 quality gap으로 분리하며 다음 창으로 진행한다. 계획상 36창 최대 예약 합은 배치 상한이며 실제 과금·전체 gap 비용과 다르다.

## 3. 코드·데이터 동작

`services/datahub/sentinel/coverage_batch.py`는 다음을 수행한다.

1. post-pilot 36셀 재감사와 공유 원장 SHA를 고정한다.
2. 36셀을 missing area 순으로 주별 정렬하고 round-robin 순서를 만든다.
3. exact queue·boundary·scene manifest·native checkpoint를 검증한다.
4. 경계와 missing geometry 안의 256×256 창을 고르고 이전 시도와 중복을 제거한다.
5. 모든 주가 계획에 포함되고 36셀 scope·32MiB 예약 상한이 맞는지 확인한다.
6. 단일 coordinator lock 아래 각 창의 HEAD pin·예약·Range I/O·QA·정산을 순차 실행한다.
7. 완전 전송 창은 observation을 남기고 QA 미달은 quality gap으로 분리한다. 429·실제 전송 실패에서만 즉시 중단한다.

성공 observation에도 `label_source=null`, `learning_ready=false`, `independent_ground_truth=false`가 기록된다. 수집 성공과 학습 적격을 분리하기 위한 계약이다.

## 4. 테스트·증거

### 계획

| 항목 | 확인값 | 상태 |
|---|---:|---|
| planned windows | 36 | `VERIFIED_REAL` 계획 artifact |
| provinces/years | 6개 주 × 2020~2025 | `VERIFIED_REAL` |
| unplanned cells | 0 | `VERIFIED_REAL` |
| 경계·missing geometry 포함 | 36개 계획 확인 | `VERIFIED_REAL` 계획 검증 |
| 기존 footprint overlap | 각 계획 0m² | `VERIFIED_REAL` 계획 검증 |
| same-scene 6 band+SCL | 전체 계획 true | `VERIFIED_REAL` 계획 검증 |
| reservation | 창당 33,554,432B | `VERIFIED_REAL` 계획값 |
| 최대 예약 합 | 1,207,959,552B | 계획 상한; 실제 과금 아님 |
| 계약시험 | 20 PASS | Root 검증 |

### 11:44 KST 실제 진행 — 역사적 snapshot

| 항목 | 확인값 |
|---|---:|
| process | PID 37644, Python, running/responding |
| progress status | `RUNNING` |
| active | Southeast Sulawesi 2025, index 4 |
| completed windows | 3 / 36 |
| quality-passing windows | 2 / 3 |
| first window QA | East Java 2023, clear 49.47%, quality gap |
| second window QA | South Sulawesi 2024, clear 100%, PASS |
| HTTP 429 | 0 |
| charged bytes / remaining | 18,351,282B / 1,660,169,748B |
| added present/clear area | 19,640,308.346606173 / 16,327,471.607276801m² |
| new training-eligible patches | 0 |

### 12:05 KST reconciliation — 현재 상태

| 항목 | 확인값 |
|---|---:|
| 저장된 progress status | `RUNNING` — stale persisted state |
| 실제 process | PID 37644 not alive |
| received / quality pass | 8 / 36, 5 pass |
| pending window | West Java 2024, index 9 |
| pending reservation | 33,554,432B, `io_started=true` |
| pending receipt | 없음; 실제 전송량 미확정 |
| observed HTTP 429 | 0 |
| current decision | `BLOCKED` |

현재 blocker는 `SENTINEL_WORKER_EXITED_BEFORE_WINDOW_SETTLEMENT`와 `PENDING_TRANSFER_AMOUNT_UNVERIFIED`다. 11:44 snapshot의 면적·byte 값은 그 시점의 유효한 역사 기록이지만 현재 누계로 재사용하지 않는다.

전역 피복은 아직 post-pilot 재감사값인 present **0.9773249834093871%**, clear **0.890386955270514%**다. 위 신규 창 면적은 배치 progress의 관측 증가분이며 후속 aggregate 재감사를 하기 전 전역 피복으로 합산하지 않는다.

## 5. 발표 스크립트

### 1분

“Sentinel 후속 배치는 36창을 계획했고 12시 5분 reconciliation에서 8창 수신·QA 통과 5를 확인했습니다. 그러나 worker PID가 사라졌고 9번째 West Java 2024 창은 32MiB 예약 뒤 실제 전송량이 미확정입니다. 429는 0이지만 정산 전 종료이므로 현재 상태는 차단입니다. pending transfer를 검증·정산하기 전 재개하지 않으며, 전역 피복은 후속 aggregate 재감사 전까지 기존 0.977325%와 0.890387%입니다.”

### 5분

1. post-pilot exact queue와 공유 원장 SHA를 입력으로 고정했다.
2. 6개 주×6개 연도 36셀 모두에서 경계·missing geometry 내부 창을 계획했다.
3. round-robin으로 첫 여섯 창이 서로 다른 주를 방문한다.
4. 각 창은 32MiB 예약, HEAD pin, bounded Range, SCL 80% QA를 거친다.
5. 429·실제 전송 실패는 정지하고, 완전 전송 QA 미달은 quality gap으로 기록해 계속한다.
6. Root가 최종 계약시험 20건을 확인했다.
7. 11:44 snapshot에는 세 창 수신·QA 통과 2·네 번째 창 active·429 0이 기록됐다.
8. 12:05 reconciliation에서는 8/36·QA 통과 5, worker 종료, 9번째 pending reservation 미정산을 확인해 `BLOCKED`로 판정했다.
9. 현재 신규 면적 누계는 후속 aggregate 재감사 전 전역 피복으로 합산하지 않으며 학습 적격은 0이다.

## 6. Q&A

**Q. 36개 창이 모두 수집됐습니까?**
아니다. 36개는 계획 수다. 최신 reconciliation은 8/36 수신·QA 통과 5이며 worker가 종료됐다.

**Q. 경계 밖 창이 섞일 수 있습니까?**
계획기는 256×256 target geometry가 BIG 개발 경계와 exact missing geometry 안에 포함되는지 확인한다. 다만 BIG 공식 사용 승인은 아직 별도다.

**Q. 1,207,959,552B가 실제 사용량입니까?**
아니다. 36×32MiB의 최대 예약 합이다. 실제 과금은 성공·실패별 원장 정산 뒤에만 알 수 있다.

**Q. 배경 실행이니 계속 성공한다고 가정해도 됩니까?**
안 된다. 429·실제 전송 실패뿐 아니라 정산 전 worker 종료도 차단 조건이다. 현재 9번째 pending transfer의 실제 byte가 미확정이라 검증·정산 전 재개하면 안 된다.

**Q. 전역 피복이 늘었습니까?**
11:44 역사 snapshot에는 present 약 +19.640308km², clear 약 +16.327472km²가 기록됐다. 최신 8개 observation의 면적·byte는 9번째 pending transfer와 분리해 재감사해야 한다. aggregate 재감사 전 전역값은 0.9773249834093871%와 0.890386955270514%로 유지한다.

**Q. clear 49.47% 창은 전송 실패입니까?**
아니다. 7개 asset과 계측이 완전하고 429·오류가 없는 품질 미달 관측이다. 품질 공백으로 분리하며 학습 적격에는 넣지 않는다.

**Q. 성공 창은 바로 학습자료입니까?**
아니다. 관측에는 label source와 독립 ground truth가 없고 학습 적격 수는 0으로 유지한다.

**Q. WorldCover 2021을 다른 연도 라벨로 붙입니까?**
아니다. 타연도 독립 ground truth로 사용하지 않으며 weak agreement와 independent accuracy를 분리한다.
