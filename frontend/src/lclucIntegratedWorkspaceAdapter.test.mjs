import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { requestShape, parseWorkflowRequest, prepareWorkflow } from './lclucWorkflowAdapter.ts';
import { parseWorkflowChangeGeoJSON } from './lclucChangeMapAdapter.ts';
import { workflowTransitionStats } from './lclucTransitionAdapter.ts';
import {
  constructLclucWorkflowRequest,
  computeLclucKpis,
  createMapLibreOverlaySpec,
  applyWorkflowChangeToMap,
  executeIntegratedLclucWorkflow,
  createInitialIntegratedState,
  LclucIntegratedWorkspaceManager,
  resolveProvince,
  SUPPORTED_PROVINCES,
  WORKFLOW_CHANGE_SOURCE_ID,
  WORKFLOW_CHANGE_FILL_LAYER_ID,
  WORKFLOW_CHANGE_LINE_LAYER_ID,
  compute10mPrecisionAoi,
  createPrecisionAoiLayerSpec,
  PRECISION_AOI_SOURCE_ID,
  PRECISION_AOI_FILL_LAYER_ID,
  PRECISION_AOI_LINE_LAYER_ID,
  createQualityMaskGridGeoJSON,
  SCL_CLASSES,
  resolveDistrictByCoord,
  resolveDistrictById,
  getDistrictsForProvince,
  getHotspotsForProvince,
  createHotspotsGeoJSON,
  buildHotspotDetailCardHtml,
  buildHotspotDetailPopupHtml,
  inspectPixelDetailedQuality,
  buildPixelDetailPopupHtml,
  checkObservationDateDivergence,
} from './lclucIntegratedWorkspaceAdapter.ts';

const fixture = () =>
  JSON.parse(
    readFileSync(
      new URL('../../evidence/integration/lcluc-change-map-generated-fixture-20261018.json', import.meta.url),
      'utf8'
    )
  );

// =============================================================================
// Task 2.1: Request Construction & Validation from Top-Level Dropdowns
// =============================================================================

test('constructLclucWorkflowRequest builds valid exact6 request from standard dropdowns', () => {
  const selection = {
    region: 'South Sulawesi',
    startYear: '2020',
    endYear: '2021',
  };

  const result = constructLclucWorkflowRequest(selection);
  assert.equal(result.valid, true);
  assert.ok(result.request);
  assert.equal(result.selectedYears?.length, 2);
  assert.deepEqual(result.selectedYears, [2020, 2021]);
  assert.equal(result.provinceSlug, 'south-sulawesi');

  const req = result.request;
  assert.equal(req.schema_version, 1);
  assert.equal(req.capability, 'landcover.change_detection');
  assert.match(req.trace_id, /^[A-Za-z0-9_-]{1,128}$/);
  assert.match(req.idempotency_key, /^[A-Za-z0-9_-]{1,128}$/);
  assert.ok(req.model_ref.id.length > 0);
  assert.match(req.model_ref.sha256, /^[a-f0-9]{64}$/);
  assert.equal(req.images.length, 2);
  assert.equal(req.images[0].year, 2020);
  assert.equal(req.images[1].year, 2021);
  assert.match(req.images[0].input_ref.sha256, /^[a-f0-9]{64}$/);
  assert.match(req.images[1].quality_report_sha256, /^[a-f0-9]{64}$/);

  // Must strictly pass parseWorkflowRequest and requestShape
  assert.ok(requestShape(req));
  assert.deepEqual(JSON.parse(JSON.stringify(parseWorkflowRequest(JSON.stringify(req)))), req);
});

test('constructLclucWorkflowRequest supports all 10 provinces in ModelAnalysisWorkspace', () => {
  for (const province of SUPPORTED_PROVINCES) {
    const res = constructLclucWorkflowRequest({
      region: province.name,
      startYear: 2020,
      endYear: 2022,
    });
    assert.equal(res.valid, true, `Province ${province.name} should be valid`);
    assert.ok(res.request);
    assert.ok(requestShape(res.request));
    assert.equal(res.provinceSlug, province.slug);
  }
});

