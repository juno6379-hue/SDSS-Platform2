import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';

type Citation = {id: string; title: string; version: string; language: string; page: number | null;
  text_offset: number; excerpt: string; url: string; source_sha256: string};
type Metric = {key: string; value: number; unit: string; name: string | null; from_codes: number[]; to_codes: number[]};
type Source = {name: string; version: string; url: string; sha256: string; sheet?: string; year?: number; download_url?: string};
type MapEvidence = {boundary_url: string; boundary_sha256: string; boundary_source: string; image_url: string | null;
  background_url?: string | null; kind: 'boundary' | 'cover' | 'transition'};
type Answer = {route: 'rag' | 'gis'; status: string; reason?: string; citations: Citation[];
  query?: {intent: string; region: string; product: string; years: number[]};
  metrics?: Metric[]; class_names?: Record<number, string>; sources?: Source[]; limitations?: string[]; map?: MapEvidence};
type Lang = 'ko' | 'id' | 'en';
type Position = [number, number];
type Rings = Position[][];
type Geometry = {type: 'Polygon'; coordinates: Rings} | {type: 'MultiPolygon'; coordinates: Rings[]};

const METRIC: Record<string, [string, string, string]> = {
  area: ['면적', 'Luas', 'Area'],
  forest_loss: ['산림→비산림 총전환', 'Kehilangan hutan bruto', 'Gross forest loss'],
  forest_net_change: ['산림 면적 순변화', 'Perubahan bersih luas hutan', 'Net forest area change'],
  start_forest_area: ['시작 연도 산림 면적', 'Luas hutan awal', 'Initial forest area'],
  end_forest_area: ['종료 연도 산림 면적', 'Luas hutan akhir', 'Final forest area'],
  transition: ['토지피복 전이 면적', 'Luas transisi tutupan lahan', 'Land-cover transition area'],
};
const LIMITS: Record<string, string> = {
  PUBLISHER_PROVINCE_BOUNDARY: 'MapBiomas 발행 반텐주 집계',
  MAPBIOMAS_BOUNDARY_CONTEXT_ONLY: '지도에는 One Map/BIG 반텐 경계만 표시합니다. MapBiomas의 실제 분류·전이 위치는 원본 래스터 확보 후 표시할 수 있습니다.',
  FOREST_START_MARGIN_CHECKED: '산림 출발 클래스의 전이 합계를 시작 연도 면적과 대조했습니다.',
  GROSS_LOSS_PUBLISHED_PAIRS_ONLY: '발행된 산림→비산림 조합의 면적을 합산했습니다.',
  DIRECT_PERIOD_NO_ANNUAL_SUM: '발행된 해당 기간의 직접 전이 값을 사용했습니다.',
  ESRI_TEN_METRE_GRID: 'Esri 10m 등적 격자 집계. 두 해의 전이는 공통 유효 픽셀을 사용합니다.',
  ESRI_TRANSITION_DISPLAY_GRID: '전이 위치 미리보기는 표시 격자이며 수치는 10m 집계에서 가져옵니다.',
  BOUNDARY_REVIEW_PENDING: 'One Map/BIG 경계의 사업 통계 사용 승인 대기',
  INDEPENDENT_ACCURACY_UNMEASURED: '제품의 분류 결과이며 독립 표본 정확도는 미측정',
};
const REASONS: Record<string, string> = {
  INTENT_REQUIRED: '문서의 방법·정의를 묻거나, 반텐의 면적·산림감소·전이 중 필요한 값을 지정하세요.',
  REGION_REQUIRED: '조회할 지역을 지정하세요. 현재 정량 자료는 반텐주를 지원합니다.',
  BANTEN_PROVINCE_ONLY: '현재 조회 범위는 반텐주 전체입니다. 다른 지역과 세부 경계는 별도 자료가 필요합니다.',
  PRODUCT_REQUIRED: 'MapBiomas, Esri 또는 산림부 중 조회할 자료를 지정하세요.',
  PRODUCT_AMBIGUOUS: '제품 하나를 지정하세요. 제품별 클래스 정의와 집계 범위가 다릅니다.',
  PRODUCT_NOT_READY: '요청한 제품의 검증된 반텐 통계가 준비되지 않았습니다.',
  PRODUCT_VERSION_NOT_READY: '요청한 버전의 검증 자료를 확인할 수 없습니다. MapBiomas Collection 4.1 또는 Esri v003을 조회할 수 있습니다.',
  KEMENHUT_ASSET_NOT_READY: '인도네시아 산림부의 동년 공식 원본과 사용 조건 검증을 기다리고 있습니다.',
  OVERLAY_ASSET_NOT_READY: '공간 중첩에는 같은 범위의 검증된 레이어가 필요합니다. 해당 레이어를 현재 조회할 수 없습니다.',
  AREA_YEAR_REQUIRED: '면적 집계 연도를 하나 지정하세요.',
  ORDERED_YEAR_PAIR_REQUIRED: '시작 및 종료 연도를 순서대로 지정하세요.',
  AREA_CLASS_REQUIRED: '면적을 조회할 클래스 하나 또는 전체 클래스 목록을 지정하세요.',
  AREA_UNIT_REQUIRED: '현재 정량 질의는 면적(ha)을 지원합니다.',
  TRANSITION_DIRECTION_REQUIRED: '산림→시가지처럼 출발·도착 클래스를 지정하세요.',
  CLASS_NOT_DEFINED_IN_PRODUCT: '요청한 클래스의 분류 정의를 이 제품에서 확인할 수 없습니다.',
  CLASS_NOT_PUBLISHED: '요청한 클래스가 반텐 발행 표에 없습니다.',
  PERIOD_NOT_PUBLISHED: '요청한 제품의 해당 기간 직접 집계를 확인할 수 없습니다.',
  TRANSITION_NOT_PUBLISHED: '요청한 출발·도착 조합의 면적이 해당 기간 발행 표에 없습니다.',
  TRANSITION_CLASSES_OVERLAP: '서로 겹치지 않는 출발·도착 클래스를 지정하세요.',
  ESRI_TREES_NOT_FOREST_DEFINITION: 'Esri는 수목 클래스이며 산림 감소 질의에는 별도의 산림 정의가 필요합니다.',
  EVIDENCE_NOT_READY: '고정한 원본 또는 통계 파일을 찾을 수 없습니다.',
  SOURCE_INTEGRITY_FAILURE: '원본 또는 파생 자료의 무결성 검증에 실패했습니다.',
  FOREST_TRANSITION_COVERAGE_MISMATCH: '산림 전이 합계가 출발 연도의 발행 면적과 맞지 않습니다.',
};

