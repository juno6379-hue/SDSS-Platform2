/** 기관 운영 API는 동일 출처의 고정 endpoint만 사용한다. 토큰은 호출 인자로만 전달한다. */
export type OpsJob = {id:string;approval_id:string;provider:string;operation:string;state:string;progress:number;cancel_requested:boolean;model:{name:string;version:string;artifact_sha256:string};result_id:string|null;package_sha256:string|null;blockers:string[];updated_at:string};
export type JobApproval = {approval_id:string;provider:string;operation:string;model:OpsJob['model'];eligible_until:string};
export type ReleaseRow = {model:string;versions:{version:string;manifest_sha:string}[];history:{revision:number;version:string;previous_version:string|null;action:string;approver?:string;approval_sha?:string;created_at?:string}[];active_version?:string|null;active_revision?:number;execution_ready?:boolean;blockers?:string[]};
export type SourceRow = {source_id:string;verification:string;publication_gate:string;public_search_enabled:boolean;collection_progress_ref?:{endpoint:string;dataset_id:string|null}};
export type OpsList<T,K extends string> = {status:string;blockers?:string[]} & Record<K,T[]>;
export const safeOpsId = (id:unknown):id is string => typeof id==='string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$/.test(id);
export function resultReviewHash(id:string) {if(!safeOpsId(id))throw Error('RESULT_ID_INVALID');return '#/reports/results?result_id='+encodeURIComponent(id);}
export function resultIdFromHash(hash:string):string|undefined {const [path,query='']=hash.split('?');if(path!=='#/reports/results')return;const id=new URLSearchParams(query).get('result_id');return safeOpsId(id)?id:undefined;}
export async function opsRequest(path:string,options:{signal?:AbortSignal;token?:string;body?:unknown}={}) {
  if(!/^\/(jobs(?:\/approvals|\/[A-Za-z0-9_-]+\/cancel)?|model-releases|institution-sources)$/.test(path))throw Error('OPERATION_ENDPOINT_INVALID');
  const headers:Record<string,string>={};
  if(options.body!==undefined){headers['Content-Type']='application/json';if(!options.token?.trim())throw Error('운영 토큰을 입력하세요.');if(!/^[\x21-\x7e]+$/.test(options.token.trim()))throw Error('운영 토큰 형식 오류');headers.Authorization='Bearer '+options.token.trim();}
  let response: Response;
  try {response=await fetch('/api'+path,{method:options.body===undefined?'GET':'POST',headers,body:options.body===undefined?undefined:JSON.stringify(options.body),signal:options.signal});}
  catch {throw Error('운영 API 연결 미확인');} // native header 오류가 토큰 값을 노출하지 않도록 일반화한다.
  if(!response.headers.get('content-type')?.includes('application/json'))throw Error('운영 API 연결 실패 · 프록시와 서버를 확인하세요.');
  const data=await response.json();
  if(!response.ok){const codes=Array.isArray(data?.blockers)?data.blockers.filter((v:unknown)=>typeof v==='string'&&/^[A-Z0-9_:-]{1,160}$/.test(v)):[];throw Error(codes.length?codes.join(' · '):`운영 요청 차단 HTTP ${response.status}`);}
  return data as unknown;
}
export function opsList<T,K extends string>(value:unknown,key:K,validate:(row:unknown)=>boolean):OpsList<T,K>{const data=value as OpsList<T,K>;if(!data||!Array.isArray(data[key])||!data[key].every(validate)||(key!=='sources'&&typeof data.status!=='string')||(data.blockers!==undefined&&(!Array.isArray(data.blockers)||!data.blockers.every(x=>typeof x==='string'))))throw Error('OPERATION_RESPONSE_INVALID');return data;}
const obj=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const fields=(v:unknown,keys:string[])=>obj(v)&&keys.every(k=>typeof v[k]==='string');
export function validOpsJob(v:unknown){if(!obj(v))return false;return fields(v,['id','approval_id','provider','operation','state','updated_at'])&&safeOpsId(v.id)&&['QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED'].includes(v.state as string)&&fields(v.model,['name','version','artifact_sha256'])&&obj(v.model)&&/^[a-fA-F0-9]{64}$/.test(String(v.model.artifact_sha256))&&typeof v.progress==='number'&&Number.isFinite(v.progress)&&v.progress>=0&&v.progress<=100&&typeof v.cancel_requested==='boolean'&&Array.isArray(v.blockers)&&v.blockers.every(x=>typeof x==='string')&&(v.result_id===null||safeOpsId(v.result_id))&&(v.package_sha256===null||(typeof v.package_sha256==='string'&&/^[a-fA-F0-9]{64}$/.test(v.package_sha256)));}
export const validApproval=(v:unknown)=>fields(v,['approval_id','provider','operation','eligible_until'])&&obj(v)&&safeOpsId(v.approval_id)&&fields(v.model,['name','version','artifact_sha256']);
export const validRelease=(v:unknown)=>obj(v)&&typeof v.model==='string'&&Array.isArray(v.versions)&&v.versions.every(x=>fields(x,['version','manifest_sha']))&&Array.isArray(v.history)&&v.history.every(x=>fields(x,['version','action'])&&obj(x)&&Number.isSafeInteger(x.revision))&&(v.execution_ready===undefined||typeof v.execution_ready==='boolean');
export const validSource=(v:unknown)=>fields(v,['source_id','verification','publication_gate'])&&obj(v)&&typeof v.public_search_enabled==='boolean';
