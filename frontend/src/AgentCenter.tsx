import { useEffect, useRef, useState } from 'react';
import { api, agentApi, ApiError, downloadAgentAsset, readAgentGeoJSON } from './api';
import { pendingIntegration, readinessAxes, isMockOnly, evidenceIdentity, sdssPublicationAllowed } from './integrationAdapter';
import type { EvidenceRecord, ReadinessRecord } from './integrationAdapter';
import { InputDiagnostics, DiagnosticOriginal } from './InputDiagnostics';
import { diagnosticText, safeDiagnosticJson, jobSnapshotView, isCurrentJobLookup } from './inputDiagnosticsAdapter';
import type { JobSnapshotView } from './inputDiagnosticsAdapter';
import JobLineageDiagnostics from './JobLineageDiagnostics';
import ReadinessSourceIdentityDiagnostics from './ReadinessSourceIdentityDiagnostics';
import CandidateQaComparisonDiagnostics from './CandidateQaComparisonDiagnostics';
import {candidateQaMountKey} from './candidateQaComparisonAdapter';
import StoredExecutionBindingCapture from './StoredExecutionBindingCapture';
import {storedBindingMountKey} from './storedExecutionBindingCaptureAdapter';

export default function AgentCenter({ tools, models, jobs, onNavigate, onStandardLayer }: { tools: EvidenceRecord[]; models: EvidenceRecord[]; jobs: EvidenceRecord[]; onNavigate: (step: number) => void; onStandardLayer?: (geo: unknown, bounds?: [number,number,number,number]) => void }) {
  const [selected, setSelected] = useState('lcluc');
  const [modelId, setModelId] = useState('');
  const [review, setReview] = useState<ReadinessRecord>();
  const [dataset, setDataset] = useState<boolean | null>(null);
  const [error, setError] = useState('');
  const [agents, setAgents] = useState<EvidenceRecord[]>([]);
  const [agentId, setAgentId] = useState('');
  const [agentReadiness, setAgentReadiness] = useState<EvidenceRecord>();
  const [standardError, setStandardError] = useState('');
  const [standardJobId, setStandardJobId] = useState('');
  const [standardJob, setStandardJob] = useState<EvidenceRecord>();
  const [inputResolution, setInputResolution] = useState<unknown>();
  const [snapshotView, setSnapshotView] = useState<JobSnapshotView>();
  const [jobLoading, setJobLoading] = useState(false);
  const jobRequestGeneration=useRef(0);
  useEffect(()=>()=>{jobRequestGeneration.current+=1;},[]);
  // 입력·Agent 변경은 진행 중인 응답의 세대를 무효화하고 이전 기록을 즉시 지운다.
  function clearJobView() {
    jobRequestGeneration.current+=1;setStandardJob(undefined);setInputResolution(undefined);setSnapshotView(undefined);setStandardResult(undefined);setSdss(undefined);setJobLoading(false);
  }
  async function lookupStandardJob() {
    const id=standardJobId.trim();if(!id)return;
    clearJobView();const generation=jobRequestGeneration.current;setStandardError('');setJobLoading(true);
    const [statusResult,snapshotResult]=await Promise.allSettled([
      agentApi<EvidenceRecord>(`/v1/jobs/${encodeURIComponent(id)}`),
      agentApi<EvidenceRecord>(`/v1/jobs/${encodeURIComponent(id)}/input-resolution`),
    ]);
    if(generation!==jobRequestGeneration.current)return;
    setJobLoading(false);
    if(statusResult.status==='rejected'){setStandardError(diagnosticText(String(statusResult.reason)));return;}
    const job=statusResult.value;
    if(!isCurrentJobLookup(generation,jobRequestGeneration.current,id,job.job_id)){setStandardError('요청 Job ID와 조회된 상태가 일치하지 않습니다.');return;}
    setStandardJob(job);
    if(snapshotResult.status==='rejected'){
      const error=snapshotResult.reason;
      setSnapshotView(error instanceof ApiError&&error.status===404?{state:'NOT_FOUND',message:'입력 기록 조회가 HTTP404입니다. Job 상태 조회 성공과 별도로, 기록이 없거나 이 API가 지원되지 않는지 확인해야 합니다.'}:{state:'ERROR',message:'입력 기록을 조회하지 못했습니다. Job 상태 조회 성공을 입력 기록 확인으로 해석하지 않습니다.'});return;
    }
    const view=jobSnapshotView(snapshotResult.value,id,String(job.trace_id||''));setSnapshotView(view);
    if(view.state==='RECORDED')setInputResolution(view.snapshot);
  }
  const [standardResult, setStandardResult] = useState<EvidenceRecord>();
  const [sdss, setSdss] = useState<EvidenceRecord>();
  const [submission, setSubmission] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  // 활성 Job만 폴링하며 선택 변경·화면 이탈 시 타이머를 해제한다.
  useEffect(() => {
    if(!standardJob?.job_id || !['CREATED','VALIDATING','QUEUED','RUNNING'].includes(String(standardJob.status))) return;
    let active=true;const generation=jobRequestGeneration.current;
    const timer=window.setInterval(()=>{agentApi<EvidenceRecord>(`/v1/jobs/${encodeURIComponent(String(standardJob.job_id))}`).then(value=>{if(active&&isCurrentJobLookup(generation,jobRequestGeneration.current,String(standardJob.job_id),value.job_id))setStandardJob(value);}).catch(e=>{if(active&&generation===jobRequestGeneration.current)setStandardError(String(e));});},2500);
    return ()=>{active=false;window.clearInterval(timer);};
  },[standardJob?.job_id, standardJob?.status]);
  async function submitStandard() {
    clearJobView();const generation=jobRequestGeneration.current;setSubmitting(true);setStandardError('');
    try {
      const payload:unknown=JSON.parse(submission);
      if(!payload||Array.isArray(payload)||typeof payload!=='object')throw new Error('실제 계약에 맞는 JSON 객체를 입력하세요.');
      const job=await agentApi<EvidenceRecord>(`/v1/agents/${encodeURIComponent(agentId)}/jobs`,payload,requestKey);
      if(generation!==jobRequestGeneration.current)return;
      setStandardJob(job);setStandardJobId(String(job.job_id||''));setInputResolution(job.input_resolution);
    }catch(e){
      if(generation!==jobRequestGeneration.current)return;
      if(e instanceof ApiError && e.data && typeof e.data==='object') {
        const body=e.data as {error?:{details?:{job_id?:string;job_status?:EvidenceRecord;input_resolution?:unknown}}};
        setInputResolution(body.error?.details?.input_resolution);
        if(body.error?.details?.job_id){setStandardJobId(body.error.details.job_id);setStandardJob(body.error.details.job_status);}
      }
      setStandardError(e instanceof ApiError ? `HTTP ${e.status}: ${JSON.stringify(safeDiagnosticJson(e.data))}` : diagnosticText(String(e)));
    }finally{setSubmitting(false);}
  }

  const [registryRefresh, setRegistryRefresh] = useState(0);
  const [standardCapabilities, setStandardCapabilities] = useState<unknown>();
  const [standardLoading, setStandardLoading] = useState(true);
  useEffect(() => {
    let active = true; setStandardLoading(true); setStandardError(''); setAgents([]); setAgentReadiness(undefined);
    agentApi<unknown>('/v1/agents').then(value => {
      const rows = Array.isArray(value) ? value : value && typeof value === 'object' && 'items' in value && Array.isArray(value.items) ? value.items : value && typeof value === 'object' && 'agents' in value && Array.isArray(value.agents) ? value.agents : [];
      if (active) setAgents(rows as EvidenceRecord[]);
    }).catch(e => {if (active) {setAgents([]);setStandardError(String(e));}}).finally(() => {if (active) setStandardLoading(false);});
    return () => {active = false;};
  }, [registryRefresh]);
  useEffect(() => {
    let active = true; setAgentReadiness(undefined); setStandardCapabilities(undefined);
    if (agentId) agentApi<EvidenceRecord>(`/v1/agents/${encodeURIComponent(agentId)}/readiness`).then(value => {if (active) setAgentReadiness(value);}).catch(e => {if (active) setStandardError(String(e));});
    if (agentId) agentApi(`/v1/agents/${encodeURIComponent(agentId)}/capabilities`).then(value => {if (active) setStandardCapabilities(value);}).catch(e => {if (active) setStandardError(String(e));});
    return () => {active = false;};
  }, [agentId,registryRefresh]);
  const tool = tools.find(row => row.id === selected);
  const model = models.find(row => row.id === modelId);
  useEffect(() => {
    let active = true;
    api<{training_readiness?: {ready_for_training?: boolean}}>('/data/collection-status').then(result => {
      if (active) setDataset(typeof result.training_readiness?.ready_for_training === 'boolean' ? result.training_readiness.ready_for_training : null);
    }).catch(e => { if (active) { setDataset(null); setError(String(e)); } });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true; setReview(undefined);
    if (modelId && selected === 'lcluc') api<ReadinessRecord>(`/models/${encodeURIComponent(modelId)}/readiness`).then(value => { if (active) setReview(value); }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [modelId, selected]);
  return <section className="panel"><span className="eyebrow">AGENT CENTER · COMPATIBILITY VIEW</span><h2>모델 Agent 준비 상태</h2>
    <p className="hint">실제로 확보한 GMAIS v0.2 내부 제안 OpenAPI의 /v1과 기존 /api 호환 정보를 구분합니다. 컨소시엄/BIG 확정 표준이나 과학적 검증 완료라는 뜻은 아닙니다.</p>
    <h3>표준 /v1 Agent Registry</h3><p className="help">Agent readiness와 모델 승인 상태는 별도입니다. 실제 응답이 없으면 연결 성공으로 표시하지 않습니다.</p>
    <button className="secondary" onClick={() => setRegistryRefresh(old => old + 1)}>표준 Registry 재조회</button>
    <label>표준 Agent 선택<select value={agentId} onChange={e => {clearJobView();setAgentId(e.target.value);setAgentReadiness(undefined);setStandardError('');setSdss(undefined);setStandardResult(undefined);}}><option value="">Agent 선택</option>{agents.map(row => <option key={String(row.agent_id)} value={String(row.agent_id)}>{String(row.agent_id)} · {String(row.readiness)} · 모델 {String(row.model_approval_status || '미제공')}</option>)}</select></label>
    {standardLoading && <p role="status" className="help">표준 Agent Registry 조회 중…</p>}
    {!standardLoading && !agents.length && <p className="empty">등록 Agent 응답 없음 · 아래 기존 Toolbox를 표준 Agent 연결 성공으로 해석하지 않습니다.</p>}
    {agentReadiness && <><p className="hint">Agent {String(agentReadiness.agent_id || agentId)} · 준비도 {String(agentReadiness.readiness)} · 모델 승인 {String(agentReadiness.model_approval_status || '미제공')}</p><pre className="json">{JSON.stringify(agentReadiness,null,2)}</pre></>}
    {standardCapabilities !== undefined && <details><summary>선택 Agent의 실제 Capability</summary><pre className="json">{JSON.stringify(standardCapabilities,null,2)}</pre></details>}
    <details className="panel"><summary>표준 Job 제출 · 승인·준비도 조건부</summary><p className="help">READY Agent만 제출할 수 있습니다. 실제 고정 데이터·모델 참조, AOI·Trace를 포함한 계약 JSON을 입력하세요. 동일 요청의 재시도는 멱등 키를 유지합니다.</p><label>요청 JSON<textarea className="editor" value={submission} placeholder="실제 /v1 계약 JSON" onChange={e=>{setSubmission(e.target.value);setRequestKey(crypto.randomUUID());}}/></label><button disabled={submitting || agentReadiness?.readiness !== 'READY' || !submission.trim()} onClick={()=>void submitStandard()}>{submitting?'제출 중…':'승인된 Agent에 Job 제출'}</button>{agentReadiness?.readiness !== 'READY' && <p className="readiness-warning">BLOCKED · 선택한 Agent가 READY 상태가 아닙니다.</p>}</details>
    <label>표준 Job ID<input autoComplete="off" spellCheck={false} name="standard-job-id" value={standardJobId} onChange={e => {clearJobView();setStandardError('');setStandardJobId(e.target.value);}} placeholder="실제 발급된 job_id"/></label><button className="secondary" disabled={!standardJobId.trim()||jobLoading} onClick={()=>void lookupStandardJob()}>{jobLoading?'Job·입력 기록 조회 중…':'Job·Trace·입력 기록 실제 조회'}</button>
    {standardJob && <p className="hint">Job {String(standardJob.job_id)} · {String(standardJob.status)} · Trace {String(standardJob.trace_id || '미제공')}</p>}
    {standardJob && <DiagnosticOriginal value={standardJob} label="Job 상태 원본 JSON · 민감 경로 제외"/>}
    {snapshotView && <div className={snapshotView.state==='RECORDED'?'hint':'readiness-warning'} role="status"><strong>제출 시점 입력 기록 · {snapshotView.state}</strong><p>{snapshotView.message}</p>{snapshotView.wrapper!==undefined&&<DiagnosticOriginal value={snapshotView.wrapper} label="입력 기록 조회 원본 · 민감 경로 제외"/>}</div>}
    {inputResolution !== undefined && <InputDiagnostics value={inputResolution} title="Job 제출 시점 고정 입력 진단"/>}
    {standardJob && inputResolution === undefined && !snapshotView && <p className="help">제출 시점 입력 기록이 아직 확인되지 않았습니다. 진단이 없는 상태를 통과로 해석하지 않습니다.</p>}
    <StoredExecutionBindingCapture key={storedBindingMountKey(`${selected}:${modelId}:${agentId}:${standardJobId}:${jobRequestGeneration.current}:${registryRefresh}`)} jobId={standardJobId}/>
    {standardJob && standardJob.job_id===standardJobId.trim() && <JobLineageDiagnostics key={`${standardJob.job_id}:${String(standardJob.trace_id||'')}:${jobRequestGeneration.current}`} jobId={String(standardJob.job_id)} traceId={String(standardJob.trace_id||'')}/>}
    {standardJob && <button className="secondary" disabled={!['CREATED','VALIDATING','QUEUED','RUNNING'].includes(String(standardJob.status))} onClick={async () => {const generation=jobRequestGeneration.current;const id=String(standardJob.job_id);setStandardError('');try {const value=await agentApi<EvidenceRecord>(`/v1/jobs/${encodeURIComponent(id)}/cancel`,{});if(!isCurrentJobLookup(generation,jobRequestGeneration.current,id,value.job_id))return;setStandardJob(value);setStandardResult(undefined);}catch(e){if(generation===jobRequestGeneration.current)setStandardError(String(e));}}}>이 Job의 취소 요청</button>}
    {standardJob && <button className="secondary" disabled={standardJob.status !== 'SUCCEEDED'} onClick={async () => {const generation=jobRequestGeneration.current;const id=String(standardJob.job_id);setStandardError('');setStandardResult(undefined);setSdss(undefined);try {const result=await agentApi<EvidenceRecord>(`/v1/jobs/${encodeURIComponent(id)}/results`);if(!isCurrentJobLookup(generation,jobRequestGeneration.current,id,result.job_id))return;const projection=await agentApi<EvidenceRecord>(`/v1/results/${encodeURIComponent(String(result.result_id))}/sdss`);if(generation!==jobRequestGeneration.current)return;setStandardResult(result);setSdss(projection);}catch(e){if(generation===jobRequestGeneration.current)setStandardError(String(e));}}}>동일 Job의 실제 Result 조회</button>}
    {standardResult && standardResult.job_id === standardJob?.job_id && <><p className="hint">Result {String(standardResult.result_id)} · 과학적 상태 {String(standardResult.status)}</p>{isMockOnly(standardResult) ? <p className="readiness-warning">MOCK_ONLY · 의사결정 지도·보고서 게시 차단</p> : <><pre className="json">{JSON.stringify(evidenceIdentity(standardResult),null,2)}</pre><p className="help">서버에서 Result 식별자·Trace·고정 버전·자산 SHA를 검증하여 게시 가능 여부를 판정합니다.</p></>}</>}
    {sdss && standardResult && standardJob && <section className="panel"><h3>표준 Result → SDSS 게시 검증</h3><p className={sdssPublicationAllowed(sdss,standardResult,standardJob)?'hint':'readiness-warning'}>{sdssPublicationAllowed(sdss,standardResult,standardJob)?'검증된 Result · 자산 열람 가능':'게시 차단 · 서버 차단 근거와 식별자 확인 필요'}</p><pre className="json">{JSON.stringify(sdss,null,2)}</pre>{sdssPublicationAllowed(sdss,standardResult,standardJob) && Array.isArray(sdss.assets) && (sdss.assets as EvidenceRecord[]).map((asset,index)=><button key={index} className="secondary" disabled={typeof asset.href !== 'string'} onClick={async()=>{try{await downloadAgentAsset(String(asset.href),String(asset.name||`result-asset-${index}`));}catch(e){setStandardError(String(e));}}}>{String(asset.name||asset.type||`검증 자산 ${index+1}`)} 내려받기</button>)}{sdssPublicationAllowed(sdss,standardResult,standardJob) && Array.isArray(sdss.layers) && (sdss.layers as EvidenceRecord[]).filter(layer=>layer.type==='GeoJSON').map((layer,index)=><button className="secondary" key={'layer'+index} onClick={async()=>{try{const geo=await readAgentGeoJSON(String(layer.href));const spatial=layer.spatial as {bbox?:unknown};const bounds=Array.isArray(spatial?.bbox)&&spatial.bbox.length===4&&spatial.bbox.every(v=>typeof v==='number'&&Number.isFinite(v))?spatial.bbox as [number,number,number,number]:undefined;onStandardLayer?.(geo,bounds);}catch(e){setStandardError(String(e));}}} disabled={!onStandardLayer}>검증 GeoJSON을 WebGIS에 표시</button>)}</section>}
    {standardError && <p className="error" role="alert">{diagnosticText(standardError)}</p>}
    <h3>기존 LCLUC 실행·모델 호환 정보</h3>
    {!tools.length && <p className="empty">서버 Toolbox 목록이 없습니다. Agent 연결 상태를 추정하지 않습니다.</p>}
    <div className="agent-grid">{tools.map(row => <button key={String(row.id)} className={selected === row.id ? 'agent-card selected' : 'agent-card secondary'} onClick={() => { setSelected(String(row.id)); setModelId(''); setError(''); }}><strong>{String(row.id)}</strong><span>{row.implemented === true ? 'LCLUC 기존 실행 코드' : '외부 모델 연결 대기'}</span><small>{String(row.status || '상태 미제공')}</small></button>)}</div>
    {tool && <><h3>{String(tool.id)} 검토</h3>{tool.implemented === true ? <><label>검토할 등록 모델<select value={modelId} onChange={e => setModelId(e.target.value)}><option value="">모델 선택 · 미선택 상태는 미검증</option>{models.map(row => <option value={String(row.id)} key={String(row.id)}>{String(row.id)} · {String(row.status)}</option>)}</select></label><div className="readiness-axes">{readinessAxes(tool, dataset, model, review).map(axis => <article key={axis.id}><strong>{axis.label}</strong><code>{axis.state}</code><p>{axis.detail}</p></article>)}</div>{review?.blockers?.length ? <div className="readiness-warning">{review.blockers.map((value, i) => <p key={i}>{typeof value === 'string' ? value : JSON.stringify(value)}</p>)}</div> : null}<div className="button-row"><button onClick={() => onNavigate(0)}>실제 데이터 준비도 확인</button><button className="secondary" onClick={() => onNavigate(6)}>모델 승인·배포 검토</button><button className="secondary" onClick={() => onNavigate(4)}>기존 공간 추론 입력</button></div></>
    : <p className="readiness-warning">BLOCKED · 외부 기관 모델 Adapter·실행 이미지·검증 증거가 연결되지 않았습니다. 이 모델의 실행·결과 지도·성과를 생성하지 않습니다.</p>}
    <details><summary>서버 Toolbox 원본 계약</summary><pre className="json">{JSON.stringify(tool, null, 2)}</pre></details></>}
    {selected==='lcluc'&&<ReadinessSourceIdentityDiagnostics key={`${selected}:${modelId}:${agentId}:${standardJobId}:${registryRefresh}`}/>}
    {selected==='lcluc'&&<CandidateQaComparisonDiagnostics key={candidateQaMountKey(`${selected}:${modelId}:${agentId}:${standardJobId}:${registryRefresh}`)}/>}
    <h3>실제 Job 상태·Trace</h3><p className="help">기존 작업 목록입니다. 공통 Orchestrator DAG·재시도·권한별 Trace API는 아직 연결되지 않았습니다.</p>
    {jobs.length ? <div className="table-scroll"><table className="inventory-table"><thead><tr><th>Job ID</th><th>상태</th><th>실패·차단 근거</th><th>Trace ID</th></tr></thead><tbody>{jobs.map(row => <tr key={String(row.id)}><td><code>{String(row.id)}</code></td><td>{String(row.status)}</td><td>{row.error ? JSON.stringify(row.error) : '서버 오류 기록 없음'}</td><td>{String(row.trace_id || '미제공')}</td></tr>)}</tbody></table></div> : <p className="empty">등록된 작업이 없습니다.</p>}
    <details><summary>미연결 공통 Adapter 요구 계약</summary><pre className="json">{JSON.stringify(pendingIntegration, null, 2)}</pre></details>
    <details><summary>거버넌스·운영 화면의 남은 범위</summary><p className="help">토큰 기반 API 연결과 기존 모델 검토 gate를 사용합니다. 기관별 로그인·RBAC 화면, RDTR/RTRW 근거 검토, 이의제기·전문가 Feedback, 운영 롤백·지원 기록 API는 아직 연결되지 않았습니다.</p><button className="secondary" disabled>Feedback API 미연결</button><button className="secondary" disabled>운영 롤백 API 미연결</button></details>
    {error && <p role="alert" className="error">{error}</p>}
  </section>;
}