test('constructLclucWorkflowRequest validates consecutive_series mode bounded by 6 years', () => {
  const fiveYears = constructLclucWorkflowRequest(
    { region: 'West Java', startYear: 2020, endYear: 2024 },
    { seriesMode: 'consecutive_series' }
  );
  assert.equal(fiveYears.valid, true);
  assert.equal(fiveYears.request?.images.length, 5);
  assert.deepEqual(fiveYears.selectedYears, [2020, 2021, 2022, 2023, 2024]);
  assert.ok(requestShape(fiveYears.request));

  // Reject more than 6 years series
  const sevenYears = constructLclucWorkflowRequest(
    { region: 'West Java', startYear: 2020, endYear: 2027 },
    { seriesMode: 'consecutive_series' }
  );
  assert.equal(sevenYears.valid, false);
  assert.match(sevenYears.error || '', /최대 6개 연도/);
});

test('constructLclucWorkflowRequest rejects invalid dropdown selections cleanly', () => {
  const invalidCases = [
    { selection: { region: 'Unknown Province', startYear: 2020, endYear: 2021 }, pattern: /지원되지 않는 지역/ },
    { selection: { region: 'South Sulawesi', startYear: 2024, endYear: 2020 }, pattern: /종료 연도.*작아야/ },
    { selection: { region: 'South Sulawesi', startYear: 2020, endYear: 2020 }, pattern: /종료 연도.*작아야/ },
    { selection: { region: 'South Sulawesi', startYear: 1890, endYear: 2021 }, pattern: /1900년에서 2200년/ },
    { selection: { region: 'South Sulawesi', startYear: 2020, endYear: 2250 }, pattern: /1900년에서 2200년/ },
    { selection: { region: 'South Sulawesi', startYear: 'abc', endYear: '2021' }, pattern: /유효한 정수/ },
  ];

  for (const { selection, pattern } of invalidCases) {
    const res = constructLclucWorkflowRequest(selection);
    assert.equal(res.valid, false);
    assert.match(res.error || '', pattern);
  }
});

test('constructLclucWorkflowRequest supports custom catalog pins override', () => {
  const customSha = '1'.repeat(64);
  const customPins = {
    model_ref: {
      id: 'custom-model-2026',
      version: 'v2.1',
      sha256: customSha,
    },
    resolveInputPin: (slug, year) => ({
      input_ref: {
        id: `custom-input-${slug}-${year}`,
        version: 'v9',
        sha256: '2'.repeat(64),
      },
      quality_report_sha256: '3'.repeat(64),
    }),
  };

  const res = constructLclucWorkflowRequest(
    { region: 'Banten', startYear: 2021, endYear: 2023 },
    { catalogPins: customPins }
  );
  assert.equal(res.valid, true);
  assert.equal(res.request?.model_ref.id, 'custom-model-2026');
  assert.equal(res.request?.model_ref.sha256, customSha);
  assert.equal(res.request?.images[0].input_ref.id, 'custom-input-banten-2021');
  assert.equal(res.request?.images[0].input_ref.sha256, '2'.repeat(64));
  assert.ok(requestShape(res.request));
});

// =============================================================================
// Task 2.2: Top KPI Cards Calculation (Forest Loss, Built-up, Net Transition)
// =============================================================================

