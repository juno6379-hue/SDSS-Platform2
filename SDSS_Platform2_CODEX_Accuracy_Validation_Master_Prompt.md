# SDSS-Platform2 — LCLUC 3축 정확도 검증체계 개발 마스터 프롬프트

**목표:** AI 기술 검증 · 외부 제품 교차검증 · 독립 과학적 검증을 분리하되 하나의 증거 기반 Accuracy Assessment Center로 통합한다.

**대상 저장소:** https://github.com/juno6379-hue/SDSS-Platform2

**기준 브랜치:** `codex/next-gates-onemap-climate-klhk` (작업 시작 시 실제 HEAD와 변경사항 확인)

**이전 검토 기준:** `fc596cb488611e5affa6b11638b4848975beaf02` (2026-11-27). 최신 코드가 우선이며 이 커밋으로 되돌리지 않는다.

**개정:** 2026-11-27 · 실행 전 의존성, 검증 표본의 대표성, 승인 및 저장소 장애 계약 보강

**사용 범위:** 분석·문서 개정 요청에는 이 문서만 검토한다. 사용자가 개발 실행을 요청하면 아래 단계의 범위에서 작업한다.

---

## 0. Codex 역할 및 최상위 실행 지침

너는 원격탐사·GIS·통계적 표본설계·AI/MLOps·FastAPI/React·PostGIS·Docker/Kubernetes 전문 개발팀을 지휘하는 root agent이다. 단순 설계 문서 작성으로 종료하지 말고 실제 소스, 테스트, UI, 운영 문서 및 검증 증거까지 작성하라. 기존 SDSS 메뉴와 실자료 조회 기능을 보존하고, 현재 코드를 분석하여 재사용하라. 본 문서의 경로와 API는 목표 설계이며 기존 계약과 충돌하면 호환 Adapter를 마련하고 변경 이유를 기록하라.

- 먼저 `AGENTS.md`, `CONTINUOUS_DEVELOPMENT.md`, `docs/architecture/`, `docs/lcluc/`, `docs/mlops/`, `services/lcluc/`, `services/mlops/`, `services/api/`, `services/storage/`, `frontend/src/`, `deploy/`, `.github/workflows/ci.yml`을 검토한다.
- `git status`, 현재 branch/HEAD, 이미 실행 중인 작업과 Worker, 시험 결과, 실제 데이터의 목록·해시·승인 상태를 기록한다. 기존 체크아웃과 미커밋 작업을 보존한다. 브랜치 변경·작업 분리·원격 push/PR은 사용자 요청과 저장소 정책을 따른다.
- 기존 `VERIFIED_REAL`, `TESTED_SYNTHETIC`, `IMPLEMENTED_UNVERIFIED`, `PLANNED`, `BLOCKED` 상태를 유지한다. 별도 필드로 `reference_kind`, `scientific_review_state`, `publication_state`, `deployment_state`를 관리한다. HTTP 200, Docker 기동, 테스트 통과, 지도 일치도는 독립 정확도나 기관 운영 승인과 동일하지 않다.
- 외부 참조지도는 학습용 weak label, 제품 비교용, 공식 정책 기준용, 독립 참조용을 구분한다. 같은 데이터로 학습·파라미터 선정·최종 독립평가를 수행하지 않는다. 실자료가 없으면 BLOCKED와 필요자료를 명시하고 합성 시험을 실제 성능으로 표시하지 않는다.
- CPU 환경을 필수로 지원한다. GPU는 선택 프로파일이다. 실제 BIG 운영 자격증명이 없으면 로컬 격리 Staging에서만 검증한다. 승인 없는 외부 다운로드·대량 수집·비용 발생·운영 DB 변경·공개 발행은 금지한다. 비밀정보와 원본 대용량 자료를 Git에 올리지 않는다.
- 가능한 작업은 완료하고 차단 항목은 사유·필요 입력·해제조건·재개 명령을 남긴다. 문서와 코드의 상태를 일치시킨다. 이미 실행 중인 수집기·Worker·에이전트의 작업을 복제하지 않는다. 기존 데이터는 검증에 재사용하고 새 예약 작업은 별도 요청에 따른다.

## 1. 현재 기준선과 목표

이전 검토 기준으로 반텐 2020 실자료에서 Esri v003 약한 참조와 비교한 RF/TinyUNet/DeepLabv3+의 Sentinel-2 일치도는 70.39/57.88/63.74%, Landsat은 71.42/66.34/67.76%였다. 약 147m 시험 격자, 6개 클래스 결과이며 원해상도 독립 정확도가 아니다. Siamese U-Net 변화 F1 약 28.83%도 약한 참조 기준이다. Spatial Filter 전후 일치도 개선 역시 독립 검증이 아니다. 위 수치는 역사적 기준선일 뿐이며 현재 실제 파일·보고서·SHA와 일치하는지 확인한다.

현재 `services/lcluc/annual.py`, `annual_inputs.py`, `annual_rasters.py` 등의 기존 연차 처리 경로는 30m 공통 격자와 최소 독립 표본 조건을 사용한다. 기존 공통 격자 비교를 보존하고 Sentinel-2 10m 출력 격자와 Landsat 30m 제품별 검증 경로를 추가한다. 20m SWIR을 10m로 재표본화한 제품에는 밴드별 원천 지지단위와 출력 격자를 함께 표시한다. Esri 면적·전이는 Esri 제품으로 표시한다.

### 기준선에서 재사용할 기능과 남은 증거

| 범위 | 재사용할 증거 | 별도로 확인할 조건 |
| --- | --- | --- |
| A | [반텐 모델 비교](docs/lcluc/BANTEN_MODEL_TRIALS.md)와 [후처리·동년 특화 참조](docs/lcluc/POSTPROCESS_QUALITY.md). RF·Tiny U-Net·DeepLabv3+ 및 Siamese 비교, 실자료 Gap·Frequency·Incident 및 계층 통합 후보를 우선 찾고 실행 기록을 대조한다. | 센서별 목표 격자의 재현, 관측범위, 검증 분할, 희소 클래스 성능. 이전 약한 참조 수치와 새 실험 수치는 실행 ID로 분리한다. |
| B | [반텐 Esri와 MapBiomas 원래 분류별 집계](docs/lcluc/BANTEN_MAPBIOMAS_AREA_COMPARISON.md). Esri의 2024년 10m 집계는 경계 격자 935,602.88ha, 유효 분류 935,224.83ha, 구름 378.05ha라는 검증 기록이 있다. | MapBiomas의 발행 경계와 One Map 경계를 고정한다. 공간 비교에는 MapBiomas 공간 원본과 승인된 의미 매핑을, 산림부 비교에는 동년 Penutupan Lahan 원본 및 사용 조건을 요구한다. |
| C | [현행 MLOps Gate와 분할 감사](docs/mlops/TRAINING_ACCURACY_DEPLOYMENT_GATES.md). | 장면 분할 충돌이 없는 후보라도 공간 중복·참조 출처·확률표본 대표성을 별도 검증한다. 현재 독립 캠페인·승인에 관한 증거는 실행 시 재조회한다. |
| 공통 | [결과·계보·운영 경로](docs/architecture/PLATFORM2_OPERATION_PATH.md), [GeoLLM 계약](docs/lcluc/GEOLLM_QUERY.md), [저장소](docs/architecture/PRODUCTION_STORAGE.md). | 로컬 실자료, 격리 Staging, 기관 운영의 범위를 기록한다. 반텐 결과는 검증한 지역·기간·지지단위 범위에서 사용한다. |

