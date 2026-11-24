# One Map/BIG 경계와 Sentinel-2 실제 완전성

작업 루트는 `E:\SDSS-Platform2`다. `E:\GeoAI–MLOps–SDSS`는 읽기 전용 참조이며 기존 원장·수집기·합산 manifest·원본을 수정하지 않는다. 이 문서는 기관 경계 승인, 기후 수치, 토지피복 독립 정확도를 확정하지 않는다.

## 최종 실자료 결과 — 2026-11-24 20:40 KST

**36/36셀 native geometry 감사와 선별CAS copy가 모두 완료됐다.** 최종 근거는 `evidence/onemap_sentinel/handoff-summary-20261124.json`, `held-audit-20261124/completeness.json`이다. 공간보고서SHA는 `71c495c1fcf18c7fbcbb962021eedb40a61779cc200d8ddbf153cab3ed241943`, migration receiptSHA는 `0204d1a1dcde0a471b512a1a042d5a05daa638214afde150762e5ea508f556e5`다.

- 물리1,779patch·manifest적격1,407patch·전수pixel/SHA검증1,779patch·119parent.
- 36셀 모두최소28적격patch 충족. 그러나 **6밴드+동일scene SCL 실제동시피복은0.976741%**, clear는 **0.889803%**다. 공간완료는false다.
- 36셀의합산경계면적1,123,552,761,159.3m² 중동시존재10,974,205,322.115m², clear9,997,410,706.463m², 동시존재누락1,112,578,555,837.185m²다. 분모는6주×6연도 합산이므로 단일연도국토면적으로해석하지않는다.
- 기존원본에이미있던미패치가장자리317,440native pixel도피복에포함했다. 이것은신규원격관측수집이아니다.
- exact누락큐72feature/317,455,915B.1km full-cell 지표는보고용보수적하한이며이큐를만드는데사용하지않았다.
- CAS6,125object/3,904,601,927B copy완료, 원격다운로드0·원본/전역원장write0. collector0·기존execution lock없음·migration lock없음으로종료했다.
- 새자료1779행모두EsriIO weak label이고영상연도와라벨연도불일치0이다. source split을그대로유지했으며학습허용이나독립정답승격을하지않았다.

| 주(2020~2025합산) | 물리patch | manifest적격 | 실제동시존재% | 동시clear% |
|---|---:|---:|---:|---:|
|Banten|337|292|3.834177|3.633940|
|West Java|264|250|0.676129|0.656567|
|East Java|248|209|0.552601|0.516498|
|Gorontalo|272|212|2.470760|2.175868|
|South Sulawesi|320|227|0.769625|0.695685|
|Southeast Sulawesi|338|217|0.869791|0.727331|

`bounded-missing-batch-plan-20261124.json`은다른6개주의고유누락geometry를제안하지만 **BLOCKED**다. 차단이유는승인된공유전역reservation adapter와deterministic scene/asset/window pin이없기때문이다. 원장잔액1,685,992,536B를새로초기화하거나읽기전용제약을우회하지않았다. 실제수집PID는없다. 다음단위는이두Gate를구현·검증한뒤에만bounded취득을시작할수있다.

## 구현과 상태

| 항목 | 상태·범위 |
|---|---|
| BIG6주 snapshot | 공식 공개 원응답·metadata·파생 경계 SHA를 재검증해 새 저장소에 고정 |
| 실제 patch 감사 | 원본 SHA·6밴드·동일 scene SCL·STAC 연도·native mask/footprint 확인 |
| 공간 계산 | EPSG:6933 geometry 교집합·차집합, 실제 pixel mask의 면적 |
| 요구 grid | 1km 조사 index, 부분 피복을 완전한 grid로 세지 않음 |
| 누락 큐 | 정확한 geometry 차집합; scene asset pin이 없는 조사 큐는 실행 불가 |
| 신규 수집 | BLOCKED — 참조 전용 전역원장에 대한 승인된 공유 reservation adapter 없음 |
| 시험 | 합성33PASS; 실제 감사 결과는 아래 완료 근거로 구분 |