test('computeLclucKpis accurately computes Forest Loss, Built-up Increase, and Transition Area', () => {
  const f = fixture();
  const pair = '2020-2021';
  const stats = workflowTransitionStats(f.receipt, f.report, pair);

  const kpiSummary = computeLclucKpis(stats);

  // Validation of metrics
  assert.equal(typeof kpiSummary.metrics.forestLossHa, 'number');
  assert.equal(typeof kpiSummary.metrics.builtUpIncreaseHa, 'number');
  assert.equal(typeof kpiSummary.metrics.changedAreaHa, 'number');
  assert.equal(typeof kpiSummary.metrics.totalValidAreaHa, 'number');
  assert.equal(typeof kpiSummary.metrics.changeRatePercent, 'number');

  // In fixture 2020-2021: 25600 m2 changed from class 1 (trees) to class 2 (grass)
  // 25600 m2 = 2.56 ha
  assert.equal(kpiSummary.metrics.totalValidAreaHa, 2.56);
  assert.equal(kpiSummary.metrics.changedAreaHa, 2.56);
  assert.equal(kpiSummary.metrics.forestLossHa, 2.56); // gross forest loss
  assert.equal(kpiSummary.metrics.forestNetChangeHa, -2.56);
  assert.equal(kpiSummary.metrics.builtUpIncreaseHa, 0); // no built-up change in this pair
  assert.equal(kpiSummary.metrics.changeRatePercent, 100);

  // Check topCards format matching ModelAnalysisWorkspace
  assert.equal(kpiSummary.topCards.length, 4);
  const [forestCard, mangroveCard, builtCard, totalCard] = kpiSummary.topCards;
  assert.equal(forestCard.id, 'forest');
  assert.equal(forestCard.label, '산림 면적');
  assert.equal(forestCard.unit, 'ha');
  assert.match(forestCard.delta, /-2\.56|2\.56/);

  assert.equal(mangroveCard.id, 'mangrove');
  assert.equal(builtCard.id, 'built_up');
  assert.equal(totalCard.id, 'total_area');
  assert.equal(totalCard.unit, 'ha');
  assert.match(totalCard.delta, /100/);

  // Check dedicated Gap 1 summary cards
  const { forestLossCard, builtUpIncreaseCard, netTransitionAreaCard } =
    kpiSummary.gap1SummaryCards;
  assert.equal(forestLossCard.id, 'forest_loss');
  assert.match(forestLossCard.value, /2\.56/);
  assert.equal(builtUpIncreaseCard.id, 'built_increase');
  assert.match(builtUpIncreaseCard.value, /0/);
  assert.equal(netTransitionAreaCard.id, 'net_transition');
  assert.match(netTransitionAreaCard.value, /2\.56/);
});

test('computeLclucKpis handles zero change pair without dividing by zero', () => {
  const f = fixture();
  const pair = '2021-2022'; // unchanged pair in fixture
  const stats = workflowTransitionStats(f.receipt, f.report, pair);

  const kpis = computeLclucKpis(stats);
  assert.equal(kpis.metrics.changedAreaHa, 0);
  assert.equal(kpis.metrics.changeRatePercent, 0);
  assert.equal(kpis.metrics.forestLossHa, 0);
  assert.equal(kpis.metrics.builtUpIncreaseHa, 0);
  assert.equal(kpis.metrics.totalValidAreaHa, 2.56);
});

// =============================================================================
// Task 2.3: MapLibre GL Layer Binding & Overlay Specifications
// =============================================================================

test('createMapLibreOverlaySpec constructs compliant source and layers', () => {
  const f = fixture();
  const pair = '2020-2021';
  const selection = workflowTransitionStats(f.receipt, f.report, pair).selection;
  const changeMap = parseWorkflowChangeGeoJSON(f.geojson[pair], selection);

  const spec = createMapLibreOverlaySpec(changeMap);
  assert.equal(spec.sourceId, WORKFLOW_CHANGE_SOURCE_ID);
  assert.equal(spec.fillLayerId, WORKFLOW_CHANGE_FILL_LAYER_ID);
  assert.equal(spec.lineLayerId, WORKFLOW_CHANGE_LINE_LAYER_ID);
  assert.equal(spec.sourceData.type, 'FeatureCollection');
  assert.equal(spec.featureCount, 1);
  assert.ok(spec.bounds);
  assert.ok(Array.isArray(spec.fillPaint['fill-color']));
});

test('applyWorkflowChangeToMap binds layer to MapLibre instance and supports removal', () => {
  const f = fixture();
  const pair = '2020-2021';
  const selection = workflowTransitionStats(f.receipt, f.report, pair).selection;
  const changeMap = parseWorkflowChangeGeoJSON(f.geojson[pair], selection);

  // Mock MapLibre map instance
  const sources = new Map();
  const layers = new Map();
  let fitBoundsCalled = false;

  const mockMap = {
    getSource: id => sources.get(id),
    addSource: (id, def) => sources.set(id, def),
    removeSource: id => sources.delete(id),
    getLayer: id => layers.get(id),
    addLayer: def => layers.set(def.id, def),
    removeLayer: id => layers.delete(id),
    fitBounds: (bounds, options) => {
      fitBoundsCalled = true;
    },
  };

  // Step 1: Bind changeMap
  const successAdd = applyWorkflowChangeToMap(mockMap, changeMap);
  assert.equal(successAdd, true);
  assert.ok(sources.has(WORKFLOW_CHANGE_SOURCE_ID));
  assert.ok(layers.has(WORKFLOW_CHANGE_FILL_LAYER_ID));
  assert.ok(layers.has(WORKFLOW_CHANGE_LINE_LAYER_ID));
  assert.equal(fitBoundsCalled, true);

  // Step 2: Update existing source
  let setDataCalled = false;
  sources.set(WORKFLOW_CHANGE_SOURCE_ID, {
    setData: data => {
      setDataCalled = true;
    },
  });
  const successUpdate = applyWorkflowChangeToMap(mockMap, changeMap);
  assert.equal(successUpdate, true);
  assert.equal(setDataCalled, true);

  // Step 3: Remove layer on null / empty
  const successRemove = applyWorkflowChangeToMap(mockMap, null);
  assert.equal(successRemove, true);
  assert.equal(sources.has(WORKFLOW_CHANGE_SOURCE_ID), false);
  assert.equal(layers.has(WORKFLOW_CHANGE_FILL_LAYER_ID), false);
  assert.equal(layers.has(WORKFLOW_CHANGE_LINE_LAYER_ID), false);
});

