import {downloadIssuanceRecord} from '@/services/issuanceRecords'
import {handlingStates} from '../handlingStatus'
import {computed,ref} from 'vue'
import {ElMessageBox} from 'element-plus'
import {platformError} from '../apiErrors'
import {createReportStagePresentation,type ReportStageContext} from './reportStagePresentation'
import outputKeys from './ReportOutputListPresentation.keys.json'
import queryKeys from './ReportQueryListPresentation.keys.json'
type Row=Record<string,any>
type OutputAction = 'report.archive.pass' | 'report.distribution.complete'
type OutputContext = ReportStageContext & {
  completeOutput?: (reportNo: string, action: OutputAction) => Promise<void>
}
type BatchRow = {id: string; allowedActions?: readonly string[]}
type BatchResult = {stage: string; account: string; label: string; succeeded: number; failures: {reportNo: string; reason: string}[]}

export function createReportOutputPresentation(c:OutputContext){const m=createReportStagePresentation(c);for(const key of [...outputKeys,...queryKeys])if(!(key in m))m[key]=undefined;
 const operation = computed(() => {
  if (c.pageKey === 'archive') return {action: 'report.archive.pass' as const, label: '归档'}
  if (c.pageKey === 'release') return {action: 'report.distribution.complete' as const, label: '发放'}
 })
 const batchBusy = ref(false)
 const batchProgress = ref({done: 0, total: 0})
 const batchResult = ref<BatchResult>()
 const canBatch = computed(() => !!(operation.value && c.completeOutput && c.session.canAction(operation.value.action)))
 const batchCandidates = computed(() => {
  const action = operation.value?.action
  if (!action) return []
  return (m.rows.items as BatchRow[]).filter(row => m.selected.includes(row.id) && row.allowedActions?.includes(action))
    .map(row => row.id)
 })

 async function completeSelected() {
  const task = operation.value
  const complete = c.completeOutput
  const reportNos = [...batchCandidates.value]
  if (!task || !complete || !canBatch.value || batchBusy.value || m.loading || m.error || !reportNos.length) return
  const stage = c.pageKey
  const actor = c.session.account
  batchBusy.value = true
  try {
   const skipped = m.rows.items.filter((row: BatchRow) => m.selected.includes(row.id)).length - reportNos.length
   const message = `确认${task.label}当前页已选且可办理的 ${reportNos.length} 份报告？${skipped ? `其余 ${skipped} 份当前不可办理。` : ''}`
   try {
    await ElMessageBox.confirm(message, `批量${task.label}`, {confirmButtonText: `确认${task.label}`, cancelButtonText: '取消'})
   } catch {
    return
   }
   if (c.pageKey !== stage || c.session.account !== actor || !canBatch.value) return
   const result: BatchResult = {stage, account: actor, label: task.label, succeeded: 0, failures: []}
   const completed = new Set<string>()
   batchResult.value = undefined
   batchProgress.value = {done: 0, total: reportNos.length}
   for (const reportNo of reportNos) {
    if (c.session.account !== actor || !c.session.canAction(task.action)) {
     result.failures.push({reportNo, reason: '会话或权限已变化，未提交'})
     batchProgress.value.done++
     continue
    }
    try {
     await complete(reportNo, task.action)
     completed.add(reportNo)
     result.succeeded++
    } catch (error) {
     const issue = platformError(error)
     const reason = ['NETWORK', 'UNAVAILABLE', 'INTERNAL'].includes(issue.code)
      ? '未能确认办理结果，请以刷新后的状态为准'
      : issue.message
     result.failures.push({reportNo, reason})
    }
    batchProgress.value.done++
   }
   batchResult.value = result
   if (c.pageKey === stage && c.session.account === actor) {
    m.selected = m.selected.filter((reportNo: string) => !completed.has(reportNo))
    await c.refreshReportList()
   }
  } finally {
   batchProgress.value = {done: 0, total: 0}
   batchBusy.value = false
  }
 }
 Object.assign(m,{
 canBatch,batchBusy,batchProgress,batchCount:computed(()=>batchCandidates.value.length),
 batchLabel:computed(()=>operation.value?.label),
 batchResult:computed(()=>{
  const result = batchResult.value
  return result && result.stage === c.pageKey && result.account === c.session.account ? result : undefined
 }),completeSelected,
 issuanceExportBusy:false,issuanceExportError:'',
 exportIssuanceRecord:async(kind:'product'|'engineering')=>{
  if(c.pageKey!=='release'||m.issuanceExportBusy||!m.selected.length)return
  const numbers=[...m.selected];m.issuanceExportBusy=true;m.issuanceExportError=''
  try{await downloadIssuanceRecord(numbers,kind)}catch(e){m.issuanceExportError=e}
  finally{m.issuanceExportBusy=false}
 },
 toolbarActions:[],toolbarAction:()=>{},
 prefix:computed(()=>`platform-report-${c.pageKey}`),archive:computed(()=>c.pageKey==='archive'),distribution:computed(()=>c.pageKey==='release'),signing:false,busy:batchBusy,
 metadata:computed(()=>m.reportCheckColumns),states:computed(()=>m.reportCheckStates),statuses:computed(()=>c.pageKey==='archive'?handlingStates(c.pageKey):c.pageKey==='release'?['未发放','已发放']:['未签发','已签发']),reportArchiveStatusLabels:computed(()=>Object.fromEntries(handlingStates(c.pageKey).map(s=>[s,s]))),reportDistributionStatusLabels:{未发放:'未发放',已发放:'已发放'},dateFields:computed(()=>m.reportCheckDateFields),reportCollectionMethods:['自取','邮寄','其他'],
 searchFields:computed(()=>m.reportCheckSearchFields),reportQueryColumns:computed(()=>m.reportCheckColumns),reportQueryStates:computed(()=>m.reportCheckStates),reportQuerySearchFields:computed(()=>m.reportCheckSearchFields),reportQueryDateFields:computed(()=>m.reportCheckDateFields),
 reportOperationIcons:{preview:'ti ti-eye',workflow:'ti ti-circle-check'},reportQueryActions:[{id:'preview',label:'查看',icon:'ti ti-eye'}],actionAllowed:()=>true,
 emit:(_name:string,row:Row,id:string)=>{if(row.actions.some((a:Row)=>a.id===id&&a.enabled))c.openForm(row.source,id==='preview')},
 });return m as any}
