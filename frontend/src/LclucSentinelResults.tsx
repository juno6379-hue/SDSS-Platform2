import { useEffect, useState } from 'react';
import LclucAnnualIntake from './LclucAnnualIntake';
import LclucModelComparison from './LclucModelComparison';
import type { SentinelExplorer, SentinelStats } from './LclucSentinelExplorer';
import { ha, SENTINEL_API } from './lclucExplorerData';

export const sentinelResultTitles = {
  area: '클래스 면적·비율',
  matrix: '전이행렬',
  change: '세부 변화탐지',
  classification: 'AI 신규 분류',
  trend: '장기 추세',
  validation: '제품 간 검증',
} as const;

export type SentinelResultId = keyof typeof sentinelResultTitles;

function pct(value: number | null) {
  return value == null ? '—' : value > 0 && value < 0.01 ? '<0.01%' : ha.format(value) + '%';
}

function useResult<T>(path: string) {
  const [result, setResult] = useState<{ data?: T; status?: number }>();
  useEffect(() => {
    const controller = new AbortController();
    void fetch(SENTINEL_API + path, { signal: controller.signal }).then(async response => {
      const next = response.ok ? { data: await response.json() as T } : { status: response.status };
      if (!controller.signal.aborted) setResult(next);
    }).catch(() => {
      if (!controller.signal.aborted) setResult({ status: 503 });
    });
    return () => controller.abort();
  }, [path]);
  return result;
}

function TransitionResults({ data, explorer, onShowMap, matrix }: {
  data: SentinelStats; explorer: SentinelExplorer; onShowMap: () => void; matrix: boolean;
}) {
  const [source, setSource] = useState('');
  const classes = data.annual[0]?.classes ?? [];
  const ranked = data.transition_matrix_ha.flatMap((row, i) => row.flatMap((area, j) =>
    area > 0 && i !== j && (!source || classes[i].code === Number(source))
      ? [{ from: classes[i], to: classes[j], area }]
      : [],
  )).sort((a, b) => b.area - a.area);
  function show(from: number, to: number) {
    explorer.selectTransition(from, to);
    onShowMap();
  }
  if (matrix) return <>
    <div className="mw-table-scroll" tabIndex={0}><table className="mw-table mw-sentinel-matrix" aria-label="공통 유효 픽셀 전이행렬">
      <thead><tr><th scope="col">시작 → 종료</th>{classes.map(item => <th scope="col" key={item.code}>{item.name}</th>)}</tr></thead>
      <tbody>{data.transition_matrix_ha.map((row, i) => <tr key={classes[i].code}>
        <th scope="row">{classes[i].name}</th>
        {row.map((area, j) => <td key={classes[j].code} className={i === j ? 'stable' : undefined}>
          {area > 0 && i !== j && explorer.canChange
            ? <button type="button" aria-label={classes[i].name + ' → ' + classes[j].name + ' ' + ha.format(area) + 'ha'}
                onClick={() => show(classes[i].code, classes[j].code)}>{ha.format(area)}</button>
            : ha.format(area)}
        </td>)}
      </tr>)}</tbody>
    </table></div>
    <p className="mw-sentinel-result-note">행은 {data.from_year}년, 열은 {data.to_year}년이며 단위는 ha입니다. 대각선은 유지 면적입니다. 전이 면적을 누르면 지도에서 해당 변화를 확인할 수 있습니다.</p>
  </>;
  return <>
    <div className="mw-sentinel-filters">
      <label>출발 클래스 <select value={source} onChange={event => setSource(event.target.value)}>
        <option value="">전체 클래스</option>{classes.map(item => <option key={item.code} value={item.code}>{item.name}</option>)}
      </select></label>
      {explorer.transition && <button type="button" onClick={() => explorer.clearTransition()}>전이 필터 해제</button>}
    </div>
    <div className="mw-table-scroll mw-sentinel-ranked"><table className="mw-table" aria-label="분류 전이 순위">
      <caption>분류 전이 순위</caption>
      <thead><tr><th>시작 클래스</th><th>종료 클래스</th><th>전이 면적</th><th>전체 변화 면적 비중</th><th>지도</th></tr></thead>
      <tbody>{ranked.map(row => <tr key={row.from.code + '-' + row.to.code}>
        <th>{row.from.name}</th><td>{row.to.name}</td><td>{ha.format(row.area)}ha</td>
        <td>{pct(data.changed_ha ? 100 * row.area / data.changed_ha : null)}</td>
        <td><button type="button" disabled={!explorer.canChange} aria-label={row.from.name + ' → ' + row.to.name + ' 지도에 표시'}
          onClick={() => show(row.from.code, row.to.code)}>표시</button></td>
      </tr>)}</tbody>
    </table>{!ranked.length && <p>이 조건의 클래스 전이가 없습니다.</p>}</div>
    <div className="mw-table-scroll"><table className="mw-table">
      <caption>연속 연도별 변화</caption>
      <thead><tr><th>기간</th><th>공통 유효 면적</th><th>변화 면적</th><th>변화율</th></tr></thead>
      <tbody>{data.annual_changes.map(row => <tr key={row.from_year}><th>{row.from_year}→{row.to_year}</th>
        <td>{ha.format(row.common_valid_ha)}ha</td><td>{ha.format(row.changed_ha)}ha</td><td>{pct(row.change_pct)}</td></tr>)}</tbody>
    </table></div>
  </>;
}