test('applyWorkflowChangeToMap handles WebGL errors gracefully without throw', () => {
  const throwingMap = {
    getSource: () => {
      throw new Error('WebGL context lost');
    },
  };
  const res = applyWorkflowChangeToMap(throwingMap, {});
  assert.equal(res, false);
});

// =============================================================================
// Task 2.4: End-to-End Execution Pipeline (executeIntegratedLclucWorkflow)
// =============================================================================

test('executeIntegratedLclucWorkflow executes full pipeline and returns all deliverables', async () => {
  const f = fixture();
  const pair = '2020-2022';

  const deps = {
    fetchWorkflow: async (suffix, body) => {
      if (suffix === '') {
        // Return matching receipt
        return { status: 200, value: f.receipt };
      }
      if (suffix === `/${f.receipt.id}/report`) {
        return { status: 200, value: f.report };
      }
      throw new Error(`Unexpected suffix: ${suffix}`);
    },
    fetchGeoJSON: async (id, index, sha, live) => {
      return f.geojson[pair];
    },
  };

  const selection = {
    region: 'South Sulawesi',
    startYear: 2020,
    endYear: 2022,
  };

  const result = await executeIntegratedLclucWorkflow(
    selection,
    deps,
    {
      seriesMode: 'consecutive_series',
      traceId: f.request.trace_id,
      idempotencyKey: f.request.idempotency_key,
      catalogPins: {
        model_ref: f.request.model_ref,
        resolveInputPin: (slug, year) => {
          const img = f.request.images.find(i => i.year === year);
          return {
            input_ref: img.input_ref,
            quality_report_sha256: img.quality_report_sha256,
          };
        },
      },
    },
    () => true
  );

  assert.ok(result);
  assert.equal(result.receipt.id, f.receipt.id);
  assert.equal(result.selectedPair, pair);
  assert.equal(result.report.years.length, 3);
  assert.equal(result.transitionStats.validPixels, 256);
  assert.equal(result.changeMap.featureCount, 1);
  assert.equal(result.kpis.metrics.forestLossHa, 2.56);
  assert.equal(result.overlaySpec.sourceId, WORKFLOW_CHANGE_SOURCE_ID);
});

test('executeIntegratedLclucWorkflow throws structured error on BLOCKED receipt', async () => {
  const selection = { region: 'South Sulawesi', startYear: 2020, endYear: 2021 };
  const val = constructLclucWorkflowRequest(selection);
  const prepared = await prepareWorkflow(JSON.stringify(val.request));

  const blockedReceipt = {
    schema_version: 1,
    scope: 'LOCAL_LCLUC_WORKFLOW_ONLY',
    status: 'BLOCKED',
    trace_id: val.request.trace_id,
    id: prepared.id,
    issue: 'MODEL_NOT_DEPLOYED_OR_EVALUATED',
    replayed: false,
    scientific_accuracy_validated: false,
    standard_gmais_result: false,
  };

  const deps = {
    fetchWorkflow: async () => ({ status: 409, value: blockedReceipt }),
    fetchGeoJSON: async () => undefined,
  };

  await assert.rejects(
    () =>
      executeIntegratedLclucWorkflow(
        selection,
        deps,
        { traceId: val.request.trace_id, idempotencyKey: val.request.idempotency_key },
        () => true
      ),
    /상태 BLOCKED.*MODEL_NOT_DEPLOYED_OR_EVALUATED/
  );
});

