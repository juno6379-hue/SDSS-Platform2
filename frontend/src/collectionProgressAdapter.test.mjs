import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
import {parseCollectionProgress,parseCandidateProgress,parseBareReview,parseBudgetProgress,CollectionProgressFlight} from './collectionProgressAdapter.ts';
function fixture(){
 const provinces=['south_sulawesi','gorontalo','southeast_sulawesi','east_java','banten','west_java'];
 const rows=provinces.map((province,index)=>({province,split:index<4?'train':index===4?'val':'test',physical:14,eligible:12,year_counts:Object.fromEntries(Array.from({length:6},(_,i)=>[String(2020+i),2])),cell_gap:6}));
 return {available:true,source_manifest_sha256:'a'.repeat(64),count_basis:'manifest_quality_status',physical_total:84,eligible_total:72,ineligible_total:12,eligible_target:100,eligible_target_gap:28,cell_floor:3,cell_gap_total:36,rows,minimum_valid_fraction:.8,minimum_province_fraction:.95,
  class_quality:{required_fraction:.005,minimum_contributing_patches:5,minimum_pixels_per_contributing_patch:256,minimum_pixels_per_split:256,max_dominance:.9,bare_by_split:{train:{pixels:300,ratio:.001,contributing_patches:0},val:{pixels:209,ratio:.0001,contributing_patches:0},test:{pixels:256,ratio:null,contributing_patches:1}},scene_split_conflicts:['explicit-shared-scene']},native_raster_reverified:false,learning_ready:false,scientific_accuracy_validated:false};
}
test('live totals and targets are derived from response, not production hardcoded numbers',()=>{
 const raw=fixture(),view=parseCollectionProgress(raw);assert.equal(view.physical,84);assert.equal(view.eligible,72);assert.equal(view.targetGap,28);assert.equal(view.cellGap,36);assert.deepEqual(view.splits,{train:48,val:12,test:12});assert.equal(view.bare.val.pixels,209);assert.equal(view.minPixelsPerSplit-view.bare.val.pixels,47);
 raw.rows[0].year_counts['2020']++;raw.rows[0].eligible++;raw.rows[0].physical++;raw.rows[0].cell_gap--;raw.physical_total++;raw.eligible_total++;raw.eligible_target_gap--;raw.cell_gap_total--;
 const changed=parseCollectionProgress(raw);assert.equal(changed.physical,85);assert.equal(changed.eligible,73);assert.equal(changed.cellGap,35);assert.equal(changed.splits.train,49);
});
test('missing data is unknown and contaminated sums, typed counters and false flags are rejected',()=>{
 assert.equal(parseCollectionProgress(undefined),undefined);assert.equal(parseCollectionProgress({available:false,learning_ready:false}),undefined);
 for(const edit of [v=>v.physical_total++,v=>v.eligible_target_gap++,v=>v.rows[0].eligible++,v=>v.rows[0].cell_gap++,v=>v.rows[0].year_counts['2020']=true,v=>v.rows[0].physical=-1,v=>v.rows[0].split='other',v=>v.rows[1].province=v.rows[0].province,v=>delete v.rows[0].year_counts['2020'],v=>v.rows.pop(),v=>v.class_quality.bare_by_split.val.pixels=true,v=>v.class_quality.bare_by_split.val.ratio=NaN,v=>v.source_manifest_sha256='A'.repeat(64),v=>v.learning_ready=true,v=>v.native_raster_reverified=true,v=>v.scientific_accuracy_validated=0]){
  const value=fixture();edit(value);assert.throws(()=>parseCollectionProgress(value));
 }
});
test('detached rows and bare metrics keep zero, null and original declaration boundaries',()=>{
 const raw=fixture(),before=structuredClone(raw),view=parseCollectionProgress(raw);assert.equal(view.bare.train.contributingPatches,0);assert.equal(view.bare.test.ratio,null);view.rows[0].yearCounts['2020']=999;view.bare.val.pixels=999;view.sceneConflicts.push('other');assert.deepEqual(raw,before);
});
test('pinned candidate is separate from current raw cohort, unavailable never becomes zero and pins/types are checked',()=>{
 const candidate={available:true,scope:'PINNED_CANDIDATE_COHORT_NOT_AUTOMATIC_CURRENT_COLLECTION',source_manifest_sha256:'b'.repeat(64),eligible_total:54,by_split:{train:30,val:10,test:14},ready_for_training:false,blocker_count:4,source_pins_match:true,source_matches_current_manifest:false,source_report:'first-group-priority/candidate-qa.json',recorded_at:'2026-10-18T10:01:19+09:00',scene_split_conflicts:[],scientific_accuracy_validated:false};
 const raw=parseCollectionProgress(fixture()),view=parseCandidateProgress(candidate);assert.equal(raw.eligible,72);assert.equal(view.eligible,54);assert.equal(view.matchesCurrent,false);assert.equal(view.blockers,4);assert.equal(parseCandidateProgress({available:false,ready_for_training:false}),undefined);
 for(const edit of [v=>v.by_split.val++,v=>v.source_pins_match=false,v=>v.ready_for_training=true,v=>v.blocker_count=true,v=>v.scientific_accuracy_validated=0,v=>v.source_matches_current_manifest=null,v=>v.scene_split_conflicts=['unresolved'],v=>v.source_report='../private',v=>v.source_manifest_sha256='bad']){const bad=structuredClone(candidate);edit(bad);assert.throws(()=>parseCandidateProgress(bad));}
 view.splits.val=999;assert.equal(candidate.by_split.val,10);
});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
test('synchronous duplicate guard, route/back/unmount/refresh generations discard old success/error/finally',async()=>{
 for(const mode of ['normal','route','invalidate','reject']){const flight=new CollectionProgressFlight(),d=deferred(),events=[];let route='current',signal;
  const handlers={route:()=>route,work:async(s,live)=>{events.push('GET');signal=s;await d.promise;if(live())events.push('result');},error:()=>events.push('error'),settled:()=>events.push('settled')};
  const p=flight.run('current',handlers);await flight.run('current',handlers);if(mode==='route')route='other';if(mode==='invalidate'||mode==='reject')flight.invalidate();if(mode==='reject')d.reject(new Error('private'));else d.resolve();await p;assert.deepEqual(events,mode==='normal'?['GET','result','settled']:['GET']);if(mode==='invalidate'||mode==='reject')assert(signal.aborted);
 }
});
const strictURL=new URL('./geollmWorkflowEvidenceAdapter.ts',import.meta.url).href;
const source=readFileSync(new URL('./collectionProgressClient.ts',import.meta.url),'utf8').replace("import {API_BASE} from './api';","const API_BASE='http://127.0.0.1:8002/api';").replace("from './geollmWorkflowEvidenceAdapter.ts'",`from '${strictURL}'`);
const client=await import('data:text/javascript;base64,'+Buffer.from(stripTypeScriptTypes(source)).toString('base64'));
test('GET existing real endpoint preserves token/cache and parses dynamic response with no writes',async()=>{
 const saved=Object.fromEntries(['fetch','sessionStorage'].map(k=>[k,Object.getOwnPropertyDescriptor(globalThis,k)])),calls=[];
 try{Object.assign(globalThis,{sessionStorage:{getItem:key=>key==='geoai_token'?'fixture-token':null},fetch:async(url,options)=>{calls.push([url,options]);return new Response(JSON.stringify({collection_targets:fixture(),recorded_at:'2026-10-18'}),{status:200});}});
  const response=await client.readCollectionProgress(new AbortController().signal,()=>true);assert.equal(parseCollectionProgress(response.collection_targets).eligible,72);assert.equal(calls.length,1);assert.equal(calls[0][0],'http://127.0.0.1:8002/api/data/collection-status');assert.equal(calls[0][1].method,'GET');assert.equal(calls[0][1].headers.Authorization,'Bearer fixture-token');assert.equal(calls[0][1].cache,'no-store');assert.equal(calls[0][1].redirect,'error');assert.equal(calls[0][1].body,undefined);
  globalThis.fetch=async()=>new Response('{"detail":"PRIVATE"}',{status:401});await assert.rejects(()=>client.readCollectionProgress(new AbortController().signal,()=>true),e=>!e.message.includes('PRIVATE'));
 }finally{for(const [k,d]of Object.entries(saved)){if(d)Object.defineProperty(globalThis,k,d);else delete globalThis[k];}}
});
test('bounded reader cancels declared/cumulative overflow and stale response without rendering',async()=>{
 const saved=Object.fromEntries(['fetch','sessionStorage'].map(k=>[k,Object.getOwnPropertyDescriptor(globalThis,k)]));
 try{for(const mode of ['declared','overflow','stale']){let live=true,reads=0,cancels=0,releases=0;Object.assign(globalThis,{sessionStorage:{getItem:()=>null},fetch:async()=>({status:200,headers:{get:()=>mode==='declared'?String(4*1024*1024+1):null},body:{getReader:()=>({read:async()=>{reads++;if(mode==='stale')live=false;return {done:false,value:new Uint8Array(mode==='overflow'?4*1024*1024+1:1)};},cancel:async()=>cancels++,releaseLock:()=>releases++})}})});
  if(mode==='stale')assert.equal(await client.readCollectionProgress(new AbortController().signal,()=>live),undefined);else await assert.rejects(()=>client.readCollectionProgress(new AbortController().signal,()=>live));assert.equal(cancels,1);assert.equal(releases,1);if(mode==='declared')assert.equal(reads,0);
 }}finally{for(const [k,d]of Object.entries(saved)){if(d)Object.defineProperty(globalThis,k,d);else delete globalThis[k];}}
});
test('collection view reuses parent GET while model review has standalone loader; no hardcoded inventory',()=>{
 const component=readFileSync(new URL('./CollectionProgress.tsx',import.meta.url),'utf8'),collection=readFileSync(new URL('./CollectionStatus.tsx',import.meta.url),'utf8'),model=readFileSync(new URL('./ModelReview.tsx',import.meta.url),'utf8');
 assert.match(collection,/CollectionProgressDetails value=\{data.collection_targets\}/);assert.match(collection,/candidateValue=\{data.candidate_quality\}/);assert.match(model,/<CollectionProgress\/>/);assert.match(component,/누출 제외 후보/);assert.match(component,/유효한 고정 후보 현황이 없습니다/);for(const literal of ['1400','1122','278','639','1095'])assert(!component.includes(literal));assert(!component.includes('POST'));assert(!component.includes('setInterval'));assert.match(component,/flight.current.invalidate/);
});

