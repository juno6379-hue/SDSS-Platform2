import test from 'node:test';
import assert from 'node:assert/strict';
import { inputDiagnosticRows, dependencyDiagnostic, safeDiagnosticJson, diagnosticText, jobSnapshotView, isCurrentJobLookup } from './inputDiagnosticsAdapter.ts';

test('무결성 통과를 권한·실행 승인으로 바꾸지 않는다',()=>{
 const rows=inputDiagnosticRows({status:'INTEGRITY_VERIFIED',resolved:[{id:'d1',version:'2020',sha256:'a'.repeat(64),integrity_verified:true,authorization_verified:false,quality_status:'VALIDATED',access_class:'PUBLIC',blocker_codes:[]}]});
 assert.equal(rows[0].integrity,'무결성 일치');assert.equal(rows[0].authorization,'권한 검증 안 됨');assert.equal(rows[0].version,'2020');assert.equal(rows[0].sha256,'a'.repeat(64));
});
test('입력 품질·기관 ACL 차단코드를 보존한다',()=>{
 const [row]=inputDiagnosticRows({resolved:[{id:'restricted',version:'1',integrity_verified:true,authorization_verified:false,quality_status:'REJECTED',access_class:'RESTRICTED',blocker_codes:['INPUT_QUALITY_REJECTED','INPUT_ACL_NOT_IMPLEMENTED']}]});
 assert.deepEqual(row.blockers,['INPUT_QUALITY_REJECTED','INPUT_ACL_NOT_IMPLEMENTED']);assert.equal(row.quality,'REJECTED');assert.equal(row.access,'RESTRICTED');
});
test('직접·의존·정책 차단 원인을 혼합하거나 실행권한을 만들지 않는다',()=>{
 const view=dependencyDiagnostic({local_blockers:[{code:'DATA_MISSING'}],upstream_blocked_by:['n1'],policy_blocked_by:['n3'],blocking_cause_node_ids:['n1','n2','n3'],diagnostic_status:'BLOCKING_CAUSES_PRESENT',execution_authorized:true});
 assert.deepEqual(view.upstream,['n1']);assert.deepEqual(view.policy,['n3']);assert.deepEqual(view.causes,['n1','n2','n3']);assert.equal(view.executionAuthorized,false);
 assert.equal(dependencyDiagnostic({diagnostic_status:'NO_BLOCKING_CAUSE_IDENTIFIED'}).executionAuthorized,false);
});
test('원본 JSON·오류 메시지에서 제한 경로와 URI·자격정보를 숨긴다',()=>{
 const source={id:'safe',uri:'private/input.tif',artifact_path:'E:/secret/data.tif',nested:{token:'abc',message:'https://host/data?sig=secret',trace_id:'trace1'}};
 const safe=safeDiagnosticJson(source);const output=JSON.stringify(safe);
 assert.equal(source.uri,'private/input.tif');assert.equal(safe.id,'safe');assert.equal(safe.nested.trace_id,'trace1');
 for(const restricted of ['private/input.tif','E:/secret','https://host','abc','sig=secret'])assert.equal(output.includes(restricted),false);
 assert.equal(diagnosticText('C:\\private\\data.tif'),'[비공개 경로·URI 숨김]');
 assert.equal(diagnosticText('private/data.tif'),'[비공개 경로·URI 숨김]');
 assert.equal(diagnosticText('s3://private-bucket/data'),'[비공개 경로·URI 숨김]');
});
test('누락·잘못된 형태의 진단 응답은 빈 상태로 표시한다',()=>{
 assert.deepEqual(inputDiagnosticRows(null),[]);assert.deepEqual(inputDiagnosticRows({resolved:'invalid'}),[]);assert.deepEqual(dependencyDiagnostic(null).upstream,[]);
});

const recorded={extension:'greenblue.job-input-snapshot.rfc1',job_id:'j1',trace_id:'t1',available:true,reason:'RECORDED_SNAPSHOT',snapshot:{scope:'INPUT_INTEGRITY_ONLY',status:'BLOCKED'},current_files_revalidated:false,execution_authorized:false,scientific_approval:false};
test('제출시점 snapshot은 동일 Job·Trace일 때만 표시한다',()=>{
 assert.equal(jobSnapshotView(recorded,'j1','t1').state,'RECORDED');
 assert.equal(jobSnapshotView(recorded,'j2','t1').state,'IDENTITY_MISMATCH');
 assert.equal(jobSnapshotView(recorded,'j1','other').state,'IDENTITY_MISMATCH');
 assert.equal(jobSnapshotView(recorded,'j1','').snapshot,undefined);
});
test('legacy·유효하지 않은 snapshot·계약 불일치를 통과로 표시하지 않는다',()=>{
 assert.equal(jobSnapshotView({...recorded,available:false,reason:'LEGACY_SNAPSHOT_NOT_RECORDED',snapshot:null},'j1','t1').state,'LEGACY');
 assert.equal(jobSnapshotView({...recorded,available:false,reason:'SNAPSHOT_INVALID',snapshot:null},'j1','t1').state,'INVALID');
 assert.equal(jobSnapshotView({...recorded,snapshot:null},'j1','t1').snapshot,undefined);
 assert.equal(jobSnapshotView({...recorded,current_files_revalidated:true},'j1','t1').state,'INVALID');
 assert.equal(jobSnapshotView({...recorded,execution_authorized:true},'j1','t1').state,'INVALID');
});
test('ID 변경·Agent 변경·이전 조회 응답은 세대 guard로 거부한다',()=>{
 assert.equal(isCurrentJobLookup(1,1,'j1','j1'),true);
 assert.equal(isCurrentJobLookup(1,2,'j1','j1'),false);
 assert.equal(isCurrentJobLookup(1,1,'j1','j2'),false);
 assert.equal(isCurrentJobLookup(3,4,'same-id','same-id'),false);
});
