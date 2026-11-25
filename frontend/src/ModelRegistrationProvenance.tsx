import {useEffect,useRef,useState} from 'react';
import {api} from './api';
import {Icon} from './Icon';
import {ModelProvenanceFlight,provenanceStatusLabels,provenanceBindingLabels} from './modelRegistrationProvenanceAdapter';
import type {ProvenanceResult} from './modelRegistrationProvenanceAdapter';
import './model-registration-provenance.css';

export default function ModelRegistrationProvenance({modelId}:{modelId:string}) {
  const [view,setView]=useState<{modelId:string;route:string;result:ProvenanceResult}>();
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const flight=useRef(new ModelProvenanceFlight());
  const selectedId=useRef(modelId); selectedId.current=modelId;
  useEffect(()=>{
    const clear=()=>{flight.current.invalidate();setView(undefined);setError('');setBusy(false);};
    clear();window.addEventListener('popstate',clear);window.addEventListener('hashchange',clear);
    return()=>{flight.current.invalidate();window.removeEventListener('popstate',clear);window.removeEventListener('hashchange',clear);};
  },[modelId]);
  async function inspect(){
    if(busy||!modelId)return;
    const route=window.location.hash;
    setView(undefined);setError('');setBusy(true);
    await flight.current.inspect(modelId,route,{
      get:path=>api(path),identity:()=>({modelId:selectedId.current,route:window.location.hash}),
      result:result=>setView({modelId,route,result}),failure:setError,settled:()=>setBusy(false),
    });
  }
  const result=view?.modelId===modelId&&view.route===window.location.hash?view.result:undefined;
  if(!modelId)return null;
  return <section className="model-registration-provenance" aria-label="모델 등록 선언 관측" lang="ko"><h3><Icon name="clipboard" size={20}/>모델 등록 선언 관측</h3><p>선택한 모델의 저장 메타데이터 안에서 버전 선언과 부모 해시의 일치 여부만 읽습니다. 자동으로 조회하지 않습니다.</p><button type="button" className="secondary" disabled={busy} onClick={()=>void inspect()}><Icon name="search" size={18}/>{busy?'등록 선언 조회 중…':'등록 선언 관측 조회'}</button>{error&&<p role="alert" className="mrp-message">{error}</p>}{result&&<><p role="status" className="mrp-message"><strong>{provenanceStatusLabels[result.status]}</strong></p><dl><div><dt>체크포인트 해시 관계</dt><dd>{provenanceBindingLabels[result.bindings.checkpoint_sha256]}</dd></div><div><dt>학습 보고서 해시 관계</dt><dd>{provenanceBindingLabels[result.bindings.training_report_sha256]}</dd></div><div><dt>선택 모델 버전 관계</dt><dd>{provenanceBindingLabels[result.bindings.model_version]}</dd></div></dl>{result.issue&&<p>고정 진단 코드 <code>{result.issue.code}</code> · 검사 필드 <code>{result.issue.field}</code></p>}</>}<p>이 진단의 범위: 기관 권위·실제 파일 바이트·실행 승인·과학 정확도는 항상 미검증입니다. 기존 모델의 승인 필드 값을 바꾸거나 평가한 결과가 아닙니다. 메타데이터 일치도 원본 인증이나 승인으로 해석하지 않습니다.</p></section>;
}
