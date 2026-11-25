import type { ReactNode } from 'react';

// 공통 24px 격자·선 굵기·둥근 끝을 메뉴, 분석 기능, 지표, 액션에 적용한다.
export function IconFrame({children,size=24,className=''}:{children:ReactNode;size?:number;className?:string}) {
  return <svg className={`sdss-icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" focusable="false" aria-hidden="true">{children}</svg>;
}

const paths:Record<string,string[]>={
  home:['m3 10 9-7 9 7','M5 9v12h5v-7h4v7h5V9'],
  data:['M20 5c0 4-16 4-16 0s16-4 16 0Z','M4 5v14c0 4 16 4 16 0V5','M4 12c0 4 16 4 16 0'],
  ai:['M7 7h10v10H7Z','M4 4h16v16H4Z','M9 1v3m6-3v3M9 20v3m6-3v3M1 9h3m-3 6h3m16-6h3m-3 6h3'],
  map:['m3 5 6-2 6 3 6-3v16l-6 3-6-3-6 2Z','M9 3v16M15 6v16'],
  chat:['M4 3h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-9l-6 4v-4H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z','M7 10h.01M12 10h.01M17 10h.01'],
  cube:['m12 2 9 5v10l-9 5-9-5V7Z','m3 7 9 5 9-5M12 12v10m-5-17 10 5'],
  report:['M5 2h9l5 5v15H5Z','M14 2v6h5M8 12h3m-3 4h8m-8 3h8'],
  bell:['M6 9a6 6 0 0 1 12 0v6l2 3H4l2-3Z','M10 21h4'],
  settings:['m9 2-1 3-3 1-2 3 2 3-2 3 2 3 3 1 1 3h6l1-3 3-1 2-3-2-3 2-3-2-3-3-1-1-3Z','M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0'],
  search:['M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z','m15 15 6 6'],
  play:['m8 4 12 8-12 8Z'],
  plus:['M12 5v14M5 12h14'],
  minus:['M5 12h14'],
  layers:['m12 3 10 5-10 5L2 8Z','m2 12 10 5 10-5M2 16l10 5 10-5'],
  focus:['M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5','M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z','M12 10v4m-2-2h4'],
  expand:['M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5','M4 20l6-6m4-4 6-6M4 4l6 6m4 4 6 6'],
  bulb:['M8 16c0-3-3-4-3-8a7 7 0 0 1 14 0c0 4-3 5-3 8Z','M9 19h6m-5 3h4M10 8l2 3 2-3m-2 3v5'],
  help:['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z','M9 9a3 3 0 1 1 4 3c-1 0-1 1-1 2m0 3v.01'],
  close:['m6 6 12 12M6 18 18 6'],
  chart:['M3 3v18h18M6 15l4-5 4 3 6-8'],
  bars:['M3 3v18h18M6 17V9h3v8m3 0V5h3v12m3 0v-5h3v5'],
  donut:['M12 3a9 9 0 1 0 9 9h-9Z','M15 2v7h7a9 9 0 0 0-7-7Z'],
  matrix:['M3 3h18v18H3Z','M9 3v18M15 3v18M3 9h18M3 15h18'],
  clipboard:['M8 5H5v17h14V5h-3','M9 2h6v5H9Z','m8 14 2 2 5-5'],
  compare:['M3 3h7v18H3Zm11 0h7v18h-7Z','M6 8h1m-1 4h1m10-4h1m-1 4h1'],
  forest:['m12 2 5 6h-3l5 6h-4l5 5H4l5-5H5l5-6H7Z','M12 19v3'],
  mangrove:['M12 14V8m0 3L8 8m4 2 4-3','M7 12a4 4 0 0 1-2-7 4 4 0 0 1 7-2 4 4 0 0 1 7 3 4 4 0 0 1-2 7H7Z','M12 14 8 21m4-7 4 7m-4-7v8'],
  buildings:['M3 21V9h7v12m2 0V3h9v18M2 21h20','M6 12v1m0 3v1m9-10h3m-3 4h3m-3 4h3m-3 4h3'],
  area:['M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5','M7 7h10v10H7Z'],
  temperature:['M14 14.5V5a3 3 0 0 0-6 0v9.5a5 5 0 1 0 6 0Z','M11 8v9m7-11h3m-3 4h2'],
  rain:['M6 14a4 4 0 0 1-1-8 5 5 0 0 1 9-2 4 4 0 1 1 3 10','M7 17l-1 3m6-3-1 3m6-3-1 3'],
  sun:['M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z','M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1'],
  people:['M10 6a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z','M1 21v-3a6 6 0 0 1 12 0v3M17 3a3 3 0 0 1 0 6m-1 5a6 6 0 0 1 7 6v1'],
  emissions:['M3 21V11l6-3v5l6-3v4h6v7Z','M17 14V5h3v9M6 17h1m4 0h1m4 0h1'],
  leaf:['M20 3C9 1 3 7 5 14c3 7 15 5 15-11Z','M3 21 16 8m-8 8v-5m4 1h5'],
  carbon:['M7 4a9 9 0 0 1 14 6m0-5v5h-5M17 20A9 9 0 0 1 3 14m0 5v-5h5','M15 9a4 4 0 1 0 0 6'],
  target:['M21 12a9 9 0 1 1-9-9','M17 12a5 5 0 1 1-5-5','M12 12l9-9m-4 0h4v4'],
  habitat:['M4 20V9l8-6 8 6v11H4Z','M8 17c0-5 3-7 8-7 0 5-3 7-8 7Zm0 0 5-4'],
  network:['m6 6 12 3m-12 0 4 9m8-6-5 6','M8 6a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm14 4a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm-8 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
  location:['M19 9c0 5-7 12-7 12S5 14 5 9a7 7 0 0 1 14 0Z','M15 9a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
  water:['M2 14c3-4 5 4 8 0s5 4 8 0 4 0 4 0M2 20c3-4 5 4 8 0s5 4 8 0 4 0 4 0','M15 7a3 3 0 0 1-6 0c0-2 3-5 3-5s3 3 3 5Z'],
  subsidence:['M12 2v12m-4-4 4 4 4-4','M3 18h6l3 3 3-3h6'],
  warning:['m12 3 10 18H2Z','M12 9v5m0 3v.01'],
  risk:['M3 18a9 9 0 1 1 18 0M12 15l5-6','M12 15a2 2 0 1 1 0 4 2 2 0 0 1 0-4ZM5 15h1m0-6 1 1m5-5v1m6 3-1 1m2 5h-1'],
};

export function Icon({name,size=24,className=''}:{name:string;size?:number;className?:string}) {
  return <IconFrame size={size} className={className}>{(paths[name]||paths.map).map((d,i)=><path key={i} d={d}/>)}</IconFrame>;
}
