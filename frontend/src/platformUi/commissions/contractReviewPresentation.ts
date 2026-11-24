import { standardResolutionForm } from '../standardResolutionForm'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { fetchCompliancePreflight, type CompliancePreflight } from '@/services/pipeline'
import { emptyContractReview } from '../../types/commissions/contractReview'
import { platformError } from '../apiErrors'
import type { FormSchema } from '../../types/forms'

export function createContractReviewPresentation(c:any) {
  const keyMap:Record<string,string>={technicalCapability:'tech',equipment:'instrument',environment:'env',methods:'method',personnel:'personnel',sample:'sample',basisAuthorization:'basisAuth'}
  const form=reactive(new Proxy(emptyContractReview(),{
    get(t,k:string){if(keyMap[k])return !!c.form.items[keyMap[k]];if(k==='cma'||k==='cnas')return c.form[k];if(k==='other')return false;return (t as any)[k]},
    set(t,k:string,v){if(c.formReadOnly||c.reviewBusy||k==='other'||k==='otherText')return true;if(keyMap[k])c.form.items[keyMap[k]]=v;else if(k==='cma'||k==='cnas')c.form[k]=v;else(t as any)[k]=v;return true},
  }))
  const preflight=ref<CompliancePreflight>(),checking=ref(false),readConfirmed=ref(false),checkError=ref<any>(''),error=ref<any>(''),rejectionOpen=ref(false),opinion=reactive({value:''})
  let generation=0
  const invalidate=()=>{generation++;preflight.value=undefined;readConfirmed.value=false;checking.value=false;opinion.value=''}
  watch(()=>[c.selectedReport?.reportNo,c.formOpen,c.formReadOnly],()=>{invalidate();error.value='';checkError.value='';rejectionOpen.value=false},{flush:'sync'})
  watch(()=>JSON.stringify(c.form.items)+c.form.cma+c.form.cnas, invalidate,{flush:'sync'})
  onBeforeUnmount(invalidate)
  const busy=computed(()=>c.reviewBusy),refreshing=computed(()=>c.reviewDetailLoading||c.formReadOnly)
  const record=computed(()=>c.formOpen?{id:c.selectedReport?.reportNo,code:c.selectedReport?.sampleNo,name:c.selectedReport?.project}:undefined)
  const hasResults=computed(()=>!!preflight.value),requiresOpinion=computed(()=>!!preflight.value?.requiresOpinion)
  const canApprove=computed(()=>!c.formReadOnly&&c.canPass&&c.session.canAction('report.contract_review.pass')&&readConfirmed.value&&preflight.value?.ready&&!preflight.value.hardBlockers.length&&(!requiresOpinion.value||!!opinion.value.trim()))
  const results=computed(()=>preflight.value?[{sampleId:c.selectedReport.reportNo,checkedAt:new Date().toISOString(),messages:preflight.value.issues.length?preflight.value.issues.map(i=>({tone:i.hardBlocker||i.acknowledgeable?'warning':'info',text:({block:'【阻断】',confirm:'【需确认】',notice:'【提示】'}[i.level|| (i.hardBlocker?'block':i.acknowledgeable?'confirm':'notice')])+(i.message||i.title)})):[{tone:'info',text:'合规校核完成'}]}]:[])
  async function check(){if(checking.value||busy.value||refreshing.value||!record.value)return;invalidate();const token=generation;checking.value=true;checkError.value='';try{const result=await fetchCompliancePreflight(c.selectedReport.reportNo,'contract_review');if(token===generation)preflight.value=result}catch(e){if(token===generation)checkError.value=platformError(e)}finally{if(token===generation)checking.value=false}}
  const standardResolution=standardResolutionForm(preflight,()=>c.selectedReport?.reportNo,check)
  async function resolveStandards(){try{await standardResolution.resolve()}catch(e){checkError.value=platformError(e)}}
  function cancel(){if(!busy.value){invalidate();c.formOpen=false}}
  async function submit(event:Event){const decision=(event as SubmitEvent).submitter?.getAttribute('value');if(busy.value||refreshing.value||checking.value)return;if(decision==='rejected'){if(c.session.canAction('report.contract_review.return'))rejectionOpen.value=true;return}if(decision!=='approved'||!canApprove.value)return;const p=preflight.value!;await c.approve({preflightVersion:p.preflightVersion,acknowledgedIssueIds:p.issues.filter(i=>i.acknowledgeable).map(i=>i.id),finalSeal:p.finalSeal,...(p.requiresOpinion?{complianceOpinion:opinion.value.trim()}:{})})}
  async function reject(reason:string){if(!reason.trim()||busy.value||c.formReadOnly||!c.session.canAction('report.contract_review.return'))return false;c.form.opinion=reason.trim();await c.submit('return');return !c.formOpen}
  const complianceSchema:FormSchema<any>={sections:[{id:'contract-required-opinion',title:'合规确认',fields:[{id:'contract-compliance-opinion',label:'合规确认意见',control:'textarea',required:true,binding:{get:()=>opinion.value,set:(_,v)=>{opinion.value=v}}}]}]}
  return reactive({standardResolution,resolveStandards,form,record,busy,refreshing,checking,readConfirmed,checkError,error,hasResults,canApprove,results,requiresOpinion,complianceSchema,opinion,check,cancel,submit,reject,rejectionOpen,refreshSample:check,separateResultsScroll:false,isBatch:false,batchRecords:[] as any[],stale:false,sampleCaption:(id:string)=>id,canReturn:computed(()=>!c.formReadOnly&&c.session.canAction('report.contract_review.return'))})
}