검증 원장을 새로 작성할 때는 축별로 `데이터 실재 여부 → 훈련·검증 역할 → 과학 검토 → 공개 승인 → 배포`를 독립적으로 기록한다. 예를 들어 A축이 `VERIFIED_REAL`이어도 `reference_kind=weak_reference`와 C축 독립 지표 `null`을 함께 표시한다.

목표는 새 모델을 무조건 늘리는 것이 아니라 다음 세 축을 구분하여 실제 운영 후보를 선정하고, 정책 활용에 필요한 불확실성을 제공하는 것이다.

| 축 | 질문 | 결과물 |
|---|---|---|
| A. AI 기술 검증 | 어떤 모델·입력·후처리가 적합한가? | 고정 실험계획, 비교표, 혼동행렬, 원해상도 분류 후보, 자원 지표 |
| B. 외부 제품 교차검증 | 어떤 제품이 어디에서 얼마나 다른가? | 제품별 면적, 공통영역 동의도, 불일치 지도, 클래스 매핑 근거 |
| C. 독립 과학적 검증 | 실제 지표를 얼마나 정확히 분류하고 변화를 측정하는가? | 확률 표본, 독립 판독, 면적 가중 정확도, 오차보정 면적·95% CI, 승인 근거 |

## 2. 축 A — AI 기술 검증 (Model Benchmark)

### A1. 입력자료와 영상 품질

- Sentinel-2 L2A: B02/B03/B04/B08 10m, B11/B12 및 SCL 20m의 원본 해상도·반사도 scale/offset·관측기간·QA를 보존하고 10m 목표 격자를 생성한다. 연속형과 범주형 재표본화 정책을 구분한다.
- Landsat C2 L2: 30m, TM/ETM+/OLI 센서별 밴드 매핑, scale/offset, QA_PIXEL/QA_RADSAT 가용성 및 Landsat 7 SLC-off를 기록한다. 장기 연차별 유효관측·계절 대표성·센서 차이를 평가한다.
- AOI 버전, CRS, affine, 해상도, scene ID, 원본 SHA, 구름·그림자·NoData·유효관측률, 관측일/합성기간, 결측 및 보완 마스크를 Dataset Manifest로 고정한다. 관측 유효영역과 보완 추정영역을 구분한다.
- 기존 95% 물리 피복/80% clear 기준은 현재 연차 실행 Gate로 보존하되 과학적 정확도 목표와 분리하며 지역·연도·목적별 승인 정책으로 설정 가능하게 한다.

### A2. 모델 비교실험

- 기존 RF, TinyUNet, DeepLabv3+ 코드와 체크포인트 계약을 재사용한다. 동일 센서·연도·AOI·클래스·학습/검증/시험 분할·공통 유효평가 위치에서 비교한다. 서로 다른 센서의 평가집합을 같은 시험으로 간주하지 않는다.
- 기준 실험: 6밴드, 6밴드+NDVI/NDWI/NDBI/NDMI/NBR; 데이터가 확보될 경우 각 센서 원해상도에서 비교. 기존 147m 시험과 30m 공통 격자 결과는 별도 실험군이다.
- spatial block/group 및 scene ID 중복 방지, 공간 buffer 및 temporal holdout 적용. 시계열 전처리/정규화/후처리의 fit 범위를 기록하고 평가 연도 정보가 예측시점 이후에 유입되지 않도록 한다. 평가 표본을 재사용한 튜닝 금지. 모델 선택은 validation에서 하고 최종 독립 시험은 고정된 후보로 수행한다.
- OA, 클래스별 UA/PA(precision/recall), F1, IoU, Macro F1, mIoU, 표본 support 및 혼동행렬을 제공한다. 표본이 없는 클래스는 null로 처리하고 평균의 분모를 명시한다. 후보 모델이 반환하는 확률의 신뢰도는 별도 보정검증(ECE/Brier 등) 없이는 인증하지 않는다.
- 처리시간, RAM, VRAM(해당 시), 면적당 추론시간, 환경/라이브러리 버전, seed, 모델·코드·입력 해시, CPU/GPU 프로파일을 등록한다.

### A3. 후처리·변화탐지

기존 Spatial·Temporal·Gap Fill·Frequency·Incident·Hierarchical Integration 구현과 증거를 먼저 대조하고 부족한 모듈을 보완한다. 필터별 단독 및 조합 Ablation을 수행한다. 최소 객체 크기는 픽셀 수와 실제 면적(m²/ha)을 함께 설정한다. NoData·수역·좁은 하천·작은 농경지·희소 클래스·실제 급변 보호 규칙을 검증한다. 결측 보완 출처일/연도·마스크를 저장한다. 미래연도까지 이용하는 회고적 필터와 실시간/예측 모드를 분리한다. 필터 설정은 validation에서 결정하며 최종 독립 표본을 이용해 재튜닝하지 않는다. 맹그로브·논 공개 지도 후보는 각각의 원천 해상도와 활용 범위를 유지하고, 양식장·팜유·목재조림은 원본 적격성과 권리 확인 결과를 개별 기록한다.

변화탐지는 분류 후 비교(Post-classification Comparison)를 기본으로 유지하고 Siamese U-Net을 후보로 비교한다. 변화/유지와 주요 전이 유형의 F1, UA, PA, IoU, 오탐·미탐, 전이행렬, 발생시기(관측 간격을 넘는 정밀도를 주장하지 않음)를 별도 기록한다. 입력이 부족하면 실행하지 않는다.

## 3. 축 B — 외부 제품 교차검증 (Product Agreement)

### B1. 제품 레지스트리 및 원본 클래스

