# LCLUC 연차 조회·변화 분석 실행

기준 화면은 기존 GeoAI Toolbox의 LCLUC다. 해당 화면의 연차 선택, 스와이프, 전이행렬과 집중지역을 SDSS-Platform2의 고정 결과 API에 연결한다. 조회한 지역·기준연도·비교연도가 모두 일치해야 결과가 열린다. 기본 그래프와 임의 수치를 생성하지 않는다.

## 연도별 지도 비교

반텐의 Esri 2020·2025 실자료, Landsat 8·Sentinel-2 관측 및 팔루 재난 비교는 [인도네시아 위성·토지피복 비교](INDONESIA_EXPLORER.md)를 참조한다. 기존 LCLUC Workspace의 지도 분석 탭과 종전의 Swipe·Time-Series·Single View 조작부를 사용한다. 실제 자료 선택과 다운로드는 지도 우측 범례에 연결했다.

대상 지역과 기준·비교 연도를 고르면 **두 시점 비교**에 지도 한 장을 표시하고 중앙 구분선으로 나눈다. 같은 격자의 기준 연도를 왼쪽, 비교 연도를 오른쪽에 표시한다. 구분선을 드래그하거나 키보드 방향키로 움직여 같은 위치를 확인할 수 있다. 지도 위에 공통 유효 면적, 변화 면적과 변화율을 표시한다. 분류별 면적 증감과 전이 내역은 기존 전이행렬에서 확인한다.

두 연도의 자료가 등록되지 않은 경우에는 같은 틀에서 선택한 두 연도와 토지피복 미등록 상태를 표시한다. 바탕에는 기존 `first-group-provinces.geojson`의 geoBoundaries 2017 ADM1 공개 참조 경계를 표시한다. 이 경계는 지도 위치를 안내하며, 분류 영상과 변화량은 등록된 연도 쌍이 있을 때 표시한다.

Edge에서 실행 중인 5175의 반텐 참조 경계와 중앙 구분선, 2020·2025 미등록 상태, 동자바 전환을 확인했다. 별도 합성 결과로 동일 화면 좌표의 두 레이어를 절반씩 표시하는 동작, 390px 창에서 포인터 드래그, 미등록 2023년 전환을 검증했다. 근거는 `artifacts/lcluc/single-map-retry.log`에 있다.

## 분류 사전과 데이터 준비

- **공식 KLHK 코드 23개**를 출처·버전·SHA-256으로 고정한다. 주제 분류 22개, 품질 코드 2500(구름), 구조적 NoData 65535를 구분한다. 기존 9분류와의 잠정 대응표는 명시적으로 선택하고 운영 승인과 별도로 사용한다. [분류 사전](TAXONOMY.md)
- 원본 후보 2개는 다른 실제 관측 연도, 같은 자료 종류와 분류 사전이 필요하다. 정렬된 등적 미터 격자 GeoTIFF와 0/1 유효 마스크를 사용한다. 출처 영수증은 관측일·자료 ID·호환 버전·출처 URI·SHA·이용 조건을 고정한다. WorldCover 2021을 이후 연도의 조회로 대체하지 않는다.
- 국지 분석 범위는 입력 격자 범위로 표시한다. 주·군·시·유역·계획구역 통계는 사용 가능한 경계 GeoJSON과 버전·SHA를 따로 등록한다.

## 한 결과 ID로 등록

`pip install -e ".[geo]"`로 로컬 계산 의존성을 설치한다. `sdss-lcluc-pair/1` JSON을 검토하여 프로젝트 내부에 둔다. `region`, `title`, `institution`, `taxonomy_id`, `taxonomy_sha256`, `source_kind`, `license`, `license_evidence`, `earlier`, `later`가 필요하다. 각 프레임에는 `raster`, `observed_on`(ISO 날짜), `dataset_id`, `version`, `uri`와 정식 자료의 `source_receipt`가 들어간다. 검증한 마스크는 `valid_mask`로 선택 연결한다. 핀은 `path`(프로젝트 상대 경로), `sha256`, `bytes`이며, 영수증은 `sdss-lcluc-source/1` 스키마를 사용한다. 경계 항목 `zones`는 `file` 핀과 `version`이다.

```powershell
python -X utf8 -m services.api.lcluc_run --manifest evidence/lcluc/approved-pair.json --sha256 <manifest-sha256>
```

명령은 원본 핀과 날짜·CRS·격자·NoData를 확인한 뒤 전이행렬·클래스별 증가/감소·집중지역·구역별 통계를 계산한다. GeoTIFF·GeoJSON·CSV·보고서와 화면 미리보기를 보존한다. 공통 결과 원장과 화면의 상세·다운로드가 같은 ID와 패키지 SHA를 사용한다. 보고서에는 공통 유효 면적이 분모로 표시된다. 계산 조건과 세부 포맷은 [변화·공간 통계 엔진](CHANGE_ANALYTICS.md)을 참조한다.

조회 API는 `GET /api/lcluc/taxonomy`, `/api/lcluc/selection?region=…&from_year=…&to_year=…`, `/api/lcluc/cases/{id}`를 사용한다. 결과 파일은 같은 ID 안에서 해시 검사 후 읽는다. 승인 플래그는 공통 결과의 과학검증과 기관공개승인에 각각 연결한다.

## AI 모델

`pip install -e ".[lcluc-ml]"`로 학습 의존성을 설치한다. Random Forest와 Tiny U-Net을 같은 고정 분할에서 비교하는 실행기를 제공한다. 입력 영상 6채널과 SCL 품질 마스크를 분리하고, 독립 검증과 약한 참조 일치도를 별도로 기록한다. 운영 모델 출시·자동 재학습 경로는 프로젝트 승인 증거가 준비되면 개통한다. [분류 비교](CLASSIFIERS.md)

## 검증 범위

- `VERIFIED_REAL` 분류 번호·명칭을 정부 자료 두 경로에서 대조했다. 보존된 KLHK 2024·2025 메타데이터의 렌더러는 25개 항목으로, 실제 원본의 23개 코드 도메인과 이용 권한 확인이 남았다.
- `TESTED_SYNTHETIC` 실제 파일 입출력을 사용한 격리 시험에서 구름·NoData가 섞인 두 GeoTIFF의 공통 면적 4ha, 변화 1ha, 변화율 25%를 계산했다. 회귀시험 37건이 통과했다. Edge에서 A~D의 이미지·스와이프, 전이 CSV 다운로드, 미등록 2023년 차단, 같은 결과 ID의 카탈로그 조회를 확인했다. 실행 중인 5175 화면에서는 등록 사례 0건과 분류 사전의 구름 코드 표시를 확인했다.
- `TESTED_SYNTHETIC` 분류기 전용 시험 12건에서 Random Forest와 Tiny U-Net을 같은 합성 시험 분할 252픽셀로 검증했다. 두 모델의 mIoU ≥ 0.50, SCL/NoData 마스크, SHA에 고정한 모델 파일 저장·복원을 확인했다. 독립 정확도는 미산출이다.
- `BLOCKED` 기관 연차 원본과 권리, 동년 독립 라벨, 실제 특화 모델 학습·승인·배포가 남았다.
- `PLANNED` Landsat 동등성, 현행 계획구역·다른 모델의 실자료 연계, 2030·2050 시나리오.
