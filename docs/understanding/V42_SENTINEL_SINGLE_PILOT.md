# v4.2 Sentinel 단일 실제 pilot

- updated_at: 2026-11-24 KST
- pilot_status: `VERIFIED_REAL`
- 전체 수집·학습 상태: `BLOCKED`
- 대상: East Java 2023, 고정 Sentinel-2 scene 한 건
- 후속 상태: 2026-11-25 36셀 재감사 완료; 상세는 `V42_SENTINEL_POST_PILOT_REAUDIT.md`

## 1. 쉬운 설명

이전에는 예약 원장과 scene/asset/window pin을 실제 원격 I/O에 연결한 경로가 없었다. 이번에는 **East Java 2023 한 건만** 허용해 그 경로를 실제로 끝까지 실행했다.

- 고정 scene: `S2A_MSIL2A_20230905T023531_R089_T49MFM_20240916T145247`
- 같은 scene의 B02·B03·B04·B08·B11·B12와 SCL을 함께 사용
- 결과 영상: 6 band × 256 × 256, 정렬된 SCL·quality mask 포함
- clear pixel: 65,536 / 65,536 = 100%
- 원격 요청: 28건, 읽은 본문: 7,471,506B
- 오류: 없음, 관측된 HTTP 429: 없음
- 원장: 예약→I/O 시작→실측 정산을 거쳐 SHA가 변경됨
- 남은 전역 byte 잔액: 1,678,521,030B
- 후속 pilot 0, 활성 collector 0, execution/ledger lock 0

따라서 단일 pilot용 reservation·pin·bounded Range·정산 경로는 `VERIFIED_REAL`이다. 그러나 이 한 패치는 전체 공간 수집 완료나 학습 준비를 뜻하지 않는다.

pilot 완료 시점에는 관측값이 36셀 aggregate에 아직 반영되지 않았고 **0.976741% paired-present와 0.889803% clear coverage는 pilot 이전 snapshot**이었다. 이후 2026-11-25 exact geometry 재감사를 완료해 현재값은 0.9773249834093871%와 0.890386955270514%다. 남은 잔액만으로 전체 수집 예산이 충분하다고 말할 수 없다는 판단은 그대로다.

## 2. 이론적 배경

### 2.1 Reservation과 실측 정산

원격 I/O 전에 최대 비용을 예약하고, I/O가 시작된 뒤에는 실제 읽은 byte로 정산한다. 동일 idempotency key의 중복 예약과 다른 작업의 원장 덮어쓰기를 막는다. 이번 실행은 33,554,432B를 예약한 뒤 실측 7,471,506B로 정산했다.

### 2.2 Scene·asset·window pin

재현 가능한 위성 패치는 다음 세 요소를 고정해야 한다.

1. scene ID와 촬영 시각
2. 같은 scene에 속한 6개 band와 SCL asset URI·ETag
3. 각 native raster에서 읽을 pixel window

이번 pilot은 이를 sealed plan과 receipt SHA로 고정했다. 10m band와 20m B11/B12/SCL을 같은 10m 출력 grid에 정렬했다.

### 2.3 품질 100%의 한계

100% clear는 이 **256×256 단일 window**에서 native SCL을 다시 계산한 결과다. East Java 전체, 2023년 전체, 36개 셀 전체의 clear coverage가 100%라는 뜻이 아니다. 또한 SCL 기반 clear 판정은 독립 지상정답 정확도가 아니다.

## 3. 코드·데이터 동작

1. read-only preflight가 활성 collector, 기존 lock, 과거 ledger drift를 확인한다.
2. 승인된 단일 plan이 scene·asset·window와 최대 pilot 수 1을 봉인한다.
3. 원장에 33,554,432B를 예약하고 I/O 시작 상태를 기록한다.
4. HEAD와 bounded HTTP Range만 사용해 필요한 TIFF block을 읽는다. 전체 remote asset은 다운로드하지 않는다.
5. 6-band image와 aligned SCL·quality GeoTIFF를 생성하고 SHA를 고정한다.
6. native SCL에서 quality를 재계산해 65,536개 전부 clear임을 확인한다.
7. 실제 본문 7,471,506B로 원장을 정산하고 receipt·observation을 기록한다.
8. source CAS와 과거 batch는 변경하지 않고 lock을 남기지 않는다.

원장 SHA는 다음과 같이 바뀌었다.

- 전: `8e98e9ba033f015e4e289860166b87f67d81a10e12fee66c9b45481296caa44a`
- 후: `b257db2925e5c4eac99081c5539216314c972d49dd6741f38f5780da7dd25de1`

