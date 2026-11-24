import { computed, reactive, ref, type Ref } from 'vue'
import type { FormSchema } from '../types/forms'
import { resolveReportStandards, type CompliancePreflight } from '@/services/pipeline'

export function standardResolutionForm(preflight:Ref<CompliancePreflight|undefined>, number:()=>string, refresh:()=>Promise<void>) {
 const selected=reactive<Record<string,string>>({}),reason=ref(''),busy=ref(false)
 const needed=computed(()=>!!preflight.value?.standardChoices?.length)
 const schema=computed<FormSchema<any>>(()=>({sections:[{id:'standard-resolution',title:'确认标准记录',fields:[
  ...(preflight.value?.standardChoices||[]).map((row,index)=>({id:'standard-choice-'+index,label:row.code,control:'select' as const,required:true,emptyLabel:row.candidates.length?'请选择对应标准':'没有候选，请维护标准库或走委托更改',options:row.candidates.map(c=>({value:String(c.id),label:`${c.code} · ${c.name} · ${c.department} · ${c.implementationDate||'未登记实施日'} · ${c.marks||'无资质标识'}`})),binding:{get:()=>selected[row.code]||'',set:(_:any,value:string)=>{selected[row.code]=value}}})),
  {id:'standard-resolution-reason',label:'确认依据',control:'textarea',required:true,binding:{get:()=>reason.value,set:(_:any,value:string)=>{reason.value=value}}}
 ]}]}))
 async function resolve(){
  if(busy.value||!preflight.value)return
  busy.value=true
  try{
   const p=preflight.value
   await resolveReportStandards(number(),{stage:p.stage,preflightVersion:p.preflightVersion,selections:Object.fromEntries((p.standardChoices||[]).map(r=>[r.code,Number(selected[r.code])])),reason:reason.value})
   reason.value='';for(const key of Object.keys(selected))delete selected[key]
   await refresh()
  }finally{busy.value=false}
 }
 return reactive({needed,schema,selected,busy,resolve})
}
