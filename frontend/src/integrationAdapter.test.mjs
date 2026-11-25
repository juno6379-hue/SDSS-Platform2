import test from 'node:test';
import assert from 'node:assert/strict';
import { isMockOnly, readinessAxes, evidenceIdentity, sdssPublicationAllowed } from './integrationAdapter.ts';

test('표준 Result MOCK_ONLY는 지도·보고서 게시를 차단한다', () => {
  assert.equal(isMockOnly({status:'MOCK_ONLY'}), true);
  assert.equal(isMockOnly({scientific_status:'MOCK_ONLY'}), true);
  assert.equal(isMockOnly({status:'BLOCKED'}), false);
  assert.equal(isMockOnly({status:'DEVELOPMENT_ONLY'}), false);
});

test('런타임 구현과 데이터 적격은 독립 검증·배포 승인을 만들지 않는다', () => {
  const axes = readinessAxes({implemented:true}, true, {status:'Draft'}, {independent_evaluation:false,can_deploy:false});
  assert.equal(axes.find(row=>row.id==='runtime').state,'IMPLEMENTED_BASELINE');
  assert.equal(axes.find(row=>row.id==='dataset').state,'REPORTED_READY');
  assert.equal(axes.find(row=>row.id==='scientific').state,'NOT_VALIDATED');
  assert.equal(axes.find(row=>row.id==='deployment').state,'BLOCKED');
  assert.equal(axes.find(row=>row.id==='contract').state,'CONFORMANCE_NOT_CONFIRMED');
});

test('외부 미구현 Agent는 학습자료가 있어도 실행 코드가 연결되지 않는다', () => {
  assert.equal(readinessAxes({implemented:false},true)[0].state,'ADAPTER_NOT_CONNECTED');
});

test('Result·Job·Input·Model·검증 근거 ID를 그대로 보존한다', () => {
  const record={result_id:'r-1',job_id:'j-1',status:'DEVELOPMENT_ONLY',input_refs:[{id:'i-1',version:'v1',sha256:'a'.repeat(64)}],model_ref:{id:'m-1',version:'1',sha256:'b'.repeat(64)},validation:{validation_level:'PSEUDO_LABEL_AGREEMENT',report_ref:'r.json'},provenance:{trace_id:'t-1'}};
  const view=evidenceIdentity(record);
  assert.equal(view.result_id,'r-1'); assert.equal(view.job_id,'j-1');
  assert.deepEqual(view.input_refs,record.input_refs); assert.deepEqual(view.model_ref,record.model_ref);
  assert.deepEqual(view.validation,record.validation); assert.equal(view.provenance.trace_id,'t-1');
});

test('SDSS 게시에는 동일 Job·Result·Trace와 독립 검증이 모두 필요하다', () => {
  const result={result_id:'r1',job_id:'j1',status:'SCIENTIFIC_VALIDATED',provenance:{trace_id:'t1'},validation:{validation_level:'INDEPENDENT_SCIENTIFIC'}};
  const job={job_id:'j1',trace_id:'t1',status:'SUCCEEDED'};
  const projection={result_id:'r1',job_id:'j1',trace_id:'t1',publishable:true,blockers:[]};
  assert.equal(sdssPublicationAllowed(projection,result,job),true);
  assert.equal(sdssPublicationAllowed({...projection,job_id:'other'},result,job),false);
  assert.equal(sdssPublicationAllowed({...projection,trace_id:'other'},result,job),false);
  assert.equal(sdssPublicationAllowed({...projection,blockers:[{code:'HASH_MISMATCH'}]},result,job),false);
  assert.equal(sdssPublicationAllowed(projection,{...result,status:'MOCK_ONLY'},job),false);
  assert.equal(sdssPublicationAllowed(projection,{...result,status:'DEVELOPMENT_ONLY'},job),false);
  assert.equal(sdssPublicationAllowed(projection,{...result,validation:{validation_level:'PSEUDO_LABEL_AGREEMENT'}},job),false);
});
