# v4.2 그대로 읽는 1분·5분 발표

## 1분

“v4.2에서는 기후 설명과 숫자의 경로를 분리하고 실제 CCKP CDD 원본 한 건을 SHA로 고정해 계산했습니다. 1951년부터 1980년까지 제공된 climatology의 개발 bbox 12,765셀 구면가중 평균은 40.91221481742199일입니다. 하지만 인도네시아 행정경계 평균이나 연별·월별 값이 아니며 ERA5 재분석은 독립 ground truth가 아닙니다. live 서비스·학습·배포는 0건이므로 전체 완료는 아닙니다.”

## 5분

1. **문제** — 벡터 유사도는 숫자의 단위·달력·격자·시나리오나 기관 authority를 보증하지 않는다.
2. **공통 계약** — source/version/URI/SHA/license/acquired_at, 관측/전망, 모델/시나리오, 단위, CF 달력, 공간·시간, ACL, trace를 필수로 고정한다.
3. **설명 경로** — ACL·license·유효기간 선필터 후 BM25·합성 hash vector·metadata로 찾고 원문 citation을 재검증한다.
4. **정량 경로** — `climate.query`는 고정 raw·receipt·CF·license가 맞는 한 CDD bbox 통계만 반환한다.
5. **source·lake·feature** — bounded discovery와 receipt, CF/as-of/ACL/bbox 계획은 fail-closed다. planner는 `execution_started=false`, `numeric_features=null`이다.
6. **시험 증거** — contract/RAG 23, source 24, lake/feature 24로 합성 71 PASS이며, 별도 climate.query는 합성 12 + 실원본 재현 2를 통과했다.
7. **정직한 한계** — 행정경계 통계, 연별/월별 시계열, 독립 정확도, live API/RAG 등록, 학습·배포는 검증하지 않았다.

상세 근거: [v4.2 기후 계약·RAG 이해자료](../V42_CLIMATE_FOUNDATION_AND_RAG.md)

## KLHK ingestion·MLOps 추가 1분

“KLHK·CCKP 문서는 원문과 SHA를 고정하고 검토 전에는 운영 RAG나 학습으로 넘기지 않도록 했습니다. 실제 metadata 원본 7개, 122개 span, 381,676바이트를 보존했고 SHA 불일치는 없었습니다. 그러나 KLHK renderer는 25항목이며 native 23클래스 domain과 license는 미확인입니다. ingestion/RAG 29건과 MLOps 6건의 합성시험은 통과했지만 실제 운영 index, 학습, 독립정확도, 배포는 모두 차단 상태입니다.”

추가 상세 근거: [KLHK 문서 ingestion과 학습·배포 Gate](../V42_KLHK_RAG_MLOPS_GATES.md)

## CCKP bbox 수치 도구 추가 1분

“실제 4,209,592바이트 ERA5 CDD NetCDF를 SHA로 고정하고 17개 Range chunk로 취득했습니다. 파일의 CF-1.6과 NETCDF3_CLASSIC, 1951년부터 1980년까지의 climatology를 직접 검사했으며, 개발 bbox의 12,765개 셀을 full-cell 구면 면적가중한 값은 40.91221481742199일입니다. 하지만 인도네시아 행정경계 평균이나 연별·월별 값이 아니며, ERA5 재분석은 독립 ground truth가 아닙니다. live 서비스 등록·학습·배포는 아직 0건입니다.”

추가 상세 근거: [CCKP Indonesia 개발 bbox 수치 도구](../V42_CCKP_INDONESIA_NUMERIC_TOOL.md)

## 최종 통합 상태 추가 1분

“36개 지역·연도 셀은 모두 최소 28개 패치를 갖지만, 실제 paired 공간 피복은 0.976741%, clear 피복은 0.889803%에 불과합니다. CAS에는 기존 로컬 산출물 6,125개 약 3.904GB를 고정했고, CCKP 개발 bbox CDD 평균 40.9122일과 Edge UI 클릭 흐름을 실제 확인했습니다. 모델 adapter와 오케스트레이터는 합성 계약시험을 통과했지만 모델 spec, private hash VectorDB의 의미 품질, 약 99% Sentinel 공간 공백, KLHK native23/license, 독립 정확도, 실제 학습·배포와 public RAG는 미완료입니다. WorldCover 2021은 타연도 정답이 아니며 weak agreement를 independent accuracy로 부르지 않습니다.”

추가 상세 근거: [최종 통합 상태](../V42_FINAL_INTEGRATION_STATUS.md)

## Sentinel 단일 pilot 추가 1분

“East Java 2023의 고정 Sentinel-2 scene 한 건에서 예약, exact asset/window pin, same-scene 6 band와 SCL, bounded Range, 실측 정산을 실제 완료했습니다. 65,536개 pixel은 모두 clear였고 28개 요청에서 7,471,506바이트를 읽었으며 오류와 429는 0이었습니다. 원장 잔액은 1,678,521,030바이트이고 후속 pilot·collector·lock은 0입니다. 하지만 이 관측은 36셀 aggregate에 아직 반영되지 않아 0.976741%는 이전 snapshot입니다. 전체 공간 완료, 예산 충분성, BIG 승인, 독립 정확도, 학습·배포는 여전히 차단 상태입니다.”

추가 상세 근거: [Sentinel 단일 실제 pilot](../V42_SENTINEL_SINGLE_PILOT.md)