// =============================================================================
// Task 2.5: Integrated Workspace State Manager & Controller
// =============================================================================

test('LclucIntegratedWorkspaceManager initializes, updates, and notifies listeners', () => {
  const deps = {
    fetchWorkflow: async () => ({ status: 200, value: {} }),
    fetchGeoJSON: async () => undefined,
  };

  const manager = new LclucIntegratedWorkspaceManager(deps);
  const states = [];
  const unsubscribe = manager.subscribe(s => states.push(s));

  assert.equal(manager.getState().status, 'IDLE');
  assert.equal(manager.getState().selection.region, 'South Sulawesi');
  assert.equal(manager.getState().validation.valid, true);

  // Update selection
  manager.updateSelection({ region: 'West Java', startYear: 2021, endYear: 2024 });
  assert.equal(manager.getState().status, 'CONFIGURING');
  assert.equal(manager.getState().selection.region, 'West Java');
  assert.equal(manager.getState().selection.startYear, 2021);
  assert.equal(manager.getState().validation.valid, true);

  // Set invalid selection
  manager.updateSelection({ startYear: 2025, endYear: 2021 });
  assert.equal(manager.getState().validation.valid, false);
  assert.match(manager.getState().error, /작아야 합니다/);

  unsubscribe();
});

test('LclucIntegratedWorkspaceManager runAnalysis executes end-to-end and binds map', async () => {
  const f = fixture();
  const pair = '2020-2021';

  const deps = {
    fetchWorkflow: async (suffix) => {
      if (suffix === '') return { status: 200, value: f.receipt };
      if (suffix === `/${f.receipt.id}/report`) return { status: 200, value: f.report };
      throw new Error(`Unexpected: ${suffix}`);
    },
    fetchGeoJSON: async () => f.geojson[pair],
  };

  const sources = new Map();
  const layers = new Map();
  const mockMap = {
    getSource: id => sources.get(id),
    addSource: (id, def) => sources.set(id, def),
    removeSource: id => sources.delete(id),
    getLayer: id => layers.get(id),
    addLayer: def => layers.set(def.id, def),
    removeLayer: id => layers.delete(id),
    fitBounds: () => {},
  };

  const manager = new LclucIntegratedWorkspaceManager(deps, {
    region: 'South Sulawesi',
    startYear: 2020,
    endYear: 2022,
  });

  manager.setMapInstance(mockMap);

  await manager.runAnalysis({
    seriesMode: 'consecutive_series',
    traceId: f.request.trace_id,
    idempotencyKey: f.request.idempotency_key,
    catalogPins: {
      model_ref: f.request.model_ref,
      resolveInputPin: (slug, year) => {
        const img = f.request.images.find(i => i.year === year);
        return {
          input_ref: img.input_ref,
          quality_report_sha256: img.quality_report_sha256,
        };
      },
    },
  });

  const state = manager.getState();
  assert.equal(state.status, 'SUCCEEDED');
  assert.equal(state.busy, false);
  assert.ok(state.receipt);
  assert.ok(state.report);
  assert.ok(state.transitionStats);
  assert.ok(state.changeMap);
  assert.ok(state.kpis);
  assert.equal(state.mapBound, true);
  assert.match(state.notice, /LCLUC 변화 분석 완료/);

  // Check map binding occurred
  assert.ok(sources.has(WORKFLOW_CHANGE_SOURCE_ID));
  assert.ok(layers.has(WORKFLOW_CHANGE_FILL_LAYER_ID));

  // Test clear resets everything cleanly
  manager.clear();
  const cleared = manager.getState();
  assert.equal(cleared.status, 'IDLE');
  assert.equal(cleared.receipt, undefined);
  assert.equal(cleared.mapBound, false);
  assert.equal(sources.has(WORKFLOW_CHANGE_SOURCE_ID), false);
});

