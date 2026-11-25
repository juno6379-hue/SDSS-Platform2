import test from 'node:test';
import assert from 'node:assert/strict';
import {jobLineageView,currentJobLineageReply} from './jobLineageAdapter.ts';
const ref={id:'r1',version:'1',sha256:'a'.repeat(64)};
const diagnostic={scope:'DATASET_LINEAGE_INTEGRITY_ONLY',root_ref:ref,status:'BLOCKED',nodes:[{...ref,integrity_verified:false}],edges:[],edge_direction:'PARENT_TO_CHILD',blockers:[{code:'DATASET_VERSION_NOT_FOUND',ref}],current_assets_revalidated:true,lineage_integrity_verified:false,authorization_verified:false,execution_authorized:false,scientific_approval:false,network_requests:0,source_files_written:0};
const base={extension:'greenblue.job-lineage-validation.rfc1',approval_status:'INTERNAL_REVIEW',job_id:'j1',trace_id:'t1',evaluation_scope:'CURRENT_TRANSITIVE_LINEAGE_NOT_SUBMISSION_SNAPSHOT',available:true,reason:'CURRENT_LINEAGE_CHECKED',status:'BLOCKED',bindings:[{input_index:0,ref,diagnostic_index:0,reused:false,checked:true}],diagnostics:[diagnostic],blockers:[{input_index:0,code:'DATASET_VERSION_NOT_FOUND'}],limits:{max_depth:32,max_nodes_per_root:64,max_total_nodes:256,max_input_refs:64,max_unique_roots:32,node_checks_performed:1,unique_roots_checked:1},current_assets_revalidated:true,lineage_integrity_verified:false,authorization_verified:false,execution_authorized:false,scientific_approval:false,network_requests:0,source_files_written:0};
test('Job현재계보는같은Job·Trace와현재검사scope를확인한다',()=>{
 assert.equal(jobLineageView(base,'j1','t1').state,'BLOCKED');
 assert.equal(jobLineageView(base,'j2','t1').state,'INVALID_RESPONSE');assert.equal(jobLineageView(base,'j1','other').state,'INVALID_RESPONSE');
 assert.equal(jobLineageView({...base,evaluation_scope:'SUBMISSION_SNAPSHOT'},'j1','t1').state,'INVALID_RESPONSE');
});
test('저장요청없는legacy·잘못된요청·상한선차단을현재통과로추정하지않는다',()=>{
 for(const reason of ['LEGACY_REQUEST_NOT_RECORDED','JOB_REQUEST_INVALID','CHECK_LIMIT_REACHED']){const result=jobLineageView({...base,available:false,reason,bindings:[],diagnostics:[],current_assets_revalidated:false},'j1','t1');assert.equal(result.state,reason);}
 assert.equal(jobLineageView({...base,available:false,reason:'LEGACY_REQUEST_NOT_RECORDED'},'j1','t1').state,'INVALID_RESPONSE');
});
test('부분검사와checked/current_assets_revalidated true를전체성공으로바꾸지않는다',()=>{
 const partial={...base,reason:'CHECK_LIMIT_REACHED',bindings:[...base.bindings,{input_index:1,ref:{...ref,id:'r2'},diagnostic_index:null,reused:false,checked:false}]};
 assert.equal(jobLineageView(partial,'j1','t1').state,'PARTIAL_LIMIT');assert.equal(jobLineageView(base,'j1','t1').state,'BLOCKED');
 const conflict={...base,bindings:[{input_index:0,ref,diagnostic_index:null,reused:false,checked:false}],diagnostics:[],current_assets_revalidated:false,blockers:[{input_index:0,code:'JOB_INPUT_REFERENCE_CONFLICT'}]};
 assert.equal(jobLineageView(conflict,'j1','t1').state,'BLOCKED');
});
test('중복참조진단재사용과고정ref연결을구별한다',()=>{
 const reused={...base,bindings:[...base.bindings,{...base.bindings[0],input_index:1,reused:true}]};assert.equal(jobLineageView(reused,'j1','t1').state,'BLOCKED');
 assert.equal(jobLineageView({...base,bindings:[{...base.bindings[0],ref:{...ref,sha256:'b'.repeat(64)}}]},'j1','t1').state,'INVALID_RESPONSE');
 assert.equal(jobLineageView({...base,bindings:[{...base.bindings[0],checked:false}]},'j1','t1').state,'INVALID_RESPONSE');
});
test('무결성집계는모든진단·입력근거가있어야하고실행·권한·과학승인은거부한다',()=>{
 const d={...diagnostic,status:'INTEGRITY_VERIFIED',lineage_integrity_verified:true,blockers:[],nodes:[{...ref,integrity_verified:true}]};const ok={...base,status:'INTEGRITY_VERIFIED',lineage_integrity_verified:true,blockers:[],diagnostics:[d]};
 assert.equal(jobLineageView(ok,'j1','t1').state,'INTEGRITY_VERIFIED');
 assert.equal(jobLineageView({...ok,reason:'CHECK_LIMIT_REACHED'},'j1','t1').state,'INVALID_RESPONSE');
 for(const key of ['authorization_verified','execution_authorized','scientific_approval']){assert.equal(jobLineageView({...base,[key]:true},'j1','t1').state,'INVALID_RESPONSE');assert.equal(jobLineageView({...base,diagnostics:[{...diagnostic,[key]:true}]},'j1','t1').state,'INVALID_RESPONSE');}
});
test('검사예산초과·형식오류·쓰기근거가있는응답을표시하지않는다',()=>{
 assert.equal(jobLineageView({...base,limits:{...base.limits,node_checks_performed:257}},'j1','t1').state,'INVALID_RESPONSE');
 assert.equal(jobLineageView({...base,source_files_written:1},'j1','t1').state,'INVALID_RESPONSE');
 assert.equal(jobLineageView({...base,diagnostics:[{...diagnostic,edges:[{source:ref,target:{id:'invalid'}}]}]},'j1','t1').state,'INVALID_RESPONSE');
});
test('Job·Agent전환과이전명시조회응답은요청세대guard로거부한다',()=>{
 assert.equal(currentJobLineageReply(1,1,'j1:t1','j1:t1'),true);assert.equal(currentJobLineageReply(1,2,'j1:t1','j1:t1'),false);assert.equal(currentJobLineageReply(1,1,'j1:t1','j2:t2'),false);
});
