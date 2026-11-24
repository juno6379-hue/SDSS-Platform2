# SDSS-Platform2

GreenBlue v4.2 설계를 바탕으로 One Map·KLHK·World Bank CCKP·기후 Data Lake·Vector RAG·GeoAI를 통합하는 새 구현 저장소입니다.

## 현재 범위

- CCKP 공식 자산의 안전한 탐색과 불변 원본·receipt 저장
- CF 메타데이터, 달력, 단위, 관측/전망 구분 검증
- 행정경계·시간 기준 기후 feature 생성과 누출 방지
- 출처·버전·권한·공간·시간을 보존하는 온톨로지/지식그래프
- 다국어(한국어·인도네시아어·영어) hybrid RAG와 인용 검증
- 정량 질의를 구조화 기후 도구로 강제 라우팅

## 2026-11-24 검증 상태

- One Map 6개 주 x 2020~2025년 36셀을 실제 감사했다. 6밴드와 같은 장면 SCL의 동시 공간피복은 `0.976741%`, clear 피복은 `0.889803%`이므로 전체 수집은 완료되지 않았다.
- 기존 검증 자료는 SHA 기반 CAS로 `6,125`개 객체, `3,904,601,927`바이트를 `data/raw/migrated/{sha256}`에 독립 복사했다. 원본 저장소와 기존 manifest는 변경하지 않았다.
- 공유 전역원장 예약·정산과 고정 scene/asset/window, 제한 Range 전송을 구현해 East Java 2023 한 창의 동일 장면 6밴드+SCL 실제 pilot을 완료했다. clear 65,536/65,536, 본문 7,471,506바이트, 28요청, 오류·관측된 HTTP 429는 0건이다.
- 정산 후 잔여 예산은 `1,678,521,030`바이트다. pilot 뒤 36셀 공간피복 aggregate는 아직 재감사하지 않았으므로 위 `0.976741%`는 pilot 전 snapshot이며 전체 수집 완료를 뜻하지 않는다.
- World Bank CCKP ERA5 CDD 표본은 Indonesia 개발 bbox에서 면적가중 평균 `40.9122148174 days`로 재현했다. 공식 행정경계 평균, 미래 전망 또는 독립 현장 정답이 아니다.
- KLHK 연차 서비스의 접근·메타데이터는 확인했지만 native 23개 클래스 domain과 라이선스는 아직 검증되지 않았다.
- 기후 보고서 로컬 검토 인덱스는 7문서/122청크다. 현재 hash embedding은 품질 미검증이고 `data_steward` 전용이며 공개 검색은 차단한다.
- LCLUC·기후·RAG 전문모델 계약은 구현했지만 실제 학습, 독립 정확도, 사람 승인, 운영 배포는 모두 차단 상태다.

상세 근거는 [One Map/Sentinel 완전성](docs/data/ONEMAP_SENTINEL_COMPLETENESS.md), [CCKP 수치 도구](docs/ai/climate/CCKP_INDONESIA_NUMERIC_TOOL.md), [VectorDB](docs/architecture/CLIMATE_REPORT_VECTOR_DB.md), [API/UI E2E](docs/ui/API_UI_E2E.md)를 참조한다.

실행 계획과 담당은 [v4.2 실행 계획](docs/architecture/V42_EXECUTION_PLAN.md)을 참조합니다.

## 개발 시작

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

로컬 증거 대시보드는 다음과 같이 실행한다.

```powershell
python -m uvicorn services.api.app:app --host 127.0.0.1 --port 8010
```

브라우저에서 `http://127.0.0.1:8010/`을 연다. 이 화면은 수집기·학습·배포를 시작하지 않는 읽기 전용 evidence UI다.

대용량 원본은 Git에 커밋하지 않으며 `data/raw/{provider}/{collection}/{source_version}/`에 receipt와 함께 저장합니다.
