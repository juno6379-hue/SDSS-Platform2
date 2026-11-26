import { useCallback, useEffect, useState } from 'react';
import type { FeatureCollection, Point, Polygon } from 'geojson';
import { ha, SENTINEL_API as API } from './lclucExplorerData';
import type { MapBounds } from './lclucExplorerData';

export const spectralLayers = {
  natural: '자연색 영상 (B04/B03/B02)',
  infrared: '컬러 적외선 (B08/B04/B03)',
  ndvi: 'NDVI 식생지수',
  ndwi: 'NDWI 수체지수',
  nbr: 'NBR 산불피해지수',
} as const;
export type SpectralLayer = keyof typeof spectralLayers;
type Coordinate = [number, number];
type Catalog = { spectral_years: number[]; cover_years: number[]; change_pairs: [number, number][] };
type Change = { from_year: number; to_year: number; common_valid_ha: number; changed_ha: number; change_pct: number | null };
type Annual = { year: number; valid_ha: number; classes: { code: number; name: string; area_ha: number; share_pct: number | null }[] };
export type SentinelStats = Change & { aoi_area_ha: number; annual: Annual[]; annual_changes: Change[]; transition_matrix_ha: number[][] };
type Sample = { years: { year: number; values: Record<string, number | null>; cover_code: number | null; qa: number | null }[] };
type Reading<T> = { key: string; data?: T; error?: string };
const qualityLabels = ['유효 합성', '잔여 구름', '잔여 그림자', '기타·관측 공백'];

async function get<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error((await response.json()).detail || `HTTP ${response.status}`);
  return response.json();
}

function read<T>(url: string, key: string, setter: (result: Reading<T>) => void) {
  const cancel = new AbortController();
  void get<T>(url, cancel.signal).then(data => {
    if (!cancel.signal.aborted) setter({ key, data });
  }).catch(error => {
    if (!cancel.signal.aborted) setter({ key, error: String(error.message) });
  });
  return () => cancel.abort();
}

export function sentinelYearAsset(year: number, layer: string) {
  return `${API}/years/${year}/layers/${layer}`;
}

export function useSentinelExplorer(active: boolean, start: number, end: number) {
  const [catalog, setCatalog] = useState<Catalog>();
  const [spectral, setSpectral] = useState<SpectralLayer>('natural');
  const [cover, setCover] = useState(false);
  const [change, setChange] = useState(false);
  const [transition, setTransition] = useState<{ query: string; from: number; to: number }>();
  const [quality, setQuality] = useState(false);
  const [tool, setTool] = useState<'point' | 'aoi'>();
  const [corner, setCorner] = useState<Coordinate>();
  const [bounds, setBounds] = useState<MapBounds>();
  const [position, setPosition] = useState<Coordinate>();
  const [queryText, setQueryText] = useState('');
  const [stats, setStats] = useState<Reading<SentinelStats>>();
  const [statsRevision, setStatsRevision] = useState(0);
  const [sample, setSample] = useState<Reading<Sample>>();
  const pair = new URLSearchParams({ from_year: String(start), to_year: String(end) }).toString();
  const statsQuery = pair + (bounds ? '&bbox=' + bounds.join(',') : '');
  const sampleQuery = position ? pair + `&lon=${position[0]}&lat=${position[1]}` : '';
  const bothSpectral = Boolean(catalog?.spectral_years.includes(start) && catalog.spectral_years.includes(end));
  const canClip = catalog?.cover_years.length === 6;
  const canChange = Boolean(catalog?.change_pairs.some(([a, b]) => a === start && b === end));

  useEffect(() => {
    if (!active) return;
    const cancel = new AbortController();
    function refresh() {
      void get<Catalog>(API, cancel.signal).then(data => {
        if (!cancel.signal.aborted) setCatalog(data);
      }).catch(() => {});
    }
    refresh();
    const timer = window.setInterval(refresh, 12000);
    return () => { window.clearInterval(timer); cancel.abort(); };
  }, [active]);
  useEffect(() => {
    if (active && (!bounds || canClip)) {
      return read<SentinelStats>(`${API}/statistics?${statsQuery}`, statsQuery, setStats);
    }
  }, [active, bounds, canClip, statsQuery, statsRevision]);
  useEffect(() => {
    if (active && sampleQuery && bothSpectral && canClip) return read<Sample>(`${API}/point?${sampleQuery}`, sampleQuery, setSample);
  }, [active, sampleQuery, bothSpectral, canClip]);

  const click = useCallback((coordinates: Coordinate) => {
    const p = coordinates.map(n => Number(n.toFixed(6))) as Coordinate;
    if (tool === 'point') {
      if (p[0] < 104 || p[0] > 108 || p[1] < -9 || p[1] > -4) setQueryText('반텐 분석 범위 안에서 클릭하세요.');
      else { setPosition(p); setQueryText(''); }
    }
    if (tool === 'aoi') {
      if (p[0] < 104 || p[0] > 108 || p[1] < -9 || p[1] > -4) {
        setQueryText('반텐 분석 범위 안에서 모서리를 지정하세요.');
        return;
      }
      if (!corner) {
        setCorner(p);
        setQueryText('AOI의 맞은편 모서리를 클릭하세요.');
        return;
      }
      if (corner[0] === p[0] || corner[1] === p[1]) {
        setQueryText('면적이 생기도록 다른 모서리를 지정하세요.');
        return;
      }
      setBounds([Math.min(corner[0], p[0]), Math.min(corner[1], p[1]), Math.max(corner[0], p[0]), Math.max(corner[1], p[1])]);
      setCorner(undefined); setTool(undefined); setQueryText('');
    }
  }, [tool, corner]);

  function cancelTool() {
    setCorner(undefined); setTool(undefined); setQueryText('');
  }
  function chooseTool(next: 'point' | 'aoi') {
    if (next === tool) {
      cancelTool();
      return;
    }
    setCorner(undefined);
    setTool(next);
    setQueryText(next === 'aoi' ? 'AOI의 첫 모서리를 클릭하세요.' : '지도에서 조회할 픽셀을 클릭하세요.');
  }
  function resetAoi() {
    setBounds(undefined); cancelTool();
  }

  return {
    active, catalog, spectral, setSpectral, cover, setCover, change, setChange, quality, setQuality,
    tool, chooseTool, cancelTool, resetAoi, click, position, corner, bounds, queryText,
    stats: stats?.key === statsQuery ? stats : undefined,
    refreshStatistics() { setStatsRevision(value => value + 1); },
    sample: sample?.key === sampleQuery ? sample : undefined,
    statsQuery, bothSpectral, canClip, canChange,
    transition: transition?.query === statsQuery ? transition : undefined,
    selectTransition(from: number, to: number) {
      setTransition({ query: statsQuery, from, to });
      setChange(true);
    },
    clearTransition() { setTransition(undefined); },
    changeUrl: `${API}/change/${start}/${end}`,
    transitionUrl: transition?.query === statsQuery
      ? `${API}/transition/${start}/${end}?from_class=${transition.from}&to_class=${transition.to}${bounds ? `&bbox=${bounds.join(',')}` : ''}`
      : undefined,
  };
}

