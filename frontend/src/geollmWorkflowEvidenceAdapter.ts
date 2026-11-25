import {workflowResponse,parseWorkflowReport,workflowSha} from './lclucWorkflowAdapter.ts';
import type {WorkflowReceipt,WorkflowReport} from './lclucWorkflowAdapter.ts';
import {workflowTransitionStats} from './lclucTransitionAdapter.ts';

export const evidenceWorkflowId=(value:string)=>/^[a-f0-9]{64}$/.test(value);
export const evidenceReadError=(status?:number)=>status===401||status===403?'인증 또는 접근 권한을 확인하세요.':status===404?'저장된 local workflow 기록이 없습니다.':status===409?'완료된 보고서를 읽을 수 없는 실행 상태입니다.':status===503?'저장된 산출물 또는 서버 상태를 확인할 수 없습니다.':'근거 응답의 크기·SHA·형식 또는 연결을 확인하세요. 자동 재시도하지 않습니다.';

// JSON.parse alone discards duplicate keys. Parse bounded finite JSON first.
export function strictEvidenceJSON(text:string):unknown{
 let at=0,nodes=0;const fail=():never=>{throw new Error('invalid evidence JSON');};
 const whitespace=()=>{while(/[\t\n\r ]/.test(text[at]||'!'))at++;};
 function string():string{
  const start=at++;let escaped=false;
  while(at<text.length){const c=text[at++];if(escaped){escaped=false;continue;}if(c==='\\'){escaped=true;continue;}if(c==='"'){
   const result=JSON.parse(text.slice(start,at)) as string;if(result.length>1024*1024||/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(result))fail();return result;
  }if(c.charCodeAt(0)<32)fail();}return fail();
 }
 function value(depth:number):unknown{
  if(depth>32||++nodes>262144)fail();whitespace();const c=text[at];
  if(c==='"')return string();
  if(c==='{'){
   at++;whitespace();const out:Record<string,unknown>=Object.create(null);if(text[at]==='}'){at++;return out;}
   while(true){whitespace();if(text[at]!=='"')fail();const key=string();if(Object.hasOwn(out,key))fail();whitespace();if(text[at++]!==':')fail();out[key]=value(depth+1);whitespace();const end=text[at++];if(end==='}')return out;if(end!==',')fail();}
  }
  if(c==='['){at++;whitespace();const out:unknown[]=[];if(text[at]===']'){at++;return out;}while(true){out.push(value(depth+1));whitespace();const end=text[at++];if(end===']')return out;if(end!==',')fail();}}
  for(const [word,literal]of [['true',true],['false',false],['null',null]] as const){if(text.slice(at,at+word.length)===word){at+=word.length;return literal;}}
  const match=/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(text.slice(at));if(!match)fail();at+=match![0].length;const number=Number(match![0]);if(!Number.isFinite(number)||(Number.isInteger(number)&&!Number.isSafeInteger(number)))fail();return number;
 }
 if(text.length>8*1024*1024)fail();const result=value(0);whitespace();if(at!==text.length)fail();return result;
}

export function evidenceStatus(status:number,value:unknown,id:string):WorkflowReceipt{
 if(!evidenceWorkflowId(id)||status!==200)throw new Error(evidenceReadError(status));
 try{return workflowResponse(status,value,{id,readOnly:true});}catch{throw new Error(evidenceReadError());}
}
export function evidenceReportPin(receipt:WorkflowReceipt):string{
 if(receipt.status!=='SUCCEEDED'||!receipt.report_path)throw new Error(evidenceReadError());
 const path=receipt.report_path.replaceAll('\\','/');const matching=receipt.artifacts?.filter(a=>a.path.replaceAll('\\','/')===path);
 if(matching?.length!==1||!workflowSha(matching[0].sha256))throw new Error(evidenceReadError());return matching[0].sha256;
}
export type WorkflowEvidence={receipt:WorkflowReceipt;report?:WorkflowReport;rawReport?:unknown;reportSha?:string};
export async function evidenceReport(bytes:Uint8Array,receipt:WorkflowReceipt):Promise<WorkflowEvidence>{
 const expected=evidenceReportPin(receipt);if(bytes.byteLength>8*1024*1024)throw new Error(evidenceReadError());
 const digest=await crypto.subtle.digest('SHA-256',new Uint8Array(bytes)),actual=Array.from(new Uint8Array(digest),n=>n.toString(16).padStart(2,'0')).join('');
 if(actual!==expected)throw new Error(evidenceReadError());
 try{
  const rawReport=strictEvidenceJSON(new TextDecoder('utf-8',{fatal:true}).decode(bytes));const report=parseWorkflowReport(rawReport,receipt);if(!report)throw 0;
  for(const change of report.changes)workflowTransitionStats(receipt,rawReport,change.pair);
  return {receipt,report,rawReport,reportSha:actual};
 }catch{throw new Error(evidenceReadError());}
}

export class WorkflowEvidenceFlight{
 private generation=0;private pending=false;private controller?:AbortController;
 invalidate(){this.generation++;this.pending=false;this.controller?.abort();this.controller=undefined;}
 async run(id:string,route:string,h:{current:()=>{id:string;route:string};work:(signal:AbortSignal,live:()=>boolean)=>Promise<void>;failure:(text:string)=>void;settled:()=>void}){
  if(this.pending)return;this.pending=true;const generation=this.generation,controller=new AbortController();this.controller=controller;
  const live=()=>generation===this.generation&&!controller.signal.aborted&&h.current().id===id&&h.current().route===route;
  try{await h.work(controller.signal,live);}catch(error){if(live())h.failure(error instanceof Error&&Object.values([401,403,404,409,503,undefined]).some(status=>error.message===evidenceReadError(status))?error.message:evidenceReadError());}
  finally{if(live()){this.pending=false;this.controller=undefined;h.settled();}}
 }
}
