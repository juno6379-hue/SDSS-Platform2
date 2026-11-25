import {parseHandoffJson,handoffCanonical,handoffDigest} from './workflowNodeHandoffAdapter.ts';
type Row=Record<string,unknown>;
const row=(v:unknown):v is Row=>!!v&&typeof v==='object'&&!Array.isArray(v);
const exact=(v:unknown,keys:string[]):v is Row=>row(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
export const workflowSha=(v:unknown):v is string=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const token=(v:unknown)=>typeof v==='string'&&/^[A-Za-z0-9_-]{1,128}$/.test(v);
const ref=(v:unknown)=>exact(v,['id','version','sha256'])&&['id','version'].every(k=>typeof v[k]==='string'&&/^[A-Za-z0-9_.-]{1,128}$/.test(v[k] as string)&&!['latest','current'].includes((v[k] as string).toLowerCase()))&&workflowSha(v.sha256);
export function requestShape(v:unknown):v is Row{
 if(!exact(v,['schema_version','capability','trace_id','idempotency_key','model_ref','images'])||v.schema_version!==1||v.capability!=='landcover.change_detection'||!token(v.trace_id)||!token(v.idempotency_key)||!ref(v.model_ref)||!Array.isArray(v.images)||v.images.length<2||v.images.length>6)return false;
 let prior=1899;return v.images.every(i=>{if(!exact(i,['year','input_ref','quality_report_sha256'])||!Number.isInteger(i.year)||Number(i.year)<=prior||Number(i.year)>2200||!ref(i.input_ref)||!workflowSha(i.quality_report_sha256))return false;prior=Number(i.year);return true;});
}
export function parseWorkflowRequest(text:string):Row{
 try{if(new TextEncoder().encode(text).length>16384)throw 0;const value=parseHandoffJson(text);if(!requestShape(value))throw 0;return value;}catch{throw new Error('고정 모델 ID·버전·SHA와 연차 입력을 포함한 exact6 JSON을 확인하세요. 최대 16KiB이며 빈 값·경로·중복 키·소수는 허용하지 않습니다.');}
}
export async function prepareWorkflow(text:string){const request=parseWorkflowRequest(text);return {request,digest:await handoffDigest(handoffCanonical(request)),id:await handoffDigest(request.idempotency_key as string)};}
export const workflowLabels={BLOCKED:'실행 전 차단 · 기록 없음',RUNNING:'실행 중 · 자동 재개 없음',FAILED:'실행 실패 · 자동 재시도 없음',SUCCEEDED:'로컬 실행 완료'};
export type WorkflowReceipt=Row&{id:string;trace_id:string;status:keyof typeof workflowLabels;replayed:boolean;artifacts?:{path:string;sha256:string}[];report_path?:string;issue:string|null};
const safeText=(v:unknown,max=256):v is string=>typeof v==='string'&&v.length>0&&v.length<=max&&!/[\x00-\x1f\x7f]/.test(v);
const issueCodes=new Set(['ADMISSION_CHANGED_AFTER_CLAIM','ADMISSION_GATE_BLOCKED','CHECKPOINT_MISMATCH','CLAIM_STATE_CHANGED','DATASET_QUALITY_OR_ACCESS_BLOCKED','DATASET_YEAR_MISMATCH','FILE_LIMIT_OR_INTEGRITY','INPUT_INTEGRITY_MISMATCH','LOCAL_EXECUTION_FAILED','LOCAL_WORKFLOW_UNAVAILABLE','MODEL_ARCHITECTURE_UNSUPPORTED','MODEL_BAND_SIGNATURE_INVALID','MODEL_CLASSES_INVALID','MODEL_EVALUATION_MISMATCH','MODEL_IDENTITY_MISMATCH','MODEL_METADATA_LIMIT','MODEL_NOT_DEPLOYED_OR_EVALUATED','MODEL_PATCH_LIMIT','MODEL_VERSION_NOT_BOUND','NORMALIZATION_MODE_UNSUPPORTED','OUTPUT_LIMIT','OUTPUT_NAMESPACE_UNAVAILABLE','OUTPUT_PATH_CHANGED','QUALITY_REPORT_MISMATCH','RASTER_BAND_SIGNATURE_MISMATCH','RASTER_LIMIT_OR_BANDS','RASTER_READ_BUDGET_EXCEEDED','RUNNER_REPORT_MISMATCH','SYNTHETIC_MODEL_BLOCKED','TRAINING_REPORT_MISMATCH']);
const issue=(v:unknown)=>v===null||(typeof v==='string'&&issueCodes.has(v));
const snapshot=(v:unknown)=>exact(v,['schema_version','capability','trace_id','model_ref','images'])&&requestShape({...v,idempotency_key:'snapshot'});
const pathText=(v:unknown)=>typeof v==='string'?v.replaceAll('\\','/') : '';
export function parseWorkflowReceipt(value:unknown,expected:{id:string;digest?:string;request?:Row}):WorkflowReceipt|undefined{
 if(!row(value)||value.schema_version!==1||value.scope!=='LOCAL_LCLUC_WORKFLOW_ONLY'||value.id!==expected.id||!workflowSha(value.id)||!token(value.trace_id)||typeof value.replayed!=='boolean'||value.scientific_accuracy_validated!==false||value.standard_gmais_result!==false||!Object.hasOwn(workflowLabels,String(value.status))||!issue(value.issue))return;
 const common=['schema_version','scope','status','trace_id','id','issue','replayed','scientific_accuracy_validated','standard_gmais_result'];
 if(value.status==='BLOCKED'){if(!exact(value,common)||value.replayed!==false||value.issue===null)return;return value as WorkflowReceipt;}
 const fields=[...common,'request_sha256','request_snapshot','created_at','artifacts'];
 if(value.status!=='RUNNING')fields.push('finished_at');
 if(value.status==='SUCCEEDED')fields.push('report_path','admission_pins');
 if(!exact(value,fields)||!workflowSha(value.request_sha256)||(expected.digest&&value.request_sha256!==expected.digest)||!snapshot(value.request_snapshot)||!safeText(value.created_at,64)||!Array.isArray(value.artifacts)||value.artifacts.length>128)return;
 if((value.request_snapshot as Row).trace_id!==value.trace_id)return;
 if(expected.request){const {idempotency_key:_,...wanted}=expected.request;if(handoffCanonical(value.request_snapshot)!==handoffCanonical(wanted))return;}
 if(value.status!=='RUNNING'&&!safeText(value.finished_at,64))return;
 if(value.status==='SUCCEEDED'){
  const prefix=`results/lcluc-workflows/${value.id}/`;
  const pinKeys=['model',...((value.request_snapshot as Row).images as Row[]).map(i=>String(i.year))];
  if(!exact(value.admission_pins,pinKeys))return;
  if(value.issue!==null||pathText(value.report_path)!==prefix+'timeseries.json'||!row(value.admission_pins)||Object.values(value.admission_pins).some(x=>!workflowSha(x))||!workflowSha(value.admission_pins.model)||!value.artifacts.length)return;
  const seen=new Set();for(const a of value.artifacts){const normalized=pathText(row(a)?a.path:undefined);if(!exact(a,['path','sha256'])||!safeText(a.path,512)||!normalized.startsWith(prefix)||normalized.split('/').some(x=>x==='..'||x==='.'||!x)||!workflowSha(a.sha256)||seen.has(normalized))return;seen.add(normalized);}
  if(!seen.has(pathText(value.report_path)))return;
 }else if(value.artifacts.length!==0||(value.status==='RUNNING'?value.issue!==null:value.issue===null))return;
 return value as WorkflowReceipt;
}
export function workflowError(status:number){return status===401||status===403?'인증 또는 접근 권한을 확인하세요.':status===404?'저장된 실행 기록이 없습니다. 실행 전 차단은 기록을 생성하지 않습니다.':status===409?'현재 상태에서는 요청할 수 없거나 동일 실행 키의 요청 내용이 다릅니다.':status===413?'요청 크기 한도를 초과했습니다.':status===400?'실행 요청 JSON을 확인하세요.':'실행 응답을 확인할 수 없습니다. 자동으로 재시도하지 않습니다.';}
export function workflowResponse(status:number,value:unknown,expected:{id:string;digest?:string;request?:Row;readOnly?:boolean}){
 const receipt=parseWorkflowReceipt(value,expected);
 if(receipt&&(!expected.readOnly||receipt.replayed===true)&&((status===200&&receipt.status!=='BLOCKED')||(status===409&&receipt.status==='BLOCKED')))return receipt;
 const codes:Record<string,number>={INVALID_REQUEST:400,REQUEST_TOO_LARGE:413,NOT_FOUND:404,IDEMPOTENCY_CONFLICT:409,WORKFLOW_NOT_SUCCEEDED:409,STORED_OUTPUT_CHANGED:503,RESOURCE_UNAVAILABLE:503};
 if(exact(value,['error'])&&exact(value.error,['code','message','retryable'])&&typeof value.error.code==='string'&&codes[value.error.code]===status&&value.error.retryable===false&&safeText(value.error.message,512))throw new Error(workflowError(status));
 if(status===401||status===403)throw new Error(workflowError(status));
 throw new Error('응답 형식을 확인할 수 없습니다.');
}
export type WorkflowReport={years:number[];changes:{pair:string;validPixels:number;area:number}[]};
export function parseWorkflowReport(value:unknown,receipt:WorkflowReceipt):WorkflowReport|undefined{
 if(receipt.status!=='SUCCEEDED'||!row(value)||value.report_path!==receipt.report_path||!row(receipt.request_snapshot)||!Array.isArray(receipt.request_snapshot.images)||!row(receipt.request_snapshot.model_ref)||value.checkpoint_sha256!==receipt.request_snapshot.model_ref.sha256||!Array.isArray(value.years)||!row(value.classifications)||!row(value.changes))return;
 const years=(receipt.request_snapshot.images as Row[]).map(i=>i.year as number);
 if(JSON.stringify(value.years)!==JSON.stringify(years)||Object.keys(value.classifications).sort().join(',')!==years.map(String).sort().join(','))return;
 const expected=new Set([...years.slice(1).map((y,i)=>`${years[i]}-${y}`),...years.slice(1).map(y=>`${years[0]}-${y}`)]);
 if(Object.keys(value.changes).length!==expected.size)return;
 const changes=[];for(const [pair,c]of Object.entries(value.changes)){if(!expected.has(pair)||!row(c)||!Number.isSafeInteger(c.valid_pixels)||Number(c.valid_pixels)<0||typeof c.changed_area_m2!=='number'||!Number.isFinite(c.changed_area_m2)||c.changed_area_m2<0)return;changes.push({pair,validPixels:c.valid_pixels as number,area:c.changed_area_m2});}
 return {years,changes};
}
export class WorkflowFlight{
 private generation=0;private pending=false;
 invalidate(){this.generation++;this.pending=false;}
 async run(identity:string,route:string,h:{current:()=>{identity:string;route:string};work:(live:()=>boolean)=>Promise<void>;failure:(s:string)=>void;settled:()=>void}){
  if(this.pending)return;this.pending=true;const g=this.generation;
  const live=()=>g===this.generation&&h.current().identity===identity&&h.current().route===route;
  try{await h.work(live);}catch(e){if(live())h.failure(e instanceof Error&&/^(고정 모델|인증 또는|저장된 실행|현재 상태|요청 크기|실행 요청|실행 응답)/.test(e.message)?e.message:'응답 형식 또는 연결을 확인하세요. 서버 처리는 취소·롤백되지 않으며 자동 재시도하지 않습니다.');}finally{if(live()){this.pending=false;h.settled();}}
 }
}