export type SentinelExplorer = ReturnType<typeof useSentinelExplorer>;

export function sentinelMarkers(bounds?: MapBounds, corner?: Coordinate, position?: Coordinate): FeatureCollection<Polygon | Point> {
  const features: FeatureCollection<Polygon | Point>['features'] = [];
  if (bounds) {
    const [w, s, e, n] = bounds;
    features.push({ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] } });
  }
  for (const point of [corner, position]) {
    if (point) features.push({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: point } });
  }
  return { type: 'FeatureCollection', features };
}

export function SentinelLayerControls({ explorer, start, end, showBoundary, toggleBoundary, mapInteractive }: {
  explorer: SentinelExplorer; start: number; end: number; showBoundary: boolean; toggleBoundary: () => void;
  mapInteractive: boolean;
}) {
  const { spectral, setSpectral, catalog, bothSpectral, canChange } = explorer;
  const overlays = [
    { label: '토지피복 참조 · Esri 10m', key: 'cover', checked: explorer.cover, change: explorer.setCover, color: '#24844f', available: explorer.canClip },
    { label: `${start}→${end} 변화탐지`, key: 'change', checked: explorer.change, change: explorer.setChange, color: '#f22080', available: canChange },
    { label: '구름·그림자 마스크', key: 'quality', checked: explorer.quality, change: explorer.setQuality, color: '#9a79bb', available: bothSpectral },
    { label: '행정 경계', key: 'boundary', checked: showBoundary, change: toggleBoundary, color: '#4e7ea1', available: mapInteractive },
  ];
  return <div className="mw-sentinel-controls">
    <details className="mw-sentinel-layer-tree" open>
      <summary>Sentinel-2 레이어</summary>
      <fieldset><legend>영상 조합</legend>
        {Object.entries(spectralLayers).map(([id, name]) => <label key={id} className="mw-sentinel-layer-row" title={name}>
          <input type="radio" name="sentinel-spectral" value={id} checked={(bothSpectral ? spectral : 'natural') === id}
            disabled={id !== 'natural' && !bothSpectral} onChange={() => setSpectral(id as SpectralLayer)}/>
          {bothSpectral ? <img alt="" src={`${sentinelYearAsset(end, id)}?thumbnail=1`}/>
            : <i className="mw-sentinel-layer-chip"/>}<span>{name}</span>
        </label>)}
      </fieldset>
      <fieldset><legend>지도 중첩</legend>
        {overlays.map(row => <label key={row.key} className="mw-sentinel-layer-row">
          <i className="mw-sentinel-layer-chip" style={{ backgroundColor: row.color }}/><span>{row.label}</span>
          <input type="checkbox" role="switch" checked={row.checked && row.available} disabled={!row.available}
            onChange={event => row.change(event.target.checked)}/>
        </label>)}
      </fieldset>
    </details>
    {['ndvi', 'ndwi', 'nbr'].includes(spectral) && <div className="mw-sentinel-index-legend"><i/><span>−1</span><span>0</span><span>+1</span></div>}
    {!bothSpectral && <small role="status">파생 영상 {catalog?.spectral_years.length ?? 0}/6년 준비</small>}
  </div>;
}

