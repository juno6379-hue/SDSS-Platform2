import { ApiError } from './api';

export type ReviewDecision = 'CHANGES_REQUESTED' | 'ACCEPTED';
export type ReviewStatus = 'PENDING' | ReviewDecision;
type EvidencePin = { path: string; sha256: string; bytes: number };
type ReviewEvent = { decision: ReviewDecision; reviewer: string; note: string; revision: number; created_at: string };
export type ResultRecord = {
  id: string; domain: string; source_key: string; title: string;
  evidence_status: string; summary: string | Record<string, unknown>;
  evidence: EvidencePin[]; blockers: string[]; review_status: ReviewStatus;
  revision: number; reviews: ReviewEvent[]; created_at: string;
};
export type ResultSource = { source: string; title: string; domain: string; evidence_status: string };

async function request<T>(path: string, options: { signal?: AbortSignal; body?: unknown } = {}): Promise<T> {
  const response = await fetch('/api/common-results' + path, {
    method: options.body === undefined ? 'GET' : 'POST',
    headers: options.body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });
  if (!response.headers.get('content-type')?.includes('application/json')) {
    throw new Error('공통 결과 API에 연결할 수 없습니다. 로컬 프록시 설정과 서버 상태를 확인하세요.');
  }
  const data = await response.json();
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}

export function resultError(error: unknown) {
  if (error instanceof ApiError && error.data && typeof error.data === 'object' && 'blockers' in error.data) {
    const blockers = error.data.blockers;
    if (Array.isArray(blockers) && blockers.every(item => typeof item === 'string')) return blockers.join(' · ');
  }
  return error instanceof Error ? error.message : String(error);
}

export async function listResults(domain: string, review: string, signal: AbortSignal) {
  const query = new URLSearchParams({ limit: '100' });
  if (domain) query.set('domain', domain);
  if (review) query.set('review_status', review);
  return (await request<{ results: ResultRecord[] }>('?' + query, { signal })).results;
}

export async function listResultSources(signal: AbortSignal) {
  return (await request<{ sources: ResultSource[] }>('/sources', { signal })).sources;
}

export async function readResult(id: string, signal?: AbortSignal) {
  return (await request<{ result: ResultRecord }>('/' + encodeURIComponent(id), { signal })).result;
}

export async function registerResult(source: string) {
  return (await request<{ result: ResultRecord }>('', { body: { source } })).result;
}

export async function saveResultReview(result: ResultRecord, decision: ReviewDecision, reviewer: string, note: string) {
  return (await request<{ result: ResultRecord }>('/' + encodeURIComponent(result.id) + '/reviews', {
    body: { decision, reviewer, note, expected_revision: result.revision },
  })).result;
}

export type ResultCatalog = {
  result_id: string; status: 'CATALOG_READY' | 'CATALOG_PENDING'; package_sha256: string | null;
  package: null | {
    institution: string;
    period_reason?: string | null;
    spatial: { crs: string; bbox: number[] } | null;
    period: { start: string; end: string; kind: string } | null;
    metrics: { id: string; label: string; value: unknown; unit: string }[];
    layers: { id: string; title: string; format: string; crs: string; nodata: unknown; href: string }[];
    sources: { id: string; title: string; uri: string; version: string; license: string; sha256: string }[];
    reports: { id: string; title: string; format: string; href: string }[];
    uncertainty: { status: 'NOT_REPORTED' | 'QUANTIFIED'; reason: string; method?: string; lower?: number; upper?: number; unit?: string };
    quality: { checks: unknown[] };
  };
  governance: {
    scientific: { status: string; history: unknown[] };
    publication: { status: string; history: unknown[] };
    release_eligible: boolean;
  };
};

// 앱 프록시로 이동할 수 있는 것은 동일 결과의 서버 제공 asset뿐이다.
export function catalogAssetHref(resultId: string, href: string): string | undefined {
  const prefix = '/api/results/' + encodeURIComponent(resultId) + '/catalog/assets/';
  if (!href.startsWith(prefix)) return undefined;
  const key = href.slice(prefix.length);
  if (!/^[A-Za-z0-9_-]+$/.test(key)) return undefined;
  return '/api/common-results/' + encodeURIComponent(resultId) + '/catalog/assets/' + key;
}

export async function readResultCatalog(id: string, signal: AbortSignal): Promise<ResultCatalog> {
  const data = await request<ResultCatalog>('/' + encodeURIComponent(id) + '/catalog', { signal });
  const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
  const strings = (value: unknown, keys: string[]) => object(value) && keys.every(key => typeof value[key] === 'string');
  if (!object(data) || data.result_id !== id || !['CATALOG_READY', 'CATALOG_PENDING'].includes(data.status)
    || !(data.package_sha256 === null || /^[a-fA-F0-9]{64}$/.test(data.package_sha256))
    || !object(data.governance) || typeof data.governance.release_eligible !== 'boolean'
    || !['scientific', 'publication'].every(axis => {
      const value = (data.governance as unknown as Record<string, unknown>)[axis];
      return strings(value, ['status']) && Array.isArray((value as Record<string, unknown>).history);
    })) throw new Error('CATALOG_RESPONSE_INVALID');
  const pkg = data.package;
  if (pkg !== null && (!object(pkg) || typeof pkg.institution !== 'string'
    || !(pkg.spatial === null || (strings(pkg.spatial, ['crs']) && Array.isArray(pkg.spatial.bbox) && pkg.spatial.bbox.length === 4 && pkg.spatial.bbox.every(Number.isFinite)))
    || !(pkg.period === null || strings(pkg.period, ['start', 'end', 'kind']))
    || !Array.isArray(pkg.metrics) || !pkg.metrics.every(row => strings(row, ['id', 'label', 'unit']))
    || !Array.isArray(pkg.layers) || !pkg.layers.every(row => strings(row, ['id', 'title', 'format', 'crs', 'href']))
    || !Array.isArray(pkg.sources) || !pkg.sources.every(row => strings(row, ['id', 'title', 'uri', 'version', 'license', 'sha256']))
    || !Array.isArray(pkg.reports) || !pkg.reports.every(row => strings(row, ['id', 'title', 'format', 'href']))
    || !object(pkg.uncertainty) || !['NOT_REPORTED', 'QUANTIFIED'].includes(pkg.uncertainty.status)
    || typeof pkg.uncertainty.reason !== 'string' || !object(pkg.quality) || !Array.isArray(pkg.quality.checks))) throw new Error('CATALOG_PACKAGE_INVALID');
  if (data.status === 'CATALOG_READY' && (pkg === null || data.package_sha256 === null)) throw new Error('CATALOG_READY_WITHOUT_PACKAGE');
  return data;
}
