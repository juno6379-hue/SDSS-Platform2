import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { api, API_BASE } from './api';
import './TemporalCompare.css';

type PaletteEntry = { value: number; color: string; label?: string };
type AnnualLayer = {
  year: number; layer_id: string; tile_url: string; bbox: [number, number, number, number];
  source?: unknown; reference_kind?: string; palette?: PaletteEntry[]; synthetic?: boolean;
  asset_sha256?: string; asset_verification?: string; aoi_id?: string; crs?: string;
  affine?: number[]; bounds?: number[]; resolution?: number[]; shape?: number[];
  class_schema_id?: string; class_schema_version?: string; nodata?: number | null;
  mask_policy_version?: string; mask_asset_sha256?: string; evidence_state?: string;
};
type Series = {
  id: string; province: string; aoi_id?: string; title: string;
  kind: 'annual_reference' | 'model_prediction'; class_names?: string[];
  palette?: PaletteEntry[]; years: AnnualLayer[]; missing_years?: number[];
  blocked_years?: { year: number; reason: string }[]; registry_status?: string; synthetic?: boolean;
};
type Comparison = {
  comparison_id: string; left_layer_id: string; right_layer_id: string; preflight_status: string;
  visual_comparison_allowed: boolean; change_statistics_allowed: boolean;
  change_statistics_status: string; pixel_query_status: string; blockers: string[];
  matched_contract_fields: string[]; mismatched_contract_fields: string[]; evidence_state: string;
};
type Inventory = {
  schema_version?: string; contract_version?: string; registry_status?: string;
  authority?: { report?: string; sha256?: string; learning_ready?: boolean; status?: string };
  counts?: { model_prediction_layers?: number; registered_layers?: number; quality_eligible_rows?: number };
  change_statistics_status?: string; series: Series[]; comparisons?: Comparison[];
  issues?: { code: string; [key: string]: unknown }[]; limitations?: string[];
};

