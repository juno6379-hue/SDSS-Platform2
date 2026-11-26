import { useState } from 'react';
import type { FormEvent } from 'react';

type Citation = {id: string; title: string; version: string; language: string; page: number | null;
  text_offset: number; excerpt: string; url: string; source_sha256: string};
type SearchResult = {status: string; p0_documents?: number; documents?: number; citations: Citation[]};

export default function MapbiomasKnowledge() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<SearchResult>();
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim() || busy) return;
    setBusy(true); setError(false);
    try {
      const response = await fetch('/api/rag/mapbiomas/search', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question: question.trim()})});
      if (!response.ok) throw new Error('knowledge');
      setResult(await response.json() as SearchResult);
    } catch { setError(true); }
    finally { setBusy(false); }
  }

  return <section className="panel" aria-label="MapBiomas Indonesia 지식 검색">
    <h2>MapBiomas Indonesia 지식 검색</h2>
    <p>ATBD · 범례·용어 · 기관별 참조 지도 <a href="/api/rag/mapbiomas/catalog" target="_blank" rel="noreferrer">문서 목록과 출처</a></p>
    <form onSubmit={search}><label>문서 검색어<input value={question} onChange={event => setQuestion(event.target.value)}
      placeholder="예: 맹그로브 범례, Gap Fill, 참조 지도" maxLength={400} required/></label>
      <button type="submit" disabled={busy || !question.trim()}>{busy ? '검색 중…' : '문서 근거 검색'}</button>
    </form>
    {error && <p role="alert">문서 검색 API에 연결하지 못했습니다.</p>}
    {result?.status === 'KNOWLEDGE_CORPUS_PENDING' && <p role="status">문서 색인 구축 중입니다.</p>}
    {result?.status === 'NO_MATCH' && <p role="status">관련 문서 근거를 찾지 못했습니다.</p>}
    {result?.status === 'FOUND' && <div aria-label="MapBiomas 출처 결과">
      <p>원문 근거 검색 · P0 {result.p0_documents}건 · 전체 {result.documents}건</p>
      {result.citations.map(item => <article key={item.id + ':' + item.page + ':' + item.text_offset}>
        <h3>{item.title}</h3><p>{item.version} · {item.language}{item.page ? ` · p. ${item.page}` : ''}</p>
        <p>{item.excerpt}</p>
        <a href={item.url} target="_blank" rel="noreferrer">MapBiomas 원문</a>
      </article>)}
    </div>}
  </section>;
}
