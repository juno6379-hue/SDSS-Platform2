import {useEffect,useRef,useState} from 'react';
import {agentApi} from './api';
import {Icon} from './Icon';
import {WorkflowModelRecordFlight,prepareWorkflowModelRecord,modelRecordOuterLabels,modelRecordStatusLabels,modelRecordBindingLabels} from './workflowModelRecordHandoffAdapter';
import type {WorkflowModelRecordExpectation,WorkflowModelRecordResult} from './workflowModelRecordHandoffAdapter';
import {provenanceStatusLabels} from './modelRegistrationProvenanceAdapter';
import './workflow-model-record-handoff.css';

export default function WorkflowModelRecordHandoff({planJson,executionRevision}:{planJson:string;executionRevision:number}){
  const [nodeId,setNodeId]=useState(''),[jobText,setJobText]=useState(''),[recordText,setRecordText]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const [view,setView]=useState<{identity:string;route:string;request:WorkflowModelRecordExpectation;result:WorkflowModelRecordResult}>();
  const flight=useRef(new WorkflowModelRecordFlight());
  const identity=JSON.stringify([planJson,executionRevision,nodeId,jobText,recordText]);
  const currentIdentity=useRef(identity);currentIdentity.current=identity;
  function clear(){flight.current.invalidate();setBusy(false);setError('');setView(undefined);}
  useEffect(()=>{clear();window.addEventListener('popstate',clear);window.addEventListener('hashchange',clear);return()=>{flight.current.invalidate();window.removeEventListener('popstate',clear);window.removeEventListener('hashchange',clear);};},[identity]);
  async function inspect(){
    if(busy||!nodeId||!jobText)return;
    const route=window.location.hash;
    setView(undefined);setError('');setBusy(true);
    await flight.current.inspect(identity,route,{
      prepare:()=>prepareWorkflowModelRecord(planJson,nodeId,jobText,recordText),
      post:request=>agentApi('/v1/workflows/full-job-model-record-handoff',request),
      current:()=>({identity:currentIdentity.current,route:window.location.hash}),
      result:(request,result)=>setView({identity,route,request,result}),failure:setError,settled:()=>setBusy(false),
    });
  }
  const visible=view?.identity===identity&&view.route===window.location.hash?view:undefined;
  const r=visible?.result,m=r?.model_reference_comparison;
  return <details className="workflow-model-record-handoff"><summary><Icon name="compare" size={20}/>모델 레코드 초안 대조</summary><section aria-label="Workflow 모델 레코드 초안 대조"><h3><Icon name="clipboard" size={22}/>완성 Job 참조와 사용자 모델 레코드 대조</h3><p>위 Workflow와 명시 선택 노드의 입력 전달을 먼저 검사한 뒤, 사용자가 제공한 레코드와 모델 참조 메타데이터만 비교합니다. 기존 완성 Job 검토와 독립적입니다.</p><label>모델 대조 선택 노드 ID<input value={nodeId} onChange={e=>{clear();setNodeId(e.target.value);}} spellCheck={false} placeholder="node_id를 직접 입력"/></label><label>모델 대조용 완성 Job JSON 원문<textarea value={jobText} onChange={e=>{clear();setJobText(e.target.value);}} spellCheck={false} placeholder="model_ref 등을 포함한 사용자 Job JSON 원문"/></label><label>사용자 모델 레코드 JSON 원문 (선택)<textarea value={recordText} onChange={e=>{clear();setRecordText(e.target.value);}} spellCheck={false} placeholder="빈 입력은 미제공 · null 원문도 그대로 전달"/></label><p>입력을 완전히 비우면 레코드를 제공하지 않습니다. 공백만 입력하면 원문을 보내며 서버가 JSON 오류로 처리합니다. null 원문은 미제공 관측이며 DB 미발견을 뜻하지 않습니다. 모델을 조회·선택·추정하거나 자동 채우지 않습니다.</p><div className="wmr-actions"><button type="button" disabled={busy||!nodeId||!jobText} onClick={()=>void inspect()}><Icon name="search" size={18}/>{busy?'모델 레코드 초안 대조 중…':'모델 레코드 초안 대조 실행'}</button>{busy&&<button type="button" className="secondary" onClick={clear}>모델 대조 응답 표시 중단</button>}<span>명시 클릭만 POST · Job 생성·실행 없음</span></div>{error&&<p className="wmr-warning" role="alert">{error}</p>}{r&&<div className="wmr-result"><p role="status" className="wmr-warning"><strong>{modelRecordOuterLabels[r.status]}</strong></p><dl><div><dt>기존 입력 전달 검사</dt><dd>{r.full_job_comparison.status==='MATCH'?'입력 선언 일치':'입력 전달 차단'}</dd></div><div><dt>모델 identity 추출</dt><dd>{r.identity_projection_performed?'명시 추출 수행':'미실행'}</dd></div><div><dt>모델 대조 호출</dt><dd>{r.model_comparison_calls}회</dd></div></dl>{r.full_job_comparison.issues.map(i=><p key={i.code}>입력 전달 진단 <code>{i.code}</code></p>)}{m&&<><h4>제공 레코드 대조 결과</h4><p className="wmr-warning">{modelRecordStatusLabels[m.status]}</p><dl><div><dt>모델 ID 관계</dt><dd>{modelRecordBindingLabels[m.bindings.id]}</dd></div><div><dt>모델 버전 관계</dt><dd>{modelRecordBindingLabels[m.bindings.version]}</dd></div><div><dt>체크포인트 SHA 관계</dt><dd>{modelRecordBindingLabels[m.bindings.sha256]}</dd></div></dl><p>등록 선언 관측 호출 {m.inspection_calls}회 · {m.record_provenance?provenanceStatusLabels[m.record_provenance.status]:'등록 선언 관측 미실행'}</p>{m.issue&&<p>고정 진단 <code>{m.issue.code}</code> · <code>{m.issue.field}</code> · <code>{m.issue.side}</code></p>}</>}<details><summary>요청 결합 해시와 기존 검사 해시</summary><p>새 요청 전체 RAW SHA <code>{visible?.request.requestDigest}</code></p><p>기존 4필드 검사 결합 SHA <code>{visible?.request.base.requestDigest}</code></p><p>서버 완성 Job 관측 SHA <code>{r.full_job_comparison.full_job_request_sha256??'미확인'}</code></p></details></div>}<p>항상 미검증: 기관 권위·실제 파일 바이트·실행 승인·과학 정확도·모델 인증. OBSERVED는 대조 수행이며 일치나 승인이 아닙니다. SHA는 입력·응답 결합 관측이며 원본 인증이 아닙니다. URI 형식은 해결·권위 검증이 아니며 실제 resolver·Registry·파일 조회는 연결하지 않습니다. 표시 중단·이동은 서버 처리 취소가 아닙니다. 기존 schema 파일 읽기는 미계측 null이며 전체 파일 I/O 0으로 해석하지 않습니다.</p></section></details>;
}