`incoming-observation-v2.json`은 `learning_ready=false`, `independent_ground_truth=false`, `used_in_aggregate_coverage=false`를 명시한다.

## 4. 테스트·증거

| 증거 | 결과 | 상태 |
|---|---|---|
| 실제 pilot result | East Java 2023, same-scene 6 band + SCL, QA PASS | `VERIFIED_REAL` |
| clear pixel | 65,536 / 65,536 = 1.0 | `VERIFIED_REAL`; 단일 window 한정 |
| 원격 계측 | 28 requests, 7,471,506B, error 0, 429 0 | `VERIFIED_REAL` |
| 원장 정산 | before/after SHA 고정, 잔액 1,678,521,030B | `VERIFIED_REAL` |
| postflight | 후속 pilot 0, collector 0, locks 0, 기존 batch 불변 | `VERIFIED_REAL` |
| pilot 계약시험 | 26 PASS | `TESTED_SYNTHETIC` |
| 36셀 aggregate 재감사 | 후속 exact geometry 재감사 완료 | `VERIFIED_REAL`; 별도 이해자료 참조 |
| 재감사 API/UI | 로컬 API와 실제 Edge에서 36행·6후보·42.75MiB 확인 | `VERIFIED_REAL` |
| 전체 수집 예산·승인 | 잔액만 확인; 충분성·BIG 승인 미확인 | `BLOCKED` |
| 독립 정확도·학습·배포 | 측정/실행 0 | `BLOCKED` |

WorldCover 2021은 다른 연도의 ground truth가 아니다. 이번 SCL quality PASS나 WorldCover/KLHK weak agreement를 independent accuracy로 바꾸어 말하지 않는다.

## 5. 발표 스크립트

### 1분

“East Java 2023의 고정 Sentinel-2 scene 한 건으로 실제 pilot을 완료했습니다. 같은 scene의 6개 band와 SCL을 정렬했고 65,536개 pixel이 모두 clear였습니다. 28개 원격 요청에서 본문 7,471,506바이트를 읽었고 오류와 429는 없었습니다. 이후 exact geometry 재감사에서 피복률은 0.977325%와 0.890387%가 됐습니다. 전체 공간 완료, 예산 충분성, BIG 승인, 독립 정확도, 학습·배포는 여전히 차단 상태입니다.”

### 5분

1. pilot은 East Java 2023 한 scene·한 window로 범위를 봉인했다.
2. 6개 band와 SCL의 scene ID, URI, ETag, native window를 고정했다.
3. 전체 asset 대신 bounded Range 7,471,506B만 읽었다.
4. 6×256×256 image, aligned SCL, quality를 생성하고 SHA로 고정했다.
5. native SCL 재계산에서 clear 100%를 확인했다.
6. 33,554,432B 예약 후 7,471,506B 실측 정산으로 원장 SHA를 갱신했다.
7. 후속 pilot·collector·lock은 0이며 과거 batch와 source CAS는 불변이다.
8. 이 결과는 single-path 실행 증거일 뿐 aggregate 공간 완료나 독립 정확도 증거가 아니다.

## 6. Q&A

**Q. reservation과 scene pin은 이제 완료됐습니까?**  
단일 pilot 경로는 실제 구현·실행·정산까지 완료했다. 전체 36셀 수집을 위한 승인, 우선순위, 예산과 반복 실행 권한은 별도이며 여전히 `BLOCKED`다.

**Q. clear 100%이면 East Java 2023이 모두 깨끗합니까?**  
아니다. 고정된 256×256 window 한 곳의 65,536 pixel에만 해당한다.

**Q. 기존 0.976741%가 증가했습니까?**  
그렇다. 후속 exact geometry 재감사에서 0.9773249834093871%로 계산됐다. 0.976741%는 pilot 이전 snapshot이다.

**Q. 잔액 1.678GB면 전체 수집에 충분합니까?**  
확정할 수 없다. 남은 byte budget은 확인됐지만 전체 gap을 채우는 비용 추정과 승인 결과가 없다.

**Q. 학습에 바로 넣습니까?**  
아니다. `learning_ready=false`, `independent_ground_truth=false`다. KLHK native23/license, 독립 라벨과 aggregate readiness Gate가 필요하다.

**Q. WorldCover 2021로 다른 연도를 검증할 수 있습니까?**  
아니다. 타연도 독립 ground truth가 아니며 weak agreement와 independent accuracy를 분리한다.
