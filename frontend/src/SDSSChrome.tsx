import { useState } from 'react';

import { Icon as SDSSIcon } from './Icon';
export { Icon as SDSSIcon } from './Icon';

export function SDSSHeader({onNavigate,onSearch,onRefresh,loading,connected}:{onNavigate:(step:number)=>void;onSearch:(query:string)=>void;onRefresh:()=>void;loading:boolean;connected:boolean}) {
  const [query,setQuery]=useState('');
  return <header className="sdss-global-header">
    <button className="sdss-reference-brand" aria-label="SDSS 홈" onClick={()=>onNavigate(0)}/>
    <div className="sdss-motto"><strong>데이터로 만드는 더 안전한 오늘,<br/>지속 가능한 내일</strong><small>Data for a Resilient Indonesia</small></div>
    <form className="sdss-global-search" onSubmit={e=>{e.preventDefault();onSearch(query);}}><input aria-label="플랫폼 데이터 검색" placeholder="지역, 데이터, 키워드로 검색하세요  (예: Indonesia, land cover, mangrove)" value={query} onChange={e=>setQuery(e.target.value)}/><button aria-label="데이터 카탈로그 검색"><SDSSIcon name="search" size={19}/></button></form>
    <div className="sdss-top-actions"><button aria-label="실제 작업·알림 보기" title="작업·알림" onClick={()=>onNavigate(22)}><SDSSIcon name="bell"/></button><button aria-label="서버 연결 설정" title="서버 연결 설정" onClick={()=>{const el=document.getElementById('sdss-connection-settings') as HTMLDetailsElement|null;if(el){el.open=true;el.scrollIntoView({behavior:'smooth'});}}}><SDSSIcon name="settings"/></button><button className="sdss-account" title={loading?'새로고침 중':'서버 상태 새로고침'} aria-label="서버 상태 새로고침" onClick={onRefresh} disabled={loading}><span className="sdss-avatar">●</span><span><strong>SDSS Indonesia</strong><small>{connected?'로컬 분석 서버 연결됨':'서버 연결 확인 필요'}</small></span><span>⌄</span></button></div>
    <div className="sdss-tomorrow">Sustainable Indonesia<br/><strong>for a Better Tomorrow</strong></div>
  </header>;
}
export function SDSSFooter(){return <footer className="sdss-global-footer"><strong>◉ SDSS</strong><span>Spatial Decision Support System for Climate Action & GeoAI</span><small>독립 검증·운영 승인 전 분석 결과 게시 차단</small><span className="sdss-footer-end">◎ KO　⌄　　<span>❧ Together for a Resilient Indonesia</span></span></footer>;}
