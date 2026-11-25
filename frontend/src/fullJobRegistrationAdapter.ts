import {prepareFullJobHandoff,fullJobHandoffView} from './fullJobHandoffAdapter.ts';
import type {FullJobExpectation,FullJobResult} from './fullJobHandoffAdapter.ts';
import {handoffDigest} from './workflowNodeHandoffAdapter.ts';

type Row=Record<string,unknown>;
const exact=(v:unknown,keys:string[]):v is Row=>v!==null&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
export type FullJobRegistrationExpectation=FullJobExpectation&{request:FullJobExpectation['request']&{contract_version:2}};
export async function prepareFullJobRegistration(workflowText:string,nodeId:string,jobText:string):Promise<FullJobRegistrationExpectation>{
 const base=await prepareFullJobHandoff(workflowText,nodeId,jobText);
 const request={...base.request,contract_version:2 as const},requestBody=JSON.stringify(request);
 if(new TextEncoder().encode(requestBody).length>1048576)throw new Error('전체 요청은 UTF-8 1MiB 이하이어야 합니다.');
 return {...base,request,requestBody,requestDigest:await handoffDigest(requestBody)};
}
export type RegistrationStatus='NOT_RUN'|'REGISTERED'|'AGENT_UNKNOWN'|'CAPABILITY_UNREGISTERED';
export type FullJobRegistrationResult={schema_version:2;scope:'WORKFLOW_FULL_JOB_LOCAL_REGISTRATION_OBSERVATION_ONLY';status:'MATCH'|'BLOCKED';full_job_comparison:FullJobResult;local_manifest_registration:{source:'LOCAL_STATIC_AGENT_MANIFESTS';status:RegistrationStatus;checked:boolean};actual_capability_supported:false;institution_acl_verified:false;execution_authorized:false};
export type FullJobRegistrationView={valid:false;message:string}|{valid:true;result:FullJobRegistrationResult};
export function fullJobRegistrationView(value:unknown,e:FullJobRegistrationExpectation):FullJobRegistrationView{
 const invalid=():FullJobRegistrationView=>({valid:false,message:'RFC2 응답의 요청 해시·등록관계·비승인 계약이 일치하지 않습니다. 결과를 사용하지 마세요.'});
 if(!exact(value,['extension','approval_status','present_in_upstream_openapi','request_sha256','result'])||value.extension!=='greenblue.workflow-full-job-input-handoff.rfc2'||value.approval_status!=='INTERNAL_REVIEW'||value.present_in_upstream_openapi!==false||value.request_sha256!==e.requestDigest||e.request.contract_version!==2)return invalid();
 const r=value.result;
 if(!exact(r,['schema_version','scope','status','full_job_comparison','local_manifest_registration','actual_capability_supported','institution_acl_verified','execution_authorized'])||r.schema_version!==2||r.scope!=='WORKFLOW_FULL_JOB_LOCAL_REGISTRATION_OBSERVATION_ONLY'||r.actual_capability_supported!==false||r.institution_acl_verified!==false||r.execution_authorized!==false)return invalid();
 const inner=fullJobHandoffView({...value,extension:'greenblue.workflow-full-job-input-handoff.rfc1',result:r.full_job_comparison},e);
 if(!inner.valid)return invalid();
 const registration=r.local_manifest_registration;
 if(!exact(registration,['source','status','checked'])||registration.source!=='LOCAL_STATIC_AGENT_MANIFESTS')return invalid();
 if(inner.result.status==='BLOCKED'){
  if(registration.status!=='NOT_RUN'||registration.checked!==false)return invalid();
 }else if(!['REGISTERED','AGENT_UNKNOWN','CAPABILITY_UNREGISTERED'].includes(String(registration.status))||typeof registration.status!=='string'||registration.checked!==true)return invalid();
 const status=inner.result.status==='MATCH'&&registration.status==='REGISTERED'?'MATCH':'BLOCKED';
 if(r.status!==status)return invalid();
 return {valid:true,result:r as FullJobRegistrationResult};
}
export const registrationLabels:Record<RegistrationStatus,string>={NOT_RUN:'미실행 · 앞선 초안 검사 차단',REGISTERED:'등록관계 관측 · 로컬 manifest',AGENT_UNKNOWN:'Agent 미등록 · 로컬 manifest',CAPABILITY_UNREGISTERED:'Capability 미등록 · 선택 Agent'};
