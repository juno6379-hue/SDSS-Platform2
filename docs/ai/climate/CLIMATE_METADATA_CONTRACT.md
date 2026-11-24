# Climate Asset / Lineage 메타데이터 계약

상태: **TESTED_SYNTHETIC**. 기준일 2026-11-24. Pydantic 2.13.5에서 합성 fixture로 확인했다. 실제 NetCDF, CCKP 국가별 수치, 독립 과학검증 또는 운영 승인은 확인하지 않았다. V42의 CLIM-01/04 계약과 CLIM-05 입력을 구현한다.

## 1. 구현과 공통 계약 관계

구현은 `services/datahub/climate/models.py`다. `ClimateAsset`, `CFTimeCoverage`, `Grid`, `SpatialCoverage`, `LineageRef`, `AccessPolicy`는 Pydantic v2 `BaseModel`이며 `extra=forbid`, `frozen=True`다. JSON 왕복과 `ClimateAsset.model_json_schema()`를 지원한다. 공통 파일·루트 설정은 수정하지 않았다. 아래 스키마를 공통 패키지로 승격하거나 이름을 매핑하는 결정은 root가 담당한다.

| 필드 | 의미·검사 |
|---|---|
| source_id, dataset_id, version | 고정 식별자. 경로 구분자·Windows 장치명·latest/current/unknown 금지 |
| source_uri | query/fragment/사용자정보 없는 명시적 HTTPS 또는 S3 원천 URI. URI 존재만으로 기관 권위를 인증하지 않음 |
| sha256 | 실제 내용 SHA를 넣기 위한 소문자 64자리 계약. ETag와 다름; 이 모델 자체가 blob을 읽어 검증하지는 않음 |
| license | 비어 있거나 unknown/TBD이면 거부. 사용 허가의 법률 검토를 대신하지 않음 |
| acquired_at | timezone-aware 실제 취득 시각 |
| available_at | 해당 버전이 사용 가능해진 시각. acquired_at보다 과거이면 availability_evidence_uri와 availability_evidence_sha256 필수 |
| observed_or_projected | observed 또는 projected. 모형 산출을 관측으로 추정하지 않음 |
| model, scenario | 명시적 관측 제품/모델. observed의 scenario는 not_applicable. projected는 실제 모델명과 허용 시나리오 필요 |
| variable, unit, temporal_method | 변수·단위·통계 의미를 함께 보존. QC의 허용 조합 외에는 차단 |
| spatial_coverage | bbox=[west,south,east,north], 유한한 수치와 비어 있지 않은 순서 |
| time_coverage | calendar/start/end/time_units/frequency. 날짜는 CF 달력에 속하는 문자열 |
| grid | resolution_x/y, width/height, unit, layout, row_order, column_order. shape×resolution과 bbox가 일치해야 함 |
| crs | 현재 EPSG:4326/degrees 또는 EPSG:6933/m만 수용. 다른 CRS는 명시적 검증 adapter 필요 |
| derived_from | dataset_id/version/sha256/role의 고정 부모 참조 목록. 동일 id/version 자기참조 금지 |
| access | public 또는 restricted. restricted는 allowed_principals 필수. 실제 인증은 별도 서비스 책임 |
| trace_id | 호출·출처 추적 식별자 |

Grid는 `layout=rectilinear_cell_bounds`, `column_order=west_to_east`, `row_order=north_to_south|south_to_north`를 명시한다. curvilinear/불규칙·회전 격자, dateline crossing 및 0~360 경도 wrap을 묵시 처리하지 않는다.

전망 시나리오는 historical, ssp126/245/370/585, rcp26/45/60/85다. `historical`도 모형 역사실험이면 projected로 유지한다. 공급자의 다른 명칭을 자동 추측하지 말고 검토된 매핑 adapter를 별도로 둔다.

## 2. CF 달력과 날짜 정책

`calendars.py`는 standard/gregorian, proleptic_gregorian, 360_day, noleap/365_day, all_leap/366_day, julian을 처리한다. 360_day의 월말30일과 noleap의 2월28일을 실제 달력 규칙으로 검사하며 Gregorian datetime으로 강제 변환하지 않는다.

이 구현은 **일 단위·연도1~9999** 범위다. standard의 1583년 이전, year0/음수, none/custom calendar, UTC/TAI leap-second 시각, sub-day decoding은 지원하지 않고 차단한다. 이는 CF 전체의 제한이 아니라 이 서비스의 보수적 지원 범위다. time_units는 days/hours/seconds since YYYY-MM-DD와 선택적 00:00:00만 검증하며 실제 NetCDF 시간축 디코더 구현을 의미하지 않는다. months/years since는 추정하지 않는다.

근거: [CF 1.11 시간 좌표와 달력 규약](https://cfconventions.org/Data/cf-documents/cf-conventions-1.11/cf-conventions.html). 코드의 일 단위 정책과 최신 CF 규격 전체 지원 여부는 구분한다.

## 3. 원천 RAW receipt와 ClimateAsset 분리

CCKP connector의 `cckp-raw-receipt/1.0`, `RAW_NOT_QC_VALIDATED`는 ClimateAsset이 아니다. 실제 S3 목록을 읽거나 원본을 받았어도 calendar/unit/model/scenario/observed_or_projected/grid/crs가 None이면 그대로 보존한다.

`qc.raw_receipt_gate()`는 `CLIM_METADATA_MISSING`과 누락 필드를 반환하고 feature 생성을 금지한다. 모두 채워져 있어도 명시적 정규화 adapter 없이 `EXPLICIT_NORMALIZATION_ADAPTER_REQUIRED`다. ERA5 폴더 이름, 국가 페이지, 객체 이름만으로 관측·단위·달력·국가 범위를 추론하지 않는다.

`check_asset()`가 metadata_valid=true여도 numeric_values_verified=false다. 구조 검증을 원본 수치·좌표축·출처 인증과 혼동하지 않는다.

## 4. 시험과 사용

```python
from services.datahub.climate import ClimateAsset, check_asset
asset = ClimateAsset.model_validate_json(metadata_json)
qc = check_asset(asset)
schema = ClimateAsset.model_json_schema()
```

합성 metadata 예시는 `tests/climate_lake/fixtures/asset.json`이다. example.invalid와 synthetic 식별자를 사용하며 실제 기관 자료로 등록하지 않는다. 명령 `python -m unittest discover -s tests/climate_lake -v`: **12 PASS, 0.112초**. JSON 왕복·누락/추가 필드·시간대·제품 버전·URI·grid·projection·CF 날짜·RAW receipt·단위·경로를 확인했다.

실제 메타데이터 adapter, CF reader/cftime 대조, blob hash 검증, 라이선스/권한 검토와 수치 QC가 다음 Gate다. publication/availability 근거 URI·SHA도 제출자 선언을 공인 인증한 것은 아니며 실제 원본을 검증해야 한다.
