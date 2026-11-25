import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ts from 'typescript';
const url=name=>new URL(name,import.meta.url).href;
let source=readFileSync(new URL('./CollectionProgress.tsx',import.meta.url),'utf8')
 .replace("import {Icon} from './Icon';","const Icon=()=>null;")
 .replace("from './provinces'",`from '${url('./provinces.ts')}'`)
 .replace("from './collectionProgressAdapter'",`from '${url('./collectionProgressAdapter.ts')}'`)
 .replace("import {readCollectionProgress} from './collectionProgressClient';","const readCollectionProgress=()=>{throw new Error('network forbidden');};")
 .replace("import './collection-progress.css';",'')
 .replace("from 'react'",`from '${url('../node_modules/react/index.js')}'`);
const code=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText.replace('"react/jsx-runtime"',JSON.stringify(url('../node_modules/react/jsx-runtime.js')));
const {CollectionProgressDetails}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const provinces=['south_sulawesi','gorontalo','southeast_sulawesi','east_java','banten','west_java'];
function fixture(scope){
 const rows=provinces.map((province,i)=>({province,split:i<4?'train':i===4?'val':'test',physical:6,eligible:6,year_counts:Object.fromEntries([2020,2021,2022,2023,2024,2025].map(y=>[y,1])),cell_gap:0}));
 const bare={available:true,status:'LOCAL_TARGET_REVIEW_FINISHED',scope:'LOCAL_LABEL_AND_HISTORICAL_SUPPORT_NOT_REMOTE_QUALITY',source_manifest_sha256:'a'.repeat(64),source_matches_current_manifest:true,report_sha256:'b'.repeat(64),recorded_at:'2026-10-18T12:00:00+09:00',source_report:'review.json',candidate_total:scope?4:12,execution_supported:false,actual_quality_verified:false,scientific_accuracy_validated:false,rows:provinces.map(province=>({province,candidates:!scope||scope.includes(province)?2:0,support_clear:!scope||scope.includes(province)?1:0,overlap:!scope||scope.includes(province)?1:0,local_invalid:0})),...(scope?{searched_provinces:scope}:{})};
 return {available:true,source_manifest_sha256:'a'.repeat(64),count_basis:'manifest_quality_status',physical_total:36,eligible_total:36,ineligible_total:0,eligible_target:36,eligible_target_gap:0,cell_floor:1,cell_gap_total:0,rows,minimum_valid_fraction:.8,minimum_province_fraction:.95,native_raster_reverified:false,learning_ready:false,scientific_accuracy_validated:false,class_quality:{required_fraction:.005,max_dominance:.9,minimum_contributing_patches:5,minimum_pixels_per_contributing_patch:256,minimum_pixels_per_split:256,scene_split_conflicts:[],bare_by_split:Object.fromEntries(['train','val','test'].map(s=>[s,{pixels:0,ratio:0,contributing_patches:0}]))},bare_target_review:bare};
}
function reviewHtml(value){return renderToStaticMarkup(React.createElement(CollectionProgressDetails,{value})).split('<section aria-label="나지 표적 후보 로컬 검토">')[1].split('</section>')[0];}
test('rendered two-province review explicitly marks scope and omits unsearched province rows',()=>{
 const html=reviewHtml(fixture(['gorontalo','west_java']));assert.match(html,/이번 탐색 대상: 고론탈로 · 서자바/);assert.match(html,/미탐색이며 후보 0개로 판단하지 않습니다/);assert.match(html,/Gorontalo/);assert.match(html,/West Java/);assert.doesNotMatch(html,/South Sulawesi|Southeast Sulawesi|East Java|Banten/);assert.equal((html.match(/미검사 · 집행 미승인/g)||[]).length,2);
});
test('legacy report renders all six rows and corrupted scope renders unknown without zero review',()=>{
 assert.equal((reviewHtml(fixture()).match(/미검사 · 집행 미승인/g)||[]).length,6);const bad=fixture(['gorontalo','west_java']);bad.bare_target_review.searched_provinces=[];const html=reviewHtml(bad);assert.match(html,/지문·합계·범위를 확인할 수 없습니다/);assert.doesNotMatch(html,/<tbody>/);
});

test('budget card renders observation pins and unknown process, then drops stale amounts',()=>{
 const raw=fixture();raw.budget_status={schema_version:1,available:true,status:'OBSERVED_LEDGER_SNAPSHOT',scope:'ADDITIONAL_BUDGET_INCLUDES_PENDING_NOT_PROCESS_LIVENESS',additional_maximum_bytes:4294967296,charged_including_pending_bytes:460,remaining_bytes:4294966836,settled_batch_bytes:250,metadata_body_bytes:10,pending_bytes:200,pending_count:2,old_pending_bytes:200,old_pending_count:2,source_manifest_sha256:'a'.repeat(64),ledger_sha256:'b'.repeat(64),observed_at:'2026-10-18T15:00:00+09:00',ledger_updated_at:'2026-10-18T14:59:00+09:00',rate_limit_active:false,process_verification:'UNKNOWN',execution_approved:false};
 const html=renderToStaticMarkup(React.createElement(CollectionProgressDetails,{value:raw}));assert.match(html,/4,294,966,836/);assert.match(html,/기존 미정산 예약 2건/);assert.match(html,/실제 수집 프로세스 실행 여부: 미확인/);assert.match(html,/사용에 이미 포함/);assert.match(html,/bbbbbbbbbbbbbbbb/);
 raw.budget_status.source_manifest_sha256='c'.repeat(64);const stale=renderToStaticMarkup(React.createElement(CollectionProgressDetails,{value:raw}));assert.match(stale,/현재 원본 연결을 확인할 수 없습니다/);assert.doesNotMatch(stale,/4,294,966,836/);
});
