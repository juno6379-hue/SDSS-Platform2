import {useEffect,useRef,useState} from 'react';
import {Icon} from './Icon';
import LclucWorkflowChangeMap from './LclucWorkflowChangeMap';
import {workflowLabels} from './lclucWorkflowAdapter';
import {evidenceWorkflowId,WorkflowEvidenceFlight} from './geollmWorkflowEvidenceAdapter';
import type {WorkflowEvidence} from './geollmWorkflowEvidenceAdapter';
import {readWorkflowEvidence} from './geollmWorkflowEvidenceClient';
import './lcluc-workflow.css';
import './geollm-workflow-evidence.css';

export default function GeoWorkflowEvidence(){
 const [id,setId]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [view,setView]=useState<WorkflowEvidence>(),[review,setReview]=useState(false);
 const current=useRef(id);current.current=id;const flight=useRef(new WorkflowEvidenceFlight());
 function clear(){flight.current.invalidate();setView(undefined);setReview(false);setError('');setBusy(false);}
 useEffect(()=>{
  window.addEventListener('hashchange',clear);window.addEventListener('popstate',clear);
  return()=>{flight.current.invalidate();window.removeEventListener('hashchange',clear);window.removeEventListener('popstate',clear);};
 },[]);
 async function read(){
  if(!evidenceWorkflowId(id)||busy)return;setView(undefined);setReview(false);setError('');setBusy(true);
  await flight.current.run(id,window.location.href,{current:()=>({id:current.current,route:window.location.href}),
   failure:text=>{setView(undefined);setReview(false);setError(text);},settled:()=>setBusy(false),
   work:async(signal,live)=>{const result=await readWorkflowEvidence(id,signal,live);if(result&&live())setView(result);}});
 }
 const receipt=view?.receipt,model=(receipt?.request_snapshot as {model_ref:{id:string;version:string;sha256:string};images:{year:number}[]}|undefined)?.model_ref;
 return <details className="geo-workflow-evidence"><summary><Icon name="report" size={20}/>Local LCLUC workflow 근거 조회</summary>
  <p>완료된 local workflow의 64자리 ID를 직접 입력하세요. 기존 분석 ID와 별도이며 LLM·정책 RAG·새 실행을 연결하지 않습니다.</p>
  <label>Local workflow ID<input value={id} maxLength={64} spellCheck={false} autoComplete="off" placeholder="소문자 0–9, a–f의 64자리 고정 ID" onChange={event=>{clear();setId(event.target.value);current.current=event.target.value;}}/></label>
  {id&&!evidenceWorkflowId(id)&&<p className="gwe-warning">공백 없이 소문자 16진수 64자리를 입력하세요. 분석 ID나 임의 경로를 넣지 않습니다.</p>}
  <div className="gwe-actions"><button type="button" disabled={!evidenceWorkflowId(id)||busy} onClick={()=>void read()}><Icon name="report" size={17}/>{busy?'기록·보고서 읽는 중…':'기록·보고서 읽기'}</button><button type="button" onClick={clear}><Icon name="close" size={17}/>표시 중단·결과 비우기</button></div>
  <p className="gwe-help">인증을 유지하는 수동 GET 조회입니다. 자동 조회·polling·재시도·실행 요청은 없습니다. 표시 중단은 현재 화면의 응답 표시와 전송을 중단하며 서버 실행을 취소하거나 되돌리지 않습니다.</p>
  {error&&<p className="gwe-warning" role="alert">{error}</p>}
  {receipt&&<section className="gwe-result" aria-label="Local workflow 기록 근거"><h3 role="status">{workflowLabels[receipt.status]}</h3>
   <dl><div><dt>Workflow ID</dt><dd><code>{receipt.id}</code></dd></div><div><dt>Trace</dt><dd><code>{receipt.trace_id}</code></dd></div><div><dt>조회 성격</dt><dd>저장된 이력 읽기 · 새 실행·현재 승인 재판정 아님</dd></div></dl>
   {model&&<dl><div><dt>고정 모델 ID</dt><dd>{model.id}</dd></div><div><dt>고정 모델 버전</dt><dd>{model.version}</dd></div><div><dt>체크포인트 SHA</dt><dd><code>{model.sha256}</code></dd></div></dl>}
   {(receipt.status==='RUNNING'||receipt.status==='FAILED')&&<p>완료 보고서를 요청하거나 결과를 생성하지 않았습니다. {receipt.status==='RUNNING'?'실행 중 또는 중단 후 미완료 상태이며 자동 재개하지 않습니다.':'실패 기록이며 자동 재시도하지 않습니다.'}</p>}
   {view.report&&<><p>관측 연도: {view.report.years.join(', ')} · 보고서 원바이트 SHA <code>{view.reportSha}</code></p>
    <div className="gwe-scroll" role="region" aria-label="검증된 변화쌍 요약" tabIndex={0}><table><caption>같은 workflow 보고서의 전체 유효 래스터 변화 요약</caption><thead><tr><th scope="col">변화쌍</th><th scope="col">유효 픽셀</th><th scope="col">변화 면적 (m²)</th></tr></thead><tbody>{view.report.changes.map(change=><tr key={change.pair}><th scope="row">{change.pair}</th><td>{change.validPixels.toLocaleString('ko-KR')}</td><td>{change.area.toLocaleString('ko-KR',{maximumFractionDigits:6})}</td></tr>)}</tbody></table></div>
    <button type="button" onClick={()=>setReview(value=>!value)}><Icon name="map" size={17}/>{review?'지도·행렬 검토 닫기':'동일 workflow 지도·행렬 검토'}</button>
    {review&&view.rawReport!==undefined&&<div className="lcluc-workflow-panel gwe-map-review"><LclucWorkflowChangeMap key={receipt.id+':'+view.reportSha} receipt={receipt} rawReport={view.rawReport} pairs={view.report.changes.map(change=>change.pair)}/></div>}
   </>}
   <p className="gwe-warning">LOCAL_LCLUC_WORKFLOW_ONLY · 과학 정확도 인증 false · 표준 GMAIS Result false. SHA·수치 일관성은 기관 권위·독립 정확도·현재 모델 승인·정책 적합성을 인증하지 않습니다. 지도·행렬은 동일 local workflow 안에서만 검토하며 기존 분석 화면으로 전달하지 않습니다.</p>
  </section>}
 </details>;
}
