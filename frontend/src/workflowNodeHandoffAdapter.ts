// Caller declarations only. Browser checks bind a reply to the exact manual request;
// they do not authenticate a Workflow or grant permission to execute it.
type Row=Record<string,unknown>;
const row=(v:unknown):v is Row=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const shape=(v:unknown,required:string[],optional:string[]=[]):v is Row=>row(v)&&required.every(k=>Object.hasOwn(v,k))&&Object.keys(v).every(k=>[...required,...optional].includes(k));
const integer=(v:unknown,min:number,max:number):v is number=>typeof v==='number'&&Number.isInteger(v)&&v>=min&&v<=max;
const scalar=(v:unknown):v is string=>typeof v==='string'&&Array.from(v).length<=256&&!/[\u0000-\u001f\u007f-\u009f\ud800-\udfff]/u.test(v);
const text=(v:unknown):v is string=>scalar(v)&&v.trim().length>0;
const sha=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
export const handoffFalseFields=['execution_authorized','ready_for_execution','ready_for_training','scientific_approval','acl_verified','registry_verified','training_authorized','pixels_verified','toc_tou_protected','executor_connected','artifact_bytes_verified','manifest_bytes_verified','workflow_origin_verified','executor_bindings_compared','transitive_lineage_verified','complete_job_validated','aoi_verified','requested_outputs_verified','predecessor_results_bound','dag_validated'];
export const handoffIoFields=['network_requests','source_files_read','source_files_written','database_calls','registry_calls','resolver_calls','executor_calls'];
const codepointCompare=(a:string,b:string)=>{const x=Array.from(a,c=>c.codePointAt(0)!),y=Array.from(b,c=>c.codePointAt(0)!);for(let i=0;i<Math.min(x.length,y.length);i++)if(x[i]!==y[i])return x[i]-y[i];return x.length-y.length;};
// Do not construct a sorted JS object: integer-like keys are re-enumerated numerically.
export function handoffCanonical(v:unknown):string{
 if(v===null||typeof v==='boolean')return JSON.stringify(v);
 if(typeof v==='string'){if(!scalar(v))throw new Error('문자열은 256자 이하이며 제어 문자·단독 surrogate를 포함할 수 없습니다.');return JSON.stringify(v);}
 if(typeof v==='number'){if(!integer(v,-2147483648,2147483647))throw new Error('숫자는 int32 정수만 지원합니다.');return JSON.stringify(v);}
 if(Array.isArray(v))return `[${v.map(handoffCanonical).join(',')}]`;
 if(row(v))return `{${Object.keys(v).sort(codepointCompare).map(k=>`${handoffCanonical(k)}:${handoffCanonical(v[k])}`).join(',')}}`;
 throw new Error('지원하지 않는 JSON 값입니다.');
}
export async function handoffDigest(value:string){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value));return Array.from(new Uint8Array(bytes),n=>n.toString(16).padStart(2,'0')).join('');}
// Strict parser keeps duplicate keys, numeric spelling and depth from being silently
// normalized by JSON.parse before the canonical pin is computed.
export function parseHandoffJson(source:string):unknown{
 if(new TextEncoder().encode(source).length>524288)throw new Error('각 JSON 원문은 UTF-8 512KiB 이하이어야 합니다.');
 let p=0;const whitespace=()=>{while(/[\t\n\r ]/.test(source[p]||'!'))p++;};
 const string=():string=>{const start=p++;while(p<source.length){const c=source[p++];if(c==='"'){const value:unknown=JSON.parse(source.slice(start,p));if(!scalar(value))throw new Error('문자열·제어 문자·Unicode 한도를 확인하세요.');return value;}if(c==='\\')p++;}throw new Error('JSON 문자열이 닫히지 않았습니다.');};
 const value=(depth:number):unknown=>{whitespace();if(depth>12)throw new Error('JSON 중첩 깊이는 12 이하이어야 합니다.');const c=source[p];if(c==='"')return string();if(c==='{'||c==='['){p++;const object=c==='{',out:Row=Object.create(null),list:unknown[]=[],keys=new Set<string>();whitespace();if(source[p]===(object?'}':']')){p++;return object?out:list;}while(true){whitespace();let key='';if(object){if(source[p]!=='"')throw new Error('JSON 객체 키를 확인하세요.');key=string();if(keys.has(key))throw new Error('중복 JSON 키는 지원하지 않습니다. 원문을 수정하세요.');keys.add(key);whitespace();if(source[p++]!==':')throw new Error('JSON 구분자를 확인하세요.');}const child=value(depth+1);if(object)out[key]=child;else list.push(child);whitespace();const end=source[p++];if(end===(object?'}':']'))return object?out:list;if(end!==',')throw new Error('JSON 배열·객체 구분자를 확인하세요.');}}
 for(const [literal,result] of [['true',true],['false',false],['null',null]] as const)if(source.startsWith(literal,p)){p+=literal.length;return result;}
 const token=source.slice(p).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/)?.[0];if(!token||/[.eE]/.test(token))throw new Error('유효한 JSON이 필요하며 소수·지수·NaN·Infinity는 지원하지 않습니다.');p+=token.length;const n=Number(token);if(!integer(n,-2147483648,2147483647))throw new Error('숫자는 int32 범위의 정수이어야 합니다.');return n;};
 const parsed=value(0);whitespace();if(p!==source.length)throw new Error('JSON 뒤의 추가 문자를 제거하세요.');return parsed;
}
type Issue={code:string;side:string;node_index:number|null;input_index:number|null};
export type HandoffResult={schema_version:1;scope:string;status:'MATCH'|'BLOCKED';declarations_match:boolean;workflow_request_sha256:string|null;pinned_workflow_request_sha256:string|null;selected_node_sha256:string|null;expected_metadata_sha256:string|null;proposed_metadata_sha256:string|null;selected_node_index:number|null;expected_input_count:number|null;proposed_input_count:number|null;issues:Issue[]}&Row;
export type HandoffRequest={workflow_request_json:string;pinned_workflow_request_sha256:string;selected_node_id:string;proposed_job_metadata_json:string};
export type HandoffExpectation={request:HandoffRequest;requestBody:string;requestDigest:string;nodeDigest:string;expectedMetadataDigest:string|null;proposalDigest:string;workflow:unknown;proposal:unknown};
export async function prepareHandoff(workflowText:string,nodeId:string,proposalText:string):Promise<HandoffExpectation>{
 if(!text(nodeId))throw new Error('선택 노드 ID를 원문 그대로 1..256자로 입력하세요. 공백을 자동 제거하지 않습니다.');
 const workflow=parseHandoffJson(workflowText),proposal=parseHandoffJson(proposalText),pin=await handoffDigest(handoffCanonical(workflow));const request={workflow_request_json:workflowText,pinned_workflow_request_sha256:pin,selected_node_id:nodeId,proposed_job_metadata_json:proposalText};const requestBody=JSON.stringify(request);if(new TextEncoder().encode(requestBody).length>1048576)throw new Error('전체 요청은 UTF-8 1MiB 이하이어야 합니다.');const w=row(workflow)?workflow:{},nodes=Array.isArray(w.nodes)?w.nodes:[],n=nodes.find(n=>row(n)&&n.node_id===nodeId);const expectedMetadata=row(n)?{agent_id:n.agent_id,capability_id:n.capability_id,execution_context:{trace_id:w.trace_id},input_refs:n.input_bindings}:null;let expectedMetadataDigest:string|null=null;try{if(expectedMetadata)expectedMetadataDigest=await handoffDigest(handoffCanonical(expectedMetadata));}catch{/* Invalid shapes are reported by the server core. */}return {request,requestBody,requestDigest:await handoffDigest(requestBody),nodeDigest:await handoffDigest(handoffCanonical(nodeId)),expectedMetadataDigest,proposalDigest:await handoffDigest(handoffCanonical(proposal)),workflow,proposal};
}
export type HandoffView={valid:false;message:string}|{valid:true;result:HandoffResult};
export function workflowHandoffView(value:unknown,expectation:HandoffExpectation):HandoffView{
 const invalid=():HandoffView=>({valid:false,message:'응답의 요청 해시·선택 노드·선언/계수·안전 오류·비승인 계약이 일치하지 않습니다. 결과를 사용하지 마세요.'});
 if(!shape(value,['extension','approval_status','present_in_upstream_openapi','request_sha256','result'])||value.extension!=='greenblue.workflow-node-input-handoff.rfc1'||value.approval_status!=='INTERNAL_REVIEW'||value.present_in_upstream_openapi!==false||value.request_sha256!==expectation.requestDigest||!row(value.result))return invalid();
 const r=value.result,fields=['schema_version','scope','status','declarations_match','workflow_request_sha256','pinned_workflow_request_sha256','selected_node_sha256','expected_metadata_sha256','proposed_metadata_sha256','selected_node_index','expected_input_count','proposed_input_count','issues',...handoffFalseFields,...handoffIoFields];
 if(!shape(r,fields)||r.schema_version!==1||r.scope!=='WORKFLOW_NODE_TO_PROPOSED_JOB_INPUT_DECLARATIONS_ONLY'||typeof r.status!=='string'||!['MATCH','BLOCKED'].includes(r.status)||typeof r.declarations_match!=='boolean'||r.declarations_match!==(r.status==='MATCH')||handoffFalseFields.some(k=>r[k]!==false)||handoffIoFields.some(k=>r[k]!==0||typeof r[k]!=='number'))return invalid();
 if(r.pinned_workflow_request_sha256!==expectation.request.pinned_workflow_request_sha256||r.selected_node_sha256!==expectation.nodeDigest)return invalid();
 for(const key of ['workflow_request_sha256','expected_metadata_sha256','proposed_metadata_sha256'])if(r[key]!==null&&!sha(r[key]))return invalid();
 if(r.workflow_request_sha256!==null&&r.workflow_request_sha256!==expectation.request.pinned_workflow_request_sha256)return invalid();
 const w=row(expectation.workflow)?expectation.workflow:{},nodes=Array.isArray(w.nodes)?w.nodes:[],selected=nodes.findIndex(n=>row(n)&&n.node_id===expectation.request.selected_node_id),n=selected>=0&&row(nodes[selected])?nodes[selected]:null;
 if(r.selected_node_index!==null&&(!integer(r.selected_node_index,0,127)||r.selected_node_index!==selected))return invalid();
 for(const key of ['expected_input_count','proposed_input_count'])if(r[key]!==null&&!integer(r[key],1,64))return invalid();
 if((r.expected_input_count===null)!==(r.expected_metadata_sha256===null)||(r.proposed_input_count===null)!==(r.proposed_metadata_sha256===null)||(r.selected_node_index===null)!==(r.expected_input_count===null))return invalid();
 if(r.expected_metadata_sha256!==null&&(!n||!Array.isArray(n.input_bindings)||r.expected_input_count!==n.input_bindings.length||r.expected_metadata_sha256!==expectation.expectedMetadataDigest))return invalid();
 if(r.proposed_metadata_sha256!==null&&(!row(expectation.proposal)||!Array.isArray(expectation.proposal.input_refs)||r.proposed_input_count!==expectation.proposal.input_refs.length||r.proposed_metadata_sha256!==expectation.proposalDigest))return invalid();
 if(r.workflow_request_sha256===null&&(r.selected_node_index!==null||r.expected_metadata_sha256!==null||r.proposed_metadata_sha256!==null))return invalid();
 const workflowCodes=['WORKFLOW_SCHEMA_INVALID','WORKFLOW_IDENTITY_INVALID','WORKFLOW_POLICY_INVALID','WORKFLOW_NODE_COUNT_INVALID','NODE_SCHEMA_INVALID','NODE_IDENTITY_INVALID','NODE_ID_AMBIGUOUS','NODE_POLICY_INVALID','NODE_DEPENDENCY_INVALID','WORKFLOW_INPUT_LIMIT'];
 const refCodes=['INPUT_COUNT_INVALID','INPUT_SCHEMA_INVALID','INPUT_IDENTITY_INVALID','INPUT_VERSION_NOT_PINNED','INPUT_SHA_INVALID','INPUT_ROLE_INVALID','INPUT_URI_INVALID','INPUT_IDENTITY_CONFLICT'];
 const comparisonCodes=['AGENT_ID_MISMATCH','CAPABILITY_ID_MISMATCH','TRACE_ID_MISMATCH','INPUT_COUNT_MISMATCH','INPUT_ID_MISMATCH','INPUT_VERSION_MISMATCH','INPUT_SHA256_MISMATCH','INPUT_ROLE_MISMATCH','INPUT_URI_MISMATCH'];
 if(!Array.isArray(r.issues)||r.issues.length>324)return invalid();const seen=new Set<string>();
 for(const raw of r.issues){if(!shape(raw,['code','side','node_index','input_index'])||typeof raw.code!=='string'||typeof raw.side!=='string'||(raw.node_index!==null&&!integer(raw.node_index,0,127))||(raw.input_index!==null&&!integer(raw.input_index,0,63)))return invalid();const {code,side,node_index,input_index}=raw;
  if(node_index!==null&&(node_index>=nodes.length||!row(nodes[node_index])))return invalid();
  if(input_index!==null){const inputs=side==='proposal'&&row(expectation.proposal)?expectation.proposal.input_refs:node_index!==null&&row(nodes[node_index])?nodes[node_index].input_bindings:null;if(!Array.isArray(inputs)||input_index>=inputs.length)return invalid();}
  const key=JSON.stringify([code,side,node_index,input_index]);if(seen.has(key))return invalid();seen.add(key);
  if(side==='workflow'){if(!workflowCodes.includes(code)&&!refCodes.includes(code)&&code!=='SELECTED_INPUTS_REQUIRED')return invalid();if(code==='SELECTED_INPUTS_REQUIRED'){if(r.workflow_request_sha256===null||node_index!==selected||r.selected_node_index!==null||input_index!==null)return invalid();}else if(r.workflow_request_sha256!==null)return invalid();}
  else if(side==='caller'){if(code!=='SELECTED_NODE_NOT_FOUND'||r.workflow_request_sha256===null||r.selected_node_index!==null||node_index!==null||input_index!==null||selected>=0)return invalid();}
  else if(side==='proposal'){if(!['PROPOSED_METADATA_SCHEMA_INVALID','PROPOSED_IDENTITY_INVALID',...refCodes].includes(code)||r.expected_metadata_sha256===null||r.proposed_metadata_sha256!==null||node_index!==null)return invalid();}
  else if(side==='comparison'){if(!comparisonCodes.includes(code)||r.expected_metadata_sha256===null||r.proposed_metadata_sha256===null)return invalid();const indexed=['INPUT_ID_MISMATCH','INPUT_VERSION_MISMATCH','INPUT_SHA256_MISMATCH','INPUT_ROLE_MISMATCH','INPUT_URI_MISMATCH'].includes(code);if(indexed?(node_index!==selected||input_index===null||!integer(r.proposed_input_count,1,64)||input_index>=r.proposed_input_count):(node_index!==null||input_index!==null))return invalid();}
  else return invalid();
 }
 if(r.status==='MATCH'){if(r.issues.length||r.workflow_request_sha256===null||r.expected_input_count===null||r.expected_input_count!==r.proposed_input_count||r.expected_metadata_sha256!==r.proposed_metadata_sha256)return invalid();}
 else if(!r.issues.length||(r.expected_metadata_sha256!==null&&r.proposed_metadata_sha256!==null&&r.expected_metadata_sha256===r.proposed_metadata_sha256))return invalid();
 return {valid:true,result:r as HandoffResult};
}
export function workflowHandoffReplyCurrent(serial:number,current:number,identity:string,currentIdentity:string,route:string,currentRoute:string){return serial===current&&identity===currentIdentity&&route===currentRoute;}
export function workflowHandoffError(status:number){return ({400:'HTTP400 · JSON 원문·중복 키·정수/문자 형식을 확인하세요.',413:'HTTP413 · 요청 크기·깊이·문자열·숫자 한도를 초과했습니다.',503:'HTTP503 · 전달 선언 검사를 사용할 수 없습니다. 통과로 대체하지 않습니다.',401:'HTTP401 · API 인증을 확인하세요.',403:'HTTP403 · API 접근 권한을 확인하세요.'} as Record<number,string>)[status]||'전달 선언 응답을 확인하지 못했습니다. 연결 상태를 확인한 뒤 직접 다시 검사하세요.';}
