import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import { Icon } from './Icon';
import ModelRegistrationProvenance from './ModelRegistrationProvenance';
import ModelErrorAnalysis from './ModelErrorAnalysis';
import AnnualInputDiagnostics from './AnnualInputDiagnostics';
import CollectionProgress from './CollectionProgress';
import './model-version-registration.css';
import { ModelRegistrationFlight, modelRegistrationBody, modelVersionIssue } from './modelVersionRegistrationAdapter';
type Row = Record<string, unknown>;
type Job = { id: string; status: string; result?: unknown; error?: unknown };
type Readiness = { model_id: string; status: string; evaluation_kind?: string; independent_evaluation?: boolean; checkpoint_integrity?: { matched?: boolean }; allowed_transitions?: string[]; can_deploy?: boolean; blockers?: unknown[]; evaluation_pending?: boolean };
function object(value: unknown): Row { return value && typeof value === 'object' && !Array.isArray(value) ? value as Row : {}; }
function percent(value: unknown) { return typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : '미확인'; }
function text(value: unknown) { return typeof value === 'string' ? value : JSON.stringify(value); }
export default function ModelReview({ models, onJob, onChanged, onInference }: { models: Row[]; onJob: (job: Job) => void; onChanged: () => Promise<void>; onInference: (id: string) => void }) {
  const [id, setId] = useState('');
  const [readiness, setReadiness] = useState<Readiness>();
  const [target, setTarget] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reportPath, setReportPath] = useState('');
  const [explicitVersion, setExplicitVersion] = useState(false);
  const [modelVersion, setModelVersion] = useState('');
  const registration = useRef(new ModelRegistrationFlight());
  const registering = useRef(false);
  const versionIssue = explicitVersion ? modelVersionIssue(modelVersion) : '';
  useEffect(() => {
    const clear = () => { registration.current.invalidate(); if (registering.current) { registering.current = false; setBusy(false); setError(''); } };
    window.addEventListener('popstate', clear); window.addEventListener('hashchange', clear);
    return () => { registration.current.invalidate(); window.removeEventListener('popstate', clear); window.removeEventListener('hashchange', clear); };
  }, []);
  const [evaluation, setEvaluation] = useState(JSON.stringify({ image_path: '', label_path: '', output_id: 'independent-evaluation', reference_kind: 'expert_independent', label_provenance: '', reviewer: '', group: '' }, null, 2));
  const model = models.find(row => row.id === id);
  const metrics = object(model?.test_metrics);
  const classNames = Array.isArray(model?.class_names) ? model.class_names : Array.isArray(metrics.class_names) ? metrics.class_names : [];
  // 화면 추정으로 승인하지 않는다. 현재 가중치 해시에 대해 서버가 허용한 전이만 노출한다.
  const allowed = readiness?.allowed_transitions || [];
  async function load() {
    const result = await api<Readiness>(`/models/${encodeURIComponent(id)}/readiness`);
    setReadiness(result); setTarget('');
  }
  useEffect(() => {
    setReadiness(undefined); setTarget(''); setError('');
    if (!id) return;
    let active = true;
    api<Readiness>(`/models/${encodeURIComponent(id)}/readiness`).then(data => { if (active) setReadiness(data); }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [id, models]);
  async function run(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); await onChanged(); await load(); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function register() {
    if (busy || registering.current || !reportPath.trim() || versionIssue) return;
    const body = modelRegistrationBody(reportPath, explicitVersion, modelVersion);
    registering.current = true; setBusy(true); setError('');
    await registration.current.submit(body, window.location.hash, {
      post: body => api<Row>('/models/register-experiment', body),
      refresh: onChanged,
      route: () => window.location.hash,
      success: setId,
      failure: setError,
      settled: () => { registering.current = false; setBusy(false); },
    });
  }
  return <section className="panel"><span className="eyebrow">REGISTRY → REVIEW → DEPLOY</span><h2>실제 모델의 검증·배포 검토</h2><CollectionProgress/><details className="model-version-registration"><summary>실제 완료 실험 보고서로 Draft 등록</summary><p className="help">서버 데이터 루트 안의 완료 보고서 경로를 입력하세요. 서버가 데이터 버전과 체크포인트 해시를 검증해 Draft로만 등록합니다. 기존 모델 ID를 덮어쓰거나 승인 상태를 지정하지 않습니다.</p><label>완료 보고서 경로<input disabled={busy} value={reportPath} onChange={e => setReportPath(e.target.value)} placeholder="results/실험ID/experiment.json"/></label><label className="model-version-option"><span><input type="checkbox" disabled={busy} checked={explicitVersion} onChange={e => setExplicitVersion(e.target.checked)}/> 모델 버전 선언 추가 (선택)</span></label>{explicitVersion && <><label>명시할 모델 버전<input disabled={busy} value={modelVersion} onChange={e => setModelVersion(e.target.value)} autoComplete="off" aria-describedby="model-version-help model-version-issue"/></label>{versionIssue && <p id="model-version-issue" role="status" className="help">{versionIssue}</p>}</>}<p id="model-version-help" className="help">버전 선언은 입력자의 메타데이터입니다. 기관 권위·원본 인증이나 과학·실행 승인을 뜻하지 않으며, 같은 모델 또는 데이터 ID의 중복 등록은 계속 거부됩니다. 화면 이동은 서버 등록의 취소나 되돌리기가 아닙니다.</p><button className="secondary" style={{display:'inline-flex',alignItems:'center',gap:6}} disabled={busy || !reportPath.trim() || !!versionIssue} onClick={() => void register()}><Icon name="clipboard" size={18}/>출처 검증 후 Draft 등록</button></details><label>등록 모델<select disabled={busy} value={id} onChange={e => setId(e.target.value)}><option value="">모델을 선택하세요</option>{models.map(row => <option value={String(row.id)} key={String(row.id)}>{String(row.name || row.id)} · {String(row.status || '미확인')}</option>)}</select></label>{!models.length && <p className="empty">등록 모델이 없습니다. 실제 학습이 완료되면 새로고침하세요.</p>}<AnnualInputDiagnostics key={'annual-input:'+id} model={model}/>{model && <><ModelRegistrationProvenance key={id} modelId={id}/><ModelErrorAnalysis key={'errors:'+id} model={model}/><p className="hint">상태 {String(model.status)} · {model.independent_evaluation === true ? '독립평가 기록 있음' : '독립평가 미완료·실험 모델'}. weak label 일치도나 합성 시험만으로 승인하지 않습니다.</p><div className="inventory-stats"><span>참조 유형<b style={{fontSize:12}}>{String(model.reference_kind || readiness?.evaluation_kind || '미확인')}</b></span><span>보관 test OA<b>{percent(metrics.overall_accuracy)}</b></span><span>보관 test mIoU<b>{percent(metrics.mean_iou)}</b></span><span>체크포인트 해시<b style={{fontSize:14}}>{readiness?.checkpoint_integrity?.matched === true ? '일치' : readiness?.checkpoint_integrity?.matched === false ? '불일치' : '미확인'}</b></span></div><p className="help">성과 수치는 해당 모델이 기록한 test 참조자료 범위입니다. WorldCover 일치도를 지상 독립 정확도로 해석하지 않습니다. 데이터 버전 {String(model.dataset_version || '미확인')}</p>{Array.isArray(metrics.class_iou) && <div className="table-scroll"><table className="inventory-table"><thead><tr><th>클래스 코드</th><th>IoU</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead><tbody>{metrics.class_iou.map((value, i) => <tr key={i}><td>{i}{typeof classNames[i] === 'string' ? ` · ${classNames[i]}` : ''}</td><td>{percent(value)}</td><td>{percent(Array.isArray(metrics.precision) ? metrics.precision[i] : null)}</td><td>{percent(Array.isArray(metrics.recall) ? metrics.recall[i] : null)}</td><td>{percent(Array.isArray(metrics.f1) ? metrics.f1[i] : null)}</td></tr>)}</tbody></table></div>}<div className="button-row"><button className="secondary" disabled={busy} onClick={() => void run(async () => {})}>검토 가능 상태 다시 조회</button>{model.status === 'Deployed' && <button onClick={() => onInference(id)}>배포 모델로 공간 추론 준비 →</button>}</div>{readiness?.blockers?.length ? <ul className="collection-limitations">{readiness.blockers.map((item, i) => <li key={i}>{text(item)}</li>)}</ul> : null}<label>전이 가능한 상태<select disabled={!allowed.length || busy} value={target} onChange={e => setTarget(e.target.value)}><option value="">서버가 허용한 상태 선택</option>{allowed.map(status => <option key={status} value={status}>{status}</option>)}</select></label><label>검토 근거<input value={reason} autoComplete="off" onChange={e => setReason(e.target.value)} placeholder="평가 결과·책임자 검토 근거"/></label><div className="button-row"><button disabled={busy || !allowed.includes(target) || !reason.trim()} onClick={() => void run(async () => { await api(`/models/${encodeURIComponent(id)}/transition`, {status:target,reason}); })}>검토 상태 전이</button><button className="secondary" disabled={busy || readiness?.can_deploy !== true} onClick={() => void run(async () => { await api(`/models/${encodeURIComponent(id)}/deploy`, {}); })}>검증된 모델 배포</button></div><details style={{marginTop:20}}><summary>전문가 독립 참조자료 평가 요청</summary><p className="help">독립성은 출처·검토자 진술 및 중복 검사를 근거로 합니다. 합성·의사라벨을 독립 정답으로 바꾸어 제출하지 마세요. 평가는 체크포인트 해시에 묶여 보관됩니다. 제품별 정규화 모델은 실제 normalization/source_scene 근거와 모델과 일치하는 label_taxonomy_signature가 추가로 필요합니다.</p><label>평가 JSON<textarea className="editor" spellCheck={false} value={evaluation} onChange={e => setEvaluation(e.target.value)}/></label><button disabled={busy || model.status !== 'Draft' || readiness?.evaluation_pending === true} onClick={() => void run(async () => { const parsed: unknown = JSON.parse(evaluation); if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('JSON 객체가 필요합니다.'); onJob(await api<Job>(`/models/${encodeURIComponent(id)}/evaluate`, parsed)); })}>평가 작업 제출</button></details><details style={{marginTop:18}}><summary>모델 원본 기록·검토 이력</summary><pre className="json">{JSON.stringify(model, null, 2)}</pre></details></>}{error && <div role="alert" className="error">{error}</div>}</section>;
}
