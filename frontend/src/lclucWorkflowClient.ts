import {API_BASE} from './api';
const headers=():Record<string,string>=>{const token=sessionStorage.getItem('geoai_token');return token?{Authorization:`Bearer ${token}`} : {};};
const base=()=>new URL(API_BASE,window.location.href).origin+'/v1/lcluc/workflows';
export async function workflowFetch(suffix:string,body?:unknown){
 if(!/^(?:\/[a-f0-9]{64}(?:\/report)?)?$/.test(suffix))throw new Error('invalid path');
 const response=await fetch(base()+suffix,{method:body===undefined?'GET':'POST',headers:{...headers(),...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
 const text=await response.text();if(new TextEncoder().encode(text).length>8*1024*1024)throw new Error('response limit');
 return {status:response.status,value:JSON.parse(text) as unknown};
}
export async function workflowAsset(id:string,index:number,filename:string,live:()=>boolean){
 if(!/^[a-f0-9]{64}$/.test(id)||!Number.isSafeInteger(index)||index<0||index>127)throw new Error('invalid asset');
 const response=await fetch(base()+`/${id}/assets/${index}`,{headers:headers(),cache:'no-store'});
 if(!response.ok)throw new Error('asset unavailable');
 const blob=await response.blob();if(blob.size>256*1024*1024)throw new Error('asset limit');if(!live())return;
 const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=filename.split(/[\\/]/).pop()?.replace(/[\x00-\x1f\x7f]/g,'')||`lcluc-${id.slice(0,12)}-${index}`;document.body.appendChild(link);link.click();link.remove();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}

// GeoJSON preview reads a bounded byte snapshot, not an arbitrary asset URL.
export async function workflowGeoJSON(id:string,index:number,expectedSha:string,live:()=>boolean):Promise<unknown|undefined>{
 if(!/^[a-f0-9]{64}$/.test(id)||!Number.isSafeInteger(index)||index<0||index>127||!/^[a-f0-9]{64}$/.test(expectedSha))throw new Error('invalid map asset');
 if(!live())return;
 const response=await fetch(base()+`/${id}/assets/${index}`,{headers:headers(),cache:'no-store'});
 if(!response.ok||!response.body)throw new Error('map unavailable');
 const reader=response.body.getReader(),limit=8*1024*1024,chunks:Uint8Array[]=[];let size=0;
 try{
  const declared=response.headers.get('content-length');
  if(declared&&/^\d+$/.test(declared)&&Number(declared)>limit)throw new Error('map limit');
  while(true){const chunk=await reader.read();if(!live()){await reader.cancel();return;}if(chunk.done)break;size+=chunk.value.byteLength;if(size>limit)throw new Error('map limit');chunks.push(chunk.value);}
 }catch(error){try{await reader.cancel();}catch{/* Transport cancellation is best effort. */}throw error;}finally{reader.releaseLock();}
 if(!live())return;
 const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
 const digest=await crypto.subtle.digest('SHA-256',bytes),actual=Array.from(new Uint8Array(digest),n=>n.toString(16).padStart(2,'0')).join('');
 if(!live())return;if(actual!==expectedSha)throw new Error('map sha mismatch');
 const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);return JSON.parse(text) as unknown;
}
