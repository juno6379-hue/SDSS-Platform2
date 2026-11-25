import {parseHandoffJson,handoffCanonical,handoffDigest,handoffFalseFields,handoffIoFields,workflowHandoffView} from './workflowNodeHandoffAdapter.ts';
import type {HandoffExpectation,HandoffResult} from './workflowNodeHandoffAdapter.ts';
type Row=Record<string,unknown>;
const row=(v:unknown):v is Row=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const exact=(v:unknown,keys:string[]):v is Row=>row(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const sha=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
// Metadata can be schema-valid yet exceed comparator 86's 256-scalar bound.
// Hash only this extracted string/ref structure, never the full decimal Job.
function metadataCanonical(v:unknown):string{
 if(v===null||typeof v==='boolean'||typeof v==='string')return JSON.stringify(v);
 if(typeof v==='number'&&Number.isSafeInteger(v))return JSON.stringify(v);
 if(Array.isArray(v))return `[${v.map(metadataCanonical).join(',')}]`;
 if(row(v))return `{${Object.keys(v).sort((a,b)=>{const x=Array.from(a,c=>c.codePointAt(0)!),y=Array.from(b,c=>c.codePointAt(0)!);for(let i=0;i<Math.min(x.length,y.length);i++)if(x[i]!==y[i])return x[i]-y[i];return x.length-y.length;}).map(k=>`${JSON.stringify(k)}:${metadataCanonical(v[k])}`).join(',')}}`;
 throw new Error('Metadata scalar shape.');
}
export const fullJobFalseFields=[...handoffFalseFields,'full_job_origin_verified','full_job_pin_verified','agent_capability_verified','model_verified'];
export type FullJobExpectation={request:{workflow_request_json:string;pinned_workflow_request_sha256:string;selected_node_id:string;full_job_request_json:string};requestBody:string;requestDigest:string;inner:HandoffExpectation};
// Full Job text is preserved, never canonicalized in JavaScript. The server owns
// strict decimal/duplicate/underflow validation and its Python hash is observation.
export async function prepareFullJobHandoff(workflowText:string,nodeId:string,jobText:string):Promise<FullJobExpectation>{
 if(!nodeId.trim()||Array.from(nodeId).length>256||/[\u0000-\u001f\u007f-\u009f\ud800-\udfff]/u.test(nodeId))throw new Error('선택 노드 ID를 원문 그대로 1..256자로 입력하세요.');
 if(!jobText.trim())throw new Error('사용자가 작성한 완성 Job JSON 원문을 입력하세요.');
 if(new TextEncoder().encode(jobText).length>524288)throw new Error('완성 Job 원문은 UTF-8 512KiB 이하이어야 합니다.');
 const workflow=parseHandoffJson(workflowText),pin=await handoffDigest(handoffCanonical(workflow));
 const request={workflow_request_json:workflowText,pinned_workflow_request_sha256:pin,selected_node_id:nodeId,full_job_request_json:jobText},requestBody=JSON.stringify(request);
 if(new TextEncoder().encode(requestBody).length>1048576)throw new Error('전체 요청은 UTF-8 1MiB 이하이어야 합니다.');
 let job:unknown;try{job=JSON.parse(jobText);}catch{/* Server returns safe transport error. */}
 const j=row(job)?job:{},context=row(j.execution_context)?j.execution_context:{};
 const proposal={agent_id:j.agent_id,capability_id:j.capability_id,execution_context:{trace_id:context.trace_id},input_refs:j.input_refs};
 let proposalDigest='';try{proposalDigest=await handoffDigest(metadataCanonical(proposal));}catch{/* Invalid metadata is represented by a BLOCKED server stage. */}
 const w=row(workflow)?workflow:{},nodes=Array.isArray(w.nodes)?w.nodes:[],n=nodes.find(n=>row(n)&&n.node_id===nodeId);
 let expectedMetadataDigest:string|null=null;try{if(row(n))expectedMetadataDigest=await handoffDigest(handoffCanonical({agent_id:n.agent_id,capability_id:n.capability_id,execution_context:{trace_id:w.trace_id},input_refs:n.input_bindings}));}catch{/* Server core decides structural validity. */}
 const inner:HandoffExpectation={request:{workflow_request_json:workflowText,pinned_workflow_request_sha256:pin,selected_node_id:nodeId,proposed_job_metadata_json:''},requestBody,requestDigest:'',nodeDigest:await handoffDigest(handoffCanonical(nodeId)),expectedMetadataDigest,proposalDigest,workflow,proposal};
 return {request,requestBody,requestDigest:await handoffDigest(requestBody),inner};
}
export type FullJobResult={status:'MATCH'|'BLOCKED';declarations_match:boolean;full_job_request_sha256:string|null;extracted_metadata_sha256:string|null;validator_attempted:boolean;validator_status:'NOT_RUN'|'INVALID'|'VALID'|'RESOURCE_UNAVAILABLE';full_job_schema_validated:boolean;bbox_numeric_order_validated:boolean;schema_files_read:null;comparator_calls:0|1;metadata_comparison:HandoffResult|null;issues:{code:string}[]}&Row;
export type FullJobView={valid:false;message:string}|{valid:true;result:FullJobResult};
export function fullJobHandoffView(value:unknown,e:FullJobExpectation):FullJobView{
 const invalid=():FullJobView=>({valid:false,message:'응답의 요청 해시·단계·metadata·비승인 계약이 일치하지 않습니다. 결과를 사용하지 마세요.'});
 if(!exact(value,['extension','approval_status','present_in_upstream_openapi','request_sha256','result'])||value.extension!=='greenblue.workflow-full-job-input-handoff.rfc1'||value.approval_status!=='INTERNAL_REVIEW'||value.present_in_upstream_openapi!==false||value.request_sha256!==e.requestDigest)return invalid();
 const r=value.result,fields=['schema_version','scope','status','declarations_match','full_job_request_sha256','extracted_metadata_sha256','full_job_schema_validated','bbox_numeric_order_validated','validator_attempted','validator_status','schema_files_read','comparator_calls','metadata_comparison','issues',...fullJobFalseFields,...handoffIoFields];
 if(!exact(r,fields)||r.schema_version!==1||r.scope!=='WORKFLOW_NODE_TO_FULL_JOB_DRAFT_HANDOFF_ONLY'||(r.status!=='MATCH'&&r.status!=='BLOCKED')||r.declarations_match!==(r.status==='MATCH')||fullJobFalseFields.some(k=>r[k]!==false)||handoffIoFields.some(k=>r[k]!==0||typeof r[k]!=='number')||r.schema_files_read!==null||typeof r.validator_attempted!=='boolean'||typeof r.full_job_schema_validated!=='boolean'||typeof r.bbox_numeric_order_validated!=='boolean'||(r.comparator_calls!==0&&r.comparator_calls!==1))return invalid();
 for(const key of ['full_job_request_sha256','extracted_metadata_sha256'])if(r[key]!==null&&!sha(r[key]))return invalid();
 if(r.validator_status==='RESOURCE_UNAVAILABLE')return invalid();
 if(!Array.isArray(r.issues)||r.issues.length>1||r.issues.some(i=>!exact(i,['code'])||typeof i.code!=='string'))return invalid();
 const code=r.issues.length?r.issues[0].code:null;
 const before=['FULL_JOB_JSON_BOUNDS_INVALID','WORKFLOW_JSON_BOUNDS_INVALID','FULL_JOB_SCHEMA_INVALID'];
 if(!r.validator_attempted){if(r.validator_status!=='NOT_RUN'||r.full_job_request_sha256!==null||!before.includes(code))return invalid();}
 else if(!sha(r.full_job_request_sha256)||!['INVALID','VALID','RESOURCE_UNAVAILABLE'].includes(String(r.validator_status))||typeof r.validator_status!=='string')return invalid();
 if(r.full_job_schema_validated!==(r.validator_status==='VALID')||r.bbox_numeric_order_validated&&!r.full_job_schema_validated)return invalid();
 if(r.comparator_calls===0){
  if(r.metadata_comparison!==null||r.extracted_metadata_sha256!==null||r.status!=='BLOCKED'||!code)return invalid();
  if(r.validator_status==='RESOURCE_UNAVAILABLE'&&code!=='RESOURCE_UNAVAILABLE'||r.validator_status==='INVALID'&&code!=='FULL_JOB_SCHEMA_INVALID')return invalid();
  if(r.validator_status==='VALID'){
   if(!r.bbox_numeric_order_validated){if(code!=='FULL_JOB_BBOX_INVALID')return invalid();}
   else if(!['MODEL_REFERENCE_INVALID','MODEL_VERSION_NOT_PINNED','WORKFLOW_RUN_ID_MISMATCH'].includes(code))return invalid();
  }
 }else{
  if(!r.validator_attempted||!r.full_job_schema_validated||!r.bbox_numeric_order_validated||r.validator_status!=='VALID'||!sha(r.extracted_metadata_sha256))return invalid();
  const inner=workflowHandoffView({extension:'greenblue.workflow-node-input-handoff.rfc1',approval_status:'INTERNAL_REVIEW',present_in_upstream_openapi:false,request_sha256:e.inner.requestDigest,result:r.metadata_comparison},e.inner);
  if(!inner.valid||r.extracted_metadata_sha256!==e.inner.proposalDigest||r.status!==inner.result.status||(r.status==='MATCH'?code!==null:code!=='METADATA_HANDOFF_BLOCKED'))return invalid();
 }
 return {valid:true,result:r as FullJobResult};
}
export {workflowHandoffReplyCurrent as fullJobHandoffReplyCurrent} from './workflowNodeHandoffAdapter.ts';
export function fullJobHandoffError(status:number){return ({400:'HTTP400 · JSON 원문·중복 키·소수/지수·숫자 underflow·문자 형식을 확인하세요.',413:'HTTP413 · 요청 크기·깊이·문자열·숫자 한도를 초과했습니다.',503:'HTTP503 · 완성 Job 초안 검사를 사용할 수 없습니다. 통과로 대체하지 않습니다.',401:'HTTP401 · API 인증을 확인하세요.',403:'HTTP403 · API 접근 권한을 확인하세요.'} as Record<number,string>)[status]||'완성 Job 초안 응답을 확인하지 못했습니다. 연결 상태를 확인한 뒤 직접 다시 검사하세요.';}
