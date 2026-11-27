# SDSS-Platform2 v4.2 이해자료 색인

- updated_at: 2026-11-26 KST
- source_commit: `UNCOMMITTED_BOOTSTRAP`
- status: 전체 플랫폼 `IMPLEMENTED_UNVERIFIED`; 아래 항목별 상태를 별도로 확인한다.

## 권장 학습 순서

1. [v4.2 기후 데이터 계약과 근거 추적형 RAG](V42_CLIMATE_FOUNDATION_AND_RAG.md) — 쉬운 설명, 이론, 코드 흐름, 시험, 발표, Q&A
2. [KLHK 문서 ingestion과 학습·배포 Gate](V42_KLHK_RAG_MLOPS_GATES.md) — 실제 취득 범위, 운영 게시 차단, MLOps Gate
3. [CCKP Indonesia 개발 bbox 수치 도구](V42_CCKP_INDONESIA_NUMERIC_TOOL.md) — 실제 NetCDF·CDD 통계와 해석 한계
4. [최종 통합 상태: One Map·Sentinel·UI·모델·워크플로](V42_FINAL_INTEGRATION_STATUS.md) — 실제 감사와 남은 차단 조건
5. [Sentinel 단일 실제 pilot](V42_SENTINEL_SINGLE_PILOT.md) — East Java 2023 예약·pin·same-scene 6 band+SCL·정산
6. [Sentinel pilot 반영 36셀 재감사](V42_SENTINEL_POST_PILOT_REAUDIT.md) — exact geometry 현재값과 다음 6창 참고량
7. [Sentinel 경계 내 후속 배치](V42_SENTINEL_BACKGROUND_COVERAGE_BATCH.md) — 36창 계획, 중단 회로, 시점별 실제 진행
8. [공통 결과 등록·검토·조회 Gate](V42_COMMON_RESULT_REVIEW_GATE.md) — 증거 고정, 불변 ID, append-only 검토, 실제 Edge·프로젝트 등록 증거
9. [결과 카탈로그와 이중 승인 Gate](V42_RESULT_CATALOG_AND_GOVERNANCE.md) — 같은 결과 ID의 수치·지도·보고서 패키지와 과학/게시 승인 분리
10. [운영 경로 2~8](V42_OPERATION_PATH_2_TO_8.md) — 기관 작업·원천·React 연결·모델 버전·저장소와 남은 인수 조건
11. [LCLUC 분류사전·변화 계산·기준 분류기](V42_LCLUC_TAXONOMY_CHANGE_CLASSIFIERS.md) — 공식 23코드, 보수적 crosswalk, 변화 엔진, RF·Tiny U-Net과 운영 차단 조건
12. [LCLUC 연차 원본 입고·후보 모델·검증 Gate](V42_LCLUC_ANNUAL_INTAKE_GATE.md) — 번들 명세, 두 센서 QA, RF 후보, 센서 간·약한 참조·독립 정확도 분리
13. [반텐 Sentinel-2 Explore Gate](V42_LCLUC_SENTINEL_EXPLORER.md) — native 10m/20m, 30m 연차 합성·지수·QA, 방향 전이·AOI 절단, MapBiomas 35년과 2021 제품 지도 일치도
14. [반텐 Landsat 장기 분석 Explorer](V42_LCLUC_LANDSAT_EXPLORER.md) — 센서별 밴드·QA, 7개 영상, 기간 합성, MapBiomas 주 통계, 시험 RF와 과거 단일 장면 시범
15. [LCLUC 후처리 및 품질관리](V42_LCLUC_POSTPROCESS_QUALITY.md) — 공간 sieve 실자료 시험, 전후 면적·약한 참조 비교·SHA 이력과 계획 도구
16. [반텐 모델 시험과 특화 분류 계층 통합](V42_LCLUC_MODEL_TRIALS_AND_SPECIALISTS.md) — RF·Tiny·Siamese 실자료 비교, Spatial Filter, 동년 특화층 접수·우선순위 계약
17. [반텐 원본별 면적과 공식 비교 기준](V42_BANTEN_ESRI_MAPBIOMAS_AREA_COMPARISON.md) — Esri 9행·MapBiomas 11행 별도 표시, Kemenhut 동년 23클래스와 독립 조사 표본 Gate
18. [MapBiomas Indonesia GeoLLM 지식 검색](V42_MAPBIOMAS_GEOLLM_KNOWLEDGE.md) — 공식 원문 14건, SHA·페이지 인용, 286청크와 로컬 교차언어 검색
19. [GeoLLM 반텐 토지피복 질의응답](V42_LCLUC_GEOLLM_QUERY.md) — 3개 언어 RAG·GIS, 기본 Dockerfile의 Compose·kind 재현성과 차단 Gate
20. [용어집](GLOSSARY_KO_EN.md) — 한글/영문/약어와 이 프로젝트의 정확한 의미
21. [1분·5분 발표 대본](presentations/1MIN_5MIN_SCRIPT.md)
22. [발표 FAQ](presentations/FAQ.md)
23. [변경 이력](CHANGELOG.md)

