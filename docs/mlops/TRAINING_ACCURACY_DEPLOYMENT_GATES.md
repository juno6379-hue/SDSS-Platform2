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

이 모듈의 시험은 합성 증거를 사용한다. 현재 Sentinel 공간피복 7.711080%를 입력하면 `SPATIAL_COVERAGE_INSUFFICIENT`로 학습을 차단한다. 실제 학습·독립정확도 산출·registry 등록·배포는 실행하지 않았다.
