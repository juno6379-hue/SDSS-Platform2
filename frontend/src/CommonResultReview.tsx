import {resultIdFromHash} from './institutionOpsClient';
import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import ResultLayerMap from './ResultLayerMap';
import { SDSSIcon } from './SDSSChrome';
import { catalogAssetHref, readResultCatalog, listResults, listResultSources, readResult, registerResult, resultError, saveResultReview } from './commonResultClient';
import type { ResultCatalog, ResultRecord, ResultSource, ReviewDecision } from './commonResultClient';
import './common-result-review.css';

const stateLabels: Record<string, string> = {
  PENDING: '검토 대기', CHANGES_REQUESTED: '수정 요청', ACCEPTED: '검토 완료',
  VERIFIED_REAL: '실증 확인', TESTED_SYNTHETIC: '합성 시험', IMPLEMENTED_UNVERIFIED: '구현·검증 대기',
  BLOCKED: '차단', PLANNED: '계획',
};
const domains: Record<string, string> = {
  sentinel: 'Sentinel-2', onemap: 'One Map · RTRW', climate: '기후', lake: 'Data Lake',
  klhk: 'KLHK', rag: '문서 검색', mlops: '모델 & MLOps', workflow: '워크플로',
};
const formatTime = (value: string) => new Date(value).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' });

function Status({ value }: { value: string }) {
  return <span className="pill common-result-status" data-state={value} title={value}>{stateLabels[value] || value}</span>;
}