type Trend = {
  source_url: string; sha256: string; acquired_on: string; years: number[];
  classes: { code: number; name: string; color: string; areas_ha: number[] }[];
};

function LongTermTrend() {
  const trend = useResult<Trend>('/historical-trend');
  const [code, setCode] = useState(24);
  const series = trend?.data;
  if (!series) return <p role="status">{trend ? '장기 통계를 읽을 수 없습니다.' : '장기 통계 조회 중'}</p>;
  const selected = series.classes.find(item => item.code === code) ?? series.classes[0];
  const max = Math.max(...selected.areas_ha, 1);
  const x = (i: number) => 12 + 336 * i / (series.years.length - 1);
  const y = (area: number) => 92 - 78 * area / max;
  return <>
    <p><b>MapBiomas Indonesia Collection 4.1 · 반텐주 · 1990–2024년</b></p>
    <p>MapBiomas 발행 경계와 분류체계를 사용합니다. 지도에서 사각형 AOI를 지정해도 이 화면은 발행된 주 통계를 표시합니다.</p>
    <div className="mw-sentinel-filters">
      <label>장기 추세 클래스 <select value={selected.code} onChange={event => setCode(Number(event.target.value))}>
        {series.classes.map(item => <option key={item.code} value={item.code}>{item.name}</option>)}
      </select></label>
      <span>{series.years[0]}년 {ha.format(selected.areas_ha[0])}ha → {series.years.at(-1)}년 {ha.format(selected.areas_ha.at(-1)!)}ha</span>
    </div>
    <figure className="mw-sentinel-trend">
      <figcaption>{selected.name} · 면적(ha) · 상단 {ha.format(max)}ha</figcaption>
      <svg viewBox="0 0 360 114" role="img" aria-label={selected.name + ' 1990년부터 2024년까지 연간 면적'}>
        <path d="M12,13 V92 H348" fill="none" stroke="#9bb0c5" strokeWidth="0.7"/>
        <polyline fill="none" stroke={selected.color} strokeWidth="1.7"
          points={selected.areas_ha.map((area, i) => x(i) + ',' + y(area)).join(' ')}/>
        {[1990, 2000, 2010, 2020, 2024].map(year => <text key={year} x={x(series.years.indexOf(year))}
          y="105" textAnchor={year === 1990 ? 'start' : year === 2024 ? 'end' : 'middle'} fontSize="7" fill="#38536e">{year}</text>)}
      </svg>
    </figure>
    <details><summary>35개 연도 면적표</summary><div className="mw-table-scroll mw-sentinel-ranked"><table className="mw-table">
      <thead><tr><th>연도</th><th>{selected.name} 면적</th></tr></thead>
      <tbody>{series.years.map((year, i) => <tr key={year}><th>{year}</th><td>{ha.format(selected.areas_ha[i])}ha</td></tr>)}</tbody>
    </table></div></details>
    <p><a href={series.source_url} target="_blank" rel="noreferrer">공식 통계 원본</a> · {series.acquired_on} 취득 ·{' '}
      <a href={SENTINEL_API + '/historical-trend?download=1'}>시계열·원본 SHA-256 다운로드</a></p>
  </>;
}