function language(text: string): Lang {
  if (/[가-힣]/.test(text)) return 'ko';
  if (/\b(berapa|luas|sawah|menurut|hutan|di|pada|apa|dari|transisi)\b/i.test(text)) return 'id';
  return 'en';
}

function boundaryPath(geometry: Geometry) {
  const rings = (geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates).flat();
  let west = Infinity, east = -Infinity, south = Infinity, north = -Infinity;
  for (const ring of rings) for (const [x, y] of ring) {
    west = Math.min(west, x); east = Math.max(east, x); south = Math.min(south, y); north = Math.max(north, y);
  }
  const scale = Math.min(320 / (east - west), 204 / (north - south));
  const offsetX = (360 - scale * (east - west)) / 2, offsetY = (244 - scale * (north - south)) / 2;
  return rings.map(ring => 'M' + ring.map(([x, y]) =>
    `${(offsetX + (x - west) * scale).toFixed(2)},${(offsetY + (north - y) * scale).toFixed(2)}`).join('L') + 'Z').join('');
}

function AnswerMap({layer}: {layer: MapEvidence}) {
  const [path, setPath] = useState('');
  const [failed, setFailed] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void fetch(layer.boundary_url, {signal: controller.signal}).then(async response => {
      if (!response.ok) throw new Error('boundary');
      const data = await response.json() as {source: {snapshot_sha256: string};
        geojson: {features: {properties: {level: string}; geometry: Geometry}[]}};
      const province = data.geojson.features.find(item => item.properties.level === 'province');
      if (data.source.snapshot_sha256 !== layer.boundary_sha256 || !province) throw new Error('boundary pin');
      if (!controller.signal.aborted) setPath(boundaryPath(province.geometry));
    }).catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, [layer.boundary_url, layer.boundary_sha256]);

  return <section aria-label="GeoLLM 결과 지도">
    <h3>지도</h3>
    <div style={{display: 'flex', flexWrap: 'wrap', alignItems: 'start', gap: 16}}>
    <figure style={{margin: 0, maxWidth: '100%'}}>
      {path && <svg viewBox="0 0 360 244" width="360" style={{maxWidth: '100%'}} role="img" aria-label="One Map BIG 반텐주 경계">
        <rect width="360" height="244" rx="8" fill="#f0f7fc"/>
        <path d={path} fill="#d5eadf" stroke="#23765e" strokeWidth="1.4" fillRule="evenodd"/>
      </svg>}
      {!path && <p role="status">{failed ? '고정 경계를 불러오지 못했습니다.' : '반텐 경계 조회 중'}</p>}
      <figcaption>{layer.boundary_source} · 반텐주 경계{layer.kind === 'boundary' ? ' (위치 참고용)' : ''}</figcaption>
    </figure>
    {layer.image_url && <figure style={{margin: 0, width: 520, maxWidth: '100%'}}>
      {imageFailed ? <p role="status">Esri 지도 파일을 불러오지 못했습니다.</p> :
        <div style={{position: 'relative', background: '#f0f7fc', borderRadius: 8, overflow: 'hidden'}}>
          {layer.background_url && <img src={layer.background_url} alt="" style={{position: 'absolute', inset: 0,
            width: '100%', height: '100%', filter: 'grayscale(1)', opacity: 0.45}}/>}
          <img src={layer.image_url} alt={layer.kind === 'transition' ? 'Esri 실제 전이 지도' : 'Esri 연차 토지피복 지도'}
            onError={() => setImageFailed(true)} style={{position: 'relative', display: 'block', width: '100%'}}/>
        </div>}
      <figcaption>Esri / Impact Observatory v003 · {layer.kind === 'transition' ? '분홍색은 질의한 전이 위치' : '반텐 연차 토지피복'}</figcaption>
    </figure>}
    </div>
  </section>;
}