내부 구현은 `services/datahub/connectors/onemap/`, `services/datahub/sentinel/`다. `rasterio/numpy/shapely/pyproj`가 필요하며 현 실행 환경에서 확인했다. 공통 dependency 설정·HTTP API·UI 서버·이해자료는 이 담당 소유 경로가 아니므로 수정하지 않는다.

## 감사 재개·성능과 현재 원본 범위

최초 patch별 감사는1,779행 읽기를 마쳤지만 East Java의 대형 geometry 반복 intersection에서 지연됐다. 완료12격자·입력SHA를 보존하고, 확인된 읽기 전용 PID178676만 종료했다. 이 시도의 `audit-20261124/`는 **부분 증거**이며 최종 완전성 보고서가 아니다.

재개 구현 `sentinel/held.py`는119개 parent frame별로 native mask를 한 번 계산하고,1,779개 patch의 값·CRS·affine이 parent의 정확한 window와 일치하는지 전수검사한다. NumPy/pyproj 배열 변환과 Transformer cache, STRtree·prepared geometry·8×8 grid block별 intersection을 사용한다. 공간 union·면적·누락 원칙은 유지하며 중심 샘플로 대체하지 않는다.

native WKB와 검증파일 pin을 parent마다 commit하고, 셀별 geometry/격자/summary도 따로 commit한다. 재개 시 입력manifest/원장/geometry/원본파일 SHA를 다시 확인한다. commit 전 중단된 파생 WKB만 소유 cache 안에서 제거하며 원본·원장에는 쓰지 않는다. 셀 checkpoint가 없는 부분은 최종 완료로 세지 않는다.

사용자 승인 후 보고용1km full-cell 지표만 `CONSERVATIVE_LOWER_BOUND`로 최적화했다. 실제 전환 시점에 완료된 **strict24셀**을 원위치 보존했고 남은 셀은 별도 `cell-checkpoints-lower-bound/`에 저장한다. native geometry의 union/difference와 실제 면적·원격 누락 큐는 바꾸지 않는다. gap이 셀에 닿으면 full에서 빼므로 경계 접촉에서 full을 적게 셀 수 있으며, 부분 피복을 full로 올리지는 않는다. grid 하한으로 수집완료·미수집 해제를 판정하지 않는다. 결정근거는 `conservative-grid-decision-20261124.json`이다. 최종 재개명령에는 `--grid-mode conservative-lower-bound`를 추가한다.

기존 parent 중528/529px 폭·849px 높이가 있어256블록으로 추출되지 않은16/17/81px strip이 존재한다. 이 자료는 이미 보유한 관측이므로 원격 missing으로 제안하면 안 된다. 최종 held 감사는 이를 포함한 parent 전체의 유효6밴드+SCL mask를 사용한다. 기존 패치의 물리·적격 행 수는 그대로 별도 집계한다.

`native-verification-receipt-20261124.json`은119parent·1779patch의파일/pixel 검증 완료를 고정하지만 공간격자 완료를 의미하지 않는다. parent119 JSON/WKB checkpoint는 `held-audit-20261124/native-checkpoints/`, 최종 공간결과는 같은 디렉터리의 `completeness.json`이 권위 근거다.

## 경계의 정확한 출처와 버전

공식 서비스는 `https://geoservices.big.go.id/rbi/rest/services/BATASWILAYAH/BATAS_WILAYAH/MapServer/12`다. 대상은 Banten, West Java, East Java, Gorontalo, South Sulawesi, Southeast Sulawesi이며 기존 snapshot에 포함된 원본129feature를 주별 dissolve한 geometry다.

원획득시각은 **2026-10-27T06:21:02.271104+00:00**이며 다시 다운로드한 최신 경계라고 부르지 않는다. 원 snapshot SHA **`233c034c0b6a777799b14ab5451afedc3ece9abbe836b28e59292a18f4c2a423`**, metadata SHA **`cc778199a0cd21148551667cbfda3bf515c4bafae931589c31679fc365fa85ab`**를 고정한다. 새 import시각은 별도로 기록한다.

기관의 공식 발행 버전·현행 효력일·법적 고시·통계 사용 승인은 확인되지 않아 null/승인 대기다. `snapshot_version=sha256:...`는 획득된 내용 버전이다. ArcGIS의 `currentVersion`을 경계 데이터의 발행 버전으로 쓰지 않는다. 새 repository의 boundary receipt와 raw6주 응답은 exclusive 생성·SHA 검증으로 보존한다.