test('patch validity/province criteria and split class dominance have separate scopes',()=>{
 const component=readFileSync(new URL('./CollectionProgress.tsx',import.meta.url),'utf8');
 assert.match(component,/패치 기준: 유효 비율 ≥ \{percent\(data.minValid\)\} · 주 경계 내부 ≥ \{percent\(data.minProvince\)\}\./);
 assert.match(component,/학습 후보의 분할\(split\) 집계 기준: 최대 단일 클래스 비중 ≤ \{percent\(data.maxDominance\)\}/);
 assert.match(component,/개별 순림 패치의 클래스 비율만으로 자동 탈락시키지 않습니다/);
 assert(!component.includes('data.minProvince)} · 최대 단일 클래스'));
});


test('minimum floor and requested priority are planned policy, old responses remain compatible',()=>{
 const old=fixture();assert.equal(parseCollectionProgress(old).balancePolicy,undefined);
 old.balance_policy={scope:'PLANNED_COLLECTION_PRIORITY_NOT_RUNNING_JOBS',minimum_floor_not_equal_quota:true,preserve_existing_patches:true,deduplicate_before_enrollment:true,priority_provinces:['southeast_sulawesi','gorontalo']};
 assert.deepEqual(parseCollectionProgress(old).balancePolicy.priorityProvinces,['southeast_sulawesi','gorontalo']);
 old.balance_policy.scope='RUNNING';assert.throws(()=>parseCollectionProgress(old));
 const component=readFileSync(new URL('./CollectionProgress.tsx',import.meta.url),'utf8');
 assert.match(component,/최소 확보 기준이며 모든 주·연도의 동일 개수를 강제/);assert.match(component,/현재 실행 중인 배치나 완료 성과를 뜻하지 않습니다/);assert.match(component,/같은 영상을 중복 추가/);
});
function bareFixture(){return {available:true,status:'LOCAL_TARGET_REVIEW_FINISHED',scope:'LOCAL_LABEL_AND_HISTORICAL_SUPPORT_NOT_REMOTE_QUALITY',source_manifest_sha256:'a'.repeat(64),source_matches_current_manifest:true,report_sha256:'b'.repeat(64),recorded_at:'2026-10-18T12:00:00+09:00',source_report:'first-group-training-priority/review.json',candidate_total:12,execution_supported:false,actual_quality_verified:false,scientific_accuracy_validated:false,rows:fixture().rows.map(r=>({province:r.province,candidates:2,support_clear:1,overlap:1,local_invalid:0}))};}
test('local bare review keeps unknown, stale and remote quality separate with bounded identity and sums',()=>{
 assert.equal(parseBareReview(undefined,'a'.repeat(64)),undefined);assert.equal(parseBareReview({available:false,status:'INVALID'},'a'.repeat(64)),undefined);
 const input=bareFixture(),view=parseBareReview(input,'a'.repeat(64));assert.equal(view.total,12);view.rows[0].clear=99;assert.equal(input.rows[0].support_clear,1);
 input.source_matches_current_manifest=false;assert.equal(parseBareReview(input,'c'.repeat(64)).matchesCurrent,false);
 for(const edit of [v=>v.candidate_total++,v=>v.rows[0].candidates++,v=>v.rows[0].overlap=true,v=>v.rows.pop(),v=>v.rows[1].province=v.rows[0].province,v=>v.actual_quality_verified=true,v=>v.execution_supported=true,v=>v.source_report='../hidden',v=>v.source_matches_current_manifest=false]){const bad=bareFixture();edit(bad);assert.throws(()=>parseBareReview(bad,'a'.repeat(64)));const raw=fixture();raw.bare_target_review=bad;const parsed=parseCollectionProgress(raw);assert.equal(parsed.bareReview,undefined);assert.equal(parsed.bareReviewInvalid,true);assert.equal(parsed.eligible,72);}
 const component=readFileSync(new URL('./CollectionProgress.tsx',import.meta.url),'utf8');assert.match(component,/미확인 후보를 0개/);assert.match(component,/미검사 · 집행 미승인/);assert.match(component,/검토 후 원본이 변경됐습니다/);
});


