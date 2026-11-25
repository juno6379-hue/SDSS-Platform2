import {resultIdFromHash,resultReviewHash} from './institutionOpsClient';
import {InstitutionJobs,ModelReleases} from './InstitutionOperations';
import { SDSSHeader, SDSSFooter } from './SDSSChrome';
import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import type { GeoJSONSource } from 'maplibre-gl';
import { api, API_BASE } from './api';
import { firstGroupProvinces } from './provinces';
import CollectionStatus from './CollectionStatus';
import ModelReview from './ModelReview';
import AnalysisReview from './AnalysisReview';
import CommonResultReview from './CommonResultReview';
import TemporalCompare from './TemporalCompare';
import AgentCenter from './AgentCenter';
import GeoQuery from './GeoQuery';
import DashboardReference from './DashboardReference';
import DataCatalogReference from './DataCatalogReference';
import CatalogInsights from './CatalogInsights';
import {COMMON_RESULT_STEP,parseRoute,routeHash,appHistoryDepth,appHistoryState,navigationResponseCurrent,insightDatasetId,readCatalogSession} from './catalogNavigation';
import { PlatformSidebar, PlatformContext, ToolboxHub, ModelWorkspace, ModelMlopsWorkspace, navigationForStep, titleForStep, menuSections } from './PlatformShell';

type RecordValue = Record<string, unknown>;
type Bbox = [number, number, number, number];
type Job = { id: string; status: string; result?: unknown; error?: unknown };
const steps = ['현황 대시보드', '위성 데이터', '학습 데이터셋', '모델 학습', '공간 추론', '변화 분석', '모델 레지스트리', '의사결정 질의', '연차 지도 비교', 'Agent Center'];
const routes = ['/datasets/prepare', '/training', '/inference', '/change'];
const templates = [
  { scenes: ['region-01', 'region-02', 'region-03'].map(group => ({ image_path: '', label_path: '', group, label_source: 'dynamic_world' })), dataset_id: 'indonesia-lcluc', patch_size: 256, bands: [1, 2, 3, 4], scale: 0.0001, offset: 0 },
  { dataset_path: '', model_id: 'indonesia-lcluc-v1', epochs: 5, batch_size: 4, lr: 0.001, seed: 42, device: 'cpu' },
  { model_id: '', image_path: '', output_id: 'landcover' },
  { t1_path: '', t2_path: '', output_id: 'landcover-change', num_classes: 9 },
];
function obj(value: unknown): RecordValue { return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : {}; }
function rows(value: unknown): RecordValue[] {
  if (Array.isArray(value)) return value.map(obj);
  for (const key of ['items', 'datasets', 'models', 'jobs', 'analyses', 'features', 'tools', 'results']) if (Array.isArray(obj(value)[key])) return (obj(value)[key] as unknown[]).map(obj);
  return [];
}
function Json({ value }: { value: unknown }) { return <pre className="json">{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre>; }
function ErrorNotice({ error }: { error: string }) { return error ? <div role="alert" className="error">{error}</div> : null; }

// 지도는 선택한 AOI와 서버가 반환한 GeoJSON만 그린다. 기저지도 실패는 별도로 표시한다.
function MapView({ bbox, geometry, boundary, viewBounds }: { bbox: Bbox; geometry: unknown; boundary?: unknown; viewBounds?: Bbox }) {
  const container = useRef<HTMLDivElement>(null);
  const instance = useRef<maplibregl.Map | null>(null);
  const [mapError, setMapError] = useState('');
  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({ container: container.current, style: { version: 8, sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors' } }, layers: [{ id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-saturation': -0.65, 'raster-opacity': 0.85 } }] }, center: [117, -2], zoom: 4 });
    instance.current = map;
    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.on('error', () => setMapError('기저지도 일부를 불러오지 못했습니다. 인터넷 연결을 확인하세요.'));
    return () => { map.remove(); instance.current = null; };
  }, []);
  useEffect(() => {
    const map = instance.current;
    if (!map) return;
    const draw = () => {
      const province = obj(boundary);
      const provinceData = province.type ? province : { type: 'FeatureCollection', features: [] };
      if (map.getSource('province')) (map.getSource('province') as GeoJSONSource).setData(provinceData as never);
      else {
        map.addSource('province', { type: 'geojson', data: provinceData as never });
        map.addLayer({ id: 'province-fill', type: 'fill', source: 'province', paint: { 'fill-color': '#276b50', 'fill-opacity': 0.12 } });
        map.addLayer({ id: 'province-line', type: 'line', source: 'province', paint: { 'line-color': '#276b50', 'line-width': 2 } });
      }
      const [w, s, e, n] = bbox;
      const aoi = { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] } };
      if (map.getSource('aoi')) (map.getSource('aoi') as GeoJSONSource).setData(aoi as never);
      else { map.addSource('aoi', { type: 'geojson', data: aoi as never }); map.addLayer({ id: 'aoi-fill', type: 'fill', source: 'aoi', paint: { 'fill-color': '#13af91', 'fill-opacity': 0.12 } }); map.addLayer({ id: 'aoi-line', type: 'line', source: 'aoi', paint: { 'line-color': '#0b806d', 'line-width': 2, 'line-dasharray': [3, 2] } }); }
      const view = viewBounds || bbox;
      map.fitBounds([[view[0], view[1]], [view[2], view[3]]], { padding: 45, maxZoom: 18, duration: 600 });
      const geo = obj(geometry);
      if (['FeatureCollection', 'Feature', 'Polygon', 'MultiPolygon'].includes(String(geo.type))) {
        if (map.getSource('result')) (map.getSource('result') as GeoJSONSource).setData(geo as never);
        else { map.addSource('result', { type: 'geojson', data: geo as never }); map.addLayer({ id: 'result-fill', source: 'result', type: 'fill', paint: { 'fill-color': '#e67b34', 'fill-opacity': 0.5 } }); }
      } else if (map.getSource('result')) (map.getSource('result') as GeoJSONSource).setData({ type: 'FeatureCollection', features: [] });
    };
    if (map.isStyleLoaded()) draw(); else map.once('load', draw);
    return () => { map.off('load', draw); };
  }, [bbox, geometry, boundary, viewBounds]);
  return <div className="map-shell"><div ref={container} className="map" /><span className="map-label">점선: 검색 bbox{boundary ? ' · 진한 실선: 공개 주 경계(2017)' : ''}{geometry ? ' · 주황: 분류지도 간 변화(독립 미검증)' : ''}</span>{mapError && <span className="map-error">{mapError}</span>}</div>;
}