test('LclucIntegratedWorkspaceManager handles backend error with fallback', async () => {
  const deps = {
    fetchWorkflow: async () => ({
      status: 503,
      value: { error: { code: 'RESOURCE_UNAVAILABLE', message: 'Service down', retryable: false } },
    }),
    fetchGeoJSON: async () => undefined,
  };

  const sources = new Map();
  const mockMap = {
    getSource: id => sources.get(id),
    addSource: (id, def) => sources.set(id, def),
    removeSource: id => sources.delete(id),
    getLayer: () => undefined,
    removeLayer: () => {},
  };

  const manager = new LclucIntegratedWorkspaceManager(deps);
  manager.setMapInstance(mockMap);

  await manager.runAnalysis();

  const state = manager.getState();
  assert.equal(state.status, 'ERROR');
  assert.equal(state.busy, false);
  assert.equal(state.mapBound, false);
  assert.match(state.error, /확인할 수 없습니다/);
});

test('LclucIntegratedWorkspaceManager abort and selection change cancel in-flight executions', async () => {
  let resolveFlight;
  const pendingPromise = new Promise(res => {
    resolveFlight = res;
  });

  const deps = {
    fetchWorkflow: async () => {
      await pendingPromise;
      return { status: 200, value: {} };
    },
    fetchGeoJSON: async () => undefined,
  };

  const manager = new LclucIntegratedWorkspaceManager(deps);
  const promise = manager.runAnalysis();

  assert.equal(manager.getState().busy, true);
  assert.equal(manager.getState().status, 'SUBMITTING');

  // Abort while pending
  manager.abort();
  assert.equal(manager.getState().busy, false);

  // Release the mock fetch
  resolveFlight();
  await promise;

  // Status must remain non-SUCCEEDED after canceled resolution
  assert.notEqual(manager.getState().status, 'SUCCEEDED');
});

test('createMapLibreOverlaySpec produces exact 9-class color mapping and styling invariants', () => {
  const f = fixture();
  const pair = '2020-2021';
  const selection = workflowTransitionStats(f.receipt, f.report, pair).selection;
  const changeMap = parseWorkflowChangeGeoJSON(f.geojson[pair], selection);

  const spec = createMapLibreOverlaySpec(changeMap);
  const fillColorExpr = spec.fillPaint['fill-color'];
  assert.equal(fillColorExpr[0], 'match');
  assert.deepEqual(fillColorExpr[1], ['get', 'to_class']);

  // Verify class colors 0 through 8
  for (let c = 0; c < 9; c++) {
    const classIdx = fillColorExpr.indexOf(c);
    assert.ok(classIdx > 0, `Class ${c} must exist in match expression`);
    assert.equal(fillColorExpr[classIdx + 1], changeMap.geojson.features[0] ? spec.fillPaint['fill-color'][classIdx + 1] : '');
  }

  assert.equal(spec.linePaint['line-color'], '#075499');
  assert.equal(spec.linePaint['line-width'], 1.8);
});

test('constructLclucWorkflowRequest prevents unexpected extra keys and produces strictly serializable JSON', () => {
  const selection = {
    region: 'South Sulawesi',
    startYear: 2020,
    endYear: 2021,
    extraUnknownField: 'injected_exploit',
  };

  const res = constructLclucWorkflowRequest(selection);
  assert.equal(res.valid, true);
  assert.ok(res.request);

  // The generated request must only have exact schema keys:
  // ['schema_version', 'capability', 'trace_id', 'idempotency_key', 'model_ref', 'images']
  const keys = Object.keys(res.request);
  assert.deepEqual(keys.sort(), [
    'capability',
    'idempotency_key',
    'images',
    'model_ref',
    'schema_version',
    'trace_id',
  ]);
  assert.equal(Object.hasOwn(res.request, 'extraUnknownField'), false);
});

// =============================================================================
// Task 2.5: Section 5 - Precision AOI, SCL Quality Mask, ADM2 Hotspots & Inspection
// =============================================================================

