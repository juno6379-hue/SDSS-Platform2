import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
import {evidenceWorkflowId,strictEvidenceJSON,evidenceStatus,evidenceReportPin,evidenceReport,evidenceReadError,WorkflowEvidenceFlight} from './geollmWorkflowEvidenceAdapter.ts';
const fixture=()=>JSON.parse(readFileSync(new URL('../../evidence/integration/lcluc-change-map-generated-fixture-20261018.json',import.meta.url),'utf8'));
async function prepared(){const f=fixture();f.receipt.replayed=true;const raw=new TextEncoder().encode(JSON.stringify(f.report));const digest=Buffer.from(await crypto.subtle.digest('SHA-256',raw)).toString('hex');f.receipt.artifacts.find(a=>a.path.replaceAll('\\','/')===f.receipt.report_path.replaceAll('\\','/')).sha256=digest;return {...f,raw,digest};}

test('manual fixed ID is exact lowercase64; existing GET receipt parser requires replay and false claims',async()=>{
 const f=await prepared();assert(evidenceWorkflowId(f.receipt.id));for(const value of ['',f.receipt.id+' ',f.receipt.id.toUpperCase(),'../'+f.receipt.id,'x'.repeat(64)])assert(!evidenceWorkflowId(value));
 assert.equal(evidenceStatus(200,f.receipt,f.receipt.id).id,f.receipt.id);
 for(const change of [r=>r.replayed=false,r=>r.id='a'.repeat(64),r=>r.scientific_accuracy_validated=true,r=>r.standard_gmais_result=0,r=>r.extra='PRIVATE']){const r=structuredClone(f.receipt);change(r);assert.throws(()=>evidenceStatus(200,r,f.receipt.id));}
});
test('strict finite JSON catches duplicate escaped keys, UTF16 errors, malformed numbers, depth and nodes',()=>{
 for(const text of ['{"x":1,"x":2}','{"x":1,"\\u0078":2}','[NaN]','[Infinity]','[1e999]','[9007199254740992]','["\\ud800"]','["\\udc00"]','[1,]','{"a":1,}','[] trailing','[01]','['.repeat(34)+'0'+']'.repeat(34),' '.repeat(8*1024*1024+1),'['+Array(262145).fill('0').join(',')+']'])assert.throws(()=>strictEvidenceJSON(text));
 const value=strictEvidenceJSON('{"quote":"a\\\"[]🌏","decimal":0.125,"__proto__":{"x":1}}');assert.equal(value.decimal,.125);assert.equal(value.quote,'a"[]🌏');assert.equal(Object.getPrototypeOf(value),null);assert.equal({}.x,undefined);
});
test('same report raw SHA, Windows paths, model/years and all transition matrices are verified',async()=>{
 const f=await prepared(),view=await evidenceReport(f.raw,evidenceStatus(200,f.receipt,f.receipt.id));assert.equal(view.reportSha,f.digest);assert.equal(view.report.changes.length,3);assert.equal(view.report.changes.find(c=>c.pair==='2021-2022').area,0);
 assert.equal(evidenceReportPin(f.receipt),f.digest);const tamper=f.raw.slice();tamper[0]=32;await assert.rejects(()=>evidenceReport(tamper,f.receipt));
 for(const edit of [r=>r.years.reverse(),r=>r.checkpoint_sha256='a'.repeat(64),r=>r.changes['2020-2021'].transition_pixels[1][2]++,r=>r.changes['2020-2021'].changed_area_m2++,r=>r.report_path='PRIVATE']){
  const r=structuredClone(f.report);edit(r);const raw=new TextEncoder().encode(JSON.stringify(r)),receipt=structuredClone(f.receipt);receipt.artifacts.find(a=>a.path===receipt.report_path).sha256=Buffer.from(await crypto.subtle.digest('SHA-256',raw)).toString('hex');await assert.rejects(()=>evidenceReport(raw,receipt));
 }
 const invalid=new Uint8Array([255]);const r=structuredClone(f.receipt);r.artifacts.find(a=>a.path===r.report_path).sha256=Buffer.from(await crypto.subtle.digest('SHA-256',invalid)).toString('hex');await assert.rejects(()=>evidenceReport(invalid,r));
});
test('duplicate report pin or poisoned HTTP/error data never becomes displayed results',async()=>{
 const f=await prepared();const r=structuredClone(f.receipt);r.artifacts.push(r.artifacts.find(a=>a.path===r.report_path));assert.throws(()=>evidenceReportPin(r));
 for(const status of [401,403,404,409,500,503])assert.throws(()=>evidenceStatus(status,{detail:'PRIVATE_TOKEN'},f.receipt.id),e=>!e.message.includes('PRIVATE'));
});
const defer=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
test('synchronous pending, identity/route/edit/back/unmount invalidation and old finally isolation',async()=>{
 for(const change of ['none','id','route','invalidate','reject']){
  const flight=new WorkflowEvidenceFlight(),d=defer(),events=[];let current={id:'id',route:'route'},signal;
  const h={current:()=>current,work:async(s,live)=>{signal=s;events.push('GET');await d.promise;if(live())events.push('result');},failure:()=>events.push('error'),settled:()=>events.push('settled')};
  const first=flight.run('id','route',h);await flight.run('id','route',h);
  if(change==='id')current={id:'other',route:'route'};if(change==='route')current={id:'id',route:'other'};if(change==='invalidate'||change==='reject')flight.invalidate();
  if(change==='reject')d.reject(new Error('PRIVATE'));else d.resolve();await first;
  assert.deepEqual(events,change==='none'?['GET','result','settled']:['GET']);if(change==='invalidate'||change==='reject')assert(signal.aborted);
 }
 const f=new WorkflowEvidenceFlight(),a=defer(),b=defer(),events=[];const h=d=>({current:()=>({id:'id',route:'route'}),work:async()=>{await d.promise;},failure:()=>events.push('error'),settled:()=>events.push(d===a?'old':'new')});
 const old=f.run('id','route',h(a));f.invalidate();const fresh=f.run('id','route',h(b));a.resolve();await old;assert.deepEqual(events,[]);b.resolve();await fresh;assert.deepEqual(events,['new']);
});

