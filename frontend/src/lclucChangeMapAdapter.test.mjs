import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {workflowChangePair,parseWorkflowChangeGeoJSON} from './lclucChangeMapAdapter.ts';

const sha='a'.repeat(64),id='b'.repeat(64),pair='2020-2021';
const geoPath=`results/lcluc-workflows/${id}/changes/${pair}/changes.geojson`;
function fixture(){
 const snapshot={schema_version:1,capability:'landcover.change_detection',trace_id:'trace1',model_ref:{id:'model',version:'v1',sha256:sha},
  images:[2020,2021].map(year=>({year,input_ref:{id:'input'+year,version:'v1',sha256:sha},quality_report_sha256:sha}))};
 const receipt={schema_version:1,scope:'LOCAL_LCLUC_WORKFLOW_ONLY',status:'SUCCEEDED',trace_id:'trace1',id,issue:null,replayed:false,
  scientific_accuracy_validated:false,standard_gmais_result:false,request_snapshot:snapshot,request_sha256:sha,
  created_at:'2026-10-18T01:00:00Z',finished_at:'2026-10-18T01:01:00Z',report_path:`results/lcluc-workflows/${id}/timeseries.json`,
  artifacts:[{path:`results/lcluc-workflows/${id}/timeseries.json`,sha256:sha},{path:geoPath,sha256:sha}],admission_pins:{model:sha,2020:sha,2021:sha}};
 const report={report_path:receipt.report_path,checkpoint_sha256:sha,years:[2020,2021],classifications:{2020:{},2021:{}},changes:{
  [pair]:{from_year:2020,to_year:2021,geojson_path:geoPath,vector_feature_count:1,vector_truncated:false,valid_pixels:256,changed_area_m2:2000}}};
 return {receipt,report};
}
const ring=()=>[[106,-7],[107,-7],[107,-6],[106,-7]];
const feature=()=>({type:'Feature',geometry:{type:'Polygon',coordinates:[ring()]},
 properties:{from_class:1,to_class:2,transition_code:11,quality:'comparison_of_classifications; unverified_change'}});
const collection=()=>({type:'FeatureCollection',features:[feature()]});
const selection=()=>{const f=fixture();return workflowChangePair(f.receipt,f.report,pair);};

