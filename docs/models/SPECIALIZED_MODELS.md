# 전문 모델 계약·카탈로그·검증 기록

기준: 2026-11-24, `E:\SDSS-Platform2`. 기존 저장소는 읽기 전용으로 검사했다.
이 문서는 모델 계약과 개발 진단의 완료를 기록한다. 세 유형 모두 실제 운영 추론·학습·배포는 `BLOCKED`이다.
독립 OA/F1/mIoU는 생성하지 않았으며 상태 JSON의 `independent_metrics`는 `null`이다.

## 1. 개발 순서와 구현 경로

1. `AGENTS.md`, `docs/architecture/V42_EXECUTION_PLAN.md`, `services/mlops/gates.py`를 읽고 공통 Gate를 변경하지 않는 연결 방식을 선택했다.
2. `services/models/catalog.py`에 Pydantic v2 manifest/input signature/artifact 계약을 구현했다. canonical JSON SHA-256으로 입력 서명을 고정하며 알 수 없는 파일/환경/클래스 대응은 `null`로 남긴다. registry 등록은 `Draft`만 허용하고 동일 ID/version 덮어쓰기를 거부한다. 등록만으로 파일 검증이나 운영 승인을 뜻하지 않는다.
3. `services/models/readiness.py`에서 공통 LCLUC training/deployment Gate를 재사용했다. 추가 클래스 대응·균형·아티팩트 누락·운영 실행기 미구현을 차단한다. 기후 feature와 RAG에 LCLUC의 6밴드/OA 기준을 오용하지 않고 유형별 정책 부재를 명시적으로 차단한다.
4. `services/models/adapters.py`에 소형 합성 LCLUC 마스크 진단, 기존 기후 feature 계획 연결, ACL 이후 합성 text embedding/ranking을 구현했다.
5. `services/models/legacy_audit.py`로 고정 SHA의 과거 실제 체크포인트를 CPU `weights_only=True`로 검사했다. 학습·가중치 변경·실제 추론은 하지 않았다.
6. `services/models/build_evidence.py`로 API/UI가 읽을 상태·JSON Schema·증거 색인을 생성하고 `tests/models/`로 차단 불변성을 검증했다.

## 2. 세 유형의 입력/실행 계약

| 유형 | 필수 입력과 보존 | 현재 실행 범위 | 상태 |
|---|---|---|---|
| LCLUC segmentation | CHW, **B02/B03/B04/B08/B11/B12 순서**, 제품별 검증 scale/offset 근거, 원본 SHA, 같은 grid SCL | 합성 ≤256×256 마스크/digest 진단. 실제 segmentation 없음 | `TESTED_SYNTHETIC` 진단 / 운영 `BLOCKED` |
| Structured climate feature | ClimateAsset + 경계 version + as-of + feature window, 관측/전망·model/scenario·calendar/unit/grid | 기존 `plan_climate_join`의 계획/누출 차단만 연결. 실제 join·수치 feature·예측 없음 | 합성 계약 시험 / 실제 모델 `BLOCKED` |
| RAG embedding/reranker | principal, 허용된 문서, 질문, 출처 citation | ACL 필터 **후** tokenization/hash fixture embedding/lexical ranking. 사전학습 embedding/reranker 없음, answer 항상 null | `TESTED_SYNTHETIC` / 운영 `BLOCKED` |

LCLUC의 KLHK 23종 → 내부 클래스 대응은 권위 있는 검증 표가 없어 `class_mapping_23_to_internal:null`이다. v1은 임의 대응표 등록을 거부한다. 과거 WorldCover 9종 head를 23종 head나 검증된 대응표로 표현하지 않는다. SCL 0..11을 검사하고 4/5/6/7/11만 진단 유효 마스크로 사용한다. 구름·그림자·결측을 토지피복 클래스로 바꾸지 않는다. 합성 함수의 `fixture_kind=synthetic`는 호출자 선언이며 실제 자료를 합성이라고 선언할 수 없게 하는 증명 체계는 아니다. 이 경로는 운영 모델이 아니며 정확도를 반환하지 않는다.

기후 입력은 기존 CF 달력/QC/ACL/as-of 검증을 그대로 사용한다. 관측과 전망을 합치거나 coarse grid를 10m 관측으로 표시하지 않는다. `climate_feature_plan`은 **계획**이다. `services/climate_query`의 검증된 구조화 조회가 존재하는 것과 새로운 기후 예측 모델이 학습됐다는 것은 별개다.

RAG의 hash embedding과 Jaccard 점수는 합성 동작 진단이며 의미 검색 모델 성능이 아니다. 정량 질문은 `climate.query` 필요 상태로 차단하고 기후 수치/서술 답변을 만들지 않는다. 문서·수치 권위 검증은 기존 RAG/구조화 도구의 별도 책임이다.

## 3. 실제 체크포인트 읽기 전용 감사

