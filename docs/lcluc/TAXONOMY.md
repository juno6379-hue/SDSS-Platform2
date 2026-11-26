# LCLUC 분류체계와 분석 대응표

## 검증 범위

- **분류사전 VERIFIED_REAL**. 2026-11-25 KST에 인도네시아 산림부 SIGAP 자료사전을 소량 조회해 23개 코드·명칭을 추출했다. 공식 장관 결정 SK 398/2024 부속서 I의 C1018AR 도메인과 기존 커넥터의 `KLHK_CODES`를 대조했다. 취득한 사전 메타데이터는 444,011바이트이며 수신 본문의 SHA-256은 `abd45de2d17d9630e5b8cb72bcb1f2bc95566928c3a2ab203f149384559f81d5`다. [SIGAP 자료사전](https://sigap.kehutanan.go.id/tema-kamus/575) · [SK 398/2024 부속서 I](https://bpkh2.planologi.kehutanan.go.id/wp-content/uploads/2025/08/SK-398-Tahun-2024-tentang-Standar-DG-dan-IGT-Lingkup-KLHK.pdf)
- **연차 지도 운영 승인 BLOCKED**. 사전의 코드와 연차 레이어의 원본 속성 도메인, 해당년도의 원본 바이트, 라이선스 및 기관 승인 각각에 증거가 필요하다. 기존 2024·2025 메타데이터에는 렌더러 심볼 25항목이 있으며 두 레이어의 23개 원본 코드 도메인과 재사용 권리가 확인되지 않았다. [기관 원본 인계 기록](../data/INSTITUTION_SOURCE_HANDOFF.md)
- **검증 로직 TESTED_SYNTHETIC**. 원본 구조가 계약에 합치하는 시험 데이터에서도 운영 승인·사용권·다운로드 검증 플래그는 차단 상태로 유지한다.

## 분류 버전과 레지스트리

| ID | 릴리스 | 코드 범위·NoData | 상태 |
|---|---|---|---|
| `klhk-23` | `sk-398-2024-c1018ar-v1` | 23개 희소 정수 코드. 서비스 내부 NoData 예약값 65535 | 공식 사전 확인. 연차 자료 적용 승인 대기 |
| `legacy-9` | `sdss-worldcover-grouped-v1` | 기존 WorldCover 묶음 분류의 0–8. NoData 255 | 기존 코드의 클래스 순서 확인 |
| `klhk-23-to-legacy-9` | `provisional-conservative-v1` | 23개 원본 코드 각각에 목표 코드 또는 명시적 제외가 지정됨 | 분석 대응표 제안. 운영 적용 승인 대기 |

[KLHK 코드표](../../services/lcluc/taxonomies/klhk-23.json) · [기존 9클래스 코드표](../../services/lcluc/taxonomies/legacy-9.json) · [잠정 대응표](../../services/lcluc/taxonomies/klhk-23-to-legacy-9.json)

공식 코드 2500은 구름을 기록한다. `classes`와 `codes`는 이 코드를 보존하고, `qa_codes`로 분류한다. `thematic_codes`에는 실제 토지피복 22개가 들어간다. 학습과 변화 계산에서는 입력에서 구조적 NoData 및 구름을 각각 제외한다. 레거시 코드 0은 수역이며 유효하다.

`analysis_groups`는 프로젝트의 명시적 통계 집합을 제공한다. `natural_forest`는 일차·이차 건조지림, 맹그로브림, 습지림을 포함한다. `forest`는 여기에 조림지 2006을 더한다. `settlement`는 정착지와 이주 정착지를 포함한다. `built_up`은 정착지 집합에 공항·항만을 포함하는 넓은 집계 정의다. 이 집합을 사용한 결과에는 그룹 ID를 고정하며, 공항·항만 내부 면적의 포장 비율을 별도로 측정한다. [KLHK 분류 및 IPCC 집계 구분](https://line.bsilhk.menlhk.go.id/siklus/assets_style/image/buku/e91d113d8f75a081c35bf56e21a874c5.pdf)

## 코드 사용

```python
import numpy as np

from services.lcluc.taxonomy import (
    apply_crosswalk,
    load_crosswalk,
    load_taxonomy,
    validate_class_codes,
)

definition = load_taxonomy("klhk-23")
pixels = np.array([2001, 2500, 65535], dtype=np.uint16)
present = validate_class_codes(pixels, definition, nodata=65535)
thematic = present & ~np.isin(pixels, definition.qa_codes)

proposal = load_crosswalk("klhk-23-to-legacy-9")
experimental = apply_crosswalk(
    pixels, proposal, source_nodata=65535, allow_provisional=True
)
```

- 분류 파일과 대응표는 코드에 등록된 SHA-256을 통과해야 로드한다. 호출자는 `expected_sha256`에 데이터·모델 매니페스트가 요구하는 핀을 전달할 수 있다. 대응표는 양쪽 분류 파일의 SHA에도 결속한다.
- 값 검증은 명시적 NoData와 배열 마스크를 인정한다. 미등록 값, 유효 셀의 NaN·소수 코드, 실제 분류 코드와 충돌하는 NoData는 차단한다. 실제 원본의 NoData는 원본 매니페스트 또는 래스터 마스크에서 읽어 전달한다.
- 잠정 대응표는 11개 원본 코드를 구분된 목표 코드로 대응하고 12개를 제외한다. 혼합농경지·양식 연못·습지 식생 등 의미가 겹치는 경계와 구름의 제외를 보존한다. `allow_provisional=True`는 격리 분석의 명시적 선택이다. `require_approved=True`는 현재 릴리스에서 차단된다.
- `inspect_klhk_annual_metadata(payload, year)`는 기존 커넥터의 필드 도메인과 공식 코드별 명칭을 함께 검사하고, 수집 승인 여부는 `approval_status`에 따로 기록한다.
- 동일 코드·분류체계의 두 시점으로 변화량을 계산한다. 타 제품으로 분류를 변환할 때는 대응표 해시와 각 시점의 제외 면적도 결과에 기록한다. WorldCover 2021 참조 일치도와 동년 독립 검증은 별도 지표로 관리한다.

## 시험

```powershell
python -m pytest tests/lcluc/test_taxonomy.py -q
```

고정 파일 무결성, 코드와 역할, QA와 NoData, 대응표 승인 차단, 연차 레이어 속성 도메인과 렌더러의 구분을 검사한다.
