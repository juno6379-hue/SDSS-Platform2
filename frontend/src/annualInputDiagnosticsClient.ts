import {API_BASE} from './api';
import {strictAnnualJSON} from './annualInputDiagnosticsAdapter';
import type {AnnualRequest} from './annualInputDiagnosticsAdapter';
export async function readAnnualInputDiagnostics(request:AnnualRequest,signal:AbortSignal,live:()=>boolean){
 if(!live())return;const token=sessionStorage.getItem('geoai_token');
 const response=await fetch(new URL(API_BASE,window.location.href).origin+'/v1/lcluc/input-diagnostics',{method:'POST',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify(request),cache:'no-store',signal});
 if(response.status===401){await response.body?.cancel();return {status:401,value:null};}
 if(!response.body)throw new Error('진단 응답을 읽을 수 없습니다.');const reader=response.body.getReader(),chunks:Uint8Array[]=[];let size=0;
 try{const length=response.headers.get('content-length');if(length&&/^\d+$/.test(length)&&Number(length)>16384)throw new Error('limit');while(true){const part=await reader.read();if(!live()){await reader.cancel();return;}if(part.done)break;size+=part.value.byteLength;if(size>16384)throw new Error('limit');chunks.push(part.value);}}
 catch(e){try{await reader.cancel();}catch{/* Cancellation only stops local transport. */}throw e;}finally{reader.releaseLock();}
 const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
 if(!live())return;return {status:response.status,value:strictAnnualJSON(new TextDecoder('utf-8',{fatal:true}).decode(bytes))};
}