EPSG:4326 원본 geometry는 유효하다. EPSG:6933 변환 후 East Java·South Sulawesi의 수치적 topology 오류는 계산용 geometry에서만 make_valid하고 전후 면적을 기록한다. 변화가 `max(1m², 원면적×1e-9)`를 넘으면 중지한다. 원본 경계는 고치지 않는다.

## 네 가지 서로 다른 수치

1. **물리 patch 행 수**: image 파일이 실제 존재하는 manifest 행 수다. 유효한6밴드·SHA·라벨·공간 독립성을 뜻하지 않는다.
2. **manifest 품질 적격**: 기존 `quality_status=quality_eligible`의 행 수다. 기존 라벨/품질 정책의 결과이며 새 BIG 공간피복과 별개다.
3. **6밴드+SCL 동시 공간피복**: 실제 이미지의 B02/B03/B04/B08/B11/B12 메타데이터·파일SHA와 각 native 원본 crop SHA/소스URI를 확인한다. 같은 scene·연도의 원본 SCL을 image grid에 nearest로 정합하고, 모든6밴드 finite·valid mask와 SCL1..11의 교집합을 계산한다. 이것이 `simultaneous_present_area_m2`다.
4. **동시 clear 피복**: 위 교집합 중 SCL4/5/6/7/11인 영역이다. 라벨 정답·모델 학습 적격 판정은 아니다. SCL2/3/8/9/10, nodata/범위 밖은 clear로 세지 않는다.

실제 affine/CRS에서 pixel mask를 polygonize하고 EPSG:6933으로 변환한 뒤 주 경계로 자른다. 여러 패치가 겹쳐도 union으로 한 번만 센다. B11/B12의10m 출력은20m 원자료 보간이며 새로운 native10m 관측으로 표현하지 않는다. 래스터 footprint는 각 변을32구간으로 분할해 투영하며, 면적은 고정 snapshot·투영 표현 기준이다. 원본20m 지오데식 전수 통계를 인증하는 기능은 아니다.

기존 Unit371의 **SCL-only 7.711080%**는145개 SCL의1km 중심 샘플 inventory다. 그것을6밴드 관측률로 복사하지 않는다. SCL full-tile을 추가했어도6밴드 TIFF가 없는 넓은 영역은 이번 동시 완전성에서 여전히 누락이다.

36셀의 최소 patch 수 기본값28은 이전 계획의 비교 기준이며 공식 공간피복 인수기준이 아니다. 모든 셀에서28개를 넘더라도 실제 주 면적 대부분이 비어 있을 수 있다. `minimum_patch_cells_met`과 `full_spatial_coverage`를 별도 보고한다. 기존 학습 준비·누출·클래스·독립 라벨 Gate는 계속 별도다.

## 요구 grid와 exact missing queue

주별 EPSG:6933의1km 고정 격자를 사용한다. `required_touched_grid_cells`는 경계를 건드리는 index이며 경계선 접촉만 있는0면적 edge가 포함될 수 있다. 완전한 grid로 세려면 해당 셀과 주 경계의 교집합 **전체**가 실제 동시 피복에 들어가야 한다(면적차0.01m² 수치 tolerance). 중심점 하나 또는 일부 pixel이 있다는 이유로 full로 세지 않는다.

`*-required-and-support.tif`의 bit flag는 다음과 같다.

| bit | 뜻 |
|---:|---|
|1|경계를 건드리는 요구 index|
|2|경계 내 셀 전체의6밴드+SCL 동시 존재|
|4|경계 내 셀 전체의 동시 clear|
|8|일부 동시 존재|
|16|일부 동시 clear|

`exact-missing-queue.geojson`에는 `boundary − simultaneous_present` 및 `present − clear`를 별도 원인으로 저장한다. EPSG:6933 분석 GeoJSON 확장 형식이므로 WebGIS에 넣기 전 EPSG:4326으로 명시적으로 변환해야 한다. scalar bbox나 중심점으로 누락 영역을 대체하지 않는다. geometry는 정확한 차집합이지만 scene_id가 null이면 아직 실행 가능한 STAC 요청이 아니다.

