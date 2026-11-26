# LCLUC 분류 기준 모델과 비교 실행

Random Forest와 Tiny U-Net을 CPU에서 실제 학습·추론하는 코드가 `services/lcluc/classifiers.py`에 있다. 두 모델은 같은 학습 분할과 정규화 값을 사용한다. 모델 선택은 validation의 평균 IoU로 하고, 두 모델의 최종 평가는 같은 test 타일과 같은 유효 라벨 픽셀에서 수행한다.

## 입력과 분류체계

- `ClassificationDomain.from_taxonomy(taxonomy)`는 공식 분류체계의 버전·SHA-256과 원본 클래스 코드를 보존한다. KLHK 23개 코드 가운데 구름 `2500`은 품질 항목으로 분리하고, 22개 주제 클래스를 모델의 출력 대상으로 사용한다. 배열의 구조적 NoData는 `65535`다.
- `SceneTile`은 B02/B03/B04/B08/B11/B12 순서의 Sentinel-2 배열, 원본 SHA, 밴드별 반사도 scale/offset과 정규화 근거 SHA를 요구한다. 영상, SCL, 라벨은 같은 좌표계·변환·격자로 정렬된 입력을 받는다. 입력 데이터를 읽거나 재투영하는 작업은 호출자가 수행한다.
- SCL은 별도 2차원 마스크다. 검증 작업에서는 식생·나지·수역으로 분류된 코드 4·5·6과 여섯 밴드가 모두 유효한 픽셀을 채택한다. 미분류·구름·그림자·NoData를 제외한다. 라벨 측 QA와 NoData는 학습·평가에서 추가로 제외한다. 영상·라벨 원본은 바꾸지 않는다.
- 좌표는 미터 단위의 공통 투영 좌표계에서 검사한다. 동일한 scene ID·원본 해시 또는 면적을 공유하는 타일을 여러 분할에 넣으면 학습을 차단한다. 영상 연도와 라벨 연도는 같아야 한다. 미래 연도 홀드아웃을 명시한 경우 학습·검증 연도가 시험 연도보다 앞서야 한다. ESA WorldCover v200/2021은 2021년 참조에 사용한다.

## 학습·추론 호출

`fit_compare(patches, domain=domain, settings=settings, readiness=readiness, approval=approval)`는 `Comparison(models, report)`를 반환한다. 패치는 `TrainingPatch(tile, labels, reference, split)`이고, 분할 값은 `train`, `validation`, `test`다. `LabelSource`는 출처·버전·연도·자료 SHA·분류체계 SHA·자료 유형과 원본 NoData를 받는다. 라벨과 SCL에 각각 좌표계와 Affine 변환을 전달하고 영상과의 일치를 검사한다.

- 학습 시작 전에 승인된 분류체계, 기존 `DataReadiness` 정책, 승인된 manifest SHA, `dataset_sha256(patches)`로 구한 실제 배열·메타데이터·분할 지문이 필요하다. 정규화 평균과 표준편차는 학습 분할의 유효 라벨 픽셀에서 구한다.
- Random Forest는 픽셀별 스펙트럼을 사용한다. 기본 48개 트리를 고정 시드로 학습하며 클래스별 픽셀 상한을 둔다. Tiny U-Net은 6채널 입력과 주변 공간 문맥을 사용하고, 같은 학습 분할의 유효 라벨 영역에서 교차 엔트로피를 최소화한다. 실제로 사용한 클래스별 표본 수와 실행 버전을 보고서에 남긴다.
- `models["random_forest"].predict(tile)` 또는 `models["tiny_unet"].predict(tile)`에서 원본 분류 코드 래스터, 유효 마스크, 클래스별 확률, 최대 확률, 정규화 범주 엔트로피를 얻는다. 최대 확률과 엔트로피는 미보정 진단값이다.
- `model.artifact_bytes()`는 JSON 메타데이터와 수치 배열을 담은 NPZ를 만든다. `load_artifact(raw, expected_sha256)`은 해시·배열 크기·트리 구조 또는 U-Net 텐서 형식을 검사한다. 모델 복원에서 Python 객체 피클은 사용하지 않는다. 운영 등록·승격·배포는 별도다.

## 비교 근거와 상태

반텐 2020 Landsat·Sentinel-2 실영상과 동년 Esri 약한 참조를 사용한 별도 시험에서 RF, Tiny U-Net, 경량 DeepLabv3+를 비교했다. 공간 홀드아웃은 Landsat에 72,391픽셀, Sentinel-2에 76,230픽셀이다. [반텐 실자료 모델과 후처리 비교](BANTEN_MODEL_TRIALS.md)

`lcluc-classifier-comparison/1` 보고서에 입력과 모델 SHA·분류 코드 순서·분할 타일·유효 피복·혼동행렬·클래스별 F1·IoU를 남긴다. 검증 평균 IoU가 같으면 모델 이름 순서를 적용한다. 참조 라벨 평가에는 전체 참조 일치도를 기록한다. 독립 평가에는 학습·검증과 출처·해시가 분리된 같은 연도의 시험 정답을 요구한다. 수치가 생겨도 별도 품질 검토·과학 승인 없이는 `scientific_accuracy_validated`나 `release_approved`를 설정하지 않는다.

- `TESTED_SYNTHETIC` Random Forest와 Tiny U-Net을 CPU에서 실제 학습해 같은 합성 시험 유효 252픽셀에서 비교했다. 두 모델의 평균 IoU가 0.50 이상이며, 두 분류 코드 보존, 유효 마스크, 확률 합계, 모델 NPZ 해시와 저장·복원 검사를 포함해 12개 시험을 통과했다. 별도 Tiny U-Net 합성 실행의 평균 IoU는 1.0이었다. 합성 평가의 독립 정확도 필드는 비어 있다.
- `BLOCKED` 실제 연차 자료의 승인·라이선스·독립 라벨·전체 주제 클래스 표본과 물리적인 데이터 준비가 남아 있다. 현재 결과는 기관 승인·실제 모델 게시 근거가 아니다.
- `VERIFIED_REAL` 반텐 2020의 센서별 비교와 2020→2025 Siamese U-Net 변화탐지 시험을 재현했다. [분류·변화 시험](BANTEN_MODEL_TRIALS.md)
- `PLANNED` 전 연도 DeepLabv3+ 운영 파이프라인, 장기 시나리오 및 분류 확률 보정.

로컬 검증 명령

```powershell
python -m pip install -e ".[dev,lcluc-ml]"
python -X utf8 -m pytest -o addopts= -q tests/lcluc/test_classifiers.py
python -m ruff check services/lcluc/classifiers.py tests/lcluc/test_classifiers.py
```
