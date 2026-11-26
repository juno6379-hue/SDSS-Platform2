import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import LclucModelComparison from './LclucModelComparison';
import './lcluc-postprocess.css';

const API = '/api/lcluc/postprocess';
const tools = [
  ['Spatial Filter', '작은 고립 패치의 후보 분류를 점검합니다. 수역·침수 식생은 보호합니다.'],
  ['Temporal Filter', '같은 격자와 분류체계의 연속 3개년 이상 분류 결과가 필요합니다.'],
  ['Gap Fill', '원본의 관측 QA와 보완에 사용할 인접 연도의 분류가 필요합니다.'],
  ['Frequency Filter', '연속 분류 시계열과 클래스별 유효 관측 기준이 필요합니다.'],
  ['Incident Filter', '반복 전환을 검사할 장기 분류 시계열이 필요합니다.'],
  ['Hierarchical Integration', '동년 특화 분류 레이어와 검토된 클래스 우선순위가 필요합니다.'],
];

type Metrics = { overall_accuracy: number; mean_iou: number; macro_f1: number; per_class?: {class_code: number; f1: number | null}[] };
type ModelResult = { method: string; heldout_pixels: number; weak_reference_metrics?: Metrics; before?: Metrics; after?: Metrics };
type Hierarchy = {status: string; groups: Record<string, string[]>; registered?: string[]};
type Integration = {id: string; overlaps: number; layers: {code: number; name: string; pixels: number}[]};
type Run = {
  id: string; candidate: string; year: number; created_at: string; changed_pixels: number; changed_ha: number; valid_pixels: number;
  classes: { code: number; name: string; color: string; before_ha: number; after_ha: number; delta_ha: number }[];
  grid: { width: number; height: number; spacing_m: number; crs: string };
  accuracy: { reference: string; pixels: number; before: Metrics; after: Metrics; independent: { status: string } };
  history: { algorithm: string; source_report_sha256: string; parameters: {
    minimum_pixels: number; connectivity: number; protected: number[];
  }; changed_pixels: number }[];
};

const fmt = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 });
const percent = (n: number) => fmt.format(n * 100) + '%';
const time = (value: string) => new Date(value).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' }) + ' KST';
const modelName = (id: string) => id.includes('deeplabv3plus') ? 'DeepLabv3+' : id.includes('tiny-unet') ? 'Tiny U-Net' : 'Random Forest';
const sensorName = (id: string) => id.includes('sentinel-2') ? 'Sentinel-2' : 'Landsat';

