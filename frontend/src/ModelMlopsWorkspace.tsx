import React, { useState, useEffect } from 'react';
import './model-mlops-workspace.css';

export interface ModelMlopsWorkspaceProps {
  onNavigate?: (step: number) => void;
  activeStep?: number;
}

interface ModelItem {
  id: number;
  name: string;
  subName: string;
  agency: string;
  version: string;
  status: '검증중';
  statusType: 'active' | 'warning' | 'info';
  deployDate: string;
  iconBg: string;
  iconText: string;
}

const INITIAL_MODELS: ModelItem[] = [
  {
    id: 1,
    name: 'LCLUC',
    subName: '(Land Cover & Land Use Change)',
    agency: '책임 미확정',
    version: '미검증',
    status: '검증중',
    statusType: 'info',
    deployDate: '미배포',
    iconBg: '#eff6ff',
    iconText: '🛰️',
  },
  {
    id: 2,
    name: 'Climate Downscaling',
    subName: '(기후 상세화)',
    agency: '책임 미확정',
    version: '미검증',
    status: '검증중',
    statusType: 'info',
    deployDate: '미배포',
    iconBg: '#fff7ed',
    iconText: '☀️',
  },
  {
    id: 3,
    name: 'Flood & Drought',
    subName: '(홍수·가뭄 예측)',
    agency: '책임 미확정',
    version: '미검증',
    status: '검증중',
    statusType: 'info',
    deployDate: '미배포',
    iconBg: '#ecfeff',
    iconText: '🌊',
  },
  {
    id: 4,
    name: 'Net Carbon Footprint',
    subName: '(탄소 순배출량)',
    agency: '책임 미확정',
    version: '미검증',
    status: '검증중',
    statusType: 'info',
    deployDate: '미배포',
    iconBg: '#ecfdf5',
    iconText: '🌱',
  },
  {
    id: 5,
    name: 'Biodiversity',
    subName: '(생물다양성 서식지)',
    agency: '책임 미확정',
    version: '미검증',
    status: '검증중',
    statusType: 'info',
    deployDate: '미배포',
    iconBg: '#f0fdf4',
    iconText: '🌲',
  },
  {
    id: 6,
    name: 'Coastal Inundation & Land Subsidence',
    subName: '(연안 침수·지반침하)',
    agency: '책임 미확정',
    version: '미검증',
    status: '검증중',
    statusType: 'info',
    deployDate: '미배포',
    iconBg: '#eff6ff',
    iconText: '🌊',
  },
];

interface CoverageRow {
  province: string;
  areaKm2: string;
  coveragePct: number | null;
  cloudPct: number | null;
  missingPct: number | null;
}

const EMPTY_COVERAGE_DATA: CoverageRow[] = [
  'South Sulawesi', 'Gorontalo', 'Southeast Sulawesi', 'Banten', 'West Java', 'East Java',
].map((province) => ({
  province,
  areaKm2: '미측정',
  coveragePct: null,
  cloudPct: null,
  missingPct: null,
}));

type NullableKpis = {
  modelsProd: number | null;
  inQueue: number | null;
  deployments30d: number | null;
  retrainNeeded: number | null;
  avgF1: number | null;
  avgMiou: number | null;
};

function numericOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function displayMetric(value: number | null, digits = 0): string {
  return value === null ? '미측정' : value.toFixed(digits);
}

function coverageCell(value: number | null): string {
  return value === null ? '미측정' : `${value}%`;
}

function approvalStatus(value: unknown): string {
  return typeof value === 'string' && value.trim() ? value : '상태 미확인';
}

