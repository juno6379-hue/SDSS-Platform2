export type DiagnosticRecord = Record<string, unknown>;
export function diagnosticRecord(value: unknown): DiagnosticRecord { return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as DiagnosticRecord : {}; }
// 진단 화면과 원본 JSON 모두에서 경로·URI·자격정보를 숨긴다.
export function diagnosticText(value: unknown): string {
  if (value === null || value === undefined || value === '') return '미제공';
  const text=String(value);
  return /(?:[a-z][a-z0-9+.-]*:\/\/|[A-Za-z]:[\\/]|\\\\[^\\]+\\|(?:^|\s)\/(?:[^\s/]+\/)+|(?:[\w.-]+[\\/])+[\w.-]+\.[A-Za-z0-9]+|(?:sig|token|secret|password)=)/i.test(text) ? '[비공개 경로·URI 숨김]' : text;
}
export function safeDiagnosticJson(value: unknown): unknown {
  if(Array.isArray(value)) return value.map(safeDiagnosticJson);
  if(value!==null && typeof value==='object') return Object.fromEntries(Object.entries(value).map(([key,item])=>[key,/(?:uri|url|path|token|secret|password|credential|authorization_header)/i.test(key)?'[비공개 필드 숨김]':safeDiagnosticJson(item)]));
  return typeof value==='string'?diagnosticText(value):value;
}
export function diagnosticList(value:unknown): string[] { return Array.isArray(value)?value.map(diagnosticText):[]; }
export function inputDiagnosticRows(value:unknown) {
 const resolution=diagnosticRecord(value);
 return (Array.isArray(resolution.resolved)?resolution.resolved:[]).map(raw=>{const row=diagnosticRecord(raw);return {index:row.input_index,id:diagnosticText(row.id),version:diagnosticText(row.version),sha256:diagnosticText(row.sha256),integrity:row.integrity_verified===true?'무결성 일치':row.integrity_verified===false?'무결성 미확인·불일치':'미확인',quality:diagnosticText(row.quality_status),access:diagnosticText(row.access_class),authorization:row.authorization_verified===true?'서버 검증 기록 있음':'권한 검증 안 됨',blockers:diagnosticList(row.blocker_codes)};});
}
export function dependencyDiagnostic(value:unknown) {const row=diagnosticRecord(value);return {local:Array.isArray(row.local_blockers)?row.local_blockers.map(diagnosticRecord):[],upstream:diagnosticList(row.upstream_blocked_by),policy:diagnosticList(row.policy_blocked_by),causes:diagnosticList(row.blocking_cause_node_ids),status:diagnosticText(row.diagnostic_status),executionAuthorized:false};}

export type JobSnapshotView = { state:'RECORDED'|'LEGACY'|'INVALID'|'IDENTITY_MISMATCH'|'NOT_FOUND'|'ERROR'; message:string; snapshot?:unknown; wrapper?:unknown };
// Job 상태와 별도로 저장 snapshot의 ID·Trace·비실행 계약을 확인한다.
export function jobSnapshotView(value:unknown,jobId:string,traceId:string):JobSnapshotView {
 const wrapper=diagnosticRecord(value);
 if(wrapper.job_id!==jobId || !traceId || wrapper.trace_id!==traceId)return {state:'IDENTITY_MISMATCH',message:'Job·Trace가 일치하지 않아 입력 기록을 표시하지 않습니다.'};
 if(wrapper.extension!=='greenblue.job-input-snapshot.rfc1'||wrapper.current_files_revalidated!==false||wrapper.execution_authorized!==false||wrapper.scientific_approval!==false)return {state:'INVALID',message:'저장 기록 응답 계약이 일치하지 않습니다.'};
 if(wrapper.available===true && wrapper.reason==='RECORDED_SNAPSHOT' && wrapper.snapshot!==null && typeof wrapper.snapshot==='object' && !Array.isArray(wrapper.snapshot))return {state:'RECORDED',message:'제출 시점에 저장된 입력 진단입니다. 현재 파일을 재검사한 결과가 아니며 실행·과학 승인을 부여하지 않습니다.',snapshot:wrapper.snapshot,wrapper};
 if(wrapper.available===false && wrapper.reason==='LEGACY_SNAPSHOT_NOT_RECORDED' && wrapper.snapshot===null)return {state:'LEGACY',message:'이전 Job에는 제출 시점 입력 기록이 저장되지 않았습니다.',wrapper};
 return {state:'INVALID',message:wrapper.reason==='SNAPSHOT_INVALID'?'저장된 입력 기록이 유효하지 않아 표시하지 않습니다.':'입력 기록 상태를 해석할 수 없습니다.',wrapper};
}
export function isCurrentJobLookup(requestGeneration:number,currentGeneration:number,requestedJobId:string,responseJobId:unknown) {return requestGeneration===currentGeneration && requestedJobId===responseJobId;}