function Workflow({ index, onJob, initialModelId = '' }: { index: number; onJob: (job: Job) => void; initialModelId?: string }) {
  const [payload, setPayload] = useState(JSON.stringify(templates[index], null, 2));
  const [result, setResult] = useState<unknown>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { setPayload(JSON.stringify(index === 2 && initialModelId ? { ...templates[index], model_id: initialModelId } : templates[index], null, 2)); setResult(undefined); setError(''); }, [index, initialModelId]);
  async function submit() {
    setError(''); setBusy(true);
    try {
      const parsed = JSON.parse(payload);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('요청은 JSON 객체여야 합니다.');
      const data = await api<Job>(routes[index], parsed);
      setResult(data);
      if (data.id) onJob(data);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  const descriptions = [
    '최소 3개 독립 지역 그룹에 실제 영상·라벨 경로를 입력하세요. 같은 지역의 연차·인접 타일은 같은 group을 사용합니다. label_source는 dynamic_world(9개 확률 밴드), worldcover, classes입니다. bands는 1부터 시작하며 구름 마스크가 있으면 quality_mask_path를 추가합니다.',
    'dataset_path에 데이터 준비 작업이 반환한 manifest 경로를 입력하세요. 학습 완료 후 서버가 반환한 검증 지표와 모델 산출물을 확인할 수 있습니다.',
    '배포된 모델 ID와 실제 입력 영상 경로를 입력하세요. 서버가 배포 체크포인트를 사용합니다. 제품별 정규화 모델은 normalization(evidence_path/evidence_sha256/scale/offset)과 source_scene(scene_id/image_sha256/band_names)이 추가로 필요합니다. 제품 XML로 확인된 실제 값만 입력하며 scale·offset을 추정하지 않습니다. 시계열은 images 각 항목에 같은 근거를 넣습니다. GeoTIFF 결과 경로는 작업 결과에서 확인합니다.',
    '동일 좌표계·해상도·공간 범위의 두 시점 분류 래스터를 입력하세요. 서버가 실제 변화량과 전이 정보를 계산합니다.',
  ];
  return <section className="panel"><div className="section-title"><div><span className="eyebrow">PROCESS 0{index + 2}</span><h2>{steps[index + 2]}</h2></div><span className="pill">비동기 작업</span></div><p className="muted">{descriptions[index]}</p><p className="hint">JSON 예시의 빈 경로·ID를 실제 값으로 바꾸세요. 설치된 서버의 정확한 입력 규격은 <a href={API_BASE.replace(/\/api$/, '') + '/docs'} target="_blank" rel="noreferrer">API 문서 ↗</a>에서 확인할 수 있습니다.</p><label>요청 JSON<textarea className="editor" spellCheck={false} value={payload} onChange={e => setPayload(e.target.value)} /></label><button disabled={busy} onClick={submit}>{busy ? '요청 중…' : '작업 실행 →'}</button><ErrorNotice error={error} />{result !== undefined && <><h3>서버 응답</h3><Json value={result} /></>}</section>;
}

export default function App() {
  const [route,setRoute]=useState(()=>parseRoute(window.location.hash));
  const step=route.step;
  const [workspaceAgent, setWorkspaceAgent] = useState(()=>parseRoute(window.location.hash).model);
  const [catalogSearch,setCatalogSearch]=useState('');
  const [workspaceTab, setWorkspaceTab] = useState(()=>parseRoute(window.location.hash).tab);
  const navigationGeneration=useRef(0);
  function go(next:number,dataset=route.dataset,replace=false){navigationGeneration.current++;setBusy(false);const value={step:next,dataset:next===1||(next>=26&&next<=30)?dataset:'',model:workspaceAgent,tab:workspaceTab};const hash=routeHash(value);if(window.location.hash!==hash){const depth=appHistoryDepth(history.state);history[replace?'replaceState':'pushState'](appHistoryState(replace?depth:depth+1),'',hash);}setRoute(value);setActionResult(undefined);setActionError('');}
  const navigate=(next:number)=>go(next,next>=26&&next<=30?insightDatasetId(route.dataset,readCatalogSession().selected,rows(resources.datasets).map(row=>String(row.id||row.dataset_id||''))):route.dataset);
  function previous(){if(appHistoryDepth(history.state)>0)history.back();else go(1,route.dataset,true);}
  useEffect(()=>{const update=()=>{navigationGeneration.current++;setBusy(false);const value=parseRoute(window.location.hash);const linkedResult=resultIdFromHash(window.location.hash);const canonical=value.step===COMMON_RESULT_STEP&&linkedResult?resultReviewHash(linkedResult):routeHash(value);if(canonical!==window.location.hash)history.replaceState(appHistoryState(appHistoryDepth(history.state)),'',canonical);setRoute(value);setWorkspaceAgent(value.model);setWorkspaceTab(value.tab);setActionResult(undefined);setActionError('');};update();window.addEventListener('popstate',update);window.addEventListener('hashchange',update);return()=>{window.removeEventListener('popstate',update);window.removeEventListener('hashchange',update);};},[]);
  useEffect(()=>{if(step===24){const value={...route,model:workspaceAgent,tab:workspaceTab};history.replaceState(appHistoryState(appHistoryDepth(history.state)),'',routeHash(value));}},[workspaceAgent,workspaceTab,step]);
  const currentMenu = step===25?1:navigationForStep(step);
  useEffect(() => { window.scrollTo({top:0,behavior:'instant'}); }, [step,workspaceAgent,workspaceTab]);
  const [resources, setResources] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [bboxText, setBboxText] = useState('106.6,-6.4,107.1,-6.0');
  const [bbox, setBbox] = useState<Bbox>([106.6, -6.4, 107.1, -6]);
  const [geometry, setGeometry] = useState<unknown>();
  const [provinceGeometry, setProvinceGeometry] = useState<unknown>();
  const [mapBounds, setMapBounds] = useState<Bbox>();
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState('2024-12-31');
  const [satellite, setSatellite] = useState('sentinel-2');
  const [endpoint, setEndpoint] = useState('planetary-computer');
  const [cloud, setCloud] = useState(20);
  const [actionResult, setActionResult] = useState<unknown>();
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeAnalysis, setActiveAnalysis] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');
  const [filename, setFilename] = useState('satellite.tif');
  const [activeModel, setActiveModel] = useState('');
  const refreshGeneration=useRef(0);
  async function refresh() {
    const generation=++refreshGeneration.current;
    setLoading(true);
    await Promise.all(['health', 'dashboard', 'datasets', 'models', 'jobs', 'tools', 'analyses'].map(async key => {
      try { const data = await api('/' + key); if(generation!==refreshGeneration.current)return; setResources(r => ({ ...r, [key]: data })); setErrors(e => ({ ...e, [key]: '' })); }
      catch (e) { if(generation===refreshGeneration.current)setErrors(v => ({ ...v, [key]: String(e) })); }
    }));
    if(generation===refreshGeneration.current)setLoading(false);
  }
  useEffect(() => { void refresh(); return()=>{refreshGeneration.current++;}; }, []);
  // 완료·실패 상태까지 실제 작업 ID를 폴링하며 화면을 떠나면 타이머를 해제한다.
  useEffect(() => {
    if (!jobs.some(j => !['completed', 'succeeded', 'failed', 'cancelled'].includes(j.status.toLowerCase()))) return;
    let active = true;
    const timer = window.setInterval(async () => {
      await Promise.all(jobs.filter(j => !['completed', 'succeeded', 'failed', 'cancelled'].includes(j.status.toLowerCase())).map(async job => {
        try {
          const updated = await api<Job>(`/jobs/${encodeURIComponent(job.id)}`);
          if (!active) return;
          setJobs(v => v.map(j => j.id === updated.id ? updated : j));
          const result = obj(updated.result);
          const geo = result.geojson || result.change_geojson || result.geometry;
          if (geo) setGeometry(geo);
          if (['succeeded', 'completed', 'failed', 'cancelled'].includes(updated.status.toLowerCase())) void refresh();
        } catch (e) { if (active) setErrors(v => ({ ...v, polling: String(e) })); }
      }));
    }, 2500);
    return () => { active = false; window.clearInterval(timer); };
  }, [jobs]);
  function addJob(job: Job) { setJobs(v => [job, ...v.filter(j => j.id !== job.id)]); }
  function readBbox(): Bbox {
    const values = bboxText.split(',').map(v => Number(v.trim()));
    if (values.length !== 4 || values.some(v => !Number.isFinite(v)) || values[0] >= values[2] || values[1] >= values[3] || values[0] < -180 || values[2] > 180 || values[1] < -90 || values[3] > 90) throw new Error('AOI는 서,남,동,북 순서의 유효한 경위도 4개여야 합니다. 서 < 동, 남 < 북을 확인하세요.');
    setBbox(values as Bbox); setMapBounds(undefined); return values as Bbox;
  }
  async function action(path: string, body?: unknown) {
    const generation=navigationGeneration.current;const routeKey=window.location.hash;
    const current=()=>navigationResponseCurrent(generation,navigationGeneration.current,routeKey,window.location.hash);
    setActionError(''); setBusy(true); setActionResult(undefined);
    try { const data = await api(path, body); if(!current())return; setActionResult(data); const result = obj(data); if (result.id && result.status) addJob(result as unknown as Job); if (result.geojson) setGeometry(result.geojson); }
    catch (e) { if(current())setActionError(String(e)); } finally { if(current())setBusy(false); }
  }
  function satelliteAction(path: string) {
    try {
      const area = readBbox();
      if (!startDate || !endDate || startDate > endDate) throw new Error('올바른 시작일과 종료일을 선택하세요.');
      void action(path, path.includes('worldcover') ? { bbox: area } : { bbox: area, start_date: startDate, end_date: endDate, endpoint, satellite, collection: satellite === 'landsat' ? 'landsat-c2-l2' : 'sentinel-2-l2a', cloud_cover: cloud, limit: 10 });
    } catch (e) { setActionError(String(e)); }
  }
  const datasets = rows(resources.datasets), models = rows(resources.models), analyses = rows(resources.analyses);
  useEffect(()=>{if(route.dataset&&resources.datasets!==undefined&&!errors.datasets&&!datasets.some(row=>String(row.id||row.dataset_id||'')===route.dataset)){const value={...route,dataset:''};history.replaceState(appHistoryState(appHistoryDepth(history.state)),'',routeHash(value));setRoute(value);}},[resources.datasets,errors.datasets,route]);
  const connected = resources.health !== undefined && !errors.health;
  if (step === 0) return <DashboardReference resources={resources} errors={errors} connected={connected} loading={loading} onRefresh={()=>void refresh()} onNavigate={navigate} onOpenModel={id=>{setWorkspaceAgent(id);setWorkspaceTab('input');navigate(24);}}/>;
  if(step>=26&&step<=30)return <CatalogInsights step={step} datasetId={route.dataset} datasets={resources.datasets===undefined?undefined:datasets} error={errors.datasets} onNavigate={navigate} onDataset={id=>go(step,id,true)} onBack={previous} onOpenModel={id=>{setWorkspaceAgent(id);setWorkspaceTab('input');navigate(24);}}/>;
  if (step === 1) return <DataCatalogReference datasetId={route.dataset} onDataset={id=>go(1,id)} datasets={resources.datasets===undefined?undefined:datasets} error={errors.datasets} loading={loading} onRefresh={()=>void refresh()} onNavigate={navigate}/>;
  return <div className={currentMenu === 5 ? "app mlops-page" : step===24?"app reference-workspace":step===12||step===13?"app toolbox-page":"app"}><SDSSHeader onSearch={query=>{setCatalogSearch(query);navigate(11);}} onNavigate={navigate} onRefresh={()=>void refresh()} loading={loading} connected={connected}/><PlatformSidebar step={step===25?1:step} connected={connected} onNavigate={navigate}/><main><div className="content">{currentMenu !== 5 && <PlatformContext step={step} agent={workspaceAgent} tab={workspaceTab}/>}{currentMenu !== 5 && import.meta.env.VITE_FIXTURE_MODE === 'true' && <div className="readiness-warning" role="status"><strong>합성 통합시험 전용 · 실제 정확도 아님</strong><span>운영 API·카탈로그와 분리된 임시 시험 화면입니다.</span></div>}{currentMenu !== 5 && <div className="page-heading"><div><span className="eyebrow">SPATIAL DECISION SUPPORT SYSTEM</span><h1>{step === 24 ? 'Model Analysis Workspace' : step===25?'관측자료 검색·다운로드':titleForStep(step)}</h1><p>인도네시아 기후행동을 위한 데이터, 분석, 검증과 의사결정.</p></div><span className="region-badge">◎ INDONESIA</span></div>}
      {currentMenu !== 5 && <nav className="local-tabs" aria-label="현재 메뉴의 세부 기능">{menuSections[currentMenu].map(([id, label]) => <button key={id} aria-current={step === id ? 'page' : undefined} className={step === id ? 'active' : ''} onClick={() => navigate(id)}>{label}</button>)}</nav>}
      {(step === 12 || step === 13) && <ToolboxHub tools={resources.tools===undefined?undefined:rows(resources.tools)} datasets={resources.datasets===undefined?undefined:datasets} models={resources.models===undefined?undefined:models} jobs={resources.jobs===undefined?undefined:rows(resources.jobs)} errors={errors} loading={loading} connected={connected} onNavigate={navigate} onRefresh={()=>void refresh()} onOpen={id => {setWorkspaceAgent(id);setWorkspaceTab('input');navigate(24);}}/>}
      {step === 24 && <ModelWorkspace agentId={workspaceAgent} tab={workspaceTab} onTab={setWorkspaceTab} onBack={() => navigate(12)} onNavigate={navigate} tools={rows(resources.tools)}>
        {workspaceAgent === 'lcluc' && workspaceTab === 'input' && <details className="panel"><summary>Expert · 기존 공간 추론 API 입력</summary><Workflow index={2} onJob={addJob} initialModelId={activeModel}/></details>}
        {workspaceAgent === 'lcluc' && workspaceTab === 'result' && <AnalysisReview initialSelected={activeAnalysis} analyses={analyses} onView={(geo,bounds)=>{setGeometry(geo);if(bounds)setBbox(bounds);navigate(14);}}/>}
        {workspaceTab === 'evidence' && <AgentCenter tools={rows(resources.tools)} models={models} jobs={rows(resources.jobs)} onNavigate={navigate} onStandardLayer={(geo,bounds)=>{setGeometry(geo);setProvinceGeometry(undefined);if(bounds){setBbox(bounds);setMapBounds(bounds);}navigate(14);}}/>}
        {workspaceTab === 'history' && <ResourceList title="실제 서버 Job·Trace" data={resources.jobs} error={errors.jobs}/>}
      </ModelWorkspace>}
      {step === 10 && <CollectionStatus/>}
      {step === 11 && <><section className="panel"><label>등록 데이터 검색<input value={catalogSearch} onChange={e=>setCatalogSearch(e.target.value)} placeholder="ID, 지역, 출처, 메타데이터 검색"/></label><p className="help">서버에서 조회한 등록 데이터의 메타데이터를 검색합니다.</p></section><ResourceList title="데이터 메타데이터·출처" data={resources.datasets===undefined?undefined:datasets.filter(row=>JSON.stringify(row).toLocaleLowerCase().includes(catalogSearch.toLocaleLowerCase()))} error={errors.datasets}/></>}
      {step === 14 && <><MapView bbox={bbox} geometry={geometry} boundary={provinceGeometry} viewBounds={mapBounds}/><AnalysisReview initialSelected={activeAnalysis} analyses={analyses} onView={(geo,bounds)=>{setGeometry(geo);setProvinceGeometry(undefined);if(bounds){setBbox(bounds);setMapBounds(bounds);}}}/></>}
      {(step === 15 || step === 16) && <GeoQuery initialKind={step === 15 ? 'execution' : 'evidence'} analyses={analyses} onAgentCenter={()=>navigate(9)} onReviewResult={id=>{setActiveAnalysis(id);navigate(14);}}/>}
      {currentMenu === 5 && (
        <>
          <ModelMlopsWorkspace onNavigate={navigate} activeStep={step} />
          {step === 6 && (
            <details className="panel" style={{ marginTop: '16px' }}>
              <summary>기존 모델 레지스트리 상세 검토 및 추론 연결 (Legacy View)</summary>
              <ModelReview models={models} onJob={addJob} onChanged={refresh} onInference={id => { setActiveModel(id); navigate(4); }}/>
            </details>
          )}
          {step === 3 && (
            <details className="panel" open style={{ marginTop: '16px' }}>
              <summary>전문가 파라미터 · 재학습 요청 (Legacy Workflow)</summary>
              <Workflow index={1} onJob={addJob} initialModelId={activeModel}/>
            </details>
          )}
          {(step === 17 || step === 18) && <ModelReleases/>}
          {step === 17 && (
            <details className="panel" style={{ marginTop: '16px' }}>
              <summary>전문가 검토 · 배포 관리 (Legacy View)</summary>
              <ModelReview models={models} onJob={addJob} onChanged={refresh} onInference={id => { setActiveModel(id); navigate(4); }}/>
            </details>
          )}
          {step === 18 && (
            <details className="panel" style={{ marginTop: '16px' }}>
              <summary>서버 원본 등록 모델 상태 (Raw API Resource)</summary>
              <ResourceList title="등록 모델 상태" data={resources.models} error={errors.models}/>
              <section className="panel" style={{ marginTop: '8px' }}>
                <h2>운영 모니터링 상세</h2>
                <p className="empty">운영 Kubernetes·성능 지표·알림 API 연결 대기</p>
              </section>
            </details>
          )}
        </>
      )}
      {step === 19 && <AnalysisReview initialSelected={activeAnalysis} analyses={analyses} onView={(geo,bounds)=>{setGeometry(geo);if(bounds)setBbox(bounds);navigate(14);}}/>}
      {step === 20 && <section className="panel"><span className="eyebrow">SPATIAL PLANNING</span><h2>RDTR 공간계획 검토</h2><p className="muted">지역 공간계획의 공식 경계·용도지역·정책 근거와 권한이 연결된 뒤 분석 결과를 중첩합니다.</p><p className="empty">공식 RDTR/RTRW 데이터와 검토·승인 API 미연결</p><div className="button-row"><button className="secondary" onClick={()=>navigate(14)}>분석 지도 보기</button><button disabled>계획 승인 API 미연결</button></div></section>}
      {step === 21 && <section className="panel"><h2>검토·승인 이력</h2><p className="empty">기관별 보고서 승인·전자서명 이력 API 미연결</p><button className="secondary" onClick={()=>navigate(17)}>모델의 실제 승인 근거 검토</button></section>}
      {step === COMMON_RESULT_STEP && <CommonResultReview/>}
      {step === 22 && <><InstitutionJobs/><ResourceList title="저장된 작업·알림" data={resources.jobs} error={errors.jobs}/></>}
      {step === 23 && <AgentCenter tools={rows(resources.tools)} models={models} jobs={rows(resources.jobs)} onNavigate={navigate} onStandardLayer={(geo,bounds)=>{setGeometry(geo);setProvinceGeometry(undefined);if(bounds){setBbox(bounds);setMapBounds(bounds);}navigate(14);}}/>}
      {step === 0 && <><div className="metrics"><Metric label="등록 데이터셋" value={errors.datasets ? '—' : resources.datasets === undefined ? '…' : String(datasets.length)} suffix="개"/><Metric label="모델 레지스트리" value={errors.models ? '—' : resources.models === undefined ? '…' : String(models.length)} suffix="개"/><Metric label="저장된 분석" value={errors.analyses ? '—' : resources.analyses === undefined ? '…' : String(analyses.length)} suffix="건"/><Metric label="API 연결" value={connected ? '정상' : '미연결'} suffix=""/></div><CollectionStatus compact/><ErrorNotice error={errors.health || ''}/><div className="map-heading"><h2>분석 영역 탐색</h2><span className="muted">선택한 연구 AOI · 실행 전 범위를 확인하세요</span></div><MapView bbox={bbox} geometry={geometry} boundary={provinceGeometry} viewBounds={mapBounds}/><div className="two-col"><section className="panel"><span className="eyebrow">YOUR NEXT STEP</span><h2>위성 데이터에서 시작하세요</h2><p className="muted">관심 영역과 기간으로 실제 카탈로그를 검색한 뒤, 데이터 준비 → 학습 → 추론 → 변화 분석 순서로 진행합니다.</p><button onClick={() => navigate(1)}>위성 데이터 검색 →</button></section><section className="panel"><span className="eyebrow">LIVE SERVER RESPONSE</span><h2>플랫폼 현황</h2><ErrorNotice error={errors.dashboard || ''}/>{resources.dashboard !== undefined ? <Json value={resources.dashboard}/> : <p className="empty">서버 현황 응답을 기다리는 중입니다.</p>}</section></div></>}
      {(step === 1 || step === 25) && <section className="panel catalog-intro"><div><span className="eyebrow">DATA CATALOG</span><h2>관측 데이터 검색</h2><p className="muted">검색·품질·출처를 확인한 다음 분석할 모델을 직접 선택하세요.</p></div><button className="secondary" onClick={()=>navigate(12)}>선택 데이터로 분석 도구 찾기 →</button></section>}

      {(step === 1 || step === 25) && <FirstGroupScope onSelect={(area, feature, provinceBbox) => { setBbox(area); setBboxText(area.join(',')); setGeometry(undefined); setProvinceGeometry(feature); setMapBounds(provinceBbox); }}/>}
      {(step === 1 || step === 25) && <><div className="two-col data-layout"><section className="panel"><span className="eyebrow">PROCESS 01</span><h2>관측 조건 설정</h2><label>관심 영역 (W, S, E, N)<input value={bboxText} onChange={e => setBboxText(e.target.value)} /></label><small className="help">경도·위도, EPSG:4326 · 예: 106.6,-6.4,107.1,-6.0</small><button className="secondary" onClick={() => { try { readBbox(); setActionError(''); } catch (e) { setActionError(String(e)); } }}>지도에서 영역 확인</button><div className="two-col"><label>시작일<input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}/></label><label>종료일<input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}/></label></div><label>위성<select value={satellite} onChange={e => setSatellite(e.target.value)}><option value="sentinel-2">Sentinel-2</option><option value="landsat">Landsat</option></select></label><label>최대 운량 {cloud}%<input type="range" min="0" max="100" value={cloud} onChange={e => setCloud(Number(e.target.value))}/></label><div className="button-row"><button disabled={busy} onClick={() => satelliteAction('/data/search')}>영상 검색 →</button><button className="secondary" disabled={busy} onClick={() => satelliteAction('/data/worldcover/plan')}>WorldCover 계획</button><button className="secondary" disabled={busy} onClick={() => satelliteAction('/data/dynamic-world/export')}>Dynamic World 내보내기</button></div></section><MapView bbox={bbox} geometry={geometry} boundary={provinceGeometry} viewBounds={mapBounds}/></div><section className="panel"><h2>실제 영상 다운로드</h2><p className="muted">검색 결과의 다운로드 가능한 자산 URL을 입력하세요. 인증이 필요한 제공처는 서버 자격증명이 필요할 수 있습니다.</p><div className="download-fields"><label>자산 URL<input type="url" placeholder="https://…" value={downloadUrl} onChange={e => setDownloadUrl(e.target.value)}/></label><label>저장 파일명<input value={filename} onChange={e => setFilename(e.target.value)}/></label><button disabled={busy || !downloadUrl || !filename} onClick={() => void action('/data/download', { url: downloadUrl, filename, max_bytes: 1000000000 })}>다운로드</button></div></section></>}
      {step >= 2 && step <= 5 && step !== 3 && <><Workflow key={step} index={step - 2} onJob={addJob} initialModelId={activeModel}/>{step === 2 && <ResourceList title="등록 데이터셋" data={resources.datasets} error={errors.datasets}/ >}{step === 5 && <><MapView bbox={bbox} geometry={geometry} boundary={provinceGeometry} viewBounds={mapBounds}/><AnalysisReview initialSelected={activeAnalysis} analyses={analyses} onView={(geo, bounds) => { setGeometry(geo); setProvinceGeometry(undefined); if (bounds) { setBbox(bounds); setMapBounds(bounds); } window.requestAnimationFrame(() => document.querySelector('.map-shell')?.scrollIntoView({behavior:'smooth'})); }}/></>}</>}
      {step === 9 && <AgentCenter tools={rows(resources.tools)} models={models} jobs={rows(resources.jobs)} onNavigate={navigate} onStandardLayer={(geo,bounds)=>{setGeometry(geo);setProvinceGeometry(undefined);if(bounds){setBbox(bounds);setMapBounds(bounds);}navigate(14);}}/>}
      {step === 8 && <TemporalCompare/>}
      {step === 7 && <GeoQuery analyses={analyses} onAgentCenter={() => navigate(9)} onReviewResult={id => {setActiveAnalysis(id);navigate(5);}}/>}
      {(step === 1 || step === 25) && <section className="panel"><h2>카탈로그 제공처 및 연차별 수집</h2><label>STAC 제공처<select value={endpoint} onChange={e => setEndpoint(e.target.value)}><option value="planetary-computer">Microsoft Planetary Computer (기본)</option><option value="earth-search">Element 84 Earth Search</option></select></label><p className="muted">수집 기준: 2020~2025년, 동일 계절·동일 밴드, 첫 번째 그룹의 6개 주 × 6개 연차의 36개 셀입니다. 검색은 위의 기간 설정으로 실행하고 수집 계획과 실제 다운로드 결과를 구분해 확인하세요.</p><div className="button-row">{[2020, 2021, 2022, 2023, 2024, 2025].map(year => <button key={year} className="secondary" onClick={() => { setStartDate(`${year}-01-01`); setEndDate(`${year}-12-31`); }}>{year}년 기간 선택</button>)}</div><p className="help">연도 버튼은 조회 기간만 바꿉니다. 계절 비교 시 월·일을 동일하게 직접 조정하세요. 다운로드 진행 여부는 실제 작업 응답에서 확인합니다.</p></section>}
      {step === 5 && <JsonRequest title="2020~2025 연차별 시계열 분석" path="/timeseries" initial={{ model_id: '', images: [2020, 2021, 2022, 2023, 2024, 2025].map(year => ({ year, image_path: '', source: '', license: '', date: `${year}-01-01` })), output_id: 'indonesia-timeseries' }} help="배포 모델 ID와 6개 연차의 실제 영상 경로를 입력하세요. 동일 계절·밴드·AOI의 정렬된 영상이 필요합니다. 서버의 분류 결과와 인접 연차·2020년 기준 변화량만 표시합니다." onJob={addJob}/>}

      <ErrorNotice error={actionError}/>{busy && <div className="notice" role="status">서버에서 요청을 처리하고 있습니다…</div>}{actionResult !== undefined && <section className="panel"><h2>요청 결과</h2>{(step === 1 || step === 25) && rows(actionResult).length > 0 && <SearchResults data={actionResult} onAsset={url => { setDownloadUrl(url); setFilename('satellite.tif'); }}/>}<Json value={actionResult}/></section>}
      {jobs.length > 0 && <section className="panel"><div className="section-title"><h2>이번 세션의 작업</h2><span className="pill">2.5초 자동 갱신</span></div><ErrorNotice error={errors.polling || ''}/>{jobs.map(job => <details key={job.id} className="job" open={job.status === 'failed'}><summary><code>{job.id}</code><span className="pill">{job.status}</span></summary><Json value={job}/></details>)}</section>}
      <ConnectionSettings onChange={() => void refresh()}/>
      <SDSSFooter/>
    </div></main></div>;
}
function Metric({ label, value, suffix }: { label: string; value: string; suffix: string }) { return <div className="metric"><span>{label}</span><strong>{value}<small>{suffix}</small></strong><div className="metric-line"/></div>; }
function FirstGroupScope({ onSelect }: { onSelect: (bbox: Bbox, feature: unknown, provinceBbox: Bbox) => void }) {
  const [selected, setSelected] = useState('south_sulawesi');
  const [boundaries, setBoundaries] = useState<RecordValue[]>([]);
  const [boundaryError, setBoundaryError] = useState('');
  useEffect(() => {
    let active = true;
    // 실제 공개 경계 파일은 별도 정적 자산으로 읽어 지도 라이브러리 번들에 포함하지 않는다.
    fetch(`${import.meta.env.BASE_URL}first-group-provinces.geojson`).then(async response => {
      if (!response.ok) throw new Error(`경계 파일 HTTP ${response.status}`);
      const data: unknown = await response.json();
      if (active) setBoundaries(rows(data));
    }).catch(e => { if (active) setBoundaryError(String(e)); });
    return () => { active = false; };
  }, []);
  const province = firstGroupProvinces.find(item => item.id === selected)!;
  const feature = boundaries.find(item => obj(item.properties).province_id === selected);
  // 공개 ADM1 참조자료 내부점으로 생성한 실제 수집 설정의 소규모 검색 bbox를 사용한다.
  return <section className="panel"><div className="section-title"><div><span className="eyebrow">PROJECT GROUP 01 · 2020–2025</span><h2>첫 번째 그룹 우선 수집 범위</h2></div><span className="pill">6개 주 · 36개 연차 셀 목표</span></div><label>프로젝트 대상 주<select value={selected} onChange={e => setSelected(e.target.value)}>{firstGroupProvinces.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><p className="muted">South Sulawesi · Gorontalo · Southeast Sulawesi · Banten · West Java · East Java</p><p className="hint">경계 상태: 공개 ADM1 참조자료 확보 · 사업 경계 미확정. 아래 bbox는 주 내부의 작은 연구 표본 검색 범위입니다. 주 전체의 수집 범위와 구분해 사용하세요.</p><p className="help">후보 bbox: {province.bbox.map(value => value.toFixed(6)).join(', ')}</p><button className="secondary" disabled={!feature} onClick={() => onSelect(province.bbox as Bbox, feature, province.provinceBbox as Bbox)}>후보 bbox 검색 적용 · 공개 주 전체 경계 보기</button><ErrorNotice error={boundaryError}/>{!feature && !boundaryError && <p className="help" role="status">공개 주 경계 자료를 불러오는 중입니다…</p>}<p className="help">경계 출처: geoBoundaries / OpenStreetMap·Wambacher, 2017년 ADM1 참조, ODbL 1.0. 사업상 확정 경계는 별도 검토가 필요합니다.</p><p className="help">2020~2025년 동일 계절·동일 밴드의 36개 주·연도 조합이 수집 목표입니다. 실제 검색 결과와 작업 상태로 확보 여부를 확인하세요.</p></section>;
}
function JsonRequest({ title, path, initial, help, disabled, onJob }: { title: string; path: string; initial: unknown; help: string; disabled?: boolean; onJob: (job: Job) => void }) {
  const [text, setText] = useState(() => JSON.stringify(initial, null, 2));
  const [result, setResult] = useState<unknown>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true); setError('');
    try {
      const payload: unknown = JSON.parse(text);
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('JSON 객체가 필요합니다.');
      const data = await api<Job>(path, payload);
      setResult(data);
      if (data.id) onJob(data);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>{title}</h2><p className="muted">{help}</p><label>요청 JSON<textarea className="editor" spellCheck={false} value={text} onChange={e => setText(e.target.value)}/></label><button disabled={disabled || busy} onClick={() => void run()}>{busy ? '요청 중…' : '작업 실행 →'}</button><ErrorNotice error={error}/>{result !== undefined && <Json value={result}/>}</section>;
}
function SearchResults({ data, onAsset }: { data: unknown; onAsset: (url: string) => void }) {
  return <div className="search-results">{rows(data).map((item, i) => <article className="job" key={String(item.id || i)}><h3>{String(item.id || '장면 ID 없음')}</h3><p className="muted">관측일 {String(item.datetime || '미제공')} · 운량 {item.cloud_cover == null ? '미제공' : `${item.cloud_cover}%`}</p><div className="button-row">{Object.entries(obj(item.assets)).map(([key, raw]) => { const asset = obj(raw); return typeof asset.href === 'string' ? <button key={key} className="secondary" onClick={() => onAsset(String(asset.href))}>{String(asset.title || key)} URL 선택</button> : null; })}</div></article>)}</div>;
}
function ConnectionSettings({ onChange }: { onChange: () => void }) {
  const [token, setToken] = useState('');
  const [saved, setSaved] = useState(false);
  return <details id="sdss-connection-settings" className="panel"><summary>서버 연결 설정 · {API_BASE}</summary><p className="muted">공유 서버에 GEOAI_API_TOKEN을 설정한 경우에만 입력합니다. 토큰은 현재 탭의 세션에 보관됩니다.</p><label>API 토큰<input type="password" autoComplete="off" value={token} onChange={e => { setToken(e.target.value); setSaved(false); }}/></label><button className="secondary" onClick={() => { if (token) sessionStorage.setItem('geoai_token', token); else sessionStorage.removeItem('geoai_token'); setToken(''); setSaved(true); onChange(); }}>토큰 적용 / 빈 값으로 해제</button>{saved && <p role="status" className="muted">토큰 설정을 적용했습니다.</p>}</details>;
}
function ResourceList({ title, data, error }: { title: string; data: unknown; error?: string }) { const list = rows(data); return <section className="panel"><h2>{title}</h2><ErrorNotice error={error || ''}/>{data === undefined ? <p className="empty">아직 응답이 없습니다. 서버 연결 후 새로고침하세요.</p> : list.length ? list.map((row, i) => <details className="job" key={String(row.id || i)}><summary><strong>{String(row.name || row.model_name || row.id || `항목 ${i + 1}`)}</strong><span className="pill">{String(row.status || row.type || '등록됨')}</span></summary><Json value={row}/></details>) : <><p className="empty">표시할 등록 항목이 없습니다.</p><details><summary>원본 응답 확인</summary><Json value={data}/></details></>}</section>; }
