# 반텐 LCLUC 모델 시험과 특화 분류 계층 통합 이해자료

- updated_at: 2026-11-26 KST
- source_commit: `UNCOMMITTED_WORKTREE`
- evidence_paths:
  - `docs/lcluc/BANTEN_MODEL_TRIALS.md`
  - `services/lcluc/banten_model_trials.py`
  - `services/lcluc/banten_deeplab_trials.py`
  - `services/lcluc/classification_trials.py`
  - `services/lcluc/deeplab.py`
  - `services/lcluc/specialists.py`
  - `services/api/lcluc_postprocess.py`
  - `frontend/src/LclucPostprocess.tsx`
  - `tests/lcluc/test_model_trials.py`
  - `artifacts/lcluc/banten-model-trials.log`
  - `artifacts/lcluc/banten-siamese-calibrated.log`
  - `artifacts/lcluc/banten-deeplab-landsat.log`
  - `artifacts/lcluc/banten-deeplab-sentinel.log`
  - `artifacts/lcluc/banten-deeplab-area-edge.log`
  - `artifacts/lcluc/banten-models-knowledge-edge.log`
- overall_status: `VERIFIED_REAL`

## 1. 쉬운 설명

### 한 문장으로

반텐 실자료에서 두 센서의 Random Forest, Tiny U-Net, 경량 DeepLabv3+와 두 시점 Siamese U-Net 후보를 고정 공간 표본으로 비교하고, 동년 특화 분류층을 승인 순서대로 합치는 계약까지 연결했다.

### 현재 확인된 범위

- `VERIFIED_REAL`: 2020 Landsat 6밴드와 동년 Esri v003으로 RF와 Tiny U-Net을 같은 19,647개 학습 표본과 72,391픽셀 공간 홀드아웃에서 비교했다. 약한 참조 일치도는 RF 71.4205%, Tiny U-Net 66.3356%다.
- `VERIFIED_REAL`: 경량 DeepLabv3+의 Landsat 약한 참조 일치도는 같은 72,391픽셀에서 67.7584%, 평균 IoU 31.31%다. 3픽셀·8방향 Spatial Filter 뒤 67.9670%가 되었고 1,865픽셀이 바뀌었다.
- `VERIFIED_REAL`: Sentinel-2는 같은 센서 안에서 19,553개 학습 표본과 76,230픽셀 홀드아웃을 고정했다. RF 70.3883%, Tiny U-Net 57.8801%, DeepLabv3+ 63.7413%이며 DeepLabv3+ 필터 뒤 63.8725%, 1,360픽셀 변경을 확인했다.
- `VERIFIED_REAL`: 3픽셀·8방향 Spatial Filter 뒤 RF는 75.09%로, Tiny U-Net은 66.49%로 바뀌었다. 변경 픽셀은 각각 31,658개와 1,885개다.
- `VERIFIED_REAL`: 2020→2025 Sentinel-2 Siamese U-Net은 64,658픽셀 홀드아웃에서 변화 클래스 F1 0.288265를 기록했고 같은 필터 뒤 0.288352를 기록했다.
- `VERIFIED_REAL`: Edge에서 RF·Tiny의 같은 72,391 표본, 전후 Swipe, Siamese 변화 지도와 계층 통합 입력 차단을 확인했다.
- `TESTED_SYNTHETIC`: 특화 분류 우선순위·충돌 감사·NoData 보호·타년 라벨 거부 계약을 검사했다. 별도 파일 기반 통합 시험에서 같은 격자의 GeoTIFF를 만들고 11픽셀을 통합했으며 원본 SHA와 NoData를 유지했다.
- `BLOCKED`: 특화 분류용 승인 동년 픽셀 라벨과 실제 출력층은 확보 대기다. GEE 인증이 없고 공개 Collection 3 객체 HEAD는 403이었다.
- `BLOCKED`: 모든 수치는 Esri 동년 약한 참조 또는 그 변화 참조를 이용한 개발 지표다. 독립 정확도와 운영 모델 승인은 미측정·미승인 상태다.

## 2. 이론적 배경

### 2.1 공간 블록 홀드아웃

인접 픽셀은 스펙트럼과 토지피복이 비슷하다. 픽셀을 무작위로 섞으면 학습 위치의 이웃이 평가에 들어갈 수 있다. 구현은 48×48 표시 격자 블록 전체를 학습 또는 평가 한쪽에 배정해 공간 누출을 줄인다. RF와 Tiny U-Net은 같은 72,391픽셀 홀드아웃을 사용하므로 모델 간 비교의 지지집합이 같다.

### 2.2 RF, Tiny U-Net과 경량 DeepLabv3+

RF는 픽셀별 여섯 밴드 특성을 분기 규칙의 집합으로 분류한다. Tiny U-Net은 주변 공간 문맥을 함께 학습하되 손실은 고정 학습 표본 위치에서만 계산한다. 복잡한 모델이 항상 높은 약한 참조 일치도를 보장하지 않으며, 이번 실험에서는 RF가 더 높은 값을 보였다.

