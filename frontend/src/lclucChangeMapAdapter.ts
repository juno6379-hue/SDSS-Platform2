import {parseWorkflowReceipt,parseWorkflowReport,workflowSha} from './lclucWorkflowAdapter.ts';

type Row=Record<string,unknown>;
type Position=[number,number];
export type WorkflowChangeSelection={
 workflowId:string;traceId:string;pair:string;index:number;sha256:string;path:string;
 vectorFeatureCount:number;vectorTruncated:boolean;validPixels:number;changedAreaM2:number;
};
export type WorkflowChangeGeometry={type:'Polygon';coordinates:Position[][]}|{type:'MultiPolygon';coordinates:Position[][][]};
export type WorkflowChangeGeoJSON={type:'FeatureCollection';features:{
 type:'Feature';geometry:WorkflowChangeGeometry;
 properties:{from_class:number;to_class:number;transition_code:number;quality:'comparison_of_classifications; unverified_change'};
}[]};
export type WorkflowChangeMap={geojson:WorkflowChangeGeoJSON;bounds:[Position,Position]|null;featureCount:number;vertexCount:number;empty:boolean};

const QUALITY='comparison_of_classifications; unverified_change' as const;
const row=(v:unknown):v is Row=>!!v&&typeof v==='object'&&!Array.isArray(v);
const exact=(v:unknown,keys:string[]):v is Row=>row(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const integer=(v:unknown,max:number):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0&&v<=max;
const positive=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
const path=(v:unknown)=>typeof v==='string'?v.replaceAll('\\','/'):'';
const token=(v:unknown):v is string=>typeof v==='string'&&/^[A-Za-z0-9_-]{1,128}$/.test(v);
function fail():never{throw new Error('변화쌍의 고정 산출물 또는 지도 형식을 확인할 수 없습니다.');}
function need(v:unknown):asserts v{if(!v)fail();}
function years(pair:unknown):[number,number]{
 need(typeof pair==='string'&&/^[0-9]{4}-[0-9]{4}$/.test(pair));
 const [a,b]=pair.split('-').map(Number);need(a>=1900&&b<=2200&&a<b);return [a,b];
}
function selection(value:unknown):asserts value is WorkflowChangeSelection{
 need(exact(value,['workflowId','traceId','pair','index','sha256','path','vectorFeatureCount','vectorTruncated','validPixels','changedAreaM2']));
 need(workflowSha(value.workflowId)&&token(value.traceId)&&workflowSha(value.sha256)&&integer(value.index,127));
 years(value.pair);
 need(value.path===`results/lcluc-workflows/${value.workflowId}/changes/${value.pair}/changes.geojson`
  &&integer(value.vectorFeatureCount,5000)&&typeof value.vectorTruncated==='boolean'
  &&integer(value.validPixels,Number.MAX_SAFE_INTEGER)&&positive(value.changedAreaM2));
}

/** Select one artifact from the same historical receipt/report, never a raw URL. */
export function workflowChangePair(receipt:unknown,rawReport:unknown,pair:unknown):WorkflowChangeSelection{
 need(row(receipt)&&workflowSha(receipt.id));
 const trusted=parseWorkflowReceipt(receipt,{id:receipt.id});
 need(trusted&&trusted.status==='SUCCEEDED'&&parseWorkflowReport(rawReport,trusted)&&row(rawReport)&&row(rawReport.changes));
 const [from,to]=years(pair);need(typeof pair==='string'&&Object.hasOwn(rawReport.changes,pair));
 const change=rawReport.changes[pair];need(row(change));
 need(Number.isSafeInteger(change.from_year)&&change.from_year===from&&Number.isSafeInteger(change.to_year)&&change.to_year===to);
 const wanted=`results/lcluc-workflows/${trusted.id}/changes/${pair}/changes.geojson`;
 need(path(change.geojson_path)===wanted&&Array.isArray(trusted.artifacts));
 const matches=trusted.artifacts.map((artifact,index)=>({artifact,index})).filter(v=>path(v.artifact.path)===wanted);
 need(matches.length===1);
 const result={workflowId:trusted.id,traceId:trusted.trace_id,pair,index:matches[0].index,
  sha256:matches[0].artifact.sha256,path:wanted,vectorFeatureCount:change.vector_feature_count,
  vectorTruncated:change.vector_truncated,validPixels:change.valid_pixels,changedAreaM2:change.changed_area_m2};
 selection(result);return result;
}

/** SHA verification belongs to the bounded byte-fetch client before this guard.
 * These checks establish rendering structure, not topology or scientific truth.
 * Bounds use MapLibre [[west,south],[east,north]]. Dateline ambiguity is rejected.
 */
export function parseWorkflowChangeGeoJSON(value:unknown,picked:WorkflowChangeSelection):WorkflowChangeMap{
 selection(picked);
 need(exact(value,['type','features'])&&value.type==='FeatureCollection'&&Array.isArray(value.features)
  &&value.features.length<=5000&&value.features.length===picked.vectorFeatureCount);
 let vertices=0,west=Infinity,south=Infinity,east=-Infinity,north=-Infinity;
 function position(v:unknown):Position{
  need(Array.isArray(v)&&v.length===2&&typeof v[0]==='number'&&typeof v[1]==='number'
   &&Number.isFinite(v[0])&&Number.isFinite(v[1])&&v[0]>=-180&&v[0]<=180&&v[1]>=-90&&v[1]<=90);
  need(++vertices<=100000);
  west=Math.min(west,v[0]);east=Math.max(east,v[0]);south=Math.min(south,v[1]);north=Math.max(north,v[1]);
  return [v[0],v[1]];
 }
 function ring(v:unknown):Position[]{
  need(Array.isArray(v)&&v.length>=4&&v.length<=100000);
  const result=v.map(position),first=result[0],last=result[result.length-1];
  need(first[0]===last[0]&&first[1]===last[1]);
  for(let i=1;i<result.length;i++)need(Math.abs(result[i][0]-result[i-1][0])<=180);
  return result;
 }
 function polygon(v:unknown):Position[][]{
  need(Array.isArray(v)&&v.length>=1&&v.length<=25000);return v.map(ring);
 }
 function geometry(v:unknown):WorkflowChangeGeometry{
  need(exact(v,['type','coordinates']));
  if(v.type==='Polygon')return {type:'Polygon',coordinates:polygon(v.coordinates)};
  need(v.type==='MultiPolygon'&&Array.isArray(v.coordinates)&&v.coordinates.length>=1&&v.coordinates.length<=25000);
  return {type:'MultiPolygon',coordinates:v.coordinates.map(polygon)};
 }
 const features=value.features.map(v=>{
  need(exact(v,['type','geometry','properties'])&&v.type==='Feature');
  const p=v.properties;need(exact(p,['from_class','to_class','transition_code','quality']));
  need(integer(p.from_class,8)&&integer(p.to_class,8)&&p.from_class!==p.to_class
   &&p.transition_code===p.from_class*9+p.to_class&&p.quality===QUALITY);
  return {type:'Feature' as const,geometry:geometry(v.geometry),properties:{from_class:p.from_class,to_class:p.to_class,
   transition_code:p.transition_code as number,quality:QUALITY}};
 });
 need(features.length===0||east-west<=180);
 const bounds:[Position,Position]|null=features.length?[[west,south],[east,north]]:null;
 return {geojson:{type:'FeatureCollection',features},bounds,featureCount:features.length,vertexCount:vertices,empty:features.length===0};
}
