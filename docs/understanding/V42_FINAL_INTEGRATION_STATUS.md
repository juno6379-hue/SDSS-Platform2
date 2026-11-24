# v4.2 최종 통합 상태: One Map·Sentinel·UI·모델·워크플로

- updated_at: 2026-11-24 KST
- overall_status: `IMPLEMENTED_UNVERIFIED`
- 범위: 완료된 One Map/Sentinel 감사, 로컬 CAS 이관, CCKP 수치 재현, API/UI 연결, 모델·벡터·오케스트레이터 계약
- 단일 pilot 후속: East Java 2023 예약·pin·실측 정산 경로 한 건은 `VERIFIED_REAL`; 전체 수집 승인은 별도다.

## 1. 쉬운 설명

현재 플랫폼은 **수집된 자료가 무엇인지 확인하고, 근거가 없으면 실행을 막고, 검증된 수치와 미검증 기능을 UI에서 구분해 보여 주는 단계**까지 왔다.

실제로 확인된 것은 다음과 같다.

- `VERIFIED_REAL` — 6개 지역×6개 연도, 즉 36개 셀 모두가 최소 28개 패치 기준을 충족했다. 다만 이는 “각 셀에 패치가 있다”는 뜻이지 “지역 전체가 공간적으로 채워졌다”는 뜻이 아니다.
- `VERIFIED_REAL` — 전체 경계 면적 대비 paired-present 피복률은 **0.976741%**, clear 피복률은 **0.889803%**다. 따라서 공간 공백은 각각 약 **99.023259%**, **99.110197%**다.
- `VERIFIED_REAL` — 로컬 CAS에 **6,125개 객체, 3,904,601,927B(약 3.904GB)**가 이관되었다. 새 원격 수집이 아니라 기존 로컬 산출물을 복사하고 해시로 고정한 결과다.
- `VERIFIED_REAL` — CCKP ERA5 CDD 자료 한 건에서 1951–1980 climatology 개발 bbox 평균 **40.91221481742199 days**를 재현했다. 인도네시아 행정경계 평균도, 연별·월별 값도 아니다.
- `VERIFIED_REAL` — root의 실제 Microsoft Edge 클릭 점검에서 UI가 고정된 API 응답과 차단 상태를 표시하는 흐름을 확인했다. 이는 화면 연결 확인이지 운영 배포나 과학 정확도 증거가 아니다.
- `TESTED_SYNTHETIC` — 세 모델 유형의 adapter 계약과 내구성 워크플로 오케스트레이터 계약을 합성 자료로 시험했다.
- `IMPLEMENTED_UNVERIFIED` — 모델 spec/catalog와 private hash embedding VectorDB는 구현되었으나 실제 모델 품질·검색 의미 품질은 검증하지 않았다.
- `VERIFIED_REAL` — East Java 2023 고정 scene 한 건에서 reservation, exact scene/asset/window pin, same-scene 6 band+SCL, bounded Range I/O와 실측 정산 경로를 완료했다.
- `BLOCKED` — Sentinel 전체 공간 공백과 전체 수집 승인·예산 충분성, KLHK native 23-class domain·license, 독립 ground truth/accuracy, 실제 학습·배포, public RAG가 남아 있다.

가장 중요한 해석은 두 가지다.

1. **36/36 최소 패치 기준 충족 ≠ 공간 수집 완료**다.
2. **WorldCover 2021 또는 KLHK와의 약한 참조 일치도 ≠ 독립 정확도**다. WorldCover 2021을 다른 연도의 정답으로 쓰지 않는다.

## 2. 이론적 배경

### 2.1 개수 완전성과 공간 완전성

셀별 패치 수는 표본의 존재 여부만 말한다. 공간 완전성은 각 패치 footprint와 경계 polygon의 교집합 면적을 합집합으로 계산해야 한다. 따라서 셀마다 28개 이상이 있어도 패치가 작은 구역에 겹쳐 있으면 전체 공간 피복률은 낮다.

이 감사에서 `weighted_present_coverage_pct=0.976741...`은 **0.976741%**다. 97.6741%가 아니다. clear coverage는 구름 등 품질 조건을 적용해 더 엄격하게 계산한 **0.889803%**다.

### 2.2 내용 주소 저장소(CAS)

CAS는 파일 내용을 SHA-256 같은 digest로 식별한다. 같은 내용은 같은 주소를 가지므로 중복·변조를 탐지하기 쉽다. 그러나 CAS에 들어갔다는 사실은 데이터의 공간 대표성, 정답성, 라이선스를 보증하지 않는다.

