import { useEffect, useRef, useState } from 'react';
import type { Geometry } from 'geojson';
import type { MapBounds } from './lclucExplorerData';

export type Hotspot = { rank: number; changed_area_ha: number; common_valid_area_ha: number; rate_pct: number; geometry: Geometry };
export type BantenComparison = {
  from_year: number;
  to_year: number;
  grid_resolution_m: number;
  boundary_area_ha: number;
  common_valid_area_ha: number;
  changed_area_ha: number;
  change_rate_pct: number | null;
  classes: { code: number; name: string }[];
  transition_matrix_ha: number[][];
  annual: { year: number; thematic_valid_pct: number }[];
  annual_area: { year: number; areas_ha: Record<number, number>; thematic_valid_pct: number }[];
  spatial: { preview: string; bounds: MapBounds; changed_grid_cells: number; visual_grid_m: number; hotspots: Hotspot[] } | null;
  recalculation?: { status: 'DIFFERS_FROM_PUBLISHED'; changed_area_ha: number };
};
type Report = { id: string; assets: Record<'html' | 'json' | 'csv', string> };
type OpticalAudit = {
  year: number; six_band_present_pct: number;
  sentinel_clear_pct?: number; landsat_clear_pct?: number;
};
type Collection = {
  esri_years: { year: number; thematic_valid_pct: number; uri: string; sha256: string }[];
  sentinel_assets: number; sentinel_scenes: number; sentinel_status: string;
  landsat_assets: number; landsat_scenes: number;
  optical_qa?: Partial<Record<'sentinel-2' | 'landsat', OpticalAudit[]>>;
};
type Operation = 'comparison' | 'analysis' | 'reports';

export function useBantenComparison(enabled: boolean, fromYear: number, toYear: number) {
  const key = enabled ? `${fromYear}/${toYear}` : '';
  const [command, setCommand] = useState<{ key: string; operation: Operation }>();
  const seen = useRef<typeof command>(undefined);
  const [collection, setCollection] = useState<Collection>();
  const [result, setResult] = useState<{ key: string; comparison?: BantenComparison; report?: Report; status: string }>();
  // Abort obsolete selections and retain an earlier audited result while generating its report.
  useEffect(() => {
    if (!key || fromYear >= toYear) return;
    const abort = new AbortController();
    const operation = command?.key === key && seen.current !== command ? command.operation : 'comparison';
    seen.current = command;
    const query = new URLSearchParams({ from_year: String(fromYear), to_year: String(toYear) });
    const post = operation !== 'comparison';
    const path = `/api/lcluc/banten-province-${operation}` + (post ? '' : `?${query}`);
    setResult(previous => ({ ...(previous?.key === key ? previous : undefined), key,
      status: operation === 'analysis' ? '반텐주 전체 10m 원본을 재계산 중입니다.'
        : operation === 'reports' ? '반텐주 전역 리포트를 생성 중입니다.' : '반텐주 전역 비교 자료 조회 중입니다.' }));
    void fetch(path, {
      signal: abort.signal,
      ...(post ? { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from_year: fromYear, to_year: toYear }) } : {}),
    }).then(async response => {
      if (!response.ok) {
        const detail = await response.json();
        throw new Error(detail.detail === 'BANTEN_PROVINCE_YEARS_NOT_READY'
          ? '선택한 두 연도의 반텐 전역 자료를 기다리고 있습니다.'
          : detail.detail === 'BANTEN_ANALYSIS_ALREADY_RUNNING' ? '반텐 전역 분석이 이미 실행 중입니다.' : '반텐주 전역 자료 검증에 실패했습니다.');
      }
      const data = await response.json();
      if (abort.signal.aborted) return;
      const analysis = data as BantenComparison;
      const changed = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 });
      setResult(previous => operation === 'reports'
        ? { key, comparison: previous?.key === key ? previous.comparison : undefined, report: data as Report,
          status: '반텐주 전역 리포트를 생성했습니다.' }
        : { key, comparison: analysis, status: analysis.recalculation
          ? `기존 검산 결과는 ${changed.format(analysis.changed_area_ha)}ha, 현재 환경의 재계산 값은 ${changed.format(analysis.recalculation.changed_area_ha)}ha입니다.`
          : '반텐주 전역 분석 결과를 확인했습니다.' });
    }).catch(error => {
      if (!abort.signal.aborted) setResult(previous => ({
        ...(previous?.key === key ? previous : undefined), key, status: error.message,
      }));
    });
    return () => abort.abort();
  }, [key, fromYear, toYear, command]);
  useEffect(() => {
    if (!enabled) return;
    const abort = new AbortController();
    function load() {
      void fetch('/api/lcluc/banten-province-collection', { signal: abort.signal })
        .then(async response => {
          if (response.ok && !abort.signal.aborted) setCollection(await response.json() as Collection);
        }).catch(() => {});
    }
    load();
    const poll = window.setInterval(load, 60000);
    return () => { window.clearInterval(poll); abort.abort(); };
  }, [enabled]);
  const current = result?.key === key ? result : undefined;
  return { ...current, collection: enabled ? collection : undefined, perform: (operation: Operation) => setCommand({ key, operation }) };
}