function Catalog({ result }: { result: ResultRecord }) {
  const [data, setData] = useState<ResultCatalog>();
  const [mapLayer, setMapLayer] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    setData(undefined); setError(''); setLoading(true);
    // 선택 결과·revision 변경과 unmount 뒤의 응답은 화면에 적용하지 않는다.
    readResultCatalog(result.id, controller.signal).then(value => {
      if (!controller.signal.aborted) setData(value);
    }).catch(reason => {
      if (!controller.signal.aborted) setError(resultError(reason));
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [result.id, result.revision]);
  const assetLink = (href: string, label: string) => {
    const safe = catalogAssetHref(result.id, href);
    return safe ? <a href={safe} target="_blank" rel="noopener noreferrer">{label} · 서버 파일 조회</a> : <span className="muted">{label} · 안전한 동일 결과 경로 미확인</span>;
  };
  const pkg = data?.package;
  return <section className="common-result-catalog" data-testid="common-result-catalog" aria-label="공통 결과 catalog">
    <h3>지표·레이어·보고서 패키지</h3>
    {loading && <p role="status">Catalog 조회 중…</p>}
    {error && <p className="error" role="alert">Catalog 조회 차단: {error}</p>}
    {data && <>
      <p data-testid="common-catalog-status">{data.status} · 패키지 SHA <code>{data.package_sha256 || '아직 없음'}</code></p>
      {!pkg && <p className="notice">패키지 준비 대기 · 지표·지도 레이어·보고서를 생성하거나 추정하지 않습니다.</p>}
      {pkg && <>
        <p>기관: {pkg.institution}</p>
        <p>공간: {pkg.spatial ? `${pkg.spatial.crs} · bbox ${pkg.spatial.bbox.join(', ')}` : '미기록'} / 기간: {pkg.period ? `${pkg.period.start} ~ ${pkg.period.end} · ${pkg.period.kind}` : '미기록'}</p>
        {pkg.period_reason && <p className="muted">{pkg.period_reason}</p>}
        <h4>지표</h4>{pkg.metrics.length ? <ul data-testid="common-catalog-metrics">{pkg.metrics.map(metric => <li key={metric.id}>{metric.label}: {typeof metric.value === 'string' || typeof metric.value === 'number' ? String(metric.value) : JSON.stringify(metric.value)} {metric.unit}</li>)}</ul> : <p className="muted">제공된 지표 없음</p>}
        <h4>지도 레이어</h4>
        {pkg.layers.length ? <ul data-testid="common-catalog-layers">{pkg.layers.map(layer => {
          const href = catalogAssetHref(result.id, layer.href);
          const bounds = pkg.spatial?.bbox;
          return <li key={layer.id}>{assetLink(layer.href, layer.title)}<p>{layer.format} · {layer.crs} · NoData {JSON.stringify(layer.nodata)}</p>
            {href && layer.format === 'GeoJSON' && bounds?.length === 4 && <>
              <button className="secondary" type="button" aria-expanded={mapLayer === layer.id} onClick={() => setMapLayer(mapLayer === layer.id ? '' : layer.id)}>{mapLayer === layer.id ? '지도 닫기' : '지도에서 보기'}</button>
              {mapLayer === layer.id && <ResultLayerMap href={href} bounds={bounds as [number, number, number, number]} title={layer.title}/>}
            </>}
          </li>;
        })}</ul> : <p className="muted">제공된 레이어 없음</p>}
        <h4>출처</h4>{pkg.sources.length ? <ul className="common-result-break" data-testid="common-catalog-sources">{pkg.sources.map(item => <li key={item.id}><strong>{item.title}</strong><p>{item.uri}</p><p>버전 {item.version} · 라이선스 {item.license} · SHA <code>{item.sha256}</code></p></li>)}</ul> : <p className="muted">제공된 출처 없음</p>}
        <h4>보고서</h4>{pkg.reports.length ? <ul data-testid="common-catalog-reports">{pkg.reports.map(report => <li key={report.id}>{assetLink(report.href, report.title)} · {report.format}</li>)}</ul> : <p className="muted">제공된 보고서 없음</p>}
        <h4>불확실성</h4><p data-testid="common-catalog-uncertainty">{pkg.uncertainty.status} · {pkg.uncertainty.reason}</p>
        {pkg.uncertainty.status === 'QUANTIFIED' && <p>방법 {pkg.uncertainty.method || '미기록'} · 하한 {pkg.uncertainty.lower ?? '미기록'} / 상한 {pkg.uncertainty.upper ?? '미기록'} {pkg.uncertainty.unit || ''}</p>}
        <details><summary>품질 검사</summary><pre>{JSON.stringify(pkg.quality.checks, null, 2)}</pre></details>
      </>}
      <h4>과학검증 · 기관공개승인</h4>
      <p className="notice">사람의 검토 완료는 과학검증 또는 기관공개승인이 아닙니다. 이 화면은 승인 상태를 조회하며 승인 작업을 실행하지 않습니다.</p>
      <div data-testid="common-catalog-governance"><p>과학검증: {data.governance.scientific.status}</p><p>기관공개승인: {data.governance.publication.status}</p><p>서버 공개 적격 판정: {data.governance.release_eligible ? '적격' : '미충족'}</p>
        <details><summary>검증·공개승인 이력</summary><pre>{JSON.stringify({ scientific: data.governance.scientific.history, publication: data.governance.publication.history }, null, 2)}</pre></details>
      </div>
    </>}
  </section>;
}

export default function CommonResultReview() {
  const [rows, setRows] = useState<ResultRecord[]>([]);
  const [sources, setSources] = useState<ResultSource[]>([]);
  const [domain, setDomain] = useState('');
  const [status, setStatus] = useState('');
  const [source, setSource] = useState('');
  const [selected, setSelected] = useState<ResultRecord>();
  const [reviewer, setReviewer] = useState('');
  const [note, setNote] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [listError, setListError] = useState('');
  const [sourceError, setSourceError] = useState('');
  const [actionError, setActionError] = useState('');
  const [feedback, setFeedback] = useState('');
  const inFlight = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    let generation = 0;
    // 동일 결과 ID만 조회하고 늦게 도착한 다른 링크의 응답은 버린다.
    function openLinkedResult() {
      const current = ++generation;
      const id = resultIdFromHash(window.location.hash);
      if (!id) return;
      setSelected(undefined); setActionError('');
      readResult(id, controller.signal).then(value => {
        if (!controller.signal.aborted && current === generation && resultIdFromHash(window.location.hash) === id) {
          if (value.id !== id) throw Error('RESULT_ID_MISMATCH');
          setSelected(value);
        }
      }).catch(error => { if (!controller.signal.aborted && current === generation) setActionError(resultError(error)); });
    }
    openLinkedResult(); window.addEventListener('hashchange', openLinkedResult);
    return () => { controller.abort(); window.removeEventListener('hashchange', openLinkedResult); };
  }, []);


  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setListError('');
    listResults(domain, status, controller.signal).then(data => {
      if (!controller.signal.aborted) setRows(data);
    }).catch(error => {
      if (!controller.signal.aborted) { setRows([]); setListError(resultError(error)); }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [domain, status, refresh]);

  useEffect(() => {
    const controller = new AbortController();
    listResultSources(controller.signal).then(data => {
      if (!controller.signal.aborted) { setSources(data); setSourceError(''); }
    }).catch(error => {
      if (!controller.signal.aborted) { setSources([]); setSourceError(resultError(error)); }
    });
    return () => controller.abort();
  }, [refresh]);

  async function operate(action: () => Promise<void>) {
    if (inFlight.current) return;
    inFlight.current = true;
    setWorking(true); setActionError(''); setFeedback('');
    try { await action(); }
    catch (error) { setActionError(resultError(error)); }
    finally { inFlight.current = false; setWorking(false); }
  }

  function register() {
    void operate(async () => {
      const result = await registerResult(source);
      setDomain(''); setStatus(''); setSelected(result); setNote(''); setRefresh(value => value + 1);
      setFeedback('공통 결과 원장에서 등록을 확인했습니다.');
    });
  }

  function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const button = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const decision = button?.value as ReviewDecision | undefined;
    if (!selected || (decision !== 'CHANGES_REQUESTED' && decision !== 'ACCEPTED') || !reviewer.trim() || !note.trim()) return;
    void operate(async () => {
      try {
        const updated = await saveResultReview(selected, decision, reviewer.trim(), note.trim());
        setSelected(updated); setNote(''); setRefresh(value => value + 1);
        setFeedback(`${stateLabels[decision]} 이력을 저장했습니다.`);
      } catch (error) {
        if (resultError(error) === 'REVIEW_CONFLICT') {
          setSelected(await readResult(selected.id));
          setRefresh(value => value + 1);
          setActionError('다른 검토가 먼저 저장됐습니다. 불러온 최신 이력을 확인한 뒤 다시 제출하세요.');
          return;
        }
        throw error;
      }
    });
  }

  const availableDomains = [...new Set([...sources.map(item => item.domain), ...rows.map(item => item.domain)])];
  return <div className="common-result-layout">
    <section className="panel" aria-labelledby="common-result-list-title">
      <div className="section-title"><h2 id="common-result-list-title"><SDSSIcon name="report" size={19}/> 등록된 공통 결과</h2><button type="button" className="secondary" disabled={working || loading} onClick={() => { setSelected(undefined); setRefresh(value => value + 1); }}>목록 새로고침</button></div>
      <div className="common-result-filters">
        <div><label htmlFor="common-result-domain">분야</label><select id="common-result-domain" value={domain} disabled={working} onChange={e => { setDomain(e.target.value); setSelected(undefined); }}><option value="">전체 분야</option>{availableDomains.map(item => <option key={item} value={item}>{domains[item] || item}</option>)}</select></div>
        <div><label htmlFor="common-result-filter-status">검토 상태</label><select id="common-result-filter-status" value={status} disabled={working} onChange={e => { setStatus(e.target.value); setSelected(undefined); }}><option value="">전체 상태</option>{['PENDING', 'CHANGES_REQUESTED', 'ACCEPTED'].map(item => <option key={item} value={item}>{stateLabels[item]}</option>)}</select></div>
      </div>
      {listError && <p className="error" role="alert">{listError}</p>}
      <p className="muted" role="status">{loading ? '결과 조회 중…' : listError ? '결과 조회 실패' : `${rows.length}건`}</p>
      <div className="common-result-list" aria-label="등록된 공통 결과 목록">
        {rows.map(row => <button type="button" className="secondary" key={row.id} aria-pressed={selected?.id === row.id} disabled={working} onClick={() => void operate(async () => { setSelected(undefined); setNote(''); setSelected(await readResult(row.id)); })}>
          <strong>{row.title}</strong><span><Status value={row.evidence_status}/> <Status value={row.review_status}/></span>
        </button>)}
      </div>
      <details className="common-result-register">
        <summary>고정 증거 등록</summary>
        {sourceError && <p className="error" role="alert">{sourceError}</p>}
        <label htmlFor="common-result-source">등록할 증거</label><select id="common-result-source" value={source} disabled={working} onChange={e => setSource(e.target.value)}><option value="">증거 선택</option>{sources.map(item => <option key={item.source} value={item.source}>{item.title}</option>)}</select>
        <button type="button" disabled={!source || working || !!sourceError} onClick={register}>선택한 증거 등록</button>
      </details>
    </section>
    <section className="panel" aria-labelledby="common-result-detail-title">
      <h2 id="common-result-detail-title"><SDSSIcon name="clipboard" size={19}/> 결과 상세</h2>
      {actionError && <p className="error" role="alert">{actionError}</p>}
      {feedback && <p className="notice" role="status">{feedback}</p>}
      {!selected && <p className="empty">{working ? '결과를 불러오는 중입니다.' : '목록에서 검토할 결과를 선택하세요.'}</p>}
      {selected && <>
        <h3>{selected.title}</h3>
        <p className="common-result-state"><span>증거 <Status value={selected.evidence_status}/></span><span>사람 검토 <Status value={selected.review_status}/></span><span className="muted">검토 버전 {selected.revision}</span></p>
        <p className="common-result-summary">{typeof selected.summary === 'string' ? selected.summary : JSON.stringify(selected.summary, null, 2)}</p>
        <details><summary>등록 정보</summary><p className="muted common-result-break">{selected.source_key} · {formatTime(selected.created_at)} KST · {selected.id}</p></details>
        <Catalog key={`${selected.id}:${selected.revision}`} result={selected}/><h3>증거 파일</h3>
        <div className="table-scroll common-result-evidence" tabIndex={0} aria-label="증거 파일과 SHA-256"><table><thead><tr><th scope="col">경로</th><th scope="col">SHA-256</th><th scope="col">바이트</th></tr></thead><tbody>
          {selected.evidence.map(pin => <tr key={pin.path}><td>{pin.path}</td><td><code>{pin.sha256}</code></td><td>{pin.bytes.toLocaleString('ko-KR')}</td></tr>)}
        </tbody></table></div>
        <h3>차단 사유</h3>{selected.blockers.length ? <ul className="common-result-break">{selected.blockers.map(blocker => <li key={blocker}>{blocker}</li>)}</ul> : <p className="muted">기록된 차단 사유 없음</p>}
        <h3>검토 이력</h3>
        {selected.reviews.length ? <ol className="common-result-history">{selected.reviews.map(event => <li key={event.revision}><Status value={event.decision}/> {event.reviewer} · {formatTime(event.created_at)} KST<p>{event.note}</p></li>)}</ol> : <p className="muted">검토 이력 없음</p>}
        <form onSubmit={submitReview}>
          <fieldset disabled={working}>
            <legend>검토 기록</legend>
            <p className="muted">이름은 로컬 검토 이력에 저장됩니다. 증거 상태와 기관 승인은 별도로 관리합니다.</p>
            <label>검토자 이름<input value={reviewer} onChange={e => setReviewer(e.target.value)} required maxLength={80} autoComplete="off"/></label>
            <label>검토 내용<textarea value={note} onChange={e => setNote(e.target.value)} required maxLength={2000} rows={3}/></label>
            <div className="button-row"><button type="submit" value="CHANGES_REQUESTED" className="secondary">수정 요청</button><button type="submit" value="ACCEPTED">검토 완료</button></div>
          </fieldset>
        </form>
      </>}
    </section>
  </div>;
}
