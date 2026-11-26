# 반텐 실자료 분류·변화 모델과 특화 분류 접수

## 분류와 동일 표본 검증

2020년 반텐 Landsat C2 L2 6밴드 합성과 동년 Esri / Impact Observatory v003을 약한 참조로 사용한다. RF의 클래스별 고정 시드 표본을 재현한 19,647개 학습 픽셀과 동일 공간 홀드아웃 72,391개를 사용했다. 48×48 픽셀 블록은 학습과 평가에 걸치지 않는다. Tiny U-Net은 블록 안 영상의 공간 문맥을 보며 학습 손실은 RF와 같은 라벨 위치에만 적용한다. RF의 독립 공간 블록 혼동행렬을 원래 증거와 대조해야 비교가 성립한다.

두 센서에서 RF, Tiny U-Net, DeepLabv3+를 비교했다. DeepLabv3+는 6밴드 경량 인코더, ASPP, 저수준 공간 특징을 사용하는 디코더를 사전학습 가중치 없이 10 epoch로 학습했다. Sentinel-2는 반텐 2020 합성에서 19,553개 학습 픽셀과 76,230개 평가 픽셀을 사용했다. 센서별로 세 모델의 평가 픽셀을 고정했으며, 두 센서의 유효 픽셀 집합은 다르다. 격자는 약 147m 표시용이고 클래스 6개가 시험에 포함됐다. [DeepLabv3+ 원 논문](https://arxiv.org/abs/1802.02611)

| 모델 | Landsat 일치도 / 평균 IoU | Sentinel-2 일치도 / 평균 IoU |
|---|---:|---:|
| Random Forest | 71.42% / 36.27% | 70.39% / 34.75% |
| Tiny U-Net | 66.34% / 29.04% | 57.88% / 23.93% |
| DeepLabv3+ | 67.76% / 31.31% | 63.74% / 24.76% |

전체 일치도와 평균 IoU·Macro F1을 함께 보면 면적이 큰 수목에 평가가 치우치는지 확인할 수 있다. 이 시험은 동년 Esri 약한 참조에 대한 모델 비교다. 동년 독립 표본이 준비되면 별도 정확도를 검증한다. 공간 필터 화면에서 각 모델을 선택해 같은 홀드아웃의 보정 전·후 지표, Swipe, 마스크, 면적과 GeoTIFF를 검토할 수 있다.

`GET /api/lcluc/postprocess/benchmarks/{sensor}`에서 `landsat` 또는 `sentinel-2`를 조회한다. 각 모델의 평가 픽셀 수, 혼동행렬, 클래스별 F1·IoU, SHA-256으로 검증하는 분류 GeoTIFF 링크를 반환한다. 기존 LCLUC의 Landsat에는 **AI 모델 비교**, Sentinel-2에는 **AI 신규 분류**에 연결한다. 연차 토지피복도는 Esri 발행 분류를 표시하며 시험 분류는 별도 후보로 제공한다.

`python -m services.lcluc.banten_deeplab_trials landsat --epochs 10`과 `python -m services.lcluc.banten_deeplab_trials sentinel-2 --epochs 10`으로 학습을 재현한다. Sentinel-2 실행은 세 모델을 훈련한다. 분할 마스크와 입력 자료의 해시는 보고서에 고정한다. [Landsat 학습 로그](../../artifacts/lcluc/banten-deeplab-landsat.log) · [Sentinel-2 학습 로그](../../artifacts/lcluc/banten-deeplab-sentinel.log)

같은 3픽셀·8방향 공간 필터에서 RF는 71.42→75.09%와 31,658 보정 픽셀, Tiny U-Net은 66.34→66.49%와 1,885 보정 픽셀을 기록했다. 두 실행의 비교 표본은 각각 72,391개다. [Edge 실행 기록](../../artifacts/lcluc/banten-models-knowledge-edge.log)

DeepLabv3+에는 같은 설정으로 Landsat 67.7584→67.9670%와 1,865 보정 픽셀, Sentinel-2 63.7413→63.8725%와 1,360 보정 픽셀을 확인했다. Edge에서 두 후보의 실행과 평가 픽셀 수 보존을 검사했다. [Edge 시험](../../artifacts/lcluc/banten-deeplab-area-edge.log)

## Siamese U-Net

구름 마스크가 적용된 반텐 2020·2025 Sentinel-2 6밴드 합성을 공통 격자에서 비교한다. 공유 인코더의 각 단계에서 두 관측의 절대 차이를 사용하고, 변경 여부 2개 클래스를 예측한다. 두 연도의 동년 Esri 분류 코드 차이가 약한 참조다. 학습·임계값 선택·최종 평가는 서로 다른 공간 블록에서 한다. 3픽셀·8방향 공간 필터 전·후에는 같은 평가 픽셀을 사용하며 원래 관측 결측은 유지한다. 후보 GeoTIFF 값은 0 유지, 1 변화 후보, 255 NoData다. 날짜 간 차이의 위치를 알려주며 개별 변화의 발생 날짜는 측정하지 않는다. [Siamese 변화탐지 원 논문](https://arxiv.org/abs/1810.08462)

14 epoch 시험은 검증 63,299픽셀에서 변화 판정 임계값 0.575를 선택했다. 별도 평가 64,658픽셀의 변화 클래스 F1은 공간 필터 전 0.288265, 후 0.288352다. 이 수치는 실자료 후보의 약한 참조 검증이며 운영 승격 근거로 삼기에는 추가 독립 검증이 필요하다. [학습 기록](../../artifacts/lcluc/banten-siamese-calibrated.log)

`python -m services.lcluc.banten_model_trials tiny --epochs 10`, `python -m services.lcluc.banten_model_trials siamese --epochs 14`로 재현한다. 데이터·참조·모델 파일의 SHA-256과 요약 평가는 `data/curated/explorer/banten-province/landsat-explore/` 아래 보고서에 있다. 모델 텐서는 실행 코드를 포함하지 않는 NPZ다.

## 인도네시아 특화 분류와 계층 통합

맹그로브·양식장, 논, 팜유·목재조림의 세 그룹은 각각 RF를 학습할 수 있도록 구현했다. 학습은 6밴드 유효 표본과 조사된 배경 코드 0, 각 그룹의 대상 클래스 표본을 요구한다. 출력 105·131·140·135·109는 SDSS의 구분 코드다. MapBiomas 원래 코드 5·31·40·35·9와의 대응은 명시적으로 관리하며, Esri 기본 코드는 그대로 보존한다.

`data/raw/annual-lcluc/specialists/banten/2020/integration.json`에 `year`, `base_sha256`, `approval_id`, 우선순위 순서의 `layers`를 등록한다. 각 레이어는 `class_code`, `year`, `label_year`, `source_id`, `provider`, `uri`, `version`, `license`, `acquired_at`, `model_sha256`, SHA와 길이를 가진 `mask`·`training_labels` 파일 pin을 요구한다. 마스크는 기본 모델과 정확히 동일한 격자의 0/1/255다. 기본 분류가 호환되는 곳에만 우선순위순으로 특화 클래스를 덮고 NoData를 보호하며 겹침 픽셀을 기록한다. 결과는 검토 후보로 보관한다.

기존 반텐 MapBiomas 4.1 통계 XLSX는 주 단위 면적 자료다. 동년 특화 학습용 픽셀 라벨이나 승인된 특화 분류 마스크가 아직 접수되지 않았다. 공식 Collection 4.1은 GEE 등록 경로를 제공하며 현 환경에 GEE 자격증명이 없다. 확인한 Collection 3의 2020 공개 객체 HEAD는 403을 반환했다. [MapBiomas GEE 안내](https://landy.mapbiomas.id/en/gee) · [직접 다운로드 안내](https://landy.mapbiomas.id/en/collectionmap)

`GET/POST /api/lcluc/postprocess/hierarchy`에서 검증 상태와 시험 실행을 제공한다. GeoAI Toolbox는 등록된 레이어를 표시하며, 조건이 충족되면 통합 GeoTIFF를 만들 수 있다.