경량 DeepLabv3+는 여섯 밴드 encoder, 서로 다른 dilation의 문맥을 모으는 ASPP, 저수준 공간 특징을 결합하는 decoder로 구성한다. 사전학습 가중치 없이 10 epoch를 실행했다. Landsat과 Sentinel-2는 각 센서 내부에서 세 모델이 같은 학습·평가 표본을 사용한다. 센서별 유효 픽셀이 달라 Landsat 72,391과 Sentinel-2 76,230을 서로 같은 픽셀 표본으로 해석하지 않는다.

### 2.3 Siamese U-Net 변화 후보

Siamese 구조는 2020과 2025 영상을 같은 encoder로 처리한 뒤 두 특징의 절대 차이를 사용한다. 출력은 변화 없음 0, 변화 1, NoData 255다. 임계값은 학습·최종 홀드아웃과 분리한 보정 블록에서 0.575로 선택했다. 변화 클래스 F1은 변화 픽셀의 precision과 recall 조화평균이다.

### 2.4 특화 분류와 계층 통합

해안·논·플랜테이션처럼 일반 분류가 어려운 주제를 별도 후보층으로 만들 수 있다. 현재 세 그룹과 출력 코드는 해안 105·131, 논 140, 플랜테이션 135·109다. 통합은 기본 지도와 같은 연도·격자·SHA를 요구하고 승인된 우선순위에서 먼저 선택된 후보를 유지한다. NoData와 비대상 기본 클래스는 보호하고 중복 적격 픽셀은 감사 수치로 남긴다.

## 3. 코드·데이터 동작

### 3.1 모델 시험 흐름

1. `banten_model_trials.py`가 고정 Landsat·Sentinel·Esri 자산의 byte와 SHA를 검사한다.
2. 48×48 블록으로 학습·보정·최종 홀드아웃을 분리한다.
3. `tiny_trial()`은 2020 Landsat 여섯 밴드와 동년 Esri 코드를 사용한다.
4. `banten_deeplab_trials.run()`은 센서별 고정 split에서 RF·Tiny U-Net·DeepLabv3+를 실행한다.
5. `classification_trials.py`는 두 센서 × 세 모델의 보고서·GeoTIFF registry를 고정한다.
6. `siamese_trial()`은 2020·2025 Sentinel 여섯 밴드와 두 해 Esri 코드 차이를 사용한다.
7. 가중치·분류 GeoTIFF·미리보기·입력 pin·평가 지표를 보고서에 기록한다.
8. API와 UI가 센서별 세 모델 비교, Spatial Filter, Siamese 원본·필터 지도와 다운로드를 제공한다.

### 3.2 특화층 접수와 통합

`SpecialistIntake`는 기준 연도, 기본 지도 SHA, 승인 ID, 각 층의 출처·라이선스·취득시각·분류코드·라벨 연도·mask SHA·모델 SHA를 검사한다. `merge()`는 우선순위와 적격 기본 클래스를 적용한다. `integrate()`는 기본 GeoTIFF를 덮어쓰지 않고 새 결과와 보고서를 `data/curated/lcluc/hierarchy/{run_id}`에 쓴다.

| API | 역할 |
|---|---|
| `GET /api/lcluc/postprocess` | RF·Tiny·Siamese 모델 및 후처리 이력 조회 |
| `POST /api/lcluc/postprocess/runs` | RF 또는 Tiny Spatial Filter 실행 |
| `GET /api/lcluc/postprocess/benchmarks/{sensor}` | Landsat 또는 Sentinel-2의 RF·Tiny·DeepLab 비교와 혼동행렬 조회 |
| `GET /api/lcluc/postprocess/benchmarks/{sensor}/{method}/classification` | SHA 검증된 여섯 분류 GeoTIFF 다운로드 |
| `GET /api/lcluc/postprocess/siamese/{kind}` | Siamese 미리보기·분류·필터 결과 조회 |
| `GET /api/lcluc/postprocess/hierarchy` | 특화층 접수 상태와 세 그룹 조회 |
| `POST /api/lcluc/postprocess/hierarchy` | 동년 승인 manifest가 있을 때 계층 통합 실행 |
| `GET /api/lcluc/postprocess/hierarchy/{run_id}/classification` | 통합 GeoTIFF 다운로드 |

## 4. 시험 증거와 상태