function Result({ run }: { run: Run }) {
  const [position, setPosition] = useState(50);
  const [corrections, showCorrections] = useState(false);
  const [failed, setFailed] = useState(false);
  const url = API + '/runs/' + run.id;
  const asset = (file: string) => url + '/assets/' + file;
  const mapError = () => setFailed(true);
  const moveDivider = (clientX: number, control: HTMLElement) => {
    const map = control.parentElement?.getBoundingClientRect();
    if (map?.width) setPosition(Math.round(Math.max(0, Math.min(100, 100 * (clientX - map.left) / map.width))));
  };
  return <>
    <section className="panel postprocess-map-card" aria-label="후처리 전후 지도">
      <header><h2>후처리 전·후 토지피복도</h2><p>반텐 · {run.year}년 · {sensorName(run.candidate)} {modelName(run.candidate)} · {fmt.format(run.grid.spacing_m)}m 표시 격자</p></header>
      <div className="postprocess-map" style={{ aspectRatio: run.grid.width + '/' + run.grid.height }}>
        <img src={asset('before.png')} alt="후처리 전 토지피복도" onError={mapError}/>
        <img src={asset('after.png')} alt="후처리 후 토지피복도" onError={mapError}
          style={{ clipPath: `inset(0 0 0 ${position}%)` }}/>
        {corrections && <img className="postprocess-corrections" src={asset('corrections.png')} alt="변경된 픽셀과 보정 위치" onError={mapError}/>}
        <span className="postprocess-map-label left">후처리 전</span><span className="postprocess-map-label right">후처리 후</span>
        <span className="postprocess-map-divider" aria-hidden="true" style={{ left: `${position}%` }}/>
        <button type="button" className="postprocess-map-handle" style={{ left: `${position}%` }}
          aria-label="지도 Swipe 분할선 드래그" onPointerDown={event => {
            event.currentTarget.setPointerCapture(event.pointerId);
            moveDivider(event.clientX, event.currentTarget);
          }} onPointerMove={event => {
            if (event.currentTarget.hasPointerCapture(event.pointerId)) moveDivider(event.clientX, event.currentTarget);
          }} onKeyDown={event => {
            if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
              event.preventDefault();
              setPosition(value => Math.max(0, Math.min(100, value + (event.key === 'ArrowLeft' ? -1 : 1))));
            }
          }}>↔</button>
      </div>
      {failed && <p role="alert">지도 파일 조회에 실패했습니다.</p>}
      <div className="postprocess-map-tools">
        <label>Swipe 위치 <input aria-label="후처리 전후 Swipe" type="range" min={0} max={100}
          value={position} onChange={event => setPosition(Number(event.target.value))}/></label>
        <button type="button" onClick={() => setPosition(50)}>50:50</button>
        <label><input type="checkbox" checked={corrections} onChange={event => showCorrections(event.target.checked)}/> 보정 위치 표시</label>
      </div>
      <p><span className="postprocess-correction-color" aria-hidden="true"/> 보정 {fmt.format(run.changed_pixels)}픽셀 · {fmt.format(run.changed_ha)} ha · 유효 영역의 {percent(run.changed_pixels / run.valid_pixels)}</p>
    </section>
    <section className="panel postprocess-area">
      <h2>클래스별 면적 증감</h2>
      <table><thead><tr><th scope="col">클래스</th><th scope="col">전 (ha)</th><th scope="col">후 (ha)</th><th scope="col">증감 (ha)</th></tr></thead>
        <tbody>{run.classes.map(row => <tr key={row.code}><th scope="row"><i style={{ background: row.color }}/>{row.name}</th>
          <td>{fmt.format(row.before_ha)}</td><td>{fmt.format(row.after_ha)}</td><td>{row.delta_ha > 0 ? '+' : ''}{fmt.format(row.delta_ha)}</td></tr>)}</tbody>
      </table>
    </section>
    <section className="panel">
      <h2>후처리 전·후 품질 비교</h2>
      <p>같은 공간 홀드아웃 {fmt.format(run.accuracy.pixels)}픽셀 · {run.accuracy.reference} 약한 참조</p>
      <table><thead><tr><th scope="col">지표</th><th scope="col">전</th><th scope="col">후</th></tr></thead>
        <tbody>{([['약한 참조 일치도', 'overall_accuracy'], ['평균 IoU', 'mean_iou'], ['Macro F1', 'macro_f1']] as const)
          .map(([label, key]) => <tr key={key}><th scope="row">{label}</th><td>{percent(run.accuracy.before[key])}</td><td>{percent(run.accuracy.after[key])}</td></tr>)}
          <tr><th scope="row">독립 정확도</th><td colSpan={2}>미측정 · 독립 표본 필요</td></tr>
        </tbody></table>
    </section>
    <section className="panel">
      <h2>필터 파라미터·처리 이력</h2>
      <p>{time(run.created_at)}</p><p className="postprocess-run-id">실행 ID <code>{run.id}</code></p>
      {run.history.map(item => <p key={item.algorithm}>Spatial Filter ({item.algorithm}) · 최소 {item.parameters.minimum_pixels}픽셀 · {item.parameters.connectivity}방향 연결 · 보호 클래스 {item.parameters.protected.join(', ')} · 보정 {fmt.format(item.changed_pixels)}픽셀</p>)}
      <div className="postprocess-downloads">
        <a href={asset('original.tif')}>원본 GeoTIFF</a><a href={asset('processed.tif')}>후처리 GeoTIFF</a>
        <a href={asset('corrections.tif')}>보정 위치 GeoTIFF</a><a href={url} target="_blank" rel="noreferrer">이력·지표 JSON</a>
      </div>
    </section>
  </>;
}

