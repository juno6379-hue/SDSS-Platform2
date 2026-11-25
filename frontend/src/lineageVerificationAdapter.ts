import {diagnosticRecord} from './inputDiagnosticsAdapter.ts';
export type FixedDatasetRef={id:string;version:string;sha256:string};
export type LineageRequest={root_ref:FixedDatasetRef;max_depth:number;max_nodes:number};
const isRef=(value:unknown):value is FixedDatasetRef=>{const row=diagnosticRecord(value);return typeof row.id==='string'&&!!row.id.trim()&&typeof row.version==='string'&&!!row.version.trim()&&typeof row.sha256==='string'&&/^[a-f0-9]{64}$/.test(row.sha256);};
const refKey=(value:FixedDatasetRef)=>JSON.stringify([value.id,value.version,value.sha256]);
export function lineageRequest(id:string,version:string,sha256:string,maxDepth=32,maxNodes=256):LineageRequest|null {
 const ref={id:id.trim(),version:version.trim(),sha256:sha256.trim()};
 if(!isRef(ref)||['latest','current','unknown','undefined','null','n/a','미확인','미제공','—','-'].includes(ref.version.toLowerCase())||!Number.isInteger(maxDepth)||maxDepth<0||maxDepth>64||!Number.isInteger(maxNodes)||maxNodes<1||maxNodes>1024)return null;
 return {root_ref:ref,max_depth:maxDepth,max_nodes:maxNodes};
}
export function lineageVerificationView(value:unknown,request:LineageRequest){
 const wrapper=diagnosticRecord(value),diagnostic=diagnosticRecord(wrapper.diagnostic);
 const invalid=(message:string)=>({state:'INVALID_RESPONSE' as const,message,diagnostic:undefined,wrapper:undefined});
 if(wrapper.extension!=='greenblue.dataset-lineage-verification.rfc1'||wrapper.approval_status!=='INTERNAL_REVIEW'||wrapper.present_in_upstream_openapi!==false||wrapper.evaluation_scope!=='CURRENT_LOCAL_ASSET_CHECK_NOT_EXECUTION_AUTHORIZATION'||diagnostic.scope!=='DATASET_LINEAGE_INTEGRITY_ONLY')return invalid('응답의 진단 계약·검사 범위가 일치하지 않습니다.');
 if([wrapper,diagnostic].some(row=>['authorization_verified','execution_authorized','scientific_approval'].some(key=>row[key]!==false)))return invalid('응답의 비승인 계약이 일치하지 않아 결과를 표시하지 않습니다.');
 if(!isRef(diagnostic.root_ref)||refKey(diagnostic.root_ref)!==refKey(request.root_ref))return invalid('요청한 고정 ID·버전·SHA와 응답의 root_ref가 다릅니다.');
 if(!Array.isArray(diagnostic.nodes)||!Array.isArray(diagnostic.edges)||!Array.isArray(diagnostic.blockers)||!diagnostic.limits||typeof diagnostic.limits!=='object'||typeof diagnostic.current_assets_revalidated!=='boolean'||typeof diagnostic.lineage_integrity_verified!=='boolean')return invalid('노드·연결·차단·검사 한도 필드가 올바르지 않습니다.');
 const limits=diagnosticRecord(diagnostic.limits);
 if(limits.max_depth!==request.max_depth||limits.max_nodes!==request.max_nodes||diagnostic.edge_direction!=='PARENT_TO_CHILD'||diagnostic.network_requests!==0||diagnostic.source_files_written!==0)return invalid('요청한 검사 한도·방향·읽기 전용 범위가 응답과 다릅니다.');
 if(!diagnostic.nodes.every(isRef)||!diagnostic.edges.every(raw=>{const edge=diagnosticRecord(raw);return isRef(edge.source)&&isRef(edge.target);}))return invalid('고정 계보 참조의 형식이 올바르지 않습니다.');
 if(!['BLOCKED','INTEGRITY_VERIFIED'].includes(String(diagnostic.status)))return invalid('지원하지 않는 계보 진단 상태입니다.');
 if(diagnostic.status==='INTEGRITY_VERIFIED' && (diagnostic.lineage_integrity_verified!==true||diagnostic.blockers.length||!diagnostic.nodes.length||diagnostic.nodes.some(raw=>diagnosticRecord(raw).integrity_verified!==true)))return invalid('계보 무결성 판정과 세부 검사 근거가 일치하지 않습니다.');
 return {state:diagnostic.status as 'BLOCKED'|'INTEGRITY_VERIFIED',message:diagnostic.status==='INTEGRITY_VERIFIED'?'이번 요청의 계보 무결성 일치가 보고되었습니다. 품질·기관 권한·과학·실행 승인은 아닙니다.':'계보 확인이 차단되었습니다. 원인 코드와 한도·접근 조건을 확인하세요.',diagnostic,wrapper};
}
export function lineageReplyIsCurrent(generation:number,currentGeneration:number,requestedKey:string,currentKey:string){return generation===currentGeneration&&requestedKey===currentKey;}
