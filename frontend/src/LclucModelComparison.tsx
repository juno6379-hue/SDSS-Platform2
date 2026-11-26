import { useEffect, useState } from 'react';
import { ha } from './lclucExplorerData';

type Sensor = 'landsat' | 'sentinel-2';
type ModelRow = {key: string; method: string; heldout_pixels: number; training_pixels: number; download: string;
  weak_reference_metrics: {overall_accuracy: number; mean_iou: number; macro_f1: number}};
type Benchmark = {year: number; reference: string; rows: ModelRow[]};
const API = '/api/lcluc/postprocess/benchmarks/';
const pct = (value: number) => ha.format(100 * value) + '%';

export default function LclucModelComparison({sensor}: {sensor: Sensor}) {
  const [result, setResult] = useState<Benchmark>();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const cancel = new AbortController();
    setResult(undefined); setFailed(false);
    void fetch(API + sensor, {signal: cancel.signal}).then(async response => {
      if (!response.ok) throw new Error('benchmark');
      const data = await response.json() as Benchmark;
      if (!cancel.signal.aborted) setResult(data);
    }).catch(() => {if (!cancel.signal.aborted) setFailed(true);});
    return () => cancel.abort();
  }, [sensor]);

  if (!result) return <p role="status">{failed ? '모델 비교 조회 실패' : '모델 비교 조회 중'}</p>;
  if (!result.rows.length) return <p role="status">해당 센서의 실자료 비교 결과 대기</p>;
  const first = result.rows[0];
  return <div className="mw-landsat-content">
    <p>반텐 · {result.year}년 · {sensor === 'landsat' ? 'Landsat' : 'Sentinel-2'} 6밴드 · 약 147m 시험 격자</p>
    <p>학습 {ha.format(first.training_pixels)} · 동일 공간 홀드아웃 {ha.format(first.heldout_pixels)}픽셀</p>
    <div className="mw-table-scroll"><table className="mw-table" aria-label={`${sensor} 실자료 모델 비교`}>
      <thead><tr><th>모델</th><th>일치도</th><th>평균 IoU</th><th>Macro F1</th><th>분류 후보</th></tr></thead>
      <tbody>{result.rows.map(item => <tr key={item.key}>
        <th scope="row">{item.method}</th><td>{pct(item.weak_reference_metrics.overall_accuracy)}</td>
        <td>{pct(item.weak_reference_metrics.mean_iou)}</td><td>{pct(item.weak_reference_metrics.macro_f1)}</td>
        <td><a href={item.download} aria-label={item.method + ' 분류 GeoTIFF'}>GeoTIFF</a></td>
      </tr>)}</tbody>
    </table></div>
    <p>동년 {result.reference} 약한 참조 · 독립 정확도 미측정</p>
    <p><a href={API + sensor} target="_blank" rel="noreferrer">혼동행렬·클래스별 시험 근거</a>
      {sensor === 'landsat' && <> · <a href="/api/lcluc/banten-landsat/baseline" target="_blank" rel="noreferrer">RF 기준모델 실행 기록</a></>}</p>
  </div>;
}
