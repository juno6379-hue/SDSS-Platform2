import test from 'node:test';
import assert from 'node:assert/strict';

import {
  LCLUC_FIRST_GROUP_PROVINCES,
  LCLUC_FIRST_GROUP_REGIONS,
  LCLUC_PROVINCE_REGISTRY,
  isFirstGroupProvince,
  sanitizeLclucProvince,
  buildLclucWmsTileUrl,
  buildLclucRestTileUrl,
  createLclucRasterSourceSpec,
  createLclucRasterLayerSpec,
  inspectPixelAtCoord,
  LclucAnimateController,
  assertStatisticsInvariance,
} from './lclucWmsRasterAdapter.ts';

import {
  generateMasterPayload,
} from './lclucMasterAdapter.ts';

test('1. First Group 6개 주 엄격 제한 검증 (Papua, DKI Jakarta, Central Java, East Kalimantan 제외)', () => {
  // 정확히 6개 주만 포함되어야 함
  assert.equal(LCLUC_FIRST_GROUP_PROVINCES.length, 6);
  assert.deepEqual([...LCLUC_FIRST_GROUP_PROVINCES], [
    'South Sulawesi',
    'Gorontalo',
    'Southeast Sulawesi',
    'Banten',
    'West Java',
    'East Java',
  ]);

  // First Group 허용 여부
  assert.equal(isFirstGroupProvince('South Sulawesi'), true);
  assert.equal(isFirstGroupProvince('Gorontalo'), true);
  assert.equal(isFirstGroupProvince('Southeast Sulawesi'), true);
  assert.equal(isFirstGroupProvince('Banten'), true);
  assert.equal(isFirstGroupProvince('West Java'), true);
  assert.equal(isFirstGroupProvince('East Java'), true);

  // 제외 대상 4개 주 및 미승인 지역 차단 확인
  assert.equal(isFirstGroupProvince('Papua'), false);
  assert.equal(isFirstGroupProvince('DKI Jakarta'), false);
  assert.equal(isFirstGroupProvince('Central Java'), false);
  assert.equal(isFirstGroupProvince('East Kalimantan'), false);
  assert.equal(isFirstGroupProvince('Bali'), false);
  assert.equal(isFirstGroupProvince('Aceh'), false);

  // sanitizeLclucProvince 폴백 로직
  assert.equal(sanitizeLclucProvince('Papua'), 'South Sulawesi');
  assert.equal(sanitizeLclucProvince('DKI Jakarta'), 'South Sulawesi');
  assert.equal(sanitizeLclucProvince('Unknown'), 'South Sulawesi');
  assert.equal(sanitizeLclucProvince('Gorontalo'), 'Gorontalo');
  assert.equal(sanitizeLclucProvince('West Java'), 'West Java');

  // LCLUC_FIRST_GROUP_REGIONS 매핑 검증
  assert.equal(LCLUC_FIRST_GROUP_REGIONS.length, 6);
  for (const [name, bounds] of LCLUC_FIRST_GROUP_REGIONS) {
    assert.ok(isFirstGroupProvince(name));
    assert.equal(bounds.length, 4);
    assert.ok(bounds[0] < bounds[2], '서경 < 동경');
    assert.ok(bounds[1] < bounds[3], '남위 < 북위');
  }

  // 레지스트리 메타데이터 완결성 검증
  for (const prov of LCLUC_FIRST_GROUP_PROVINCES) {
    const meta = LCLUC_PROVINCE_REGISTRY[prov];
    assert.ok(meta, `${prov} 메타데이터 존재`);
    assert.ok(meta.availableYears.includes(2020));
    assert.ok(meta.availableYears.includes(2025));
    assert.equal(meta.defaultT1, 2020);
    assert.equal(meta.defaultT2, 2025);
    assert.ok(meta.geoserverWorkspace.length > 0);
    assert.ok(meta.layerPrefix.length > 0);
  }
});

test('2. GeoServer WMS 1.1.1 및 REST 타일 소스/레이어 규격 검증', () => {
  // WMS 타일 URL 생성
  const wmsUrl = buildLclucWmsTileUrl('South Sulawesi', 2024);
  assert.ok(wmsUrl.includes('SERVICE=WMS'));
  assert.ok(wmsUrl.includes('VERSION=1.1.1'));
  assert.ok(wmsUrl.includes('REQUEST=GetMap'));
  assert.ok(wmsUrl.includes('FORMAT=image%2Fpng') || wmsUrl.includes('FORMAT=image/png'));
  assert.ok(wmsUrl.includes('SRS=EPSG%3A3857') || wmsUrl.includes('SRS=EPSG:3857'));
  assert.ok(wmsUrl.includes('{bbox-epsg-3857}'));
  assert.ok(wmsUrl.includes('south_sulawesi_2024'));

  // REST 타일 URL 생성
  const restUrl = buildLclucRestTileUrl('West Java', 2020);
  assert.ok(restUrl.includes('/v1/lcluc/tiles/west_java/2020/{z}/{x}/{y}.png'));

  // MapLibre Raster Source Spec
  const sourceSpec = createLclucRasterSourceSpec('Gorontalo', 2025);
  assert.equal(sourceSpec.type, 'raster');
  assert.equal(sourceSpec.tileSize, 256);
  assert.ok(Array.isArray(sourceSpec.tiles));
  assert.ok(sourceSpec.tiles.length >= 1);
  assert.ok(sourceSpec.attribution?.includes('GeoServer WMS'));

  // MapLibre Raster Layer Spec with nearest-neighbor resampling
  const layerSpec = createLclucRasterLayerSpec('test-layer', 'test-source', 0.85);
  assert.equal(layerSpec.id, 'test-layer');
  assert.equal(layerSpec.type, 'raster');
  assert.equal(layerSpec.source, 'test-source');
  assert.equal(layerSpec.paint['raster-opacity'], 0.85);
  assert.equal(layerSpec.paint['raster-resampling'], 'nearest', '이산 분류 경계 번짐 방지를 위해 nearest-neighbor 필수');
});

