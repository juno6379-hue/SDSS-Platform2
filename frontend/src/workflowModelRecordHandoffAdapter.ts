import {prepareFullJobHandoff,fullJobHandoffView,fullJobHandoffError} from './fullJobHandoffAdapter.ts';
import type {FullJobExpectation,FullJobResult} from './fullJobHandoffAdapter.ts';
import {handoffDigest} from './workflowNodeHandoffAdapter.ts';
import {parseModelProvenance} from './modelRegistrationProvenanceAdapter.ts';
import type {ProvenanceResult} from './modelRegistrationProvenanceAdapter.ts';
type Row=Record<string,unknown>;
const row=(v:unknown):v is Row=>!!v&&typeof v==='object'&&!Array.isArray(v);
const exact=(v:unknown,keys:readonly string[]):v is Row=>row(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
export const modelRecordFalseFlags=['authority_verified','artifact_bytes_verified','execution_authorized','scientific_accuracy_validated','model_verified'] as const;
export const modelRecordOuterLabels={HANDOFF_BLOCKED:'완성 Job 입력 전달 차단',MODEL_REFERENCE_ABSENT:'모델 참조 없음 · 대조 미실행',MODEL_REFERENCE_OBSERVED:'모델 참조 대조 수행 · 결과 별도 확인'} as const;
export const modelRecordStatusLabels={REFERENCE_INVALID:'참조 형식 확인 필요',RECORD_NOT_PROVIDED:'사용자 레코드 미제공',RECORD_INVALID:'제공 레코드 형식 확인 필요',REFERENCE_CONFLICT:'참조와 레코드 충돌',REFERENCE_NOT_COMPARABLE:'레코드 선언 근거로 대조 불가',MATCH_UNVERIFIED:'메타데이터 일치 · 모델 인증 미검증'} as const;
export const modelRecordBindingLabels={NOT_CHECKED:'검사하지 않음',MATCH:'메타데이터 일치',MISMATCH:'메타데이터 불일치'} as const;
type Binding=keyof typeof modelRecordBindingLabels;
export type ModelRecordComparison={status:keyof typeof modelRecordStatusLabels;bindings:Record<'id'|'version'|'sha256',Binding>;record_provenance:ProvenanceResult|null;issue:{code:string;field:string;side:string}|null;inspection_calls:0|1}&Row;
export type WorkflowModelRecordResult={status:keyof typeof modelRecordOuterLabels;full_job_comparison:FullJobResult;model_reference_comparison:ModelRecordComparison|null;identity_projection_performed:boolean;model_comparison_calls:0|1}&Row;
export type WorkflowModelRecordExpectation={base:FullJobExpectation;request:FullJobExpectation['request']&{model_record_json?:string};requestBody:string;requestDigest:string;job:unknown;record:unknown;recordParsed:boolean};
export async function prepareWorkflowModelRecord(workflowText:string,nodeId:string,jobText:string,recordText:string):Promise<WorkflowModelRecordExpectation>{
  // Check the merged transport first; raw text is never canonicalized here.
  const provisional={workflow_request_json:workflowText,pinned_workflow_request_sha256:'0'.repeat(64),selected_node_id:nodeId,full_job_request_json:jobText,...(recordText===''?{}:{model_record_json:recordText})};
  if(new TextEncoder().encode(JSON.stringify(provisional)).length>1048576)throw new Error('요청 전체는 UTF-8 1MiB 이하이어야 합니다.');
  if([workflowText,jobText,recordText].some(v=>new TextEncoder().encode(v).length>524288))throw new Error('각 JSON 원문은 UTF-8 512KiB 이하이어야 합니다.');
  const base=await prepareFullJobHandoff(workflowText,nodeId,jobText);
  const request={...base.request,...(recordText===''?{}:{model_record_json:recordText})},requestBody=JSON.stringify(request);
  let job:unknown,record:unknown=null,recordParsed=true;
  try{job=JSON.parse(jobText);}catch{/* Only the server decides strict transport validity. */}
  if(recordText!=='')try{record=JSON.parse(recordText);}catch{recordParsed=false;}
  return {base,request,requestBody,requestDigest:await handoffDigest(requestBody),job,record,recordParsed};
}
export function parseModelRecordComparison(v:unknown):ModelRecordComparison|undefined{
  if(!exact(v,['schema_version','scope','status','bindings','record_provenance','issue','inspection_calls',...modelRecordFalseFlags])||v.schema_version!==1||v.scope!=='DECLARED_MODEL_IDENTITY_TO_SUPPLIED_RECORD_ONLY'||modelRecordFalseFlags.some(k=>v[k]!==false)||typeof v.status!=='string'||!Object.hasOwn(modelRecordStatusLabels,v.status)||!exact(v.bindings,['id','version','sha256'])||(v.inspection_calls!==0&&v.inspection_calls!==1))return;
  const b=v.bindings;
  if(!['id','version','sha256'].every(k=>typeof b[k]==='string'&&Object.hasOwn(modelRecordBindingLabels,b[k] as string)))return;
  const issue=v.issue;
  if(issue!==null&&(!exact(issue,['code','field','side'])||!['code','field','side'].every(k=>typeof issue[k]==='string')))return;
  const isIssue=(code:string,field:string,side:string)=>row(issue)&&issue.code===code&&issue.field===field&&issue.side===side;
  const unchecked=b.id==='NOT_CHECKED'&&b.version==='NOT_CHECKED'&&b.sha256==='NOT_CHECKED';
  if(v.status==='REFERENCE_INVALID'){
    if(v.inspection_calls!==0||v.record_provenance!==null||!unchecked||!(isIssue('REFERENCE_IDENTITY_INVALID','reference_identity','REFERENCE')||isIssue('MODEL_REFERENCE_INVALID','reference_identity','REFERENCE')||isIssue('MODEL_VERSION_NOT_PINNED','reference_identity','REFERENCE')||isIssue('SHA256_INVALID','sha256','REFERENCE')))return;
  }else if(v.status==='RECORD_NOT_PROVIDED'||v.status==='RECORD_INVALID'){
    if(v.inspection_calls!==0||v.record_provenance!==null||!unchecked)return;
    if(v.status==='RECORD_NOT_PROVIDED'?!isIssue('RECORD_NOT_PROVIDED','model_record','RECORD'):!(isIssue('RECORD_INVALID','model_record','RECORD')||isIssue('MODEL_REFERENCE_INVALID','id','RECORD')))return;
  }else if(v.inspection_calls===0){
    if(v.status!=='REFERENCE_CONFLICT'||v.record_provenance!==null||b.id!=='MISMATCH'||b.version!=='NOT_CHECKED'||b.sha256!=='NOT_CHECKED'||!isIssue('ID_MISMATCH','id','COMPARISON'))return;
  }else{
    const p=parseModelProvenance(v.record_provenance);
    if(!p||b.id!=='MATCH')return;
    if(v.status==='REFERENCE_NOT_COMPARABLE'){
      if(p.status==='CONSISTENT_UNVERIFIED'||b.version!=='NOT_CHECKED'||b.sha256!=='NOT_CHECKED'||!isIssue('REGISTRATION_NOT_COMPARABLE','model_version_declaration','RECORD'))return;
    }else{
      if(p.status!=='CONSISTENT_UNVERIFIED'||!['MATCH','MISMATCH'].includes(b.version as string)||!['MATCH','MISMATCH'].includes(b.sha256 as string))return;
      if(v.status==='MATCH_UNVERIFIED'){if(b.version!=='MATCH'||b.sha256!=='MATCH'||issue!==null)return;}
      else if(v.status!=='REFERENCE_CONFLICT'||(b.version==='MISMATCH'?!isIssue('VERSION_MISMATCH','version','COMPARISON'):b.sha256!=='MISMATCH'||!isIssue('CHECKPOINT_SHA256_MISMATCH','sha256','COMPARISON')))return;
    }
  }
  return v as ModelRecordComparison;
}
function recordRelationsAgree(m:ModelRecordComparison,e:WorkflowModelRecordExpectation):boolean{
  if(!e.recordParsed)return false;
  if(e.record===null)return m.status==='RECORD_NOT_PROVIDED';
  if(m.status==='RECORD_NOT_PROVIDED')return false;
  if(!row(e.record))return m.status==='RECORD_INVALID'&&m.issue?.code==='RECORD_INVALID';
  if(m.status==='RECORD_INVALID')return true; // Server owns bounded Python text validity.
  const ref=row(e.job)&&row(e.job.model_ref)?e.job.model_ref:undefined;
  if(!ref)return false;
  if(m.bindings.id!==(ref.id===e.record.id?'MATCH':'MISMATCH'))return false;
  if(m.inspection_calls===1&&m.record_provenance?.status==='CONSISTENT_UNVERIFIED'){
    const d=e.record.model_version_declaration;
    if(!row(d))return false;
    if(m.bindings.version!==(ref.version===d.version?'MATCH':'MISMATCH')||m.bindings.sha256!==(ref.sha256===d.checkpoint_sha256?'MATCH':'MISMATCH'))return false;
  }
  return true;
}
export function workflowModelRecordView(value:unknown,e:WorkflowModelRecordExpectation):WorkflowModelRecordResult|undefined{
  if(!exact(value,['extension','approval_status','present_in_upstream_openapi','request_sha256','result'])||value.extension!=='greenblue.workflow-full-job-model-record-handoff.rfc1'||value.approval_status!=='INTERNAL_REVIEW'||value.present_in_upstream_openapi!==false||value.request_sha256!==e.requestDigest)return;
  const r=value.result;
  if(!exact(r,['schema_version','scope','status','full_job_comparison','model_reference_comparison','identity_projection_performed','model_comparison_calls',...modelRecordFalseFlags])||r.schema_version!==1||r.scope!=='WORKFLOW_FULL_JOB_MODEL_RECORD_OBSERVATION_ONLY'||typeof r.status!=='string'||!Object.hasOwn(modelRecordOuterLabels,r.status)||modelRecordFalseFlags.some(k=>r[k]!==false)||typeof r.identity_projection_performed!=='boolean'||(r.model_comparison_calls!==0&&r.model_comparison_calls!==1))return;
  // Reuse 89 validation with its original four-field digest after binding the NEW raw body above.
  const inner=fullJobHandoffView({extension:'greenblue.workflow-full-job-input-handoff.rfc1',approval_status:'INTERNAL_REVIEW',present_in_upstream_openapi:false,request_sha256:e.base.requestDigest,result:r.full_job_comparison},e.base);
  if(!inner.valid||!e.recordParsed)return;
  if(inner.result.status==='BLOCKED'){
    if(r.status!=='HANDOFF_BLOCKED'||r.identity_projection_performed!==false||r.model_comparison_calls!==0||r.model_reference_comparison!==null)return;
  }else if(row(e.job)&&!Object.hasOwn(e.job,'model_ref')){
    if(r.status!=='MODEL_REFERENCE_ABSENT'||r.identity_projection_performed!==false||r.model_comparison_calls!==0||r.model_reference_comparison!==null)return;
  }else{
    if(r.status!=='MODEL_REFERENCE_OBSERVED'||r.identity_projection_performed!==true||r.model_comparison_calls!==1)return;
    const m=parseModelRecordComparison(r.model_reference_comparison);
    if(!m||m.status==='REFERENCE_INVALID'||!recordRelationsAgree(m,e))return;
  }
  return r as WorkflowModelRecordResult;
}
export function workflowModelRecordError(status:number){return fullJobHandoffError(status).replaceAll('완성 Job 초안','모델 레코드 초안');}
export class WorkflowModelRecordFlight{
  private generation=0;private pending=false;
  invalidate(){this.generation++;this.pending=false;}
  async inspect(identity:string,route:string,hooks:{prepare:()=>Promise<WorkflowModelRecordExpectation>;post:(request:WorkflowModelRecordExpectation['request'])=>Promise<unknown>;current:()=>{identity:string;route:string};result:(e:WorkflowModelRecordExpectation,r:WorkflowModelRecordResult)=>void;failure:(message:string)=>void;settled:()=>void}){
    if(this.pending)return;this.pending=true;const serial=++this.generation;
    const current=()=>{const v=hooks.current();return serial===this.generation&&identity===v.identity&&route===v.route;};
    try{const e=await hooks.prepare();if(!current())return;const response=await hooks.post(e.request);if(current()){const result=workflowModelRecordView(response,e);if(result)hooks.result(e,result);else hooks.failure('응답의 요청 결합·관측 단계·미검증 계약을 확인하지 못했습니다. 결과를 표시하지 않습니다.');}}
    catch(error){if(current())hooks.failure(workflowModelRecordError(row(error)&&typeof error.status==='number'?error.status:400));}
    finally{if(current()){this.pending=false;hooks.settled();}}
  }
}