test('searched province scope defaults to six, subsets stay detached and outside positives fail closed',()=>{
 const original=bareFixture();assert.equal(parseBareReview(original,'a'.repeat(64)).searchedProvinces.length,6);
 const subset=bareFixture();subset.searched_provinces=['gorontalo','west_java'];for(const r of subset.rows){if(!subset.searched_provinces.includes(r.province))Object.assign(r,{candidates:0,support_clear:0,overlap:0});}subset.candidate_total=4;
 const view=parseBareReview(subset,'a'.repeat(64));assert.deepEqual(view.searchedProvinces,['gorontalo','west_java']);view.searchedProvinces.push('banten');assert.equal(subset.searched_provinces.length,2);
 for(const scope of [[],['gorontalo','gorontalo'],['unknown'],[''],null,'gorontalo',[true],[['gorontalo']]]){const bad=structuredClone(subset);bad.searched_provinces=scope;assert.throws(()=>parseBareReview(bad,'a'.repeat(64)));}
 const bad=bareFixture();bad.searched_provinces=['gorontalo','west_java'];assert.throws(()=>parseBareReview(bad,'a'.repeat(64)));const raw=fixture();raw.bare_target_review=bad;assert.equal(parseCollectionProgress(raw).bareReviewInvalid,true);
});

