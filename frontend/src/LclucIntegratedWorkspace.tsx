/**
 * LCLUC Integrated Workspace Component (UX Gap 1 & CODEX Section 5 Implementation)
 *
 * Integrates:
 * 1. OSM Official Administrative Boundaries & 10m Precision Study Area (2.56km × 2.56km = 655.36 ha)
 * 2. Sentinel-2 SCL Cloud / Shadow Mask & Degraded Area Visualization
 * 3. Hotspot Marker to ADM2 District (Kabupaten / Kota) Integration & Detail Cards
 * 4. Detailed Single-Pixel Quality & Provenance Inspection (100 m² = 0.01 ha single cell)
 * 5. Satellite Observation Date vs Map Display Year Divergence Warning Badge
 *
 * Mirrored from isolated workspace: evidence/integration/lcluc-ui-workspace-20261019/
 */

import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import {
  LclucIntegratedWorkspaceManager,
  SUPPORTED_PROVINCES,
  SUPPORTED_YEARS,
  compute10mPrecisionAoi,
  createPrecisionAoiLayerSpec,
  createQualityMaskGridGeoJSON,
  checkObservationDateDivergence,
  getHotspotsForProvince,
  createHotspotsGeoJSON,
  buildHotspotDetailCardHtml,
  inspectPixelDetailedQuality,
  buildPixelDetailPopupHtml,
  OSM_BOUNDARY_SOURCE_ID,
  OSM_BOUNDARY_LINE_LAYER_ID,
  PRECISION_AOI_SOURCE_ID,
  PRECISION_AOI_FILL_LAYER_ID,
  PRECISION_AOI_LINE_LAYER_ID,
  type HotspotMarkerInfo,
  type DetailedPixelQualityResult,
  type IntegratedWorkspaceState,
} from './lclucIntegratedWorkspaceAdapter';
import { workflowFetch, workflowGeoJSON } from './lclucWorkflowClient';

export interface LclucIntegratedWorkspaceProps {
  initialRegion?: string;
  initialStartYear?: number;
  initialEndYear?: number;
  onNavigateToWebGIS?: () => void;
}