## 수집·중복·예산·429 Gate

공유 원장 SHA가 바뀌거나 collector/lock가 있거나 상태가 불명확하면 차단한다. 429 circuit, 잔여예산, 디스크4배 여유, 고유한 최대6개 exact target, 기존 수집 key 중복을 검사한다. 예시 batch 상한은64MiB 이하이며 이 값이 기존 전역 한도를 확대하지 않는다.

현재 기존 GeoAI 저장소는 참조 전용이다. 새 저장소에 별도 원장을 만들어 과거 예약·잔액을 우회하지 않는다. 승인된 공유 reservation/lock adapter와 scene/asset/원격 window pin이 없으므로 실제 worker는 시작하지 않는다. 조사 CLI 자체에는 `--execute` 수집 옵션이 없다. 향후 연결할 때는 첫 실패/429/예산/디스크/lock 이상 즉시 중지, 보수적 미측정 예약 유지, 자동 환불·전역 sync·중복 수집 금지가 필요하다.

WorldCover2021을 다른 연도 독립 정답으로 사용하지 않는다. 이번 계산은 라벨을 읽거나 기존 라벨을 다른 연도로 복제하지 않는다.

## 재현 명령·증거

```powershell
python -X utf8 -m services.datahub.sentinel --reference-root "E:\GeoAI–MLOps–SDSS" --boundary "E:\GeoAI–MLOps–SDSS\evidence\integration\unit362-province-evidence-20261027\six-province-boundary-candidate.geojson" --boundary-sha256 233c034c0b6a777799b14ab5451afedc3ece9abbe836b28e59292a18f4c2a423 --manifest "E:\GeoAI–MLOps–SDSS\data\first-group-training-esri-v1\annual-window-report.json" --manifest-sha256 0c149628ccfa916ee976e561c5da05f9ccc810cbeab7d233a05b9bc7eff54658 --ledger "E:\GeoAI–MLOps–SDSS\data\first-group-training-budget\global-ledger.json" --ledger-sha256 8e98e9ba033f015e4e289860166b87f67d81a10e12fee66c9b45481296caa44a --output evidence/onemap_sentinel/audit-20261124
python -X utf8 -m pytest tests/onemap_sentinel -o addopts= -q --junitxml=evidence/onemap_sentinel/synthetic-tests-20261124.xml
```

기존 output은 덮어쓰지 않는다. 재실행할 때는 새 증거 디렉터리를 사용한다. 전후 manifest·ledger SHA가 같지 않으면 완료 판정을 내리지 않는다.

경계 근거는 `evidence/onemap_sentinel/audit-20261124/boundary/receipt.json`이다. 최종 공간결과는 `held-audit-20261124/completeness.json`, `held-audit-20261124/exact-missing-queue.geojson`, strict24셀과lower-bound12셀checkpoint다. 최초 `audit-20261124/audit/`의12격자는부분실행이력이며최종집계로사용하지않는다. 합성시험 근거는 `evidence/onemap_sentinel/synthetic-tests-20261124.xml`에저장했다.

최적화된 재개 명령은 아래와 같다. 처음의 부분감사 CLI를 다시 전체 실행하지 않는다.

```powershell
python -X utf8 -m services.datahub.sentinel.held --reference-root "E:\GeoAI–MLOps–SDSS" --boundary-receipt evidence/onemap_sentinel/audit-20261124/boundary/receipt.json --manifest "E:\GeoAI–MLOps–SDSS\data\first-group-training-esri-v1\annual-window-report.json" --manifest-sha256 0c149628ccfa916ee976e561c5da05f9ccc810cbeab7d233a05b9bc7eff54658 --ledger "E:\GeoAI–MLOps–SDSS\data\first-group-training-budget\global-ledger.json" --ledger-sha256 8e98e9ba033f015e4e289860166b87f67d81a10e12fee66c9b45481296caa44a --output evidence/onemap_sentinel/held-audit-20261124
```

## 검증 자료의 선별 copy·새 저장소 이전

