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
