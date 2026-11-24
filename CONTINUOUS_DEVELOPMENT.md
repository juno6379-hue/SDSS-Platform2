# SDSS-Platform2 지속 개발 원장

## 2026-11-24 현재 상태

상태 라벨은 `VERIFIED_REAL`, `TESTED_SYNTHETIC`, `IMPLEMENTED_UNVERIFIED`, `BLOCKED`, `PLANNED`만 사용한다.

- `VERIFIED_REAL` One Map 6개 주 x 2020~2025년 36셀 감사 완료. 1,779개 패치, 1,407개 품질 적격 패치, 119개 parent frame을 검증했다.
- `VERIFIED_REAL` 6밴드와 같은 장면 SCL 동시 공간피복은 0.976741%, clear 피복은 0.889803%다. 전체 공간수집 완료는 `false`다.
- `VERIFIED_REAL` 검증 자료 6,125개 객체, 3,904,601,927바이트를 `data/raw/migrated/{sha256}`에 독립 복사했다. 원본 CAS와 기존 manifest는 불변이다.
- `VERIFIED_REAL` 공유 전역원장 adapter, 고정 scene/asset/window planner, 제한 Range 전송기를 구현하고 East Java 2023 한 창의 동일 장면 6밴드+SCL pilot을 수행했다. QA clear 65,536/65,536, 본문 7,471,506바이트, 28요청, 오류·관측된 429는 0건이다.
- `VERIFIED_REAL` pilot 정산 뒤 전역원장 SHA는 `b257db2925e5c4eac99081c5539216314c972d49dd6741f38f5780da7dd25de1`, 잔여 예산은 1,678,521,030바이트다. 후속 pilot·collector·lock은 모두 0이다.
- `BLOCKED` exact 누락 큐는 72개 feature이며 pilot 뒤 36셀 공간피복 aggregate는 아직 재감사하지 않았다. 기존 0.976741%는 pilot 전 snapshot이고, 한 창 성공은 전체 수집 완료가 아니다.
- `VERIFIED_REAL` CCKP CDD 표본의 Indonesia 개발 bbox 면적가중 평균은 40.9122148174 days다. 행정경계 평균·전망·독립 정답이 아니다.
- `IMPLEMENTED_UNVERIFIED` 기후 보고서 로컬 검토 VectorDB는 7문서/122청크다. hash embedding 품질, 라이선스 공개 범위, steward 인증이 미완료다.
- `BLOCKED` KLHK native 23개 클래스 domain·라이선스, 독립 지상 정답, 실제 모델 학습·독립 정확도·사람 승인·운영 배포가 미완료다.
- `VERIFIED_REAL` 로컬 API/UI를 Edge에서 기능별로 클릭 검증했다. 읽기 전용 화면이며 collector·학습·배포를 시작하지 않는다.

## 활성 작업

1. 완료된 단일 pilot의 evidence를 API/UI evidence lock과 `docs/understanding/`에 인계한다.
2. pilot 관측을 포함해 36셀 공간피복 aggregate를 재감사하는 별도 Gate를 준비한다.
3. 전체 누락 큐 317,455,915바이트는 계획 메타데이터 기준이고 실제 원격 COG 전송량과 다르므로, 잔여 1,678,521,030바이트로 전체 수집 가능하다고 가정하지 않는다.
4. 추가 원격 수집은 BIG 권한·공간피복 목표·예산 승인을 받은 뒤 공유 원장 예약을 통해서만 수행한다.

## 다음 Gate

1. BIG 경계의 권한·시점·통계 사용 승인.
2. 6개 주 x 6개 연도의 6밴드+SCL 공간피복 목표와 현실적인 예산 승인.
3. KLHK 연차 원본의 23개 클래스 domain, 라이선스, 버전·취득시각 고정.
4. immutable dataset/split, leakage 0, 독립 정답을 이용한 실제 학습·평가.
5. 약한 참조 일치도와 독립 정확도를 분리한 사람 승인·rollback·배포.
6. 승인된 embedding과 ACL을 적용한 운영 VectorDB 및 공개/비공개 검색 경계.

## 보고 원칙

- 실제 프로세스, 에이전트, 예약 상태를 구분한다.
- 패치 개수만으로 공간수집 완료를 주장하지 않는다.
- WorldCover 2021을 다른 연도의 정답으로 사용하지 않는다.
- 실제 독립 정확도와 약한 참조 일치도를 분리한다.
- UI·문서·단일 Gate 완료를 전체 프로젝트 완료로 보고하지 않는다.
