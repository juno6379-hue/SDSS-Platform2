// 외부 요청·비밀키·동적 HTML 삽입 없이 같은 origin의 검증 결과만 표시한다.
const byId = id => document.getElementById(id);
function show(id, value) { byId(id).textContent = JSON.stringify(value, null, 2); }
async function call(path, body) {
  const response = await fetch(`/api/${path}`, {method:body === undefined ? 'GET':'POST',headers:body === undefined ? {}:{'Content-Type':'application/json'},body:body === undefined ? undefined:JSON.stringify(body)});
  const data = await response.json();
  return {...data, status:response.ok ? (data.status || 'IMPLEMENTED_UNVERIFIED'):'BLOCKED', http_status:response.status};
}
async function load(path, target) {
  show(target,{status:'LOADING'});
  try {
    const data=await call(path); show(target,data);
    if(path==='health') document.querySelector('[data-testid="connection-state"]').textContent=data.http_status===200?'로컬 API 응답 정상':'연결 미확인';
    if(path==='cckp') {
      byId('cckp-output').dataset.status=data.status;
      document.querySelector('[data-testid="cckp-value"]').textContent=data.status==='VERIFIED_REAL' && typeof data.result?.value==='number'?data.result.value.toFixed(4):'미검증';
      document.querySelector('[data-testid="cckp-unit"]').textContent=data.status==='VERIFIED_REAL'?data.result?.unit || '미확인':'—';
    }
    if(path==='climate/contract' && data.sample) byId('climate-request').value=JSON.stringify(data.sample,null,2);
  } catch(error) {
    show(target,{status:'BLOCKED',blockers:['LOCAL_API_UNAVAILABLE'],detail:String(error)});
    if(path==='health') document.querySelector('[data-testid="connection-state"]').textContent='연결 미확인';
    if(path==='cckp') {document.querySelector('[data-testid="cckp-value"]').textContent='미검증';document.querySelector('[data-testid="cckp-unit"]').textContent='—';}
  }
}
document.querySelectorAll('[data-endpoint]').forEach(button=>button.addEventListener('click',async()=>{
  button.disabled=true;
  try {await load(button.dataset.endpoint,button.dataset.output || `${button.dataset.endpoint}-output`);} finally {button.disabled=false;}
}));
byId('climate-run').addEventListener('click',async(event)=>{
  event.target.disabled=true;
  try {show('climate-output',await call('climate/query',JSON.parse(byId('climate-request').value)));}
  catch(error){show('climate-output',{status:'BLOCKED',blockers:['INVALID_JSON_OR_API_FAILURE'],detail:String(error)});}
  finally {event.target.disabled=false;}
});
for(const [id,path,target] of [['rag-search','rag/search','rag-output'],['report-search','reports/search','report-output']]) {
  byId(id).addEventListener('click',async(event)=>{
    event.target.disabled=true;
    try{show(target,await call(path,{question:byId('rag-question').value}));}
    catch(error){show(target,{status:'BLOCKED',blockers:['SEARCH_API_UNAVAILABLE'],detail:String(error)});}
    finally{event.target.disabled=false;}
  });
}
void load('health','health-output');
void load('climate/contract','contract-output');
void load('gates','gates-output');