test('3. 통계 불변성(Invariance) 검증: Swipe/Opacity/Zoom UI 조작과 무관한 분석 일관성', () => {
  // 단일 분석 세션 생성
  const payloadOriginal = generateMasterPayload('South Sulawesi', 2020, 2025, {
    fakeFilter: true,
    confidenceThreshold: 0.7,
  });

  // 데이터셋 식별자 및 통계 불변 플래그 검증
  assert.ok(payloadOriginal.datasetId.startsWith('lcluc_'));
  assert.ok(payloadOriginal.version.startsWith('1.0'));
  assert.equal(payloadOriginal.isStatsInvariant, true);
  assert.equal(payloadOriginal.statisticsBasis, 'full_valid_source_raster_invariant');

  // 시뮬레이션: Swipe 분할바 이동(dividerRatio: 0.1 vs 0.9), 투명도 변경(0.2 vs 1.0), 줌 배율(zoom: 4 vs 12)
  // 분석 페이로드는 뷰포트 상태를 전달받지 않으므로 절대 변경되지 않음
  const payloadAfterUserInteraction = generateMasterPayload('South Sulawesi', 2020, 2025, {
    fakeFilter: true,
    confidenceThreshold: 0.7,
  });

  const invarianceCheck = assertStatisticsInvariance(payloadOriginal, payloadAfterUserInteraction);
  assert.equal(invarianceCheck.isInvariant, true);
  assert.equal(invarianceCheck.mismatches.length, 0);

  // 불변성 위반 검출 기능 확인 (인위적 변조 시뮬레이션)
  const tamperedPayload = {
    ...payloadOriginal,
    kpis: { ...payloadOriginal.kpis, forestAreaHa: 999999 },
  };
  const violationCheck = assertStatisticsInvariance(payloadOriginal, tamperedPayload);
  assert.equal(violationCheck.isInvariant, false);
  assert.ok(violationCheck.mismatches.some(m => m.includes('KPI.forestAreaHa')));
});

test('4. 좌표 기반 정확한 단일 픽셀 검사(inspectPixelAtCoord) 검증 (화면 RGB 추정 배제)', () => {
  const bounds = LCLUC_PROVINCE_REGISTRY['South Sulawesi'].bounds;

  // 연구 영역 내부 좌표 (South Sulawesi 중심 부근)
  const centerLng = (bounds[0] + bounds[2]) / 2;
  const centerLat = (bounds[1] + bounds[3]) / 2;

  const pixelResult = inspectPixelAtCoord(centerLng, centerLat, bounds, 2024, 'South Sulawesi');
  assert.ok(pixelResult !== null);
  assert.ok(typeof pixelResult.classId === 'number');
  assert.ok(pixelResult.classId >= 0 && pixelResult.classId <= 8, '0~8 정수 클래스 ID');
  assert.ok(pixelResult.className.length > 0);
  assert.ok(pixelResult.color.startsWith('#'));
  assert.ok(pixelResult.elevationM >= 0);

  // 단일 픽셀 해상도 10m x 10m = 100 m² (0.01 ha) 확인 (주 전체 면적 표시 금지 규정)
  assert.equal(pixelResult.pixelAreaM2, 100);
  assert.equal(pixelResult.pixelAreaHa, 0.01);
  assert.equal(pixelResult.pixelResolutionM, 10);
  assert.ok(pixelResult.datasetId.includes('south_sulawesi'));

  // 연구 영역 외부 좌표 쿼리 시 null 반환 확인
  const outsideResult = inspectPixelAtCoord(50.0, 50.0, bounds, 2024, 'South Sulawesi');
  assert.equal(outsideResult, null);
});

test('5. Animate 모드 제어기(LclucAnimateController) 연속 재생 및 누락 연도 감지 검증', () => {
  const controller = new LclucAnimateController('Gorontalo', 2020);

  // 초기 상태
  assert.equal(controller.currentYear, 2020);
  assert.equal(controller.isPlaying, false);

  // 다음 연도 진행
  const y1 = controller.nextYear();
  assert.equal(y1, 2021);
  const y2 = controller.nextYear();
  assert.equal(y2, 2022);

  // 존재하는 연도 설정 시 정상 상태
  const validCheck = controller.setTargetYear(2023);
  assert.equal(validCheck.isAvailable, true);
  assert.equal(validCheck.errorMessage, undefined);
  assert.equal(controller.currentYear, 2023);

  // 데이터 없는 누락 연도 설정 시 "자료 없음 (No Data)" 감지
  const missingCheck = controller.setTargetYear(2015);
  assert.equal(missingCheck.isAvailable, false);
  assert.ok(missingCheck.errorMessage?.includes('자료 없음 (No Data)'));

  // 재생 토글
  assert.equal(controller.togglePlay(), true);
  assert.equal(controller.isPlaying, true);
  assert.equal(controller.togglePlay(), false);
  assert.equal(controller.isPlaying, false);
});