사용자 승인으로 native 파일검증 완료 집합의 이전은 공간grid 계산과 병렬 진행한다. `migration.py`는 전체6.5GB 디렉터리를 복사하지 않는다. 권위 source manifest의1779patch image/label/quality,119parent6band/native6bands/SCL/STAC, calibration JSON·제품XML, BIG8개 snapshot 파일 및 원본manifest만 명시선택한다. 실패 QA후보·과거 중복 output·미선택 dataset·대형 raw reference label crop는 제외한다. 라벨은 같은 연도 weak reference이며 독립 정답으로 승격하지 않는다.

선별 계획 실측: **source alias6,655개→SHA dedupe6,125개,3,904,601,927B**. 기존 자유공간1,967,375,163,392B에 대해 최소7,809,203,854B 여유를 요구했고 통과했다. 로컬copy 상한8GiB는 원격수집 예산과 별개이며 기존 전역 acquisition 원장의 예약을 환불하거나 확대하지 않는다. 계획은 `migration-plan-20261124.json`에 고정했다.

저장은 gitignore된 `data/raw/migrated/{sha256}`에 한다. source는 rb, target은 같은 store의 새 temp에 copy→stream SHA/size→target post-SHA→atomic commit한다. 기존 CAS는 hash·size와 단일link를 확인해 재사용하고 내용이 다르면 덮어쓰지 않는다. 실패 시 해당 temp만 지우고 failure receipt를 남긴다. 이동·삭제·원본chmod·원본hardlink는 하지 않는다. 실제hardlink capability는 새 store의 작은 synthetic probe에서만 검사하고 제거한다. 링크를 쓰면 원본 drift가 전파되므로 실제자료의 정책은 COPY다.

`migration-receipt-20261124.json`에는 source/target SHA·size·alias·copy/reuse·시각·hardlink probe를, `migrated-scene-manifest.json`에는 새CAS localpath를 기록한다. 기존 raw calibration JSON의 역사적 경로는 고치지 않고 새scene의normalization/source_metadata_path를 새CAS로 명시한다. 미래 adapter는 이 새 mapping을 사용해야 한다. 새 manifest도 learning_ready=false이며 누출·클래스·정답·모델 승인 Gate를 자동 통과시키지 않는다.

Git에는 코드·문서·manifest·receipt만 남겨야 한다. raw TIFF/XML, geometry WKB와 대형 queue/TIFF 감사 산출물은 별도 데이터 artifact로 보존하고 Root가 stage에서 제외한다. 공통 .gitignore 자체는 이 작업에서 수정하지 않았다. 자료의 새위치 copy는 관측공백을 새로 수집한 성과가 아니며 원격GET0·기존원장write0이다.

## 선별 이전 실제 완료

`migration-receipt-20261124.json` 및 `migrated-scene-manifest.json` 생성과 함께 **6,125개 객체·3,904,601,927B copy**를 완료했다. 기존CAS 재사용0, sourcewrite0, 원격다운로드0이다. 새store의hardlink probe는supported=true·drift전파=true였으나 실제자료는모두copy했고 target단일link(nlink1)를확인했다. source와target이같은E:volume임도stat_dev로확인했다. 원본↔target hardlink는만들지않았다.

`post-migration-state-20261124.json`에서 파일수·총size·migration lock해제·원장SHA·원본manifestSHA·새CAS의6밴드TIFF 표본읽기를확인했다. 데이터는gitignore된rawstore에만있다. 실제oldledger SHA는 `8e98e9ba033f015e4e289860166b87f67d81a10e12fee66c9b45481296caa44a`, source manifestSHA는 `0c149628ccfa916ee976e561c5da05f9ccc810cbeab7d233a05b9bc7eff54658`로불변이다.

집계상 물리patch1,779개·manifest적격1,407개이며36셀모두최소28개를충족(실제최소28)했다. 이수치는공간피복완료나학습가능을뜻하지않는다. native 공간면적·exact누락큐는 별도의최종completeness 보고서를기준으로하고, 보고서생성전에는미완료다.

시험최종결과는 **33PASS/30.93초**, 외부rasterio affine연산경고59건이다. 보수적격자가부분셀을full로올리지않음·queuegeometry불변·119parent방식의잔여strip포함/재개·원본불변copy·CAS중복/변조·partial제거를검사했다. 실제새관측수집·학습·승격·배포는실행하지않았다.

## 후속 단위 — 공유 원장 adapter·단일 scene/window pilot