## 현재 상태 요약

| 영역 | 상태 | 설명 |
|---|---|---|
| 공통 기후 lineage 계약 | `TESTED_SYNTHETIC` | 5개 계약시험 통과 |
| Climate ontology/KG | `TESTED_SYNTHETIC` | 16노드·11관계와 exact source span 계약 |
| ACL·hybrid retrieval·citation | `TESTED_SYNTHETIC` | 합성 문서/hash vector 기반 18개 RAG 시험 |
| CCKP 제한형 discovery | `VERIFIED_REAL` | S3 목록 5페이지 5,289B와 listed NetCDF HEAD 1건만 |
| CCKP bounded source 계약 | `TESTED_SYNTHETIC` | 계획·receipt·재개·429 등 24 PASS; 별도 global tool에서 한 원본 실제 취득 |
| Indonesia CCKP 계획 | `BLOCKED` | 공식 식별자·국가 prefix 미확인, 추측 URL 생성 금지 |
| Climate lake·CF/QC 계약 | `TESTED_SYNTHETIC` | 12 PASS; 실제 numeric QA/curated publication 없음 |
| 시공간 feature planner | `TESTED_SYNTHETIC` | 12 PASS; 실제 join 0, execution_started=false, numeric_features=null |
| CCKP CDD bbox 수치 도구 | `VERIFIED_REAL` | 4,209,592B SHA pin, Range 17개, CF-1.6/NETCDF3_CLASSIC, 12,765셀, 40.91221481742199 days |
| CCKP live 수치 서비스 | `BLOCKED` | 행정경계·다른 변수/기간·HTTP/RAG 등록·학습·배포 0 |
| private hash VectorDB | `IMPLEMENTED_UNVERIFIED` | 7문서·122 chunk·64차원 index; 의미 검색 품질 미검증 |
| 기관 인증·authority | `BLOCKED` | 문자열 결속과 실제 기관 인증을 구분 |
| 독립 정확도 | `BLOCKED` | WorldCover 약한 참조와 분리; 독립 라벨 미검증 |
| API/UI 이전 snapshot | `VERIFIED_REAL` | 이전 Edge 클릭·API 11 PASS; 새 재감사 UI 검증으로 재사용하지 않음 |
| 재감사 API/UI | `VERIFIED_REAL` | 로컬 8011 및 Edge 158에서 36행·6후보·42.75MiB 확인 |
| KLHK/CCKP metadata 원본 | `VERIFIED_REAL` | 7개·122 span·381,676B, raw SHA mismatch 0 |
| KLHK native 23-class·license | `BLOCKED` | 2024/2025 renderer 25항목; native domain·사용허가 미확인 |
| KLHK 공식 분류사전 | `VERIFIED_REAL` | SIGAP·SK 398/2024 대조 23코드: 토지피복 22 + 구름 품질코드 1; 444,011B·SHA 고정 |
| KLHK→legacy-9 crosswalk | `IMPLEMENTED_UNVERIFIED` | 잠정 보수표 11개 mapping·12개 exclusion, taxonomy SHA 결속·기본 차단; 운영 승인 없음 |
| LCLUC 변화 엔진 | `TESTED_SYNTHETIC` | 동일 taxonomy·grid·equal-area CRS의 두 시점 공통 유효면적 계산 4 PASS; 실제 변화량 아님 |
| LCLUC 기준 분류기 | `TESTED_SYNTHETIC` | RF·Tiny U-Net 전용 12 PASS; 합성 holdout 252픽셀·각 mIoU≥0.50·SHA 저장/복원. 독립 정확도 0 |
| LCLUC 연차 입고 Gate | `TESTED_SYNTHETIC` | Docker 5180·kind 5181 독립 합성 E2E, 4단계 상태 전이·4 GeoTIFF SHA·회귀 45 PASS/1 SKIP |
| LCLUC 연차 Edge | `TESTED_SYNTHETIC` | 양 환경에서 실제 Sentinel-2 2020 지도와 합성 2026 상태 행·증거 링크 클릭 확인 |
| LCLUC 실자료 watcher | `VERIFIED_REAL` | 60초 간격 실제 inbox 감시, synthetic 비활성, 운영 접수 0건 |
| Sentinel-2 Explore 2020 API | `VERIFIED_REAL` | 자연색·CIR·NDVI·NDWI·NBR·quality PNG 6종과 30m 10-band GeoTIFF SHA 응답 확인 |
| Sentinel-2 Explore 2020↔2025 Edge | `VERIFIED_REAL` | 영상 5조합·3 overlay·swipe·두 날짜 Explore·53,155.27ha AOI·전이 5개·CSV 112행 |
| Sentinel-2 Explore Esri 참조 | `VERIFIED_REAL` | 2020~2025 6/6년과 가능한 변화 15/15쌍 발행·audit |
| Sentinel-2 Explore 분광 발행 | `VERIFIED_REAL` | 32장면·2020~2025 6/6년·PNG 36개·30m 10-band GeoTIFF 6개 검산 |
| Sentinel-2 Explore API·핵심 Edge | `VERIFIED_REAL` | 주 전체/API AOI 39,631.96ha, Edge AOI 53,155.27ha·CSV 112행, 5조합·3 overlay·점·다운로드 |
| Sentinel-2 Explore 연도 선택 UI | `VERIFIED_REAL` | 시작 연도 2024 변경 시 NBR 유지·정확한 2024→2025 변화 layer 연결, 최종 Edge/HTTP exit 0 |
| Sentinel-2 Explore 결과·layer UI | `VERIFIED_REAL` | Edge 5175 면적표·목록 접기/펼치기·5영상·4 switch·방향 지도/필터·AI 상태·35년 다운로드·2021 행렬·AOI 52,128.16ha 확인 |
| Sentinel-2 지도 결속 상세 결과 | `VERIFIED_REAL` | Sentinel-2 선택 시 상단 7개 이동 항목으로 지도 분석·6개 결과 카드 초점 이동 확인 |
| 상세 결과 전환 회귀 | `VERIFIED_REAL` | 상단 탭 이동 중 패널 한 개·AOI 유지, Landsat·Esri 해제, Sentinel 재선택 AOI 복원, 포커스 이동, 2024→2025 표 갱신 확인 |
| LCLUC 카드·Sentinel 패널 출처 표기 | `VERIFIED_REAL` | Edge에서 두 카드의 Esri v003·반텐주 전체·2020→2025, 기반자료 전환 후 수치 유지, Sentinel 광학·Esri AOI 출처 문구 확인 |
| Sentinel 2열 지도·6카드 Workspace | `VERIFIED_REAL` | 1650px에서 연차·Sentinel 지도 폭 각각 886.95px, 오른쪽 2카드·하단 4카드, 920px 세로 배치, 7개 실제 이동 확인 |
| Sentinel Swipe·도구 결속 | `VERIFIED_REAL` | T1/T2 2022→2024가 API·필터·지도·AOI 표에 공유, 50:50 복귀, 점 조회·행정경계 switch 확인 |
| Landsat Explorer 2020~2025 | `VERIFIED_REAL` | 실제 24장면, 7개 preset, 기간 clear 97.8617%·99.8192%, Edge 886.95px·역사 Swipe·순차 재생·T2 정지 확인 |
| Landsat 2020 시험 RF | `VERIFIED_REAL` | 공간 블록 홀드아웃 72,391픽셀, Esri v003 약한 참조 일치도 71.4205%, 독립 정확도 미측정 |
| Landsat 과거 단일 장면 시범 | `VERIFIED_REAL` | 1988·1990·2000·2010 Landsat 5 TM, 총 1,257,798,910B, manifest·API·원본 SHA와 맑은 관측 확인 |
| Landsat 픽셀 변화 발생시점 | `PLANNED` | 조밀한 시계열과 LandTrendr·CCDC 비교 필요 |
| LCLUC Spatial Filter 실자료 시험 | `VERIFIED_REAL` | 4픽셀·4방향, 61,274픽셀·129,889.72ha 보정, 실행 ID·전후·세 GeoTIFF SHA 확인 |
| Spatial Filter 약한 참조 비교 | `VERIFIED_REAL` | 동일 72,391 공간 홀드아웃, Esri v003 일치도 71.4205%→75.3574% |
| Spatial Filter 계약시험 | `TESTED_SYNTHETIC` | NoData·보호 클래스 유지와 4·8방향 연결 차이 2건 |
| 후처리 독립 정확도·운영 보정 | `BLOCKED` | `REFERENCE_REQUIRED`, 147m 표시 격자 시험이며 운영 기준·독립 평가·승인 대기 |
| RF·Tiny 동일 실자료 비교 | `VERIFIED_REAL` | 학습 19,647, 같은 홀드아웃 72,391, Esri 약한 참조 71.4205%·66.3356% |
| RF·Tiny 3픽셀·8방향 후처리 | `VERIFIED_REAL` | RF 75.09%·31,658픽셀, Tiny 66.49%·1,885픽셀 변경 |
| 두 센서 DeepLabv3+ 시험 | `VERIFIED_REAL` | Landsat 72,391에서 67.7584%→67.9670%, Sentinel-2 76,230에서 63.7413%→63.8725% |
| 센서별 3모델 benchmark API | `VERIFIED_REAL` | Landsat·Sentinel-2 각각 RF·Tiny·DeepLab 보고서와 SHA 고정 GeoTIFF 6개 |
| Sentinel Siamese 변화 후보 | `VERIFIED_REAL` | 2020→2025, 홀드아웃 64,658, 변화 F1 0.288265→0.288352 |
| 특화 분류 계층 통합 계약 | `TESTED_SYNTHETIC` | 우선순위·충돌·NoData·타년 거부, 별도 GeoTIFF 11픽셀 통합·원본 SHA 유지 |
| 실제 특화 분류층·독립 평가 | `BLOCKED` | 승인 동년 라벨·mask·GEE 권한·독립 정답·운영 승인 대기 |
| Temporal·Gap·Frequency·Incident | `PLANNED` | 연속 분류·QA·클래스 기준 필요 |
| MapBiomas GeoLLM 원문·검색 | `VERIFIED_REAL` | 공식 14건·P0 9건·286청크·44용어·25지도·5범례, Edge 한글/영문 3질의·원문 링크 |
| MapBiomas embedding·생성 답변 | `BLOCKED` | 현재 로컬 어휘 근거 검색이며 음성·embedding·생성 답변·공개 운영 색인 없음 |
| Esri·MapBiomas 원본별 집계 API/UI | `VERIFIED_REAL` | 공통 연도 2020~2024, Esri 9행·MapBiomas 11행 별도 표시, Edge 2020·2024 선택 |
| 2024 Esri 피복 구성 | `VERIFIED_REAL` | 경계 935,602.88ha = 유효 935,224.83ha + 구름 378.05ha + NoData 0ha |
| Kemenhut 공식 비교 기준 | `BLOCKED` | 동년 Penutupan Lahan 23클래스 원본·APL 범위·발행판·권리·SHA 입고 대기 |
| 독립 정확도 | `BLOCKED` | Kemenhut 공식 참조와 분리한 현장·전문가 판독 표본 필요 |
| LANDY 4.1 전이 연결 | `VERIFIED_REAL` | 원본 XLSX TRANSITION 반텐 113행을 정제하고 GeoLLM 총전환·방향 전이에 연결 |
| LANDY 4.1 공간 raster | `BLOCKED` | 반텐 연차 분류·전이 GeoTIFF와 발행 집계 경계 도형 미확보 |
| GeoLLM 다국어 RAG·GIS | `VERIFIED_REAL` | 한국어·인도네시아어·영어, 문서 인용과 MapBiomas·Esri 고정 수치 도구 Edge 검증 |
| MapBiomas 총전환·순변화 | `VERIFIED_REAL` | 2023→2024 산림→비산림 3,146.85ha, 산림면적 순변화 −1,265.58ha를 별도 지표로 제공 |
| GeoLLM Esri 전이 지도 | `VERIFIED_REAL` | 2023→2024 수목→시가지 3,561.79ha와 실제 v003 전이 PNG |
| GeoLLM 기본 컨테이너 이식 | `VERIFIED_REAL` | 기본 Dockerfile `libexpat1` 새 빌드로 Compose 5180·kind 5181 다국어 RAG·GIS 통과, 파생 런타임 이미지 없음 |
| GeoLLM 실행 pin·마운트 | `VERIFIED_REAL` | JSON 10개·지도 자산 해시와 API·XLSX·정제 JSON SHA 동일, 양쪽 raw·evidence `ro`·curated `rw` |
| GeoLLM 보완 전 API 이미지 | `BLOCKED` | Dockerfile 보완 전 `b471bb3`은 양쪽에서 `libexpat.so.1` 누락으로 시작 실패, 파생 이미지 검증은 역사로 보존 |
| GeoLLM Kemenhut·overlay | `BLOCKED` | 승인 동년 원본과 중첩 대상 자산 미입고 |
| GeoLLM 독립 정확도·결과 ID | `BLOCKED` | 독립 표본 미연결, 읽기 전용 `result_id=null` |
| Sentinel-2 Explore 방향 전이 | `VERIFIED_REAL` | AOI 전이 합계와 선택 클래스쌍 PNG를 같은 사각형·반텐 경계로 절단; 방향·AOI fixture는 `TESTED_SYNTHETIC` |
| MapBiomas 반텐 장기 추세 | `VERIFIED_REAL` | 발행자 주 통계 1990~2024 35년·11클래스; 사용자 AOI·Esri 통계와 별도 |
| Esri↔WorldCover 2021 지도 일치 | `VERIFIED_REAL` | 10m·6대분류, 926,628.52ha, 80.9456760515%; 독립 정확도 미측정, 적용 연도 2021 |
| 생산 연차 AI 실제 접수 | `BLOCKED` | 운영 접수 0건; 실제 후보 분류·독립 검증·release 없음 |
| Sentinel-2 Explore 독립 정확도 | `BLOCKED` | Esri v003 통계는 참조 분석이며 `independent_accuracy_measured=false` |
| 실제 2026 연차 bundle | `BLOCKED` | 실제 2026 원본·receipt·bundle SHA·동년 라벨 없음 |
| 연차 센서 간·약한 참조 실제 일치도 | `BLOCKED` | 실제 2026 센서별 후보 지도와 동년 약한 참조가 없어 미산출; 독립 정확도와 별도 |
| 연차 독립 정확도·release | `BLOCKED` | 출처가 분리된 승인 독립 표본 없음; 후보 RF 생성과 모델 공개·활성화는 별도 승인 |
| LCLUC Python 통합 | `TESTED_SYNTHETIC` | 분류사전·변화·등록 포함 37 PASS; 격리 fixture 4ha/1ha/25%, 2023 없음·동일 SHA/연도 거부·단일 결과 ID/CSV |
| Esri 반텐 실제 LCLUC 사례 | `VERIFIED_REAL` | 결과 `f9f3…605a`, 공통 712.30ha·변화 32.65ha·4.58%. 반텐 고정 표본이며 독립 정확도 아님 |
| 기존 LCLUC Workspace | `VERIFIED_REAL` | Edge 5175에서 7탭·4 KPI·50:50/Time-Series·범례·실자료 preview/ZIP·행렬/내보내기·미등록·JS0 확인 |
| 반텐 Esri 2020~2025 전역 | `VERIFIED_REAL` | 6/6 실제 원천·One Map 935,602.88ha, 기존 Workspace swipe·6년 면적 시계열·전환행렬·KPI·원천 inventory 확인 |
| 반텐 Esri 2020→2025 대표쌍 | `VERIFIED_REAL` | 공통 935,231.32ha·변화 78,998.91ha, 1km 변화 셀 8,663개·hotspot 20개, HTML/JSON/CSV ID `0c62…dab6` |
| 반텐 native 광학자료 | `VERIFIED_REAL` | S2 224/224·32/32·21,626,452,905B, Landsat 168/168·24/24·11,700,363,947B, 양 센서 6개년 QA·RGB 완료 |
| 반텐 광학 과학 인수 | `BLOCKED` | `COVERAGE_GAPS`: Landsat 10.35~274.32ha, S2 2021~2025 0.09~2.88ha 경계 미피복 |
| 반텐 독립 정확도 | `BLOCKED` | Esri 동일 연도 reference coverage·연차 변화는 확보했지만 독립 현장·전문가 정답 평가는 없음 |
| LCLUC Docker·Kubernetes 이식 | `VERIFIED_REAL` | Docker 5180·Kubernetes 5181에서 같은 이미지·읽기전용 원본·3 PVC·경계/결과·광학 12 layer 확인. 과학 인수와 별도 |
| One Map 행정명 overlay | `VERIFIED_REAL` | API 6주·129군시; 양쪽 지도에서 6주 이름과 Tangerang·Kota Tangerang 직접 확인. 클릭·사업통계 승인 미검증 |
| One Map 경계 사업통계 승인 | `BLOCKED` | 현재 경계는 LCLUC·WebGIS 지도 참조용이며 승인 통계 경계로 확정하지 않음 |
| Esri v003 9색 | `VERIFIED_REAL` | 8개 면적 클래스+Clouds 품질(code 10, 68/0); NoData 0 투명. 독립 정확도 미측정 |
| 실제 문서 운영 RAG 게시 | `BLOCKED` | public index 0, quantitative answer 0, 기관 authority 미인증 |
| KLHK/RAG ingestion 계약 | `TESTED_SYNTHETIC` | 신규 11 + 기존 RAG 18 = 29 PASS |
| 학습·배포 MLOps Gate | `TESTED_SYNTHETIC` | 6 PASS; 실제 학습·독립정확도·배포 0 |
| Sentinel 36셀 수량 감사 | `VERIFIED_REAL` | 36/36 최소 28패치; full spatial coverage와 다름 |
| Sentinel 공간 피복 | `BLOCKED` | post-pilot paired 0.9773249834093871%, clear 0.890386955270514%; 약 99% 공백 |
| East Java 2023 단일 pilot | `VERIFIED_REAL` | same-scene 6 band+SCL, clear 65,536/65,536, 28요청·7,471,506B, 오류·429 0 |
| pilot 원장·postflight | `VERIFIED_REAL` | SHA `8e98...aa44a`→`b257...25de1`, 잔액 1,678,521,030B, 후속pilot·collector·locks 0 |
| Sentinel aggregate 재감사 | `VERIFIED_REAL` | 36셀·72 exact features, present/clear 각각 +6,556,514.480755895m²; 외부 I/O 0 |
| 다음 6창 참고량 | `PLANNED` | 7,471,506B×6=44,829,036B; 전체 전송량·실행 승인·예산 충분성 미확정 |
| 로컬 CAS 이관 | `VERIFIED_REAL` | 6,125객체·3,904,601,927B; 원격 다운로드 0 |
| 전문 모델 adapter | `TESTED_SYNTHETIC` | 14 PASS; 실제 모델 학습·추론·배포 아님 |
| 내구성 오케스트레이터 | `TESTED_SYNTHETIC` | 5개 계약시험; 실제 workflow state·학습 adapter 없음 |
| data follow-up 단일 pilot 경로 | `VERIFIED_REAL` | reservation·scene/asset/window pin·bounded I/O·실측 정산 한 건 완료; 전체 수집은 아님 |
| 경계 내 후속 배치 계획 | `VERIFIED_REAL` | 6주×2020~2025 36창, 경계·missing geometry 내부, 창당 32MiB |
| 경계 내 후속 배치 역사 snapshot | `VERIFIED_REAL` | 11:44 KST 당시 3/36·QA 2·429 0; 현재 실행 상태가 아님 |
| 경계 내 후속 배치 현재 상태 | `BLOCKED` | 12:05 KST worker 종료, 8/36·QA 5, 9번째 West Java 2024 32MiB pending·실제 byte 미확정 |
| 배치 신규 관측 | `VERIFIED_REAL` | 8개 observation이 저장됐지만 최신 면적·byte는 미정산 9번째 창과 분리; aggregate 재감사 전 전역 피복에 미반영 |
| 배치 학습 적격 | `BLOCKED` | 새 training-eligible 0; label·독립 ground truth 없음 |
| 공통 결과 registry·workflow | `VERIFIED_REAL` | 실제 프로젝트 10개 결과, verify/register/lookup 30단계 성공, ID 재조회 일치 |
| 공통 결과 Edge 검토 | `VERIFIED_REAL` | 선택시험 5 PASS·DOM 2 PASS; 임시 DB 등록·수정 요청·검토 완료·새로고침 확인 |
| 공통 결과 로컬 제공 | `VERIFIED_REAL` | 8014에서 10 result·PENDING 10·30단계 scope·One Map 상세, JS 오류 0 |
| 공통 결과 운영 전환 | `BLOCKED` | local/loopback 한정; 다중 사용자 인증·공용 DB/Lake cutover·복구 미검증 |
| 결과 카탈로그 실제 seed | `VERIFIED_REAL` | CCKP `40.91221481742199 days`·12,765 Point·보고서 2개, BIG 반텐 역사 폴리곤 1개·보고서 1개 |
| 결과 카탈로그 Edge | `VERIFIED_REAL` | `c4a3954` GitHub push, 실제 seed 2·지도 2·보고서 3 조회 |
| 결과 카탈로그 계약 | `TESTED_SYNTHETIC` | 동일 ID 결속·asset SHA·형식 fail-closed·분리 승인 6 PASS |
| 실제 과학·게시 승인 | `BLOCKED` | 두 seed 모두 scientific/publication `PENDING`; 기관 authority·결정 근거 미확보 |
| 카탈로그 불확실성 | `BLOCKED` | 두 seed 모두 `NOT_REPORTED`; 0 오차나 독립 정확도를 뜻하지 않음 |
| 기관 작업 provider 계약 | `TESTED_SYNTHETIC` | 멱등 제출·재개·취소·model pin·asset 검증·결과 등록 8 PASS |
| 기관 작업 실운영 | `BLOCKED` | 조회 HTTP 200이지만 `JOB_PROVIDER_CONFIG_NOT_SET`; worker exit 1, 실제 endpoint·token·승인 0 |
| 기관 운영 React 연결 | `VERIFIED_REAL` | API 8014·Vite 5175 세 경로 HTTP 200, 합성 계약·138 modules build; 실제 Edge 클릭은 `PLANNED` |
| 기관 원천 인벤토리 | `VERIFIED_REAL` | RTRW·CCKP·Lake·KLHK·private index·Sentinel 로컬 6종 pin, 원격 요청·원장 쓰기 0 |
| 기관 원천 공개 | `BLOCKED` | 6종 모두 publication gate 차단·public search false |
| 현행 6지역 RTRW | `BLOCKED` | 0/6; Banten 역사 샘플과 BIG 93,340 record는 현행 6지역 완료 증거가 아님 |
| MLOps scene 격리 후보 | `VERIFIED_REAL` | 1,779→1,751행, 적격 1,382행, 원본 scene 충돌 1→0; 학습 허용은 false |
| 모델 release·rollback | `TESTED_SYNTHETIC` | 합성 ONNX 입력 10의 출력 11→12→11, 과학 승인 철회 뒤 실행 차단 |
| 실제 모델 학습·배포 | `BLOCKED` | 지리 중첩·피복·독립 라벨 미검증, 실제 학습·평가·실모델 배포 0 |
| SeaweedFS S3 개발 경로 | `VERIFIED_REAL` | 실제 CCKP 검산 JSON 3,295B, SHA·재시도, 익명 403, 45초 presigned GET·만료 403 |
| Docker Compose 5180 | `VERIFIED_REAL` | health·공통 결과·jobs·기존 GeoAI·반텐 원본 count·실제 광학 12 layer HTTP 확인 |
| 로컬 Kubernetes 5181 | `VERIFIED_REAL` | 같은 이미지, 읽기전용 원본, 3 PVC, 경계·2020~2025 결과·광학 12 layer 해시 확인 |
| 개발 PostGIS/pgvector·S3 | `VERIFIED_REAL` | 실제 schema, CCKP 보고서 3,295B signed SHA readback, 무인증 API 403 |
| PostgreSQL jobs | `TESTED_SYNTHETIC` | 실제 개발 DB에서 모의 기관 응답 10 PASS; 실제 기관 작업 아님 |
| Worker `--once` | `VERIFIED_REAL` | 승인된 대기 작업 0건, `jobs_checked=0` 안전 종료 |
| 기관 운영 인프라 인수 | `BLOCKED` | 실제 기관 provider·IAM/SSO·백업/복구·RPO/RTO·과학 인수 미확정 |
| 기관 저장소 운영 인수 | `BLOCKED` | 기관 DB·버킷·IAM·SSO·RPO/RTO 인수 미검증 |

앞선 climate 계약 합성 71 PASS와 ingestion/RAG 29·MLOps 6, 모델 14, 오케스트레이터 5, Sentinel pilot 계약 26, 후속 배치 계약 20, 결과 카탈로그 계약 6 PASS의 범위는 중복 시험을 섞지 않고 개별 Gate별로 읽는다. 후속 배치는 실행 중이 아니며 12:05 KST 기준 정산 전 worker 종료로 차단됐다. 공통 결과 10건 등록은 기존 증거의 접수·재조회이지 과학 실행 10건이 아니다. 카탈로그 `CATALOG_READY`도 과학·게시 승인 완료가 아니다. 신규 면적은 후속 aggregate 재감사 전 전역 피복으로 합산하지 않으며, QA 통과·검토 완료도 독립 정확도·학습 적격을 뜻하지 않는다.
