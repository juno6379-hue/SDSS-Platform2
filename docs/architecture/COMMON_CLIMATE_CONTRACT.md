# 공통 기후 계약 1.0

상태: `TESTED_SYNTHETIC`

`services/contracts/climate.py`는 source connector, climate lake, GeoAI feature, Climate RAG가 함께 사용하는 fail-closed 계약이다.

핵심 보장:

- projected 자산은 `model`과 `scenario`가 모두 있어야 한다.
- observed 자산에는 scenario를 붙일 수 없다.
- 취득 시각은 timezone을 포함해야 한다.
- CF 달력 종류와 시간 범위를 검증한다.
- restricted/private 자산은 허용 역할이 필요하다.
- 구조화 기후 질의는 변수와 시작·종료 시각이 필요하다.
- 성공 응답은 최소 하나의 출처·버전·source span 인용이 필요하다.
- Vector RAG 경로는 `numeric_payload`를 반환할 수 없다.

현재 시험은 합성 계약 시험이며 실제 CCKP 수치를 검증한 독립정확도 시험이 아니다.