test('pair is bound to same receipt report year pair unique artifact index and SHA',()=>{
 const f=fixture(),picked=workflowChangePair(f.receipt,f.report,pair);
 assert.deepEqual(picked,{workflowId:id,traceId:'trace1',pair,index:1,sha256:sha,path:geoPath,
  vectorFeatureCount:1,vectorTruncated:false,validPixels:256,changedAreaM2:2000});
});
test('Windows report and artifact paths normalize to the same canonical selection',()=>{
 const f=fixture();f.receipt.report_path=f.receipt.report_path.replaceAll('/','\\');f.report.report_path=f.receipt.report_path;
 for(const a of f.receipt.artifacts)a.path=a.path.replaceAll('/','\\');
 f.report.changes[pair].geojson_path=geoPath.replaceAll('/','\\');
 assert.equal(workflowChangePair(f.receipt,f.report,pair).path,geoPath);
});
test('receipt status flags identity report pin metadata pair and duplicate artifact contamination reject',()=>{
 const mutations=[f=>f.receipt.status='FAILED',f=>f.receipt.scientific_accuracy_validated=true,f=>f.report.checkpoint_sha256=id,
  f=>f.report.years.reverse(),f=>f.report.changes[pair].from_year=true,f=>f.report.changes[pair].to_year=2022,
  f=>f.report.changes[pair].geojson_path=geoPath.replace(pair,'2021-2022'),f=>f.receipt.artifacts.push(f.receipt.artifacts[1]),
  f=>f.receipt.artifacts[1].sha256='bad',f=>f.report.changes[pair].vector_feature_count=5001,
  f=>f.report.changes[pair].vector_feature_count=true,f=>f.report.changes[pair].vector_truncated=0,
  f=>delete f.report.changes[pair].vector_truncated];
 for(const mutate of mutations){const f=fixture();mutate(f);assert.throws(()=>workflowChangePair(f.receipt,f.report,pair));}
 const f=fixture();for(const p of ['2020-2020','2021-2020','2020-2022','../../private','toString',null])assert.throws(()=>workflowChangePair(f.receipt,f.report,p));
});
test('Polygon is sanitized without aliases and MapLibre bounds use longitude latitude order',()=>{
 const value=collection(),original=structuredClone(value),picked=selection(),result=parseWorkflowChangeGeoJSON(value,picked);
 assert.deepEqual(result.bounds,[[106,-7],[107,-6]]);assert.equal(result.vertexCount,4);assert.equal(result.empty,false);
 assert.deepEqual(result.geojson,value);result.geojson.features[0].geometry.coordinates[0][0][0]=100;
 assert.deepEqual(value,original);assert.equal(picked.path,geoPath);
});
test('MultiPolygon and holes count all vertices with finite WGS84 bounds',()=>{
 const value=collection();value.features[0].geometry={type:'MultiPolygon',coordinates:[[ring(),ring()],[ring()]]};
 const result=parseWorkflowChangeGeoJSON(value,selection());assert.equal(result.vertexCount,12);assert.equal(result.featureCount,1);
});
test('zero-feature native output is valid empty data with null bounds and no invented geometry',()=>{
 const picked={...selection(),vectorFeatureCount:0,changedAreaM2:0},result=parseWorkflowChangeGeoJSON({type:'FeatureCollection',features:[]},picked);
 assert.equal(result.empty,true);assert.equal(result.featureCount,0);assert.equal(result.vertexCount,0);assert.equal(result.bounds,null);
 assert.deepEqual(result.geojson,{type:'FeatureCollection',features:[]});
});
test('truncated vector subset preserves full raster statistics without computing polygon area',()=>{
 const picked={...selection(),vectorTruncated:true,validPixels:100000,changedAreaM2:123456789};
 const result=parseWorkflowChangeGeoJSON(collection(),picked);
 assert.equal(result.featureCount,1);assert.equal(picked.changedAreaM2,123456789);assert.equal(picked.validPixels,100000);
});
test('external CRS links unsupported geometry properties feature count and malformed classes reject',()=>{
 const edits=[v=>v.crs={type:'link',properties:{href:'https://example.invalid'}},v=>v.links=[],v=>v.features[0].links=[],
  v=>v.features[0].geometry={type:'GeometryCollection',geometries:[]},v=>v.features[0].geometry.type='LineString',
  v=>v.features[0].properties.url='https://example.invalid',v=>v.features[0].properties.from_class=true,
  v=>v.features[0].properties.to_class=1,v=>v.features[0].properties.transition_code=12,v=>v.features[0].properties.quality='verified',
  v=>v.features.push(feature()),v=>v.features[0].geometry=null];
 for(const edit of edits){const v=collection();edit(v);assert.throws(()=>parseWorkflowChangeGeoJSON(v,selection()));}
});
test('coordinates require closed four-position 2D rings and finite latitude longitude',()=>{
 const values=[[[106,-7],[107,-7],[106,-7]],[[106,-7],[107,-7],[107,-6],[106,-6]],
  [[106,-7,0],...ring().slice(1)],[[181,-7],...ring().slice(1)],[[106,91],...ring().slice(1)],
  [[NaN,-7],...ring().slice(1)],[[Infinity,-7],...ring().slice(1)],[['106',-7],...ring().slice(1)]];
 for(const r of values){const v=collection();v.features[0].geometry.coordinates=[r];assert.throws(()=>parseWorkflowChangeGeoJSON(v,selection()));}
});
test('antimeridian crossing edges and globally ambiguous extent do not trigger world fit',()=>{
 const v=collection();v.features[0].geometry.coordinates=[[[179,0],[-179,0],[-179,1],[179,0]]];
 assert.throws(()=>parseWorkflowChangeGeoJSON(v,selection()));
 const a=feature(),b=feature();a.geometry.coordinates=[[[-100,0],[-99,0],[-99,1],[-100,0]]];
 b.geometry.coordinates=[[[100,0],[101,0],[101,1],[100,0]]];
 assert.throws(()=>parseWorkflowChangeGeoJSON({type:'FeatureCollection',features:[a,b]},{...selection(),vectorFeatureCount:2}));
});
test('feature and vertex budgets accept the exact boundary and reject one more',()=>{
 const features=Array.from({length:5000},feature);
 assert.equal(parseWorkflowChangeGeoJSON({type:'FeatureCollection',features},{...selection(),vectorFeatureCount:5000}).featureCount,5000);
 assert.throws(()=>parseWorkflowChangeGeoJSON({type:'FeatureCollection',features:[...features,feature()]},{...selection(),vectorFeatureCount:5000}));
 const coords=Array.from({length:100000},(_,i)=>i%2?[107,-6]:[106,-7]);coords[coords.length-1]=coords[0];
 const v=collection();v.features[0].geometry.coordinates=[coords];
 assert.equal(parseWorkflowChangeGeoJSON(v,selection()).vertexCount,100000);
 coords.push(coords[0]);assert.throws(()=>parseWorkflowChangeGeoJSON(v,selection()));
});
test('selection shape and pins remain bounded even when parser is called separately',()=>{
 for(const patch of [{index:-1},{index:true},{sha256:'bad'},{path:'../private'},{vectorFeatureCount:1.5},{vectorTruncated:1},
  {traceId:'../trace'},{workflowId:'bad'},{validPixels:Infinity},{changedAreaM2:-1},{extra:'private'}]){
  assert.throws(()=>parseWorkflowChangeGeoJSON(collection(),{...selection(),...patch}),e=>!e.message.includes('private'));
 }
});

