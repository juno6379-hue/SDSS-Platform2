import {modelErrorPins} from './modelErrorAnalysisAdapter.ts';
import {modelVersionIssue} from './modelVersionRegistrationAdapter.ts';
type Row=Record<string,unknown>;
export type FixedRef={id:string;version:string;sha256:string};
export type AnnualRow={year:number;image_ref:FixedRef;evidence_ref:FixedRef;metadata_ref:FixedRef;quality_report_ref:FixedRef;mask_ref:FixedRef};
export type AnnualRequest={schema_version:1;capability:'landcover.input_diagnostics';model_ref:FixedRef;training_report_sha256:string;requested_years:AnnualRow[];policy:{schema_version:1;minimum_valid_numerator:number;minimum_valid_denominator:number;comparison:'greater_than_or_equal'}};
export type Counts={valid_pixels:number;invalid_pixels:number;total_pixels:number};
export type AnnualSummary={schema_version:1;scope:string;status:string;request_sha256:string|null;blocking_stage:string|null;issue:{code:string;year:number|null}|null;per_year_observations:{year:number;status:'NOT_CHECKED'|'MET'|'NOT_MET';counts:Counts|null;policy_met:boolean|null}[];caller_policy_evaluated:boolean;caller_policy_met:boolean;artifact_bytes_verified:boolean};
const need=(v:unknown)=>{if(!v)throw new Error('입력 또는 진단 응답의 고정 참조·형식을 확인할 수 없습니다.');};
const exact=(v:unknown,ks:string[]):v is Row=>!!v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===ks.length&&ks.every(k=>Object.hasOwn(v,k));
const integer=(v:unknown,min:number,max:number):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=min&&v<=max;
const sha=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const roles=['image_ref','evidence_ref','metadata_ref','quality_report_ref','mask_ref'] as const;
export const annualFalseFields=['quality_report_verified','quality_mask_verified','mask_semantics_verified','registry_aoi_verified','source_authority_verified','scientific_accuracy_validated','execution_authorized','state_dict_verified','workflow_supported'];
export const annualModelPins=modelErrorPins;
// Bounded recursive descent retains duplicate keys and integer lexical typing.
export function strictAnnualJSON(text:string):unknown{
 need(new TextEncoder().encode(text).length<=16384);let p=0,nodes=0;
 const ws=()=>{while(/[\x20\t\r\n]/.test(text[p]||'!'))p++;};
 const string=()=>{const start=p++;let escape=false;while(p<text.length){const c=text[p++];if(!escape&&c==='"'){const s=JSON.parse(text.slice(start,p)) as string;need(Array.from(s).length<=512&&Array.from(s).every(c=>{const n=c.codePointAt(0)!;return n<0xd800||n>0xdfff;}));return s;}if(!escape&&c==='\\')escape=true;else escape=false;}throw new Error('JSON');};
 const value=(depth:number):unknown=>{need(++nodes<=4096&&depth<=16);ws();const c=text[p];if(c==='"')return string();if(c==='{'||c==='['){p++;const obj:Row=Object.create(null),arr:unknown[]=[];ws();if(text[p]===(c==='{'?'}':']')){p++;return c==='{'?obj:arr;}while(true){if(c==='{'){ws();need(text[p]==='"');const key=string();need(++nodes<=4096&&!Object.hasOwn(obj,key));ws();need(text[p++]===':');obj[key]=value(depth+1);}else arr.push(value(depth+1));ws();const end=text[p++];if(end===(c==='{'?'}':']'))break;need(end===',');}return c==='{'?obj:arr;}for(const [token,v]of [['true',true],['false',false],['null',null]] as const){if(text.startsWith(token,p)){p+=token.length;return v;}}const m=/^-?(?:0|[1-9][0-9]*)/.exec(text.slice(p));need(m);const token=m![0];need(token.replace('-','').length<=16);p+=token.length;const v=Number(token);need(Number.isSafeInteger(v));return v;};
 const result=value(0);ws();need(p===text.length);return result;
}
const refText=(v:unknown):v is string=>typeof v==='string'&&Array.from(v).length>=1&&Array.from(v).length<=256&&!!v.trim()&&Array.from(v).every(c=>{const n=c.codePointAt(0)!;return n>=32&&!(n>=127&&n<=159)&&!(n>=0xd800&&n<=0xdfff);});
const ref=(v:unknown):v is FixedRef=>exact(v,['id','version','sha256'])&&refText(v.id)&&!modelVersionIssue(v.version)&&sha(v.sha256);
export function prepareAnnualRequest(model:unknown,yearsText:string,numerator:string,denominator:string):AnnualRequest{
 const pins=annualModelPins(model);need(pins);need(/^(0|[1-9][0-9]*)$/.test(numerator)&&/^[1-9][0-9]*$/.test(denominator));const num=Number(numerator),den=Number(denominator);need(integer(den,1,1000000)&&integer(num,0,den));
 const rows=strictAnnualJSON(yearsText);need(Array.isArray(rows)&&rows.length>=2&&rows.length<=6);let previous=0;const images=new Set<string>();
 for(const item of rows as unknown[]){need(exact(item,['year',...roles]));const r=item as Row;need(integer(r.year,1900,2200)&&r.year>previous&&roles.every(k=>ref(r[k])));previous=r.year as number;const keys=roles.map(k=>{const a=r[k] as FixedRef;return JSON.stringify([a.id,a.version]);});need(new Set(keys.slice(0,3)).size===3&&new Set([keys[0],keys[3],keys[4]]).size===3&&!images.has(keys[0]));images.add(keys[0]);}
 const request:AnnualRequest={schema_version:1,capability:'landcover.input_diagnostics',model_ref:{...pins!.model_ref},training_report_sha256:pins!.training_report_sha256,requested_years:rows as AnnualRow[],policy:{schema_version:1,minimum_valid_numerator:num,minimum_valid_denominator:den,comparison:'greater_than_or_equal'}};need(new TextEncoder().encode(JSON.stringify(request)).length<=16384);return request;
}
function canonical(v:unknown):string{if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical((v as Row)[k])).join(',')+'}';return JSON.stringify(v);}
export async function annualRequestSHA(request:AnnualRequest){const raw=new TextEncoder().encode(canonical(request));return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),n=>n.toString(16).padStart(2,'0')).join('');}
export function parseAnnualSummary(value:unknown,request:AnnualRequest,digest:string):AnnualSummary{
 need(exact(value,['schema_version','scope','status','request_sha256','blocking_stage','issue','per_year_observations','caller_policy_evaluated','caller_policy_met','artifact_bytes_verified',...annualFalseFields]));const v=value as Row;need(v.schema_version===1&&v.scope==='LCLUC_ANNUAL_DIAGNOSTIC_SUMMARY_READ_ONLY'&&annualFalseFields.every(k=>v[k]===false)&&['caller_policy_evaluated','caller_policy_met','artifact_bytes_verified'].every(k=>typeof v[k]==='boolean')&&Array.isArray(v.per_year_observations));
 const rows=v.per_year_observations as Row[],emptyFlags=v.caller_policy_evaluated===false&&v.caller_policy_met===false&&v.artifact_bytes_verified===false;
 const issue=(code:string,year:number|null)=>exact(v.issue,['code','year'])&&v.issue.code===code&&v.issue.year===year;
 if(v.status==='INVALID_REQUEST'){need(v.request_sha256===null&&v.blocking_stage==='REQUEST'&&issue('INVALID_REQUEST',null)&&rows.length===0&&emptyFlags);return value as AnnualSummary;}
 need(sha(digest)&&v.request_sha256===digest);
 if(v.status==='OUTPUT_INVALID'){need(v.blocking_stage==='OUTPUT'&&issue('OUTPUT_INVALID',null)&&rows.length===0&&emptyFlags);return value as AnnualSummary;}
 need(rows.length===request.requested_years.length&&rows.every((r,i)=>exact(r,['year','status','counts','policy_met'])&&r.year===request.requested_years[i].year));
 if(v.status==='SOURCE_BLOCKED'){const i=v.issue as Row;need(['ANNUAL','COUNTS'].includes(v.blocking_stage as string)&&exact(i,['code','year'])&&i.code==='SOURCE_BLOCKED'&&(i.year===null||request.requested_years.some(r=>r.year===i.year))&&emptyFlags&&rows.every(r=>r.status==='NOT_CHECKED'&&r.counts===null&&r.policy_met===null));return value as AnnualSummary;}
 need(v.status==='CALLER_POLICY_MET_UNVERIFIED'||v.status==='CALLER_POLICY_NOT_MET');let first:number|null=null;
 for(const r of rows){need(exact(r.counts,['valid_pixels','invalid_pixels','total_pixels']));const c=r.counts as Row;need(integer(c.total_pixels,1,1048576)&&integer(c.valid_pixels,0,c.total_pixels as number)&&integer(c.invalid_pixels,0,c.total_pixels as number)&&Number(c.valid_pixels)+Number(c.invalid_pixels)===c.total_pixels);const met=Number(c.valid_pixels)*request.policy.minimum_valid_denominator>=Number(c.total_pixels)*request.policy.minimum_valid_numerator;need(r.policy_met===met&&r.status===(met?'MET':'NOT_MET'));if(!met&&first===null)first=r.year as number;}
 const met=first===null;need(v.caller_policy_evaluated===true&&v.caller_policy_met===met&&v.artifact_bytes_verified===met&&v.status===(met?'CALLER_POLICY_MET_UNVERIFIED':'CALLER_POLICY_NOT_MET')&&(met?v.issue===null&&v.blocking_stage===null:v.blocking_stage==='POLICY'&&issue('CALLER_POLICY_NOT_MET',first)));return value as AnnualSummary;
}
const errors:Record<string,[number,string]>={AUTH_CONFIGURATION_REQUIRED:[503,'서버 진단 인증 설정이 필요합니다. 관리자 설정을 확인하세요.'],AUTH_REQUIRED:[401,'인증 토큰을 확인하세요.'],REQUEST_TOO_LARGE:[413,'요청은 UTF-8 16KiB 이내여야 합니다.'],UNSUPPORTED_MEDIA_TYPE:[415,'JSON 요청 형식을 확인하세요.'],DIAGNOSTIC_BUSY:[429,'다른 진단이 실행 중입니다. 완료 후 직접 다시 조회하세요.'],RESOURCE_UNAVAILABLE:[503,'진단 자료를 읽을 수 없습니다. 자동 재시도하지 않습니다.']};
export function annualHTTPResponse(status:number,value:unknown,request:AnnualRequest,digest:string){
 if(status===401)throw new Error('인증 토큰을 확인하세요.');
 if([200,422,503].includes(status)&&exact(value,['schema_version','scope','status','request_sha256','blocking_stage','issue','per_year_observations','caller_policy_evaluated','caller_policy_met','artifact_bytes_verified',...annualFalseFields])){const result=parseAnnualSummary(value,request,digest);need(status===(result.status==='INVALID_REQUEST'?422:result.status==='OUTPUT_INVALID'?503:200));return result;}
 need(exact(value,['schema_version','scope','error'])&&value.schema_version===1&&value.scope==='LCLUC_ANNUAL_DIAGNOSTIC_HTTP_ERROR'&&exact(value.error,['code'])&&typeof value.error.code==='string'&&Object.hasOwn(errors,value.error.code));const e=errors[((value as Row).error as Row).code as string];need(e[0]===status);throw new Error(e[1]);
}
export class AnnualDiagnosticFlight{private generation=0;private pending=false;invalidate(){this.generation++;this.pending=false;}async run(identity:string,route:string,h:{current:()=>{identity:string;route:string};work:(live:()=>boolean)=>Promise<void>;failure:(e:unknown)=>void;settled:()=>void}){if(this.pending)return;this.pending=true;const g=this.generation,live=()=>g===this.generation&&h.current().identity===identity&&h.current().route===route;try{await h.work(live);}catch(e){if(live())h.failure(e);}finally{if(live()){this.pending=false;h.settled();}}}}
