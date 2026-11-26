import { useEffect, useState } from 'react';
import { ha, SENTINEL_API } from './lclucExplorerData';

type Row = {code: number; name: string; area_ha: number};
type Comparison = {year: number; common_years: number[];
  esri: {aoi_area_ha: number; thematic_area_ha: number; nodata_area_ha: number; classes: Row[]};
  mapbiomas: {published_area_ha: number; classes: Row[]}};

function AreaTable({title, rows}: {title: string; rows: Row[]}) {
  return <div className="mw-table-scroll"><table className="mw-table" aria-label={title}>
    <thead><tr><th>코드</th><th>원래 분류</th><th>면적 (ha)</th></tr></thead>
    <tbody>{rows.map(row => <tr key={row.code}><td>{row.code}</td><th scope="row">{row.name}</th>
      <td>{ha.format(row.area_ha)}</td></tr>)}</tbody>
  </table></div>;
}

export default function LclucBantenAreaComparison() {
  const [selected, select] = useState<number>();
  const [data, setData] = useState<Comparison>();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const cancel = new AbortController();
    setFailed(false);
    const path = SENTINEL_API + '/mapbiomas-area-comparison' + (selected ? '?year=' + selected : '');
    void fetch(path, {signal: cancel.signal}).then(async response => {
      if (!response.ok) throw new Error('area comparison');
      const result = await response.json() as Comparison;
      if (!cancel.signal.aborted) setData(result);
    }).catch(() => { if (!cancel.signal.aborted) setFailed(true); });
    return () => cancel.abort();
  }, [selected]);
  if (!data) return <p role="status">{failed ? '제품 원본 면적 조회 실패' : '제품 원본 면적 조회 중'}</p>;
  const pending = selected !== undefined && data.year !== selected;
  const cloud = data.esri.classes.find(row => row.code === 10)?.area_ha ?? 0;
  return <div className="mw-landsat-content">
    <label>면적 조회 연도 <select value={selected ?? data.year} onChange={event => select(Number(event.target.value))}>
      {data.common_years.map(year => <option key={year}>{year}</option>)}
    </select></label>
    <p>공통 경계·분류체계 검증 전입니다. 두 제품은 각각의 원래 분류와 집계 범위로 표시합니다.</p>
    {failed || pending ? <p role="status">{failed ? '제품 원본 면적 조회 실패' : '선택 연도 조회 중'}</p> : <>
      <h4>{data.year}년 Esri v003 · One Map 반텐 경계 재집계</h4>
      <p>경계 격자 {ha.format(data.esri.aoi_area_ha)}ha · 분류 유효 {ha.format(data.esri.thematic_area_ha)}ha · 구름 {ha.format(cloud)}ha · NoData {ha.format(data.esri.nodata_area_ha)}ha</p>
      <AreaTable title="Esri 반텐 원본 분류 면적" rows={data.esri.classes}/>
      <h4>{data.year}년 MapBiomas Collection 4.1 · 발행 주 통계</h4>
      <p>발행 면적 합계 {ha.format(data.mapbiomas.published_area_ha)}ha</p>
      <AreaTable title="MapBiomas 반텐 원본 분류 면적" rows={data.mapbiomas.classes}/>
    </>}
  </div>;
}