const adapterURL=new URL('./geollmWorkflowEvidenceAdapter.ts',import.meta.url).href;
const clientSource=readFileSync(new URL('./geollmWorkflowEvidenceClient.ts',import.meta.url),'utf8').replace("import {API_BASE} from './api';","const API_BASE='http://127.0.0.1:8003/api';").replace("from './geollmWorkflowEvidenceAdapter.ts'",`from '${adapterURL}'`);
const client=await import('data:text/javascript;base64,'+Buffer.from(stripTypeScriptTypes(clientSource)).toString('base64'));
function globals(values){const prior=Object.fromEntries(Object.keys(values).map(k=>[k,Object.getOwnPropertyDescriptor(globalThis,k)]));Object.assign(globalThis,values);return()=>{for(const [k,d]of Object.entries(prior)){if(d)Object.defineProperty(globalThis,k,d);else delete globalThis[k];}};}

test('manual authenticated fixed GET only: success status then report with atomic pinned view',async()=>{
 const f=await prepared(),calls=[];const restore=globals({window:{location:{href:'http://127.0.0.1:5180/'}},sessionStorage:{getItem:key=>key==='geoai_token'?'fixture-token':null},fetch:async(url,options)=>{calls.push([url,options]);return new Response(url.endsWith('/report')?f.raw:JSON.stringify(f.receipt),{status:200});}});
 try{const view=await client.readWorkflowEvidence(f.receipt.id,new AbortController().signal,()=>true);assert.equal(view.reportSha,f.digest);assert.equal(calls.length,2);assert.equal(calls[0][0],`http://127.0.0.1:8003/v1/lcluc/workflows/${f.receipt.id}`);assert.equal(calls[1][0],calls[0][0]+'/report');for(const [,o]of calls){assert.equal(o.method,'GET');assert.equal(o.cache,'no-store');assert.equal(o.redirect,'error');assert.equal(o.headers.Authorization,'Bearer fixture-token');assert.equal(o.body,undefined);}}
 finally{restore();}
});
test('RUNNING/FAILED use one GET, HTTP failures and stale result never fetch next report',async()=>{
 const f=await prepared();for(const mode of ['RUNNING','FAILED','404','503','stale']){
  const calls=[];let live=true;const receipt=structuredClone(f.receipt);if(mode==='RUNNING'||mode==='FAILED'){
   receipt.status=mode;receipt.artifacts=[];delete receipt.report_path;delete receipt.admission_pins;if(mode==='RUNNING')delete receipt.finished_at;else receipt.issue='LOCAL_EXECUTION_FAILED';
  }
  const restore=globals({window:{location:{href:'http://127.0.0.1:5180/'}},sessionStorage:{getItem:()=>null},fetch:async(url)=>{calls.push(url);if(mode==='stale')live=false;return new Response(mode==='404'||mode==='503'?'{"detail":"PRIVATE"}':JSON.stringify(receipt),{status:mode==='404'?404:mode==='503'?503:200});}});
  try{if(mode==='404'||mode==='503')await assert.rejects(()=>client.readWorkflowEvidence(receipt.id,new AbortController().signal,()=>live),e=>!e.message.includes('PRIVATE'));else{const result=await client.readWorkflowEvidence(receipt.id,new AbortController().signal,()=>live);if(mode==='stale')assert.equal(result,undefined);else{assert.equal(result.receipt.status,mode);assert.equal(result.report,undefined);}}assert.equal(calls.length,1);}finally{restore();}
 }
});
test('bounded stream cancels declared/cumulative overflow and stale bytes, releases lock',async()=>{
 for(const mode of ['declared','overflow','stale']){let reads=0,cancel=0,release=0,live=true;
  const response={headers:{get:()=>mode==='declared'?String(8*1024*1024+1):null},body:{getReader:()=>({read:async()=>{reads++;if(mode==='stale')live=false;return {done:false,value:new Uint8Array(mode==='overflow'?8*1024*1024+1:1)};},cancel:async()=>cancel++,releaseLock:()=>release++})}};
  if(mode==='stale')assert.equal(await client.evidenceBytes(response,new AbortController().signal,()=>live),undefined);else await assert.rejects(()=>client.evidenceBytes(response,new AbortController().signal,()=>live));assert.equal(cancel,1);assert.equal(release,1);if(mode==='declared')assert.equal(reads,0);
 }
});
test('component mount preserves legacy query; no auto request and local id never goes to legacy onReviewResult',()=>{
 const panel=readFileSync(new URL('./GeoWorkflowEvidence.tsx',import.meta.url),'utf8'),query=readFileSync(new URL('./GeoQuery.tsx',import.meta.url),'utf8');
 assert.match(query,/kind === 'evidence' && <GeoWorkflowEvidence\/>/);assert.match(query,/onReviewResult\(String\(record.id\)\)/);assert(!panel.includes('onReviewResult'));assert(!panel.includes('sessionStorage'));assert(!panel.includes('setInterval'));assert(!panel.includes('POST'));
 assert.match(panel,/useState\(''\)/);assert.match(panel,/onClick=\{\(\)=>void read\(\)\}/);assert.match(panel,/review&&view.rawReport!==undefined/);assert.match(panel,/LclucWorkflowChangeMap/);assert.match(panel,/hashchange/);assert.match(panel,/popstate/);assert.match(panel,/flight.current.invalidate\(\)/);
});