type Side = 'left' | 'right';
function sourceText(value: unknown) { return typeof value === 'string' ? value : value ? JSON.stringify(value) : '출처 미제공'; }
function shortSha(value?: string) { return value ? `${value.slice(0, 12)}…${value.slice(-8)}` : '없음'; }
function tileUrl(layer: AnnualLayer) {
  const template = layer.tile_url || `/api/data/landcover-layers/${encodeURIComponent(layer.layer_id)}/tiles/{z}/{x}/{y}.png`;
  if (/^https?:\/\//.test(template)) return template;
  if (template.startsWith('/api/')) return new URL(API_BASE, window.location.href).origin + template;
  return `${API_BASE}${template.startsWith('/') ? '' : '/'}${template}`;
}

function AnnualMaps({ left, right, swipe, position, onPositionChange }: {
  left: AnnualLayer; right?: AnnualLayer; swipe: boolean; position: number;
  onPositionChange: (value: number) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const leftContainer = useRef<HTMLDivElement>(null);
  const rightContainer = useRef<HTMLDivElement>(null);
  const maps = useRef<{ left?: maplibregl.Map; right?: maplibregl.Map }>({});
  const viewport = useRef<{ center: [number, number]; zoom: number; bearing: number; pitch: number } | undefined>(undefined);
  const dragging = useRef(false);
  const [errors, setErrors] = useState<Record<Side, string>>({ left: '', right: '' });
  const [loading, setLoading] = useState<Record<Side, boolean>>({ left: true, right: swipe });

  useEffect(() => {
    if (!leftContainer.current || !container.current) return;
    setErrors({ left: '', right: '' }); setLoading({ left: true, right: swipe });
    const ownOrigin = new URL(API_BASE, window.location.href).origin;
    function create(target: HTMLDivElement, layer: AnnualLayer, side: Side) {
      const map = new maplibregl.Map({ container: target, attributionControl: false,
        style: { version: 8, sources: { annual: { type: 'raster', tiles: [tileUrl(layer)], tileSize: 256 } },
          layers: [{ id: 'blank', type: 'background', paint: { 'background-color': '#e5ebe8' } },
            { id: 'annual', type: 'raster', source: 'annual', paint: { 'raster-resampling': 'nearest', 'raster-fade-duration': 0 } }] },
        center: viewport.current?.center || [(layer.bbox[0] + layer.bbox[2]) / 2, (layer.bbox[1] + layer.bbox[3]) / 2],
        zoom: viewport.current?.zoom || 9, bearing: viewport.current?.bearing || 0, pitch: viewport.current?.pitch || 0,
        transformRequest: url => {
          const token = sessionStorage.getItem('geoai_token');
          return { url, ...(url.startsWith(ownOrigin) && token ? { headers: { Authorization: `Bearer ${token}` } } : {}) };
        } });
      map.on('error', () => {
        setErrors(old => ({ ...old, [side]: `${side === 'left' ? '왼쪽' : '오른쪽'} ${layer.year} 타일을 불러오지 못했습니다.` }));
        setLoading(old => ({ ...old, [side]: false }));
      });
      map.on('idle', () => setLoading(old => ({ ...old, [side]: false })));
      return map;
    }
    const a = create(leftContainer.current, left, 'left');
    const b = swipe && right && rightContainer.current ? create(rightContainer.current, right, 'right') : undefined;
    maps.current = { left: a, right: b };
    if (!viewport.current) a.fitBounds(left.bbox, { padding: 35, duration: 0, maxZoom: 18 });
    let synchronizing = false;
    const syncFrom = (source: maplibregl.Map, target?: maplibregl.Map) => {
      if (synchronizing) return;
      const center = source.getCenter();
      viewport.current = { center: [center.lng, center.lat], zoom: source.getZoom(), bearing: source.getBearing(), pitch: source.getPitch() };
      if (target) {
        synchronizing = true;
        try { target.jumpTo(viewport.current); } finally { synchronizing = false; }
      }
    };
    const syncLeft = () => syncFrom(a, b);
    const syncRight = () => b && syncFrom(b, a);
    a.on('move', syncLeft); a.on('load', syncLeft); b?.on('move', syncRight); b?.on('load', syncRight);
    const observer = new ResizeObserver(() => { a.resize(); b?.resize(); syncLeft(); });
    observer.observe(container.current);
    return () => { observer.disconnect(); maps.current = {}; a.remove(); b?.remove(); };
  }, [swipe]);

  useEffect(() => {
    setErrors({ left: '', right: '' }); setLoading({ left: true, right: Boolean(swipe && right) });
    const pairs: [maplibregl.Map | undefined, AnnualLayer | undefined, Side][] = [
      [maps.current.left, left, 'left'], [maps.current.right, right, 'right']
    ];
    const listeners: (() => void)[] = [];
    for (const [map, layer] of pairs) {
      if (!map || !layer) continue;
      const update = () => (map.getSource('annual') as maplibregl.RasterTileSource | undefined)?.setTiles([tileUrl(layer)]);
      if (map.isStyleLoaded()) update(); else map.once('load', update);
      listeners.push(() => map.off('load', update));
    }
    return () => listeners.forEach(remove => remove());
  }, [left.layer_id, right?.layer_id, swipe]);

  function pointerPosition(clientX: number) {
    const rect = container.current?.getBoundingClientRect();
    if (rect?.width) onPositionChange(Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100)));
  }
  return <>
    <div className="temporal-map" ref={container}>
      <div className="temporal-map-canvas" ref={leftContainer}/>
      {swipe && <div className="temporal-map-canvas temporal-right" ref={rightContainer} style={{ clipPath: `inset(0 0 0 ${position}%)` }}/>}
      <span className="temporal-year temporal-year-left">{swipe ? '왼쪽 ' : ''}{left.year}</span>
      {swipe && <>
        <span className="temporal-year temporal-year-right">오른쪽 {right?.year}</span>
        <button type="button" className="temporal-divider-control" style={{ left: `${position}%` }}
          role="separator" aria-orientation="vertical" aria-label="Swipe 비교 경계"
          aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(position)}
          onPointerDown={event => { dragging.current = true; event.currentTarget.setPointerCapture(event.pointerId); pointerPosition(event.clientX); }}
          onPointerMove={event => { if (dragging.current) pointerPosition(event.clientX); }}
          onPointerUp={event => { dragging.current = false; event.currentTarget.releasePointerCapture(event.pointerId); }}
          onPointerCancel={() => { dragging.current = false; }}
          onKeyDown={event => {
            const delta = event.shiftKey ? 10 : 1;
            if (event.key === 'Home') { event.preventDefault(); onPositionChange(0); }
            if (event.key === 'End') { event.preventDefault(); onPositionChange(100); }
            if (event.key === 'ArrowLeft') { event.preventDefault(); onPositionChange(Math.max(0, position - delta)); }
            if (event.key === 'ArrowRight') { event.preventDefault(); onPositionChange(Math.min(100, position + delta)); }
          }}><span aria-hidden="true">↔</span></button>
      </>}
      {(loading.left || loading.right) && <span className="temporal-loading" role="status">
        {[loading.left && `왼쪽 ${left.year}`, loading.right && right && `오른쪽 ${right.year}`].filter(Boolean).join(' · ')} 타일 불러오는 중…
      </span>}
    </div>
    {errors.left && <p className="error" role="alert">{errors.left}</p>}
    {errors.right && <p className="error" role="alert">{errors.right}</p>}
  </>;
}

