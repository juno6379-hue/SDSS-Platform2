# 학습·독립정확도·배포 Gate

상태: `TESTED_SYNTHETIC`

## 목적

패치 수량만 충족했다고 학습이나 배포를 시작하지 않는다. `services/mlops/gates.py`는 다음 증거를 모두 검증한다.

- One Map 6개 주와 36개 주·연도 셀 완전성
- Sentinel-2 B02/B03/B04/B08/B11/B12와 SCL 동시 존재
- 실제 경계 내부 공간피복과 유효 픽셀 비율
- train/validation/test 수량과 공간·장면 group 누출 방지
- 원본 파일·manifest·ledger SHA-256
- 독립 지상정답의 공간 holdout·동년 정합·라벨 원천 분리
- 모델·학습보고서·registry·환경 해시, 보안검사, rollback 시험, 운영 승인

## 약한 참조와 독립정확도

WorldCover 2021, Esri, Dynamic World, KLHK와의 비교는 출처·연도·독립성 조건에 따라 약한 참조 일치도일 수 있다. `weak_reference`나 `pseudo_label` 결과는 수치가 높아도 배포 Gate를 열 수 없다. 다른 연도의 WorldCover 2021을 독립 정답으로 사용하지 않는다.

## 현재 판정

정책 시험은 합성 증거를 사용한다. 2026-11-25 고정 후보 1,779행을 원본 `scene_id`로 감사한 결과, 동일 장면이 반텐 validation 16행과 서자바 test 12행에 존재했다. 주별 `source_group`을 따로 검사하면 이 충돌을 놓칠 수 있다. 원본 장면과 공간 그룹을 기준으로 split을 재구성하고 독립 라벨·공간 중첩 검증을 완료해야 한다. [고정 감사 결과](../../evidence/models/scene-split-audit-20261125.json)

공통 결과 원장에는 `BLOCKED`인 감사 증거를 등록했다. 실제 학습, 독립 정확도 산출, 운영 모델 등록과 배포는 각 승인 조건이 충족되어야 한다.


## 모델 버전 실행과 다음 검증

동일 원본 장면을 격리한 새 후보에서 원본 장면 ID 충돌이 0건이다. 공간 중첩과 현재 6개 주 피복, 독립 정확도는 검증 대상이다. [후보 고정 보고서](../../evidence/models/scene-quarantine-candidate-20261125.json)

실행기는 승인된 고정 모델 버전을 실제 ONNX CPU 세션에 연결한다. 합성 두 버전에서 활성화·롤백 후 출력 11→12→11을 시험했다. 실제 특화 모델의 승인 및 배포 기록은 비어 있다. [운영 실행과 승인 API](../architecture/PLATFORM2_OPERATION_PATH.md)
