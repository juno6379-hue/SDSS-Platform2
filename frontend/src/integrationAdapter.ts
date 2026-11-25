/** 기존 API의 호환 표시다. GMAIS 표준 구현·적합성을 추정하지 않는다. */
export type EvidenceRecord = Record<string, unknown>;
export type ReadinessRecord = { status?: string; independent_evaluation?: boolean; can_deploy?: boolean; blockers?: unknown[]; checkpoint_integrity?: {matched?: boolean} };

// 서로 다른 준비 상태를 합쳐 하나의 '준비 완료' 배지로 만들지 않는다.
export function readinessAxes(tool: EvidenceRecord, dataset: boolean | null, model?: EvidenceRecord, review?: ReadinessRecord) {
  return [
    { id: 'runtime', label: '실행 코드', state: tool.implemented === true ? 'IMPLEMENTED_BASELINE' : 'ADAPTER_NOT_CONNECTED', detail: tool.implemented === true ? '기존 구현 존재·운영 실행 승인과 별도' : '외부 모델 연결 대기' },
    { id: 'dataset', label: '학습 데이터', state: dataset === true ? 'REPORTED_READY' : dataset === false ? 'BLOCKED' : 'UNKNOWN', detail: '학습 적격 판정이며 독립 모델 검증과 별도' },
    { id: 'scientific', label: '과학적 검증', state: review?.independent_evaluation === true ? 'INDEPENDENT_RECORD_REPORTED' : 'NOT_VALIDATED', detail: '현재 모델·체크포인트에 연결된 독립 참조 평가 필요' },
    { id: 'deployment', label: '배포 승인', state: model?.status === 'Deployed' ? 'DEPLOYED_RECORD' : review?.can_deploy === true ? 'ELIGIBLE_FOR_REVIEWED_DEPLOYMENT' : 'BLOCKED', detail: `현재 모델 상태 ${String(model?.status || '미등록')}` },
    { id: 'contract', label: '공통 계약 적합성', state: 'CONFORMANCE_NOT_CONFIRMED', detail: 'GMAIS v0.2 원본 확보·현재 Agent의 적합 시험 증거는 별도 확인' },
  ];
}

export function isMockOnly(record: EvidenceRecord) {
  return ['status', 'scientific_status', 'result_classification', 'validation_status', 'result_quality'].some(key => record[key] === 'MOCK_ONLY');
}

export function evidenceIdentity(record: EvidenceRecord) {
  return { id: record.id, result_id: record.result_id, model_ref: record.model_ref, input_refs: record.input_refs,
    validation: record.validation, model_id: record.model_id, dataset_id: record.dataset_id, dataset_version: record.dataset_version,
    status: record.status, scientific_status: record.scientific_status || record.result_classification,
    reference_kind: record.reference_kind, independent_evaluation: record.independent_evaluation,
    checkpoint_sha256: record.checkpoint_sha256, source: record.source, provenance: record.provenance,
    changed_area_m2: record.changed_area_m2, quality: record.quality, uncertainty: record.uncertainty,
    trace_id: record.trace_id, job_id: record.job_id };
}

// 미구현 API를 호출하지 않고 연결에 필요한 계약과 상태를 명시한다.
export const pendingIntegration = {
  source: 'SOURCE_FOUND', standard: 'GMAIS v0.2', schema_version: '0.2.0', adapter_version: 'legacy-readonly-ui-v1',
  required_contracts: ['Agent Registry/Capabilities/Readiness', 'Authorized Workflow Plan/Job/Trace',
    'Metadata/Policy Evidence with version and ACL', 'Result/Layer/Report identity and scientific status'],
  execution_enabled: false,
} as const;

// 서버 SHA 판정과 Job·Result·Trace 식별자가 모두 일치할 때만 게시를 제안한다.
export function sdssPublicationAllowed(adapter: EvidenceRecord, result: EvidenceRecord, job: EvidenceRecord) {
  return adapter.publishable === true && result.status === 'SCIENTIFIC_VALIDATED' && job.status === 'SUCCEEDED'
    && !isMockOnly(result) && adapter.result_id === result.result_id && adapter.job_id === result.job_id
    && adapter.job_id === job.job_id && typeof adapter.trace_id === 'string' && !!adapter.trace_id
    && adapter.trace_id === job.trace_id && result.provenance !== null && typeof result.provenance === 'object'
    && adapter.trace_id === (result.provenance as EvidenceRecord).trace_id
    && result.validation !== null && typeof result.validation === 'object'
    && (result.validation as EvidenceRecord).validation_level === 'INDEPENDENT_SCIENTIFIC'
    && Array.isArray(adapter.blockers) && adapter.blockers.length === 0;
}
