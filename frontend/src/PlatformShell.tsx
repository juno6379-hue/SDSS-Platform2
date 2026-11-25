import { SDSSIcon } from './SDSSChrome';
import { COMMON_RESULT_STEP } from './catalogNavigation';
export { default as ModelWorkspace } from './ModelAnalysisWorkspace';
export { default as ToolboxHub } from './GeoAIToolbox';
export { default as ModelMlopsWorkspace } from './ModelMlopsWorkspace';

const menus = [ ['Dashboard','대시보드','▦'], ['Data Catalog','데이터 카탈로그','▤'], ['GeoAI Toolbox','분석 도구','◈'], ['WebGIS Analysis','공간 분석','◫'], ['GeoLLM Assistant','자연어 공간질의','☷'], ['Model & MLOps','모델 운영','⚙'], ['Reports & RDTR','보고서·공간계획','▣'] ];
export const menuSections: [number,string][][] = [ [[0,'전체 현황'],[22,'작업·알림'],[23,'Agent 현황']], [[1,'데이터 검색'],[26,'모델 입력자료'],[27,'다운로드 이용조건'],[28,'메타데이터·품질'],[29,'Toolbox 전환'],[30,'WebGIS 공간연계'],[10,'품질·정합 감사'],[11,'메타데이터·출처'],[2,'데이터 등록']], [[12,'6개 모델 허브'],[9,'다중 Agent 워크플로'],[13,'모델 선택 목록']], [[14,'레이어·지도'],[8,'시계열·지도 비교'],[5,'공간통계·중첩']], [[7,'자연어 질의'],[15,'실행계획 검토'],[16,'근거·출처 확인']], [[6,'Model Registry'],[3,'재학습·재보정'],[17,'승인·배포'],[18,'운영 모니터링']], [[19,'보고서 작성'],[20,'RDTR 공간계획'],[21,'검토·승인 이력'],[COMMON_RESULT_STEP,'공통 결과 검토']] ];
export function navigationForStep(step:number) { if(step===24||step===4)return 2; return Math.max(0,menuSections.findIndex(rows=>rows.some(([id])=>id===step))); }
export function titleForStep(step:number) { return menuSections.flat().find(([id])=>id===step)?.[1] || '공간 추론'; }
export const agents = [
 {id:'lcluc', title:'LCLUC', ko:'토지피복·토지이용 변화',icon:'◒',desc:'다중분광 영상 분류, 토지피복 변화와 전이행렬',fields:['관심영역 / AOI','기준 연도 T1','비교 연도 T2','토지피복 클래스','밴드·라벨 품질 기준']},
 {id:'climate',title:'Climate Downscaling',ko:'기후 다운스케일링',icon:'☀',desc:'기온·강수 상세화, 기후 시나리오와 불확실성',fields:['관심영역 / AOI','SSP 시나리오','기후 변수 / 단위','목표 기간','목표 격자 해상도']},
 {id:'carbon',title:'Net Carbon Footprint',ko:'탄소 배출·흡수',icon:'♧',desc:'지역·부문별 배출원, 흡수원과 공간 탄소 수지',fields:['관심영역 / AOI','배출·흡수 범주','산정 방법','산정 기간','산출 단위']},
 {id:'biodiversity',title:'Biodiversity Mapping',ko:'생물다양성·서식지',icon:'❋',desc:'종 분포, 서식지 적합도와 보호지역 중첩',fields:['관심영역 / AOI','대상 종 / 서식지','환경 요인','보호구역 참조','독립 현장 참조']},
 {id:'coastal',title:'Sea Level & Subsidence',ko:'해수면 상승·지반침하',icon:'≈',desc:'조위·변위 추세, 수직기준면과 연안 노출도',fields:['연안 관심영역 / AOI','해수면·침하 지표','관측·시나리오 기간','수직 기준면','독립 관측 참조']},
 {id:'flood',title:'Flood & Drought',ko:'홍수·가뭄 위험',icon:'◇',desc:'유역별 강우·수문 시나리오, 노출·취약성',fields:['관심 유역 / AOI','홍수·가뭄 유형','강우·수문 시나리오','DEM 참조','보정·평가 지표']},
];
export function PlatformSidebar({step,connected,onNavigate}:{step:number;connected:boolean;onNavigate:(step:number)=>void}) {
  const current=navigationForStep(step);
  const icons=['home','data','ai','map','chat','cube','report'];
  return <aside className="sidebar"><nav aria-label="전체 플랫폼 메뉴">{menus.map(([name,ko],i)=><button key={name} className={current===i?'nav active':'nav'} aria-current={current===i?'page':undefined} onClick={()=>onNavigate(menuSections[i][0][0])}><span><SDSSIcon name={icons[i]}/></span><div>{['대시보드','데이터 카탈로그','GeoAI 툴박스','WebGIS 분석','GeoLLM Assistant','모델 & MLOps','리포트 & RDTR'][i]}<small>{name} · {ko}</small></div></button>)}</nav><p className="sdss-sidebar-copy">AI와 공간데이터로<br/>인도네시아의<br/>기후행동을 지원합니다.</p><div className="sdss-sidebar-scenery" aria-hidden="true"/><div className="sidebar-bottom">{connected?'분석 서버 연결됨':'서버 연결 확인 필요'}</div></aside>;
}
export function PlatformContext({step,agent,tab}:{step:number;agent:string;tab:string}) { const current=navigationForStep(step);return <><div className="breadcrumb" aria-label="현재 위치">⌂ <span>›</span>{menus[current][0]}<span>›</span>{step===24?`${agents.find(a=>a.id===agent)?.title} › Analysis Workspace${tab==='input'?'':` › ${{result:'결과·통계',evidence:'검증·근거',history:'실행 이력'}[tab]||''}`}`:titleForStep(step)}</div><div className="ux-guide"><div><strong>데이터로 만드는 더 안전한 오늘, 지속 가능한 내일</strong><p>Data for a Resilient Indonesia</p></div><span className="pill">실제 서버 상태와 검증 근거 기반</span></div></>; }
