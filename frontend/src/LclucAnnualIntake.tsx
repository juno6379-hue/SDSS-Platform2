import { useEffect, useState } from 'react';

type Sensor = 'sentinel-2' | 'landsat';
type Scores = Partial<Record<Sensor, number | null>>;
type Run = {
  run_id: string; year: number; scope: 'real' | 'synthetic'; state: string; blocker: string | null;
  quality?: Record<Sensor, { physical_fraction: number; clear_fraction: number }>;
  sensor_agreement: number | null; weak_reference_agreement: Scores;
  independent_accuracy: Scores; synthetic_holdout: Scores;
  artifacts?: Record<string, { href: string; sha256: string }>;
};

const states: Record<string, string> = {
  PREPROCESSING: '전처리·품질검사 중',
  WAITING_INPUT: '원본 수신 대기',
  QUALITY_BLOCKED: '광학 자료 품질 기준 미달',
  WAITING_TRAINING_REFERENCE: '동년 학습 라벨 대기',
  WAITING_TRAINING_APPROVAL: '학습 승인 대기',
  TRAINING_AND_INFERENCE: '후보 모델 학습·추론 중',
  WAITING_INDEPENDENT_REFERENCE: '독립 검증자료 대기',
  VERIFICATION_BLOCKED: '검증자료 확인 필요',
  INDEPENDENT_EVALUATED: '독립 정확도 산출',
  TESTED_SYNTHETIC: '합성 검증 완료',
  BLOCKED: '입력 또는 승인 확인 필요',
  RETRYABLE_ERROR: '처리 재시도 대기',
};
const sensors: Record<Sensor, string> = { 'sentinel-2': 'Sentinel-2', landsat: 'Landsat' };
const percent = new Intl.NumberFormat('ko-KR', { style: 'percent', maximumFractionDigits: 2 });

function formatScores(scores: Scores) {
  return (Object.keys(sensors) as Sensor[])
    .filter(sensor => scores[sensor] != null)
    .map(sensor => `${sensors[sensor]} ${percent.format(scores[sensor]!)}`).join(' · ');
}

export default function LclucAnnualIntake({ region, realOnly = false }: { region: string; realOnly?: boolean }) {
  const [snapshot, setSnapshot] = useState<{ region: string; runs: Run[]; error: boolean }>();
  useEffect(() => {
    const controller = new AbortController();
    async function refresh() {
      try {
        const response = await fetch(`/api/lcluc/annual-runs?${new URLSearchParams({ region })}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error();
        const { runs } = await response.json() as { runs: Run[] };
        if (!controller.signal.aborted) setSnapshot({ region, runs, error: false });
      } catch {
        if (!controller.signal.aborted) setSnapshot({ region, runs: [], error: true });
      }
    }
    void refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [region]);
  const current = snapshot?.region === region ? snapshot : undefined;
  const shown = realOnly ? current?.runs.filter(run => run.scope === 'real') : current?.runs;
  if (!shown?.length) return <tr><th>연차 자동 처리</th>
    <td colSpan={2}>{!current ? '접수 상태 조회 중' : current.error ? '접수 상태 조회 실패' : '접수된 신규 연차 자료 없음'}</td></tr>;
  return <>{shown.map(run => <tr key={run.run_id}>
    <th>연차 자동 처리 · {run.year}{run.scope === 'synthetic' && ' (합성 시험)'}</th>
    <td>{states[run.state] ?? run.state}
      {run.quality && (Object.keys(sensors) as Sensor[]).map(sensor => <div key={sensor}>
        {sensors[sensor]} 피복 {percent.format(run.quality![sensor].physical_fraction)}
        {' · 맑은 픽셀 '}{percent.format(run.quality![sensor].clear_fraction)}
      </div>)}
      <a href={`/api/lcluc/annual-runs/${run.run_id}`} target="_blank" rel="noreferrer">처리 증거·출처</a>
      {realOnly && (Object.keys(sensors) as Sensor[]).map(sensor => {
        const cover = run.artifacts?.[sensor + '-cover'];
        const confidence = run.artifacts?.[sensor + '-confidence'];
        return (cover || confidence) && <div key={sensor}>
          {cover && <a href={cover.href}>{sensors[sensor]} 분류 GeoTIFF</a>}
          {cover && confidence && ' · '}
          {confidence && <a href={confidence.href}>신뢰도 GeoTIFF</a>}
        </div>;
      })}
    </td>
    <td>{run.sensor_agreement != null && <div>동년 센서 간 지도 일치도 {percent.format(run.sensor_agreement)}</div>}
      {formatScores(run.weak_reference_agreement) && <div>약한 참조 일치도 {formatScores(run.weak_reference_agreement)}</div>}
      <div>{formatScores(run.independent_accuracy) ? `독립 정확도 ${formatScores(run.independent_accuracy)}` : '독립 정확도 미측정'}</div>
      {formatScores(run.synthetic_holdout) && <div>합성 홀드아웃 {formatScores(run.synthetic_holdout)}</div>}
    </td>
  </tr>)}</>;
}