### 2.3 약한 참조 일치도와 독립 정확도

약한 참조는 후보 라벨 생성·오류 탐색·보조 비교에 유용하다. 독립 정확도는 모델 학습·참조 생성과 분리된 라벨 원천, 동년성, 공간 holdout, 평가 protocol이 필요하다. 따라서 다음을 분리한다.

- WorldCover 2021: 약한 참조. 다른 연도 정답 아님.
- KLHK 기관 자료: 중요한 기관 참조가 될 수 있으나 native 23-class domain·license와 평가 독립성이 확정되지 않음.
- weak agreement: 참조와의 일치 정도.
- independent accuracy: 독립 지상정답으로 평가한 성능. 현재 없음.

### 2.4 Fail-closed 실행

워크플로는 등록된 Python adapter만 실행하며 plan/input fingerprint가 달라지면 기존 상태를 재사용하지 않는다. 증거 SHA, 의존성, lock, blocker가 맞지 않으면 다음 단계로 진행하지 않는다. 이 구조가 있다고 해서 실제 adapter가 모두 등록되었거나 학습이 실행된 것은 아니다.

## 3. 코드·데이터 동작

### 3.1 One Map·Sentinel 감사와 CAS

`services/datahub/connectors/onemap/`과 `services/datahub/sentinel/`은 경계·패치·scene 증거를 읽고 셀별 수량과 footprint 피복을 별도로 계산한다. `evidence/onemap_sentinel/` 인계 자료는 다음 사실을 고정한다.

| 항목 | 값 | 상태/해석 |
|---|---:|---|
| 최소 패치 기준 충족 셀 | 36/36 | `VERIFIED_REAL`; 수량 기준만 충족 |
| 물리 패치 record | 1,779 | `VERIFIED_REAL` 감사 입력 |
| 품질 적격 manifest | 1,407 | `VERIFIED_REAL` 감사 입력 |
| paired-present coverage | 0.9767414314207837% | `VERIFIED_REAL`; 보수적 하한 |
| clear coverage | 0.8898034032819104% | `VERIFIED_REAL`; 보수적 하한 |
| full spatial coverage | false | `BLOCKED` |
| missing queue | 72 features / 317,455,915B | 참조 대기열; 승인 없는 다운로드 금지 |
| CAS post-state | 6,125 objects / 3,904,601,927B | `VERIFIED_REAL`; 로컬 copy, 원격 download 0 |
| 활성 collector | 0 | 감사 시점 상태 |

이 표는 pilot 이전 held-audit snapshot이다. 이후 단일 pilot 경로에서는 reservation adapter와 exact scene/asset/window pin을 실제 사용해 원격 I/O와 원장 정산을 완료했다. 그러나 pilot 관측은 아직 36셀 aggregate에 포함되지 않았으므로 위 0.976741%·0.889803%를 최신 aggregate로 다시 계산했다고 말할 수 없다.

### 3.2 East Java 2023 단일 실제 pilot

고정 scene `S2A_MSIL2A_20230905T023531_R089_T49MFM_20240916T145247`에서 B02·B03·B04·B08·B11·B12와 SCL을 동일 scene으로 고정했다. 6×256×256 출력과 정렬된 SCL·quality mask를 생성했으며 clear pixel은 65,536/65,536였다.

- 원격 요청 28건, 본문 7,471,506B
- 오류 0, 관측 HTTP 429 0
- ledger SHA: `8e98...aa44a` → `b257...25de1`
- 남은 전역 byte 잔액: 1,678,521,030B
- 후속 pilot 0, 활성 collector 0, legacy execution/ledger lock 0
- `learning_ready=false`, `independent_ground_truth=false`, `used_in_aggregate_coverage=false`

따라서 **단일 pilot 실행 경로**는 `VERIFIED_REAL`이지만 전체 수집 승인, 예산 충분성, BIG 승인과 aggregate 공간 완료는 `BLOCKED`다.

### 3.3 CCKP 정량 경로

`services/climate_query/`는 고정된 원본 SHA, Range receipt, CF metadata와 계산 조건을 확인한 뒤 허용된 CDD 통계만 재현한다. 실제 검증값은 개발 bbox 12,765 full cells의 구면 면적가중 평균 **40.91221481742199 days** 한 건이다.

이 값은 `[95,-11,141,6]` bbox 결과이며 행정경계 clipping, 해양 제외, 부분셀 가중을 하지 않았다. ERA5는 재분석 자료이므로 독립 현장 ground truth가 아니다.