test('actual tiny CPU empty and nonempty reports bind GeoJSON bytes and transition metadata',()=>{
 const root=fileURLToPath(new URL('../../',import.meta.url));
 const code=`import json,sys,torch\nsys.path.insert(0,'tests')\nfrom test_lcluc_workflow import LclucWorkflowTests\nfrom backend.app.lcluc_workflow import execute_lcluc_workflow\nfrom backend.app.ml.network import TinyUNet\nt=LclucWorkflowTests();t.setUpClass();t.setUp()\ntry:\n outputs=[]\n def collect():\n  r=execute_lcluc_workflow(t.store,t.request)\n  assert r['status']=='SUCCEEDED',r\n  report=json.loads((t.root/r['report_path']).read_text(encoding='utf8'))\n  g=t.root/report['changes']['2020-2021']['geojson_path']\n  outputs.append({'receipt':r,'report':report,'raw':g.read_text(encoding='utf8')})\n collect()\n model=TinyUNet(3)\n with torch.no_grad():\n  for p in model.parameters():p.zero_()\n  model.enc1[0].weight[0,0,1,1]=1\n  model.enc1[2].weight[0,0,1,1]=1\n  model.dec1[0].weight[0,16,1,1]=1\n  model.dec1[2].weight[0,0,1,1]=1\n  model.head.bias[1]=.01005\n  model.head.weight[2,0,0,0]=1\n saved=torch.load(t.checkpoint,map_location='cpu',weights_only=True);saved['state_dict']=model.state_dict();torch.save(saved,t.checkpoint)\n sha=t.sha(t.checkpoint)\n t.model['checkpoint_sha256']=sha;t.model['evaluation']['checkpoint_sha256']=sha\n t.model['model_version_declaration']['checkpoint_sha256']=sha;t.model['model_version_declaration']['version']='v2'\n t.store.put('models',t.model)\n t.request['model_ref'].update(sha256=sha,version='v2');t.request['idempotency_key']='nonempty-map-fixture'\n collect()\n print(json.dumps(outputs))\nfinally:t.tearDown();t.tearDownClass()\n`;
 const run=spawnSync('python',['-c',code],{cwd:root,encoding:'utf8',maxBuffer:1024*1024,
  env:{...process.env,PYTHONIOENCODING:'utf-8',PYTHONPATH:[resolve(root,'.runtime'),resolve(root,'backend'),root].join(';')}});
 assert.equal(run.status,0,run.stderr);
 const outputs=JSON.parse(run.stdout),parsed=[];
 for(const v of outputs){
  const picked=workflowChangePair(v.receipt,v.report,pair);
  assert.equal(createHash('sha256').update(v.raw).digest('hex'),picked.sha256);
  parsed.push(parseWorkflowChangeGeoJSON(JSON.parse(v.raw),picked));
 }
 assert.equal(parsed[0].empty,true);assert.equal(parsed[0].bounds,null);
 assert.equal(parsed[1].empty,false);assert.equal(parsed[1].featureCount,1);
 assert.equal(parsed[1].geojson.features[0].properties.transition_code,11);
 const picked=workflowChangePair(outputs[1].receipt,outputs[1].report,pair);
 assert.equal(picked.validPixels,256);assert.equal(picked.changedAreaM2,25600);
 assert.throws(()=>workflowChangePair(outputs[0].receipt,outputs[1].report,pair));
});