export default function LclucPostprocess() {
  const [candidate, setCandidate] = useState<string | null>();
  const [candidates, setCandidates] = useState<string[]>([]);
  const [models, setModels] = useState<Record<string, ModelResult>>({});
  const [hierarchy, setHierarchy] = useState<Hierarchy>();
  const [integration, setIntegration] = useState<Integration>();
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, selectRun] = useState<string>();
  const [tool, selectTool] = useState(0);
  const [minimum, setMinimum] = useState('3');
  const [connectivity, setConnectivity] = useState(8);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const run = runs.find(item => item.id === selected);

  useEffect(() => {
    const cancel = new AbortController();
    void fetch(API, { signal: cancel.signal }).then(async response => {
      if (!response.ok) throw new Error('catalog');
      const catalog = await response.json() as { candidate: string | null; candidates: string[]; models: Record<string, ModelResult>; runs: Run[] };
      setRuns(catalog.runs);
      setCandidate(catalog.candidate);
      setCandidates(catalog.candidates);
      setModels(catalog.models);
      selectRun(catalog.runs[0]?.id);
    }).catch(() => { if (!cancel.signal.aborted) setError('후처리 입력과 이력 조회에 실패했습니다.'); });
    return () => cancel.abort();
  }, []);

  useEffect(() => {
    if (tool !== 5) return;
    const abort = new AbortController();
    void fetch(API + '/hierarchy', {signal: abort.signal}).then(async response => {
      if (!response.ok) throw new Error('hierarchy');
      setHierarchy(await response.json() as Hierarchy);
    }).catch(() => { if (!abort.signal.aborted) setError('계층 통합 입력 상태 조회에 실패했습니다.'); });
    return () => abort.abort();
  }, [tool]);

  async function runIntegration() {
    setBusy(true); setError('');
    try {
      const response = await fetch(API + '/hierarchy', { method: 'POST' });
      if (!response.ok) throw new Error('hierarchy');
      setIntegration(await response.json() as Integration);
    } catch { setError('동년 특화 레이어와 승인 입력을 확인하세요.'); }
    finally { setBusy(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidate || busy || tool !== 0) return;
    setError(''); setBusy(true);
    try {
      const response = await fetch(API + '/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ candidate, minimum_pixels: Number(minimum), connectivity }) });
      if (!response.ok) throw new Error('run');
      const result = await response.json() as Run;
      setRuns(previous => [result, ...previous.filter(item => item.id !== result.id)]);
      selectRun(result.id);
    } catch { setError('시험 실행에 실패했습니다. 분류 후보의 원본과 고정 근거를 확인하세요.'); }
    finally { setBusy(false); }
  }

  return <div className="postprocess">
    <section className="panel postprocess-toolbox">
      <h2>LCLUC Toolbox</h2>
      <div className="postprocess-tools" aria-label="후처리 도구">
        {tools.map(([label], index) => <button type="button" key={label} aria-pressed={tool === index}
          onClick={() => selectTool(index)}>{label}</button>)}
      </div>
      <p>{tool > 0 && tool < 5 && <strong>계획 · </strong>}{tools[tool][1]}</p>
      {tool === 5 && <div aria-label="특화 분류 입력 상태">
        {!hierarchy ? <p role="status">동년 특화 분류 입력 확인 중</p> : <>
          <p role="status">{hierarchy.status === 'READY' ? '실행 가능 · ' + hierarchy.registered?.join(', ') : hierarchy.status === 'INTAKE_CONTRACT_INVALID' ? '입력 계약 검증 실패' : '동년 라벨·특화 레이어 확보 대기'}</p>
          {Object.values(hierarchy.groups).map(names => <p key={names[0]}>{names.join(' · ')}</p>)}
          <button type="button" disabled={busy || hierarchy.status !== 'READY'} onClick={() => void runIntegration()}>계층 통합 시험 실행</button>
          {integration && <p>경합 {fmt.format(integration.overlaps)}픽셀 · <a href={API + '/hierarchy/' + integration.id + '/classification'}>통합 GeoTIFF</a></p>}
        </>}
      </div>}
      {tool === 0 && <form onSubmit={submit}>
        <label>입력 분류<select value={candidate ?? ''} disabled={!candidate} onChange={event => setCandidate(event.target.value)}>
          {candidates.length ? candidates.map(id => <option key={id} value={id}>반텐 {sensorName(id)} {modelName(id)} · 2020</option>) :
            <option value="">{candidate === null ? '등록된 후보 없음' : '후보 조회 중'}</option>}
        </select></label>
        <label>최소 연결 픽셀<input type="number" min={2} max={30} step={1} required value={minimum} onChange={event => setMinimum(event.target.value)}/></label>
        <label>연결 방향<select value={connectivity} onChange={event => setConnectivity(Number(event.target.value))}><option value={8}>8방향</option><option value={4}>4방향</option></select></label>
        <button type="submit" disabled={!candidate || busy}>{busy ? '시험 실행 중…' : '후처리 시험 실행'}</button>
      </form>}
      {error && <p role="alert">{error}</p>}
      {runs.length > 0 && <label className="postprocess-history">실행 이력 <select value={selected} onChange={event => selectRun(event.target.value)}>
        {runs.map(item => <option value={item.id} key={item.id}>{time(item.created_at)} · {sensorName(item.candidate)} {modelName(item.candidate)} · {item.history[0].parameters.minimum_pixels}픽셀 · {item.id.slice(0, 10)}</option>)}
      </select></label>}
    </section>
    <section className="panel"><h2>Landsat 모델 비교</h2><LclucModelComparison sensor="landsat"/></section>
    <section className="panel"><h2>Sentinel-2 모델 비교</h2><LclucModelComparison sensor="sentinel-2"/></section>
    {models.siamese?.before && models.siamese?.after && <section className="panel">
      <h2>Sentinel-2 Siamese U-Net 변화 후보</h2>
      <p>2020→2025 · Esri 연차 변화 약한 참조 · 같은 {fmt.format(models.siamese.heldout_pixels)}픽셀</p>
      <p>전체 지도 일치도 {percent(models.siamese.before.overall_accuracy)} → {percent(models.siamese.after.overall_accuracy)} · 공간 필터 시험</p>
      <p>변화 클래스 F1 {percent(models.siamese.before.per_class?.find(row => row.class_code === 1)?.f1 ?? 0)} → {percent(models.siamese.after.per_class?.find(row => row.class_code === 1)?.f1 ?? 0)}</p>
      <a href={API + '/siamese/preview'} target="_blank" rel="noreferrer">변화 후보 지도</a>{' · '}
      <a href={API + '/siamese/classification'}>변화 후보 GeoTIFF</a>{' · '}
      <a href={API + '/siamese/filtered_preview'} target="_blank" rel="noreferrer">공간 필터 후 지도</a>{' · '}
      <a href={API + '/siamese/filtered'}>공간 필터 후 GeoTIFF</a>
    </section>}
    {run && <Result key={run.id} run={run}/>}
  </div>;
}
