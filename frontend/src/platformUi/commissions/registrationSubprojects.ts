import { computed, onBeforeUnmount, ref, watch, toRaw } from 'vue'
import { fetchSubprojects, fetchErpSubprojects } from '@/services/businessSupplement'

const fields: Record<string,string> = {name:'projectName',accountingDepartment:'dept',businessCategory:'businessCategory',amount:'amount',receivedAmount:'receivedAmount',receiptType:'receiptType',paymentDescription:'paymentDescription',notes:'remark'}

// The template edits visible fields; source identifiers remain on the backend rows.
export function registrationSubprojects(c:any, onError:(error:unknown)=>void) {
  const choices=ref<any[]>([]), ids=new WeakMap<object,string>()
  let sequence=0, nextId=0
  const identity=(row:any)=>{row=toRaw(row);if(!ids.has(row))ids.set(row,`saved-${++nextId}`);return ids.get(row)!}
  const key=(row:any)=>row.source==='erp'?JSON.stringify([row.contractNo,row.catalogCode,row.sourceEventId]):row.catalogId?`catalog:${row.catalogId}`:''
  watch(()=>[c.mode,c.sampleEntrustNo],async()=>{
    const token=++sequence;choices.value=[]
    if(c.mode==='entrust')return
    try {
      const [catalog,erp]=await Promise.all([fetchSubprojects(),c.sampleEntrustNo?fetchErpSubprojects(c.sampleEntrustNo):Promise.resolve({rows:[]})])
      if(token!==sequence)return
      choices.value=[...catalog.filter(r=>r.enabled).map(r=>({projectName:r.name,dept:r.dept,businessCategory:r.businessCategory,source:'manual',sourceKey:'',sourceEventId:'',sourceProof:'',contractNo:'',catalogId:r.id,catalogCode:r.code,catalogRevision:r.revision})),...erp.rows.filter(r=>r.enabled).map(r=>({projectName:r.name,dept:r.dept,businessCategory:r.businessCategory,source:'erp',contractNo:r.contractNo,catalogId:null,catalogCode:r.code,catalogRevision:null,sourceKey:r.sourceKey,sourceEventId:r.sourceEventId,sourceProof:r.sourceProof}))]
    } catch(error){if(token===sequence)onError(error)}
  },{immediate:true})
  onBeforeUnmount(()=>sequence++)
  const label=(row:any)=>`${row.projectName}（${row.catalogCode || row.catalogId || ''}${row.source==='erp'?' · 外部ERP':''}）`
  const labelFor=(row:any)=>choices.value.some(r=>key(r)&&key(r)===key(row))?label(row):row.projectName
  const options=computed(()=>{
    const rows=[...choices.value.map(r=>({name:label(r),accountingDepartment:r.dept,businessCategory:r.businessCategory})),...c.s.subItems.map((r:any)=>({name:labelFor(r),accountingDepartment:r.dept,businessCategory:r.businessCategory}))]
    return [...new Map(rows.filter(r=>r.name).map(r=>[r.name,r])).values()]
  })
  function get(){return c.s.subItems.map((row:any)=>({id:identity(row),...Object.fromEntries(Object.entries(fields).map(([to,from])=>[to,row[from]??''])),name:labelFor(row)}))}
  function set(rows:any[]){
    if(c.readOnly||c.submitting)return
    const previous=new Map(c.s.subItems.map((r:any)=>[identity(r),r]))
    c.s.subItems=rows.map(row=>{
      const saved:any=previous.get(row.id), choice=choices.value.find(r=>label(r)===row.name)
      const unchanged=saved&&row.name===labelFor(saved)
      if(!unchanged&&!choice)throw Error('子项目选项已变化，请重新选择')
      const result={...saved,...(!unchanged?choice:{}),...Object.fromEntries(Object.entries(fields).map(([to,from])=>[from,row[to]??''])),projectName:unchanged?saved.projectName:choice.projectName}
      if(result.source==='erp'){result.dept=(unchanged?saved:choice).dept;result.businessCategory=(unchanged?saved:choice).businessCategory}
      ids.set(result,row.id)
      return result
    })
  }
  const isLocked=(name:string,id:string)=>{const saved=c.s.subItems.find((r:any)=>identity(r)===id);return (saved&&name===labelFor(saved)?saved:choices.value.find(r=>label(r)===name))?.source==='erp'}
  return {get,set,options,isLocked}
}