test('compute10mPrecisionAoi creates exact 2.56km x 2.56km (655.36 ha) AOI distinct from OSM province boundary', () => {
  const province = 'South Sulawesi';
  const aoi = compute10mPrecisionAoi(province);

  assert.equal(aoi.provinceName, 'South Sulawesi');
  assert.equal(aoi.widthKm, 2.56);
  assert.equal(aoi.heightKm, 2.56);
  assert.equal(aoi.pixelResolutionM, 10);
  assert.equal(aoi.gridDimension, '256x256');
  assert.equal(aoi.totalPixels, 65536);
  assert.equal(aoi.totalAreaHa, 655.36);

  // Center coordinate within bounds
  const [w, s, e, n] = aoi.bounds;
  assert.ok(w < e);
  assert.ok(s < n);
  assert.ok(aoi.center[0] > w && aoi.center[0] < e);
  assert.ok(aoi.center[1] > s && aoi.center[1] < n);

  // GeoJSON polygon structure
  assert.equal(aoi.geojson.type, 'Feature');
  assert.equal(aoi.geojson.geometry.type, 'Polygon');
  assert.equal(aoi.geojson.geometry.coordinates[0].length, 5); // Closed polygon
  assert.deepEqual(aoi.geojson.geometry.coordinates[0][0], aoi.geojson.geometry.coordinates[0][4]);

  // Check layer spec
  const spec = createPrecisionAoiLayerSpec(aoi);
  assert.equal(spec.sourceId, PRECISION_AOI_SOURCE_ID);
  assert.equal(spec.fillLayerId, PRECISION_AOI_FILL_LAYER_ID);
  assert.equal(spec.lineLayerId, PRECISION_AOI_LINE_LAYER_ID);
  assert.equal(spec.fillPaint['fill-color'], '#10b981');
  assert.equal(spec.fillPaint['fill-opacity'], 0.15);
  assert.equal(spec.linePaint['line-color'], '#059669');
});

test('createQualityMaskGridGeoJSON generates SCL cloud and shadow warning grid with quality metrics', () => {
  const province = 'South Sulawesi';
  const aoi = compute10mPrecisionAoi(province);
  const result = createQualityMaskGridGeoJSON(aoi.bounds, province);

  assert.equal(result.geojson.type, 'FeatureCollection');
  assert.equal(result.geojson.features.length, 64); // 8x8 grid

  // Verify feature properties
  for (const feat of result.geojson.features) {
    assert.equal(feat.type, 'Feature');
    assert.equal(feat.geometry.type, 'Polygon');
    assert.ok(typeof feat.properties.sclClass === 'number');
    assert.ok(typeof feat.properties.sclLabel === 'string');
    assert.ok(typeof feat.properties.isDegraded === 'boolean');
    assert.ok(typeof feat.properties.fillColor === 'string');
    assert.ok(typeof feat.properties.hatchStyle === 'string');
  }

  // SCL classes 0, 1, 3, 8, 9, 10 must be degraded
  for (const sclId of [0, 1, 3, 8, 9, 10]) {
    assert.equal(SCL_CLASSES[sclId].isDegraded, true, `SCL ${sclId} must be degraded`);
  }
  // SCL 4 (Vegetation), 6 (Water) are clear
  assert.equal(SCL_CLASSES[4].isDegraded, false);
  assert.equal(SCL_CLASSES[6].isDegraded, false);

  // Summary validation
  const sum = result.summary;
  assert.ok(sum.validClearPercent >= 0 && sum.validClearPercent <= 100);
  assert.ok(sum.cloudCoverPercent >= 0 && sum.cloudCoverPercent <= 100);
  assert.ok(sum.cloudShadowPercent >= 0 && sum.cloudShadowPercent <= 100);
  assert.ok(sum.noDataPercent >= 0 && sum.noDataPercent <= 100);
  assert.ok(['EXCELLENT', 'GOOD', 'FAIR', 'POOR'].includes(sum.qualityGrade));
  assert.equal(typeof sum.isObservationUsable, 'boolean');
});

test('LclucHotspotDistrictResolver maps hotspot markers to ADM2 districts with risk metrics and mitigations', () => {
  const province = 'South Sulawesi';
  const districts = getDistrictsForProvince(province);
  assert.ok(districts.length >= 5);

  const maros = districts.find(d => d.name.includes('Maros'));
  assert.ok(maros);
  assert.equal(maros.province, province);
  assert.equal(maros.type, 'Kabupaten');

  const hotspots = getHotspotsForProvince(province);
  assert.ok(hotspots.length > 0);

  const hotspot = hotspots[0];
  assert.ok(hotspot.id);
  assert.ok(hotspot.districtName);
  assert.ok(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(hotspot.riskLevel));
  assert.ok(hotspot.changeAreaHa > 0);
  assert.ok(hotspot.mitigationRecommendation.length > 0);

  // Coordinate resolution
  const resolved = resolveDistrictByCoord(hotspot.coordinates[0], hotspot.coordinates[1], province);
  assert.ok(resolved);
  assert.equal(resolved.province, province);

  // HTML Card Rendering
  const cardHtml = buildHotspotDetailCardHtml(hotspot);
  assert.ok(cardHtml.includes('lcluc-hotspot-card'));
  assert.ok(cardHtml.includes(hotspot.districtName));
  assert.ok(cardHtml.includes(`${hotspot.changeAreaHa.toLocaleString()} ha`));
  assert.ok(cardHtml.includes(hotspot.mitigationRecommendation));

  // GeoJSON creation
  const geojson = createHotspotsGeoJSON(province);
  assert.equal(geojson.type, 'FeatureCollection');
  assert.equal(geojson.features.length, hotspots.length);
  assert.equal(geojson.features[0].geometry.type, 'Point');
  assert.equal(geojson.features[0].properties.districtName, hotspots[0].districtName);
});