type SupportEntry = { year: number; optical_scene_receipts: number; joint_support_pct: number;
  areas_ha: { boundary: number; clear_optical: number; clear_and_esri_thematic: number } };
type Agreement = { year: number; compared_ha: number; excluded_by_crosswalk_ha: number;
  overall_map_agreement_pct: number; worldcover_source: string;
  classes: { name: string; esri_code: number; worldcover_codes: number[] }[]; matrix_ha: number[][] };
type ProductSupport = { reports: Record<string, { annual: SupportEntry[] }>; thematic_agreement: Agreement | null };

function ProductValidation() {
  const result = useResult<ProductSupport>('/product-support');
  if (!result?.data) return <p role="status">{result ? '제품 비교 자료 조회 실패' : '제품 비교 자료 조회 중'}</p>;
  const releases = Object.entries(result.data.reports);
  const agreement = result.data.thematic_agreement;
  return <>
    {agreement ? <>
      <p><b>{agreement.year}년 Esri v003 ↔ ESA WorldCover v200 · 반텐 전체 · 10m</b></p>
      <p>지도 일치도 <strong>{pct(agreement.overall_map_agreement_pct)}</strong> · 비교 면적 {ha.format(agreement.compared_ha)}ha
        {' · '}분류 대응표 제외 {ha.format(agreement.excluded_by_crosswalk_ha)}ha · 독립 정확도 미측정</p>
      <details><summary>제품 간 클래스 일치·불일치 행렬</summary>
        <div className="mw-table-scroll"><table className="mw-table mw-sentinel-matrix" aria-label="Esri 행 / WorldCover 열 · 면적(ha)">
          <caption>Esri 행 / WorldCover 열 · 면적(ha)</caption>
          <thead><tr><th scope="col">Esri → WorldCover</th>{agreement.classes.map(item =>
            <th scope="col" key={item.esri_code}>{item.name}</th>)}</tr></thead>
          <tbody>{agreement.matrix_ha.map((row, i) => <tr key={agreement.classes[i].esri_code}>
            <th scope="row">{agreement.classes[i].name}</th>
            {row.map((area, j) => <td key={agreement.classes[j].esri_code}
              className={i === j ? 'stable' : undefined}>{ha.format(area)}</td>)}
          </tr>)}</tbody>
        </table></div>
        <p>6개 대분류로 맞춰 비교했습니다. 습지·맹그로브·눈 또는 얼음·이끼 및 지의류는 비교 범위에서 제외됩니다.</p>
        <a href={agreement.worldcover_source} target="_blank" rel="noreferrer">ESA WorldCover 2021 v200 원본 출처</a>
      </details>
    </> : <p>동년 토지피복 제품 간 지도 일치도 자료 대기</p>}
    <p><b>동년 광학 관측과 Esri 참조 지원 범위 · 반텐 전체 · 30m 정합 격자</b></p>
    <p>맑은 관측과 Esri 유효 픽셀의 겹침 비율은 반텐 경계의 면적을 기준으로 계산합니다.</p>
    {!releases.length && <p role="status">등록된 광학 관측 지원 범위 자료가 없습니다.</p>}
    <div className="mw-table-scroll"><table className="mw-table">
      <thead><tr><th>센서</th><th>연도</th><th>장면</th><th>맑은 관측</th><th>Esri 유효 클래스와 겹침</th><th>주 면적 비율</th></tr></thead>
      <tbody>{releases.flatMap(([sensor, report]) => report.annual.map(row => <tr key={sensor + row.year}>
        <th>{sensor === 'sentinel-2' ? 'Sentinel-2' : 'Landsat'}</th><td>{row.year}</td><td>{row.optical_scene_receipts}</td>
        <td>{ha.format(row.areas_ha.clear_optical)}ha</td><td>{ha.format(row.areas_ha.clear_and_esri_thematic)}ha</td>
        <td>{pct(row.joint_support_pct)}</td>
      </tr>))}</tbody>
    </table></div>
    <p><a href={SENTINEL_API + '/product-support'}>센서별 QA·출처 기록</a></p>
  </>;
}