export default function TemporalCompare() {
  const [data, setData] = useState<Inventory>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [id, setId] = useState('');
  const [mode, setMode] = useState<'animate' | 'swipe'>('animate');
  const [frame, setFrame] = useState(0);
  const [rightIndex, setRightIndex] = useState(1);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1500);
  const [position, setPosition] = useState(50);
  const series = data?.series.find(row => row.id === id);
  const years = [...(series?.years || [])].sort((a, b) => a.year - b.year);
  const left = years[Math.min(frame, years.length - 1)];
  const right = years[Math.min(rightIndex, years.length - 1)];
  const comparison = data?.comparisons?.find(row => left && right && (
    (row.left_layer_id === left.layer_id && row.right_layer_id === right.layer_id) ||
    (row.left_layer_id === right.layer_id && row.right_layer_id === left.layer_id)));
  const swipeAllowed = Boolean(mode === 'swipe' && left && right && left.layer_id !== right.layer_id &&
    data?.registry_status !== 'BLOCKED' && comparison?.visual_comparison_allowed);

  async function refresh() {
    setBusy(true); setPlaying(false); setError('');
    try {
      const result = await api<Inventory>('/data/landcover-series');
      setData(result); setId(old => result.series.some(row => row.id === old) ? old : result.series[0]?.id || '');
      setFrame(0); setRightIndex(1);
    } catch (e) { setData(undefined); setId(''); setError(String(e)); } finally { setBusy(false); }
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => { setPlaying(false); setFrame(0); setRightIndex(1); }, [id, mode]);
  useEffect(() => {
    if (years.length > 1 && frame === rightIndex) setRightIndex(frame === years.length - 1 ? frame - 1 : frame + 1);
  }, [frame, rightIndex, years.length]);
  useEffect(() => {
    if (!playing || years.length < 2 || mode !== 'animate') return;
    const timer = window.setInterval(() => setFrame(old => (old + 1) % years.length), speed);
    return () => window.clearInterval(timer);
  }, [playing, speed, years.length, mode]);

  const palette = left?.palette || series?.palette || [];
  return <section className="panel temporal-panel">
    <div className="section-title"><div><span className="eyebrow">ANIMATE / SWIPE</span><h2>권위 원장 연차 지도 비교</h2></div>
      <button className="secondary" disabled={busy} onClick={() => void refresh()}>{busy ? '조회 중…' : '레이어 재조회'}</button></div>
    <p className="help">권위 원장이 참조한 실제 source window만 표시합니다. 같은 AOI·격자·스키마·마스크 계약을 통과한 두 시점만 Swipe합니다.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {data?.registry_status === 'BLOCKED' && <p className="readiness-warning" role="alert">레이어 registry가 차단되었습니다: {(data.issues || []).map(row => row.code).join(', ') || '원장 검증 오류'}</p>}
    {data && <div className="temporal-evidence-grid">
      <span>원장 상태<b>{data.registry_status || '미제공'}</b></span><span>계약<b>{data.contract_version || '미제공'}</b></span>
      <span>등록 레이어<b>{data.counts?.registered_layers ?? '미제공'}</b></span><span>모델 예측<b>{data.counts?.model_prediction_layers ?? '미제공'}</b></span>
    </div>}
    <label>연차 시리즈<select value={id} onChange={e => setId(e.target.value)}><option value="">시리즈 선택</option>
      {data?.series.map(row => <option key={row.id} value={row.id}>{row.title} · {row.kind === 'annual_reference' ? '연차 참조' : '모델 예측'}</option>)}</select></label>
    {data && !data.series.length && <p className="empty">권위 원장에서 표시 가능한 연차 레이어를 찾지 못했습니다.</p>}
    {series && <>
      <p className="hint">{series.kind === 'annual_reference' ? '연차 참조 라벨 · 모델 예측 아님' : '모델 예측 · 독립 지상정답 아님'} · {series.province} · AOI {series.aoi_id || '미제공'}</p>
      {(series.synthetic || left?.synthetic) && <p className="readiness-warning">합성 fixture · 실제 관측·모델 정확도 아님</p>}
      <p className="help">확보 연도: {years.map(row => row.year).join(', ') || '없음'} · 누락 연도: {series.missing_years === undefined ? '서버 미제공' : series.missing_years.length ? series.missing_years.join(', ') : '없음'}
        {series.blocked_years?.length ? ` · 충돌 차단: ${series.blocked_years.map(row => row.year).join(', ')}` : ''}</p>
      <div className="button-row"><button className={mode === 'animate' ? '' : 'secondary'} onClick={() => setMode('animate')}>Animate 자동 재생</button>
        <button className={mode === 'swipe' ? '' : 'secondary'} onClick={() => setMode('swipe')}>Swipe 좌우 비교</button></div>
      {years.length < 2 && <p className="readiness-warning">실제 확보 레이어가 {years.length}개입니다. 두 연도 비교는 두 개 이상의 등록 레이어가 필요합니다.</p>}
      {left && <>{mode === 'animate' ? <div className="temporal-controls">
        <button disabled={years.length < 2} onClick={() => setPlaying(old => !old)}>{playing ? '일시 정지' : '재생'}</button>
        <label>재생 간격<select value={speed} onChange={e => setSpeed(Number(e.target.value))}><option value={500}>0.5초</option><option value={1500}>1.5초</option><option value={3000}>3초</option></select></label>
        <label>표시 연도 {left.year}<input aria-label="애니메이션 연도" type="range" min={0} max={Math.max(0, years.length - 1)} value={frame} disabled={years.length < 2} onChange={e => { setPlaying(false); setFrame(Number(e.target.value)); }}/></label>
      </div> : <>
        <div className="temporal-controls"><label>왼쪽 연도<select value={frame} onChange={e => setFrame(Number(e.target.value))}>{years.map((row, i) => <option key={row.layer_id} value={i}>{row.year}</option>)}</select></label>
          <label>오른쪽 연도<select value={Math.min(rightIndex, years.length - 1)} disabled={years.length < 2} onChange={e => setRightIndex(Number(e.target.value))}>{years.map((row, i) => <option key={row.layer_id} value={i} disabled={i === frame}>{row.year}</option>)}</select></label>
          <label>좌우 경계 {Math.round(position)}%<input aria-label="Swipe 비교 경계" type="range" min={0} max={100} value={position} onChange={e => setPosition(Number(e.target.value))}/></label></div>
        <div className="temporal-presets" aria-label="Swipe 경계 프리셋"><button type="button" className="secondary" onClick={() => setPosition(100)}>왼쪽 100%</button><button type="button" className="secondary" onClick={() => setPosition(50)}>50 / 50</button><button type="button" className="secondary" onClick={() => setPosition(0)}>오른쪽 100%</button></div>
        <div className={`temporal-contract ${comparison?.visual_comparison_allowed ? 'ready' : 'blocked'}`} role="status">
          <b>{comparison?.preflight_status || 'BLOCKED_NO_COMPARISON_CONTRACT'}</b>
          <span>comparison_id: {comparison?.comparison_id || '없음'}</span>
          {comparison?.blockers.length ? <span>차단 사유: {comparison.blockers.join(', ')}</span> : <span>AOI/CRS/affine/bounds/resolution/shape/schema/NoData/mask 일치</span>}
        </div>
      </>}
      {(mode !== 'swipe' || swipeAllowed) && <AnnualMaps key={series.id} left={left} right={right} swipe={swipeAllowed} position={position} onPositionChange={setPosition}/>}
      {mode === 'swipe' && !swipeAllowed && <p className="readiness-warning" role="alert">비교 preflight가 통과되지 않아 두 레이어를 겹치지 않았습니다.</p>}
      <p className="help temporal-source">왼쪽 {left.year}: {left.reference_kind || series.kind} · SHA {shortSha(left.asset_sha256)} · {sourceText(left.source)}
        {mode === 'swipe' && right && <><br/>오른쪽 {right.year}: {right.reference_kind || series.kind} · SHA {shortSha(right.asset_sha256)} · {sourceText(right.source)}</>}</p>
      {mode === 'swipe' && comparison && <div className="temporal-stat-block" role="status">
        <b>변화·면적·전이행렬: {comparison.change_statistics_allowed ? '사용 가능' : '차단'}</b>
        <span>{comparison.change_statistics_status}</span><span>픽셀 팝업: {comparison.pixel_query_status}</span>
        {!comparison.change_statistics_allowed && <span>표시용 참조 타일 비교를 과학적 변화 통계로 계산하지 않습니다.</span>}
      </div>}
      <p className="help">CRS {left.crs || '미제공'} · 해상도 {left.resolution?.join(' × ') || '미제공'} · shape {left.shape?.join(' × ') || '미제공'} · NoData {left.nodata ?? 'null'} · schema {left.class_schema_version || '미제공'}</p>
      <div className="temporal-legend" aria-label="분류 범례">{palette.length ? palette.map(entry => <span key={entry.value}><i style={{background: entry.color}}/>{entry.value} · {entry.label || series.class_names?.[entry.value] || `클래스 ${entry.value}`}</span>) : <p className="help">서버가 색상 범례를 제공하지 않았습니다.</p>}</div>
    </>}
    </>}{data?.limitations?.map((value, i) => <p className="help" key={i}>{value}</p>)}
  </section>;
}