- 경로: `E:\GeoAI–MLOps–SDSS\data\models\baseline2021_cpu_v1_model\best.pt`
- 실제 크기: **130,145 bytes**. SHA-256: `ad74f5cf5ab4bfd42bffd94b2fa399bf28f3527bc8e9f424d6a9d5339b12cd6c`.
- 고정 바이트를 먼저 읽어 SHA를 확인하고 같은 바이트를 `weights_only=True`, `map_location=cpu`로 로드했다. 크기 상한 16MiB이며 불일치 파일은 역직렬화하지 않는다.
- 실제 `tiny_unet`, seed 42, `enc1.0.weight=[8,3,3,3]`, `head.weight=[9,8,1,1]`: 입력 **3밴드**, 출력 **9종**이다. 새 6밴드 계약과 일치하지 않는다.
- 실제 보고서 SHA: `d99f4bd22ce96b1c322e99514edb1bedc04944a88f8e9cb85d771cced38fef9f`. 보고서는 `synthetic:false`, `reference_kind:worldcover_weak_label`, 3 epoch를 기록한다. 이것은 약한 참조 기반 과거 연결 시험이며 독립 정확도가 아니다.
- 체크포인트에 결합한 재현 환경 SHA, 검증된 23종 대응표, 독립 현장 GT/evaluator/운영 승인 근거가 없다. `inspection_state:VERIFIED_REAL`은 **실제 파일/텐서의 검사**만 뜻하고, 최종 상태는 `BLOCKED`이다. 가중치와 과거 보고서는 변경하지 않았다.

## 4. API/UI용 증거 계약

생성 위치: `evidence/models/`.

- `catalog.json`: 세 모델의 Draft manifest, null 아티팩트, input signature SHA.
- `model-manifest.schema.json`: Pydantic에서 생성한 JSON Schema.
- `readiness.json`: 유형별 `axes.training/inference/deployment`의 `status`, `allowed`, `blockers`; 실제 학습/배포 false와 독립 metrics null.
- `legacy-checkpoint-audit.json`: 실제 파일 검사와 불일치 근거. 과거 파일이 catalog의 새 모델 체크포인트로 등록된 것은 아니다.
- `synthetic-smoke.json`: 합성 마스크/문서 진단. 독립 지표나 실제 segmentation 없음.
- `runtime-environment.json`: 현재 진단 런타임 Python/Pydantic/NumPy 정보 및 내용 SHA. **과거 모델 학습 재현 환경을 증명하지 않는다.**
- `evidence-index.json`: 앞선 파일들의 SHA. 자체가 서명된 운영 승인이나 독립 검증 증거는 아니다.

이 JSON은 파일 소비 계약이며 새 HTTP route/화면 연결은 이 담당 범위에서 추가하지 않았다. root/API/UI 담당이 연결·권한·서버 반영을 별도로 검증해야 한다. 현 데이터 readiness를 임의로 가져오거나 수집 중인 manifest의 개수를 재사용하지 않아 `data_readiness:null`이다.

## 5. 실행·시험 증거와 인수조건

루트에서 실행:

```powershell
python -m unittest discover -s tests/models -v
python -m services.models.build_evidence --legacy-checkpoint 'E:\GeoAI–MLOps–SDSS\data\models\baseline2021_cpu_v1_model\best.pt'
```

필요 런타임은 공통 Pydantic v2 및 기존 climate 선택 의존성의 NumPy이다. torch는 과거 checkpoint의 선택적 읽기 전용 감사에만 필요하다. 미설치면 감사는 차단된다. 학습·네트워크 다운로드는 없다.

합성 시험은 입력 서명 변조, 밴드 순서/임의 대응표 거부, 필수 기후 의미/ACL 서명 제거 거부, registry 불변 버전, artifact SHA/경로 이탈, 데이터 누출 Gate 전달, 약한 참조 승격 금지, SCL 마스크/NaN/grid, ACL 이전 본문 처리 금지, 수치 질문 차단, 기후 metadata/as-of, 불일치 checkpoint 역직렬화 거부를 검사한다. **14개 시험 PASS**이며 실제 시험 로그는 `evidence/models/test-results.txt`에 저장한다. 실제 checkpoint 감사 CLI도 exit 0으로 완료하고 최종 상태 `BLOCKED`를 반환했다.

다음 인수조건: 실제 6밴드/SCL/정규화·그룹 분할·대표성/클래스 균형 자료 검증 → 승인된 클래스 대응표/서명된 데이터 계약 → 새 모델과 보고서/재현환경 SHA 결합 → 약한 참조 일치도와 독립 현장 평가 분리 → 보안/rollback/운영 승인. 공통 Gate의 현재 6주/36셀/1000패치/600·100·100 및 F1/OA 임계값은 개발 정책이며 컨소시엄 공식 승인 기준으로 주장하지 않는다. 유형별 기후/RAG 학습·배포 정책과 실제 운영 실행기는 후속 과제다. 현재 데이터/독립 정확도 부족을 합성 진단으로 해소했다고 주장하지 않는다.