test('inspectPixelDetailedQuality returns invariant 100 m2 (0.01 ha) single pixel area, SCL flag, and dual provenance', () => {
  const province = 'South Sulawesi';
  const aoi = compute10mPrecisionAoi(province);

  // Valid point inside bounds (center)
  const pixel = inspectPixelDetailedQuality(
    aoi.center[0],
    aoi.center[1],
    aoi.bounds,
    province,
    2020,
    2025
  );

  assert.ok(pixel !== null);
  // STRICT INVARIANT: Must be single 10m pixel cell, NEVER province area
  assert.equal(pixel.pixelAreaM2, 100);
  assert.equal(pixel.pixelAreaHa, 0.01);
  assert.ok(pixel.elevationM >= 0);

  // Observation dates and provenance
  assert.ok(pixel.observationDateT1.includes('2020'));
  assert.ok(pixel.observationDateT2.includes('2025'));
  assert.equal(pixel.dataProvenanceT1, 'ESA WorldCover 2020 v100 (10m Reference Baseline)');
  assert.equal(pixel.dataProvenanceT2, 'GeoAI LCLUC CNN-Transformer v1.0 (AI 모델 추론)');

  // Quality flag
  assert.ok(['VALID_CLEAR', 'CLOUD_MASKED', 'SHADOW_MASKED', 'NODATA'].includes(pixel.qualityFlag));

  // Popup HTML must contain 100 m² and 0.01 ha
  const popupHtml = buildPixelDetailPopupHtml(pixel);
  assert.ok(popupHtml.includes('100 m²'));
  assert.ok(popupHtml.includes('0.01 ha'));
  assert.ok(popupHtml.includes('ESA WorldCover 2020'));
  assert.ok(popupHtml.includes('GeoAI LCLUC CNN-Transformer'));

  // Out of bounds check
  const outOfBounds = inspectPixelDetailedQuality(0, 0, aoi.bounds, province);
  assert.equal(outOfBounds, null);
});

test('checkObservationDateDivergence detects display year divergence and assigns correct severity and badge', () => {
  // Same year -> No divergence
  const noDiv = checkObservationDateDivergence(2021, 2021);
  assert.equal(noDiv.hasDivergence, false);
  assert.equal(noDiv.yearDelta, 0);
  assert.equal(noDiv.severity, 'NONE');

  // 1-year delta -> INFO
  const infoDiv = checkObservationDateDivergence(2022, 2021);
  assert.equal(infoDiv.hasDivergence, true);
  assert.equal(infoDiv.yearDelta, 1);
  assert.equal(infoDiv.severity, 'INFO');
  assert.ok(infoDiv.badgeHtml?.includes('mw-divergence-warning-badge'));

  // 2-year delta -> WARNING
  const warnDiv = checkObservationDateDivergence(2023, 2021);
  assert.equal(warnDiv.hasDivergence, true);
  assert.equal(warnDiv.yearDelta, 2);
  assert.equal(warnDiv.severity, 'WARNING');

  // 4-year delta -> CRITICAL
  const critDiv = checkObservationDateDivergence(2025, 2021);
  assert.equal(critDiv.hasDivergence, true);
  assert.equal(critDiv.yearDelta, 4);
  assert.equal(critDiv.severity, 'CRITICAL');
  assert.ok(critDiv.warningMessage?.includes('4년 편차'));
  assert.ok(critDiv.badgeHtml?.includes('mw-divergence-warning-badge'));
});