function AiClassification() {
  return <>
    <LclucModelComparison sensor="sentinel-2"/>
    <p>반텐 연차 작업의 동년 학습 라벨·승인·후보 분류·독립 검증 상태입니다. 등록된 실제 분류와 신뢰도 GeoTIFF는 처리 증거에서 조회할 수 있습니다.</p>
    <div className="mw-table-scroll"><table className="mw-table">
      <thead><tr><th>연차 작업</th><th>분류 상태·산출물</th><th>검증 지표</th></tr></thead>
      <tbody><LclucAnnualIntake region="banten" realOnly/></tbody>
    </table></div>
  </>;
}

export function SentinelResult({ result, explorer, start, end, colors, onShowMap }: {
  result: SentinelResultId; explorer: SentinelExplorer; start: number; end: number;
  colors: Record<number, string>; onShowMap: () => void;
}) {
  if (result === 'classification') return <AiClassification/>;
  if (result === 'trend') return <LongTermTrend/>;
  if (result === 'validation') return <ProductValidation/>;

  const data = explorer.stats?.data;
  const error = explorer.stats?.error;
  if (!data) return <p className="mw-sentinel-result-note" role="status">
    {error === 'AOI_OUTSIDE_BANTEN' ? 'AOI가 반텐 경계와 겹치지 않습니다.'
      : error === 'AOI_CONTAINS_NO_10M_PIXELS' ? 'AOI에 포함되는 10m 픽셀이 없습니다.'
        : error ? 'AOI 통계를 조회할 수 없습니다.' : 'AOI 통계 조회 중'}
  </p>;
  if (result !== 'area') return <TransitionResults key={start + '-' + end} data={data} explorer={explorer}
    onShowMap={onShowMap} matrix={result === 'matrix'}/>;

  const a = data.annual.find(row => row.year === start);
  const b = data.annual.find(row => row.year === end);
  if (!a || !b) return <p className="mw-sentinel-result-note" role="status">선택 연도의 면적 통계가 없습니다.</p>;
  return <>
    <div className="mw-table-scroll"><table className="mw-table" aria-label="클래스별 유효 면적 및 비율">
      <thead><tr><th scope="col">클래스</th><th scope="col">{start} 면적</th><th scope="col">{start} 비율</th><th scope="col">{end} 면적</th><th scope="col">{end} 비율</th></tr></thead>
      <tbody>{a.classes.map((row, index) => <tr key={row.code}>
        <th scope="row"><i className="mw-sentinel-swatch" style={{ backgroundColor: colors[row.code] }}/>{row.name}</th>
        <td>{ha.format(row.area_ha)}ha</td><td>{pct(row.share_pct)}</td>
        <td>{ha.format(b.classes[index].area_ha)}ha</td><td>{pct(b.classes[index].share_pct)}</td>
      </tr>)}</tbody>
      <tfoot><tr><th>유효 면적</th><td colSpan={2}>{ha.format(a.valid_ha)}ha</td><td colSpan={2}>{ha.format(b.valid_ha)}ha</td></tr></tfoot>
    </table></div>
    <p className="mw-sentinel-result-note">비율은 각 연도의 유효 분류 면적을 기준으로 계산합니다.</p>
  </>;
}