function stringOrFallback(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

const PIPELINE_BLOCKED_LABEL = '실행 근거 없음';

interface ExperimentMetrics {
  accuracy: [number, number, number];
  precision: [number, number, number];
  recall: [number, number, number];
  f1: [number, number, number];
  miou: [number, number, number];
  bestRun: string;
  bestVersion: string;
  bestF1: number;
  bestMiou: number;
  gainPct: string;
}

const EXPERIMENT_RUNS: Record<string, ExperimentMetrics> = {
  'lcluc': {
    accuracy: [0.78, 0.82, 0.87],
    precision: [0.75, 0.80, 0.85],
    recall: [0.70, 0.78, 0.83],
    f1: [0.72, 0.79, 0.84],
    miou: [0.68, 0.74, 0.81],
    bestRun: 'Run-003',
    bestVersion: 'v1.2.0',
    bestF1: 0.84,
    bestMiou: 0.81,
    gainPct: '+7.1% (대비 Run-001)',
  },
  'climate': {
    accuracy: [0.74, 0.79, 0.83],
    precision: [0.71, 0.76, 0.81],
    recall: [0.68, 0.73, 0.79],
    f1: [0.70, 0.75, 0.80],
    miou: [0.65, 0.71, 0.76],
    bestRun: 'Run-003',
    bestVersion: 'v1.1.0',
    bestF1: 0.80,
    bestMiou: 0.76,
    gainPct: '+5.4% (대비 Run-001)',
  },
  'carbon': {
    accuracy: [0.70, 0.73, 0.75],
    precision: [0.68, 0.71, 0.74],
    recall: [0.65, 0.69, 0.72],
    f1: [0.66, 0.70, 0.73],
    miou: [0.62, 0.65, 0.69],
    bestRun: 'Run-002',
    bestVersion: 'v1.0.3',
    bestF1: 0.70,
    bestMiou: 0.65,
    gainPct: '+2.1% (성능 저하 감지)',
  },
};

interface ApprovalItem {
  id: string;
  model_name: string;
  requested_by: string;
  date: string;
  status: string;
  status_code: string;
}

interface RetrainingStage {
  id: string;
  name: string;
  status: string;
  reasonCode: string;
}

export default function ModelMlopsWorkspace({ onNavigate, activeStep }: ModelMlopsWorkspaceProps) {
  const [period, setPeriod] = useState('최근 7일');
  const [selectedExperimentModel, setSelectedExperimentModel] = useState('lcluc');
  const [showRetrainModal, setShowRetrainModal] = useState(false);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const [liveKpis, setLiveKpis] = useState<NullableKpis>({
    modelsProd: null,
    inQueue: null,
    deployments30d: null,
    retrainNeeded: null,
    avgF1: null,
    avgMiou: null,
  });

  const [coverageRows, setCoverageRows] = useState<CoverageRow[]>(EMPTY_COVERAGE_DATA);
  const [summaryStatus, setSummaryStatus] = useState('LOADING');
  const [reasonCodes, setReasonCodes] = useState<string[]>([]);
  const [trainingAllowed, setTrainingAllowed] = useState(false);
  const [approvalAllowed, setApprovalAllowed] = useState(false);
  const [approvalsList, setApprovalsList] = useState<ApprovalItem[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [approvalModel, setApprovalModel] = useState('LCLUC');
  const [approvalVersion, setApprovalVersion] = useState('v1.2.1-candidate');
  const [approvalRationale, setApprovalRationale] = useState('');
  const [retrainingStages, setRetrainingStages] = useState<RetrainingStage[]>([]);
  const [confidenceStatus, setConfidenceStatus] = useState('미측정');
  const [accuracyStatus, setAccuracyStatus] = useState('미측정');

  useEffect(() => {
    let active = true;
    async function loadSummary() {
      try {
        const res = await fetch('/v1/mlops/summary');
        if (!res.ok) throw new Error(`SUMMARY_HTTP_${res.status}`);
        const data = await res.json();
        if (!active || !data) return;
        setSummaryStatus(stringOrFallback(data.status, 'BLOCKED_INVALID_SUMMARY'));
        setReasonCodes(Array.isArray(data.reason_codes) ? data.reason_codes.filter((v: unknown) => typeof v === 'string') : []);
        setTrainingAllowed(data.actions?.retrain_allowed === true || data.training?.action_allowed === true);
        setApprovalAllowed(data.actions?.approval_allowed === true || data.approval?.action_allowed === true);
        const readiness = data.retraining_readiness;
        if (Array.isArray(readiness?.stages)) {
          setRetrainingStages(readiness.stages.map((stage: any) => ({
            id: stringOrFallback(stage?.id, 'unknown-stage'),
            name: stringOrFallback(stage?.name, '단계 미확인'),
            status: stringOrFallback(stage?.status, 'blocked'),
            reasonCode: stringOrFallback(stage?.reason_code, 'EVIDENCE_REQUIRED'),
          })));
        } else {
          setRetrainingStages([]);
        }
        setConfidenceStatus(
          readiness?.confidence?.value == null
            ? `미측정 · ${stringOrFallback(readiness?.confidence?.reason_code, 'NO_VERIFIED_CONFIDENCE_CALIBRATION')}`
            : String(readiness.confidence.value),
        );
        setAccuracyStatus(
          readiness?.accuracy?.overall_accuracy == null
            ? `미측정 · ${stringOrFallback(readiness?.accuracy?.reason_code, 'NO_INDEPENDENT_GROUND_TRUTH_EVALUATION')}`
            : String(readiness.accuracy.overall_accuracy),
        );
        if (data.kpis) {
          setLiveKpis({
            modelsProd: numericOrNull(data.kpis.models_in_production?.value),
            inQueue: numericOrNull(data.kpis.training_in_queue?.value),
            deployments30d: numericOrNull(data.kpis.deployments_30d?.value),
            retrainNeeded: numericOrNull(data.kpis.retraining_needed?.value),
            avgF1: numericOrNull(data.kpis.mean_f1_score?.value),
            avgMiou: numericOrNull(data.kpis.mean_miou?.value),
          });
        }
        const provinces = data.coverage_audit?.provinces;
        if (Array.isArray(provinces)) {
          setCoverageRows(EMPTY_COVERAGE_DATA.map((fallback) => {
            const source = provinces.find((row: any) => row?.province === fallback.province || row?.name === fallback.province);
            if (!source) return fallback;
            return {
              province: fallback.province,
              areaKm2: source.area_km2 == null ? '미측정' : String(source.area_km2),
              coveragePct: numericOrNull(source.coverage_pct),
              cloudPct: numericOrNull(source.cloud_pct),
              missingPct: numericOrNull(source.missing_pct),
            };
          }));
        } else {
          setCoverageRows(EMPTY_COVERAGE_DATA);
        }
        if (Array.isArray(data.approvals)) {
          const mapped: ApprovalItem[] = data.approvals.map((a: any) => ({
            id: stringOrFallback(a.id, 'approval-id-missing'),
            model_name: stringOrFallback(a.model_name || a.model_id, '모델 미확인'),
            requested_by: stringOrFallback(a.requested_by, '요청자 미확인'),
            date: typeof a.date === 'string' ? a.date.substring(0, 10) : '일자 미확인',
            status: approvalStatus(a.status),
            status_code: stringOrFallback(a.status_code, 'unknown'),
          }));
          setApprovalsList(mapped);
        } else {
          setApprovalsList([]);
        }
      } catch {
        if (!active) return;
        setSummaryStatus('BLOCKED_SUMMARY_UNAVAILABLE');
        setReasonCodes(['SUMMARY_UNAVAILABLE']);
        setTrainingAllowed(false);
        setApprovalAllowed(false);
        setApprovalsList([]);
        setCoverageRows(EMPTY_COVERAGE_DATA);
        setRetrainingStages([]);
        setConfidenceStatus('미측정 · SUMMARY_UNAVAILABLE');
        setAccuracyStatus('미측정 · SUMMARY_UNAVAILABLE');
        setLiveKpis({ modelsProd: null, inQueue: null, deployments30d: null, retrainNeeded: null, avgF1: null, avgMiou: null });
      }
    }
    loadSummary();
    return () => { active = false; };
  }, [period]);

  async function handleExecuteRetrain() {
    if (!trainingAllowed) {
      triggerToast('BLOCKED: 실행된 학습 및 검증된 재학습 근거가 없습니다.');
      return;
    }
    setIsSubmitting(true);
    try {
      const res = await fetch('/v1/mlops/retrain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: 'carbon_flux',
          target_version: 'v1.0.4-candidate',
          dataset_version: 'fg-annual-2020-2025-v2',
          epochs: 50,
          holdout_split: 'test_west_java_val_banten',
        }),
      });
      if (!res.ok) throw new Error(`RETRAIN_HTTP_${res.status}`);
      const data = await res.json();
      if (data.status !== 'success' && data.status !== 'accepted') throw new Error('RETRAIN_NOT_ACCEPTED');
      setShowRetrainModal(false);
      setLiveKpis(prev => ({ ...prev, inQueue: prev.inQueue === null ? 1 : prev.inQueue + 1 }));
      triggerToast(data.message || '재학습 작업이 대기열에 성공적으로 등록되었습니다.');
    } catch {
      setShowRetrainModal(false);
      triggerToast('재학습 요청이 수락되지 않았습니다.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleExecuteApproval() {
    if (!approvalAllowed) {
      triggerToast('BLOCKED: 검증된 모델·사람 승인 근거가 없습니다.');
      return;
    }
    setIsSubmitting(true);
    try {
      const res = await fetch('/v1/mlops/approval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: approvalModel,
          version: approvalVersion,
          target_env: 'production',
          requested_by: 'GeoAI Team 최준오',
          rationale: approvalRationale,
        }),
      });
      if (!res.ok) throw new Error(`APPROVAL_HTTP_${res.status}`);
      const data = await res.json();
      if (data.status !== 'success' && data.status !== 'accepted') throw new Error('APPROVAL_NOT_ACCEPTED');
      setShowApprovalModal(false);
      if (data.approval) {
        const item: ApprovalItem = {
          id: data.approval.id,
          model_name: data.approval.model_name || `${approvalModel} ${approvalVersion}`,
          requested_by: data.approval.requested_by || 'GeoAI Team',
          date: data.approval.date?.substring(0, 10) || '일자 미확인',
          status: '검토중',
          status_code: 'pending',
        };
        setApprovalsList(prev => [item, ...prev]);
      }
      triggerToast(data.message || '승인 요청이 성공적으로 접수되었습니다.');
    } catch {
      setShowApprovalModal(false);
      triggerToast('승인 요청이 수락되지 않았습니다.');
    } finally {
      setIsSubmitting(false);
    }
  }

  const experimentData = EXPERIMENT_RUNS[selectedExperimentModel] || EXPERIMENT_RUNS['lcluc'];

  function triggerToast(msg: string) {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 2500);
  }

  return (
    <div className="mlops-workspace" data-testid="model-mlops-workspace">
      {/* 1. Top Context Bar */}
      <div className="mlops-top-bar">
        <div className="mlops-breadcrumb">
          <span>홈</span>
          <span className="sep">›</span>
          <span className="current">모델 & MLOps</span>
        </div>
        <div className="mlops-top-controls">
          <div className="mlops-timestamp">
            <span role="img" aria-label="evidence">🔒</span>
            <span>요약 API 증거 상태 기준</span>
          </div>
          <select
            className="mlops-period-select"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            aria-label="기간 선택"
          >
            <option value="최근 7일">최근 7일</option>
            <option value="최근 30일">최근 30일</option>
            <option value="최근 90일">최근 90일</option>
            <option value="전체">전체</option>
          </select>
        </div>
      </div>

      {/* 2. Title Card / Hero Banner */}
      <div className="mlops-hero-card">
        <div className="mlops-hero-icon" aria-hidden="true">
          ⬡
        </div>
        <div className="mlops-hero-text">
          <h1>모델 & MLOps</h1>
          <p>AI 모델의 등록, 학습, 검증, 배포, 모니터링, 재학습을 통합 관리합니다.</p>
          <p role="status" style={{ marginTop: '8px', color: '#b45309', fontWeight: 700 }}>
            {summaryStatus} · 실제 학습·측정 예측·사람 승인·운영 배포 근거 없음
            {reasonCodes.length > 0 ? ` · ${reasonCodes.join(', ')}` : ''}
          </p>
        </div>
      </div>

      {/* 3. Top 6 KPI Summary Cards */}
      <div className="mlops-kpi-row">
        {/* KPI 1 */}
        <div className="mlops-kpi-card blue">
          <div className="mlops-kpi-header">
            <div className="mlops-kpi-icon-wrap">⬡</div>
            <div className="mlops-kpi-title-block">
              <span className="mlops-kpi-title">운영 모델</span>
              <span className="mlops-kpi-subtitle">(Production)</span>
            </div>
          </div>
          <div className="mlops-kpi-body">
            <div>
              <span className="mlops-kpi-value">{displayMetric(liveKpis.modelsProd)}</span>
            </div>
          </div>
        </div>

        {/* KPI 2 */}
        <div className="mlops-kpi-card orange">
          <div className="mlops-kpi-header">
            <div className="mlops-kpi-icon-wrap">⏱</div>
            <div className="mlops-kpi-title-block">
              <span className="mlops-kpi-title">학습 대기</span>
              <span className="mlops-kpi-subtitle">(In Queue)</span>
            </div>
          </div>
          <div className="mlops-kpi-body">
            <div>
              <span className="mlops-kpi-value">{displayMetric(liveKpis.inQueue)}</span>
            </div>
          </div>
        </div>

        {/* KPI 3 */}
        <div className="mlops-kpi-card cyan">
          <div className="mlops-kpi-header">
            <div className="mlops-kpi-icon-wrap">🚀</div>
            <div className="mlops-kpi-title-block">
              <span className="mlops-kpi-title">배포 버전</span>
              <span className="mlops-kpi-subtitle">(Last 30 days)</span>
            </div>
          </div>
          <div className="mlops-kpi-body">
            <div>
              <span className="mlops-kpi-value">{displayMetric(liveKpis.deployments30d)}</span>
            </div>
          </div>
        </div>

        {/* KPI 4 */}
        <div className="mlops-kpi-card red">
          <div className="mlops-kpi-header">
            <div className="mlops-kpi-icon-wrap">🔄</div>
            <div className="mlops-kpi-title-block">
              <span className="mlops-kpi-title">재학습 필요</span>
              <span className="mlops-kpi-subtitle">(Needs Retraining)</span>
            </div>
          </div>
          <div className="mlops-kpi-body">
            <div>
              <span className="mlops-kpi-value">{displayMetric(liveKpis.retrainNeeded)}</span>
            </div>
          </div>
        </div>

        {/* KPI 5 */}
        <div className="mlops-kpi-card green">
          <div className="mlops-kpi-header">
            <div className="mlops-kpi-icon-wrap">📊</div>
            <div className="mlops-kpi-title-block">
              <span className="mlops-kpi-title">평균 F1 Score</span>
              <span className="mlops-kpi-subtitle">(All Models)</span>
            </div>
          </div>
          <div className="mlops-kpi-body">
            <div>
              <span className="mlops-kpi-value">{displayMetric(liveKpis.avgF1, 2)}</span>
            </div>
          </div>
        </div>

        {/* KPI 6 */}
        <div className="mlops-kpi-card blue">
          <div className="mlops-kpi-header">
            <div className="mlops-kpi-icon-wrap">🥞</div>
            <div className="mlops-kpi-title-block">
              <span className="mlops-kpi-title">평균 mIoU</span>
              <span className="mlops-kpi-subtitle">(LCLUC/Segmentation)</span>
            </div>
          </div>
          <div className="mlops-kpi-body">
            <div>
              <span className="mlops-kpi-value">{displayMetric(liveKpis.avgMiou, 2)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Split Layout: Main Column + Right Insights Panel */}
      <div className="mlops-layout-split">
        {/* Main 3 Rows Column */}
        <div className="mlops-main-column">
          {/* ROW 1: Model Registry + (Pipeline & Experiments) */}
          <div className="mlops-grid-row-1">
            {/* Left: Model Registry */}
            <div className="mlops-section-card">
              <div className="mlops-section-header">
                <div className="mlops-section-header-title">
                  <span>모델 레지스트리 (Model Registry)</span>
                </div>
                <button
                  className="mlops-section-link"
                  onClick={() => onNavigate?.(6)}
                >
                  전체보기 →
                </button>
              </div>

              <div className="mlops-table-wrap">
                <table className="mlops-table">
                  <thead>
                    <tr>
                      <th style={{ width: '28px' }}>#</th>
                      <th>모델명 (Model)</th>
                      <th>담당기관</th>
                      <th>현재버전</th>
                      <th>상태</th>
                      <th>최근 배포일</th>
                      <th style={{ width: '24px' }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {INITIAL_MODELS.map((m) => (
                      <tr key={m.id}>
                        <td style={{ color: '#94a3b8', fontWeight: 600 }}>{m.id}</td>
                        <td>
                          <div className="mlops-model-cell">
                            <div className="mlops-model-icon" style={{ background: m.iconBg }}>
                              {m.iconText}
                            </div>
                            <div className="mlops-model-text">
                              <span className="mlops-model-name">{m.name}</span>
                              <span className="mlops-model-sub">{m.subName}</span>
                            </div>
                          </div>
                        </td>
                        <td style={{ color: '#475569' }}>{m.agency}</td>
                        <td style={{ fontWeight: 600, color: '#334155' }}>{m.version}</td>
                        <td>
                          <span className={`mlops-badge-status ${m.statusType}`}>
                            {m.status}
                          </span>
                        </td>
                        <td style={{ color: '#64748b' }}>{m.deployDate}</td>
                        <td>
                          <button
                            className="mlops-btn-action-more"
                            title="옵션"
                            onClick={() => triggerToast(`${m.name} 세부 옵션 열림`)}
                          >
                            ···
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Right Stack: Training Pipeline & Experiment Tracking */}
            <div className="mlops-right-stack-row-1">
              {/* Top: Training Pipeline */}
              <div className="mlops-section-card">
                <div className="mlops-section-header">
                  <div className="mlops-section-header-title">
                    <span>학습 파이프라인 (Training Pipeline)</span>
                  </div>
                  <button className="mlops-section-link" onClick={() => onNavigate?.(3)}>
                    상세보기 →
                  </button>
                </div>

                <div className="mlops-pipeline-flow">
                  {/* Step 1 */}
                  <div className="mlops-pipeline-step pending">
                    <div className="mlops-pipeline-icon">🗄️</div>
                    <span className="mlops-pipeline-name">데이터 수집</span>
                    <span className="mlops-pipeline-sub">Data Ingestion</span>
                    <span className="mlops-pipeline-badge gray">{PIPELINE_BLOCKED_LABEL}</span>
                  </div>
                  <span className="mlops-pipeline-arrow">→</span>

                  {/* Step 2 */}
                  <div className="mlops-pipeline-step pending">
                    <div className="mlops-pipeline-icon">⚙️</div>
                    <span className="mlops-pipeline-name">전처리</span>
                    <span className="mlops-pipeline-sub">Preprocessing</span>
                    <span className="mlops-pipeline-badge gray">{PIPELINE_BLOCKED_LABEL}</span>
                  </div>
                  <span className="mlops-pipeline-arrow">→</span>

                  {/* Step 3 */}
                  <div className="mlops-pipeline-step pending">
                    <div className="mlops-pipeline-icon">🛡️</div>
                    <span className="mlops-pipeline-name">라벨/정합성</span>
                    <span className="mlops-pipeline-sub">QA</span>
                    <span className="mlops-pipeline-badge gray">{PIPELINE_BLOCKED_LABEL}</span>
                  </div>
                  <span className="mlops-pipeline-arrow">→</span>

                  {/* Step 4 */}
                  <div className="mlops-pipeline-step pending">
                    <div className="mlops-pipeline-icon">🧠</div>
                    <span className="mlops-pipeline-name">모델 학습</span>
                    <span className="mlops-pipeline-sub">Training</span>
                    <span className="mlops-pipeline-badge gray">BLOCKED</span>
                  </div>
                  <span className="mlops-pipeline-arrow">→</span>

                  {/* Step 5 */}
                  <div className="mlops-pipeline-step pending">
                    <div className="mlops-pipeline-icon">📊</div>
                    <span className="mlops-pipeline-name">성능 검증</span>
                    <span className="mlops-pipeline-sub">Validation</span>
                    <span className="mlops-pipeline-badge gray">대기</span>
                  </div>
                  <span className="mlops-pipeline-arrow">→</span>

                  {/* Step 6 */}
                  <div className="mlops-pipeline-step pending">
                    <div className="mlops-pipeline-icon">✓</div>
                    <span className="mlops-pipeline-name">승인</span>
                    <span className="mlops-pipeline-sub">Approval</span>
                    <span className="mlops-pipeline-badge gray">대기</span>
                  </div>
                  <span className="mlops-pipeline-arrow">→</span>

                  {/* Step 7 */}
                  <div className="mlops-pipeline-step pending">
                    <div className="mlops-pipeline-icon">☁️</div>
                    <span className="mlops-pipeline-name">배포</span>
                    <span className="mlops-pipeline-sub">Deployment</span>
                    <span className="mlops-pipeline-badge gray">대기</span>
                  </div>
                  <span className="mlops-pipeline-arrow">→</span>

                  {/* Step 8 */}
                  <div className="mlops-pipeline-step pending">
                    <div className="mlops-pipeline-icon">📈</div>
                    <span className="mlops-pipeline-name">모니터링</span>
                    <span className="mlops-pipeline-sub">Monitoring</span>
                    <span className="mlops-pipeline-badge gray">미검증</span>
                  </div>
                  <span className="mlops-pipeline-arrow">→</span>

                  {/* Step 9 */}
                  <div className="mlops-pipeline-step">
                    <div className="mlops-pipeline-icon">🔄</div>
                    <span className="mlops-pipeline-name">재학습</span>
                    <span className="mlops-pipeline-sub">Retraining</span>
                    <span className="mlops-pipeline-badge gray">BLOCKED</span>
                  </div>
                </div>
                <div
                  data-testid="retraining-evidence-contract"
                  style={{ marginTop: '12px', padding: '12px', borderRadius: '10px', background: '#fff7ed', color: '#7c2d12' }}
                >
                  <strong>주 전체 보완·재학습 증거 게이트</strong>
                  <div style={{ marginTop: '6px', lineHeight: 1.55 }}>
                    {retrainingStages.length > 0
                      ? retrainingStages.map((stage) => (
                        <div key={stage.id}>
                          {stage.name}: {stage.status.toUpperCase()} · {stage.reasonCode}
                        </div>
                      ))
                      : <div>BLOCKED · 재학습 준비성 근거를 불러오지 못했습니다.</div>}
                  </div>
                  <div style={{ marginTop: '8px' }}>
                    모델 confidence: {confidenceStatus}
                  </div>
                  <div>
                    독립 accuracy/F1/mIoU: {accuracyStatus}
                  </div>
                  <small style={{ display: 'block', marginTop: '6px' }}>
                    confidence는 모델 확률의 보정 상태이며 accuracy가 아닙니다. Esri weak label은 독립 정답으로 사용하지 않습니다.
                  </small>
                </div>
              </div>

              {/* Bottom: Experiment Tracking */}
              <div className="mlops-section-card">
                <div className="mlops-section-header">
                  <div className="mlops-section-header-title">
                    <span>실험 추적 (Experiment Tracking)</span>
                  </div>
                  <button className="mlops-section-link" onClick={() => onNavigate?.(3)}>
                    상세보기 →
                  </button>
                </div>

                <div className="mlops-experiment-filter-row">
                  <div className="mlops-experiment-select-group">
                    <label>모델</label>
                    <select
                      value={selectedExperimentModel}
                      onChange={(e) => setSelectedExperimentModel(e.target.value)}
                    >
                      <option value="lcluc">LCLUC (Land Cover & Land Use Change)</option>
                      <option value="climate">Climate Downscaling (기후 상세화)</option>
                      <option value="carbon">Net Carbon Footprint (탄소 순배출량)</option>
                    </select>
                  </div>
                  <div className="mlops-chart-legend">
                    <div className="mlops-legend-item">
                      <span className="mlops-legend-dot run1" />
                      <span>Run-001</span>
                    </div>
                    <div className="mlops-legend-item">
                      <span className="mlops-legend-dot run2" />
                      <span>Run-002</span>
                    </div>
                    <div className="mlops-legend-item">
                      <span className="mlops-legend-dot run3" />
                      <span>Run-003 (합성 예시)</span>
                    </div>
                  </div>
                </div>

                <div className="mlops-experiment-body">
                  {/* Grouped Bar Chart */}
                  <div className="mlops-grouped-bar-chart">
                    <div className="mlops-chart-y-axis-row">
                      {/* Metric 1: Accuracy */}
                      <div className="mlops-chart-group">
                        <div
                          className="mlops-bar-pillar run1"
                          style={{ height: `${experimentData.accuracy[0] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.accuracy[0]}</span>
                        </div>
                        <div
                          className="mlops-bar-pillar run2"
                          style={{ height: `${experimentData.accuracy[1] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.accuracy[1]}</span>
                        </div>
                        <div
                          className="mlops-bar-pillar run3"
                          style={{ height: `${experimentData.accuracy[2] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.accuracy[2]}</span>
                        </div>
                      </div>

                      {/* Metric 2: Precision */}
                      <div className="mlops-chart-group">
                        <div
                          className="mlops-bar-pillar run1"
                          style={{ height: `${experimentData.precision[0] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.precision[0]}</span>
                        </div>
                        <div
                          className="mlops-bar-pillar run2"
                          style={{ height: `${experimentData.precision[1] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.precision[1]}</span>
                        </div>
                        <div
                          className="mlops-bar-pillar run3"
                          style={{ height: `${experimentData.precision[2] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.precision[2]}</span>
                        </div>
                      </div>

                      {/* Metric 3: Recall */}
                      <div className="mlops-chart-group">
                        <div
                          className="mlops-bar-pillar run1"
                          style={{ height: `${experimentData.recall[0] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.recall[0]}</span>
                        </div>
                        <div
                          className="mlops-bar-pillar run2"
                          style={{ height: `${experimentData.recall[1] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.recall[1]}</span>
                        </div>
                        <div
                          className="mlops-bar-pillar run3"
                          style={{ height: `${experimentData.recall[2] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.recall[2]}</span>
                        </div>
                      </div>

                      {/* Metric 4: F1-Score */}
                      <div className="mlops-chart-group">
                        <div
                          className="mlops-bar-pillar run1"
                          style={{ height: `${experimentData.f1[0] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.f1[0]}</span>
                        </div>
                        <div
                          className="mlops-bar-pillar run2"
                          style={{ height: `${experimentData.f1[1] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.f1[1]}</span>
                        </div>
                        <div
                          className="mlops-bar-pillar run3"
                          style={{ height: `${experimentData.f1[2] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.f1[2]}</span>
                        </div>
                      </div>

                      {/* Metric 5: mIoU */}
                      <div className="mlops-chart-group">
                        <div
                          className="mlops-bar-pillar run1"
                          style={{ height: `${experimentData.miou[0] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.miou[0]}</span>
                        </div>
                        <div
                          className="mlops-bar-pillar run2"
                          style={{ height: `${experimentData.miou[1] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.miou[1]}</span>
                        </div>
                        <div
                          className="mlops-bar-pillar run3"
                          style={{ height: `${experimentData.miou[2] * 100}%` }}
                        >
                          <span className="mlops-bar-val-tip">{experimentData.miou[2]}</span>
                        </div>
                      </div>
                    </div>
                    <div className="mlops-chart-x-labels">
                      <span>Accuracy</span>
                      <span>Precision</span>
                      <span>Recall</span>
                      <span>F1-Score</span>
                      <span>mIoU</span>
                    </div>
                  </div>

                  {/* Best Run Box */}
                  <div className="mlops-best-run-box">
                    <span className="mlops-best-run-title">
                      TESTED_SYNTHETIC <br /> (결정론적 시나리오)
                    </span>
                    <span className="mlops-best-run-name">
                      {experimentData.bestRun} <small style={{ fontSize: '11px', color: '#64748b' }}>실학습 버전 아님</small>
                    </span>
                    <div className="mlops-best-run-metric">
                      <span>F1-Score</span>
                      <strong>{experimentData.bestF1}</strong>
                    </div>
                    <div className="mlops-best-run-metric">
                      <span>mIoU</span>
                      <strong>{experimentData.bestMiou}</strong>
                    </div>
                    <span className="mlops-best-run-badge">
                      과학 성능·승격 근거로 사용 금지
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ROW 2: Dataset & Coverage (Left) + Monitoring & Drift (Right) */}
          <div className="mlops-grid-row-2">
            {/* Left: Dataset & Coverage */}
            <div className="mlops-section-card">
              <div className="mlops-section-header">
                <div className="mlops-section-header-title">
                  <span>데이터셋 & 커버리지 (Dataset & Coverage)</span>
                </div>
                <button className="mlops-section-link" onClick={() => onNavigate?.(1)}>
                  전체보기 →
                </button>
              </div>

              {/* Source Badges */}
              <div className="mlops-source-badges-row">
                <div className="mlops-source-badge">
                  <strong>Sentinel-2</strong>
                  <span>위성영상 (10 m)</span>
                </div>
                <div className="mlops-source-badge">
                  <strong>Esri Land Cover</strong>
                  <span>(2020 / 2022)</span>
                </div>
                <div className="mlops-source-badge">
                  <strong>WorldCover</strong>
                  <span>(10 m)</span>
                </div>
                <div className="mlops-source-badge">
                  <strong>SCL</strong>
                  <span>구름 마스크</span>
                </div>
                <div className="mlops-source-badge">
                  <strong>AOI</strong>
                  <span>6개 주 경계</span>
                </div>
              </div>

              {/* Split: Table + Mini Map */}
              <div className="mlops-coverage-split">
                <div className="mlops-table-wrap">
                  <table className="mlops-table">
                    <thead>
                      <tr>
                        <th>주 (Province)</th>
                        <th>면적 (km²)</th>
                        <th>데이터 커버리지</th>
                        <th>구름률</th>
                        <th>결측률</th>
                      </tr>
                    </thead>
                    <tbody>
                      {coverageRows.map((row) => (
                        <tr key={row.province}>
                          <td style={{ fontWeight: 600, color: '#1e293b' }}>{row.province}</td>
                          <td style={{ color: '#475569' }}>{row.areaKm2}</td>
                          <td>
                            <div className="mlops-coverage-bar-cell">
                              <div className="mlops-coverage-bar-bg">
                                <div
                                  className="mlops-coverage-bar-fill"
                                  style={{ width: `${row.coveragePct ?? 0}%` }}
                                />
                              </div>
                              <span className="mlops-coverage-pct-txt">{coverageCell(row.coveragePct)}</span>
                            </div>
                          </td>
                          <td className="mlops-diff-red">{coverageCell(row.cloudPct)}</td>
                          <td className="mlops-diff-red">{coverageCell(row.missingPct)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mini Choropleth Map */}
                <div className="mlops-mini-map-box">
                  <svg
                    className="mlops-mini-map-svg"
                    viewBox="0 0 320 150"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    {/* 위치 안내용 단색 개략도. 커버리지 측정값은 아직 없다. */}
                    {/* Sumatra background outline */}
                    <path
                      d="M20 50 L45 75 L70 100 L55 110 L30 85 Z"
                      fill="#e2e8f0"
                      stroke="#cbd5e1"
                      strokeWidth="1"
                    />
                    {/* West Java & Banten */}
                    <path
                      d="M75 115 L95 118 L110 116 L105 125 L80 123 Z"
                      fill="#e2e8f0"
                      stroke="#cbd5e1"
                      strokeWidth="1.5"
                    />
                    {/* East Java */}
                    <path
                      d="M112 116 L145 115 L155 122 L120 124 Z"
                      fill="#e2e8f0"
                      stroke="#cbd5e1"
                      strokeWidth="1.5"
                    />
                    {/* Kalimantan outline */}
                    <path
                      d="M100 45 L145 40 L160 80 L125 90 L105 70 Z"
                      fill="#e2e8f0"
                      stroke="#cbd5e1"
                      strokeWidth="1"
                    />
                    {/* Sulawesi (South Sulawesi & Southeast Sulawesi & Gorontalo) */}
                    {/* Gorontalo (Northern arm) */}
                    <path
                      d="M185 45 L210 40 L215 48 L195 50 Z"
                      fill="#e2e8f0"
                      stroke="#cbd5e1"
                      strokeWidth="1.5"
                    />
                    {/* South & Southeast Sulawesi */}
                    <path
                      d="M180 55 L190 70 L185 95 L175 100 L172 75 L180 55 Z"
                      fill="#e2e8f0"
                      stroke="#cbd5e1"
                      strokeWidth="1.5"
                    />
                    <path
                      d="M188 75 L205 85 L200 95 L185 90 Z"
                      fill="#e2e8f0"
                      stroke="#cbd5e1"
                      strokeWidth="1.5"
                    />
                    {/* Maluku & Papua background */}
                    <path
                      d="M225 50 L235 65 L225 80 Z"
                      fill="#e2e8f0"
                      stroke="#cbd5e1"
                      strokeWidth="1"
                    />
                    <path
                      d="M250 60 L295 55 L310 90 L265 95 Z"
                      fill="#e2e8f0"
                      stroke="#cbd5e1"
                      strokeWidth="1"
                    />
                  </svg>
                  <div className="mlops-mini-map-legend">
                    <span className="mlops-mini-map-legend-label">커버리지 미측정 · 위치 안내만 제공</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Monitoring & Drift */}
            <div className="mlops-section-card">
              <div className="mlops-section-header">
                <div className="mlops-section-header-title">
                  <span>모니터링 & 드리프트 (Monitoring & Drift)</span>
                  <span className="mlops-live-badge">근거 없음</span>
                </div>
                <button className="mlops-section-link" onClick={() => onNavigate?.(18)}>
                  전체보기 →
                </button>
              </div>

              {/* 5 KPI Metric Columns */}
              <div className="mlops-monitoring-kpis-grid">
                <div className="mlops-mon-kpi-col">
                  <span className="mlops-mon-kpi-label">추론 요청 수<br />(Inference)</span>
                  <span className="mlops-mon-kpi-val">미측정</span>
                </div>
                <div className="mlops-mon-kpi-col">
                  <span className="mlops-mon-kpi-label">평균 지연시간<br />(Latency)</span>
                  <span className="mlops-mon-kpi-val">미측정</span>
                </div>
                <div className="mlops-mon-kpi-col">
                  <span className="mlops-mon-kpi-label">실패한 작업<br />(Failed Jobs)</span>
                  <span className="mlops-mon-kpi-val">미측정</span>
                </div>
                <div className="mlops-mon-kpi-col">
                  <span className="mlops-mon-kpi-label">데이터 드리프트<br />(Data Drift)</span>
                  <span className="mlops-mon-kpi-val">미측정</span>
                </div>
                <div className="mlops-mon-kpi-col">
                  <span className="mlops-mon-kpi-label">클래스 불균형<br />(Class Imbalance)</span>
                  <span className="mlops-mon-kpi-val">미측정</span>
                </div>
              </div>

              <div className="mlops-drift-sparkline-wrap" role="status">
                측정 예측과 기준 성능이 없어 추론·드리프트 시계열을 표시할 수 없습니다.
              </div>

              {/* Alert Banner */}
              <div className="mlops-alert-banner">
                <div className="mlops-alert-left">
                  <div className="mlops-alert-icon">⚠️</div>
                  <div className="mlops-alert-text">
                    <span className="mlops-alert-title">재학습 차단 (Retraining Blocked)</span>
                    <span className="mlops-alert-desc">
                      실행된 학습·측정 예측·독립 검증 근거가 없어 재학습 트리거를 판단할 수 없습니다.
                    </span>
                  </div>
                </div>
                <button
                  className="mlops-btn-retrain"
                  onClick={() => setShowRetrainModal(true)}
                  disabled={!trainingAllowed}
                  title={!trainingAllowed ? 'BLOCKED_NO_EXECUTED_TRAINING_OR_MEASURED_PREDICTIONS' : undefined}
                >
                  {trainingAllowed ? '재학습 실행 >' : '재학습 차단'}
                </button>
              </div>
            </div>
          </div>

          {/* ROW 3: Deployment & Serving (Left) + Approval Workflow (Right) */}
          <div className="mlops-grid-row-3">
            {/* Left: Deployment & Serving */}
            <div className="mlops-section-card">
              <div className="mlops-section-header">
                <div className="mlops-section-header-title">
                  <span>배포 및 서비스 (Deployment & Serving)</span>
                </div>
                <button className="mlops-section-link" onClick={() => onNavigate?.(17)}>
                  전체보기 →
                </button>
              </div>

              <div className="mlops-envs-grid">
                {/* Dev Env */}
                <div className="mlops-env-card">
                  <div className="mlops-env-top">
                    <div>
                      <div className="mlops-env-title">개발 (Dev)</div>
                      <div className="mlops-env-sub">개발/실험 환경</div>
                    </div>
                    <span className="mlops-badge-status info">미검증</span>
                  </div>
                  <div className="mlops-env-pods-info">
                    <span className="k8s-icon">☸</span>
                    <span>Kubernetes</span>
                    <strong style={{ marginLeft: 'auto' }}>실행 근거 없음</strong>
                  </div>
                  <div className="mlops-env-endpoints">
                    <div className="mlops-env-endpoint-row">
                      <span
                        className="mlops-env-endpoint-link"
                        title="검증되지 않은 계획 endpoint"
                      >
                        🔒 계획 endpoint · 미검증
                      </span>
                      <button
                        className="mlops-btn-action-more"
                        onClick={() => triggerToast('검증된 개발 endpoint가 없습니다.')}
                        title="미검증"
                      >
                        📋
                      </button>
                    </div>
                    <div className="mlops-env-endpoint-row">
                      <a
                        href="http://127.0.0.1:8088/geoserver/web/"
                        target="_blank"
                        rel="noreferrer"
                        className="mlops-env-endpoint-link"
                      >
                        🗺️ GeoServer
                      </a>
                    </div>
                  </div>
                </div>

                {/* Staging Env */}
                <div className="mlops-env-card">
                  <div className="mlops-env-top">
                    <div>
                      <div className="mlops-env-title">스테이징 (Staging)</div>
                      <div className="mlops-env-sub">사전 검증 환경</div>
                    </div>
                    <span className="mlops-badge-status info">미검증</span>
                  </div>
                  <div className="mlops-env-pods-info">
                    <span className="k8s-icon">☸</span>
                    <span>Kubernetes</span>
                    <strong style={{ marginLeft: 'auto' }}>실행 근거 없음</strong>
                  </div>
                  <div className="mlops-env-endpoints">
                    <div className="mlops-env-endpoint-row">
                      <span
                        className="mlops-env-endpoint-link"
                        title="검증되지 않은 계획 endpoint"
                      >
                        🔒 계획 endpoint · 미검증
                      </span>
                      <button
                        className="mlops-btn-action-more"
                        onClick={() => triggerToast('검증된 스테이징 endpoint가 없습니다.')}
                        title="미검증"
                      >
                        📋
                      </button>
                    </div>
                    <div className="mlops-env-endpoint-row">
                      <a
                        href="http://127.0.0.1:8088/geoserver/web/"
                        target="_blank"
                        rel="noreferrer"
                        className="mlops-env-endpoint-link"
                      >
                        🗺️ GeoServer
                      </a>
                    </div>
                  </div>
                </div>

                {/* Production Env */}
                <div className="mlops-env-card">
                  <div className="mlops-env-top">
                    <div>
                      <div className="mlops-env-title">운영 (Production)</div>
                      <div className="mlops-env-sub">대국민 서비스</div>
                    </div>
                    <span className="mlops-badge-status info">미검증</span>
                  </div>
                  <div className="mlops-env-pods-info">
                    <span className="k8s-icon">☸</span>
                    <span>Kubernetes</span>
                    <strong style={{ marginLeft: 'auto' }}>실행 근거 없음</strong>
                  </div>
                  <div className="mlops-env-endpoints">
                    <div className="mlops-env-endpoint-row">
                      <span
                        className="mlops-env-endpoint-link"
                        title="검증되지 않은 계획 endpoint"
                      >
                        🔒 계획 endpoint · 미검증
                      </span>
                      <button
                        className="mlops-btn-action-more"
                        onClick={() => triggerToast('검증된 운영 endpoint가 없습니다.')}
                        title="미검증"
                      >
                        📋
                      </button>
                    </div>
                    <div className="mlops-env-endpoint-row">
                      <a
                        href="http://127.0.0.1:8088/geoserver/web/"
                        target="_blank"
                        rel="noreferrer"
                        className="mlops-env-endpoint-link"
                      >
                        🗺️ GeoServer
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Approval Workflow */}
            <div className="mlops-section-card">
              <div className="mlops-section-header">
                <div className="mlops-section-header-title">
                  <span>승인 워크플로우 (Human-in-the-loop)</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <button
                    className="mlops-btn-new-request"
                    onClick={() => setShowApprovalModal(true)}
                    disabled={!approvalAllowed}
                    title={!approvalAllowed ? 'BLOCKED_NO_HUMAN_APPROVAL_EVIDENCE' : undefined}
                  >
                    {approvalAllowed ? '+ 새 승인 요청' : '승인 요청 차단'}
                  </button>
                  <button className="mlops-section-link" onClick={() => onNavigate?.(17)}>
                    전체보기 →
                  </button>
                </div>
              </div>

              {/* 4-Step Flow */}
              <div className="mlops-workflow-steps-row">
                <div className="mlops-wf-step">
                  <div className="mlops-wf-step-icon">👤</div>
                  <span>검토자 (Reviewer)</span>
                </div>
                <span className="mlops-wf-arrow">→</span>

                <div className="mlops-wf-step">
                  <div className="mlops-wf-step-icon">📋</div>
                  <span>성능 검토 (Evaluation)</span>
                </div>
                <span className="mlops-wf-arrow">→</span>

                <div className="mlops-wf-step">
                  <div className="mlops-wf-step-icon">✓</div>
                  <span>승인 / 반려 (Approval)</span>
                </div>
                <span className="mlops-wf-arrow">→</span>

                <div className="mlops-wf-step">
                  <div className="mlops-wf-step-icon">🚀</div>
                  <span>배포 (Release)</span>
                </div>
              </div>

              {/* Recent Approval Table */}
              <div className="mlops-table-wrap" style={{ marginTop: '4px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: '#475569' }}>
                  최근 승인 이력
                </span>
                <table className="mlops-table" style={{ marginTop: '6px' }}>
                  <thead>
                    <tr>
                      <th>모델명</th>
                      <th>요청자</th>
                      <th>요청일</th>
                      <th>상태</th>
                    </tr>
                  </thead>
                  <tbody>
                    {approvalsList.length === 0 && (
                      <tr><td colSpan={4} style={{ color: '#64748b' }}>확인된 승인 이력이 없습니다.</td></tr>
                    )}
                    {approvalsList.map((app) => (
                      <tr key={app.id}>
                        <td style={{ fontWeight: 600, color: '#1e293b' }}>{app.model_name}</td>
                        <td style={{ color: '#475569' }}>{app.requested_by}</td>
                        <td style={{ color: '#64748b' }}>{app.date}</td>
                        <td>
                          <span
                            className={`mlops-badge-status ${
                              app.status_code === 'approved' || app.status === '승인'
                                ? 'active'
                                : app.status_code === 'pending' || app.status === '검토중'
                                ? 'info'
                                : 'warning'
                            }`}
                          >
                            {app.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        {/* Right Sidebar: Operational Insights Panel */}
        <div className="mlops-insights-panel">
          <div className="mlops-insights-header">
            <span className="bulb">💡</span>
            <span>운영 인사이트</span>
          </div>

          {/* Insight 1 */}
          <div className="mlops-insight-item">
            <div className="mlops-insight-icon green">⬡</div>
            <div className="mlops-insight-content">
              <span className="mlops-insight-title">모델 버전 관리</span>
              <span className="mlops-insight-desc">
                모델 항목은 계획 목록이며 실제 버전·배포 이력은 확인되지 않았습니다.
              </span>
            </div>
          </div>

          {/* Insight 2 */}
          <div className="mlops-insight-item">
            <div className="mlops-insight-icon blue">🗄️</div>
            <div className="mlops-insight-content">
              <span className="mlops-insight-title">데이터셋 계보 추적</span>
              <span className="mlops-insight-desc">
                위성영상, 보조자료, 전처리 이력을 추적하여 데이터 신뢰도를 확보합니다.
              </span>
            </div>
          </div>

          {/* Insight 3 */}
          <div className="mlops-insight-item">
            <div className="mlops-insight-icon orange">📊</div>
            <div className="mlops-insight-content">
              <span className="mlops-insight-title">성능 비교 및 실험 관리</span>
              <span className="mlops-insight-desc">
                합성 시나리오는 UI 동작 확인용이며 최적 모델이나 과학 성능을 뜻하지 않습니다.
              </span>
            </div>
          </div>

          {/* Insight 4 */}
          <div className="mlops-insight-item">
            <div className="mlops-insight-icon cyan">☁️</div>
            <div className="mlops-insight-content">
              <span className="mlops-insight-title">배포 상태 확인</span>
              <span className="mlops-insight-desc">
                로컬 서비스 상태만 별도 확인하며 개발·스테이징·운영 배포는 검증되지 않았습니다.
              </span>
            </div>
          </div>

          {/* Insight 5 */}
          <div className="mlops-insight-item">
            <div className="mlops-insight-icon green">🔄</div>
            <div className="mlops-insight-content">
              <span className="mlops-insight-title">재학습 트리거 확인</span>
              <span className="mlops-insight-desc">
                측정 예측과 기준 성능이 없어 재학습 필요 시점 판단은 차단됩니다.
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Retrain Modal */}
      {showRetrainModal && (
        <div className="mlops-modal-overlay" onClick={() => setShowRetrainModal(false)}>
          <div className="mlops-modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="mlops-modal-header">
              <h3>재학습 트리거 실행 확인</h3>
              <button className="mlops-modal-close" onClick={() => setShowRetrainModal(false)}>✕</button>
            </div>
            <div className="mlops-modal-body">
              <p>
                <strong>상태:</strong> BLOCKED_NO_EXECUTED_TRAINING_OR_MEASURED_PREDICTIONS
              </p>
              <p>
                <strong>사유:</strong> 실행된 학습·checkpoint·측정 예측·독립 검증이 없습니다.
              </p>
              <p>
                현재 재학습 요청을 보낼 수 없습니다.
              </p>
            </div>
            <div className="mlops-modal-footer">
              <button
                className="mlops-btn-action-more"
                style={{ padding: '6px 12px', background: '#f1f5f9' }}
                onClick={() => setShowRetrainModal(false)}
                disabled={isSubmitting}
              >
                취소
              </button>
              <button
                className="mlops-btn-retrain"
                disabled={isSubmitting || !trainingAllowed}
                onClick={handleExecuteRetrain}
              >
                {isSubmitting ? '요청 처리 중...' : trainingAllowed ? '재학습 작업 시작' : '재학습 차단'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Approval Modal */}
      {showApprovalModal && (
        <div className="mlops-modal-overlay" onClick={() => setShowApprovalModal(false)}>
          <div className="mlops-modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="mlops-modal-header">
              <h3>새 모델 승인 요청 (Human-in-the-loop)</h3>
              <button className="mlops-modal-close" onClick={() => setShowApprovalModal(false)}>✕</button>
            </div>
            <div className="mlops-modal-body">
              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span>대상 모델 선택</span>
                <select
                  className="mlops-period-select"
                  value={approvalModel}
                  onChange={(e) => {
                    setApprovalModel(e.target.value);
                    if (e.target.value.includes('Climate')) setApprovalVersion('v1.1.1-candidate');
                    else if (e.target.value.includes('Carbon')) setApprovalVersion('v1.0.4-candidate');
                    else setApprovalVersion('v1.2.1-candidate');
                  }}
                >
                  <option value="LCLUC">LCLUC (v1.2.1-candidate)</option>
                  <option value="Climate Downscaling">Climate Downscaling (v1.1.1-candidate)</option>
                  <option value="Net Carbon Footprint">Net Carbon Footprint (v1.0.4-candidate)</option>
                </select>
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span>승인 요청 사유 및 검증 근거</span>
                <textarea
                  className="editor"
                  rows={3}
                  value={approvalRationale}
                  onChange={(e) => setApprovalRationale(e.target.value)}
                />
              </label>
            </div>
            <div className="mlops-modal-footer">
              <button
                className="mlops-btn-action-more"
                style={{ padding: '6px 12px', background: '#f1f5f9' }}
                onClick={() => setShowApprovalModal(false)}
                disabled={isSubmitting}
              >
                닫기
              </button>
              <button
                className="mlops-btn-new-request"
                disabled={isSubmitting || !approvalAllowed || approvalRationale.trim().length === 0}
                onClick={handleExecuteApproval}
              >
                {isSubmitting ? '요청 제출 중...' : approvalAllowed ? '승인 요청 제출' : '승인 요청 차단'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toastMessage && (
        <div
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            background: '#0f172a',
            color: '#ffffff',
            padding: '10px 16px',
            borderRadius: '8px',
            fontSize: '13px',
            boxShadow: '0 10px 15px -3px rgba(0,0,0,0.2)',
            zIndex: 9999,
          }}
        >
          {toastMessage}
        </div>
      )}
    </div>
  );
}
