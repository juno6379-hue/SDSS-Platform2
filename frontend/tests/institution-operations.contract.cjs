// 합성 계약시험: 네트워크·원장·모델 승인 없이 실제 클라이언트 함수를 검사한다.
const fs=require('node:fs'),ts=require('typescript'),assert=require('node:assert/strict');
const source=fs.readFileSync('src/institutionOpsClient.ts','utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const client={};new Function('exports',compiled)(client);
assert.equal(client.resultReviewHash('r-test'),'#/reports/results?result_id=r-test');
assert.equal(client.resultIdFromHash('#/reports/results?result_id=r-test'),'r-test');
for(const id of ['https://external.example','../result','x/y','%2f','x?token=1'])assert.throws(()=>client.resultReviewHash(id));
assert.equal(client.resultIdFromHash('#/view/22?result_id=r-test'),undefined);
assert.equal(client.resultIdFromHash('#/reports/results?result_id=..%2Fsecret'),undefined);
const job={id:'j-test',approval_id:'a-test',provider:'fixture',operation:'fixture',state:'QUEUED',progress:0,cancel_requested:false,model:{name:'fixture',version:'v1',artifact_sha256:'a'.repeat(64)},result_id:null,package_sha256:null,blockers:[],updated_at:'2026-11-25T00:00:00Z'};
assert.ok(client.validOpsJob(job));assert.equal(client.validOpsJob({...job,progress:101}),false);assert.equal(client.validOpsJob({...job,result_id:'https://example.com'}),false);
assert.throws(()=>client.opsList({status:'READY',jobs:[{id:'bad'}]},'jobs',client.validOpsJob));
assert.equal(client.opsList({status:'BLOCKED',blockers:['JOB_PROVIDER_CONFIG_NOT_SET'],jobs:[]},'jobs',client.validOpsJob).status,'BLOCKED');
let calls=[];global.fetch=async(path,options)=>{calls.push({path,options});return {ok:true,headers:{get:()=> 'application/json'},json:async()=>({job})};};
(async()=>{
 await client.opsRequest('/jobs');assert.equal(calls[0].options.headers.Authorization,undefined);
 await assert.rejects(()=>client.opsRequest('/jobs',{body:{approval_id:'a-test'}}));
 await client.opsRequest('/jobs',{token:'temporary-fixture-token',body:{approval_id:'a-test'}});
 assert.equal(calls.at(-1).path,'/api/jobs');assert.equal(calls.at(-1).options.headers.Authorization,'Bearer temporary-fixture-token');assert.deepEqual(JSON.parse(calls.at(-1).options.body),{approval_id:'a-test'});
 await client.opsRequest('/jobs/j-test/cancel',{token:'temporary-fixture-token',body:{}});
 await assert.rejects(()=>client.opsRequest('/jobs/../../private'));
 const ui=fs.readFileSync('src/InstitutionOperations.tsx','utf8');assert.ok(!/localStorage|sessionStorage|console\.|URLSearchParams/.test(ui));assert.ok(ui.includes("setToken('')"));
 const config=fs.readFileSync('vite.config.ts','utf8');assert.ok(config.indexOf("for (const name of ['jobs'")<config.indexOf('if (target) for'));
 const app=fs.readFileSync('src/App.tsx','utf8');assert.ok(app.includes('<InstitutionJobs/><ResourceList title="저장된 작업·알림"'));assert.ok(app.includes('<ModelReleases/>'));assert.ok(app.includes('const linkedResult=resultIdFromHash(window.location.hash)'));
 console.log('TESTED_SYNTHETIC: client routing, validators, bearer scoping, empty/blocked states, legacy coexistence PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
