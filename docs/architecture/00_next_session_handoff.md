# 다음 세션 인계

검증 기준 시각: 2026-11-24 KST

## 완료된 범위

- One Map 6개 주 x 6개 연도 36셀의 실제 6밴드+동일 장면 SCL 공간감사와 exact 누락 큐 생성
- 기존 검증 자료의 SHA CAS 선별 이전과 원본·전역원장 불변 검증
- CCKP Indonesia bbox 수치 도구와 실제 NetCDF 표본 검증
- KLHK 연차 connector·실제 메타데이터 취득과 fail-closed 스키마/라이선스 판정
- 기후 보고서 ingestion·KG sidecar·로컬 private VectorDB와 PostgreSQL/PostGIS/pgvector 운영 스키마
- 세 전문모델 계약, 학습·독립정확도·배포 Gate, 내구성 workflow 상태 계약
- FastAPI와 same-origin UI 연결, API 시험, 실제 Edge 기능별 클릭 확인
- 공유 전역원장 adapter, 결정적 scene/asset/window pin planner, 제한 Range 전송기 구현과 단일 실제 pilot 완료

## 핵심 고정 근거

- `evidence/onemap_sentinel/handoff-summary-20261124.json`
- `evidence/onemap_sentinel/held-audit-20261124/completeness.json`
- `evidence/onemap_sentinel/migration-receipt-20261124.json`
- `evidence/cckp_indonesia/numeric-result-validated.json`
- `evidence/klhk_rag/verification-20261124.json`
- `evidence/vectorstore/climate-report-index-pinned.json`
- `evidence/models/readiness.json`
- `services/api/evidence-lock.json`
- `evidence/onemap_sentinel/pilot-unit-20261124/run-01/result.json`
- `evidence/onemap_sentinel/pilot-unit-20261124/incoming-observation-v2.json`
- `evidence/onemap_sentinel/pilot-unit-20261124/postflight-integrity.json`

대형 `exact-missing-queue.geojson`과 WKB checkpoint는 로컬 생성물이며 Git에서 제외한다. committed completeness 보고서가 해당 큐의 SHA-256, 크기, feature 수를 고정한다.

## 즉시 이어갈 작업

1. 완료된 East Java 2023 단일 pilot을 API/UI와 이해자료에 고정한다. clear 65,536/65,536, 본문 7,471,506바이트, 28요청, 오류·관측 429 0건이다.
2. 현재 ledger SHA `b257db2925e5c4eac99081c5539216314c972d49dd6741f38f5780da7dd25de1`와 잔액 1,678,521,030바이트를 다음 실행 전 다시 검증한다.
3. pilot 뒤 36셀 공간피복 aggregate를 재감사한다. 기존 0.976741%는 pilot 전 snapshot이며 1건 성공을 6개 주 전체 완료로 표현하지 않는다.
4. 추가 수집은 BIG 승인·공간피복 목표·예산 승인을 받은 뒤 동일 공유 원장 adapter로만 수행한다.
5. KLHK native 23-class·라이선스와 독립 정답이 확보되기 전 실제 학습·승격·배포는 금지한다.

## 실행

```powershell
python -m uvicorn services.api.app:app --host 127.0.0.1 --port 8010
python -X utf8 -m pytest -o addopts= -q
```

UI: `http://127.0.0.1:8010/`