### 3.4 API/UI

`services/api/`는 증거 lock과 SHA를 확인하고 CCKP, KLHK/RAG, private vector, Sentinel 감사, 모델 readiness, workflow 상태를 읽기 전용으로 제공한다. `web/`은 외부 asset 없이 이 상태를 표시하며 실행 버튼을 열지 않는다.

root가 실제 Edge에서 화면 클릭 흐름을 확인했다(`VERIFIED_REAL`). 별도로 자동 API 시험 11개는 통과했고 Playwright browser 시험 3개는 명시적 실행 조건이 없어 skip되었다. 따라서 실제 Edge 클릭과 자동 browser suite는 같은 증거로 합치지 않는다. 운영 배포·다중 사용자·인증은 검증되지 않았다.

### 3.5 모델 계약

`services/models/`에는 다음 세 유형의 manifest와 adapter 계약이 있다.

1. LCLUC 6-band segmentation
2. structured climate feature
3. RAG embedding/reranker

합성시험은 band 순서, cloud mask, ACL-before-tokenization, numeric RAG 차단, registry 불변성 등을 확인한다(`TESTED_SYNTHETIC`). 하지만 spec은 설계 계약일 뿐 학습된 모델이 아니다(`IMPLEMENTED_UNVERIFIED`). 실제 legacy checkpoint는 3-band 입력·9-class 출력이므로 새 6-band·23-class 계약과 맞지 않아 추론을 차단한다.

### 3.6 Private VectorDB

`services/vectorstore/`의 고정 SQLite index에는 7개 문서, 122개 chunk, 64차원 `synthetic-hash-64-v1` embedding이 있다. 접근은 private/data_steward로 제한되고 public search와 numeric answer는 꺼져 있다.

DB SHA와 문서 수는 고정됐지만 hash embedding의 다국어·의미 검색 품질은 검증하지 않았다. 그러므로 저장 구현은 `IMPLEMENTED_UNVERIFIED`, public RAG는 `BLOCKED`다.

### 3.7 내구성 워크플로

`services/orchestration/workflow.py`는 DAG 순서, input/plan drift, atomic state, lock, resume, evidence digest, blocker를 처리한다. 합성시험으로 계약을 확인했지만 실제 학습·배포 adapter 실행은 없다. 별도의 Sentinel data follow-up 단위는 단일 pilot까지 실제 완료됐으며 이를 전체 orchestration·학습 완료로 확대하지 않는다.

## 4. 테스트·증거

| 증거 | 결과 | 판정 |
|---|---|---|
| Sentinel held audit | 36/36 최소 수량, paired 0.976741%, clear 0.889803%, full coverage=false | `VERIFIED_REAL` |
| CAS migration receipt/post-state | 6,125 objects, 3,904,601,927B, remote downloads 0 | `VERIFIED_REAL` |
| East Java 2023 single pilot | same-scene 6 band+SCL, clear 65,536/65,536, 28 requests, 7,471,506B | `VERIFIED_REAL` |
| pilot postflight | error·429·후속 pilot·collector·locks 모두 0, 잔액 1,678,521,030B | `VERIFIED_REAL` |
| CCKP 실제 원본 재현 | 4,209,592B 원본, 17 Range chunks, 12,765 cells, 40.91221481742199 days | `VERIFIED_REAL` |
| Edge UI 직접 클릭 | 고정 API 상태와 차단 표시 확인 | `VERIFIED_REAL`; 운영 배포 증거 아님 |
| API 자동시험 | 11 passed | 계약·실원본 snapshot 재현 |
| Playwright browser suite | 3 skipped | 자동 browser 통과로 표현 금지 |
| 모델 계약 | 14 passed | `TESTED_SYNTHETIC` |
| 오케스트레이터 계약 | 5 tests | `TESTED_SYNTHETIC` |
| private VectorDB | DB/document/chunk/SHA pin | 저장은 구현, embedding quality `IMPLEMENTED_UNVERIFIED` |

현재 blocker는 다음과 같다.

- Sentinel present 기준 약 99.023259%, clear 기준 약 99.110197% 공간 공백
- single pilot 후 36셀 coverage aggregate 재감사 없음; 0.976741%는 이전 snapshot
- 전체 수집 승인·예산 충분성과 BIG 승인 미확인
- KLHK native 23-class coded domain과 license 미확인
- 독립 ground truth와 독립 accuracy 없음
- 실제 학습·추론·배포 0
- public RAG와 운영 semantic embedding 없음

## 5. 발표 스크립트

### 1분