이 절은 위 선별copy/공간감사가 끝난 후의 별도 실행 단위다. 이전 단위의 원장불변 SHA는 당시snapshot이며 현재원장으로무조건재사용하지않는다. 새작업의명시적reserve/settle에한해 old `global-ledger.json`·동일directory temp·legacy `.lock`/`.execution.lock`만쓰기대상이다. 기존6125CAS와old data/code/manifest는읽기전용을유지한다.

### 공유 예산 계약

`sentinel/shared_ledger.py`는기본readonly다. 실제수집기OS조회·기존lock·429·잔액·디스크를확인하고, 명시writable execution lease에서만 mutation을허용한다. legacy와동일한O_EXCL marker에OS byte/file lock도유지해새adapter와기존collector의동시실행을막는다. read-only preflight는lock조차생성하지않는다.

reserve/mark_io/settle/release마다원장current SHA를CAS precondition으로검사하고, 동일directory의새temp를fsync한후atomic replace한다. 과거원장pin·기존pending·global charge합계를검사하고예산을초기화하지않는다. idempotency key는province/year/scene/B02 pixelwindow/7assets로결정하며원장시각이변해도같다. 기존key는추가예약/재실행하지않는다. 자동stale-lock삭제와미측정pending환불은금지한다.

IO이전취소만0으로release가능하다. IO시작은원장에먼저기록한다. 정상/실패에서계측이완전할때만현재예약을실측본문바이트로정산하고, timeout/미반환buffer 등미측정오류는전체예약을보수적으로남긴다. 429는Retry-After·host/path(query제외)를기록하고전역회로를열어후속요청을막는다. 지난예약에는이환불규칙을소급적용하지않는다.

### 결정적 공간·자산 pin

`pin_planner.py`는exact72-feature queue의SHA/317,455,915B와BIGboundary SHA를검사한다.1km 보수적하한은목표선정에쓰지않는다. 고정migrated scene/STAC CAS와119parent footprint만읽어,같은연도의기존held footprint 밖이면서exact missing·주boundary·STAC scene footprint 안에256×256 B02창이완전히들어가도록선택한다. B02/B03/B04/B08/B11/B12/SCL은같은scene이며각asset URI/STAC메타SHA·CRS·shape·affine·정수pixelwindow를고정한다.

