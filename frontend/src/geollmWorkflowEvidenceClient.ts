import {API_BASE} from './api';
import {evidenceWorkflowId,evidenceReadError,evidenceStatus,evidenceReport,strictEvidenceJSON} from './geollmWorkflowEvidenceAdapter.ts';
import type {WorkflowEvidence} from './geollmWorkflowEvidenceAdapter.ts';

export async function evidenceBytes(response:Response,signal:AbortSignal,live:()=>boolean):Promise<Uint8Array|undefined>{
 if(!response.body)throw new Error(evidenceReadError());const reader=response.body.getReader(),chunks:Uint8Array[]=[];let total=0;
 try{
  const length=response.headers.get('content-length');if(length&&/^[0-9]+$/.test(length)&&Number(length)>8*1024*1024)throw 0;
  while(true){const part=await reader.read();if(signal.aborted||!live()){await reader.cancel();return;}if(part.done)break;total+=part.value.byteLength;if(total>8*1024*1024)throw 0;chunks.push(part.value);}
 }catch{try{await reader.cancel();}catch{/* Transport cancellation is best effort. */}throw new Error(evidenceReadError());}finally{reader.releaseLock();}
 const bytes=new Uint8Array(total);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}return bytes;
}
export async function readWorkflowEvidence(id:string,signal:AbortSignal,live:()=>boolean):Promise<WorkflowEvidence|undefined>{
 if(!evidenceWorkflowId(id))throw new Error(evidenceReadError());if(signal.aborted||!live())return;
 const token=sessionStorage.getItem('geoai_token'),headers:Record<string,string>=token?{Authorization:`Bearer ${token}`} : {};
 const base=new URL(API_BASE,window.location.href).origin+'/v1/lcluc/workflows/'+id;
 async function get(url:string){
  const response=await fetch(url,{method:'GET',headers,cache:'no-store',redirect:'error',signal});
  if(response.status!==200){await response.body?.cancel();throw new Error(evidenceReadError(response.status));}return evidenceBytes(response,signal,live);
 }
 const statusBytes=await get(base);if(!statusBytes||signal.aborted||!live())return;
 const receipt=evidenceStatus(200,strictEvidenceJSON(new TextDecoder('utf-8',{fatal:true}).decode(statusBytes)),id);
 if(receipt.status!=='SUCCEEDED')return {receipt};
 const reportBytes=await get(base+'/report');if(!reportBytes||signal.aborted||!live())return;
 const view=await evidenceReport(reportBytes,receipt);if(signal.aborted||!live())return;return view;
}
