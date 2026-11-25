type Row = Record<string, unknown>;
export type ModelRegistrationBody = { report_path: string; model_version?: string };
// Python str.strip whitespace set. Never normalize the caller's transmitted value.
const strip = (v: string) => v.replace(/^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/gu, '');
export function modelVersionIssue(value: unknown): string {
  if (typeof value !== 'string') return '모델 버전은 문자로 입력하세요.';
  const chars = Array.from(value);
  if (!chars.length || chars.length > 256 || !strip(value) || chars.some(c => { const n = c.codePointAt(0)!; return n < 32 || (n >= 127 && n <= 159) || (n >= 0xd800 && n <= 0xdfff); })) return '모델 버전은 공백뿐인 값·제어문자 없이 1~256자로 입력하세요.';
  if (['latest', 'current'].includes(strip(value).toLowerCase())) return 'latest/current 대신 명시적인 고정 모델 버전을 입력하세요.';
  return '';
}
export function modelRegistrationBody(reportPath: string, explicit: boolean, version: unknown): ModelRegistrationBody {
  if (!explicit) return { report_path: reportPath };
  const issue = modelVersionIssue(version);
  if (issue) throw new Error(issue);
  return { report_path: reportPath, model_version: version as string };
}
export function registeredModelId(result: unknown): string {
  const r = result && typeof result === 'object' ? result as Row : {};
  const model = r.model && typeof r.model === 'object' ? r.model as Row : {};
  return String(model.id || r.id || '');
}
// Invalidating presentation never cancels or rolls back a server registration.
export class ModelRegistrationFlight {
  private generation = 0;
  private pending = false;
  invalidate() { this.generation++; this.pending = false; }
  async submit(body: ModelRegistrationBody, route: string, hooks: {
    post: (body: ModelRegistrationBody) => Promise<unknown>;
    refresh: () => Promise<void>;
    route: () => string;
    success: (id: string) => void;
    failure: (error: string) => void;
    settled: () => void;
  }): Promise<void> {
    if (this.pending) return;
    this.pending = true;
    const generation = ++this.generation;
    const current = () => generation === this.generation && route === hooks.route();
    let registered = false;
    try {
      const result = await hooks.post(body);
      registered = true;
      // The store may have changed even when this component has been left.
      await hooks.refresh();
      if (current()) hooks.success(registeredModelId(result));
    } catch (e) { if (current()) hooks.failure(registered ? `서버 등록 응답은 성공했으나 목록 갱신 또는 화면 반영에 실패했습니다. 등록을 반복하지 말고 목록을 확인하세요. ${String(e)}` : String(e)); }
    finally { if (current()) { this.pending = false; hooks.settled(); } }
  }
}
