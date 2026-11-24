# 기후변화 보고서 VectorDB

상태: `TESTED_SYNTHETIC`

## 저장 범위

- CCKP·KLHK·정책·방법론 보고서의 불변 원문 receipt
- 출처 span이 검증된 chunk
- source/dataset/version/SHA/authority/license/ACL/validity
- geography·공간범위·기간·variable·scenario·model
- embedding model과 vector, lexical index, ontology/KG sidecar

기후 수치 배열과 통계 결과는 VectorDB의 의미 유사도에서 생성하지 않는다. 수치 질문은 검증된 `climate.query`로 라우팅하고 VectorDB는 방법론·출처·정책 문맥과 인용만 제공한다.

## 구현

- `services/vectorstore/sqlite_store.py`: UI와 로컬 통합시험을 위한 영속 SQLite hybrid store
- `services/vectorstore/pgvector_schema.sql`: 운영 PostgreSQL 17 + PostGIS + pgvector 계약
- ACL은 vector/lexical scoring 전에 적용한다.
- chunk id의 내용이 바뀌면 overwrite하지 않고 `IMMUTABLE_CHUNK_ID_DRIFT`로 차단한다.
- source span, document SHA, version, authority, license를 검색 결과에 포함한다.

SQLite vector는 운영 semantic 품질을 입증하지 않는다. 운영 전에는 실제 embedding 모델 고정, golden query 평가, pgvector migration, 인증 principal, backup/restore 및 권한시험이 필요하다.
