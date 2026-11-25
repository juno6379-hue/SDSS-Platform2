import {useEffect,useRef,useState} from 'react';
import {Icon} from './Icon';
import AnalysisIcon from './AnalysisIcon';
import LclucWorkflowChangeMap from './LclucWorkflowChangeMap';
import {WorkflowFlight,parseWorkflowRequest,prepareWorkflow,workflowResponse,workflowSha,workflowLabels,parseWorkflowReport} from './lclucWorkflowAdapter';
import type {WorkflowReceipt,WorkflowReport} from './lclucWorkflowAdapter';
import {workflowFetch,workflowAsset} from './lclucWorkflowClient';
import './lcluc-workflow.css';
export default function LclucWorkflowPanel(){
 const [text,setText]=useState(''),[lookup,setLookup]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [receipt,setReceipt]=useState<WorkflowReceipt>(),[report,setReport]=useState<WorkflowReport>(),[rawReport,setRawReport]=useState<unknown>();
 const flight=useRef(new WorkflowFlight()),identity=JSON.stringify([text,lookup]),current=useRef(identity);current.current=identity;
 function clear(){flight.current.invalidate();setBusy(false);setError('');setReceipt(undefined);setReport(undefined);setRawReport(undefined);}
 useEffect(()=>{clear();window.addEventListener('popstate',clear);window.addEventListener('hashchange',clear);return()=>{flight.current.invalidate();window.removeEventListener('popstate',clear);window.removeEventListener('hashchange',clear);};},[identity]);
 let valid=false;try{parseWorkflowRequest(text);valid=true;}catch{/* No inferred refs. */}
 async function action(kind:'submit'|'lookup'|'report'|'asset',index=0){
  if(busy)return;setBusy(true);setError('');if(kind==='submit'||kind==='lookup'){setReceipt(undefined);setReport(undefined);setRawReport(undefined);}if(kind==='report'){setReport(undefined);setRawReport(undefined);}
  const route=window.location.href;
  await flight.current.run(identity,route,{current:()=>({identity:current.current,route:window.location.href}),settled:()=>setBusy(false),failure:message=>{setError(message);setReport(undefined);if(kind==='submit'||kind==='lookup')setReceipt(undefined);},work:async live=>{
   if(kind==='submit'){const prepared=await prepareWorkflow(text);if(!live())return;const result=await workflowFetch('',prepared.request);if(!live())return;const r=workflowResponse(result.status,result.value,prepared);if(r.trace_id!==prepared.request.trace_id)throw new Error('response identity');setReceipt(r);}
   if(kind==='lookup'){if(!workflowSha(lookup))throw new Error('response identity');const result=await workflowFetch('/'+lookup);if(!live())return;setReceipt(workflowResponse(result.status,result.value,{id:lookup,readOnly:true}));}
   if(kind==='report'&&receipt){const result=await workflowFetch('/'+receipt.id+'/report');if(!live())return;if(result.status!==200){workflowResponse(result.status,result.value,{id:receipt.id});throw new Error('report unavailable');}const parsed=parseWorkflowReport(result.value,receipt);if(!parsed)throw new Error('report invalid');setReport(parsed);setRawReport(result.value);}
   if(kind==='asset'&&receipt&&receipt.artifacts?.[index])await workflowAsset(receipt.id,index,receipt.artifacts[index].path,live);
  }});
 }
 return <details className="lcluc-workflow-panel"><summary><Icon name="network" size={20}/>LCLUC 고정 입력 실행 · 상태와 산출물</summary><section aria-label="LCLUC 로컬 Workflow 실행"><h3><Icon name="play" size={21}/>고정 Registry 입력으로 로컬 시계열 실행</h3><p>현재 모델은 Draft이며 독립 라벨 미확보 상태입니다. Deployed 모델·현재 체크포인트에 결합된 독립 평가·VALIDATED/PUBLIC 연차 자료가 필요합니다. 위 지역·연도 초안에서 요청을 자동 생성하지 않습니다.</p><p className="lwf-warning">global 정규화만 지원합니다. per_scene 공식 제품 정규화·6밴드 제품·구름 mask 연결은 차단/후속입니다. 로컬 완료는 과학 정확도 또는 표준 GMAIS Result 인증이 아닙니다.</p>
 <label>명시 실행 요청 JSON (exact6 · 최대 16KiB)<textarea value={text} onChange={e=>{clear();setText(e.target.value);}} placeholder="schema_version, capability, trace_id, idempotency_key, model_ref(id/version/sha256), images(year/input_ref/quality_report_sha256)를 직접 입력" spellCheck={false}/></label>
 {text&&!valid&&<p className="lwf-warning">고정 모델 ID·버전·SHA와 연차 입력 2~6개를 확인하세요. 빈 값·임의 경로·중복 키·소수·추가 키는 허용하지 않습니다.</p>}
 <div className="lwf-actions"><button type="button" disabled={busy||!valid} onClick={()=>void action('submit')}><Icon name="play" size={17}/>{busy?'요청 처리 중…':'명시 요청 실행'}</button><span>클릭할 때만 POST · 자동 제출·재시도·재개 없음</span></div>
 <label>저장된 실행 ID (SHA-256 64자리)<input value={lookup} onChange={e=>{clear();setLookup(e.target.value);}} placeholder="조회할 실행 ID를 직접 입력" spellCheck={false}/></label><div className="lwf-actions"><button type="button" disabled={busy||!workflowSha(lookup)} onClick={()=>void action('lookup')}><Icon name="search" size={17}/>저장 상태 조회</button>{busy&&<button type="button" onClick={clear}><Icon name="close" size={17}/>응답 표시 중단</button>}</div>
 {error&&<p className="lwf-warning" role="alert">{error}</p>}
 {receipt&&<div className="lwf-result"><h4 role="status">{workflowLabels[receipt.status]}</h4><dl><div><dt>실행 ID</dt><dd><code>{receipt.id}</code></dd></div><div><dt>Trace</dt><dd>{receipt.trace_id}</dd></div><div><dt>재생 여부</dt><dd>{receipt.replayed?'과거 상태 읽기 · 새 실행 승인 아님':'이번 명시 요청'}</dd></div><div><dt>관측 범위</dt><dd>로컬 LCLUC · 과학 인증 false · GMAIS 표준 결과 false</dd></div></dl>{receipt.issue&&<p>고정 진단: <code>{receipt.issue}</code></p>}{receipt.status==='BLOCKED'&&<p>실행 전 차단으로 저장 기록이 없습니다. 이 ID의 GET 조회는 404일 수 있습니다.</p>}{receipt.status==='RUNNING'&&<p>실행 중 또는 중단 후 미완료 기록입니다. 자동 재개하거나 성공으로 추정하지 않습니다.</p>}{receipt.status==='FAILED'&&<p>실패 기록과 부분 파일을 보존합니다. 같은 키는 자동 재실행하지 않습니다.</p>}
 {receipt.status==='SUCCEEDED'&&<><button type="button" disabled={busy} onClick={()=>void action('report')}><Icon name="report" size={17}/>검증된 보고서 읽기</button><h4>인증을 유지하는 산출물 다운로드</h4><ul>{receipt.artifacts?.map((a,i)=><li key={a.path}><span>{a.path.replaceAll('\\','/').split('/').slice(3).join('/')}<small>SHA {a.sha256}</small></span><button type="button" disabled={busy} onClick={()=>void action('asset',i)}><AnalysisIcon label="결과 내보내기"/>다운로드 {i+1}</button></li>)}</ul></>}
 {report&&<div><h4>실제 보고서 요약</h4><p>관측 연도: {report.years.join(', ')}</p><div className="lwf-table"><table><thead><tr><th>변화쌍</th><th>유효 픽셀</th><th>변화 면적 (m²)</th></tr></thead><tbody>{report.changes.map(c=><tr key={c.pair}><td>{c.pair}</td><td>{c.validPixels.toLocaleString()}</td><td>{c.area.toLocaleString()}</td></tr>)}</tbody></table></div><p>시점·센서·계절·구름·모델 오차를 포함할 수 있으며 독립 정확도 검증이 아닙니다.</p>{rawReport!==undefined&&<LclucWorkflowChangeMap receipt={receipt} rawReport={rawReport} pairs={report.changes.map(c=>c.pair)} disabled={busy}/>}</div>}</div>}
 <p>입력 편집·이동·뒤로 가기·표시 중단은 늦은 응답 표시만 폐기합니다. 서버 실행을 취소하거나 파일·DB 변경을 롤백하지 않습니다. 조회·보고서·다운로드도 자동 실행하지 않습니다.</p></section></details>;
}
