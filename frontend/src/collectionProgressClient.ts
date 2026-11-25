import {API_BASE} from './api';
import {strictEvidenceJSON} from './geollmWorkflowEvidenceAdapter.ts';
export async function readCollectionProgress(signal:AbortSignal,live:()=>boolean):Promise<unknown|undefined>{
 if(!live()||signal.aborted)return;const token=sessionStorage.getItem('geoai_token');
 const response=await fetch(API_BASE+'/data/collection-status',{method:'GET',headers:token?{Authorization:`Bearer ${token}`}:{},cache:'no-store',redirect:'error',signal});
 if(response.status!==200){await response.body?.cancel();throw new Error('현황 조회 실패');}
 if(!response.body)throw new Error('현황 응답 없음');const reader=response.body.getReader(),chunks:Uint8Array[]=[];let size=0;
 try{const declared=response.headers.get('content-length');if(declared&&/^[0-9]+$/.test(declared)&&Number(declared)>4*1024*1024)throw 0;while(true){const part=await reader.read();if(!live()||signal.aborted){await reader.cancel();return;}if(part.done)break;size+=part.value.byteLength;if(size>4*1024*1024)throw 0;chunks.push(part.value);}}
 catch{try{await reader.cancel();}catch{/* Best effort read cancellation. */}throw new Error('현황 응답 한도 또는 연결 확인 필요');}finally{reader.releaseLock();}
 if(!live()||signal.aborted)return;const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
 return strictEvidenceJSON(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
}
