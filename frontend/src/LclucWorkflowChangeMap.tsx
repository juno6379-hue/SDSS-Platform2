import {useEffect,useRef,useState} from 'react';
import maplibregl from 'maplibre-gl';
import {Icon} from './Icon';
import {WorkflowFlight} from './lclucWorkflowAdapter';
import type {WorkflowReceipt} from './lclucWorkflowAdapter';
import {workflowGeoJSON} from './lclucWorkflowClient';
import {parseWorkflowChangeGeoJSON} from './lclucChangeMapAdapter';
import type {WorkflowChangeMap,WorkflowChangeSelection} from './lclucChangeMapAdapter';
import {workflowTransitionStats,WORKFLOW_CLASS_COLORS} from './lclucTransitionAdapter';
import type {WorkflowTransitionStats} from './lclucTransitionAdapter';
import LclucTransitionSummary from './LclucTransitionSummary';
import type {TransitionUnit} from './LclucTransitionSummary';

function Preview({view}:{view:WorkflowChangeMap}){
 const node=useRef<HTMLDivElement>(null),mapRef=useRef<maplibregl.Map|null>(null);
 const [error,setError]=useState(''),[loading,setLoading]=useState(true);
 useEffect(()=>{
  if(view.empty||!view.bounds||!node.current)return;
  let alive=true,map:maplibregl.Map|undefined,observer:ResizeObserver|undefined;
  setError('');setLoading(true);
  const fail=()=>{if(alive){setError('지도 표시를 사용할 수 없습니다. WebGL 지원과 브라우저 설정을 확인하세요. 아래 보고서 통계는 그대로 유지됩니다.');setLoading(false);}};
  const load=()=>{if(!alive||!map)return;try{
   map.addSource('workflow-change',{type:'geojson',data:view.geojson});
   const fillColor:maplibregl.ExpressionSpecification=['match',['get','to_class'],0,WORKFLOW_CLASS_COLORS[0],1,WORKFLOW_CLASS_COLORS[1],2,WORKFLOW_CLASS_COLORS[2],3,WORKFLOW_CLASS_COLORS[3],4,WORKFLOW_CLASS_COLORS[4],5,WORKFLOW_CLASS_COLORS[5],6,WORKFLOW_CLASS_COLORS[6],7,WORKFLOW_CLASS_COLORS[7],8,WORKFLOW_CLASS_COLORS[8],'#6b7280'];
   map.addLayer({id:'workflow-change-fill',type:'fill',source:'workflow-change',paint:{'fill-color':fillColor,'fill-opacity':.7}});
   map.addLayer({id:'workflow-change-line',type:'line',source:'workflow-change',paint:{'line-color':'#075499','line-width':2}});
   map.fitBounds(view.bounds!,{padding:32,maxZoom:14,duration:0});setLoading(false);
  }catch{fail();}};
  try{
   map=new maplibregl.Map({container:node.current,style:{version:8,sources:{},layers:[{id:'neutral-background',type:'background',paint:{'background-color':'#edf3f8'}}]},center:[118,-3],zoom:3,attributionControl:false});
   mapRef.current=map;map.addControl(new maplibregl.AttributionControl({compact:false,customAttribution:'LCLUC 로컬 변화 산출물 · 기관 출처·과학 정확도 미인증'}),'bottom-right');
   map.on('load',load);map.on('error',fail);map.on('webglcontextlost',fail);observer=new ResizeObserver(()=>map?.resize());observer.observe(node.current);
  }catch{fail();}
  return()=>{alive=false;observer?.disconnect();if(map){map.off('load',load);map.off('error',fail);map.off('webglcontextlost',fail);map.remove();}mapRef.current=null;};
 },[view]);
 if(view.empty)return <p className="lwf-map-empty" role="status">표시할 변화 도형 0개입니다. 가짜 도형을 생성하지 않습니다. 벡터 지도와 전체 유효 래스터의 변화량 통계는 별도입니다.</p>;
 return <div className="lwf-map-preview"><div ref={node} className="lwf-map-canvas" aria-label="검증된 선택 변화쌍 지도"/>{loading&&!error&&<p role="status" className="lwf-map-message">지도 표시 준비 중…</p>}{error&&<p role="alert" className="lwf-map-message lwf-warning">{error}</p>}<div className="lwf-map-controls" role="group" aria-label="변화 지도 조작"><button type="button" disabled={!!error||loading} aria-label="변화 지도 확대" onClick={()=>mapRef.current?.zoomIn()}><Icon name="plus" size={18}/></button><button type="button" disabled={!!error||loading} aria-label="변화 지도 축소" onClick={()=>mapRef.current?.zoomOut()}><Icon name="minus" size={18}/></button><button type="button" disabled={!!error||loading} aria-label="변화 도형 전체 보기" onClick={()=>{if(view.bounds)mapRef.current?.fitBounds(view.bounds,{padding:32,maxZoom:14,duration:0});}}><Icon name="focus" size={18}/></button></div></div>;
}