function QuantitativeAnswer({result, lang}: {result: Answer; lang: Lang}) {
  const labels = {ko: ['정량 GIS 결과', '근거 자료', '클래스', '검증된 도구 출력'],
    id: ['Hasil GIS', 'Sumber data', 'Kelas', 'Hasil dari alat GIS'],
    en: ['GIS result', 'Data sources', 'Classes', 'Verified GIS tool output']}[lang];
  const labelIndex = {ko: 0, id: 1, en: 2}[lang];
  const localizedNumber = new Intl.NumberFormat({ko: 'ko-KR', id: 'id-ID', en: 'en-US'}[lang],
    {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const classes = (codes: number[]) => codes.map(code => `${result.class_names?.[code] ?? ''} (${code})`).join(' · ');
  if (result.status === 'BLOCKED') return <p role="status" data-testid="geollm-blocked">
    {REASONS[result.reason ?? ''] ?? '해당 질의를 확인할 수 없습니다.'}
  </p>;
  return <section aria-label={labels[0]} data-testid="geollm-gis-answer">
    <h3>{labels[0]}</h3>
    <p>{labels[3]} · Banten · {result.query?.years.join(' → ')}</p>
    <dl>{result.metrics?.map(item => <div key={item.key + item.from_codes.join(',')}>
      <dt>{METRIC[item.key]?.[labelIndex]}{item.name ? ` · ${item.name}` : ''}</dt>
      <dd><strong>{localizedNumber.format(item.value)} {item.unit}</strong></dd>
      <dd>{labels[2]} · {classes(item.from_codes)}{item.to_codes.length ? ` → ${classes(item.to_codes)}` : ''}</dd>
    </div>)}</dl>
    {result.map && <AnswerMap key={result.map.image_url ?? 'boundary'} layer={result.map}/>}
    <h3>{labels[1]}</h3>
    <ul>{result.sources?.map(source => <li key={source.sha256}>
      <a href={source.url} target="_blank" rel="noreferrer">{source.name} · {source.version}</a>
      {source.sheet ? ` · ${source.sheet}` : ''}{source.year ? ` · ${source.year}` : ''}
      {source.download_url && <> · <a href={source.download_url}>XLSX</a></>}
      <details><summary>SHA-256</summary><code style={{overflowWrap: 'anywhere'}}>{source.sha256}</code></details>
    </li>)}</ul>
    <ul>{result.limitations?.map(code => <li key={code}>{LIMITS[code]}</li>)}</ul>
  </section>;
}

export default function MapbiomasKnowledge() {
  const [question, setQuestion] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [result, setResult] = useState<Answer>();
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true); setError(false); setResult(undefined); setSubmitted(text);
    try {
      const response = await fetch('/api/lcluc/geollm/query', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question: text})});
      if (!response.ok) throw new Error('geollm');
      setResult(await response.json() as Answer);
    } catch { setError(true); }
    finally { setBusy(false); }
  }

  return <section className="panel" aria-label="GeoLLM 토지피복 질의응답">
    <h2>GeoLLM 토지피복 질의응답</h2>
    <p>한국어 · Bahasa Indonesia · English · <a href="/api/rag/mapbiomas/catalog" target="_blank" rel="noreferrer">LANDY 문서 목록</a></p>
    <form onSubmit={search}><label>GeoLLM 질문<input value={question} onChange={event => setQuestion(event.target.value)}
      placeholder="예: MapBiomas 반텐 2024년 논 면적은?" maxLength={400} required/></label>
      <button type="submit" disabled={busy || !question.trim()}>{busy ? '조회 중…' : '질의 실행'}</button>
    </form>
    {error && <p role="alert">GeoLLM API에 연결하지 못했습니다.</p>}
    {result?.route === 'gis' && <QuantitativeAnswer result={result} lang={language(submitted)}/>}
    {result?.status === 'KNOWLEDGE_CORPUS_PENDING' && <p role="status">문서 색인 구축 중입니다.</p>}
    {result?.status === 'NO_MATCH' && <p role="status">관련 문서 근거를 찾지 못했습니다.</p>}
    {!!result?.citations.length && <div aria-label="MapBiomas 출처 결과">
      <h3>문서 근거</h3>
      {result.citations.map(item => <article key={item.id + ':' + item.page + ':' + item.text_offset}>
        <h4>{item.title}</h4><p>{item.version} · {item.language}{item.page ? ` · p. ${item.page}` : ''}</p>
        <p>{item.excerpt}</p>
        <a href={item.url} target="_blank" rel="noreferrer">MapBiomas 원문</a>
      </article>)}
    </div>}
  </section>;
}