export default function LclucIntegratedWorkspace({
  initialRegion = 'South Sulawesi',
  initialStartYear = 2020,
  initialEndYear = 2021,
  onNavigateToWebGIS,
}: LclucIntegratedWorkspaceProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);

  // Initialize integrated manager with real scoped client dependencies
  const [manager] = useState(() => {
    return new LclucIntegratedWorkspaceManager(
      {
        fetchWorkflow: workflowFetch,
        fetchGeoJSON: workflowGeoJSON,
      },
      {
        region: initialRegion,
        startYear: initialStartYear,
        endYear: initialEndYear,
      }
    );
  });

  const [state, setState] = useState<IntegratedWorkspaceState>(() => manager.getState());

  // Section 5 Layer Toggles & Interactive Inspection State
  const [showOsmBoundary, setShowOsmBoundary] = useState<boolean>(true);
  const [showPrecisionAoi, setShowPrecisionAoi] = useState<boolean>(true);
  const [showQualityMask, setShowQualityMask] = useState<boolean>(true);
  const [showHotspots, setShowHotspots] = useState<boolean>(true);
  const [selectedHotspot, setSelectedHotspot] = useState<HotspotMarkerInfo | null>(null);
  const [inspectedPixel, setInspectedPixel] = useState<DetailedPixelQualityResult | null>(null);

  // Derive Section 5 Precision AOI, Quality Mask, Hotspots, and Divergence Check
  const precisionAoi = useMemo(() => {
    return compute10mPrecisionAoi(state.selection.region);
  }, [state.selection.region]);

  const qualityMask = useMemo(() => {
    return createQualityMaskGridGeoJSON(precisionAoi.bounds, state.selection.region);
  }, [precisionAoi.bounds, state.selection.region]);

  const hotspots = useMemo(() => {
    return getHotspotsForProvince(state.selection.region);
  }, [state.selection.region]);

  // Check observation date divergence: Baseline Sentinel-2 composite reference is 2021
  const divergence = useMemo(() => {
    const compositeYear = 2021;
    return checkObservationDateDivergence(Number(state.selection.endYear), compositeYear);
  }, [state.selection.endYear]);

  // Keep selected hotspot synchronized when province changes
  useEffect(() => {
    if (hotspots.length > 0) {
      setSelectedHotspot(hotspots[0]);
    } else {
      setSelectedHotspot(null);
    }
    setInspectedPixel(null);
  }, [hotspots]);

  useEffect(() => {
    const unsubscribe = manager.subscribe(nextState => {
      setState(nextState);
    });
    return () => {
      unsubscribe();
      manager.abort();
    };
  }, [manager]);

  // Setup MapLibre instance if maplibregl is loaded in window or runtime
  useEffect(() => {
    if (!mapContainerRef.current) return;
    let map: any = null;

    try {
      const maplibregl = (window as any).maplibregl;
      if (maplibregl && typeof maplibregl.Map === 'function') {
        map = new maplibregl.Map({
          container: mapContainerRef.current,
          style: {
            version: 8,
            sources: {
              imagery: {
                type: 'raster',
                tiles: [
                  'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                ],
                tileSize: 256,
              },
            },
            layers: [{ id: 'imagery', type: 'raster', source: 'imagery' }],
          },
          center: [precisionAoi.center[0], precisionAoi.center[1]],
          zoom: 11,
          attributionControl: { compact: true },
        });

        map.on('load', () => {
          mapInstanceRef.current = map;
          manager.setMapInstance(map);

          // 1. Add Precision AOI layer
          const aoiSpec = createPrecisionAoiLayerSpec(precisionAoi);
          if (!map.getSource(aoiSpec.sourceId)) {
            map.addSource(aoiSpec.sourceId, {
              type: 'geojson',
              data: aoiSpec.sourceData,
            });
            map.addLayer({
              id: aoiSpec.fillLayerId,
              type: 'fill',
              source: aoiSpec.sourceId,
              paint: aoiSpec.fillPaint,
            });
            map.addLayer({
              id: aoiSpec.lineLayerId,
              type: 'line',
              source: aoiSpec.sourceId,
              paint: aoiSpec.linePaint,
            });
          }

          // 2. Add SCL Quality Mask layer
          const maskSourceId = 'lcluc-quality-mask';
          const maskFillId = 'lcluc-quality-mask-fill';
          const maskLineId = 'lcluc-quality-mask-line';
          if (!map.getSource(maskSourceId)) {
            map.addSource(maskSourceId, {
              type: 'geojson',
              data: qualityMask.geojson,
            });
            map.addLayer({
              id: maskFillId,
              type: 'fill',
              source: maskSourceId,
              paint: {
                'fill-color': ['get', 'fillColor'],
                'fill-opacity': ['get', 'opacity'],
              },
            });
            map.addLayer({
              id: maskLineId,
              type: 'line',
              source: maskSourceId,
              paint: {
                'line-color': '#f59e0b',
                'line-width': 1.0,
                'line-dasharray': [2, 2],
              },
            });
          }

          // 3. Add Hotspot Markers
          const hotspotsSourceId = 'lcluc-hotspots';
          const hotspotsCircleId = 'lcluc-hotspots-circle';
          if (!map.getSource(hotspotsSourceId)) {
            const hotspotsGeoJSON = createHotspotsGeoJSON(state.selection.region);
            map.addSource(hotspotsSourceId, {
              type: 'geojson',
              data: hotspotsGeoJSON,
            });
            map.addLayer({
              id: hotspotsCircleId,
              type: 'circle',
              source: hotspotsSourceId,
              paint: {
                'circle-radius': 7,
                'circle-color': [
                  'match',
                  ['get', 'riskLevel'],
                  'CRITICAL', '#dc2626',
                  'HIGH', '#ea580c',
                  'MEDIUM', '#eab308',
                  '#10b981',
                ],
                'circle-stroke-width': 2,
                'circle-stroke-color': '#ffffff',
              },
            });
          }

          // Map Click: Detailed Pixel Inspection
          map.on('click', (e: any) => {
            if (!e || !e.lngLat) return;
            const { lng, lat } = e.lngLat;
            const pixel = inspectPixelDetailedQuality(
              lng,
              lat,
              precisionAoi.bounds,
              state.selection.region,
              Number(state.selection.startYear),
              Number(state.selection.endYear)
            );
            if (pixel) {
              setInspectedPixel(pixel);
            }
          });
        });
      }
    } catch (err) {
      console.warn('MapLibre GL initialization skipped or unsupported in environment:', err);
    }

    return () => {
      if (map) {
        map.remove();
        mapInstanceRef.current = null;
        manager.setMapInstance(null);
      }
    };
  }, [manager, precisionAoi, qualityMask, state.selection]);

  // Synchronize layer visibility with toggles
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;
    try {
      if (map.getLayer(PRECISION_AOI_FILL_LAYER_ID)) {
        map.setLayoutProperty(PRECISION_AOI_FILL_LAYER_ID, 'visibility', showPrecisionAoi ? 'visible' : 'none');
        map.setLayoutProperty(PRECISION_AOI_LINE_LAYER_ID, 'visibility', showPrecisionAoi ? 'visible' : 'none');
      }
      if (map.getLayer('lcluc-quality-mask-fill')) {
        map.setLayoutProperty('lcluc-quality-mask-fill', 'visibility', showQualityMask ? 'visible' : 'none');
        map.setLayoutProperty('lcluc-quality-mask-line', 'visibility', showQualityMask ? 'visible' : 'none');
      }
      if (map.getLayer('lcluc-hotspots-circle')) {
        map.setLayoutProperty('lcluc-hotspots-circle', 'visibility', showHotspots ? 'visible' : 'none');
      }
    } catch (e) {
      // Ignored if layers not ready
    }
  }, [showPrecisionAoi, showQualityMask, showHotspots]);

  const handleRegionChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      manager.updateSelection({ region: e.target.value });
    },
    [manager]
  );

  const handleStartYearChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      manager.updateSelection({ startYear: e.target.value });
    },
    [manager]
  );

  const handleEndYearChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      manager.updateSelection({ endYear: e.target.value });
    },
    [manager]
  );

  const handleRunAnalysis = useCallback(() => {
    void manager.runAnalysis();
  }, [manager]);

  const handleClear = useCallback(() => {
    manager.clear();
  }, [manager]);

  // Sample center pixel inspection handler
  const handleInspectCenterPixel = useCallback(() => {
    const pixel = inspectPixelDetailedQuality(
      precisionAoi.center[0],
      precisionAoi.center[1],
      precisionAoi.bounds,
      state.selection.region,
      Number(state.selection.startYear),
      Number(state.selection.endYear)
    );
    setInspectedPixel(pixel);
  }, [precisionAoi, state.selection]);

  return (
    <div className="lcluc-integrated-workspace" style={{ padding: '16px', background: '#f8fafc' }}>
      {/* Top Filter Bar */}
      <header
        style={{
          display: 'flex',
          gap: '12px',
          alignItems: 'center',
          flexWrap: 'wrap',
          background: '#ffffff',
          padding: '12px 16px',
          borderRadius: '8px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        }}
      >
        <label style={{ display: 'flex', flexDirection: 'column', fontSize: '13px', fontWeight: 600 }}>
          지역 (Province)
          <select
            value={state.selection.region}
            onChange={handleRegionChange}
            disabled={state.busy}
            style={{ padding: '6px 10px', borderRadius: '4px', marginTop: '4px' }}
          >
            {SUPPORTED_PROVINCES.map(p => (
              <option key={p.id} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', fontSize: '13px', fontWeight: 600 }}>
          시작 연도
          <select
            value={state.selection.startYear}
            onChange={handleStartYearChange}
            disabled={state.busy}
            style={{ padding: '6px 10px', borderRadius: '4px', marginTop: '4px' }}
          >
            {SUPPORTED_YEARS.map(y => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', fontSize: '13px', fontWeight: 600 }}>
          종료 연도
          <select
            value={state.selection.endYear}
            onChange={handleEndYearChange}
            disabled={state.busy}
            style={{ padding: '6px 10px', borderRadius: '4px', marginTop: '4px' }}
          >
            {SUPPORTED_YEARS.map(y => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>

        {/* Observation Date Divergence Warning Badge */}
        {divergence.hasDivergence && (
          <div
            className="mw-divergence-warning-badge"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              background: divergence.severity === 'CRITICAL' ? '#fef2f2' : divergence.severity === 'WARNING' ? '#fff7ed' : '#f0f9ff',
              color: divergence.severity === 'CRITICAL' ? '#dc2626' : divergence.severity === 'WARNING' ? '#ea580c' : '#0284c7',
              border: `1px solid ${divergence.severity === 'CRITICAL' ? '#fca5a5' : divergence.severity === 'WARNING' ? '#fed7aa' : '#bae6fd'}`,
              padding: '6px 12px',
              borderRadius: '16px',
              fontSize: '12px',
              fontWeight: 700,
            }}
            title={divergence.warningMessage}
          >
            <span>⚠️ 관측 연도 편차 ({divergence.yearDelta}년)</span>
            <small style={{ fontWeight: 500, opacity: 0.85 }}>
              (표출: {divergence.displayYear}년 vs 위성실측: {divergence.observationYear}년)
            </small>
          </div>
        )}

        {/* Quality Grade Pill */}
        <div
          className="mw-quality-grade-pill"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            background: qualityMask.summary.qualityGrade === 'EXCELLENT' || qualityMask.summary.qualityGrade === 'GOOD' ? '#ecfdf5' : '#fffbeb',
            color: qualityMask.summary.qualityGrade === 'EXCELLENT' || qualityMask.summary.qualityGrade === 'GOOD' ? '#065f46' : '#92400e',
            border: `1px solid ${qualityMask.summary.qualityGrade === 'EXCELLENT' || qualityMask.summary.qualityGrade === 'GOOD' ? '#a7f3d0' : '#fde68a'}`,
            padding: '6px 12px',
            borderRadius: '16px',
            fontSize: '12px',
            fontWeight: 700,
          }}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: qualityMask.summary.qualityGrade === 'EXCELLENT' || qualityMask.summary.qualityGrade === 'GOOD' ? '#10b981' : '#f59e0b',
            }}
          />
          <span>Quality Grade: {qualityMask.summary.qualityGrade}</span>
          <span style={{ fontWeight: 500, opacity: 0.85 }}>({qualityMask.summary.validClearPercent}% Valid Clear)</span>
        </div>

        {/* Top Run Button (Bridge to Workflow) */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            type="button"
            className="mw-run-button"
            onClick={handleRunAnalysis}
            disabled={state.busy || !state.validation.valid}
            style={{
              padding: '8px 18px',
              backgroundColor: state.busy ? '#94a3b8' : '#087d41',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 700,
              cursor: state.busy || !state.validation.valid ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>{state.busy ? '분석 실행 중…' : '▶ 분석 실행'}</span>
          </button>

          {state.busy && (
            <button
              type="button"
              onClick={handleClear}
              style={{
                padding: '8px 12px',
                background: '#f1f5f9',
                border: '1px solid #cbd5e1',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              중단
            </button>
          )}
        </div>
      </header>

      {/* Layer Controls Bar (Section 5: OSM, Precision AOI, SCL Quality, Hotspots) */}
      <section
        style={{
          display: 'flex',
          gap: '16px',
          alignItems: 'center',
          flexWrap: 'wrap',
          background: '#ffffff',
          padding: '10px 16px',
          borderRadius: '8px',
          marginTop: '10px',
          boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
          fontSize: '12.5px',
        }}
      >
        <span style={{ fontWeight: 700, color: '#334155' }}>레이어 오버레이:</span>
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showOsmBoundary}
            onChange={e => setShowOsmBoundary(e.target.checked)}
          />
          <span style={{ color: '#0284c7', fontWeight: 600 }}>OSM 행정경계 (ADM1)</span>
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showPrecisionAoi}
            onChange={e => setShowPrecisionAoi(e.target.checked)}
          />
          <span style={{ color: '#059669', fontWeight: 600 }}>
            10m 정밀 연구지역 ({precisionAoi.widthKm}km × {precisionAoi.heightKm}km = {precisionAoi.totalAreaHa} ha)
          </span>
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showQualityMask}
            onChange={e => setShowQualityMask(e.target.checked)}
          />
          <span style={{ color: '#d97706', fontWeight: 600 }}>Sentinel-2 SCL 품질 마스크 (구름/그림자 차폐 경고)</span>
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showHotspots}
            onChange={e => setShowHotspots(e.target.checked)}
          />
          <span style={{ color: '#dc2626', fontWeight: 600 }}>변화 핫스팟 (ADM2 시군구 연계)</span>
        </label>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
          <button
            type="button"
            onClick={handleInspectCenterPixel}
            style={{
              padding: '4px 10px',
              borderRadius: '4px',
              border: '1px solid #0284c7',
              background: '#eff6ff',
              color: '#0284c7',
              fontWeight: 600,
              fontSize: '11.5px',
              cursor: 'pointer',
            }}
          >
            🔍 단일 픽셀 정밀 검사 (중심 10m)
          </button>
        </div>
      </section>

      {/* Notice & Error Banners */}
      {state.notice && (
        <div
          role="status"
          style={{
            margin: '12px 0',
            padding: '10px 14px',
            background: '#ecfdf5',
            borderLeft: '4px solid #10b981',
            color: '#065f46',
            borderRadius: '4px',
            fontSize: '14px',
          }}
        >
          {state.notice}
        </div>
      )}

      {state.error && (
        <div
          role="alert"
          style={{
            margin: '12px 0',
            padding: '10px 14px',
            background: '#fef2f2',
            borderLeft: '4px solid #ef4444',
            color: '#991b1b',
            borderRadius: '4px',
            fontSize: '14px',
          }}
        >
          <strong>실행 오류:</strong> {state.error}
        </div>
      )}

      {/* Top KPI Cards (Updated from Transition Statistics) */}
      <section style={{ margin: '16px 0' }}>
        <h3 style={{ fontSize: '16px', marginBottom: '8px', color: '#1e293b' }}>
          주요 지표 ({state.selection.region} · {state.selectedPair || `${state.selection.startYear}–${state.selection.endYear}`})
        </h3>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '12px',
          }}
        >
          {state.kpis ? (
            state.kpis.topCards.map(card => (
              <div
                key={card.id}
                style={{
                  background: '#ffffff',
                  padding: '14px 16px',
                  borderRadius: '8px',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                  borderTop: '3px solid #087d41',
                }}
              >
                <div style={{ fontSize: '13px', color: '#64748b' }}>{card.label}</div>
                <div style={{ fontSize: '24px', fontWeight: 700, color: '#0f172a', margin: '4px 0' }}>
                  {card.value} <small style={{ fontSize: '14px', fontWeight: 500 }}>{card.unit}</small>
                </div>
                <div
                  style={{
                    fontSize: '12px',
                    fontWeight: 600,
                    color: card.delta.startsWith('-') ? '#dc2626' : '#16a34a',
                  }}
                >
                  {card.delta}
                </div>
                <small style={{ fontSize: '11px', color: '#94a3b8', display: 'block', marginTop: '4px' }}>
                  {card.subtext}
                </small>
              </div>
            ))
          ) : (
            <div
              style={{
                gridColumn: '1 / -1',
                padding: '16px',
                background: '#ffffff',
                borderRadius: '8px',
                color: '#64748b',
                textAlign: 'center',
              }}
            >
              분석 실행 대기 중 · "분석 실행" 버튼을 누르면 검증된 통계와 산림 손실·시가지 증가 지표가 계산됩니다.
            </div>
          )}
        </div>
      </section>

      {/* Dedicated Gap 1 KPI Summary Cards (Forest Loss, Built-up Increase, Net Transition Area) */}
      {state.kpis && (
        <section
          style={{
            margin: '16px 0',
            background: '#ffffff',
            padding: '16px',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
          }}
        >
          <h4 style={{ fontSize: '15px', color: '#0f172a', marginBottom: '10px' }}>
            LCLUC 변화 요약 (Gap 1 핵심 지표)
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            <div style={{ padding: '10px', background: '#fef2f2', borderRadius: '6px' }}>
              <div style={{ fontSize: '12px', color: '#991b1b', fontWeight: 600 }}>Forest Loss (산림 감소)</div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#dc2626' }}>
                {state.kpis.gap1SummaryCards.forestLossCard.value} ha
              </div>
              <small style={{ fontSize: '11px', color: '#7f1d1d' }}>
                {state.kpis.gap1SummaryCards.forestLossCard.subtext}
              </small>
            </div>

            <div style={{ padding: '10px', background: '#f0fdf4', borderRadius: '6px' }}>
              <div style={{ fontSize: '12px', color: '#166534', fontWeight: 600 }}>Built-up Increase (시가지 증가)</div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#15803d' }}>
                {state.kpis.gap1SummaryCards.builtUpIncreaseCard.value} ha
              </div>
              <small style={{ fontSize: '11px', color: '#14532d' }}>
                {state.kpis.gap1SummaryCards.builtUpIncreaseCard.subtext}
              </small>
            </div>

            <div style={{ padding: '10px', background: '#eff6ff', borderRadius: '6px' }}>
              <div style={{ fontSize: '12px', color: '#1e40af', fontWeight: 600 }}>Net Transition (전환 면적)</div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#2563eb' }}>
                {state.kpis.gap1SummaryCards.netTransitionAreaCard.value} ha
              </div>
              <small style={{ fontSize: '11px', color: '#1e3a8a' }}>
                {state.kpis.gap1SummaryCards.netTransitionAreaCard.subtext}
              </small>
            </div>
          </div>
        </section>
      )}

      {/* Main MapLibre GL ResearchMap Container */}
      <section
        style={{
          height: '440px',
          background: '#0f172a',
          borderRadius: '8px',
          position: 'relative',
          overflow: 'hidden',
          boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
        }}
      >
        <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />

        {/* Map State Indicator Overlay */}
        <div
          style={{
            position: 'absolute',
            top: '12px',
            left: '12px',
            background: 'rgba(15, 23, 42, 0.85)',
            color: '#f8fafc',
            padding: '8px 12px',
            borderRadius: '6px',
            fontSize: '12px',
            backdropFilter: 'blur(4px)',
            maxWidth: '380px',
          }}
        >
          <strong>{state.selection.region}</strong> · {state.selection.startYear}–{state.selection.endYear}
          <div style={{ fontSize: '11px', color: state.mapBound ? '#4ade80' : '#fbbf24', marginTop: '2px' }}>
            {state.mapBound
              ? `LCLUC 변화 레이어 연결 · 도형 ${state.changeMap?.featureCount ?? 0}개`
              : '과학모델 레이어 대기 중'}
          </div>
          <div style={{ fontSize: '10.5px', color: '#94a3b8', marginTop: '4px' }}>
            연구구역: {precisionAoi.widthKm}km × {precisionAoi.heightKm}km ({precisionAoi.totalAreaHa} ha) · 10m 정밀격자
          </div>
        </div>
      </section>

      {/* Section 5: Hotspots to ADM2 District Integration & Pixel Inspector Section */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: '16px',
          marginTop: '16px',
        }}
      >
        {/* Hotspots & ADM2 Integration Card */}
        <div
          style={{
            background: '#ffffff',
            padding: '16px',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            border: '1px solid #e2e8f0',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h4 style={{ fontSize: '14px', margin: 0, color: '#0f172a' }}>
              📍 변화 핫스팟 및 ADM2 시군구 연계 ({hotspots.length}개소 식별)
            </h4>
            <span style={{ fontSize: '11px', color: '#64748b' }}>클릭하여 상세 검토</span>
          </div>

          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
            {hotspots.map(h => (
              <button
                key={h.id}
                type="button"
                onClick={() => setSelectedHotspot(h)}
                style={{
                  padding: '5px 10px',
                  borderRadius: '6px',
                  border: selectedHotspot?.id === h.id ? '2px solid #0284c7' : '1px solid #cbd5e1',
                  background: selectedHotspot?.id === h.id ? '#eff6ff' : '#ffffff',
                  color: selectedHotspot?.id === h.id ? '#0284c7' : '#334155',
                  cursor: 'pointer',
                  fontSize: '11.5px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <span>{h.riskLevel === 'CRITICAL' ? '🔴' : h.riskLevel === 'HIGH' ? '🟠' : '🟡'}</span>
                <span>{h.districtName}</span>
                <small style={{ color: '#64748b' }}>({h.changeAreaHa} ha)</small>
              </button>
            ))}
          </div>

          {selectedHotspot && (
            <div
              className="lcluc-hotspot-card-wrapper"
              dangerouslySetInnerHTML={{ __html: buildHotspotDetailCardHtml(selectedHotspot) }}
            />
          )}
        </div>

        {/* Detailed Single-Pixel Quality & Provenance Inspector */}
        <div
          style={{
            background: '#ffffff',
            padding: '16px',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            border: '1px solid #e2e8f0',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h4 style={{ fontSize: '14px', margin: 0, color: '#0f172a' }}>
              🔬 단일 픽셀 정밀 검사 (10m Resolution Cell)
            </h4>
            <button
              type="button"
              onClick={handleInspectCenterPixel}
              style={{
                padding: '3px 8px',
                fontSize: '11px',
                borderRadius: '4px',
                background: '#f1f5f9',
                border: '1px solid #cbd5e1',
                cursor: 'pointer',
              }}
            >
              중심 좌표 샘플링
            </button>
          </div>

          {inspectedPixel ? (
            <div dangerouslySetInnerHTML={{ __html: buildPixelDetailPopupHtml(inspectedPixel) }} />
          ) : (
            <div
              style={{
                padding: '24px',
                textAlign: 'center',
                color: '#64748b',
                background: '#f8fafc',
                borderRadius: '6px',
                fontSize: '12px',
              }}
            >
              <div>지도를 클릭하거나 "중심 좌표 샘플링" 버튼을 누르면</div>
              <div style={{ marginTop: '4px', fontWeight: 600 }}>
                100 m² (0.01 ha) 단일 픽셀의 T1/T2 피복, SCL 품질 및 다중 출처(Provenance)가 표시됩니다.
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
