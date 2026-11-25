type Row = Record<string, unknown>;
const exact = (v: unknown, keys: readonly string[]): v is Row => !!v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k));
const fields = ['checkpoint_sha256', 'training_report_sha256', 'model_version'] as const;
export const provenanceFalseFlags = ['authority_verified', 'artifact_bytes_verified', 'execution_authorized', 'scientific_accuracy_validated'] as const;
export const provenanceStatusLabels = { ABSENT: '등록 선언 없음', INVALID: '등록 선언 형식 확인 필요', RECORD_CONFLICT: '레코드 선언 충돌', PARENT_BINDING_UNKNOWN: '부모 해시 근거 부족', CONSISTENT_UNVERIFIED: '메타데이터 일치 · 인증 미검증' } as const;
export const provenanceBindingLabels = { NOT_CHECKED: '검사하지 않음', MATCH: '메타데이터 일치', MISMATCH: '메타데이터 불일치', MISSING: '부모 해시 없음', NOT_RECORDED: '선택 버전 기록 없음' } as const;
export type ProvenanceStatus = keyof typeof provenanceStatusLabels;
export type ProvenanceBinding = keyof typeof provenanceBindingLabels;
export type ProvenanceResult = { schema_version: 1; scope: string; status: ProvenanceStatus; declaration_present: boolean | null; bindings: Record<typeof fields[number], ProvenanceBinding>; issue: {code: string; field: string} | null } & Record<typeof provenanceFalseFlags[number], false>;
const invalidFields: Record<string, readonly string[]> = {
  RECORD_INVALID: ['record'],
  MODEL_REFERENCE_INVALID: ['id', 'model_version_declaration.version', 'model_version'],
  MODEL_VERSION_NOT_PINNED: ['model_version_declaration.version', 'model_version'],
  DECLARATION_SCHEMA_INVALID: ['model_version_declaration', 'model_version_declaration.schema_version', 'model_version_declaration.source'],
  SHA256_INVALID: ['model_version_declaration.checkpoint_sha256', 'model_version_declaration.training_report_sha256', 'checkpoint_sha256', 'training_report_sha256'],
};
export function parseModelProvenance(v: unknown): ProvenanceResult | undefined {
  if (!exact(v, ['schema_version', 'scope', 'status', 'declaration_present', 'bindings', 'issue', ...provenanceFalseFlags]) || v.schema_version !== 1 || v.scope !== 'LOCAL_MODEL_REGISTRATION_METADATA_OBSERVATION_ONLY' || !provenanceFalseFlags.every(k => v[k] === false)) return;
  if (typeof v.status !== 'string' || !Object.hasOwn(provenanceStatusLabels, v.status) || !exact(v.bindings, fields)) return;
  const b = v.bindings;
  if (!fields.every(k => typeof b[k] === 'string')) return;
  const notChecked = fields.every(k => b[k] === 'NOT_CHECKED');
  const issue = v.issue;
  if (issue !== null && (!exact(issue, ['code', 'field']) || typeof issue.code !== 'string' || typeof issue.field !== 'string')) return;
  const isIssue = (code: string, field: string) => issue !== null && (issue as Row).code === code && (issue as Row).field === field;
  if (v.status === 'ABSENT') {
    if (v.declaration_present !== false || !notChecked || issue !== null) return;
  } else if (v.status === 'INVALID') {
    if (!notChecked || issue === null) return;
    const i = issue as {code: string; field: string};
    if (!Object.hasOwn(invalidFields, i.code) || !invalidFields[i.code].includes(i.field)) return;
    if (i.code === 'RECORD_INVALID') { if (v.declaration_present !== null) return; }
    else if (typeof v.declaration_present !== 'boolean' || (i.field !== 'id' && v.declaration_present !== true)) return;
  } else {
    if (v.declaration_present !== true || !['MATCH','MISMATCH','MISSING'].includes(b.checkpoint_sha256 as string) || !['MATCH','MISMATCH','MISSING'].includes(b.training_report_sha256 as string) || !['MATCH','MISMATCH','NOT_RECORDED'].includes(b.model_version as string)) return;
    const mismatch = fields.find(k => b[k] === 'MISMATCH');
    const missing = fields.slice(0, 2).find(k => b[k] === 'MISSING');
    if (v.status === 'RECORD_CONFLICT') { if (!mismatch || !isIssue('RECORD_BINDING_CONFLICT', mismatch)) return; }
    else if (v.status === 'PARENT_BINDING_UNKNOWN') { if (mismatch || !missing || !isIssue('PARENT_BINDING_MISSING', missing)) return; }
    else if (mismatch || missing || issue !== null) return;
  }
  return v as ProvenanceResult;
}
export function modelProvenanceError(error: unknown): string {
  const status = /^Error: HTTP (401|403|404|503)\b/.exec(String(error))?.[1];
  return status === '401' || status === '403' ? '인증 정보를 확인한 뒤 다시 조회하세요.' : status === '404' ? '선택한 모델을 찾을 수 없습니다. 목록을 다시 확인하세요.' : '등록 선언 관측을 완료할 수 없습니다. 잠시 후 다시 조회하세요.';
}
export class ModelProvenanceFlight {
  private generation = 0;
  private pending = false;
  invalidate() { this.generation++; this.pending = false; }
  async inspect(modelId: string, route: string, hooks: {
    get: (path: string) => Promise<unknown>;
    identity: () => {modelId: string; route: string};
    result: (value: ProvenanceResult) => void;
    failure: (message: string) => void;
    settled: () => void;
  }) {
    if (this.pending || !modelId) return;
    this.pending = true;
    const generation = ++this.generation;
    const current = () => { const identity = hooks.identity(); return generation === this.generation && modelId === identity.modelId && route === identity.route; };
    try {
      const value = await hooks.get(`/models/${encodeURIComponent(modelId)}/registration-provenance`);
      if (current()) {
        const result = parseModelProvenance(value);
        if (result) hooks.result(result);
        else hooks.failure('등록 선언 관측 응답을 안전하게 확인하지 못했습니다. 결과를 표시하지 않습니다.');
      }
    } catch (e) { if (current()) hooks.failure(modelProvenanceError(e)); }
    finally { if (current()) { this.pending = false; hooks.settled(); } }
  }
}