최초계획의ETag/size는null이며 `HEAD_REQUIRED`다. 이것을live immutable pin으로보고하지않는다. 승인된단일pilot transaction의예산안에서HEAD로7개ETag/size를확인하고 `sealed-plan.json`을생성한후에만 Range GET을시작한다. URI추측·SAS저장·모르는호스트/redirect는금지한다. SAS는공식container token방식으로메모리에만캐시한다. 공식근거는 [Microsoft SDK SAS 구현](https://github.com/microsoft/planetary-computer-sdk-for-python/blob/main/planetary_computer/sas.py)이며, ETag조건은 [Azure Blob conditional headers](https://learn.microsoft.com/en-us/rest/api/storageservices/specifying-conditional-headers-for-blob-service-operations)를따른다.

`remote.py`는2초간격·최대80request·전체32MiB 본문한도·If-Match·정확한Content-Range/길이를검증한다. GDAL은urllib RangeReader만통해읽고직접network를호출하지않는다. 전체COG는다운로드하지않는다. Range오류/ETag변경/429를무시하거나재시도하지않으며첫실패회로로후속을중지한다. 계측은애플리케이션이읽어반환받은HTTP본문이며HTTP헤더/TLS·미측정내부buffer는실제수신량으로단정하지않는다.

### 제한 실행과 QA

`pilot.py`는기본preflight-only다. 명시execute의현재상한은 **1pilot/32MiB**다.7개native crop을새 `data/raw/sentinel-pilots/<key>/`에보존하고B11/B12를B02격자로bilinear, SCL을nearest정합한다. 기존CAS를덮어쓰지않는다.6밴드모두유효·SCL4/5/6/7/11 clear비율80%를QA기준으로사용한다. 부족하면데이터가생겼더라도BLOCKED로보고하고다음target을시작하지않는다.

실행전실제readonly preflight는old SHA `8e98e9ba033f015e4e289860166b87f67d81a10e12fee66c9b45481296caa44a`, collector0·lock0·429false·기존pending2·잔액1,685,992,536B로통과했다. 선택은EastJava2023, scene `S2A_MSIL2A_20230905T023531_R089_T49MFM_20240916T145247`, B02window `[1855,5348,256,256]`다. sourceplan과read-only근거는 `evidence/onemap_sentinel/pilot-unit-20261124/`에고정했다.

새단위시험은 **26PASS/7.75초**, 외부rasterio경고2건이다. 실제TIFF를합성Range transport로읽는검증, legacy/OS lock, CAS경합, idempotency, 원장원자교체실패, 미측정환불금지, HEADpin·SAS cache, 첫실패/429, 단일pilot QA/정산을검사했다. 이는실제HEAD/Range성공과구분한다.

### 전체 수집·승인 차단 유지

기존동시존재의반대인미피복은 **99.023259%**(clear기준99.110197%)다. 현재잔액약1.686GB는전체누락에대한승인·원가산정된수집계획을지원하지않으며, 단일32MiB pilot을허용할뿐이다. compressed COG 실제필요량·cloud재관측횟수·전기간전수취득량은미측정이다. 이잔액만으로전체확보가능/완료라고말하지않는다.

BIG기관·통계승인대기, 전체공간완료false, 독립정답미검증은계속별도blocker다. 성공pilot도훈련/승격/배포를열지않는다. 후속batch전에는이번새관측을원본등록/중복공간index에반영하고exactqueue와sourcepin을새버전으로갱신해야한다. 자동다음pilot은없다.

### 실제 단일 pilot 완료 — 2026-11-24

지정한1건이 **VERIFIED_REAL / PILOT_QA_PASS**로종료했다.7개HEAD의ETag·size를고정했고20개Range응답을조건부검증했다. 총28request는HTTP2008건(SAS1+HEAD7), HTTP20620건이다. Range본문 **7,471,104B**+SAS메타본문 **402B**=총 **7,471,506B**이며계측완전=true로동일값을정산했다. 오류0·4290·후속pilot0이다.32MiB예약전부를다운로드했다고표현하지않는다.

QA는6밴드와같은scene SCL의clear **65,536/65,536(100%)**로통과했다. nativeSCL에서품질mask를별도로다시정합해저장quality와동일함을확인했다. 이것은SCL기반관측품질검사이지모델정확도·독립정답·학습허용이아니다. 신규관측에는라벨이없고학습준비=false다.

- 원장SHA: `8e98e9ba033f015e4e289860166b87f67d81a10e12fee66c9b45481296caa44a` → **`b257db2925e5c4eac99081c5539216314c972d49dd6741f38f5780da7dd25de1`**.
- 현재전역잔액 **1,678,521,030B**. 이번예약의미사용분만정산해돌렸고기존pending2건및모든과거batch내용은그대로다.
- 기존원본manifestSHA `0c149628...4658`, migration receiptSHA `0204d1a1...56e5`, CAS객체수6,125개는불변이다. 기존data/CAS에는쓰지않았다.
- legacyexecution/ledger lock해제, collector종료, 추가pilot미시작이다.

실제원본은gitignore된 `data/raw/sentinel-pilots/sdss2-pilot-154d9f5e507eced7ddfa09038a78f551c6784fd6803f8ab5f3e015a55e45f010/`의7native TIFF와image/alignedSCL/quality3개다. 메타근거는 `pilot-unit-20261124/run-01/{sealed-plan.json,data-receipt.json,ledger-before.json,ledger-after.json,result.json}`, 별도검증은 `postflight-integrity.json`, 신규관측인계는 `incoming-observation-v2.json`이다.

실제일회실행은Python API `run_pilot(plan, sha256(plan), old_ledger, evidence/run-01, data/raw/sentinel-pilots, execute=True)`였다. 같은계획은current CAS SHA 불일치/기존idempotency key 때문에재실행하지않는다. 이미수집한새관측을기존aggregate에자동추가하지않았으므로위36셀0.976741%는기존snapshot값이다.1개pilot으로전체99%공백완료나예산충분성을주장하지않는다. API/UI·학습·승격·배포는이번에실행하지않았다.