| 제품 | 역할 | 원칙 |
|---|---|---|
| Kemenhut/KLHK Penutupan Lahan | 인도네시아 공식 비교 기준 | 동년 23개 클래스 원본·버전·축척·권리·APL 포함범위 확인 |
| Esri/Impact Observatory | 최근 연차 10m 비교 제품 | 원본 클래스 코드 및 구름·NoData 유지 |
| MapBiomas Indonesia Collection 4.1 | 1990~2024년 장기 비교, 특화 유형 | 원본 분류체계·발행경계 보존, 공식 XLSX와 공간 래스터 구분 |
| ESA WorldCover/Dynamic World | 동년 보조 비교/weak label | 제품별 정의와 기간 보존, 2021 지도를 다른 연도 정답으로 사용 금지 |
| GreenBlue Sentinel/Landsat | 자체 후보 지도 | 모델 버전·입력·QA·독립 검증 상태 명시 |

원래 클래스 코드를 보존하고 별도의 `TaxonomyCrosswalk`에서 원본·대상 범례 버전, 일대일/다대일/미대응/혼합 관계, 증거, 승인자 및 해시를 기록한다. 한 원본 클래스가 여러 대상 클래스를 포함하면 같은 위치를 분리할 독립 공간정보가 있을 때만 나눈다. 맹그로브·팜유·이탄습지림 등을 임의로 등치하지 않는다. MapBiomas 발행 경계와 One Map 경계의 차이, 지도 버전과 관측기간 차이, 단위와 NoData 차이를 출처별로 보존한다.

### B2. 공통 비교 엔진

동년·공통 AOI 버전·공통 의미 클래스·공통 유효영역·비교 격자를 고정한 후 공간 비교를 수행한다. 각 원본 제품의 native 면적은 별도로 제공한다. 10m↔30m 비교에는 30m 등적 격자 또는 명시적으로 정의한 공통 공간 지지단위와 범주형 집계 규칙을 사용하고, Landsat 업샘플링을 10m 정확도 향상으로 표시하지 않는다. 경계 픽셀 포함 규칙, 면적 계산법, NoData 및 구름 제외 면적과 공통 분모를 기록한다.

제품별 집계에는 전체 AOI, 각 제품의 유효 영역, 양쪽 공통 유효 영역, 미대응·혼합 코드 제외 면적, 최종 비교 분모를 따로 기록한다. 대상 격자의 원점·경계 처리, 면적 가중 범주 집계, 동률·최소 유효 비율 처리, 제외 사유를 해시로 고정한다. 면적 합계와 제외 면적의 폐합을 확인한다.

결과는 제품별 원본 면적, 공통 클래스 면적과 차이(ha·%), `agreement` 행렬, 불일치 지도, Swipe 및 선택 위치의 원본 클래스·출처·관측기간을 포함한다. 비율 차이는 분모와 방향을, Quantity/Allocation Disagreement는 정의와 가중방법을 함께 표시한다. 공간 원본 없이 XLSX 통계만 있으면 발행 집계까지만 제공한다. Kemenhut/KLHK 등 공식 지도와의 비교도 B축이며 공식성은 C축 독립 표본의 품질 조건을 대신하지 않는다.

MapBiomas 4.1 분류 GeoTIFF/GEE, Kemenhut 23-class 원본의 접근·라이선스·승인이 미확보라면 입고 규격과 차단 상태만 구현하고 기존 발행 통계를 활용한다. 외부 원본을 덮어쓰거나 동일 제품인 것처럼 재분류하지 않는다.

## 4. 축 C — 독립 과학적 검증 (Accuracy Assessment)

### C1. 확률표본 설계 (Sampling Design)

MapBiomas Collection 4.1 ATBD 5장과 Olofsson et al. (2014)의 확률기반 검증을 참고한다. 검증 목표와 사용할 참조자료를 먼저 정하고 SDSS의 보고 지역·희소 전이·비용에 맞게 층과 표본을 설계한다.

- 모집단/보고영역/기준연도 또는 연도쌍/센서/공간 지지단위/분류체계/유효영역을 명확히 정의하고 승인된 지도를 고정한다. 전체 AOI와 관측 유효영역의 면적·범위를 분리한다. NoData가 큰 경우 관측유효영역 결과를 전체 AOI로 일반화하지 않는다. 전체 AOI 추정이 필요하면 미관측 층에 별도 확률표본과 참조자료를 확보한다.
- 기본 층은 지도상 클래스(변화평가는 전이/변화·유지)로 설계하고 지리·생태권역·경사·희소 클래스·저신뢰 구역을 보조 층 또는 표본배분 변수로 검토한다. 층은 중복 없이 모집단을 포괄하며 모든 평가 단위는 알려진 양의 포함확률을 가져야 한다. 샘플링 프레임, 층별 면적·모집단 수, 표본 수, 포함확률, 가중치, seed, 설계 버전, 예비표본 순서를 기록한다.
- 사전에 목표 신뢰수준·허용오차·클래스/지역별 보고수준·예상 분산·판독비용을 정의한다. 소규모 Pilot로 분산을 추정하고 층별 배분을 최적화한다. 희소 변화 클래스에 충분한 표본을 배정한다. 단순 무작위 근사 표본수와 실제 층화 배분을 구분한다. 반텐 1,000~1,500개는 초기 예산 계획용 제안이며 확정된 과학 표본수가 아니다.
- 임의 표본 교체·선택적 제외 금지. 판독 불가/미응답은 사유를 기록하고 설계에 근거한 가중치 조정 또는 추정 제한을 적용한다. 검증 표본 위치와 학습/튜닝 데이터의 공간·시간·출처 중복을 검사한다. 동일 센서 비교의 paired design과 장기 연도 반복판독의 상관성을 고려한다.
- 기존 연차 워커의 최소 100개 독립 표본은 실행 Gate일 뿐 통계적 대표성으로 간주하지 않는다. 독립 검증의 표본설계 승인·유효층·가중치·참조자료 품질이 별도로 충족되어야 한다.
- 1차 산출은 등면적 단위의 층화 비복원 단순무작위표본으로 제한한다. 경계에 걸친 단위의 모집단 귀속 규칙을 고정하고 대상 단위의 실제 면적이 달라지면 그 설계에 맞는 추정 방법을 사용한다. 동일 표본 위에서 모델을 비교할 때는 모든 후보의 유효영역, 표본 포함확률, 반복측정 ID를 보존한다.
- 설계 동결에는 AOI·비교지도·교차분류표·표본 프레임·난수 생성기와 seed·추정량과 CI 정책·비응답 정책의 버전과 SHA-256을 포함한다. 층별 n, 모집단 N, 포함확률과 추출 가능한 모든 단위의 범위를 질의 결과에 남긴다.

### C2. 독립 판독 및 TVI형 UI

`Reference Sample Registry`와 `Temporal Visual Inspection`형 전문가 판독 화면을 구축한다.

