type Row=Record<string,unknown>;
const row=(v:unknown):v is Row=>!!v&&typeof v==='object'&&!Array.isArray(v);
const count=(v:unknown):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
const fraction=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1;
const sha=(v:unknown):v is string=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
export const progressSplits=['train','val','test'] as const;
export type ProgressSplit=typeof progressSplits[number];
export type ProgressRow={province:string;split:ProgressSplit;physical:number;eligible:number;yearCounts:Record<string,number>;cellGap:number};
export type BareObservation={pixels:number;ratio:number|null;contributingPatches:number};
export type CandidateProgress={sourceSha:string;eligible:number;splits:Record<ProgressSplit,number>;blockers:number;matchesCurrent:boolean;sourceReport:string;recordedAt:string;sceneConflicts:string[]};
export function parseCandidateProgress(value:unknown):CandidateProgress|undefined{
 if(!row(value)||value.available!==true)return;
 const fail=():never=>{throw new Error('후보 현황 응답 형식이 일치하지 않습니다.');};
 if(value.scope!=='PINNED_CANDIDATE_COHORT_NOT_AUTOMATIC_CURRENT_COLLECTION'||!sha(value.source_manifest_sha256)||value.ready_for_training!==false||value.scientific_accuracy_validated!==false||value.source_pins_match!==true||typeof value.source_matches_current_manifest!=='boolean'||!count(value.eligible_total)||!count(value.blocker_count)||!row(value.by_split)||!Array.isArray(value.scene_split_conflicts)||value.scene_split_conflicts.length!==0||typeof value.source_report!=='string'||value.source_report.length>512||/[\x00-\x1f\x7f]/.test(value.source_report)||typeof value.recorded_at!=='string'||!Number.isFinite(Date.parse(value.recorded_at)))fail();
 const sourceReport=value.source_report as string;if(/^(?:\/|\\|[A-Za-z]:|[a-z]+:)/i.test(sourceReport)||sourceReport.replaceAll('\\','/').split('/').some(p=>p==='..'||p==='.'||!p))fail();
 const bySplit=value.by_split as Row;if(Object.keys(bySplit).sort().join(',')!=='test,train,val'||progressSplits.some(s=>!count(bySplit[s]))||progressSplits.reduce((n,s)=>n+Number(bySplit[s]),0)!==value.eligible_total)fail();
 return {sourceSha:value.source_manifest_sha256 as string,eligible:value.eligible_total as number,splits:{train:bySplit.train as number,val:bySplit.val as number,test:bySplit.test as number},blockers:value.blocker_count as number,matchesCurrent:value.source_matches_current_manifest as boolean,sourceReport,recordedAt:value.recorded_at as string,sceneConflicts:[]};
}
export type BalancePolicy={priorityProvinces:string[]};
function parseBalancePolicy(value:unknown):BalancePolicy|undefined{
 if(value===undefined)return;
 if(!row(value)||value.scope!=='PLANNED_COLLECTION_PRIORITY_NOT_RUNNING_JOBS'||value.minimum_floor_not_equal_quota!==true||value.preserve_existing_patches!==true||value.deduplicate_before_enrollment!==true||!Array.isArray(value.priority_provinces)||value.priority_provinces.join(',')!=='southeast_sulawesi,gorontalo')throw new Error('수집 우선순위 정책 형식 불일치');
 return {priorityProvinces:[...value.priority_provinces] as string[]};
}
export type BareReview={sourceSha:string;matchesCurrent:boolean;recordedAt:string;sourceReport:string;total:number;searchedProvinces:string[];rows:{province:string;candidates:number;clear:number;overlap:number;invalid:number}[]};
export function parseBareReview(value:unknown,currentSha:string):BareReview|undefined{
 if(value===undefined||(row(value)&&value.available===false))return;
 const fail=():never=>{throw new Error('나지 후보 검토 응답 형식 불일치');};
 if(!row(value)||value.available!==true||value.status!=='LOCAL_TARGET_REVIEW_FINISHED'||value.scope!=='LOCAL_LABEL_AND_HISTORICAL_SUPPORT_NOT_REMOTE_QUALITY'||!sha(value.source_manifest_sha256)||!sha(value.report_sha256)||typeof value.source_matches_current_manifest!=='boolean'||value.source_matches_current_manifest!==(value.source_manifest_sha256===currentSha)||value.execution_supported!==false||value.actual_quality_verified!==false||value.scientific_accuracy_validated!==false||!count(value.candidate_total)||typeof value.recorded_at!=='string'||!Number.isFinite(Date.parse(value.recorded_at))||typeof value.source_report!=='string'||value.source_report.length>512||/[:\\\x00-\x1f\x7f]/.test(value.source_report)||value.source_report.split('/').some(p=>!p||p==='.'||p==='..')||!Array.isArray(value.rows)||value.rows.length!==6)return fail();
 const expected=['south_sulawesi','gorontalo','southeast_sulawesi','east_java','banten','west_java'];const searched=value.searched_provinces===undefined?[...expected]:value.searched_provinces;
 if(!Array.isArray(searched)||searched.length===0||searched.some(p=>typeof p!=='string'||!expected.includes(p))||new Set(searched).size!==searched.length)return fail();
 const seen=new Set<string>(),rows:BareReview['rows']=[];
 for(const raw of value.rows){if(!row(raw)||typeof raw.province!=='string'||!expected.includes(raw.province)||seen.has(raw.province)||['candidates','support_clear','overlap','local_invalid'].some(k=>!count(raw[k]))||raw.candidates!==Number(raw.support_clear)+Number(raw.overlap)+Number(raw.local_invalid))return fail();seen.add(raw.province);rows.push({province:raw.province,candidates:raw.candidates as number,clear:raw.support_clear as number,overlap:raw.overlap as number,invalid:raw.local_invalid as number});}
 if(rows.reduce((n,r)=>n+r.candidates,0)!==value.candidate_total||rows.some(r=>!searched.includes(r.province)&&r.candidates!==0))return fail();
 return {sourceSha:value.source_manifest_sha256,matchesCurrent:value.source_matches_current_manifest,recordedAt:value.recorded_at,sourceReport:value.source_report,total:value.candidate_total,searchedProvinces:[...searched] as string[],rows};
}
export type BudgetProgress={maximum:number;charged:number;remaining:number;settled:number;metadata:number;pending:number;pendingCount:number;oldPending:number;oldPendingCount:number;sourceSha:string;ledgerSha:string;observedAt:string;updatedAt:string;rateLimited:boolean};
export function parseBudgetProgress(value:unknown,currentSha:string):BudgetProgress|undefined{
 if(value===undefined||(row(value)&&value.available===false))return;
 const fail=():never=>{throw new Error('예산 원장 응답 확인 필요');};
 if(!row(value)||value.schema_version!==1||value.available!==true||value.status!=='OBSERVED_LEDGER_SNAPSHOT'||value.scope!=='ADDITIONAL_BUDGET_INCLUDES_PENDING_NOT_PROCESS_LIVENESS'||value.process_verification!=='UNKNOWN'||value.execution_approved!==false||!sha(value.source_manifest_sha256)||value.source_manifest_sha256!==currentSha||!sha(value.ledger_sha256)||typeof value.rate_limit_active!=='boolean'||typeof value.observed_at!=='string'||!Number.isFinite(Date.parse(value.observed_at))||typeof value.ledger_updated_at!=='string'||!Number.isFinite(Date.parse(value.ledger_updated_at)))return fail();
 const expected=['schema_version','available','status','scope','process_verification','execution_approved','source_manifest_sha256','ledger_sha256','rate_limit_active','observed_at','ledger_updated_at','additional_maximum_bytes','charged_including_pending_bytes','remaining_bytes','settled_batch_bytes','metadata_body_bytes','pending_bytes','pending_count','old_pending_bytes','old_pending_count'];if(Object.keys(value).sort().join(',')!==expected.sort().join(',')||![value.observed_at,value.ledger_updated_at].every(t=>/(?:Z|[+-]\d{2}:\d{2})$/.test(t as string)))return fail();
 const fields=['additional_maximum_bytes','charged_including_pending_bytes','remaining_bytes','settled_batch_bytes','metadata_body_bytes','pending_bytes','pending_count','old_pending_bytes','old_pending_count'];if(fields.some(k=>!count(value[k])))return fail();
 const v=value as Record<string,number>;
 if(v.additional_maximum_bytes<1||v.additional_maximum_bytes>4*1024**3||v.charged_including_pending_bytes>v.additional_maximum_bytes||v.remaining_bytes!==v.additional_maximum_bytes-v.charged_including_pending_bytes||v.settled_batch_bytes+v.metadata_body_bytes+v.pending_bytes!==v.charged_including_pending_bytes||v.old_pending_bytes>v.pending_bytes||v.old_pending_count>2||v.old_pending_count>v.pending_count||v.pending_count>10000||(v.pending_count===0)!==(v.pending_bytes===0)||(v.old_pending_count===0)!==(v.old_pending_bytes===0))return fail();
 return {maximum:v.additional_maximum_bytes,charged:v.charged_including_pending_bytes,remaining:v.remaining_bytes,settled:v.settled_batch_bytes,metadata:v.metadata_body_bytes,pending:v.pending_bytes,pendingCount:v.pending_count,oldPending:v.old_pending_bytes,oldPendingCount:v.old_pending_count,sourceSha:value.source_manifest_sha256,ledgerSha:value.ledger_sha256,observedAt:value.observed_at,updatedAt:value.ledger_updated_at,rateLimited:value.rate_limit_active};
}
export type CollectionProgressView={budget?:BudgetProgress;budgetInvalid:boolean;bareReview?:BareReview;bareReviewInvalid:boolean;balancePolicy?:BalancePolicy;sourceSha:string;physical:number;eligible:number;ineligible:number;target:number;targetGap:number;cellFloor:number;cellGap:number;years:string[];rows:ProgressRow[];splits:Record<ProgressSplit,number>;minValid:number;minProvince:number;classFraction:number;minClassPatches:number;minPixelsPerPatch:number;minPixelsPerSplit:number;maxDominance:number;bare:Record<ProgressSplit,BareObservation>;sceneConflicts:string[]};
export function parseCollectionProgress(value:unknown):CollectionProgressView|undefined{
 if(!row(value)||value.available!==true)return;
 const fail=():never=>{throw new Error('수집 현황 응답의 집계·정책 형식을 확인할 수 없습니다.');};
 if(value.count_basis!=='manifest_quality_status'||!sha(value.source_manifest_sha256)||value.native_raster_reverified!==false||value.learning_ready!==false||value.scientific_accuracy_validated!==false)fail();
 const keys=['physical_total','eligible_total','ineligible_total','eligible_target','eligible_target_gap','cell_floor','cell_gap_total'];if(keys.some(key=>!count(value[key])))fail();
 if(Number(value.physical_total)!==Number(value.eligible_total)+Number(value.ineligible_total)||Number(value.eligible_target_gap)!==Math.max(0,Number(value.eligible_target)-Number(value.eligible_total)))fail();
 if(!fraction(value.minimum_valid_fraction)||!fraction(value.minimum_province_fraction)||!Array.isArray(value.rows)||value.rows.length!==6||!row(value.class_quality))fail();
 const rows:ProgressRow[]=[],splits={train:0,val:0,test:0},seen=new Set<string>();let years:string[]|undefined;
 for(const raw of value.rows as unknown[]){
  if(!row(raw))return fail();const item=raw;
  if(typeof item.province!=='string'||!/^[a-z_]{1,64}$/.test(item.province)||seen.has(item.province)||!progressSplits.includes(item.split as ProgressSplit)||!count(item.physical)||!count(item.eligible)||!count(item.cell_gap)||!row(item.year_counts))fail();
  const current=Object.keys(item.year_counts as Row).sort();if(current.length!==6||current.some(y=>!/^20[0-9]{2}$/.test(y))||current.some((y,i)=>i>0&&Number(y)!==Number(current[i-1])+1)||Object.values(item.year_counts as Row).some(n=>!count(n)))fail();
  if(years&&years.join(',')!==current.join(','))fail();years=current;seen.add(item.province as string);
  const yearCounts={...item.year_counts as Record<string,number>};if(Object.values(yearCounts).reduce((a,b)=>a+b,0)!==item.eligible||Number(item.eligible)>Number(item.physical)||Object.values(yearCounts).reduce((a,n)=>a+Math.max(0,Number(value.cell_floor)-n),0)!==item.cell_gap)fail();
  const split=item.split as ProgressSplit;splits[split]+=item.eligible as number;rows.push({province:item.province as string,split,physical:item.physical as number,eligible:item.eligible as number,yearCounts,cellGap:item.cell_gap as number});
 }
 if(rows.reduce((a,r)=>a+r.physical,0)!==value.physical_total||rows.reduce((a,r)=>a+r.eligible,0)!==value.eligible_total||rows.reduce((a,r)=>a+r.cellGap,0)!==value.cell_gap_total)fail();
 const c=value.class_quality as Row;if(!fraction(c.required_fraction)||!fraction(c.max_dominance)||!count(c.minimum_contributing_patches)||!count(c.minimum_pixels_per_contributing_patch)||!count(c.minimum_pixels_per_split)||!row(c.bare_by_split)||!Array.isArray(c.scene_split_conflicts)||c.scene_split_conflicts.length>20000||c.scene_split_conflicts.some(s=>typeof s!=='string'||s.length>512||/[\x00-\x1f\x7f]/.test(s)))fail();
 const bare={} as Record<ProgressSplit,BareObservation>;
 for(const split of progressSplits){const raw=(c.bare_by_split as Row)[split];if(!row(raw))return fail();const b=raw;if(!count(b.pixels)||!count(b.contributing_patches)||(b.ratio!==null&&!fraction(b.ratio)))fail();bare[split]={pixels:b.pixels as number,ratio:b.ratio as number|null,contributingPatches:b.contributing_patches as number};}
 let bareReview:BareReview|undefined,bareReviewInvalid=false;try{bareReview=parseBareReview(value.bare_target_review,value.source_manifest_sha256 as string);}catch{bareReviewInvalid=true;}
 let budget:BudgetProgress|undefined,budgetInvalid=false;try{budget=parseBudgetProgress(value.budget_status,value.source_manifest_sha256 as string);}catch{budgetInvalid=true;}
 return {budget,budgetInvalid,bareReview,bareReviewInvalid,balancePolicy:parseBalancePolicy(value.balance_policy),sourceSha:value.source_manifest_sha256 as string,physical:value.physical_total as number,eligible:value.eligible_total as number,ineligible:value.ineligible_total as number,target:value.eligible_target as number,targetGap:value.eligible_target_gap as number,cellFloor:value.cell_floor as number,cellGap:value.cell_gap_total as number,years:years!,rows,splits,minValid:value.minimum_valid_fraction as number,minProvince:value.minimum_province_fraction as number,classFraction:c.required_fraction as number,minClassPatches:c.minimum_contributing_patches as number,minPixelsPerPatch:c.minimum_pixels_per_contributing_patch as number,minPixelsPerSplit:c.minimum_pixels_per_split as number,maxDominance:c.max_dominance as number,bare,sceneConflicts:[...c.scene_split_conflicts as string[]]};
}
export class CollectionProgressFlight{
 private generation=0;private pending=false;private controller?:AbortController;
 invalidate(){this.generation++;this.pending=false;this.controller?.abort();}
 async run(route:string,h:{route:()=>string;work:(signal:AbortSignal,live:()=>boolean)=>Promise<void>;error:()=>void;settled:()=>void}){
  if(this.pending)return;this.pending=true;const generation=this.generation,controller=new AbortController();this.controller=controller;
  const live=()=>generation===this.generation&&!controller.signal.aborted&&h.route()===route;
  try{await h.work(controller.signal,live);}catch{if(live())h.error();}finally{if(live()){this.pending=false;h.settled();}}
 }
}
