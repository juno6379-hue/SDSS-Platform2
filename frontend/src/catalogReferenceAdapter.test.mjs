import test from 'node:test';
import assert from 'node:assert/strict';
import {projectCatalogDataset,filterCatalog,catalogCsv,emptyCatalogFilters} from './catalogReferenceAdapter.ts';
const rows=[projectCatalogDataset({id:'r1',name:'Sentinel image',metadata:{province:'West Java',theme:'위성영상',provider:'Copernicus',data_type:'raster',start_date:'2020-01-01',end_date:'2022-12-31',access_class:'PUBLIC',file_format:'GeoTIFF',quality_status:'VALIDATED'}}),projectCatalogDataset({id:'r2',name:'Climate annual',province:'South Sulawesi',theme:'기후',provider:'BMKG',data_type:'table',year:2024,access_class:'RESTRICTED',file_format:'CSV'}),projectCatalogDataset({id:'missing',name:'No classified metadata',path:'private/data.tif',status:'Approved',synthetic:true})];
const filter=patch=>filterCatalog(rows,{...emptyCatalogFilters,...patch});
test('원본에 없는 분류·기간·권한·품질을 파일경로/승인상태로 추정하지 않는다',()=>{
 assert.equal(rows[2].format,'');assert.equal(rows[2].quality,'');assert.equal(rows[2].access,'');assert.deepEqual(rows[2].provinces,[]);assert.equal('path' in rows[2],false);
 assert.equal(projectCatalogDataset({source:'private/manifest.json'}).provider,'');
});
test('검색과 지역·유형·주제·기관·접근·형식 조건은 실제 메타데이터에 모두 적용된다',()=>{
 for(const condition of [{text:'copernicus'},{provinces:['West Java']},{type:'raster'},{theme:'위성영상'},{provider:'Copernicus'},{access:'PUBLIC'},{format:'GeoTIFF'}])assert.deepEqual(filter(condition).map(r=>r.id),['r1']);
 assert.deepEqual(filter({provider:'BMKG',access:'PUBLIC'}),[]);
 assert.deepEqual(filter({provinces:['West Java','South Sulawesi']}).map(r=>r.id),['r1','r2']);
});
test('기간은 겹치는 기록만 검색하고 기간 미확인은 제외한다',()=>{
 assert.deepEqual(filter({from:'2021',to:'2023'}).map(r=>r.id),['r1']);
 assert.deepEqual(filter({from:'2024',to:'2025'}).map(r=>r.id),['r2']);
 assert.deepEqual(filter({from:'2025'}),[]);
});
test('초기화 필터는 실제 원본행만 반환하며 입력객체를 변경하지 않는다',()=>{
 const before=JSON.stringify(rows);assert.equal(filter({}).length,3);filter({text:'no match'});assert.equal(JSON.stringify(rows),before);
});
test('CSV는 선택된 실제 행을 UTF8 BOM·표준 quoting으로 내보내고 수식 삽입을 막는다',()=>{
 const csv=catalogCsv([projectCatalogDataset({id:'r1',name:'  =HYPERLINK("bad")',provider:'A,B'})]);
 assert.ok(csv.startsWith('\uFEFF'));assert.ok(csv.includes('"\'  =HYPERLINK(""bad"")"'));assert.ok(csv.includes('"A,B"'));assert.ok(!csv.includes('missing'));assert.equal(csv.split('\r\n').length,2);
});

test('역전·잘못된 연도 범위는 결과를 반환하지 않고 등록방식은 제공기관으로 추정하지 않는다',()=>{
 const broad=[projectCatalogDataset({id:'broad',start_date:'2020',end_date:'2030'})];
 assert.deepEqual(filterCatalog(broad,{...emptyCatalogFilters,from:'2025',to:'2021'}),[]);
 assert.deepEqual(filterCatalog(broad,{...emptyCatalogFilters,from:'20'}),[]);
 assert.equal(projectCatalogDataset({source:'manual-local-registration'}).provider,'');
 assert.equal(projectCatalogDataset({source:{institution:'BIG'}}).provider,'BIG');
 assert.equal(projectCatalogDataset({access_class:'CONFIDENTIAL'}).access,'CONFIDENTIAL');
});