- sample_id, geometry, 대상연도/기간, sensor/support, stratum_id, inclusion_probability, weight, campaign_id, status, evidence_ref를 관리한다.
- 판독자에게 모델 예측 클래스·확률, 층, 지도 범례의 정답 단서 및 다른 판독 결과를 숨긴다. 블라인드 계약은 화면뿐 아니라 API 필드, 지도 타일·서명 URL·내보내기에도 적용한다. 목표 지지단위와 허용 관측기간은 표시한다.
- 독립 참조에는 시공간 해상도와 시점이 적합한 고해상도 영상이나 검증된 현장 기록을 우선 사용한다. 모델 입력인 같은 시계열 Landsat/Sentinel-2를 판독 보조로 시청한 경우 자료 계보를 기록한다. 학습·튜닝에 사용한 라벨, 그 파생물 또는 비교제품의 클래스 자체를 판독 정답으로 등록하지 않는다. 판독 근거의 시간차·해상도·권리·판독 불확실성·독립성 판단을 표본별로 저장한다.
- 판독자 A/B/C가 독립적으로 클래스, 판독확신, 판단근거, 불확실/판독불가 이유를 기록한다. 2인 이상 일치를 후보 합의로 삼되 낮은 확신·복잡/희소 클래스·불일치는 상급 전문가 검토로 보낸다. 합의 자체가 진실임을 보장하지 않는다. 최종 확정과 동결, 변경 이력 및 판독자 간 일치도를 별도로 관리한다.
- 변화 표본은 T1/T2 참조 라벨, 전이 유형, 변화 여부, 확인 가능한 발생기간, 근거를 독립적으로 판독한다. 전체 과거 연도를 동일 위치에서 판독하는 경우 반복측정 구조를 보존한다.
- 전문가/검토자/승인자 권한을 분리한다. 최종 표본은 불변 버전으로 고정하고 새 수정은 새 revision으로 관리한다. 학습용 내보내기와 독립 검증용 내보내기를 분리한다.

### C3. 통계적 정확도 및 면적 오차보정

층화 무작위 표본에서 단순 개수 혼동행렬과 면적 가중 혼동행렬을 분리한다. 행은 지도상 클래스 i, 열은 독립 참조 클래스 j로 명시한다. 지도 클래스가 층인 단순 설계에서 `W_i=A_i/A_total`, `p_ij=W_i*n_ij/n_i`, `OA=sum_i p_ii`, `UA_i=p_ii/sum_j p_ij`, `PA_j=p_jj/sum_i p_ij`, `Ahat_j=A_total*sum_i p_ij`를 구현한다. 복합층에서는 각 층의 면적 가중치를 적용해 행렬을 집계하며, 불균등 포함확률 설계는 설계에 맞는 추정량과 분산추정량을 사용한다. 위 공식의 적용 전제와 분모를 검증한다.

