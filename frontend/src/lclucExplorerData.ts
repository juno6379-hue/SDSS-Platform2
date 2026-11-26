import { useEffect, useState } from 'react';
import type { FeatureCollection, MultiPolygon, Point, Polygon } from 'geojson';

export const SENTINEL_API = '/api/lcluc/banten-sentinel-explorer';
export type MapBounds = [number, number, number, number];
export type ProvinceLandCover = {
  bounds?: MapBounds;
  colors?: Record<number, string>;
  years: Record<number, string>;
  optical?: Partial<Record<'sentinel-2' | 'landsat', Record<number, { preview: string; display_clear_pct: number; scene_count: number }>>>;
};
export function readBantenLandCover(signal: AbortSignal) {
  return read<ProvinceLandCover>('/api/lcluc/banten-province-display', signal);
}
export type LandCoverClass = { code: number; name: string; color: string };
export type ExplorerCase = {
  id: string;
  taxonomy_id: string;
  esri_display?: { colors: Record<number, string>; earlier: string; later: string } | null;
  source_kind: string;
  from_year: number;
  to_year: number;
  previews: Record<'earlier-preview' | 'later-preview' | 'change-preview', string>;
  assets: { id: string; href: string }[];
  report: {
    classes: LandCoverClass[];
    grid: { bounds_crs84: MapBounds };
    coverage: { common_valid_area_ha: number; common_valid_fraction: number };
    major_changes: { changed_area_ha: number; change_rate_pct: number };
    annual_stats: { code: number; from_area_ha: number; to_area_ha: number; net_ha: number }[];
    transition_matrix_ha: number[][];
    hotspot_count: number;
    zones: { id: string; name: string; major_changes: { changed_area_ha: number } }[];
  };
};
type Observation = { observed_on: string; scene: string; preview: string; bundle: string };
export type ExplorerImagery = {
  id: 'sentinel-2' | 'landsat' | 'disaster';
  region: string;
  title: string;
  attribution: string;
  scope: string;
  earlier: Observation;
  later: Observation;
};
export type AdminBoundary = {
  region: string;
  province_count: number;
  district_count: number;
  source: { label: string; uri: string; acquired_at: string; approved_for_project_statistics: boolean };
  geojson: FeatureCollection<Polygon | MultiPolygon, { level: 'province' | 'district'; name: string; province_id: string }>;
  province_labels: FeatureCollection<Point, { name: string; province_id: string }>;
};

async function read<T>(path: string, signal?: AbortSignal) {
  const res = await fetch(path, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export function readAdminBoundary() {
  return read<AdminBoundary>('/api/lcluc/boundaries');
}

export function useLclucExplorer(enabled: boolean, region: string, from: number, to: number, refresh: number) {
  const key = `${region}/${from}/${to}/${refresh}`;
  const [result, setResult] = useState<{ key: string; detail?: ExplorerCase; status: string }>();
  const [imagery, setImagery] = useState<ExplorerImagery[]>([]);

  useEffect(() => {
    if (!enabled) return;
    const abort = new AbortController();
    read<{ series: ExplorerImagery[] }>('/api/lcluc/imagery', abort.signal)
      .then(data => { if (!abort.signal.aborted) setImagery(data.series); })
      .catch(() => { if (!abort.signal.aborted) setImagery([]); });
    return () => abort.abort();
  }, [enabled]);

  useEffect(() => {
    if (!enabled || from >= to) return;
    const abort = new AbortController();
    const query = new URLSearchParams({ region, from_year: String(from), to_year: String(to) });
    async function loadPair() {
      const data = await read<{ cases: { id: string; source_kind: string }[] }>(`/api/lcluc/selection?${query}`, abort.signal);
      const selected = data.cases.find(item => item.source_kind !== 'synthetic_fixture');
      const detail = selected && /^[0-9a-f]{64}$/.test(selected.id)
        ? await read<ExplorerCase>('/api/lcluc/cases/' + selected.id, abort.signal)
        : undefined;
      if (!abort.signal.aborted) {
        setResult({ key, detail, status: detail ? '연차 비교 결과 조회 완료' : '선택한 지역·연도의 토지피복 비교 자료 미등록' });
      }
    }
    loadPair().catch(error => {
      if (!abort.signal.aborted) setResult({ key, status: `비교 자료 조회 실패 (${error.message})` });
    });
    return () => abort.abort();
  }, [enabled, region, from, to, key]);

  const current = enabled && result?.key === key ? result : undefined;
  return {
    detail: current?.detail,
    status: from >= to ? '종료 연도를 시작 연도보다 늦게 선택하세요.' : current?.status ?? '연차 자료 조회 중',
    imagery,
  };
}

export const ha = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 });
