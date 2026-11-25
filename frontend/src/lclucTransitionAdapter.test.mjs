import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {workflowTransitionStats,WORKFLOW_CLASS_COLORS} from './lclucTransitionAdapter.ts';

const fixture=()=>JSON.parse(readFileSync(new URL('../../evidence/integration/lcluc-change-map-generated-fixture-20261018.json',import.meta.url),'utf8'));
const pair='2020-2021';
const stats=f=>workflowTransitionStats(f.receipt,f.report,pair);
const change=f=>f.report.changes[pair];
function zero(f){const c=change(f);c.transition_pixels=Array.from({length:9},()=>Array(9).fill(0));c.transition_area_m2=Array.from({length:9},()=>Array(9).fill(0));
 Object.assign(c,{valid_pixels:0,total_area_m2:0,changed_area_m2:0,change_rate:null,class_net_area_m2:Array(9).fill(0),vector_feature_count:0});}

test('stored real CPU three-year fixture yields pinned full-raster nonempty and unchanged statistics',()=>{
 const f=fixture(),s=stats(f);assert.equal(s.selection.pair,pair);assert.equal(s.validPixels,256);assert.equal(s.totalAreaM2,25600);
 assert.equal(s.changedAreaM2,25600);assert.equal(s.changeRate,1);assert.equal(s.classes[1].beforePixels,256);assert.equal(s.classes[2].afterPixels,256);
 assert.equal(s.classes[1].netAreaM2,-25600);assert.equal(s.classes[2].netAreaM2,25600);
 const same=workflowTransitionStats(f.receipt,f.report,'2021-2022');assert.equal(same.changedAreaM2,0);assert.equal(same.changeRate,0);assert.equal(same.validPixels,256);
 assert.equal(workflowTransitionStats(f.receipt,f.report,'2020-2022').changedAreaM2,25600);
});
test('empty full raster has exact zero matrices null rate and zero totals',()=>{
 const f=fixture();zero(f);const s=stats(f);assert.equal(s.validPixels,0);assert.equal(s.changeRate,null);assert.equal(s.totalAreaM2,0);
 assert(s.classes.every(v=>v.beforePixels===0&&v.afterPixels===0&&v.netAreaM2===0));
});
test('ordered actual labels including duplicates are retained by ID and colors are frozen display-only',()=>{
 const f=fixture();f.report.class_names=Array(9).fill('same');change(f).class_names=[...f.report.class_names];const s=stats(f);
 assert.deepEqual(s.classes.map(c=>c.id),[0,1,2,3,4,5,6,7,8]);assert(s.classes.every(c=>c.name==='same'));
 assert(Object.isFrozen(WORKFLOW_CLASS_COLORS));assert.equal(new Set(WORKFLOW_CLASS_COLORS).size,9);
});
test('output matrices labels selection and derived classes are detached without input mutation',()=>{
 const f=fixture(),before=structuredClone(f),s=stats(f);s.transitionPixels[1][2]=0;s.transitionAreaM2[1][2]=0;s.classes[0].name='changed';s.selection.path='other';assert.deepEqual(f,before);
});
test('truncated vector preview never reduces full raster totals',()=>{
 const f=fixture();change(f).vector_truncated=true;change(f).vector_feature_count=0;const s=stats(f);assert.equal(s.selection.vectorTruncated,true);assert.equal(s.validPixels,256);assert.equal(s.changedAreaM2,25600);
});
test('known projected and actual ellipsoidal area units only',()=>{
 const f=fixture();change(f).area_method='ellipsoidal_geodesic_m2';assert.equal(stats(f).areaMethod,'ellipsoidal_geodesic_m2');
 for(const method of ['geographic_cell_area_m2','km2','pixels',null]){change(f).area_method=method;assert.throws(()=>stats(f));}
});
test('corrupt totals rates net and full-raster basis reject without echoing payload',()=>{
 const mutations=[c=>c.valid_pixels++,c=>c.total_area_m2++,c=>c.changed_area_m2--,c=>c.change_rate=.5,c=>c.change_rate=Infinity,
 c=>c.class_net_area_m2[1]++,c=>c.statistics_basis='vector subset',c=>c.transition_area_m2[1][2]=Infinity,c=>c.transition_pixels[1][2]=true,
 c=>c.transition_area_m2[1][2]=-1,c=>c.transition_pixels[1][2]=.5,c=>c.transition_area_m2[0][0]=1,c=>c.transition_pixels[0][0]=1,
 c=>c.transition_pixels[1][2]=Number.MAX_SAFE_INTEGER,c=>c.class_net_area_m2[0]=NaN,c=>c.changed_area_m2=true];
 for(const mutate of mutations){const f=fixture();mutate(change(f));assert.throws(()=>stats(f),/^Error: 고정 변화쌍의 전체 래스터 전이 통계를 확인할 수 없습니다\.$/);}
});
test('matrix dimensions sparse arrays unsafe sum and finite accumulation are bounded',()=>{
 const mutations=[c=>c.transition_pixels.pop(),c=>c.transition_area_m2[0].push(0),c=>delete c.transition_pixels[0][0],c=>c.class_net_area_m2.pop(),
 c=>delete c.class_net_area_m2[0],c=>{c.transition_pixels[0][0]=Number.MAX_SAFE_INTEGER;c.transition_area_m2[0][0]=1;},
 c=>{c.transition_area_m2[1][2]=Number.MAX_VALUE;c.transition_area_m2[0][0]=Number.MAX_VALUE;c.transition_pixels[0][0]=1;}];
 for(const mutate of mutations){const f=fixture();mutate(change(f));assert.throws(()=>stats(f));}
});
test('label exact order length controls blank lone-surrogate and type violations reject',()=>{
 for(const bad of ['', ' '.repeat(3),'x'.repeat(129),'a\nb','\u007f','\ud800',true,null]){const f=fixture();f.report.class_names[0]=bad;change(f).class_names[0]=bad;assert.throws(()=>stats(f));}
 const f=fixture();change(f).class_names.reverse();assert.throws(()=>stats(f));
 for(const mutate of [v=>v.pop(),v=>delete v[0]]){const g=fixture();mutate(g.report.class_names);assert.throws(()=>stats(g));}
 const g=fixture();g.report.class_names[0]='🌍';change(g).class_names[0]='🌍';assert.equal(stats(g).classes[0].name,'🌍');
});
test('floating accumulation tolerance is area-relative while rate remains dimensionless',()=>{
 const f=fixture();change(f).class_net_area_m2[1]+=0.0001;assert.equal(stats(f).areaToleranceM2,.000256);
 change(f).class_net_area_m2[1]+=0.001;assert.throws(()=>stats(f));
 const g=fixture(),c=change(g);c.transition_area_m2[1][2]=1e15;c.total_area_m2=1e15;c.changed_area_m2=1e15;c.class_net_area_m2[1]=-1e15;c.class_net_area_m2[2]=1e15;c.change_rate=.99;assert.throws(()=>stats(g));
});
test('zero rate nonzero total and total0/null invariant cannot be disguised by tolerance',()=>{
 for(const mutate of [c=>c.change_rate=0,c=>c.total_area_m2=1e-9,c=>c.changed_area_m2=1e-9]){const f=fixture();zero(f);mutate(change(f));assert.throws(()=>stats(f));}
});
test('same receipt report identity pair and artifact namespace remain required',()=>{
 const f=fixture();f.report.checkpoint_sha256='0'.repeat(64);assert.throws(()=>stats(f));
 const g=fixture();change(g).geojson_path='results/other/changes.geojson';assert.throws(()=>stats(g));
 assert.throws(()=>workflowTransitionStats(fixture().receipt,fixture().report,'2022-2020'));
});