“v4.2는 증거를 고정하고 완료와 미완료를 화면에서 구분하는 통합 단계까지 왔습니다. East Java 2023 단일 scene은 예약·pin·same-scene 6 band+SCL·실측 정산까지 실제 완료했고 clear 65,536/65,536, 오류와 429 0을 확인했습니다. 그러나 이 pilot을 36셀 aggregate에 아직 반영하지 않아 0.976741%는 이전 snapshot입니다. 전체 공간 공백과 수집 승인·예산, KLHK 23-class와 license, 독립 ground truth, 실제 학습·배포, public RAG는 남아 있습니다. WorldCover 2021은 다른 연도 정답이 아니며 weak agreement를 독립 정확도로 발표하지 않습니다.”

### 5분

1. **감사** — 36/36은 셀별 최소 패치 수 기준이며 full spatial coverage가 아니다.
2. **공간 지표** — paired-present 0.976741%, clear 0.889803%로 약 99% 공백이 남는다.
3. **저장** — 기존 로컬 산출물 6,125개, 3,904,601,927B를 CAS로 복사·해시 고정했다. 새 원격 수집은 0건이다.
4. **정량 기후** — 실제 ERA5 CDD 원본에서 1951–1980 개발 bbox 평균 40.91221481742199 days를 재현했다. 행정경계 평균이나 독립 ground truth가 아니다.
5. **UI** — 실제 Edge 클릭은 API/UI 연결과 차단 표시를 확인했다. 자동 Playwright 3건은 skip이며 운영 배포를 증명하지 않는다.
6. **모델·RAG** — 모델 adapter와 오케스트레이터 계약은 합성시험을 통과했다. 모델 spec과 private hash VectorDB 품질은 미검증이다.
7. **다음 Gate** — 단일 pilot 경로는 완료됐지만 aggregate 재감사, 전체 수집 승인·예산, 공간 공백 보완, KLHK native23/license, 독립 평가셋, 실제 학습·배포, public RAG 승인이 필요하다.

## 6. Q&A

**Q. 36/36이면 Sentinel 학습자료가 완성된 것 아닙니까?**  
아니다. 모든 셀이 최소 수량을 충족했을 뿐 paired 공간 피복은 0.976741%, clear 피복은 0.889803%다.

**Q. 0.976741은 97.6741%입니까?**  
아니다. evidence field가 percent 단위이므로 **0.976741%**다.

**Q. CAS 3.904GB는 새로 다운로드한 양입니까?**  
아니다. 기존 로컬 산출물의 copy 이관이며 원격 다운로드와 ledger write는 0건이다.

**Q. reservation과 scene pin은 아직도 미구현입니까?**  
아니다. East Java 2023 단일 pilot에서는 실제 예약·pin·I/O·정산까지 완료했다. 다만 전체 36셀 반복 수집 승인과 예산 충분성은 검증되지 않았다.

**Q. pilot로 0.976741%가 개선됐습니까?**  
아직 알 수 없다. pilot 관측은 aggregate에 사용되지 않았고 36셀 coverage 재감사를 하지 않았다. 0.976741%는 pilot 이전 snapshot이다.

**Q. UI가 Edge에서 동작했으니 운영 서비스입니까?**  
아니다. 로컬 실제 클릭으로 연결을 확인했을 뿐 인증·다중 사용자·배포·가용성은 별도 검증 대상이다.

**Q. 모델 catalog가 있으니 학습 가능한 상태입니까?**  
아니다. spec과 adapter 계약은 있지만 data readiness, 23-class mapping, checkpoint, 독립 accuracy, reproducible environment가 없어 학습·추론·배포를 차단한다.

**Q. private VectorDB가 semantic RAG 완성을 뜻합니까?**  
아니다. `synthetic-hash-64-v1`은 의미 품질을 검증하지 않은 private review index다. public search와 numeric answer는 비활성이다.

**Q. WorldCover 2021이나 KLHK 일치도를 정확도라고 말할 수 있습니까?**  
독립 라벨 원천과 평가 protocol이 없으면 말할 수 없다. weak agreement와 independent accuracy를 분리하며 WorldCover 2021을 다른 연도의 정답으로 사용하지 않는다.

**Q. 다음 작업은 무엇입니까?**  
단일 reservation·pin 경로는 완료됐다. 다음에는 BIG와 전체 수집 승인·예산을 확정하고, pilot을 포함한 36셀 aggregate를 재감사한 뒤 공간 공백을 보완해야 한다. KLHK native 23-class/license와 독립 평가자료도 별도로 확보해야 한다.
