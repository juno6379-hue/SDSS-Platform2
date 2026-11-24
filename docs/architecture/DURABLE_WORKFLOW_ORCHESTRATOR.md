# 재개 가능한 workflow 오케스트레이터

상태: `TESTED_SYNTHETIC`

`services/orchestration/workflow.py`는 source discovery부터 배포 Gate까지 증거를 연결하기 위한 최소 durable runner다.

## 보장

- workflow plan과 입력 fingerprint가 바뀌면 기존 state를 재사용하지 않는다.
- 등록된 Python adapter만 실행하며 JSON에서 임의 shell command를 받지 않는다.
- 실행 전 preflight는 파일이나 네트워크를 변경하지 않는다.
- 각 단계 시작·완료·차단·실패를 UTF-8 JSON으로 atomic 기록한다.
- 성공한 단계는 같은 plan에서 재실행하지 않는다.
- dependency가 성공하지 않으면 downstream을 실행하지 않는다.
- 동시 실행 lock을 사용하고 종료 시 lock을 제거한다.
- evidence SHA-256과 blocker를 단계별로 보존한다.

## 후속 adapter

CCKP, KLHK, One Map/Sentinel, RAG ingestion, climate query, MLOps Gate의 adapter를 등록하는 통합 API는 UI/API 담당 작업에서 연결한다. 실제 학습·배포 adapter는 데이터와 독립정확도 Gate가 충족되기 전까지 등록하지 않는다.
