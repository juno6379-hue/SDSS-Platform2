import test from 'node:test';
import assert from 'node:assert/strict';
import {lineageRequest,lineageVerificationView,lineageReplyIsCurrent} from './lineageVerificationAdapter.ts';
const ref={id:'manual-root',version:'2020-v1',sha256:'a'.repeat(64)};
const request={root_ref:ref,max_depth:32,max_nodes:256};
const base={extension:'greenblue.dataset-lineage-verification.rfc1',approval_status:'INTERNAL_REVIEW',present_in_upstream_openapi:false,evaluation_scope:'CURRENT_LOCAL_ASSET_CHECK_NOT_EXECUTION_AUTHORIZATION',authorization_verified:false,execution_authorized:false,scientific_approval:false,diagnostic:{scope:'DATASET_LINEAGE_INTEGRITY_ONLY',edge_direction:'PARENT_TO_CHILD',network_requests:0,source_files_written:0,status:'BLOCKED',root_ref:ref,nodes:[{...ref,integrity_verified:false}],edges:[],blockers:[{code:'DATASET_VERSION_NOT_FOUND',ref}],limits:{max_depth:32,max_nodes:256},lineage_integrity_verified:false,current_assets_revalidated:true,authorization_verified:false,execution_authorized:false,scientific_approval:false}};
test('미상·별칭·형식이 다른 고정참조와 잘못된 검사한도는 제출하지 않는다',()=>{
 assert.equal(lineageRequest('','',''),null);assert.equal(lineageRequest('id','latest','a'.repeat(64)),null);assert.equal(lineageRequest('id','CURRENT','a'.repeat(64)),null);assert.equal(lineageRequest('id','미확인','a'.repeat(64)),null);assert.equal(lineageRequest('id','unknown','a'.repeat(64)),null);assert.equal(lineageRequest('id','1','unknown'),null);assert.equal(lineageRequest('id','1','A'.repeat(64)),null);
 assert.equal(lineageRequest('id','1','a'.repeat(64),65,256),null);assert.equal(lineageRequest('id','1','a'.repeat(64),32,0),null);assert.equal(lineageRequest('id','1','a'.repeat(64),1.5,5),null);
 assert.deepEqual(lineageRequest('manual-root','2020-v1','a'.repeat(64)),request);
});
test('HTTP200 BLOCKED와 current_assets_revalidated 시도를 성공으로 바꾸지 않는다',()=>{
 const result=lineageVerificationView(base,request);assert.equal(result.state,'BLOCKED');assert.equal(result.diagnostic.current_assets_revalidated,true);assert.equal(result.diagnostic.lineage_integrity_verified,false);
});
test('같은 고정 ID·버전·SHA 응답만 표시한다',()=>{
 for(const root_ref of [{...ref,id:'other'},{...ref,version:'2021-v1'},{...ref,sha256:'b'.repeat(64)}])assert.equal(lineageVerificationView({...base,diagnostic:{...base.diagnostic,root_ref}},request).state,'INVALID_RESPONSE');
});
test('wrapper와 diagnostic의 기관·실행·과학 승인 불변조건을 검증한다',()=>{
 for(const flag of ['authorization_verified','execution_authorized','scientific_approval']){
 assert.equal(lineageVerificationView({...base,[flag]:true},request).state,'INVALID_RESPONSE');
 assert.equal(lineageVerificationView({...base,diagnostic:{...base.diagnostic,[flag]:true}},request).state,'INVALID_RESPONSE');
 }
});
test('계보 일치는 일관된 노드·차단 근거가 있어야 하고 과학 승인과 구별한다',()=>{
 const verified={...base,diagnostic:{...base.diagnostic,status:'INTEGRITY_VERIFIED',nodes:[{...ref,integrity_verified:true}],blockers:[],lineage_integrity_verified:true}};
 const view=lineageVerificationView(verified,request);assert.equal(view.state,'INTEGRITY_VERIFIED');assert.equal(view.diagnostic.scientific_approval,false);
 assert.equal(lineageVerificationView({...verified,diagnostic:{...verified.diagnostic,blockers:[{code:'LINEAGE_CYCLE'}]}},request).state,'INVALID_RESPONSE');
 assert.equal(lineageVerificationView({...verified,diagnostic:{...verified.diagnostic,nodes:[]}},request).state,'INVALID_RESPONSE');
 assert.equal(lineageVerificationView({...base,diagnostic:{...base.diagnostic,limits:{max_depth:1,max_nodes:256}}},request).state,'INVALID_RESPONSE');
 assert.equal(lineageVerificationView({...base,diagnostic:{...base.diagnostic,source_files_written:1}},request).state,'INVALID_RESPONSE');
 assert.equal(lineageVerificationView({...base,diagnostic:{...base.diagnostic,edges:[{source:ref,target:{id:'invalid'}}]}},request).state,'INVALID_RESPONSE');
});
test('입력 수정·다른 상세창·늦은 응답은 세대와 입력키로 거부한다',()=>{
 assert.equal(lineageReplyIsCurrent(1,1,'root-a','root-a'),true);assert.equal(lineageReplyIsCurrent(1,2,'root-a','root-a'),false);assert.equal(lineageReplyIsCurrent(1,1,'root-a','root-b'),false);
});
