import type { EvidenceRecord } from './integrationAdapter';

export const toolboxModels = [
  { id:'lcluc', apiId:'lcluc', title:'LCLUC Change Detection', ko:'토지피복·토지이용 변화 탐지', desc:'위성영상으로 읽는 토지피복 변화와 시계열 분석', icon:'layers', image:1 },
  { id:'climate', apiId:'climate-downscaling', title:'Climate Downscaling', ko:'기후 상세화', desc:'기온·강수 시나리오의 고해상도 공간 분석', icon:'rain', image:2 },
  { id:'carbon', apiId:'net-carbon-footprint', title:'Net Carbon Footprint', ko:'탄소 순배출량 분석', desc:'토지이용과 활동자료 기반 배출·흡수량 산정', icon:'leaf', image:3 },
  { id:'biodiversity', apiId:'biodiversity', title:'Biodiversity Mapping', ko:'생물다양성 지도화', desc:'주요 서식지와 생태적 보전가치의 공간 탐색', icon:'habitat', image:4 },
  { id:'coastal', apiId:'sea-level-subsidence', title:'Sea Level Rise & Land Subsidence', ko:'해수면 상승·지반침하', desc:'연안의 해수면·지반 변화와 노출지역 분석', icon:'water', image:5 },
  { id:'flood', apiId:'flood-drought', title:'Flood & Drought Analysis', ko:'홍수·가뭄 분석', desc:'강우와 수문 시나리오 기반 유역 위험도 분석', icon:'rain', image:6 },
] as const;

export function toolboxHasErrors(errors:Record<string,string>) {
  return ['tools','datasets','models','jobs','health'].some(key=>Boolean(errors[key]));
}

export function toolboxImplementation(tools:EvidenceRecord[]|undefined, id:string, failed=false):'implemented'|'pending'|'unknown' {
  if(failed||!tools)return 'unknown';
  const model=toolboxModels.find(row=>row.id===id);
  const record=tools.find(row=>row.id===model?.apiId||row.id===id);
  return record?.implemented===true?'implemented':record?.implemented===false?'pending':'unknown';
}

export function toolboxCounts(tools:EvidenceRecord[]|undefined, failed=false) {
  const result={implemented:0,pending:0,unknown:0};
  for(const model of toolboxModels)result[toolboxImplementation(tools,model.id,failed)]++;
  return result;
}

export function recentToolboxJobs(jobs:EvidenceRecord[]|undefined) {
  if(!jobs)return [];
  const timestamp=(row:EvidenceRecord)=>{const value=row.updated_at||row.created_at;return typeof value==='string'&&Number.isFinite(Date.parse(value))?Date.parse(value):0;};
  return [...jobs].sort((a,b)=>timestamp(b)-timestamp(a)).slice(0,4);
}

export function toolboxJobState(value:unknown) {
  const state=typeof value==='string'?value.toUpperCase():'';
  if(['SUCCEEDED','COMPLETED','SUCCESS'].includes(state))return {label:'완료 기록',tone:'success',icon:'clipboard'};
  if(['RUNNING','EXECUTING'].includes(state))return {label:'실행 기록',tone:'running',icon:'play'};
  if(['FAILED','ERROR','BLOCKED','CANCELLED'].includes(state))return {label:state==='BLOCKED'?'차단 기록':'종료·오류',tone:'error',icon:'warning'};
  if(['QUEUED','PENDING','CREATED'].includes(state))return {label:'대기 기록',tone:'waiting',icon:'report'};
  return {label:'상태 미확인',tone:'waiting',icon:'help'};
}
