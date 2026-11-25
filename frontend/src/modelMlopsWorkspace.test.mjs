import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

test('ModelMlopsWorkspace files and components exist', () => {
  const tsxPath = join(process.cwd(), 'frontend', 'src', 'ModelMlopsWorkspace.tsx');
  const cssPath = join(process.cwd(), 'frontend', 'src', 'model-mlops-workspace.css');

  assert.ok(existsSync(tsxPath), 'ModelMlopsWorkspace.tsx must exist');
  assert.ok(existsSync(cssPath), 'model-mlops-workspace.css must exist');

  const tsxContent = readFileSync(tsxPath, 'utf-8');
  const cssContent = readFileSync(cssPath, 'utf-8');

  // Verify 6 Models in Model Registry
  assert.match(tsxContent, /LCLUC/);
  assert.match(tsxContent, /Climate Downscaling/);
  assert.match(tsxContent, /Flood & Drought/);
  assert.match(tsxContent, /Net Carbon Footprint/);
  assert.match(tsxContent, /Biodiversity/);
  assert.match(tsxContent, /Coastal Inundation & Land Subsidence/);

  // Verify Top 6 KPIs
  assert.match(tsxContent, /운영 모델/);
  assert.match(tsxContent, /학습 대기/);
  assert.match(tsxContent, /배포 버전/);
  assert.match(tsxContent, /재학습 필요/);
  assert.match(tsxContent, /평균 F1 Score/);
  assert.match(tsxContent, /평균 mIoU/);

  // Verify 9-Step Training Pipeline
  assert.match(tsxContent, /데이터 수집/);
  assert.match(tsxContent, /전처리/);
  assert.match(tsxContent, /라벨\/정합성/);
  assert.match(tsxContent, /모델 학습/);
  assert.match(tsxContent, /성능 검증/);
  assert.match(tsxContent, /승인/);
  assert.match(tsxContent, /배포/);
  assert.match(tsxContent, /모니터링/);
  assert.match(tsxContent, /재학습/);

  // Verify Experiment Tracking
  assert.match(tsxContent, /Run-001/);
  assert.match(tsxContent, /Run-002/);
  assert.match(tsxContent, /Run-003/);
  assert.match(tsxContent, /TESTED_SYNTHETIC/);
  assert.match(tsxContent, /과학 성능·승격 근거로 사용 금지/);

  // Verify 6 Provinces in Dataset Coverage
  assert.match(tsxContent, /South Sulawesi/);
  assert.match(tsxContent, /Gorontalo/);
  assert.match(tsxContent, /Southeast Sulawesi/);
  assert.match(tsxContent, /Banten/);
  assert.match(tsxContent, /West Java/);
  assert.match(tsxContent, /East Java/);

  // Verify 5 Monitoring Metrics
  assert.match(tsxContent, /추론 요청 수/);
  assert.match(tsxContent, /평균 지연시간/);
  assert.match(tsxContent, /실패한 작업/);
  assert.match(tsxContent, /데이터 드리프트/);
  assert.match(tsxContent, /클래스 불균형/);

  // Verify Retraining Trigger Alert Banner
  assert.match(tsxContent, /재학습 차단/);
  assert.match(tsxContent, /BLOCKED_NO_EXECUTED_TRAINING_OR_MEASURED_PREDICTIONS/);
  assert.match(tsxContent, /주 전체 보완·재학습 증거 게이트/);
  assert.match(tsxContent, /retraining_readiness/);
  assert.match(tsxContent, /NO_VERIFIED_CONFIDENCE_CALIBRATION/);
  assert.match(tsxContent, /NO_INDEPENDENT_GROUND_TRUTH_EVALUATION/);
  assert.match(tsxContent, /confidence는 모델 확률의 보정 상태이며 accuracy가 아닙니다/);
  assert.match(tsxContent, /Esri weak label은 독립 정답으로 사용하지 않습니다/);

  // Verify 3 Deployment Environments
  assert.match(tsxContent, /개발 \(Dev\)/);
  assert.match(tsxContent, /스테이징 \(Staging\)/);
  assert.match(tsxContent, /운영 \(Production\)/);

  // Verify 4-step Human-in-the-loop Approval Workflow
  assert.match(tsxContent, /승인 워크플로우/);
  assert.match(tsxContent, /승인 요청 차단/);
  assert.match(tsxContent, /최근 승인 이력/);

  // Verify 5 Operational Insights in Right Panel
  assert.match(tsxContent, /운영 인사이트/);
  assert.match(tsxContent, /모델 버전 관리/);
  assert.match(tsxContent, /데이터셋 계보 추적/);
  assert.match(tsxContent, /성능 비교 및 실험 관리/);
  assert.match(tsxContent, /배포 상태 확인/);
  assert.match(tsxContent, /재학습 트리거 확인/);

  // Fail closed when operational evidence is missing.
  assert.match(tsxContent, /BLOCKED_SUMMARY_UNAVAILABLE/);
  assert.match(tsxContent, /coveragePct: null/);
  assert.match(tsxContent, /setTrainingAllowed\(false\)/);
  assert.match(tsxContent, /setApprovalAllowed\(false\)/);
  assert.doesNotMatch(tsxContent, /const DEFAULT_APPROVALS/);
  assert.doesNotMatch(tsxContent, /status: '운영중'/);
  assert.doesNotMatch(tsxContent, /12,428/);
  assert.doesNotMatch(tsxContent, /↑ \+18%/);
  assert.match(tsxContent, /커버리지 미측정 · 위치 안내만 제공/);

  // Verify CSS classes
  assert.match(cssContent, /\.mlops-workspace/);
  assert.match(cssContent, /\.mlops-kpi-card/);
  assert.match(cssContent, /\.mlops-insights-panel/);
  assert.match(cssContent, /\.mlops-pipeline-flow/);
  assert.match(cssContent, /\.mlops-grouped-bar-chart/);
  assert.match(cssContent, /\.mlops-alert-banner/);
  assert.match(cssContent, /\.mlops-envs-grid/);
});