export default function LclucWorkflowChangeMap({receipt,rawReport,pairs,disabled=false}:{receipt:WorkflowReceipt;rawReport:unknown;pairs:string[];disabled?:boolean}){
 const [pair,setPair]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [unit,setUnit]=useState<TransitionUnit>('pixels');
 const [result,setResult]=useState<{identity:string;report:unknown;selection:WorkflowChangeSelection;view:WorkflowChangeMap}>();
 const identity=JSON.stringify([receipt.id,receipt.request_sha256,pair]),current=useRef(identity);current.current=identity;
 const flight=useRef(new WorkflowFlight());
 let stats:WorkflowTransitionStats|undefined;let statsError='';
 if(pair){try{stats=workflowTransitionStats(receipt,rawReport,pair);}catch{statsError='전이행렬·클래스·면적 집계가 일치하지 않아 통계와 지도 읽기를 표시하지 않습니다. 자료를 추정하거나 보정하지 않습니다.';}}
 function clearMap(){flight.current.invalidate();setResult(undefined);setBusy(false);setError('');}
 useEffect(()=>{clearMap();window.addEventListener('popstate',clearMap);window.addEventListener('hashchange',clearMap);return()=>{flight.current.invalidate();window.removeEventListener('popstate',clearMap);window.removeEventListener('hashchange',clearMap);};},[receipt,rawReport,pair]);
 async function readMap(){
  const selectedStats=stats;if(!pair||!selectedStats||busy||disabled)return;setBusy(true);setError('');setResult(undefined);const route=window.location.href;
  await flight.current.run(identity,route,{current:()=>({identity:current.current,route:window.location.href}),settled:()=>setBusy(false),failure:()=>{setResult(undefined);setError('변화 지도 응답을 확인할 수 없습니다. 파일 크기·SHA·도형 형식을 확인하세요. 자동 재시도하지 않습니다.');},work:async live=>{
   const selection=selectedStats.selection;
   const value=await workflowGeoJSON(selection.workflowId,selection.index,selection.sha256,live);if(!live()||value===undefined)return;
   const view=parseWorkflowChangeGeoJSON(value,selection);if(!live())return;setResult({identity,report:rawReport,selection,view});
  }});
 }
 const visible=stats&&result?.identity===identity&&result.report===rawReport&&result.selection.sha256===stats.selection.sha256?result:undefined;
 return <section className="lwf-change-map" aria-label="선택 변화쌍 지도"><h4><Icon name="map" size={19}/>선택 변화쌍의 검증 GeoJSON 지도</h4><p>보고서에서 변화쌍을 직접 선택하고 지도 읽기를 누르세요. 기존 상단 지도·주요 지표는 바꾸지 않습니다. 외부 기저지도 요청 없이 중립 배경에 검증된 도형만 표시합니다.</p><label>지도 변화쌍<select value={pair} onChange={e=>{clearMap();setPair(e.target.value);}}><option value="">변화쌍을 직접 선택하세요</option>{pairs.map(p=><option key={p} value={p}>{p}</option>)}</select></label><div className="lwf-actions"><button type="button" disabled={!pair||!stats||busy||disabled} onClick={()=>void readMap()}><Icon name="map" size={17}/>{busy?'변화 지도 읽는 중…':'선택 변화쌍 지도 읽기'}</button>{busy&&<button type="button" onClick={clearMap}><Icon name="close" size={17}/>지도 응답 표시 중단</button>}</div>{statsError&&<p className="lwf-warning" role="alert">{statsError}</p>}{stats&&<LclucTransitionSummary stats={stats} unit={unit} onUnit={setUnit}/>} {error&&<p className="lwf-warning" role="alert">{error}</p>}{visible&&<><p>Trace {visible.selection.traceId} · 변화쌍 {visible.selection.pair} · 도형 {visible.view.featureCount.toLocaleString()}개 · 정점 {visible.view.vertexCount.toLocaleString()}개</p><p>전체 유효 래스터 {visible.selection.validPixels.toLocaleString()}픽셀 · 변화 면적 {visible.selection.changedAreaM2.toLocaleString()}m²</p>{visible.selection.vectorTruncated&&<p className="lwf-warning">벡터 도형이 잘렸습니다. 지도는 일부 도형이며 전체 유효 래스터의 변화량 통계와 구분해야 합니다.</p>}<Preview key={identity} view={visible.view}/><p>산출물 SHA <code>{visible.selection.sha256}</code> · 과학 정확도 인증 false · 표준 GMAIS Result false. 해시 일치는 원출처 기관 권위나 독립 과학 검증이 아닙니다.</p></>}<p>변화쌍 변경은 지도만 비웁니다. 입력·영수증·이동·뒤로 가기·화면 종료는 이전 지도와 늦은 응답을 폐기합니다. 좌표 범위와 렌더링 구조 검사는 실제 위상·지리학적·과학적 정확도 인증이 아닙니다.</p></section>;
}
