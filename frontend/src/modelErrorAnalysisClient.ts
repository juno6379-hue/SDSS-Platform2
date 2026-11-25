import {API_BASE} from './api';
import type {ModelErrorRequest,ErrorArtifact} from './modelErrorAnalysisAdapter';
const headers=():Record<string,string>=>{const token=sessionStorage.getItem('geoai_token');return {'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})};};
const base=()=>new URL(API_BASE,window.location.href).origin+'/v1/models/error-analysis';
async function bytes(response:Response,limit:number,live:()=>boolean){
 if(!response.body)throw new Error('body unavailable');const reader=response.body.getReader(),chunks:Uint8Array[]=[];let count=0;
 try{const declared=response.headers.get('content-length');if(declared&&/^\d+$/.test(declared)&&Number(declared)>limit)throw new Error('body limit');while(true){const c=await reader.read();if(!live()){await reader.cancel();return;}if(c.done)break;count+=c.value.byteLength;if(count>limit)throw new Error('body limit');chunks.push(c.value);}}catch(error){try{await reader.cancel();}catch{/* Best effort transport cancellation. */}throw error;}finally{reader.releaseLock();}
 const result=new Uint8Array(count);let offset=0;for(const c of chunks){result.set(c,offset);offset+=c.byteLength;}return result;
}
export async function readModelErrorAnalysis(request:ModelErrorRequest,live:()=>boolean){
 if(!live())return;const response=await fetch(base(),{method:'POST',headers:headers(),body:JSON.stringify(request),cache:'no-store'});const raw=await bytes(response,8*1024*1024,live);if(!raw||!live())return;return {status:response.status,value:JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw)) as unknown};
}
export async function downloadModelErrorAnalysis(request:ModelErrorRequest,artifact:ErrorArtifact,live:()=>boolean){
 const names=['error-analysis.json','error-analysis-classes.csv','error-analysis-confusions.csv'];
 if(!Number.isSafeInteger(artifact.index)||artifact.index<0||artifact.index>2||artifact.filename!==names[artifact.index]||!/^[a-f0-9]{64}$/.test(artifact.sha256)||!Number.isSafeInteger(artifact.bytes)||artifact.bytes<1||artifact.bytes>8*1024*1024)throw new Error('invalid artifact');if(!live())return;
 const response=await fetch(base()+`/assets/${artifact.index}`,{method:'POST',headers:headers(),body:JSON.stringify(request),cache:'no-store'});if(!response.ok)throw new Error('asset unavailable');const raw=await bytes(response,artifact.bytes,live);if(!raw||!live())return;if(raw.byteLength!==artifact.bytes)throw new Error('asset size');const digest=await crypto.subtle.digest('SHA-256',raw);if(!live())return;const actual=Array.from(new Uint8Array(digest),n=>n.toString(16).padStart(2,'0')).join('');if(actual!==artifact.sha256)throw new Error('asset sha');
 const url=URL.createObjectURL(new Blob([raw],{type:artifact.index===0?'application/json':'text/csv'})),link=document.createElement('a');link.href=url;link.download=artifact.filename;document.body.appendChild(link);link.click();link.remove();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}
