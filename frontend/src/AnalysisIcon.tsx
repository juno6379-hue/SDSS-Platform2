import type { ReactNode } from 'react';
import { IconFrame } from './Icon';

// 모든 모델에서 기능의 의미로 아이콘을 선택한다. 탭 순서가 바뀌어도 의미를 유지한다.
function iconFor(label: string): ReactNode {
  if (/내보내기/.test(label)) return <><path d="M12 3v12m-4-4 4 4 4-4"/><path d="M4 15v5h16v-5"/></>;
  if (/행렬/.test(label)) return <><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/><path d="m4.5 6 1 1 2-2m3 7 1 1 2-2m3 7 1 1 2-2"/></>;
  if (/핫스팟/.test(label)) return <><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/></>;
  if (/지역 비교/.test(label)) return <><path d="M3 20h18M5 17v-6h3v6m3 0V5h3v12m3 0V8h3v9"/><path d="m4 5 3-2 3 2"/></>;
  if (/시나리오/.test(label)) return <><path d="M4 5h4l4 7h4m-8-7 4 14h4M16 9l4 3-4 3m0 1 4 3-4 3"/><circle cx="4" cy="5" r="2"/></>;
  if (/시계열|추세/.test(label)) return <><path d="M3 3v17h18M6 14l4-5 4 3 5-7"/><circle cx="6" cy="14" r="1"/><circle cx="10" cy="9" r="1"/><circle cx="14" cy="12" r="1"/><circle cx="19" cy="5" r="1"/></>;
  if (/변화/.test(label)) return <><path d="M10 4H4v16h6m4-16h6v16h-6M12 2v20"/><path d="m6 10 2 2-2 2m12-4-2 2 2 2"/></>;
  if (/연결성/.test(label)) return <><path d="m7 6 10 3m-10 0 3 9m8-6-5 7"/><circle cx="5" cy="6" r="3"/><circle cx="19" cy="10" r="3"/><circle cx="11" cy="20" r="2"/></>;
  if (/위협|취약/.test(label)) return <><path d="m12 3 10 17H2Z"/><path d="M12 9v5m0 3v.1"/></>;
  if (/우선/.test(label)) return <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z"/><path d="m12 6 1 2 2 .5-1.5 1.5.5 2-2-1-2 1 .5-2L9 8.5l2-.5Z"/></>;
  if (/흡수/.test(label)) return <><path d="M20 3C8 2 3 7 5 14c2 6 14 5 15-11Z"/><path d="M3 21 16 8m-8 8v-5m4 1h5"/></>;
  if (/수지/.test(label)) return <><path d="M12 3v18M5 21h14M4 6h16M5 6l-3 8h6Zm14 0-3 8h6Z"/><path d="M2 14c0 3 6 3 6 0m8 0c0 3 6 3 6 0"/></>;
  if (/프로파일/.test(label)) return <><path d="M3 3v18h18M4 16l4-6 4 4 4-8 5 4"/><path d="M4 18h17" strokeDasharray="2 3"/></>;
  if (/노출/.test(label)) return <><path d="M3 21V9h7v12m2 0V3h9v18M6 12v1m0 3v1m9-10h3m-3 4h3m-3 4h3M2 21h20"/></>;
  if (/통계/.test(label)) return <><path d="M3 3v18h18M6 17v-5h3v5m3 0V6h3v11m3 0v-8h3v8"/></>;
  return <><path d="m3 5 6-2 6 3 6-3v16l-6 3-6-3-6 2Z"/><path d="M9 3v16M15 6v16"/><circle cx="15" cy="10" r="2"/></>;
}

export default function AnalysisIcon({label}:{label:string}) {
  return <IconFrame className="analysis-function-icon">{iconFor(label)}</IconFrame>;
}