function percent(value: number | null) {
  if (value == null) return '—';
  return value > 0 && value < 0.01 ? '<0.01%' : `${ha.format(value)}%`;
}

export function SentinelAnalysisPanel({ explorer, start, end, names, mapInteractive, downloadsId, onShowMap }: {
  explorer: SentinelExplorer; start: number; end: number; names: Record<number, string>;
  mapInteractive: boolean; downloadsId: string; onShowMap: () => void;
}) {
  const data = explorer.stats?.data;
  const canUseRaster = explorer.bothSpectral && explorer.canClip;
  return <section className="mw-sentinel-analysis" aria-label="Sentinel-2 AOI 분석">
    <div className="mw-sentinel-aoi-header"><strong>Sentinel-2 · AOI 분석</strong>
      <div>
        <button type="button" disabled={!canUseRaster || !mapInteractive} aria-pressed={explorer.tool === 'point'}
          className={explorer.tool === 'point' ? 'active' : ''}
          onClick={() => { if (explorer.tool !== 'point') onShowMap(); explorer.chooseTool('point'); }}>점 조회</button>
        <button type="button" disabled={!explorer.canClip || !mapInteractive} aria-pressed={explorer.tool === 'aoi'}
          className={explorer.tool === 'aoi' ? 'active' : ''}
          onClick={() => { if (explorer.tool !== 'aoi') onShowMap(); explorer.chooseTool('aoi'); }}>AOI 지정</button>
        <button type="button" onClick={explorer.resetAoi}>주 전체 AOI</button>
      </div>
    </div>
    <p className="mw-land-cover-source">영상·지수·품질은 Sentinel-2 L2A 자료를 사용합니다. 클래스 면적·비율과 전이행렬은 선택한 AOI의 Esri 연차 토지피복을 집계한 값입니다.</p>
    {explorer.queryText && <p role="status">{explorer.queryText}</p>}
    {explorer.position && <details open className="mw-sentinel-point">
      <summary>Explore · {explorer.position.join(', ')}</summary>
      {explorer.sample?.data ? <div className="mw-sentinel-pair">
        {explorer.sample.data.years.map(row => <div key={row.year}>
          <b>{row.year}년</b> · {row.cover_code ? names[row.cover_code] ?? `코드 ${row.cover_code}` : '토지피복 값 없음'}
          <p>{['NDVI', 'NDWI', 'NBR'].map(code => `${code} ${row.values[code] == null ? '—' : row.values[code]?.toFixed(3)}`).join(' · ')}</p>
          <small>{row.qa == null ? '관측 범위 밖' : qualityLabels[row.qa]}</small>
          <details><summary>밴드별 표면반사도</summary>
            <p>{['B02', 'B03', 'B04', 'B08', 'B11', 'B12'].map(code => `${code} ${row.values[code]?.toFixed(3) ?? '—'}`).join(' · ')}</p>
          </details>
        </div>)}
      </div> : <p role="status">{explorer.sample?.error ? '선택 위치의 픽셀을 조회할 수 없습니다.' : '픽셀 조회 중'}</p>}
    </details>}
    {data && <>
        <p><b>{explorer.bounds ? '선택 사각형 × 반텐 경계' : '반텐주 전체'}</b> {ha.format(data.aoi_area_ha)}ha · Esri / Impact Observatory v003 10m 참조 분류</p>
        <div className="mw-sentinel-pair">
          <span>{start}→{end} 변화 <b>{ha.format(data.changed_ha)}ha · {percent(data.change_pct)}</b></span>
          <span>공통 유효 면적 {ha.format(data.common_valid_ha)}ha · 독립 정확도 미측정</span>
        </div>
      </>}
    <details id={downloadsId} tabIndex={-1}><summary>결과 다운로드</summary>
        {data ? <>
          <div className="mw-sentinel-downloads">
            <a href={`${API}/statistics?${explorer.statsQuery}&format=csv`}>AOI 통계·전이 CSV</a>
            <a href={`${API}/statistics?${explorer.statsQuery}&download=1`}>AOI 결과 JSON</a>
          </div>
          <div className="mw-sentinel-downloads">
            {canUseRaster && [start, end].map(year => <div key={year}>
              <b>{year} 반텐 전역</b>
              <a href={sentinelYearAsset(year, explorer.spectral) + '?download=1'}>현재 영상 PNG</a>
              <a href={sentinelYearAsset(year, 'spectral')}>반사도·지수·QA GeoTIFF</a>
              <a href={sentinelYearAsset(year, 'land-cover')}>Esri 토지피복 GeoTIFF</a>
              <a href={`${API}/years/${year}/metadata`} target="_blank" rel="noreferrer">원본·품질 기록</a>
            </div>)}
            {explorer.canChange && <a href={explorer.changeUrl + '/raster'}>{start}→{end} 반텐 전역 변화 GeoTIFF</a>}
          </div>
        </> : <p role="status">{explorer.stats?.error ? 'AOI를 다시 지정하세요.' : 'AOI 결과 조회 중'}</p>}
    </details>
  </section>;
}
