import {modelVersionIssue} from './modelVersionRegistrationAdapter.ts';
type Row=Record<string,unknown>;
const row=(v:unknown):v is Row=>!!v&&typeof v==='object'&&!Array.isArray(v);
const exact=(v:unknown,keys:string[]):v is Row=>row(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const sha=(v:unknown):v is string=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const integer=(v:unknown):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
const label=(v:unknown,max=128):v is string=>typeof v==='string'&&Array.from(v).length>0&&Array.from(v).length<=max&&Array.from(v).every(c=>{const n=c.codePointAt(0)!;return n>=32&&!(n>=127&&n<=159)&&!(n>=0xd800&&n<=0xdfff);});
const need=(v:unknown)=>{if(!v)throw new Error('오류 분석 응답 형식과 고정 참조를 확인할 수 없습니다.');};
export type ModelErrorRequest={schema_version:1;model_ref:{id:string;version:string;sha256:string};training_report_sha256:string};
export function modelErrorPins(value:unknown):ModelErrorRequest|undefined{
 if(!row(value)||typeof value.id!=='string'||!/^[A-Za-z0-9_-]{1,100}$/.test(value.id)||!sha(value.checkpoint_sha256)||!sha(value.training_report_sha256))return;
 const d=value.model_version_declaration;
 if(!exact(d,['schema_version','source','version','checkpoint_sha256','training_report_sha256'])||d.schema_version!==1||d.source!=='CALLER_EXPLICIT_REGISTRATION'||modelVersionIssue(d.version)||d.checkpoint_sha256!==value.checkpoint_sha256||d.training_report_sha256!==value.training_report_sha256||('model_version'in value&&value.model_version!==d.version))return;
 return {schema_version:1,model_ref:{id:value.id,version:d.version as string,sha256:value.checkpoint_sha256},training_report_sha256:value.training_report_sha256};
}
export const errorClassLabels={REFERENCE_AND_PREDICTION_ABSENT:'참조·예측 모두 미관측',NO_REFERENCE_SUPPORT:'참조 미관측',REFERENCE_PRESENT_NOT_PREDICTED:'참조 있음 · 예측 없음',OBSERVED:'참조·예측 관측'};
export type ErrorClass={class_index:number;class_name:string;status:keyof typeof errorClassLabels;reference_pixels:number;predicted_pixels:number;true_positive_pixels:number;false_negative_pixels:number;false_positive_pixels:number;recall:number|null;precision:number|null;omission_rate:number|null;commission_rate:number|null;recall_evaluable:boolean;precision_evaluable:boolean};
export type ErrorPair={reference_class_index:number;reference_class_name:string;predicted_class_index:number;predicted_class_name:string;pixel_count:number;reference_class_fraction:number};
export type ErrorSplit={schema_version:1;scope:string;matrix_axes:string;reference_pixel_count:number;misclassified_pixel_count:number;classes:ErrorClass[];confusion_pairs:ErrorPair[];unobserved_reference_classes:number[];unpredicted_reference_present_classes:number[];spatial_error_map_generated:false;independent_accuracy_certified:false};
export type ErrorAnalysis={selected_epoch:number;model_id:string;checkpoint_sha256:string;reference_kind:string;by_split:{val:ErrorSplit;test:ErrorSplit}};
export type ErrorArtifact={index:number;filename:string;sha256:string;bytes:number};
export type ModelErrorView={schema_version:1;scope:string;status:'AVAILABLE'|'UNAVAILABLE';issue:null|'MODEL_VERSION_DECLARATION_UNAVAILABLE'|'ERROR_ANALYSIS_UNAVAILABLE';model_ref:ModelErrorRequest['model_ref'];training_report_sha256:string;analysis:ErrorAnalysis|null;artifacts:ErrorArtifact[];scientific_accuracy_validated:false;standard_gmais_result:false};
const fraction=(value:unknown,wanted:number|null)=>wanted===null?value===null:typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=1&&Math.abs(value-wanted)<=1e-12;
function parseSplit(value:unknown):ErrorSplit{
 need(exact(value,['schema_version','scope','matrix_axes','reference_pixel_count','misclassified_pixel_count','classes','confusion_pairs','unobserved_reference_classes','unpredicted_reference_present_classes','spatial_error_map_generated','independent_accuracy_certified']));const v=value as Row;
 need(v.schema_version===1&&v.scope==='FINAL_CONFUSION_ERROR_ANALYSIS_ONLY'&&v.matrix_axes==='ROWS_REFERENCE_COLUMNS_PREDICTION'&&v.spatial_error_map_generated===false&&v.independent_accuracy_certified===false&&integer(v.reference_pixel_count)&&integer(v.misclassified_pixel_count)&&Array.isArray(v.classes)&&v.classes.length===9&&Array.isArray(v.confusion_pairs)&&v.confusion_pairs.length<=72);
 const classes=Array.from(v.classes as unknown[]);const matrix=Array.from({length:9},()=>Array(9).fill(0) as number[]);
 classes.forEach((c,i)=>{need(exact(c,['class_index','class_name','status','reference_pixels','predicted_pixels','true_positive_pixels','false_negative_pixels','false_positive_pixels','recall','precision','omission_rate','commission_rate','recall_evaluable','precision_evaluable']));const a=c as Row;need(a.class_index===i&&label(a.class_name)&&Object.hasOwn(errorClassLabels,String(a.status))&&['reference_pixels','predicted_pixels','true_positive_pixels','false_negative_pixels','false_positive_pixels'].every(k=>integer(a[k])));matrix[i][i]=a.true_positive_pixels as number;});
 const pairs=Array.from(v.confusion_pairs as unknown[]);let previous:ErrorPair|undefined;
 pairs.forEach(p=>{need(exact(p,['reference_class_index','reference_class_name','predicted_class_index','predicted_class_name','pixel_count','reference_class_fraction']));const a=p as ErrorPair;const i=a.reference_class_index,j=a.predicted_class_index;need(integer(i)&&i<9&&integer(j)&&j<9&&i!==j&&integer(a.pixel_count)&&a.pixel_count>0&&matrix[i][j]===0&&a.reference_class_name===(classes[i] as Row).class_name&&a.predicted_class_name===(classes[j] as Row).class_name);if(previous)need(previous.pixel_count>a.pixel_count||(previous.pixel_count===a.pixel_count&&(previous.reference_class_index<i||(previous.reference_class_index===i&&previous.predicted_class_index<j))));matrix[i][j]=a.pixel_count;previous=a;});
 const reference=matrix.map(r=>r.reduce((a,b)=>a+b,0)),predicted=classes.map((_,j)=>matrix.reduce((s,r)=>s+r[j],0));const total=reference.reduce((a,b)=>a+b,0),tp=matrix.reduce((s,r,i)=>s+r[i],0);
 need(Number.isSafeInteger(total)&&total===v.reference_pixel_count&&total-tp===v.misclassified_pixel_count);
 classes.forEach((c,i)=>{const a=c as ErrorClass,r=reference[i],p=predicted[i],t=matrix[i][i];need(a.reference_pixels===r&&a.predicted_pixels===p&&a.false_negative_pixels===r-t&&a.false_positive_pixels===p-t&&a.recall_evaluable===(r>0)&&a.precision_evaluable===(p>0));need(fraction(a.recall,r?t/r:null)&&fraction(a.precision,p?t/p:null)&&fraction(a.omission_rate,r?(r-t)/r:null)&&fraction(a.commission_rate,p?(p-t)/p:null));need(a.status===(!r&&!p?'REFERENCE_AND_PREDICTION_ABSENT':!r?'NO_REFERENCE_SUPPORT':!p?'REFERENCE_PRESENT_NOT_PREDICTED':'OBSERVED'));});
 pairs.forEach(p=>{const a=p as ErrorPair;need(fraction(a.reference_class_fraction,a.pixel_count/reference[a.reference_class_index]));});
 need(JSON.stringify(v.unobserved_reference_classes)===JSON.stringify(reference.flatMap((n,i)=>n===0?[i]:[]))&&JSON.stringify(v.unpredicted_reference_present_classes)===JSON.stringify(reference.flatMap((n,i)=>n>0&&predicted[i]===0?[i]:[])));
 return value as ErrorSplit;
}
export const errorArtifactNames=['error-analysis.json','error-analysis-classes.csv','error-analysis-confusions.csv'] as const;
export function parseModelErrorView(value:unknown,request:ModelErrorRequest):ModelErrorView{
 need(exact(value,['schema_version','scope','status','issue','model_ref','training_report_sha256','analysis','artifacts','scientific_accuracy_validated','standard_gmais_result']));const v=value as Row;
 need(v.schema_version===1&&v.scope==='PINNED_TRAINING_ERROR_ANALYSIS_READ_ONLY'&&v.scientific_accuracy_validated===false&&v.standard_gmais_result===false&&exact(v.model_ref,['id','version','sha256'])&&v.model_ref.id===request.model_ref.id&&v.model_ref.version===request.model_ref.version&&v.model_ref.sha256===request.model_ref.sha256&&v.training_report_sha256===request.training_report_sha256&&Array.isArray(v.artifacts));
 if(v.status==='UNAVAILABLE'){need(typeof v.issue==='string'&&['MODEL_VERSION_DECLARATION_UNAVAILABLE','ERROR_ANALYSIS_UNAVAILABLE'].includes(v.issue)&&v.analysis===null&&(v.artifacts as unknown[]).length===0);return value as ModelErrorView;}
 need(v.status==='AVAILABLE'&&v.issue===null&&(v.artifacts as unknown[]).length===3);
 Array.from(v.artifacts as unknown[]).forEach((a,i)=>{need(exact(a,['index','filename','sha256','bytes']));const r=a as Row;need(r.index===i&&r.filename===errorArtifactNames[i]&&sha(r.sha256)&&integer(r.bytes)&&r.bytes>0&&r.bytes<=8*1024*1024);});
 need(exact(v.analysis,['schema_version','scope','selected_epoch','model_id','checkpoint_sha256','reference_kind','claim','test_used_for_epoch_selection','training_policy_changed','scientific_accuracy_validated','by_split']));const a=v.analysis as Row;
 need(a.schema_version===1&&a.scope==='SELECTED_BEST_EPOCH_FINAL_ERROR_ANALYSIS'&&integer(a.selected_epoch)&&a.selected_epoch>0&&a.model_id===request.model_ref.id&&a.checkpoint_sha256===request.model_ref.sha256&&label(a.reference_kind)&&label(a.claim,256)&&a.test_used_for_epoch_selection===false&&a.training_policy_changed===false&&a.scientific_accuracy_validated===false&&exact(a.by_split,['val','test']));
 const splits=a.by_split as Row,val=parseSplit(splits.val),test=parseSplit(splits.test);need(val.classes.every((c,i)=>c.class_name===test.classes[i].class_name));
 return value as ModelErrorView;
}
export function modelErrorResponse(status:number,value:unknown,request:ModelErrorRequest){if(status===200)return parseModelErrorView(value,request);if(status===401||status===403)throw new Error('인증 또는 접근 권한을 확인하세요.');const codes:Record<string,number>={INVALID_REQUEST:400,REQUEST_TOO_LARGE:413,NOT_FOUND:404,PIN_CONFLICT:409,STORED_OUTPUT_CHANGED:503,RESOURCE_UNAVAILABLE:503};if(exact(value,['error'])&&exact(value.error,['code','message','retryable'])&&typeof value.error.code==='string'&&codes[value.error.code]===status&&value.error.retryable===false&&label(value.error.message,256))throw new Error(status===409?'모델 고정 참조가 현재 저장 기록과 다릅니다.':status===404?'선택 모델 또는 오류 분석 파일을 찾을 수 없습니다.':'오류 분석을 읽을 수 없습니다. 파일을 생성하거나 자동 재시도하지 않습니다.');throw new Error('오류 분석 응답 형식을 확인할 수 없습니다.');}
export class ModelErrorFlight{
 private generation=0;private pending=false;
 invalidate(){this.generation++;this.pending=false;}
 async run(identity:string,route:string,h:{current:()=>{identity:string;route:string};work:(live:()=>boolean)=>Promise<void>;failure:(message:string)=>void;settled:()=>void}){if(this.pending)return;this.pending=true;const g=this.generation,live=()=>g===this.generation&&h.current().identity===identity&&h.current().route===route;try{await h.work(live);}catch{if(live())h.failure('오류 분석을 표시할 수 없습니다. 고정 참조·인증·파일 상태를 확인하세요. 자동 생성·재시도하지 않습니다.');}finally{if(live()){this.pending=false;h.settled();}}}
}
