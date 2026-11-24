# Climate Data Lake와 시공간 Feature 계획

상태: **TESTED_SYNTHETIC / 실제 자료 실행 BLOCKED**. 기준일 2026-11-24. CLIM-03의 경로·curated 진입 계약, CLIM-04의 메타데이터/단위 검사, CLIM-05의 계획을 구현했다. RAW 다운로드·receipt 저장은 source 담당 구현이며 여기서 복제하거나 대량 다운로드하지 않았다.

## 1. RAW → staging → curated

`services/datahub/climate/lake.py`의 `lake_paths(asset, lake_root, extension)`은 다음 경로를 계산하며 파일을 만들지 않는다.

```text
raw/{source_id}/{dataset_id}/{version}/{sha256}/asset.nc
raw/{source_id}/{dataset_id}/{version}/{sha256}/receipt.json
staging/{source_id}/{dataset_id}/{version}/{sha256}/qc.json
curated/{source_id}/{dataset_id}/{version}/{sha256}/asset.nc
```

확장자는 nc/parquet/json만 허용하고 root 밖으로 resolve되는 경로를 거부한다. 새 버전/파생 수치에는 새 asset SHA와 부모 lineage를 사용한다. staging/qc.json은 asset SHA namespace에 속한 QC 기록이지 QC 파일 자체의 SHA라는 뜻은 아니다. 실제 쓰기·동시성·중복 방지·객체 잠금/WORM은 이 경로 계산기가 구현하지 않는다.

`require_curated_lineage()`는 metadata_valid와 numeric_values_verified가 true인 명시적 QC 기록 및 고정 부모 참조를 요구한다. 메타데이터 QC는 numeric_values_verified=false를 반환하므로 자체적으로 curated 승인을 만들지 않는다. 외부 QC dict는 신뢰된 실행 경계에서 공급해야 하며 dict의 boolean만으로 실제 QA·운영 승인을 인증하지 않는다. 실제 수치 QA artifact 검증·publication은 다음 Gate다.

## 2. 허용 변수·단위와 변환

| 변수 | 허용 단위 | 조건 |
|---|---|---|
| tas/tasmin/tasmax | K, degC | K↔degC; 절대영도 미만 거부 |
| pr | kg m-2 s-1, mm day-1, mm | rate는 mean_rate, amount는 sum. rate↔amount는 명시적 CF 기간 필수 |
| ps | Pa, hPa | 양수 압력만 수용 |
| hurs | 1, % | 입력 범위0~1 또는0~100 |
| sfcWind | m s-1 | 음수 거부 |

`convert_value()`는 호출자가 제공한 유한 scalar를 검증·변환하며 자료를 조회하거나 RAG 답변에서 수치를 추출하지 않는다. 함수 이름만으로 전체 NetCDF QA가 완료된 것은 아니다. 강수 변환 receipt에는 물 등가 1kg/m²=1mm, 하루86400초, 명시적 기간 평균 rate/기간 sum 가정을 남긴다. 360_day의 한 달을 Gregorian 날짜로 바꾸어31일로 합산하지 않는다.

실제 누적강수와 flux의 cell_methods, 결측·단위속성·scale_factor/add_offset·누적 리셋/앙상블은 실제 CF reader에서 확인해야 한다. 지원되지 않는 변수·단위는 추정 변환하지 않고 BLOCKED다.

## 3. 경계 as-of와 미래 누출 방지

`services/geoai/features/climate_join.py`의 `plan_climate_join()`는 ClimateAsset, BoundaryVersion, FeatureJoinRequest를 받는다.

- asset version이 as_of 시각에 사용 가능해야 한다. 과거 공개 시각을 선언할 때 고정된 release URI/SHA를 보존한다.
- 경계 available_at≤as_of, valid_from≤as_of<valid_to 조건을 적용한다. 최신 경계를 과거 행정구역으로 역적용하지 않는다.
- CF calendar가 다르면 명시적 변환 근거 없이 차단한다. feature window가 asset time coverage 안에 있어야 한다.
- 관측 feature window는 목적이 scenario_analysis여도 cutoff 이후 자료를 사용할 수 없다. cutoff는 UTC as_of 날짜의 논리적 year/month/day보다 뒤로 둘 수 없다.
- historical_training에 projection을 넣지 않는다. 미래 projection은 scenario_analysis에서 모델·시나리오 가정을 경고하며 관측 정답으로 바꾸지 않는다.
- derived_from이 있으면 부모 공개시각·fit 기간의 graph resolver가 없으므로 `PARENT_LINEAGE_AS_OF_RESOLUTION_REQUIRED`로 차단한다. normalization 통계나 파생 feature를 통해 간접 미래 누출을 허용하지 않는다.
- restricted 자산의 principal ACL 불일치에는 dataset/boundary 식별자를 반환하지 않는다. principal의 실제 인증은 이 계획 함수 밖의 공통 보안 계층 책임이다.

다른 모델 달력의 날짜와 실제 UTC instant 사이의 과학적 시간 정합을 구현한 것은 아니다. 일 단위 논리적 cutoff와 source availability는 별도 조건으로 검사한다. leap-second/sub-day 정합, publication 진위·권위, 부모 graph의 실제 해시 검증은 후속 작업이다.

## 4. 공간 계획과 coarse 경고

현재는 **bbox와 rectilinear cell-bounds의 candidate window만** 계산한다. CRS가 다르면 `EXPLICIT_REPROJECTION_REQUIRED`, 공간 교집합이 없으면 BLOCKED다. 위도축 방향을 grid.row_order로 명시해 north-to-south와 south-to-north index를 구분한다. end index는 exclusive이며 경계가 정확히 cell edge에 닿으면 면적0인 이웃 cell을 추가하지 않는다.

polygon 교차·geodesic 면적 가중·지역 평균/합·리샘플·downscaling·zonal statistics·실제 feature 배열은 실행하지 않는다. 반환은 `PLANNED/BLOCKED`, `execution_started=false`, `numeric_features=null`이다. 경계 권위 provisional/unverified는 개발 경고이며 공식 통계 사용 승인이 아니다.

native 격자 nominal 해상도가1km 이상이면 coarse 경고를 표시하고, 더 세밀한 requested_resolution_m에는 downscaling을 실제 관측 증가로 해석하지 않는 경고를 추가한다. degree→m은 적도 명목값111,320m/degree에 불과하고 실제 cell 면적·고위도 거리를 산출한 값이 아니다. CCKP 격자를 Sentinel-2 10m 관측으로 표현하지 않는다.

## 5. 시험·운영 인계

```powershell
cd E:\SDSS-Platform2
python -m unittest discover -s tests/climate_lake -v
python -m unittest discover -s tests/climate_features -v
```

- lake/metadata: **12 PASS, 0.112초**
- features: **12 PASS, 0.039초**
- 모두 합성 fixture이고 실제 CCKP/NetCDF 수신·GeoAI 학습·독립 정확도·배포 실행은0이다.

CF2월30일/윤년/달력 alias, 단위 차원·기간 변환, 불명확한 RAW 차단, 경계 as-of·공개시각·직접/간접 미래누출·projection role·ACL·CRS·정확한 cell edge·위도 방향을 검사했다. source/RAG 공통 파일·UI는 수정하지 않았다. UI에 연결할 때 PLANNED와 numeric_features=null을 그대로 유지해야 하며 숫자 지도나 모델 성공으로 표시하면 안 된다.
