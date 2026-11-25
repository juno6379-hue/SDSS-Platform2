import test from 'node:test';
import assert from 'node:assert/strict';
import {toolboxModels,toolboxImplementation,toolboxCounts,recentToolboxJobs,toolboxJobState,toolboxHasErrors} from './toolboxAdapter.ts';

test('API 장기 ID를 짧은 workspace ID에 연결하고 구현·승인을 구분한다',()=>{
  const tools=toolboxModels.map(model=>({id:model.apiId,implemented:model.id==='lcluc'}));
  assert.deepEqual(toolboxCounts(tools),{implemented:1,pending:5,unknown:0});
  assert.equal(toolboxImplementation(tools,'climate'),'pending');
  assert.equal(toolboxImplementation([{id:'climate',implemented:true}],'climate'),'implemented');
});
test('미조회·조회실패·빠진 레코드는 연계대기나 구현으로 추정하지 않는다',()=>{
  assert.deepEqual(toolboxCounts(undefined),{implemented:0,pending:0,unknown:6});
  assert.deepEqual(toolboxCounts([{id:'lcluc',implemented:true}],true),{implemented:0,pending:0,unknown:6});
  assert.equal(toolboxImplementation([{id:'lcluc',implemented:'true'}],'lcluc'),'unknown');
  assert.equal(toolboxImplementation([],'climate'),'unknown');
});
test('최근 이력은 입력을 바꾸지 않고 기록 시각으로 정렬·제한한다',()=>{
  const jobs=Array.from({length:6},(_,i)=>({id:String(i),created_at:`2026-10-${10+i}T00:00:00Z`}));
  assert.deepEqual(recentToolboxJobs(jobs).map(row=>row.id),['5','4','3','2']);
  assert.equal(jobs[0].id,'0');assert.deepEqual(recentToolboxJobs(undefined),[]);
});
test('Job 미확인 값을 완료로 표시하지 않고 기록 상태를 보존한다',()=>{
  assert.equal(toolboxJobState(undefined).label,'상태 미확인');
  assert.equal(toolboxJobState('SUCCEEDED').label,'완료 기록');
  assert.equal(toolboxJobState('RUNNING').label,'실행 기록');
  assert.equal(toolboxJobState('BLOCKED').label,'차단 기록');
});
test('성공 후 빈 오류키와 무관한 API 오류는 툴박스 실패 경고를 만들지 않는다',()=>{
  assert.equal(toolboxHasErrors({tools:'',datasets:'',models:'',jobs:'',health:''}),false);
  assert.equal(toolboxHasErrors({analyses:'별도 화면 오류'}),false);
  assert.equal(toolboxHasErrors({tools:'조회 실패'}),true);
  assert.equal(toolboxHasErrors({health:'연결 실패'}),true);
});
