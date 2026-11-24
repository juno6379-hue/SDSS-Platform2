# 이해자료 변경 이력

## 2026-11-24 — v4.2 공통 기후 계약·Climate RAG 초기 이해패키지

- `V42_CLIMATE_FOUNDATION_AND_RAG.md` 신규 작성
- `INDEX.md`, `GLOSSARY_KO_EN.md`, 발표 대본, FAQ 신규 작성
- contract 5개 + RAG 18개 = 23개 합성 시험 통과 근거 반영
- 실제 CCKP 수치·공식 문서 인덱스·기관 인증·semantic embedding·API/UI는 미검증/차단으로 구분
- WorldCover 약한 참조와 독립 정확도, authority 문자열 결속과 실제 기관 승인을 분리

## 2026-11-24 — CCKP source·climate lake·feature planner 인계 반영

- 실제 CCKP 검증 범위를 S3 목록 5페이지 5,289B와 NetCDF HEAD 1건으로 제한해 기록
- NetCDF 본문 0B, Indonesia 식별자/국가 prefix 미확인, 실제 download plan `BLOCKED` 반영
- CCKP source 합성 24 PASS와 receipt·재개·예산·429 fail-closed 계약 설명 추가
- climate lake 12 PASS와 feature planner 12 PASS 반영
- 실제 join·numeric feature·학습·배포 0건, `execution_started=false`, `numeric_features=null` 명시
- 전체 합성 증거를 contract/RAG 23 + source 24 + lake/feature 24 = 71 PASS로 갱신

## 2026-11-24 — KLHK/RAG ingestion·MLOps Gate 반영

- `V42_KLHK_RAG_MLOPS_GATES.md` 신규 작성
- `VERIFIED_REAL` 범위를 metadata 원본 7개·122 span·381,676B·raw SHA mismatch 0으로 제한
- KLHK 2024/2025 renderer 25항목과 native 23-class domain·license 미확인을 분리
- 실제 문서 운영 index 게시 0, quantitative RAG answer 0, 기관 authority 미인증 명시
- ingestion 신규 11 + 기존 RAG 18 = 29, MLOps 6 합성 PASS 반영
- WorldCover/KLHK 약한 참조와 독립 ground truth, 합성 READY와 실제 학습·배포를 분리

## 2026-11-24 — CCKP Indonesia 개발 bbox 수치 도구 반영

- `V42_CCKP_INDONESIA_NUMERIC_TOOL.md` 신규 작성
- 4,209,592B 원본 SHA pin, 승인된 Range 17 chunk 재개, `NETCDF3_CLASSIC`·CF-1.6 검증 반영
- bbox CSV 12,765행과 1951–1980 제공 CDD climatology 구면가중 평균 40.91221481742199 days 기록
- 합성 12 + 실원본 read-only 재현 2 = 14 PASS 반영
- 인도네시아 행정경계 평균·연별/월별 시계열·독립 ground truth가 아님을 명시
- HTTP/RAG live 등록, curated 등록, 학습, 배포 0건을 분리

## 2026-11-24 — One Map·Sentinel·UI·모델·워크플로 최종 통합 인계 반영

- `V42_FINAL_INTEGRATION_STATUS.md` 신규 작성
- Sentinel 36/36 최소 수량 감사와 paired 0.976741%·clear 0.889803% 공간 피복을 분리
- 약 99% 공간 공백, reservation adapter와 exact scene/asset/window pin 부재를 `BLOCKED`로 명시
- 로컬 CAS 6,125객체·3,904,601,927B 이관과 원격 download/write 0건 반영
- 실제 Edge 클릭 검증과 API 11 PASS·Playwright 3 SKIP을 서로 다른 증거로 기록
- 모델 adapter 14 PASS와 오케스트레이터 5개 합성 계약시험을 `TESTED_SYNTHETIC`으로 반영
- 모델 spec과 private `synthetic-hash-64-v1` VectorDB 의미 품질을 `IMPLEMENTED_UNVERIFIED`로 구분
- KLHK native23/license, 독립 ground truth/accuracy, 실제 학습·배포, public RAG를 `BLOCKED`로 유지
- WorldCover 2021은 타연도 정답이 아니며 weak agreement와 independent accuracy가 다름을 재강조
- 진행 중 data follow-up adapter는 완료 범위에서 제외

## 2026-11-24 — East Java 2023 Sentinel 단일 실제 pilot 반영

- `V42_SENTINEL_SINGLE_PILOT.md` 신규 작성
- 고정 scene의 same-scene B02·B03·B04·B08·B11·B12+SCL 및 clear 65,536/65,536를 `VERIFIED_REAL`로 반영
- 28개 원격 요청·본문 7,471,506B·오류 0·관측 429 0 기록
- ledger SHA `8e98...aa44a`→`b257...25de1`, 잔액 1,678,521,030B와 후속 pilot·collector·locks 0 반영
- 기존 reservation/scene pin 미구현 설명을 단일 pilot 경로 구현·실행 완료로 정정
- pilot이 36셀 aggregate에 미반영되어 0.976741%는 이전 snapshot임을 명시
- 전체 공간 완료·전체 예산 충분성·BIG 승인·독립 정확도·학습·배포는 `BLOCKED` 유지
- WorldCover 2021 타연도 ground truth 금지와 weak agreement/independent accuracy 분리 유지
