import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {parseWorkflowDraft,workflowBodySha256,workflowLineageView,workflowReplyCurrent} from './workflowLineageAdapter.ts';
const ref={id:'root-한국',version:'2020-v1',sha256:'a'.repeat(64)};
const payload={schema_version:'0.2.0',workflow_run_id:'wf1',trace_id:'t1',nodes:[{node_id:'n1',input_bindings:[ref],depends_on:[]},{node_id:'n2',input_bindings:[ref],depends_on:['n1']},{node_id:'n3',input_bindings:[],depends_on:[]}],policy:{on_blocked:'STOP_DEPENDENTS'}};
const draft=parseWorkflowDraft(JSON.stringify(payload,null,2));const sha=createHash('sha256').update(draft.body,'utf8').digest('hex');
const diagnostic={scope:'DATASET_LINEAGE_INTEGRITY_ONLY',root_ref:ref,status:'BLOCKED',nodes:[{...ref,integrity_verified:false}],edges:[],edge_direction:'PARENT_TO_CHILD',blockers:[{code:'DATASET_VERSION_NOT_FOUND',ref}],current_assets_revalidated:true,lineage_integrity_verified:false,authorization_verified:false,execution_authorized:false,scientific_approval:false,network_requests:0,source_files_written:0};
const bindings=[{node_id:'n1',input_index:0,ref,diagnostic_index:0,checked:true,reused:false},{node_id:'n2',input_index:0,ref,diagnostic_index:0,checked:true,reused:true}];
const base={extension:'greenblue.workflow-lineage-validation.rfc1',approval_status:'INTERNAL_REVIEW',present_in_upstream_openapi:false,schema_version:1,evaluation_scope:'CURRENT_WORKFLOW_TRANSITIVE_LINEAGE_PLAN_ONLY',workflow_run_id:'wf1',trace_id:'t1',request_sha256:sha,mode:'PLAN_ONLY',status:'BLOCKED',execution_started:false,can_execute:false,available:true,reason:'CURRENT_LINEAGE_CHECKED',dag_validated:true,topological_order:['n1','n3','n2'],nodes:payload.nodes.map(node=>({node_id:node.node_id,bindings:bindings.filter(b=>b.node_id===node.node_id),blockers:node.node_id==='n3'?[{code:'INPUT_REFS_REQUIRED'}]:[],inputs_complete:false,status:'BLOCKED',execution_authorized:false})),bindings,diagnostics:[diagnostic],blockers:[{node_id:'n1',input_index:0,code:'DATASET_VERSION_NOT_FOUND'},{node_id:'n3',input_index:null,code:'INPUT_REFS_REQUIRED'}],lineage_integrity_verified:false,current_assets_revalidated:true,authorization_verified:false,execution_authorized:false,scientific_approval:false,network_requests:0,source_files_written:0,limits:{max_depth:32,max_nodes_per_root:64,max_total_nodes:256,max_input_refs:64,max_unique_roots:32,max_workflow_nodes:128,node_checks_performed:1,unique_roots_checked:1}};
test('해시는실제agentApi JSON.stringify UTF8본문이며키정렬canonical이아니다',async()=>{
 assert.equal(await workflowBodySha256(draft.body),sha);assert.equal(draft.body,JSON.stringify(payload));
 const reordered={trace_id:payload.trace_id,workflow_run_id:payload.workflow_run_id,...payload};assert.notEqual(await workflowBodySha256(JSON.stringify(reordered)),sha);
 assert.equal(parseWorkflowDraft('invalid'),null);assert.equal(parseWorkflowDraft('{}'),null);
});
test('WorkflowID·Trace·실제본문SHA가모두일치하는현재진단만표시한다',()=>{
 assert.equal(workflowLineageView(base,draft,sha).state,'CURRENT_DIAGNOSTIC');
 for(const patch of [{workflow_run_id:'wf2'},{trace_id:'other'},{request_sha256:'b'.repeat(64)}])assert.equal(workflowLineageView({...base,...patch},draft,sha).state,'INVALID_RESPONSE');
});
test('공유ref재사용·빈노드·상충참조무해시진단을실행성공으로바꾸지않는다',()=>{
 assert.equal(workflowLineageView(base,draft,sha).wrapper.bindings[1].reused,true);
 const conflict={...base,diagnostics:[],bindings:bindings.map(binding=>({...binding,diagnostic_index:null,checked:false})),current_assets_revalidated:false,blockers:[{node_id:'n1',input_index:0,code:'WORKFLOW_INPUT_REFERENCE_CONFLICT'}]};
 assert.equal(workflowLineageView(conflict,draft,sha).state,'CURRENT_DIAGNOSTIC');
});
test('계보무결성일치여도Workflow는항상PLAN_ONLY/BLOCKED·비실행이다',()=>{
 const d={...diagnostic,status:'INTEGRITY_VERIFIED',lineage_integrity_verified:true,blockers:[],nodes:[{...ref,integrity_verified:true}]};const ok={...base,diagnostics:[d],blockers:[],lineage_integrity_verified:true,nodes:base.nodes.map(node=>({...node,inputs_complete:true,blockers:[]}))};
 assert.equal(workflowLineageView(ok,draft,sha).state,'CURRENT_DIAGNOSTIC');assert.equal(workflowLineageView({...ok,nodes:base.nodes},draft,sha).state,'INVALID_RESPONSE');
 for(const patch of [{status:'INTEGRITY_VERIFIED'},{execution_started:true},{can_execute:true},{execution_authorized:true},{scientific_approval:true}])assert.equal(workflowLineageView({...ok,...patch},draft,sha).state,'INVALID_RESPONSE');
});
test('선행상한·부분검사·노드순서와고정binding신원을검증한다',()=>{
 assert.equal(workflowLineageView({...base,available:false,reason:'CHECK_LIMIT_REACHED',bindings:[],diagnostics:[],nodes:[],topological_order:[],dag_validated:false},draft,sha).state,'LIMIT_REJECTED');
 assert.equal(workflowLineageView({...base,reason:'CHECK_LIMIT_REACHED'},draft,sha).state,'PARTIAL_LIMIT');
 assert.equal(workflowLineageView({...base,topological_order:['n1','n2','other']},draft,sha).state,'INVALID_RESPONSE');
 assert.equal(workflowLineageView({...base,bindings:[{...bindings[0],ref:{...ref,sha256:'b'.repeat(64)}}]},draft,sha).state,'INVALID_RESPONSE');
});
test('JSON수정·메뉴이동·같은JSON복귀에도이전응답은세대로거부한다',()=>{
 assert.equal(workflowReplyCurrent(1,1,'json-a','json-a'),true);assert.equal(workflowReplyCurrent(1,2,'json-a','json-a'),false);assert.equal(workflowReplyCurrent(1,1,'json-a','json-b'),false);
});
