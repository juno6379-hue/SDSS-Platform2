const object=(value:unknown):Record<string,unknown>=>value!==null&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:{};
const exact=(value:Record<string,unknown>,keys:readonly string[])=>Object.keys(value).length===keys.length&&keys.every(key=>Object.hasOwn(value,key));
const sha=(value:unknown):value is string=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const count=(value:unknown):value is number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=1&&value<=64;
const flags=['execution_authorized','ready_for_execution','ready_for_training','scientific_approval','acl_verified','registry_verified','training_authorized','pixels_verified','toc_tou_protected','executor_connected','artifact_bytes_verified','manifest_bytes_verified','current_files_revalidated','executor_bindings_compared'];
const unavailable=['CAPTURE_UNAVAILABLE','CAPTURE_TIME_INVALID','CAPTURE_ROWS_UNAVAILABLE','CAPTURE_ROW_UNAVAILABLE','CAPTURE_BINDING_INVALID','CAPTURE_BOUNDARY_FAILURE'];
export type BindingCaptureState='RECORDED'|'UNAVAILABLE'|'LEGACY'|'INVALID';
export type StoredBindingView={valid:false;message:string}|{valid:true;state:BindingCaptureState;message:string;requestCount:number|null;captureCount:number|null;manifestCount:number|null;aggregateHash:string|null;issue:{code:string;inputIndex:number|null}|null};
export function storedBindingJobId(value:unknown):string|null{return typeof value==='string'&&/^[A-Za-z0-9_-]{1,200}$/.test(value)?value:null;}
export async function storedBindingJobDigest(jobId:string){const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(jobId));return Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('');}
export function storedBindingMountKey(context:string){return `stored-execution-binding:${context}`;}
export function storedBindingReplyCurrent(serial:number,currentSerial:number,key:string,currentKey:string,route:string,currentRoute:string){return serial===currentSerial&&key===currentKey&&route===currentRoute;}
export function storedBindingError(status:number){const labels:Record<number,string>={404:'HTTP404 · 이 Job 또는 저장된 입력 연결 조회 API를 찾지 못했습니다. 다른 조회 성공을 기록 존재로 추정하지 않습니다.',503:'HTTP503 · 저장된 입력 연결 기록을 현재 조회할 수 없습니다. 현재 파일 검사나 실행 승인으로 대체하지 않습니다.',401:'HTTP401 · API 인증을 확인하세요. 자료 이용·학습 승인은 별도입니다.',403:'HTTP403 · API 접근 권한을 확인하세요. 자료 이용·학습 승인은 별도입니다.'};return labels[status]||'저장된 입력 연결 응답을 확인하지 못했습니다. 연결 상태를 확인한 뒤 직접 다시 조회하세요.';}
export function storedBindingView(value:unknown,expectedJobDigest:string):StoredBindingView{
 const row=object(value);const fail=(message:string):StoredBindingView=>({valid:false,message});
 if(!exact(row,['schema_version','extension','approval_status','scope','status','request_job_sha256','request_binding_count','capture_binding_count','manifest_pin_count','expected_bindings_sha256','stored_binding_integrity_match','issues',...flags])||row.schema_version!==1||row.extension!=='greenblue.stored-execution-input-binding.rfc1'||row.approval_status!=='INTERNAL_REVIEW'||row.scope!=='STORED_SUBMISSION_BINDING_ONLY'||typeof row.status!=='string'||!['RECORDED','UNAVAILABLE','LEGACY','INVALID'].includes(row.status))return fail('저장된 입력 연결의 응답 계약·상태·검사 범위가 일치하지 않습니다.');
 if(!sha(expectedJobDigest)||row.request_job_sha256!==expectedJobDigest)return fail('요청한 Job ID 원문의 해시와 응답 기준이 다릅니다. 이전 또는 다른 Job의 기록을 표시하지 않습니다.');
 if(flags.some(key=>row[key]!==false))return fail('비승인·현재 파일 미검사·실행자 미대조 계약이 일치하지 않아 결과를 표시하지 않습니다.');
 if(!Array.isArray(row.issues)||row.issues.length>1||typeof row.stored_binding_integrity_match!=='boolean')return fail('저장 기록의 확인 상태·원인 형식이 올바르지 않습니다.');
 if(row.status==='RECORDED'){
  if(!count(row.request_binding_count)||!count(row.capture_binding_count)||!count(row.manifest_pin_count)||row.request_binding_count!==row.capture_binding_count||row.request_binding_count!==row.manifest_pin_count||!sha(row.expected_bindings_sha256)||row.stored_binding_integrity_match!==true||row.issues.length!==0)return fail('기록 있음 판정과 입력 계수·집계 해시·저장 연결 검사 근거가 모순됩니다.');
  return {valid:true,state:'RECORDED',message:'제출 시 저장된 입력 연결 기록과 Job의 저장 요청 사이의 구조 일치가 보고되었습니다. 현재 Registry·원본 파일·실행자 입력을 검증한 결과가 아닙니다.',requestCount:row.request_binding_count,captureCount:row.capture_binding_count,manifestCount:row.manifest_pin_count,aggregateHash:row.expected_bindings_sha256,issue:null};
 }
 if(row.capture_binding_count!==null||row.manifest_pin_count!==null||row.expected_bindings_sha256!==null||row.stored_binding_integrity_match!==false||row.issues.length!==1)return fail('미기록·사용 불가·무효 상태의 null·저장 연결 검사 계약이 올바르지 않습니다.');
 const issue=object(row.issues[0]);if(!exact(issue,['code','input_index'])||typeof issue.code!=='string')return fail('저장 기록의 안전한 원인 코드 형식이 올바르지 않습니다.');
 if(row.status==='LEGACY'){
  if(issue.code!=='LEGACY_CAPTURE_NOT_RECORDED'||issue.input_index!==null||!count(row.request_binding_count))return fail('이전 Job 미기록 상태와 저장 요청 계수가 일치하지 않습니다.');
 }else if(row.status==='INVALID'){
  if(!['STORED_JOB_INVALID','STORED_CAPTURE_INVALID'].includes(issue.code)||issue.input_index!==null||(issue.code==='STORED_JOB_INVALID'?row.request_binding_count!==null:!count(row.request_binding_count)))return fail('저장 요청·연결 기록의 무효 원인과 계수가 일치하지 않습니다.');
 }else{
  if(!unavailable.includes(issue.code)||!count(row.request_binding_count)||(issue.code==='CAPTURE_ROW_UNAVAILABLE'?!(typeof issue.input_index==='number'&&Number.isSafeInteger(issue.input_index)&&issue.input_index>=0&&issue.input_index<row.request_binding_count):issue.input_index!==null))return fail('기록 생성 불가의 원인·입력 순서 범위가 올바르지 않습니다.');
 }
 const messages={LEGACY:'이전 Job에 이 연결 기록이 저장되지 않았습니다. 미기록은 입력 0개나 검증 통과를 뜻하지 않으며 소급 기록을 생성하지 않습니다.',UNAVAILABLE:'제출 시 이 연결 기록을 만들지 못한 상태입니다. 저장 요청 수와 생성되지 않은 연결·핀 수를 구분합니다.',INVALID:'저장된 Job 요청 또는 연결 기록의 형식·일관성을 확인할 수 없습니다. 현재 파일을 재검사하거나 정상 기록으로 대체하지 않습니다.'};
 return {valid:true,state:row.status as 'LEGACY'|'UNAVAILABLE'|'INVALID',message:messages[row.status as keyof typeof messages],requestCount:row.request_binding_count as number|null,captureCount:null,manifestCount:null,aggregateHash:null,issue:{code:issue.code,inputIndex:issue.input_index as number|null}};
}