| 항목 | 상태 | 증거와 범위 |
|---|---|---|
| RF·Tiny 동일 실자료 비교 | `VERIFIED_REAL` | 학습 19,647, 홀드아웃 72,391, 71.4205%와 66.3356% 약한 참조 일치도 |
| Landsat DeepLabv3+ | `VERIFIED_REAL` | 학습 19,647, 홀드아웃 72,391, 67.7584%·mIoU 31.31%, 필터 뒤 67.9670%·1,865픽셀 |
| Sentinel-2 세 모델 비교 | `VERIFIED_REAL` | 학습 19,553, 홀드아웃 76,230, RF 70.3883%·Tiny 57.8801%·DeepLab 63.7413% |
| Sentinel-2 DeepLab 후처리 | `VERIFIED_REAL` | 63.7413%→63.8725%, 1,360픽셀, 같은 76,230 표본 |
| benchmark API·여섯 GeoTIFF | `VERIFIED_REAL` | 두 센서 API, 2×3 report와 SHA 고정 분류 자산 |
| RF·Tiny Spatial Filter | `VERIFIED_REAL` | 3픽셀·8방향, RF 75.09%·31,658픽셀, Tiny 66.49%·1,885픽셀 |
| Siamese 변화 후보 | `VERIFIED_REAL` | 64,658픽셀, 변화 F1 0.288265→0.288352 |
| 실제 Edge 검토 | `VERIFIED_REAL` | 모델 표본·Tiny 전후·Siamese 지도·계층 입력 차단 |
| 모델·RAG 관련 회귀 | `TESTED_SYNTHETIC` | 24 pytest PASS |
| 파일 기반 계층 통합 | `TESTED_SYNTHETIC` | 별도 1 PASS, 같은 격자, 11픽셀, 원본 SHA·NoData 유지 |
| 실제 특화층 접수 | `BLOCKED` | 동년 승인 라벨·mask 미확보, GEE 인증 없음, 공개 객체 HEAD 403 |
| 독립 정확도·운영 승인 | `BLOCKED` | 독립 현장·전문가 정답과 모델 release 승인 미확보 |

## 5. 발표 스크립트

### 1분

“반텐 2020 실자료에서 두 센서별로 RF, Tiny U-Net, 경량 DeepLabv3+를 같은 공간 표본에서 비교했습니다. Landsat 홀드아웃 72,391픽셀의 약한 참조 일치도는 71.42%, 66.34%, 67.76%이고 Sentinel-2 홀드아웃 76,230픽셀에서는 70.39%, 57.88%, 63.74%입니다. DeepLabv3+ 공간 필터 뒤 Landsat은 67.97%, Sentinel-2는 63.87%였습니다. Edge에서 여섯 GeoTIFF, 모델 비교와 후처리 실행을 확인했습니다. 2020→2025 Siamese 후보와 동년 특화층 계층 계약도 별도 검증했습니다. 모든 모델 수치는 Esri 약한 참조 기반이며 독립 정확도와 운영 승인은 별도 Gate입니다.”

### 5분 핵심 순서

1. 센서별 같은 공간 블록 홀드아웃으로 RF·Tiny·DeepLabv3+를 비교한다.
2. 고정 실자료·라벨·split·모델 SHA를 보고서에 남긴다.
3. 같은 Spatial Filter로 모델별 전후를 비교한다.
4. Siamese는 두 시점의 공유 encoder 특징 차이로 변화 후보를 만든다.
5. 임계값 보정 블록과 최종 홀드아웃을 분리한다.
6. 특화층은 동년·동일 격자·기본 SHA·승인 ID를 필수로 한다.
7. 우선순위, 적격 기본 클래스, NoData 보호, 충돌 감사를 적용한다.
8. 수치는 Esri 약한 참조 일치도로 보고하고 독립 정확도와 운영 승인을 분리한다.

## 6. Q&A

**Q. RF 71.42%와 Tiny 66.34%는 독립 정확도입니까?**

동년 Esri v003과 비교한 약한 참조 일치도다. 독립 현장·전문가 표본 정확도는 미측정이다.

**Q. Tiny U-Net의 값이 낮으면 구현 실패입니까?**

같은 홀드아웃에서 실제 비교가 재현됐다는 개발 증거다. 모델 채택은 독립 평가, 클래스별 성능, 운영 목적과 승인 기준으로 결정한다.

**Q. Landsat과 Sentinel-2 모델 수치를 직접 순위로 비교할 수 있습니까?**

각 센서 내부의 세 모델은 같은 표본을 사용한다. Landsat은 72,391픽셀, Sentinel-2는 76,230픽셀로 유효 지지집합이 달라 센서 간 수치에는 입력·표본 차이가 함께 반영된다.

**Q. DeepLabv3+는 사전학습 모델입니까?**

이번 경량 구현은 여섯 밴드 입력과 ASPP·decoder를 사용하고 사전학습 가중치 없이 10 epoch로 실행했다.

**Q. Siamese F1 0.288352를 운영 변화 탐지로 사용할 수 있습니까?**

Esri 연차 지도 차이를 약한 참조로 사용한 후보 지표다. 운영 활성화에는 독립 변화 정답, 오류 분석과 승인된 release가 필요하다.

**Q. 특화 모델은 현재 실제로 합쳐졌습니까?**

파일 기반 합성 시험에서 11픽셀 통합과 원본 SHA·NoData 보호를 확인했다. 실제 동년 승인 라벨과 출력층 접수는 `BLOCKED`다.

**Q. 다른 연도 라벨을 사용할 수 있습니까?**

접수 계약은 `layer.year`, `label_year`, 계획 연도가 같을 때만 허용한다. 타년 라벨은 시험에서 거부됐다.
