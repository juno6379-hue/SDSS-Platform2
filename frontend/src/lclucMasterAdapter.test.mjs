import test from 'node:test';
import assert from 'node:assert/strict';
import {
  LclucMasterController,
  LCLUC_MASTER_TABS,
  generateMasterPayload,
  generateCsvTransitionMatrix,
  generateCsvTimeSeries,
  generateExecutiveHtmlReport,
} from './lclucMasterAdapter.ts';
import { SUPPORTED_PROVINCES } from './lclucIntegratedWorkspaceAdapter.ts';

// =============================================================================
// 1. Definition and Schema Invariants
// =============================================================================

test('LCLUC_MASTER_TABS contains all 7 core capability tabs with complete metadata', () => {
  assert.equal(LCLUC_MASTER_TABS.length, 7);
  const expectedIds = ['map', 'timeseries', 'change', 'matrix', 'hotspot', 'compare', 'export'];
  const ids = LCLUC_MASTER_TABS.map(t => t.id);
  assert.deepEqual(ids, expectedIds);

  for (const tab of LCLUC_MASTER_TABS) {
    assert.ok(tab.label.length > 0);
    assert.ok(tab.englishLabel.length > 0);
    assert.ok(tab.icon.length > 0);
    assert.ok(tab.description.length > 0);
  }
});

// =============================================================================
// 2. Controller Initialization, Tab Switching & State Preservation
// =============================================================================

test('LclucMasterController initializes with valid defaults and notifies subscribers', () => {
  const controller = new LclucMasterController('South Sulawesi', 2020, 2024);
  const state = controller.getState();

  assert.equal(state.activeTab, 'map');
  assert.equal(state.province, 'South Sulawesi');
  assert.equal(state.startYear, 2020);
  assert.equal(state.endYear, 2024);
  assert.equal(state.busy, false);
  assert.equal(state.status, 'READY');
  assert.equal(state.filterOptions.opacity, 0.75);
  assert.equal(state.filterOptions.fakeFilterEnabled, true);
  assert.equal(state.filterOptions.confidenceThreshold, 0.70);
  assert.equal(state.filterOptions.activeClasses.length, 9);
  assert.ok(state.payload);
});

test('LclucMasterController preserves filter and province state across 7 tab transitions', () => {
  const controller = new LclucMasterController('West Java', 2021, 2025);
  controller.setOpacity(0.42);
  controller.setUnit('pixels');

  const tabList = ['map', 'timeseries', 'change', 'matrix', 'hotspot', 'compare', 'export'];

  for (const tab of tabList) {
    controller.setTab(tab);
    const s = controller.getState();
    assert.equal(s.activeTab, tab);
    assert.equal(s.province, 'West Java');
    assert.equal(s.startYear, 2021);
    assert.equal(s.endYear, 2025);
    assert.equal(s.filterOptions.opacity, 0.42);
    assert.equal(s.filterOptions.unit, 'pixels');
  }
});

// =============================================================================
// 3. User Controls, Validation & Threshold Bounds
// =============================================================================

test('LclucMasterController validates year order and bounds numeric inputs', () => {
  const controller = new LclucMasterController('Banten', 2020, 2023);

  // Invalid year order
  controller.setYears(2024, 2020);
  assert.match(controller.getState().error, /작아야 합니다/);

  // Equal years invalid
  controller.setYears(2022, 2022);
  assert.match(controller.getState().error, /작아야 합니다/);

  // Valid year order clears error
  controller.setYears(2021, 2024);
  assert.equal(controller.getState().error, '');
  assert.equal(controller.getState().startYear, 2021);
  assert.equal(controller.getState().endYear, 2024);

  // Opacity clamping
  controller.setOpacity(-0.5);
  assert.equal(controller.getState().filterOptions.opacity, 0);
  controller.setOpacity(1.5);
  assert.equal(controller.getState().filterOptions.opacity, 1);
  controller.setOpacity(0.65);
  assert.equal(controller.getState().filterOptions.opacity, 0.65);

  // Class toggle
  assert.equal(controller.getState().filterOptions.activeClasses[1], true);
  controller.toggleClass(1);
  assert.equal(controller.getState().filterOptions.activeClasses[1], false);
  controller.toggleClass(1);
  assert.equal(controller.getState().filterOptions.activeClasses[1], true);
});

// =============================================================================
// 4. Data Adapter Mathematical Integrity (7 Modules)
// =============================================================================

test('generateMasterPayload produces consistent data across all 10 provinces', () => {
  for (const prov of SUPPORTED_PROVINCES) {
    const payload = generateMasterPayload(prov.name, 2020, 2024);
    assert.equal(payload.province, prov.name);
    assert.equal(payload.startYear, 2020);
    assert.equal(payload.endYear, 2024);

    // Module 2: Time-series checks
    assert.equal(payload.timeSeries.years.length, 5);
    assert.equal(payload.timeSeries.annualPoints.length, 5);
    assert.equal(payload.timeSeries.trajectories.length, 9);
    for (const pt of payload.timeSeries.annualPoints) {
      assert.equal(pt.classAreasHa.length, 9);
      const sum = pt.classAreasHa.reduce((a, b) => a + b, 0);
      assert.ok(Math.abs(sum - pt.totalAreaHa) < 1.0, `Sum ${sum} must approximate total ${pt.totalAreaHa}`);
    }

    // Module 4: Transition Matrix 9x9 checks
    assert.equal(payload.transitionMatrix.matrixHa.length, 9);
    assert.equal(payload.transitionMatrix.matrixPixels.length, 9);
    assert.equal(payload.transitionMatrix.topFlows.length, 5);
    assert.equal(payload.transitionMatrix.gainLossList.length, 9);

    let matrixTotalHa = 0;
    for (let r = 0; r < 9; r++) {
      for (let c = 0; c < 9; c++) {
        matrixTotalHa += payload.transitionMatrix.matrixHa[r][c];
      }
    }
    assert.ok(matrixTotalHa > 0);

    // Module 5: Hotspot checks
    assert.equal(payload.hotspots.method, 'Getis-Ord Gi*');
    assert.ok(payload.hotspots.clusters.length >= 3);
    for (const cl of payload.hotspots.clusters) {
      assert.ok(cl.zScore > 0);
      assert.ok(cl.areaHa > 0);
      assert.ok(['99%', '95%', '90%'].includes(cl.confidence));
    }

    // Module 6: Regional 10-province benchmark checks
    assert.equal(payload.regionalComparison.benchmarks.length, 10);
    assert.equal(payload.regionalComparison.benchmarks[0].rank, 1);
    assert.equal(payload.regionalComparison.benchmarks[9].rank, 10);
  }
});

