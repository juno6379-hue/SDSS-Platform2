# SDSS-Platform2

GreenBlue v4.2 설계를 바탕으로 One Map·KLHK·World Bank CCKP·기후 Data Lake·Vector RAG·GeoAI를 통합하는 새 구현 저장소입니다.

## 현재 범위

- CCKP 공식 자산의 안전한 탐색과 불변 원본·receipt 저장
- CF 메타데이터, 달력, 단위, 관측/전망 구분 검증
- 행정경계·시간 기준 기후 feature 생성과 누출 방지
- 출처·버전·권한·공간·시간을 보존하는 온톨로지/지식그래프
- 다국어(한국어·인도네시아어·영어) hybrid RAG와 인용 검증
- 정량 질의를 구조화 기후 도구로 강제 라우팅

실행 계획과 담당은 [v4.2 실행 계획](docs/architecture/V42_EXECUTION_PLAN.md)을 참조합니다.

## 개발 시작

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

대용량 원본은 Git에 커밋하지 않으며 `data/raw/{provider}/{collection}/{source_version}/`에 receipt와 함께 저장합니다.
