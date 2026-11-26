import { useEffect, useState } from 'react';
import { ha, SENTINEL_API } from './lclucExplorerData';
import type { MapBounds } from './lclucExplorerData';

const API = '/api/lcluc/banten-landsat';
export const landsatLayers = {
  natural: 'Natural Color', agriculture: 'Agriculture', urban: 'Urban', swir: 'SWIR',
  ndvi: 'NDVI', ndmi: 'NDMI', mndwi: 'MNDWI',
} as const;
export type LandsatLayer = keyof typeof landsatLayers;

type Epoch = { key: string; period: [number, number]; clear_pct: number; two_observations_pct: number;
  median_observations: number; grid_spacing_m: [number, number]; scenes: string[]; bounds: MapBounds };
type Catalog = { annual: Epoch[]; periods: Epoch[];
  archive_checks: { year: number; state: string; items_on_first_page: number }[];
  band_profiles: Record<string, number[]> };
type Trend = { source_url: string; years: number[]; classes: { code: number; name: string; areas_ha: number[] }[] };

export function landsatAsset(year: string | number, layer: LandsatLayer | 'reflectance') {
  return API + '/products/' + year + '/' + layer;
}

function useReading<T>(url: string, enabled = true, refresh?: number) {
  const [reading, setReading] = useState<{ data?: T; error?: number }>();
  useEffect(() => {
    if (!enabled) return;
    const cancel = new AbortController();
    async function load() {
      try {
        const response = await fetch(url, { signal: cancel.signal });
        const reading = response.ok ? { data: await response.json() as T } : { error: response.status };
        if (!cancel.signal.aborted) setReading(reading);
      } catch {
        if (!cancel.signal.aborted) setReading({ error: 503 });
      }
    }
    void load();
    const timer = refresh ? window.setInterval(load, refresh) : undefined;
    return () => { cancel.abort(); window.clearInterval(timer); };
  }, [url, enabled, refresh]);
  return reading;
}

export function useLandsatExplorer(active: boolean) {
  const source = useReading<Catalog>(API, active, 20000);
  const [layer, setLayer] = useState<LandsatLayer>('natural');
  const [change, setChange] = useState(false);
  return { active, catalog: source?.data, error: source?.error, layer, setLayer, change, setChange,
    changeUrl: (start: number, end: number) => API + '/change/' + start + '/' + end };
}

export type LandsatExplorer = ReturnType<typeof useLandsatExplorer>;
const mappings: Record<LandsatLayer, string> = {
  natural: 'Red / Green / Blue', agriculture: 'SWIR1 / NIR / Blue',
  urban: 'SWIR2 / SWIR1 / Red', swir: 'SWIR2 / NIR / Red',
  ndvi: '(NIR − Red) / (NIR + Red)', ndmi: '(NIR − SWIR1) / (NIR + SWIR1)',
  mndwi: '(Green − SWIR1) / (Green + SWIR1)',
};
const ratio = (value: number) => ha.format(value) + '%';

export function LandsatLayerControls({ explorer, end, pairReady }: { explorer: LandsatExplorer; end: number; pairReady: boolean }) {
  return <div className="mw-sentinel-controls">
    <details className="mw-sentinel-layer-tree" open>
      <summary>Landsat 레이어</summary>
      <fieldset><legend>영상 조합</legend>
        {Object.entries(landsatLayers).map(([id, name]) => <label className="mw-sentinel-layer-row" key={id} title={mappings[id as LandsatLayer]}>
          <input type="radio" name="landsat-spectral" value={id} checked={explorer.layer === id}
            disabled={!pairReady} onChange={() => explorer.setLayer(id as LandsatLayer)}/>
          {pairReady ? <img alt="" src={landsatAsset(end, id as LandsatLayer) + '?thumbnail=1'}/>
            : <i className="mw-sentinel-layer-chip"/>}<span>{name}</span>
        </label>)}
      </fieldset>
      <fieldset><legend>지도 중첩</legend>
        <label className="mw-sentinel-layer-row" title="공통 유효 픽셀에서 NDVI 변화량 ±0.20">
          <i className="mw-sentinel-layer-chip" style={{ backgroundColor: '#db5d37' }}/><span>NDVI 변화</span>
          <input type="checkbox" role="switch" checked={explorer.change && pairReady} disabled={!pairReady}
            onChange={event => explorer.setChange(event.target.checked)}/>
        </label>
      </fieldset>
    </details>
    <small>{mappings[explorer.layer]}</small>
    {explorer.change && pairReady && <small>증가 녹색 · 감소 주황 · ΔNDVI ±0.20</small>}
    {!pairReady && <small role="status">{explorer.error ? 'Landsat 발행 목록 조회 실패' : '해당 연도의 분광 영상 준비 중'}</small>}
  </div>;
}