test('Unit 340 Fake Change Filter toggle modifies change detection statistics', () => {
  const rawPayload = generateMasterPayload('South Sulawesi', 2020, 2024, { fakeFilter: false });
  const filteredPayload = generateMasterPayload('South Sulawesi', 2020, 2024, { fakeFilter: true });

  // Filtered change area must be smaller than raw change area
  assert.equal(rawPayload.changeDetection.spuriousBouncesRemovedHa, 0);
  assert.ok(filteredPayload.changeDetection.spuriousBouncesRemovedHa > 0);
  assert.ok(filteredPayload.changeDetection.filteredChangedAreaHa < rawPayload.changeDetection.rawChangedAreaHa);
  assert.ok(filteredPayload.changeDetection.bounceRemovalRatioPct > 10);
});

test('Confidence threshold modifies high vs low confidence area partitioning', () => {
  const lowThresh = generateMasterPayload('East Kalimantan', 2020, 2024, { confidenceThreshold: 0.50 });
  const highThresh = generateMasterPayload('East Kalimantan', 2020, 2024, { confidenceThreshold: 0.90 });

  // Higher threshold requires stricter confidence, leaving less high-confidence area
  assert.ok(highThresh.changeDetection.highConfidenceAreaHa < lowThresh.changeDetection.highConfidenceAreaHa);
  assert.ok(highThresh.changeDetection.lowConfidenceFilteredHa > lowThresh.changeDetection.lowConfidenceFilteredHa);
});

// =============================================================================
// 5. Export Generation & Download Handler Integrity
// =============================================================================

test('generateCsvTransitionMatrix produces valid 10x10 CSV matrix', () => {
  const p = generateMasterPayload('Gorontalo', 2020, 2023);
  const csv = generateCsvTransitionMatrix(p.transitionMatrix);
  const lines = csv.trim().split('\n');

  assert.equal(lines.length, 10); // 1 header + 9 rows
  const headerCols = lines[0].split(',');
  assert.equal(headerCols.length, 10); // 1 label col + 9 classes
});

test('generateCsvTimeSeries produces valid multi-year CSV with all columns', () => {
  const p = generateMasterPayload('Papua', 2020, 2024);
  const csv = generateCsvTimeSeries(p.timeSeries);
  const lines = csv.trim().split('\n');

  assert.equal(lines.length, 6); // 1 header + 5 year rows
  assert.match(lines[0], /연도,(Water|수체),(Trees|산림)/);
});

test('generateExecutiveHtmlReport contains executive metadata and valid HTML tags', () => {
  const p = generateMasterPayload('DKI Jakarta', 2020, 2024);
  const html = generateExecutiveHtmlReport(p);

  assert.match(html, /<!DOCTYPE html>/);
  assert.match(html, /DKI Jakarta 토지피복 및 토지이용 변화 종합 보고서/);
  assert.match(html, /총 산림 감소량/);
  assert.match(html, /Getis-Ord Gi\*/);
  assert.match(html, /Workflow ID:/);
});

test('triggerDownload produces valid filenames and MIME types for all 5 formats', () => {
  const controller = new LclucMasterController('Central Java', 2020, 2024);

  const formats = ['csv', 'html', 'geojson', 'geotiff', 'zip'];
  const expectedExts = ['.csv', '.html', '.geojson', '.tif', '.zip'];
  const expectedMimes = [
    'text/csv;charset=utf-8;',
    'text/html;charset=utf-8;',
    'application/geo+json;charset=utf-8;',
    'application/octet-stream',
    'application/octet-stream',
  ];

  for (let i = 0; i < formats.length; i++) {
    const res = controller.triggerDownload(formats[i]);
    assert.equal(res.success, true);
    assert.ok(res.filename.endsWith(expectedExts[i]), `File ${res.filename} must end with ${expectedExts[i]}`);
    assert.equal(res.mimeType, expectedMimes[i]);
  }
});

// =============================================================================
// 6. Asynchronous Run Analysis Flow
// =============================================================================

test('LclucMasterController runAnalysis executes async transition pipeline', async () => {
  const controller = new LclucMasterController('Southeast Sulawesi', 2020, 2023);
  const states = [];
  const unsub = controller.subscribe(s => states.push(s.status));

  const promise = controller.runAnalysis();
  assert.equal(controller.getState().busy, true);
  assert.equal(controller.getState().status, 'LOADING');

  await promise;

  assert.equal(controller.getState().busy, false);
  assert.equal(controller.getState().status, 'READY');
  assert.match(controller.getState().notice, /Southeast Sulawesi.*갱신 완료/);
  assert.ok(states.includes('LOADING'));
  assert.ok(states.includes('READY'));

  unsub();
});
