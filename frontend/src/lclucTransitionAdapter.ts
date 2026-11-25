import {workflowChangePair,type WorkflowChangeSelection} from './lclucChangeMapAdapter.ts';

/** Display colors by numeric ID only; labels always come from the pinned report. */
export const WORKFLOW_CLASS_COLORS=Object.freeze(['#2563eb','#15803d','#84cc16','#14b8a6','#eab308','#a16207','#dc2626','#a8a29e','#a5d8f3'] as const);
const BASIS='full_valid_raster; vector truncation does not affect statistics' as const;
export type WorkflowTransitionStats={
 selection:WorkflowChangeSelection;
 classes:{id:number;name:string;color:string;beforePixels:number;afterPixels:number;beforeAreaM2:number;afterAreaM2:number;netAreaM2:number}[];
 transitionPixels:number[][];transitionAreaM2:number[][];validPixels:number;totalAreaM2:number;changedAreaM2:number;
 changeRate:number|null;areaMethod:'projected_grid_area_m2'|'ellipsoidal_geodesic_m2';statisticsBasis:typeof BASIS;areaToleranceM2:number;
};
type Row=Record<string,unknown>;
const row=(v:unknown):v is Row=>!!v&&typeof v==='object'&&!Array.isArray(v);
const nonnegative=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
const integer=(v:unknown):v is number=>nonnegative(v)&&Number.isSafeInteger(v);
function need(v:unknown):asserts v{if(!v)throw new Error('고정 변화쌍의 전체 래스터 전이 통계를 확인할 수 없습니다.');}
function names(v:unknown):string[]{
 need(Array.isArray(v)&&v.length===9);
 return Array.from(v,name=>{need(typeof name==='string'&&name.length>0&&name.length<=128&&name.trim().length>0
  &&!/[\u0000-\u001f\u007f-\u009f\ud800-\udfff]/u.test(name));return name;});
}
function matrix(v:unknown,pixels:boolean):number[][]{
 need(Array.isArray(v)&&v.length===9);
 return Array.from(v,line=>{need(Array.isArray(line)&&line.length===9);return Array.from(line,n=>{need(pixels?integer(n):nonnegative(n));return n;});});
}

/** Full-raster arithmetic consistency, not vector-derived area or scientific validation.
 * Area sums tolerate floating accumulation: max(1e-6 m², 1e-8 * max(1,total m²)).
 * Dimensionless rate uses the same relative factor, never the area-unit tolerance.
 */
export function workflowTransitionStats(receipt:unknown,rawReport:unknown,pair:unknown):WorkflowTransitionStats{
 let selection:WorkflowChangeSelection;
 try{selection=workflowChangePair(receipt,rawReport,pair);}catch{need(false);}
 need(row(rawReport)&&row(rawReport.changes));const change=rawReport.changes[selection.pair];need(row(change));
 const labels=names(rawReport.class_names),other=names(change.class_names);need(labels.every((name,i)=>name===other[i]));
 const pixels=matrix(change.transition_pixels,true),area=matrix(change.transition_area_m2,false);
 need(integer(change.valid_pixels)&&nonnegative(change.total_area_m2)&&nonnegative(change.changed_area_m2));
 const total=change.total_area_m2,changed=change.changed_area_m2,tolerance=Math.max(1e-6,1e-8*Math.max(1,total));
 const near=(a:number,b:number)=>Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=tolerance;
 need(change.statistics_basis===BASIS&&(change.area_method==='projected_grid_area_m2'||change.area_method==='ellipsoidal_geodesic_m2'));
 const beforePixels=Array(9).fill(0) as number[],afterPixels=Array(9).fill(0) as number[];
 const beforeArea=Array(9).fill(0) as number[],afterArea=Array(9).fill(0) as number[];
 let pixelTotal=0,areaTotal=0,offDiagonal=0;
 for(let i=0;i<9;i++)for(let j=0;j<9;j++){
  const p=pixels[i][j],a=area[i][j];need((p===0)===(a===0));
  pixelTotal+=p;beforePixels[i]+=p;afterPixels[j]+=p;areaTotal+=a;beforeArea[i]+=a;afterArea[j]+=a;if(i!==j)offDiagonal+=a;
 }
 need(Number.isSafeInteger(pixelTotal)&&pixelTotal===change.valid_pixels&&near(areaTotal,total)&&near(offDiagonal,changed)&&changed<=total);
 need(change.valid_pixels===0?total===0:total>0);
 if(total===0)need(change.change_rate===null);
 else need(nonnegative(change.change_rate)&&change.change_rate<=1&&Math.abs(change.change_rate-changed/total)<=1e-8);
 need(Array.isArray(change.class_net_area_m2)&&change.class_net_area_m2.length===9);
 const net=Array.from(change.class_net_area_m2,(n,i)=>{need(typeof n==='number'&&Number.isFinite(n)&&near(n,afterArea[i]-beforeArea[i]));return n;});
 return {selection,classes:labels.map((name,id)=>({id,name,color:WORKFLOW_CLASS_COLORS[id],beforePixels:beforePixels[id],afterPixels:afterPixels[id],
  beforeAreaM2:beforeArea[id],afterAreaM2:afterArea[id],netAreaM2:net[id]})),transitionPixels:pixels,transitionAreaM2:area,
  validPixels:change.valid_pixels,totalAreaM2:total,changedAreaM2:changed,changeRate:change.change_rate as number|null,
  areaMethod:change.area_method,statisticsBasis:BASIS,areaToleranceM2:tolerance};
}