export function LandsatInventory({ explorer, start, end }: { explorer: LandsatExplorer; start: number; end: number }) {
  const catalog = explorer.catalog;
  if (!catalog) return <p role="status">{explorer.error ? 'Landsat 발행 목록 조회 실패' : '발행 목록 조회 중'}</p>;
  return <div className="mw-landsat-content">
    <p>반텐주 · USGS Landsat Collection 2 Level-2 · 비교 {start}→{end}</p>
    <div className="mw-table-scroll"><table className="mw-table">
      <thead><tr><th>기간</th><th>맑은 관측 1회 이상</th><th>2회 이상</th><th>영상·기록</th></tr></thead>
      <tbody>{[...catalog.annual, ...catalog.periods].map(row => <tr key={row.key}><th>{row.key}
        {row.scenes.length > 0 && <small className="mw-landsat-observation-count"> · {row.scenes.length}장면</small>}</th>
        <td>{ratio(row.clear_pct)}</td><td>{ratio(row.two_observations_pct)}</td>
        <td><a href={landsatAsset(row.key, 'natural')} target="_blank" rel="noreferrer">PNG</a>{' · '}
          <a href={landsatAsset(row.key, 'reflectance')}>GeoTIFF</a>{' · '}
          <a href={API + '/products/' + row.key} target="_blank" rel="noreferrer">기록</a></td>
      </tr>)}</tbody>
    </table></div>
    <details><summary>센서별 밴드·과거 카탈로그</summary>
      <p>TM·ETM+는 B1·2·3·4·5·7, OLI는 B2·3·4·5·6·7을 Blue·Green·Red·NIR·SWIR1·SWIR2에 맞춥니다. C2 L2 표면반사도와 QA를 사용합니다.</p>
      <p>발행 격자 {catalog.annual[0]?.grid_spacing_m.map(n => ha.format(n)).join(' × ')}m(EPSG:3857) · 원본 분광 밴드 30m</p>
      <p>과거 단일 장면은 표시용 시험 영상입니다. 맑은 관측 비율은 반텐주 격자 기준입니다.</p>
      {catalog.archive_checks.map(row => <p key={row.year}>{row.year}년 조회 후보 {row.items_on_first_page}개 · {
        row.state === 'PUBLISHED' ? '영상 발행' : row.state === 'NO_SELECTED_SCENE' ? '조회 조건을 충족한 장면 없음' : '발행할 장면 대기'
      }</p>)}
    </details>
  </div>;
}

export function LandsatLongTrend() {
  const reading = useReading<Trend>(SENTINEL_API + '/historical-trend');
  const [start, setStart] = useState(1990);
  const [end, setEnd] = useState(2024);
  const trend = reading?.data;
  if (!trend) return <p role="status">{reading?.error ? '발행 통계 조회 실패' : '장기 통계 조회 중'}</p>;
  const first = trend.years.indexOf(start);
  const last = trend.years.indexOf(end);
  return <div className="mw-landsat-content">
    <p>MapBiomas Indonesia Collection 4.1 · 반텐주 발행 통계 · 1990~2024년</p>
    <div className="mw-sentinel-filters">
      <label>통계 시작 <select value={start} onChange={e => setStart(Number(e.target.value))}>
        {trend.years.filter(year => year < end).map(year => <option key={year}>{year}</option>)}</select></label>
      <label>통계 종료 <select value={end} onChange={e => setEnd(Number(e.target.value))}>
        {trend.years.filter(year => year > start).map(year => <option key={year}>{year}</option>)}</select></label>
    </div>
    <div className="mw-table-scroll"><table className="mw-table">
      <thead><tr><th>클래스</th><th>{start} 면적</th><th>{end} 면적</th><th>누적 순변화</th><th>연평균 순변화</th><th>변화율</th></tr></thead>
      <tbody>{trend.classes.map(row => {
        const a = row.areas_ha[first], b = row.areas_ha[last], diff = b - a;
        return <tr key={row.code}><th>{row.name}</th><td>{ha.format(a)}ha</td><td>{ha.format(b)}ha</td>
          <td>{ha.format(diff)}ha</td><td>{ha.format(diff / (end - start))}ha/년</td>
          <td>{a > 0 ? ratio(100 * diff / a) : '—'}</td></tr>;
      })}</tbody>
    </table></div>
    <p><a href={trend.source_url} target="_blank" rel="noreferrer">발행 출처</a>{' · '}
      <a href={SENTINEL_API + '/historical-trend?download=1'}>35개년 자료 다운로드</a></p>
  </div>;
}

export function LandsatLongChange() {
  const reading = useReading<Trend>(SENTINEL_API + '/historical-trend');
  if (!reading?.data) return <p role="status">{reading?.error ? '장기 변화 자료 조회 실패' : '장기 변화 조회 중'}</p>;
  const { years, classes } = reading.data;
  const groups: [string, number[]][] = [
    ['산림·맹그로브', [3, 5]], ['농경지', [21, 35, 40]], ['시가화', [24]],
  ];
  return <div className="mw-landsat-content">
    <p>MapBiomas 발행 반텐주 전체 · 연간 순변화가 가장 컸던 시기</p>
    <div className="mw-table-scroll"><table className="mw-table">
      <thead><tr><th>항목</th><th>1990~2024 순변화</th><th>최대 감소 연도구간</th><th>최대 증가 연도구간</th></tr></thead>
      <tbody>{groups.map(([label, codes]) => {
        const rows = classes.filter(row => codes.includes(row.code));
        const areas = years.map((_, i) => rows.reduce((sum, row) => sum + row.areas_ha[i], 0));
        const changes = areas.slice(1).map((area, i) => ({ year: years[i + 1], amount: area - areas[i] }));
        const low = changes.reduce((a, b) => a.amount < b.amount ? a : b);
        const high = changes.reduce((a, b) => a.amount > b.amount ? a : b);
        const interval = ({ year, amount }: typeof low) => (year - 1) + '→' + year + ' · ' + ha.format(amount) + 'ha';
        return <tr key={label}><th>{label}</th><td>{ha.format(areas.at(-1)! - areas[0])}ha</td>
          <td>{low.amount < 0 ? interval(low) : '—'}</td><td>{high.amount > 0 ? interval(high) : '—'}</td></tr>;
      })}</tbody>
    </table></div>
    <p>위 표는 주 단위 분류 면적의 연속 연도 차이입니다. 지도 NDVI 변화는 공통 유효 픽셀의 식생 신호 변화량입니다.</p>
  </div>;
}