function budgetFixture(){return {schema_version:1,available:true,status:'OBSERVED_LEDGER_SNAPSHOT',scope:'ADDITIONAL_BUDGET_INCLUDES_PENDING_NOT_PROCESS_LIVENESS',additional_maximum_bytes:4294967296,charged_including_pending_bytes:460,remaining_bytes:4294966836,settled_batch_bytes:250,metadata_body_bytes:10,pending_bytes:200,pending_count:2,old_pending_bytes:200,old_pending_count:2,source_manifest_sha256:'a'.repeat(64),ledger_sha256:'b'.repeat(64),observed_at:'2026-10-18T15:00:00+09:00',ledger_updated_at:'2026-10-18T14:59:00+09:00',rate_limit_active:false,process_verification:'UNKNOWN',execution_approved:false};}
test('budget preserves fully charged pending once and refuses invalid or mismatched snapshots',()=>{
 assert.equal(parseBudgetProgress(undefined,'a'.repeat(64)),undefined);assert.equal(parseBudgetProgress({available:false},'a'.repeat(64)),undefined);const good=parseBudgetProgress(budgetFixture(),'a'.repeat(64));assert.equal(good.remaining,4294966836);assert.equal(good.oldPending,200);
 for(const edit of [v=>v.remaining_bytes--,v=>v.pending_bytes++,v=>v.old_pending_bytes=201,v=>v.old_pending_count=3,v=>v.charged_including_pending_bytes=true,v=>v.observed_at='invalid',v=>v.ledger_sha256='bad',v=>v.process_verification='RUNNING',v=>v.execution_approved=true,v=>v.source_manifest_sha256='c'.repeat(64)]){const bad=budgetFixture();edit(bad);assert.throws(()=>parseBudgetProgress(bad,'a'.repeat(64)));const raw=fixture();raw.budget_status=bad;assert.equal(parseCollectionProgress(raw).budgetInvalid,true);assert.equal(parseCollectionProgress(raw).eligible,72);}
 const raw=fixture();raw.budget_status=budgetFixture();assert.equal(parseCollectionProgress(raw).budget.remaining,4294966836);
});
