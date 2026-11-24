# CCKP Indonesia bbox 수치 도구 실증

기준일 2026-11-24. 실제 원본 취득·파싱·제한 bbox 통계는 **VERIFIED_REAL**이며, 오류/계약 fixture는 **TESTED_SYNTHETIC**이다. 행정경계 국가 평균, 개별 연도 시계열, 독립 정확도, 모델 학습·배포는 수행하지 않았다.

## 1. 국가 URL을 추정하지 않은 실제 경로

기존 connector가 실제 반환한 S3 목록 `services/datahub/connectors/cckp/evidence/era5-cdd-historical-listing-20261124.json`에서 0B folder marker를 제외하고 64MiB 이하 NetCDF 1개를 선택했다. 새로운 `/Indonesia/`, `/IDN/` URL을 만들지 않았다.

```text
s3://wbg-cckp/data/era5-x0.25/cdd/era5-x0.25-historical/
climatology-cdd-annual-max_era5-x0.25_era5-x0.25-historical_climatology_mean_1951-1980.nc
```

파일 전체는 global grid다. Indonesia 부분집합은 별도 bbox 요청의 결과이며 원본을 country object로 바꾸지 않는다. 기존 `plan_download()`의 country-prefix gate는 보존하고, root가 승인한 별도 `global_asset.py`가 기존 `inventory_from_dict/head_object/S3Transport`의 목록·host·TLS·If-Match·bounded primitive를 재사용한다. 공식 문서가 global gridded NetCDF 구조를 설명한다: [World Bank CCKP 원본 문서](https://github.com/worldbank/climateknowledgeportal).

## 2. 전송 실패·명시 재개·중복 재사용

| 항목 | 실측/보존값 |
|---|---|
| 원본 크기 | 4,209,592B |
| S3 ETag | `"89a1fc4164f41e1db1e22e776918d4df"`; SHA256으로 취급하지 않음 |
| 원본 SHA256 | `646fba633f7ca2d4cde8138209deb63b3fa4430bbc46e0be3288e6039f9b01f7` |
| 최초 GET | HEAD 성공 후 body read TimeoutError. 받은 바이트 수 미측정; 예약 4,209,592B 보존 |
| root 승인 후 재개 | 같은 plan/reservation/ETag, If-Match+256KiB Range, 순차17chunk |
| 완료 body | 4,209,592B. 각 chunk 뒤 partial bytes/SHA를 파일로 보존 |
| 보수 누적 | 최초 불확실 예약+재개 body = 8,419,184B, 상한67,108,864B 미만 |
| 재사용 | raw/receipt/seal 검증 후 0HTTP·0B; 실제 no-network transport guard로 확인 |

evidence 경로는 모두 `evidence/cckp_indonesia/`다. `first-transfer-state.json`으로 최초 예약을 보존했고 `transfer-state.json`은 같은 상태·계획의 재개 정보를 이어서 기록했다. 다른 예산/원장을 생성하거나 초기 예약을 환불하지 않았다. `range-progress-001..017.json`, `raw-receipt.json`, `receipt-seal.json`, `reuse-verification.json`이 근거다. HTTP429는 Retry-After를 기록하고 즉시 중지하며 자동 재시도하지 않는다. body 예산이며 HTTP/TLS header 전체 wire byte를 계측한 것은 아니다.

완료 receipt와 raw가 어긋나거나 partial/orphan·stale lock가 있으면 수동 검토로 차단한다. 이 파일 기반 계약은 WORM/분산 트랜잭션·여러 독립 output root를 합친 전역 예산을 구현한 것은 아니다.

## 3. 실제 NetCDF 내부 검사

`netcdf-metadata.json`에 파일을 직접 열어 읽은 전역/변수 속성·좌표·CF 시간 정보를 보존했다.

- 실제 저장형식 `NETCDF3_CLASSIC`. 속성의 HDF5/compression 설명만 믿지 않고 파일 형식을 읽었다. netCDF4 backend가 필요하며 h5netcdf만으로 이 파일을 읽을 수 없다.
- `Conventions=CF-1.6`, `time.calendar=gregorian`, `time.units=days since 1850-01-01 00:00:00`, time1/lat721/lon1440.
- `wb_period_label`과 `time.climatology_period` 모두 `1951-1980`이다. 파일명만으로 기간을 추정하지 않았다.
- `wb_model_label=era5`, `wb_collection_label=era5-x0.25`, `wb_scenario_label=historical`, `wb_variable_label=cdd`.
- 수치 변수 `climatology-cdd-annual-max`, units days, 설명은 연간 건조일(<1mm)의 최장 연속 길이 지수다. variable의 `climatoloyg_calculation=max`, 전역 `wb_statistic_label=max`, `wb_percentile_label=mean`을 그대로 보존하며 별도 연간·월간 값을 역산하지 않는다.
- lat/lon 1D·유한·단조·등간격과 degrees_north/degrees_east, 실제0.25° 간격·셀 bounds를 검사했다. FillValue/NaN은 유효한0으로 바꾸지 않는다.

time 한 개의 climatology이므로 2010년 값이나 부분 기간 평균을 요청하면 `CLIMATOLOGY_PERIOD_MISMATCH_NO_ANNUAL_VALUES_INFERRED`다. calendar/단위/좌표/기간이 미확인되면 null/BLOCKED이며 파일명·문서 유사도로 채우지 않는다.

## 4. 라이선스·출처의 인정 범위

NetCDF 안에는 license 속성이 없다. [공식 World Bank ERA5 카탈로그](https://datacatalog.worldbank.org/search/dataset/0065626/climate-change-knowledge-portal-observed-climate-data-era5-0-25-degree)에서 Public/CC-BY-4.0을 확인했고 `license-evidence.json`에 조회 URI·짧은 표기·검증 방법을 고정했다. 그 evidence SHA는 `cddad402f01f95fac8029104f4b4ba777ae09adcf4f6a719d641a80425949a89`다.

코드/문서 저장소의 MPL을 데이터 라이선스로 전파하지 않았다. ECMWF/Copernicus Climate Data Store와 World Bank CCKP 출처를 함께 인용한다. 파일 license가 별도로 충돌하거나 공식 카탈로그 근거가 없거나 달라지면 numeric publish를 차단한다. 이 evidence는 내부 출처 검토 기록이며 법적 자문·기관 통계 승인 또는 독립 정답 인증은 아니다.

ERA5는 이 카탈로그의 observed 데이터 계열에 해당하는 **재분석**이다. 모델 입력/수치 결과에는 `data_role=ERA5_REANALYSIS`, canonical scenario=not_applicable와 원본 scenario=historical을 함께 보존한다. 재분석을 독립 현장 ground truth로 부르지 않는다.

## 5. 실제 bbox 결과와 한계

`query-request.json`은 개발용 bbox `[95,-11,141,6]`, geography_id `IDN_BBOX_DEVELOPMENT`, 1951-01-01~1980-12-31, cdd/observed/era5/not_applicable/days를 명시한다.

`numeric-result-validated.json`의 결과:

| 항목 | 값 |
|---|---|
| 계산 | 셀 중심이 bbox 안인 native grid의 full-cell 구면 면적 가중 평균 |
| 격자 | 69×185, 유효12,765 / 전체12,765 / masked0 |
| 값 | **40.91221481742199 days** |
| calendar | standard (원본 gregorian alias) |
| 해상도 | 0.25° 보존 |
| 행정경계 국가 평균 | false |
| 독립 정확도·학습·curated 등록 | false |

이 값은 **제공된 CDD climatology 필드의 개발 bbox 통계**다. 해양과 이웃 국가 영역이 포함될 수 있으며 인도네시아 행정경계·육지 평균이 아니다. bbox 가장자리와 교차하는 셀의 부분 면적 clip도 수행하지 않는다. 실제 lat_bnds/lon_bnds를 이용한 구면 cell 면적 비례 가중이며 ellipsoid/권위 polygon 통계가 아니다. 0.25° 자료를 Sentinel-2 10m 관측으로 표시하지 않는다.

실제 선택된 12,765개 cell의 위도·경도·CDD 값은 `indonesia-bbox-values.csv`에 별도 보존했다. `subset-provenance.json`이 원본/CSV SHA와 기간·단위·인용·행정경계 subset=false를 연결한다. 이 CSV를 공식 Indonesia 국가 통계나 학습용 curated feature로 자동 등록하지 않았다.

## 6. `climate.query` 계약과 실행

구현은 `services/climate_query/{models,numeric,global_asset,__main__}.py`다. 필수 요청은 geography/time/variable/observed_or_projected/model/scenario/aggregation/unit이다. 임의 source URL/로컬 경로·RAG 숫자·추가 필드는 사용자 schema가 받지 않는다. 원본/receipt/license 경로는 승인된 서버 설정으로 공급해야 한다.

숫자는 고정 raw SHA와 receipt seal, 내부 CF 메타데이터·요청 의미·라이선스 evidence pin이 일치하고 유효 grid 값이 있을 때만 반환한다. canonical result는 value/unit/기간/geography/model/scenario/provenance/citations/trace/경고를 포함한다. blocked는 value=null이다. Vector RAG는 이 값을 생성·보간하지 않고 실행 요청과 실제 결과 근거를 전달하는 역할만 한다.

```powershell
cd E:\SDSS-Platform2
python -B -m services.climate_query contract
python -B -m services.climate_query download --listing services/datahub/connectors/cckp/evidence/era5-cdd-historical-listing-20261124.json --output evidence/cckp_indonesia --execute
python -B -m services.climate_query query --raw evidence/cckp_indonesia/global-asset.nc --receipt evidence/cckp_indonesia/raw-receipt.json --request evidence/cckp_indonesia/query-request.json --license-evidence evidence/cckp_indonesia/license-evidence.json --license-evidence-sha256 cddad402f01f95fac8029104f4b4ba777ae09adcf4f6a719d641a80425949a89 --output evidence/cckp_indonesia/numeric-result-NEW.json
python -B -m unittest discover -s tests/climate_query -v
```

download은 이미 완료된 검증 원본을 재사용한다. 새 상태에서 execute 없이 부르면 plan-only다. `--reviewed-range-retry`는 명시적으로 검토·승인된 최초 실패의 단1회 재개에만 사용한다. 동일 출력 증거 JSON은 덮지 않으며 재현 query 출력은 새 파일명을 쓴다.

root가 optional climate 의존성에 netCDF4/cftime 등을 선언했다. 실제 설치·파싱 환경은 netCDF4 1.7.5.1.post1, cftime1.6.6.1, numpy2.4.6이다. 실제 HDF5/netCDF4 자산이나 여러 모델/다중 시간축은 이 한 파일 실증으로 검증됐다고 주장하지 않는다.

## 7. 시험·후속 경계

합성과 실원본 read-only 재현을 별도 파일로 나눴다. `test_numeric.py`/`test_global_asset.py`는 임시 NetCDF·fake transport로 schema·period/model/scenario/unit·CF누락·hash/license·FillValue·Range partial·재사용·429 차단을 시험한다. `test_real_evidence.py`는 저장된 실제4.2MB 원본의 형식/CF/기간/SHA/12,765셀/수치와 no-HTTP 재사용을 확인한다. 원본이 없는 환경은 real evidence 시험을 명시적으로 SKIP한다.

최종 결과는 **14 PASS / 4.395초**(합성12, 실원본 read-only2)이며 소유 코드·시험의 Ruff 검사도 PASS다. `test-summary.json`에 실행 명령·구분을, `evidence-manifest.json`에 실제 evidence 전 파일의 크기/SHA를 고정했다. manifest 자체 SHA는 `8b63859d7ba01a0bf51a706ee1d4bfff357e5946666eae3a51e5cbd49e8196e5`다. 처음 GET 실패와 후속 승인 재개를 하나의 성공만으로 덮지 않았다.

이 도구를 HTTP/RAG 서비스에 실제 등록·배포한 것은 아니다. 공식 Indonesia polygon과 면적 weighting, 다양한 변수·기간·모델·시나리오 파일, 부모 lineage/권한 서비스 및 실제 numeric QC 표준화는 후속 Gate다. CDD/days는 이번 지수 전용 도구에서 읽었으며 기존 lake의 tas/pr 단위표를 임의 수정하거나 curated/모델 학습 gate를 해제하지 않았다. 모델 학습·독립 OA/F1/mIoU·운영 배포는0이다.