- 각 층 `h`의 동일 면적 단위가 비복원 단순무작위로 추출되고 응답이 완전하면, 셀·클래스·정분류 지시변수 `z`의 층별 평균을 `Σ_h W_h mean_h(z)`로 합산한다. 표본분산이 정의될 때 `var = Σ_h W_h² (1 - n_h/N_h) s_h²/n_h`를 사용한다. 면적 추정의 표준오차에는 `A_total`을 곱한다. 층화 변수가 지도 클래스와 다른 경우 층별 지시변수를 합산하고 `n_i` 단축식을 사용하지 않는다. [Olofsson et al.](https://nottingham-repository.worktribe.com/index.php/OutputFile/728232) · [Stehman](https://doi.org/10.1080/01431161.2014.930207)
- CI는 신뢰수준·분산법·전제·경계 처리 규칙을 사전에 고정한다. 복합·군집·반복 표본, 응답률 보정 또는 UA/PA 등 비율 추정량은 설계에 맞는 비율 분산·공분산 또는 설계 기반 재표본화를 검증한 뒤 적용한다. 단순 IID bootstrap과 설계 전용 분산식을 혼용하지 않는다.
- 클래스별 지도 면적, 오차보정 면적, SE, CI를 제공하고 추정 합계가 정의된 모집단과 일치하는지 확인한다. 전수조사 층을 제외하고 `n_h < 2`이거나 설계에 필요한 정보가 없으면 해당 지표의 CI는 `null`과 `NOT_ESTIMABLE`로 표시한다. 추정 불가 사유와 표본·응답 수를 보존하고, 0건 관측이나 무변동 표본을 면적 0 또는 완전한 확실성으로 자동 발행하지 않는다.
- OA, UA, PA, commission/omission, F1, IoU, mIoU를 산출하고 raw sample metric과 design-weighted metric을 명확히 구분한다. 지역별/연도별/클래스별 표본 대표성이 충분한 도메인에서만 결과를 공개한다.
- 변화평가는 별도의 확률표본 설계를 사용한다. change/no-change 및 주요 from/to 클래스의 면적 가중 행렬, 변화 오차보정 면적과 CI, 산림 총전환과 순변화 구분을 제공한다. 연도별 면적의 차이에 CI를 계산할 때 공분산을 고려한다(동일 표본 반복판독 등). 독립성 근거 없이 두 연도 CI를 단순 합산하지 않는다.

### C4. 과학 검토 및 승인

기존 `services/mlops/gates.py`, 공통 결과 카탈로그와 모델 릴리스 계약을 확장한다. 검증 산출물의 과학 검토, 결과 공개 승인, 모델 승격, 운영 배포를 별도 행위로 기록한다. 승인자 권한·시각·결정·범위·근거 해시를 남긴다. 검증 목표치는 검토자 승인 전 `PROPOSED`로 둔다. 최소 클래스 성능, 중요 변화 성능, CI 정밀도, 관측범위, 처리비용을 함께 평가하며 채택 기준을 독립 표본 판독 전에 고정한다. 독립 참조 미입고, 표본 편향, 권리 미확인, 평가 누출, 해시 불일치가 해당 승인 범위에 있으면 `BLOCKED`로 기록한다. 입력·후처리·모델·분류체계·권리·표본이 바뀌면 새 revision과 영향받은 승인 범위를 기록한다. 기존 승인 증거는 해당 revision의 이력으로 보존한다.

## 5. 기존 SDSS에 통합할 UI/UX

기존 React와 SDSS 메뉴 스타일을 유지한다. 기존 LCLUC 조회 화면에 정확도 요약 배지를 추가하되, 별도 작업 메뉴로 `GeoAI Toolbox → Accuracy Assessment Center`를 제공한다. 분석 대상 제품·지역·연도·모델·실험 ID를 고정해 화면 간 이동 시 동일 식별자를 유지한다.

| 탭 | 기능 |
|---|---|
| Overview | A/B/C 3축 상태, 실제/합성/미확보 구분, 과학 승인·공개 승인 별도 표시 |
| AI Benchmark | 센서/모델/입력/후처리 비교, OA·Macro F1·mIoU, 클래스별 지표, 자원 사용량, 결과 Swipe |
| Product Agreement | Esri·KLHK·MapBiomas·자체 후보 선택, 제품별 해상도/범례, 공통영역 비교, 면적 및 불일치 지도 |
| Sampling Design | 모집단·층·배분·표본수·seed·가중치, 표본 지도, 검토·동결·내보내기 |
| Reference Inspection | 블라인드 독립 판독, 연도별 Explore/Swipe/Animate, 목표 공간 지지단위, 증거·판독 입력 |
| Consensus Review | 판독 불일치·재판독·불확실 표본·최종 라벨 승인·이력 |
| Accuracy & Area | raw/weighted 혼동행렬, OA/UA/PA/F1/IoU, 지도면적 vs 오차보정 면적, 95% CI, 표본수 |
| Change Validation | 변화/유지 및 주요 전이 검증, 오탐·미탐 지도, 총전환·순변화·면적 CI, 후처리 영향 |
| Evidence & Release | 데이터·모델·표본·결과 해시, 검증보고서, 과학검토/공개/배포 상태, 승인 이력 |

- 모든 그래프·수치·지도는 검증된 실제 API Result를 사용한다. 합성/시연은 별도의 명시적 demo 모드에서만 제공한다. 기존 합성 함수/고정 KPI가 실제 경로에서 호출되지 않는지 추적한다.
- NoData·비교불가·미판독·표본 미확보는 0% 또는 0ha로 표시하지 않는다. 원본 클래스와 공통 클래스 및 raw count/weighted 지표를 명확하게 구분한다.
- 결과마다 센서·해상도·AOI·기간·분류체계·검증 종류·유효영역·표본 설계·출처·버전을 노출한다. 지도 색상과 범례는 해당 제품의 승인된 범례를 사용한다.
- 한국어·인도네시아어·영어 UI 용어를 정리한다. GeoLLM이 결과 조회 링크로 관련 탭에 이동할 수 있게 한다.

## 6. 소스 구조 및 API 계약

현행 코드의 실제 경로를 점검하고 가능한 부분은 재사용한다. 대규모 이동을 피하고 호환 import 및 API를 유지한다. 다음은 신규 모듈 제안이다.

```text
services/
  lcluc/
    annual.py                       # 기존: 수정 최소화, 공통 격자 경로 유지
    annual_inputs.py
    annual_rasters.py
    classification_trials.py
    postprocess.py
    accuracy/
      __init__.py
      contracts.py                  # Campaign, SampleDesign, ReferenceSample, Assessment
      benchmark.py                  # A축: 실험·센서·모델 비교 실행
      product_registry.py           # B축: 원본 제품/연도/해상도/권위/권리
      taxonomy_crosswalk.py         # 승인된 의미 매핑
      product_agreement.py          # 공통영역 면적 및 공간 일치도
      sampling_design.py            # C축: 확률표본·층·배분·가중치
      sample_registry.py            # 표본 및 이력
      reference_labeling.py         # 블라인드 판독
      consensus_review.py           # 합의·전문가 판정
      weighted_metrics.py           # count vs design-based confusion matrix
      area_estimation.py            # 오차보정 면적·분산·CI
      change_validation.py          # 변화/전이 정확도
      validation_report.py          # 공통 Result 및 보고서
      storage_adapter.py            # 기존 storage/repository 재사용
      worker.py                     # CPU 장시간 작업 실행 진입점
  api/
    lcluc_accuracy.py               # 신규 라우터
  mlops/
    gates.py                        # 기존 gate 보존·확장
  storage/                          # 기존 기관별 PostgreSQL/S3 계약 재사용
  rag/                              # 검증방법 문서 및 GeoLLM Tool 연결
frontend/src/
  LclucAccuracyCenter.tsx
  lclucAccuracyClient.ts
  lclucAccuracyContracts.ts
  accuracy/                         # 탭별 구성요소
  lcluc-accuracy.css
tests/lcluc/accuracy/               # 신규 단위/통계/회귀 시험
tests/api_ui/                       # API·권한·기존 화면 회귀
deploy/                             # 기존 compose/kind manifest 확장
```

### API 제안

기존 `/api/lcluc/...`, 공통 Job/Result API의 실제 prefix·인증방식과 정합한다. 경로 충돌 시 기존 API 유지, 신규 API에 명시적 버전/호환 adapter 적용. 대용량 분석은 비동기 작업(202 + job_id), 결과는 공통 Result ID를 반환한다.

| HTTP | 경로(제안) | 목적 |
|---|---|---|
| GET | `/api/lcluc/accuracy/status` | 3축 준비상태와 blockers |
| POST | `/api/lcluc/accuracy/benchmarks/jobs` | 고정 모델 실험 제출 |
| GET | `/api/lcluc/accuracy/benchmarks/{id}` | 비교결과 및 증거 |
| POST | `/api/lcluc/accuracy/product-agreement/jobs` | 제품 교차비교 |
| GET | `/api/lcluc/accuracy/products` | 제품별 버전·연도·범례·권리 |
| GET | `/api/lcluc/accuracy/crosswalks/{id}` | 승인 클래스 매핑 조회 |
| POST | `/api/lcluc/accuracy/campaigns` | 독립 검증 캠페인 생성 |
| POST | `/api/lcluc/accuracy/campaigns/{id}/design` | 표본계획 생성/검토 |
| POST | `/api/lcluc/accuracy/campaigns/{id}/freeze` | 승인된 설계·표본 동결 |
| GET | `/api/lcluc/accuracy/campaigns/{id}/samples` | 역할별 표본 조회 |
| POST | `/api/lcluc/accuracy/samples/{id}/interpretations` | 독립 판독 제출 |
| POST | `/api/lcluc/accuracy/samples/{id}/review` | 권한 있는 전문가 검토 |
| POST | `/api/lcluc/accuracy/campaigns/{id}/assessment/jobs` | 가중 정확도·면적·변화 평가 |
| GET | `/api/lcluc/accuracy/assessments/{id}` | 정확도·면적·CI·한계 |
| GET | `/api/lcluc/accuracy/assessments/{id}/report` | 검증보고서·다운로드 |

승인·실행·취소·결과 파일 접근은 기존 인증과 공통 작업계약을 재사용한다. 기관 principal은 서버에서 확인하고 요청 본문에 들어온 기관 ID를 신뢰하지 않는다. 판독자에게 모델 정답이 유출되지 않도록 API 응답/지도 URL도 역할별로 분리한다. 스키마 검증, 오류코드, idempotency, immutable input fingerprint, 작업 재시작·취소·중복 제출·경쟁 상태를 검증한다.

공통 응답에 `schema_version`, `assessment_id`, `job_id`, `result_id`, `axis`, `evaluation_kind`, `reference_kind`, `dataset_refs`, `model_ref`, `campaign_ref`, `aoi_ref`, `period`, `grid`, `taxonomy_ref`, `valid_area_ha`, `metrics`, `confidence_intervals`, `evidence_refs`, `trace_id`, `blockers`, `scientific_review_state`, `publication_state`, `deployment_state`를 지원한다. 공통 Result ID에서 지표·지도·출처·보고서·불확실성이 같은 revision으로 열린다. 평가 종류, 참조 역할, 증거의 실재 여부를 개별 필드로 관리한다. 미생성 ID·수치·지도 URI는 `null`이고 미산출 이유를 기계 판독할 수 있게 제공한다. 과학적 결과와 운영 승인 상태를 같은 플래그로 결합하지 않는다.

## 7. Data Lake 및 검증 DB

기존 `services/storage/`, 결과 카탈로그, 기관별 RLS 및 lineage 구조를 우선 검토한다. 이미 있는 schema는 중복 생성하지 않는다. 다음 논리 엔터티를 기존 계약에 맞게 확장하거나 신규 migration으로 도입한다.

- `accuracy_campaign`: 기관/목적/보고영역/기간/제품/모집단/상태/버전.
- `sampling_stratum`: 층 정의, 면적, 모집단 수, 배분, 포함확률, 설계 유형.
- `reference_sample`: 위치(PostGIS), 목표 지지단위, 대상연도, 층, weight, seed 및 동결 상태.
- `sample_interpretation`: 판독자/참조 클래스/시기/근거/신뢰도/판독불가/제출 시각.
- `sample_consensus`: 합의·상급 검토·승인된 참조 라벨·revision.
- `benchmark_run`, `agreement_run`, `accuracy_assessment`: 고정 데이터/모델/표본/코드 참조와 지표 및 QA.
- `assessment_metric`, `area_estimate`, `change_estimate`: 추정량, 분모, 가중치, SE, CI, 한계, null 사유.
- `assessment_evidence`, `scientific_review`: 원문/지도/보고서/해시·권리·승인 이력.

Object Storage는 원본 참조영상·COG·GeoPackage·표본/판독 export·모델·보고서를 보관한다. PostGIS/PostgreSQL은 정량 지표와 계보를 보관한다. pgvector는 검증 방법론 및 보고서의 설명용 검색에 사용하며 숫자의 권위 원천으로 사용하지 않는다. 대용량 원본을 DB에 무조건 복제하지 않는다.

기존 `PROJECT_STORAGE_AUTHORITY_NOT_CONFIGURED`가 남으면 해당 기관의 운영 연결은 `BLOCKED`로 기록한다. [GeoLLM 저장소 모드](docs/lcluc/GEOLLM_QUERY.md#step-04-geollm-저장소-모드)의 `local`/명시 `lake` 계약을 따르고 검증 모듈은 기존 PostGIS·S3 기관 계보, Job·Result 저장 경로를 우선 확장한다. 새 조회 전용 어댑터를 도입하더라도 운영 모드에서 연결·설정 오류를 `BLOCKED`로 반환하고 선행 조회·로컬 마운트·임시 캐시에서 독립 지표를 대체하지 않는다. DB/S3 장애, 연결 복구 및 소속이 다른 사용자·Worker의 접근을 격리 Staging에서 시험한다. 환경별 보안값, 데이터셋 버전 및 release를 문서화하고 기존 SQLite/로컬 결과를 보존한다.

## 8. Docker·Kubernetes 및 MLOps

현행 `Dockerfile`, `deploy/compose.yaml`, `deploy/kubernetes/local-validation.yaml`, `deploy/storage/compose.yaml`을 활용한다. 초기에 기존 API 이미지와 독립적인 정확도 Worker 실행 진입점을 사용해도 좋다. 서비스마다 이미지를 불필요하게 늘리지 말고 실행 경계/의존성을 분리한다. 장시간 래스터 처리와 대량 표본 분석은 API 요청 스레드에서 실행하지 않는다.

- `sdss-web`: 기존 React/Nginx + 정확도 검증센터.
- `sdss-api`: 검증 API/판독/조회/승인, 무상태 지향.
- `lcluc-accuracy-worker`: CPU Job/queue worker, 선택 GPU 모델 실행. 장시간 작업/자원 제한 및 동시 실행 제어.
- `postgres-postgis`: 기관별 카탈로그/표본/정량지표/영속 작업상태.
- `object-storage`: 승인된 원본 및 파생자료, 내용 해시/영속성.
- `mlops`: 고정 모델·실험·검증·승격·롤백 연계.
- `geollm`: 검증 결과 API/Tool 소비, 문서 근거 검색.

Compose CPU 환경과 kind staging에 동일한 애플리케이션 이미지를 사용한다. 필요 시 동일 이미지에서 command를 변경해 Worker/Job으로 실행한다. ConfigMap/Secret, PVC 또는 승인된 외부 저장소, non-root/read-only root filesystem(적절한 scratch volume), liveness/readiness, service DNS, resource requests/limits, 실패/재시도/복구 및 로그의 민감정보 제거를 구현한다. 실제 기관 endpoint·IAM/SSO·운영 권한은 별도 승인 대상이다.

## 9. GeoLLM 연계

기존 GeoLLM 한국어·인도네시아어·영어 라우터, GIS/문서 분리와 명시적 Data Lake 저장소 모드를 재사용한다. 정량 Tool은 권한이 있는 등록된 결과의 지표·출처·버전·단위·AOI·기간·신뢰구간을 응답한다. 질의에서 제품·기간·지표 의미가 모호하면 특정 제품이나 추정량을 추정해 답하지 않고 필요한 조건을 안내한다. 다음 Tool을 공통 Tool/Result 계약에 등록한다. 이름은 기존 규칙을 따른다.

- `lcluc.get_benchmark`: 동일 센서·평가집합의 후보 모델 비교.
- `lcluc.get_product_agreement`: 외부 제품 간 동의도/차이지도.
- `lcluc.get_accuracy`: 독립 표본 및 설계 기반 지표 조회.
- `lcluc.get_area_estimate`: 지도면적/오차보정 면적/95% CI 조회.
- `lcluc.get_change_accuracy`: 변화/전이의 정확도와 불확실성 조회.
- `lcluc.get_validation_evidence`: 검증자료·판독·버전·근거/제한사항.

질의 예에서 “반텐 2020 Sentinel-2 RF 정확도는?”에는 약한 참조 일치도와 독립 정확도 미측정을 함께 알려준다. “반텐 2023~2024년 산림감소 면적과 95% 신뢰구간은?”에는 총전환·순변화와 제품을 판별하고, 승인된 오차보정 결과가 없으면 요청한 CI를 `null`로 둔다. “MapBiomas의 표본설계 방법은?”에는 ATBD 원문을 인용한다. 문서 색인의 발행 수치와 등록된 분석 결과는 권위와 버전을 각각 기록한다.

## 10. 병렬 멀티에이전트 실행계획

root가 공통 계약·마이그레이션·UI 조정·CI 및 최종 통합을 소유한다. 에이전트 간 인터페이스와 파일 소유권을 먼저 합의하고 실제 동시 실행 한도에 맞게 순차 배정한다. 아래 표는 역할 목록이며 현재 가동 중인 역할·프로세스를 조회한 뒤 빈 범위만 배정한다. 공통 변경은 root에 제안한 뒤 반영한다.

| Agent | 작업 범위 | 제출 산출물 |
|---|---|---|
| A1 imagery_quality | 원해상도·품질·데이터셋 계약 | Sentinel 10m/Landsat 30m 경로, QA, tests |
| A2 model_benchmark | RF/TinyUNet/DeepLabv3+ 비교, holdout | 실험계약·지표·자원 비교·재현 스크립트 |
| A3 postprocess_change | 후처리·Ablation·변화탐지 | 필터·변화 후보·전후 검증 |
| B product_agreement | 외부제품·crosswalk·공간비교 | 제품 등록·동의도/차이지도·검증근거 |
| C1 sampling_design | 확률표본 설계 및 추출 | 표본·층·가중치·동결 계약 |
| C2 reference_inspection | 판독/합의/역할 및 검토 | 블라인드 UI/API·검증 이력 |
| C3 statistical_assessment | 가중행렬·분산·CI·변화면적 | 통계 엔진·독립 재계산 시험 |
| D data_storage | 기존 저장소/계보/기관 권한 | migration·adapter·backup/recovery |
| E web_api_geollm | React 통합·API·Tool | 화면·다국어 질의·계약시험 |
| F deployment_qa | Compose/kind/CI·회귀·보안 | E2E·재시작·권한·로그 |
| G documentation | 쉬운 이해자료·운영/과학 매뉴얼 | 문서·검증 상태표·다음 세션 인계 |

| 순서 | 실행 범위 | 다음 단계 조건 |
| --- | --- | --- |
| 1 | 기준선의 실제 HEAD·활성 작업·증거·CI 점검과 공통 결과 등록·검토·조회의 회귀 확인 | 기존 경로와 증거의 위치, 재사용 가능한 모듈, 차단 자료를 문서화 |
| 2 | 반텐 한 기간의 소형 합성 캠페인에서 표본–블라인드 판독–가중 통계–Result ID–화면·GeoLLM을 처음부터 끝까지 연결. A/B의 원본 감사, C의 통계·판독 경계는 파일 소유권을 나눠 병렬로 진행 | 합성 표시, 설계 가중치와 면적 폐합, 조회·승인 분리, 운영 모드 저장소 차단 확인 |
| 3 | 확보된 범위에서 반텐 실자료 모델·후처리(A) 및 제품 비교(B), UI와 다운로드·GeoLLM 회귀 | 센서/제품/기간·격자·공통 분모·출처·버전이 결과 ID로 추적됨 |
| 4 | 승인된 반텐 확률 설계와 참조자료로 C축 실제 판독 및 독립 평가 | 채택 기준·표본 모집단·판독·추정 검증 완료. 과학 검토·공개·배포는 별도 기록 |
| 5 | 동일 이미지로 CPU Compose와 kind 재현 및 기존 화면 클릭, 기관 수용시험은 승인 후 실행 | 실제 시험 범위와 누락 사유 기록. 지역 확대는 검증 범위·자료·별도 승인 기준에 따름 |

설계와 판독 지침을 동결하기 전에는 C축의 공식 판독·보고를 시작하지 않는다. 독립 참조가 지연돼도 범위가 명확한 A/B 실자료 시험과 C축 합성 E2E를 병렬로 완료한다.

## 11. 필수 테스트 및 수용 기준

### T1. 통계·공간 단위시험

1. 등면적 단위를 층화한 합성 검산 자료를 포함한다. 10,000ha 모집단, 층 면적 9,000/1,000ha, 층별 표본 10개, 행=지도·열=참조인 개수 행렬 `[[8,2],[1,9]]`이면 단순 OA 85%, 설계 가중 OA 81%, 보정 면적 7,300/2,700ha가 된다. 층화 기준과 지도 클래스가 다른 예제도 추가해 독립 검산 결과와 면적·분산·CI를 대조한다.
2. 완전 분류, 일부 오분류, 희소 클래스, 빈 층, n=1, 0 분모, 미응답, 중복 표본, 가중치 합·면적 합 보존을 검증한다. 정의되지 않은 지표/CI가 null이며 이유가 표시되는지 확인한다.
3. 동일 지도는 공통영역에서 100% agreement, 의도적 불일치 지도는 정확한 전이·불일치 픽셀·면적을 반환해야 한다. 미대응 클래스, NoData, 서로 다른 연도/AOI/해상도, 위경도 면적왜곡 처리 시험을 포함한다.
4. 10m/30m 입력 grid, 범주형 재표본화, 경계 픽셀, quality mask, 후처리 보정 영역, 작은 객체 보존, 미래 정보 누출 방지를 시험한다.
5. 변화 전이행렬, 산림 총전환/순변화, 공통 유효영역, 반복표본의 공분산 처리 여부를 검증한다.

### T2. 보안·계약·운영 시험

- 동일 scene/공간/연도 누출, 모델 선택 후 시험집합 재튜닝, 학습 라벨을 독립 참조로 제출하는 경우, 다른 연도 참조, 불변 해시 변경, 임의 승인·권리 누락을 차단한다.
- 표본 판독자 간 결과 비공개, 예측 라벨 블라인드, 리뷰/승인 권한 분리, 기관 간 접근 차단, 중복 제출/동시 승인, 데이터 변경에 따른 revision을 검증한다.
- 기존 실자료 API와 화면, 신규 스키마·오류코드, Result ID와 SHA를 확인한다. 세 언어에서 동일 조건의 개체 ID·수치·단위·출처·버전·지도 SHA를 대조한다. GeoLLM의 근거 없는 숫자와 미발행 CI 반환을 차단한다.
- 운영 모드 API/Worker에 접근 가능한 로컬 원본을 함께 연결하고 DB와 S3를 각각 끊는다. 일반 UI는 열리고 영향을 받는 질의는 `BLOCKED`이며 수치·인용·지도 링크가 비어야 한다. 설정 오류, 원격 객체 검증 실패, 재시작과 연결 복구 뒤 동일 release 조회를 확인한다.
- 이전 CI 관찰 건수를 고정 기준으로 사용하지 않는다. 현행 로그로 실패·스킵·환경별 의존성을 확인하고 합성 fixture와 실자료 계약시험을 분리한다. pytest, Ruff, 프론트 타입 검사·빌드, Docker 이미지, Compose/kind와 CI 결과를 남긴다.
- Docker Compose와 kind에서 동일 샘플 캠페인→독립 판독→가중통계→Result→UI→GeoLLM 조회를 시험한다. 합성 데이터임을 모든 화면에 표시한다. 저장소 영속성, restart, queue resume, 권한, 오류처리, DB/S3 backup/restore를 확인한다.

### T3. 실자료 반텐 Pilot 및 독립 과학 검증 Gate

실제 반텐 영상으로 가능한 A/B를 먼저 검증한다. 원해상도에 해당하는 원천 밴드 또는 출력 격자가 누락되면 해당 실험만 보류한다. C축은 승인된 확률 표본·참조·판독 조건을 갖춘 범위에서 실행한다.

1. 2020 및 가능한 최신 공통연도에서 Sentinel-2 10m/Landsat 30m 제품별 고정 데이터 구축. 동일 센서 비교, 센서 간 공통지지단위 비교를 분리.
2. 동일 train/validation/holdout으로 RF/TinyUNet/DeepLabv3+ 비교. 후처리 Ablation 및 선정 기준 동결. 약한 참조 시험과 독립 과학 검증 분리.
3. Kemenhut 공식 23-class/Esri/MapBiomas 원본과 승인 crosswalk를 확보한 범위에서 교차비교. 미확보 제품은 BLOCKED.
4. 반텐 모집단·층·표본배분 설계 승인 → 실제 표본 추출 → 블라인드 판독 → 불일치 전문가 재검토 → 최종 라벨 동결. 희소 클래스·변화의 대표성을 확인.
5. 가중 OA/UA/PA, 클래스별 F1/IoU, 지도면적 및 오차보정 면적·95% CI, 변화 탐지 지표, 관측유효영역 및 제한사항을 보고.
6. 현지 전문가/기관의 과학 검토, 결과 공개 승인, 모델 승격 및 운영배포를 각각 별도 Gate에서 진행한다. 실제 독립자료가 보류되면 독립 지표·CI를 비워 두고 차단 범위와 승인에 필요한 증거를 기록한다. 공식 Kemenhut 비교가 보류돼도 별도로 승인된 독립 참조의 C축 적용 가능성은 독립적으로 판단한다.

## 12. 산출물 및 완료 보고 방식

다음 문서를 저장소에 추가/갱신한다. 기존 파일 경로 규칙을 우선 적용한다.

```text
docs/lcluc/ACCURACY_VALIDATION_STRATEGY.md
docs/lcluc/ACCURACY_SAMPLING_AND_REFERENCE_PROTOCOL.md
docs/lcluc/ACCURACY_STATISTICAL_METHODS.md
docs/lcluc/ACCURACY_API_AND_UI.md
docs/lcluc/ACCURACY_BANTEN_PILOT.md
docs/architecture/ACCURACY_STORAGE_DEPLOYMENT.md
docs/understanding/V42_LCLUC_ACCURACY_CENTER.md
docs/architecture/00_next_session_handoff.md      # 현행 인계문서 갱신
CONTINUOUS_DEVELOPMENT.md                         # 실제 완료·차단 근거 기록
```

완료 보고서는 각 A/B/C축을 다음 형식으로 제출한다.

| 기능 | 구현 파일 | 시험/증거 경로 | 상태 | 실자료 범위 | 미확보 자료 및 차단 사유 | 다음 작업 |
|---|---|---|---|---|---|---|

각 시험의 커밋 SHA, 실행환경, 명령, 결과, 실패/skip 사유, 보고서 해시를 기록한다. 실제 자료·대용량 산출물은 Git에 넣지 않고 권한 있는 Data Lake의 manifest/receipt/pin으로 연결한다. 기존 `artifacts/` 관례에 맞춰 로컬 로그/스크린샷을 보존한다. 링크가 로컬 파일이면 실제 파일 존재 여부를 확인하고 Git에 포함된 것으로 오인하지 않도록 설명한다.

최종 성공은 모든 코드가 작성된 것만으로 판단하지 않는다. **개발완료(합성·실자료 시험), 과학적 독립검증, 기관 운영 승인**을 각각 판단한다. 독립 표본을 아직 확보하지 못한 경우에도 검증센터의 기능 구현과 합성 E2E 시험을 완료하고 독립 평가 결과는 null로 표시한다. 사업 공정률·정확도 수치를 임의 추정하지 않는다.

## 13. 참고 방법론 (원문 확인 후 적용)

- MapBiomas Indonesia Collection 4.1의 후처리와 검증 절을 참고한다. [영문 ATBD 원본](https://landy.mapbiomas.id/assets/files/ATBD%20Mapbiomas%20ID%20Col%204.1%20EN.pdf)
- MapBiomas Indonesia의 범례·검증·참조 자료를 확인한다. [Legend](https://landy.mapbiomas.id/en/legendcode) · [Accuracy Assessment](https://landy.mapbiomas.id/en/accuracy-assessment) · [Reference Maps](https://landy.mapbiomas.id/en/refmap)
- Olofsson et al. (2014). 토지 변화 정확도·면적·신뢰구간의 표본·판독·분석 원칙. [저자 원고](https://nottingham-repository.worktribe.com/index.php/OutputFile/728232) · [DOI](https://doi.org/10.1016/j.rse.2014.02.015)
- Stehman (2014). 층화 기준과 지도 클래스가 다를 때의 추정. [논문](https://doi.org/10.1080/01431161.2014.930207)
- Stehman & Foody (2019). 토지피복 정확도 검증의 독립성·대표성·재현성. [저자 원고](https://nottingham-repository.worktribe.com/preview/2307002/AccuracyReview_Final_Submitted.pdf)
- 기존 SDSS `docs/lcluc/ANNUAL_INTAKE.md`, `BANTEN_MODEL_TRIALS.md`, `POSTPROCESS_QUALITY.md`, `BANTEN_MAPBIOMAS_AREA_COMPARISON.md`, `docs/mlops/TRAINING_ACCURACY_DEPLOYMENT_GATES.md`.

**사용자가 이 프롬프트의 개발 실행을 요청하면 §10의 기준선 감사부터 시작한다. 첫 구현 범위는 기존 공통 결과 경로와 연결되는 소형 반텐 합성 캠페인이다. 실자료·과학 검토·기관 공개 승인으로 확대할 시점은 각 단계의 증거로 판단한다.**
