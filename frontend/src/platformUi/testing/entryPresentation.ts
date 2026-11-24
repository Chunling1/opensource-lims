import { onBeforeRouteLeave, onBeforeRouteUpdate, useRouter, type RouteLocationNormalized } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUnsavedChanges } from '../../components/common/useUnsavedChanges'
import {sortableBusinessColumns} from '../listSorting'
import {reportGroupChoices,matchesReportGroup} from '../reportGroups'
import {handlingDefault,handlingStates,handlingQuery} from '../handlingStatus'
import { useLiveSearch } from '@/composables/liveSearch'
import { reportDataStatus, reportDataStatusChoices } from '../reportDataStatus'
import { fetchReportEquipment } from '@/services/quality'
import { toRef } from 'vue'
import { fetchAuthorizedReportPeople } from '@/services/pipeline'
import { persistTableSettings } from '../../services/platform/tablePreferences'
import {planMatches} from '../lists/planCatalogue'
import { computed, reactive, ref, provide, watch, onBeforeUnmount } from 'vue'
import { artifactObjectUrl } from '@/services/reportAssurance'
import { reportPreviewError } from '../apiErrors'
import { AppError } from '../../services/common/errors'
import recordKeys from './EntryRecordPresentation.keys.json'
import listKeys from './EntryListPresentation.keys.json'
import { emptySampleDetails } from '../../types/commissions/sampleForm'
import { emptySampleCommission } from '../../types/commissions/sampleCommission'
import { sampleFormTabs } from '../../views/commissions/forms/sampleSchema'
import { dataEntryColumns as baseDataEntryColumns, dataEntryActions } from '../../types/testing/dataEntry'
import { emptyTrialForm } from '../../types/testing/dataEntryDetail'
import { completeReportObjectUrl, confirmCompleteReportPreview, attachmentObjectUrl, listUploadedAttachments } from '@/services/attachments'
import { downloadBlob } from '../../services/reports/reportPdf'
import { runReportUpload } from '../reportAttachments'
import { entryEquipment } from './entryEquipment'

// This boundary maps values/events only. The views and all visual structure are
// byte-derived from the supplied demo and verified separately by componentLayout.
export function createEntryPresentation(c: any) {
 const router=useRouter()
 let active=true
 const context=(keys:string[],values:any)=>reactive(Object.assign(Object.fromEntries(keys.map(key=>[key,undefined])),values))
 const reportOnly=ref(false), tab=ref('trial'), reportTab=ref('template'), pdfUrl=ref(''), previewBusy=ref(false), error=ref<any>(''), confirmed=ref(false)
 const statusAction=ref<any>(), statusBusy=ref(false), completingFromList=ref(false)
 const previewReceipt=ref('')
 const previewSaving=ref(false), confirming=ref(false)
 const navigationBusy=computed(()=>c.saving||c.uploading||c.compositionSaving||c.attachmentDeleting||c.returnBusy||previewSaving.value||c.preparationLoading||statusBusy.value)
 const working=computed(()=>navigationBusy.value||previewBusy.value)
 const saved=ref(''),signature=()=>JSON.stringify(c.t),dirty=computed(()=>!!saved.value&&saved.value!==signature())
 async function save(validate=false){if(c.formReadOnly||working.value)return false;const ok=await c.persistTestInfo(validate);if(ok)saved.value=signature();return ok}
 watch(()=>c.preparationLoading,loading=>{if(!loading&&!c.preparationError)saved.value=signature()})
 // Compare source values, not a new array identity on each status poll.
 watch([signature,()=>c.previewState.sourceHash,()=>JSON.stringify(c.uploaded),()=>JSON.stringify(c.documentContent?.compositionOptions)],()=>{confirmed.value=false;previewReceipt.value='';if(pdfUrl.value){URL.revokeObjectURL(pdfUrl.value);pdfUrl.value=''}},{flush:'sync'})
 const field=(key:string,label:string,control='text',options?:any[])=>({id:'platform-trial-'+key,label,control,options,binding:{get:()=>c.t[key],set:(_:any,v:any)=>{if(!c.formReadOnly)c.t[key]=v}}})
 const extraSections=computed(()=>[
  {id:'platform-trial-supplement',title:'报告信息',fields:[field('recordNo','原始记录编号'),field('result','检测结果','textarea'),
   {id:'platform-standard-display',label:'检测依据显示',control:'custom',slot:'standard-display',width:'col-12'},
   {id:'platform-judgment-display',label:'判定依据显示',control:'custom',slot:'judgment-display',width:'col-12'},
   {id:'platform-report-language',label:'报告语言',control:'select',options:[{value:'CN',label:'中文'},{value:'EN',label:'英文'}],disabled:()=>c.isCalibrationReport,binding:{get:()=>c.documentContent?.compositionOptions?.reportLanguage||'CN',set:(_:any,v:any)=>c.saveDocumentOption('reportLanguage',v)}},
   {id:'platform-no-supplement',label:'无需补充正文，使用平台模板生成报告',control:'checkbox',visible:!!c.documentPreflight?.noSupplementSupported&&!c.documentContent?.compositionOptions?.preserveUploadedReport,disabled:c.completedReportAttachments.length>0||c.reportPageAttachments.length>0,binding:{get:()=>!!c.documentPreflight?.noSupplementBody,set:(_:any,v:any)=>c.confirmNoSupplement(v)}},
  ]},
  {id:'platform-included-files',title:'并入正式报告的附件',visible:c.orderedOtherAttachments.length>0,fields:c.orderedOtherAttachments.map((f:any)=>({id:'platform-include-'+f.id,label:f.name,control:'checkbox',disabled:!f.mergeEligible,binding:{get:()=>c.isOtherIncluded(f),set:(_:any,v:any)=>c.toggleOtherAttachment(f,v)}}))},
 ])
 provide('platform-entry-presentation',reactive({conclusions:[{value:'判定合格',label:'合格'},{value:'判定不合格',label:'不合格'},{value:'不判定',label:'不判定'}],extraSections,hasCompleteIntervals:computed(()=>c.t.testIntervals.length>0&&c.t.testIntervals.every((r:any)=>r.start&&r.end)),fileDisposition:(f:any)=>f.kind==='report'?'完整报告（当前有效，必并入）':c.includedOtherAttachmentIds.includes(Number(f.id))?'附加文件（已选入正式报告）':'附加文件（未选入正式报告）',
  judgmentSource:computed(()=>c.detail?.rawSample?.judgmentEntries ?? c.detail?.rawSample?.standardJudge ?? (c.detail?.summary||[]).filter((s:any)=>s.title==='实验信息').flatMap((s:any)=>s.fields||[]).find((f:any)=>['判定依据','判定标准','标准/判定'].includes(f[0]))?.[1] ?? ''),textSettings:c.t,standardOptions:computed(()=>c.standardOptions||[]),standardLoading:computed(()=>!!c.standardLoading),reportLanguage:computed(()=>c.documentContent?.compositionOptions?.reportLanguage||'CN'),isCalibrationReport:computed(()=>c.isCalibrationReport),reportEquipment:computed(()=>c.equipment||[]),
  environmentFields:[field('calibrationPlace','试验／校准地点'),field('temperature','温度'),field('humidity','湿度'),field('pressure','压力')]}))
 // Invalidate verdicts immediately whenever report or intervals change. Only
 // the latest response may repopulate them; no local duplicate date rules.
 let equipmentEpoch=0, peopleEpoch=0
 async function refreshEquipment(){
  const epoch=++equipmentEpoch, number=c.selected?.reportNo, dates=JSON.stringify(c.t.testIntervals)
  if(c.formReadOnly||!c.formOpen||!number||!['检测录入中','退回待重传','检测更改中'].includes(c.selected.status))return
  c.equipment=c.equipment.map((item:any)=>({...item,eligibility:undefined}))
  const result=await fetchReportEquipment(number,JSON.parse(dates))
  if(!active||epoch!==equipmentEpoch||c.selected?.reportNo!==number||!c.formOpen||c.formReadOnly||JSON.stringify(c.t.testIntervals)!==dates)throw Error('报告或试验日期已变化，请重新打开仪器选择')
  c.equipment=result.rows
 }
 async function refreshPeople(){
  const epoch=++peopleEpoch, number=c.selected?.reportNo
  if(c.formReadOnly||!c.formOpen||!number||!['检测录入中','退回待重传','检测更改中'].includes(c.selected.status))return
  const result=await fetchAuthorizedReportPeople(number)
  if(!active||epoch!==peopleEpoch||c.selected?.reportNo!==number||!c.formOpen||c.formReadOnly)throw Error('报告已切换，请重新选择人员')
  c.authorizedPeople=result
 }
 watch(()=>JSON.stringify([c.selected?.reportNo,c.t.testIntervals,c.formReadOnly,c.formOpen]),()=>{
  void refreshEquipment().catch(()=>{})
 },{immediate:true,flush:'sync'})
 onBeforeUnmount(()=>{equipmentEpoch++;peopleEpoch++})
 const direct:Record<string,string>={conclusion:'conclusion',conclusionStatus:'resultStatus',failedParameters:'unqualifiedParams',notes:'remark',tester1Id:'primaryTester1Code',tester2Id:'primaryTester2Code',reviewerId:'reviewerCode',approverId:'approverCode',calibrationDate:'calibrationTime'}
 const flags:Record<string,string>={showEquipmentCode:'archiveNo',showEquipmentModel:'spec',showEquipmentManufacturer:'maker',showEquipmentSerial:'factoryNo'}
 const dates=computed(()=>c.t.testIntervals.map((row:any)=>reactive({kind:'range',get from(){return row.start},set from(v){if(!c.formReadOnly)row.start=v},get to(){return row.end},set to(v){if(!c.formReadOnly)row.end=v}})))
 const form=reactive(new Proxy(emptyTrialForm(),{
  get(target,key:string){if(direct[key])return c.t[direct[key]];if(flags[key])return c.t.equipmentDisplay[flags[key]];if(key==='testDates')return dates.value;if(key==='equipmentIds')return c.t.equipmentIds.map(String);if(key==='calibrationEnabled')return c.isCalibrationReport;return (target as any)[key]},
  set(target,key:string,value){if(c.formReadOnly)return true;if(direct[key])c.t[direct[key]]=value;else if(flags[key])c.t.equipmentDisplay[flags[key]]=value;else if(key==='testDates')c.t.testIntervals=value.map((r:any)=>({start:r.from,end:r.to}));else if(key==='equipmentIds')c.t.equipmentIds=value.map(Number);else if(key!=='calibrationEnabled')(target as any)[key]=value;return true}
 }))
 const sample=computed(()=>{
  const row=c.selected||{},raw=c.detail?.rawSample||{},snap=c.detail?.entrustSnapshot||{},info=snap.info||{}
  const text=(value:any)=>value==null?'':String(value)
  const mapText=(source:any,mapping:Record<string,string>)=>Object.fromEntries(Object.entries(mapping).map(([target,key])=>[target,text(source[key])]))
  const commissionInfo={...emptySampleCommission(),...mapText(info,{invoiceType:'invoiceType',taxpayerNumber:'taxNo',invoiceCompany:'companyName',invoiceAddress:'bizAddr',bankName:'bank',bankAccount:'account',contractParty:'contractPartyA',payer:'otherPartyA',customerAddress:'clientAddr',customerLegalRepresentative:'clientLegal',customerPhone:'clientPhone',customerPostcode:'clientZip',projectRegistrationCode:'projectRecordNo',projectTradingCode:'projectTradeCode',projectAddress:'projectAddr',handlerPhone:'handlerPhone'}),code:row.entrustNo||snap.entrustNo||'',owner:info.handler||snap.owner||'',name:snap.projectName||row.project||'',customer:snap.client||row.client||'',contract:snap.contractNo||'',contact:info.consignor||row.consignor||'',phone:info.consignorPhone||row.consignorPhone||'',handlingDepartmentId:info.handleDept||snap.department||'',commissionDate:info.entrustDate||'',erpContract:info.erpProjectNo||row.erpProjectNo||'',erpProjectType:info.erpType||row.erpProjectType||''}
  const settings={formatId:text(raw.reportType||row.reportFormat),titleId:text(raw.reportTitle||row.reportTitle),languageId:text(c.documentContent?.compositionOptions?.reportLanguage||raw.reportLanguage||'CN'),layoutId:text(c.documentContent?.compositionOptions?.reportTemplateVariant||raw.reportTemplateVariant)}
  const details={...emptySampleDetails(),...mapText(raw,{manufacturer:'manufacturer',specification:'spec',trademark:'trademark',productionDate:'produceDate',deliveryDate:'sendDate',appearance:'appearance',nameplate:'nameplate',productCode:'factoryNo',testingLocation:'testLocation',internalNotes:'innerRemark',samplingOrganization:'sampleUnit',samplingLocation:'samplingLocation',sampler:'sampler',samplingTime:'sampleTime',samplingQuantity:'sampleQty',samplingBase:'entrustQty',inspectedOrganization:'inspectedUnit',taskSource:'taskSource',standardPrice:'stdPrice',paymentMethod:'payWay',paymentStatus:'payStatus',paidAmount:'paid',feeNotes:'otherSettle',externalDueDate:'sendOutTime',internalDueDate:'sendInTime',disposalMethod:'sampleHandle',reportDelivery:'deliverWay',mailingAddress:'mailAddr',reportCopies:'deliverStd',reportForm:'reportForm',onsiteArrangement:'fieldAgreement',appointmentDate:'innerStdDate',assessmentStandard:'standardJudge'}),testPlan:raw.schemeName||row.schemeName||'',testBasis:c.t.standards.join('；'),testingDepartment:raw.testDept||row.department||'',requestedTestDate:/^\d{4}-\d{2}-\d{2}/.test(row.deadline||'')?row.deadline:'',urgent:raw.urgent==='是',hasExternalDueDate:!!raw.sendOutTime,hasInternalDueDate:!!raw.sendInTime,hasAppointment:!!raw.innerStdDate,useAssessmentStandard:!!raw.standardJudge,reportSettings:settings,
   subprojects:(raw.subItems||[]).map((item:any,index:number)=>({id:String(index),name:text(item.projectName),accountingDepartment:text(item.dept),businessCategory:text(item.businessCategory),amount:text(item.amount),receivedAmount:text(item.receivedAmount),receiptType:text(item.receiptType),paymentDescription:text(item.paymentDescription),notes:text(item.remark)}))}
  return {id:row.reportNo||'',code:row.sampleNo||'',reportCode:row.reportNo||'',name:raw.sampleName||row.project||'',customer:row.client||'',owner:row.owner||'',departmentId:row.department||'',contact:commissionInfo.contact,phone:commissionInfo.phone,projects:Array.isArray(raw.projectList)&&raw.projectList.length?raw.projectList:(row.testItems||'').split(/[；;]/).filter(Boolean),quantity:raw.sampleAmount??'',unit:text(raw.unit),category:raw.testCategory||row.testCategory||'',storage:text(raw.storage),notes:text(raw.remark),commissionInfo,details,attachments:[],events:[],assignmentInfo:{dataEntryPerson:c.entryStaffDisplay},version:0}
 })
 const entryDetail=computed(()=>({sample:sample.value,form,version:0,reportRevision:0,layoutId:c.documentContent?.compositionOptions?.reportTemplateVariant||'Standard',layoutAdopted:true,
  layouts:[{id:'Standard',label:'标准版'},...(c.supportsExtendedTemplate?[{id:'Extended',label:'扩展版（长首页／两页）'}]:[])],
  template:{id:c.selected?.template||'',version:c.selected?.version||'',labels:['报告编号：'+(c.selected?.reportNo||''),'报告语言：'+(c.documentContent?.compositionOptions?.reportLanguage||'CN'),'模板：'+(c.documentPreflight?.templateSelection?.filename||c.selected?.template||'')],error:c.preparationError||''},
  options:{people:c.testerOptions.map(person),reviewers:c.reviewerOptions.map(person),approvers:c.approverOptions.map(person),equipment:c.equipment.map((e:any)=>entryEquipment(e,c.t.testIntervals)),maxFileSize:500*1024*1024},
  equipmentConfig:{version:0,associatedIds:c.equipment.map((e:any)=>String(e.id)),defaultIds:[]},
  capabilities:{canView:true,canEdit:!c.formReadOnly,canManageReport:!c.formReadOnly,canManageOriginals:!c.formReadOnly,canComplete:!c.formReadOnly,canUndo:false},
  files:[...c.completedReportAttachments.map((f:any)=>file(f,'report')),...c.orderedOtherAttachments.map((f:any)=>file(f,'appendix'))],
  reportStatus:pdfUrl.value?'ready':c.formReadOnly?'pending':c.previewReady?'ready':c.previewState.status==='failed'?'failed':previewBusy.value||['queued','running'].includes(c.previewState.status)?'running':'pending',
  job:!c.formReadOnly&&['queued','running','ready','failed'].includes(c.previewState.status)?{id:c.previewState.sourceHash||'',elapsedMs:0,status:c.previewState.status==='queued'?'running':c.previewState.status,phase:c.previewState.status,error:c.previewState.status==='failed'?c.previewState.message:undefined}:undefined,
  reportConfirmed:confirmed.value,templateStale:false,completeReportStale:false,completeReportGeneration:{layoutIds:[],unavailableReason:'现平台提供完整 Word 编写模板，请使用“下载模板”；正式报告以后台生成的 PDF 为准。'},
 }))
 function person(p:any){return {id:p.code,name:p.name,departmentId:'',departmentName:p.department||c.currentDepartment,certificateNumber:'',phone:'',position:p.position||'',jobTitle:p.title||''}}
 function file(f:any,kind:string){return {id:String(f.id),name:f.name,type:f.contentType||'application/octet-stream',size:f.sizeBytes||0,kind}}
 function people(role:string){return (role==='tester'?c.testerOptions:role==='reviewer'?c.reviewerOptions:c.approverOptions).map(person)}
 async function blobFor(f:any){const res=await attachmentObjectUrl(f,c.reportDetailView);try{return await (await fetch(res.url)).blob()}finally{if(res.url.startsWith('blob:'))URL.revokeObjectURL(res.url)}}
 async function reloadFiles(){const number=c.selected?.reportNo,view=c.reportDetailView;const rows=await listUploadedAttachments(number,view);if(!active||c.selected?.reportNo!==number||c.reportDetailView!==view)throw Error('报告已切换，请在当前报告重新操作');c.uploaded=rows}
 function uploadFile(f:unknown):File{if(!(f instanceof File))throw Error('请选择本地文件重新上传');return f}
 async function originals(){await c.loadElnStatus();await reloadFiles();return {version:Date.now(),sampleVersion:0,sampleCode:c.selected?.sampleNo||'',maxFileSize:500*1024*1024,capabilities:{canUpload:!c.formReadOnly&&c.session.canAction('report.attachment.upload'),canLink:!c.formReadOnly&&c.elnStatus.canLaunch,canDelete:!c.formReadOnly},records:[...c.rawRecordAttachments.map((f:any)=>({id:String(f.id),name:f.name,source:'file',files:[file(f,'original')],status:f.status||'',capabilities:{canUpload:false,canDelete:c.canRemoveAttachment(f),canLink:false}})),...c.elnStatus.records.map((r:any)=>({id:r.id,name:r.template.name,source:'eln',files:[],status:c.elnStatusText(r.status),eln:{version:r.template.version,recordId:r.id},capabilities:{canUpload:false,canDelete:false,canLink:!c.formReadOnly&&r.status==='FINALIZED'}}))]}}
 const services={
  entrySchemeEquipment(rows:any[],skipped:any[]){
   if(c.formReadOnly)return
   const map=new Map(c.equipment.map((row:any)=>[row.id,row]));rows.forEach(row=>map.set(row.id,row));skipped.forEach(row=>{const item=map.get(Number(row.id)) as any;if(item)map.set(Number(row.id),{...item,eligibility:{selectable:false,level:"block",message:row.reason}})});c.equipment=[...map.values()]
  },
  reportWorkflowRecords:!!c.loadEntryRecords,
  async entryPeople(_id:string,q:any){await refreshPeople();const rows=people(q.role).filter((p:any)=>p.id!==q.excludeId&&(!q.keyword||(p.name+p.id).includes(q.keyword)));return {items:rows.slice((q.page-1)*q.pageSize,q.page*q.pageSize),total:rows.length,page:q.page,pageSize:q.pageSize,scope:q.scope||'preset',presetConfigured:true,departmentName:c.currentDepartment}},
  async entryPerson(_id:string,q:any){await refreshPeople();const found=people(q.role).find((p:any)=>p.id===q.id&&p.id!==q.excludeId);if(!found)throw Error('该人员不在本项目当前授权范围内，请刷新人员后重选');return found},
  async entryDetail(){await refreshEquipment();return entryDetail.value},
  async entryAction(){throw Error('现平台不支持在检测录入中修改方案默认设备，请在方案管理中配置')},
  originals,
  launchEln:()=>{if(!c.formReadOnly&&c.elnStatus.canLaunch)return c.launchEln()},importEln:()=>{if(!c.formReadOnly&&c.elnFinalizedCount)return c.prepareElnDraft()},
  async originalAction(_id:string,action:string,p:any){if(c.formReadOnly)throw Error('当前为只读状态');if(action==='upload')await runReportUpload(uploadFile(p.file),c.uploadRawRecord);else if(action==='remove'){for(const id of p.ids){const f=c.rawRecordAttachments.find((f:any)=>String(f.id)===id);if(f)await c.removeUploadedAttachment(f)}}else throw Error('现平台不支持此原始记录操作');return originals()},
  async entryDownload(_id:string,url:string){if(url.includes('/preview?')){const files=c.rawRecordAttachments.filter((f:any)=>f.name.toLowerCase().endsWith('.pdf'));if(!files.length)throw Error('当前没有 PDF 原始记录；Word 文件可在上传记录中下载查看');if(files.length!==c.rawRecordAttachments.length)throw Error('原始记录含 Word 文件，不能生成完整合并预览；请分别下载查看');const {PDFDocument}=await import('pdf-lib');const merged=await PDFDocument.create();for(const f of files){const src=await PDFDocument.load(await (await blobFor(f)).arrayBuffer());for(const page of await merged.copyPages(src,src.getPageIndices()))merged.addPage(page)}return new Blob([new Uint8Array(await merged.save())],{type:'application/pdf'})}const id=decodeURIComponent(url.split('/').at(-1)!);const f=c.uploaded.find((f:any)=>String(f.id)===id);if(!f)throw Error('文件已不可访问，请刷新');return blobFor(f)},
  async attachments(){await reloadFiles();return {...sample.value,canManageAttachments:!c.formReadOnly&&c.session.canAction('report.attachment.upload'),attachments:c.uploaded.map((f:any)=>({...file(f,'appendix'),dataUrl:''}))}},
  async attachSample(_id:string,_version:number,f:any){await runReportUpload(uploadFile(f),c.uploadOtherAttachment);return services.attachments()},
  async deleteSampleAttachment(_id:string,_version:number,id:string){const f=c.uploaded.find((f:any)=>String(f.id)===id);if(!f)throw Error('文件不存在');await c.removeUploadedAttachment(f);return services.attachments()},
  async downloadAttachment(f:any){const source=c.uploaded.find((row:any)=>String(row.id)===f.id);if(!source)throw Error('文件不存在');downloadBlob(await blobFor(source),source.name)},
  async entryRecords(id:string,query:any,signal:AbortSignal){if(c.loadEntryRecords)return c.loadEntryRecords(id,query,signal);throw Error('现平台未提供此独立记录查询接口，请从委托更改或报告查询查看流程记录')},
 }
 provide('platform-entry-services',services)
 const previewEpoch=ref(0)
 // refreshPreview resolves after the first poll, not after PDF generation.
 // Keep this request attached to the form while the controller owns polling.
 function waitForPreview(current:()=>boolean){
  return new Promise<boolean>((resolve,reject)=>{
   const stop=watch(()=>[current(),c.previewReady,c.previewState.status],check,{flush:'sync'})
   function check(){
    if(!current()){stop();resolve(false)}
    else if(c.previewReady){stop();resolve(true)}
    else if(c.previewState.status==='failed'||c.previewState.status==='missing'){
     stop();reject(new AppError('BUSINESS_RULE',c.previewState.message||'报告预览未就绪，请核对上传文件后重试'))
    }
   }
   check()
  })
 }
 const preview=async(resume=false)=>{
  if(working.value||pdfUrl.value)return
  const no=c.selected?.reportNo, view=c.reportDetailView, token=++previewEpoch.value
  if(!no)return
  const retryFailed=c.previewState.status==='failed', readonly=c.formReadOnly
  const sourceSignature=signature(), fileSignature=JSON.stringify([c.uploaded,c.documentContent?.compositionOptions])
  previewBusy.value=true;previewSaving.value=!readonly&&!resume;error.value=''
  const current=()=>active&&token===previewEpoch.value&&c.formOpen&&c.selected?.reportNo===no&&c.reportDetailView===view&&c.formReadOnly===readonly&&signature()===sourceSignature&&JSON.stringify([c.uploaded,c.documentContent?.compositionOptions])===fileSignature
  try{
   let url:string
   if(readonly)url=await artifactObjectUrl(no,view)
   else {
    // Own the busy flag before saving so repeated clicks cannot save twice.
    if(!resume&&!(await c.persistTestInfo(true))||!current())return
    saved.value=sourceSignature
    previewSaving.value=false
    if(!resume)await c.refreshPreview(retryFailed)
    if(!current())return
    if(!(await waitForPreview(current)))return
    const sourceHash=c.previewState.sourceHash
    const loaded=await completeReportObjectUrl(no,view)
    url=loaded.url
    if(!c.previewReady||c.previewState.sourceHash!==sourceHash){URL.revokeObjectURL(url);if(current())throw new AppError('BUSINESS_RULE','报告内容已变化，请重新生成预览');return}
    if(current())previewReceipt.value=loaded.receipt||''
   }
   if(!current()){URL.revokeObjectURL(url);return}
   pdfUrl.value=url
  }catch(e){if(current())error.value=reportPreviewError(e)}finally{if(token===previewEpoch.value){previewBusy.value=false;previewSaving.value=false}}
 }
 async function downloadFile(id:string,name?:string){const f=c.uploaded.find((f:any)=>String(f.id)===id);if(f)downloadBlob(await blobFor(f),name||f.name)}
 const layoutId=computed({get:()=>entryDetail.value.layoutId,set:v=>{void c.saveDocumentOption('reportTemplateVariant',v)}})
 const record=context(recordKeys,{reportOnly,tab,reportTab,loading:computed(()=>c.preparationLoading),detail:computed(()=>c.preparationLoading||!c.detail?undefined:entryDetail.value),form,sampleForm:sample,sampleOptions:{subprojectOptions:[],choices:{}},tabs:[...sampleFormTabs,{key:'trial',label:'试验信息',tabId:'entry-tab-0',panelId:'entry-panel-0'},{key:'original',label:'原始记录',tabId:'entry-tab-1',panelId:'entry-panel-1'}],
  canAdminEdit:computed(()=>!!c.canAdminEdit),adminEditing:computed(()=>!!c.adminEditing),
  canPreserveUploadedReport:computed(()=>c.session.roleKey==='admin'||c.session.account==='admin'),
  preserveUploadedReport:computed(()=>c.documentContent?.compositionOptions?.preserveUploadedReport===true),
  preserveOptionUnavailable:computed(()=>!c.documentContent),
  togglePreserveUploadedReport:async()=>{
   if(!(c.session.roleKey==='admin'||c.session.account==='admin')||c.formReadOnly||working.value||!c.documentContent)return
   if(dirty.value){error.value={code:'BUSINESS_RULE',message:'请先保存检测数据，再切换完整报告保留方式。'};return}
   await c.saveDocumentOption('preserveUploadedReport',c.documentContent.compositionOptions?.preserveUploadedReport!==true)
  },
  toggleAdminEditing:()=>{
   if(working.value||record.originalBusy||!c.canAdminEdit)return
   if(dirty.value){error.value={code:'BUSINESS_RULE',message:'请先保存当前修改，或返回列表放弃修改，再切换编辑模式。'};return}
   error.value='';c.toggleAdminEditing()
  },
  navigationBusy,confirming,working,originalBusy:false,error:computed(()=>error.value||(c.preparationError?{code:'UNAVAILABLE',message:c.preparationError}:'')),stale:false,readonlyMode:computed(()=>c.formReadOnly),editable:computed(()=>!c.formReadOnly),dirty,checkMode:false,checkOpen:false,recipientPicking:false,reportCheckMode:false,queryMode:false,reportQueryMode:false,previewLayout:false,changeMode:computed(()=>c.isChangePage),
  fieldErrors:{},peopleScopes:{},reportConfig:computed(()=>{const value=sample.value.details.reportSettings;return {version:'platform-readonly',options:Object.fromEntries(Object.entries(value).map(([key,id])=>[key,id?[{id,label:key==='languageId'?({CN:'中文',EN:'英文'}[id]||id):id}]:[]])),defaults:value,combinations:[value]}}),reportConfigLoading:false,reportConfigError:'',returnTo:computed(()=>c.route.path),layoutId,pdfUrl,previewName:computed(()=>(c.selected?.reportNo||'report')+'.pdf'),uploadStatus:{leaveAttempted:{value:false}},reportConfirmed:confirmed,
  canConfirmReport:computed(()=>!c.formReadOnly&&!working.value&&!dirty.value&&c.previewReady&&!!pdfUrl.value),
  canCompleteChange:computed(()=>!!c.isChangeRound&&!c.formReadOnly&&!c.adminEditing),
  completeChange:async()=>{
   if(!active||!c.formOpen||!c.isChangeRound||c.formReadOnly||c.adminEditing||working.value||record.originalBusy)return false
   statusBusy.value=true;error.value=''
   try{
    if(await c.completeChange()!==false)return true
    if(!c.completionFeedback)throw Error('更改尚未提交，请按提示补全或修正检测数据后重试。')
    return false
   }catch(e){error.value={code:'BUSINESS_RULE',message:e instanceof Error?e.message:String(e)};return false}
   finally{statusBusy.value=false}
  },
  load:c.refreshLinkedData,save:()=>save(),selectTab:(v:string)=>{tab.value=v},selectReportTab:(v:string)=>{reportTab.value=v;if(v==='preview')void preview()},beginReport:(v:string)=>{reportTab.value=v;if(v==='preview')void preview()},openReport:async()=>{if(c.formReadOnly||await save(true)){reportOnly.value=true;reportTab.value='template';window.scrollTo(0,0)}},back:()=>{if(navigationBusy.value||record.originalBusy)return;if(dirty.value){record.discard='list';return}c.formOpen=false;reportOnly.value=false},abandon:()=>{if(navigationBusy.value||record.originalBusy)return;const target=record.discard;record.discard='';c.formOpen=false;reportOnly.value=false;if(target!=='list')void router.push(target)},
  finalPreview:preview,pollProgress:preview,confirmReport:async()=>{
   if(c.formReadOnly||working.value||dirty.value||!c.previewReady||!pdfUrl.value)return
   if(!previewReceipt.value){error.value={code:'BUSINESS_RULE',message:'预览确认凭据缺失，请重新打开最新预览'};return}
   const no=c.selected?.reportNo, proof=previewReceipt.value
   statusBusy.value=true;confirming.value=true;error.value=''
   try{await confirmCompleteReportPreview(no,proof);if(active&&c.formOpen&&c.selected?.reportNo===no&&previewReceipt.value===proof&&!dirty.value){confirmed.value=true;reportTab.value='complete'}}
   catch(e){error.value=reportPreviewError(e);confirmed.value=false}
   finally{statusBusy.value=false;confirming.value=false}
  },
  templateDownload:c.downloadAuthoringTemplate,changeReportLayout:(v:string)=>{layoutId.value=v},
  uploadReportFile:async(kind:string,f:File)=>runReportUpload(f,kind==='report'?c.uploadCompletedReport:kind==='original'?c.uploadRawRecord:c.uploadOtherAttachment),
  remove:(f:any)=>c.removeUploadedAttachment(c.uploaded.find((a:any)=>String(a.id)===f.id)),
  download:(path:string,name:string)=>downloadFile(decodeURIComponent(path.split('/').at(-1)!),name),
  action:async(action:string,payload:any)=>{if(action==='sort')await c.persistIncludedOtherAttachments(payload.ids.map(Number).filter((id:number)=>c.includedOtherAttachmentIds.includes(id)))},
  attachmentOpen:false,recordsMode:undefined,discard:'',success:'',checkError:'',completionError:'',progressError:'',loadReportConfig:()=>{},syncAttachments:()=>{},apply:()=>{},
 })
 function leave(to:RouteLocationNormalized){
  if(!c.formOpen)return true
  if(navigationBusy.value||record.originalBusy)return false
  if(dirty.value){record.discard=to.fullPath;return false}
  return true
 }
 onBeforeRouteLeave(leave)
 onBeforeRouteUpdate(leave)
 useUnsavedChanges(computed(()=>c.formOpen&&(dirty.value||navigationBusy.value||record.originalBusy)))
 const draft=reactive({reportGroup:'',searchField:c.route?.query?.keyword?'reportCode':'code',contains:String(c.route?.query?.keyword||''),status:c.serverPaging?handlingDefault(c.isChangePage?'data_change':'data_entry'):'',sampleType:'',conclusion:'',dateField:'commissionDate',from:'',to:''}), applied=ref({...draft}),selected=ref<string[]>([]),page=ref(1),size=ref(10),columns=ref<string[]>(dataEntryColumns.filter(col=>!('default' in col)||col.default).map(col=>col.key))
 const sortOrder=reactive({sort:'code',direction:'asc'}),selectedPlans=ref<any>({groupIds:[],planIds:[],excludedPlanIds:[]}),appliedPlans=ref<any>({groupIds:[],planIds:[],excludedPlanIds:[]})
 persistTableSettings(()=> 'testing-entry',{columns,pageSize:size,sort:toRef(sortOrder,'sort'),direction:toRef(sortOrder,'direction')});
 const mappedRows=(source:any[])=>source.map((r:any)=>({...r,id:r.reportNo,code:r.sampleNo,reportCode:r.reportNo,
  name:r.sampleOrProjectName||r.projectName||'',engineeringName:r.projectName||'',projectName:r.schemeName||'',
  customer:r.client,parameters:r.testItems||'',sampleType:r.reportCategory||'',dataStatus:reportDataStatus(r),requestedTestDate:/^\d{4}-\d{2}-\d{2}/.test(r.deadline||'')?r.deadline:'',commissionCode:r.entrustNo||'',commissionDate:r.sampleRegisteredAt||'',dataEntryPerson:r.owner||''}))
 const rows=computed(()=>c.serverPaging?mappedRows(c.entryRows):mappedRows(c.entryRows).filter((r:any)=>{const q=applied.value;return matchesReportGroup(r,q.reportGroup)&&planMatches(r,appliedPlans.value)&&(!q.contains||String(r[q.searchField]||'').toLowerCase().includes(q.contains.toLowerCase()))&&(!q.status||r.dataStatus===q.status)&&(!q.sampleType||r.sampleType===q.sampleType)&&(!q.from||String(r[q.dateField]||'')>=q.from)&&(!q.to||String(r[q.dateField]||'').slice(0,10)<=q.to)}).sort((a:any,b:any)=>String(a[sortOrder.sort]||'').localeCompare(String(b[sortOrder.sort]||''),'zh-CN',{numeric:true})*(sortOrder.direction==='desc'?-1:1)))
 function open(row:any,readonly=false,report=false){c.onListSelection([row]);c.openSelectedForm(readonly);reportOnly.value=report;tab.value='trial';reportTab.value='template';window.scrollTo(0,0)}
 async function hydrated(){await c.nextTick();if(c.preparationLoading)await new Promise<void>((resolve,reject)=>{const timer=setTimeout(()=>{stop();reject(Error('报告资料仍在加载，请稍后重试'))},30000);const stop=watch(()=>c.preparationLoading,(busy:boolean)=>{if(!busy){clearTimeout(timer);stop();resolve()}})});if(c.preparationError)throw Error(c.preparationError)}
 function allowed(r:any,label:string){if(completingFromList.value||c.saving)return false;if(label==='查看数据'||label==='报告填写'||label==='附件管理')return true;if(label==='撤销完成')return r.status==='待审核'&&r.allowedActions?.includes('report.report_check.undo');if(label==='退回')return c.canReturnReport(r);if(label==='作废')return false;if(label==='录入完成')return ['检测录入中','检测更改中'].includes(r.status);return c.session.canCorrectBusinessData||r.status!=='待审核'}
 const list=context(listKeys,{reportGroupOptions:computed(()=>reportGroupChoices(c.session)),title:computed(()=>c.pageName),rows:computed(()=>({items:c.serverPaging?rows.value:rows.value.slice((page.value-1)*size.value,page.value*size.value),total:c.serverPaging?c.entryPage.total:rows.value.length,page:page.value,pageSize:size.value})),draft,selected,loading:computed(()=>c.entryListState?.loading||false),error:computed(()=>c.entryListState?.error||''),planBusy:false,exporting:false,more:false,activeFilters:computed(()=>Number(!!draft.from||!!draft.to)),
  dataEntryColumns:dataEntryColumns.map(col=>col.key==='sampleType'?{...col,label:'报告类别'}:col),columns:computed(()=>dataEntryColumns.filter(col=>columns.value.includes(col.key)).map(col=>col.key==='sampleType'?{...col,label:'报告类别'}:col)),columnKeys:columns,dataEntryActions:[...dataEntryActions,{label:'刷新关联资料',icon:'ti ti-refresh'},{label:'重新生成表单',icon:'ti ti-rotate'},{label:'编辑报告内容',icon:'ti ti-file-pencil'}],dataEntryStates:computed(()=>c.serverPaging?handlingStates(c.isChangePage?'data_change':'data_entry'):reportDataStatusChoices(c.entryRows)),sampleTypes:['普通','英文','分项','补充'],
  dataEntrySearchFields:[{value:'all',label:'全部'},{value:'code',label:'样品编号'},{value:'reportCode',label:'报告编号'},{value:'commissionCode',label:'委托编号'},{value:'customer',label:'委托单位'},{value:'name',label:'样品/工程名称'},{value:'engineeringName',label:'项目名称'},{value:'dataEntryPerson',label:'数据录入人'}],assignmentConclusions:[],dataEntryDateFields:[{value:'commissionDate',label:'登记日期'},{value:'requestedTestDate',label:'要求试验日期'}],query:sortOrder,
  search:()=>{liveSearch.cancel();applied.value={...draft};appliedPlans.value=JSON.parse(JSON.stringify(selectedPlans.value));page.value=1;selected.value=[]},patch:(v:any)=>{if(v.page)page.value=Number(v.page);if(v.size)size.value=Number(v.size);if(v.columns===undefined&&Object.keys(v).includes('columns'))columns.value=dataEntryColumns.filter(col=>!('default' in col)||col.default).map(col=>col.key);if(v.sort){list.query.sort=v.sort;list.query.direction=v.direction;page.value=1;selected.value=[];}},
  toggleColumn:(key:string)=>{columns.value=columns.value.includes(key)?columns.value.filter(v=>v!==key):[...columns.value,key]},actionAllowed:allowed,
  rowAction:async(r:any,label:string)=>{if(!allowed(r,label))return;if(label==='退回')await c.returnToEntrust(r);else if(label==='撤销完成'||label==='录入完成')statusAction.value={row:r,action:label==='录入完成'?'complete':'undo'};else{open(r,label==='查看数据'||(!c.session.canCorrectBusinessData&&r.status==='待审核'),label==='报告填写');const opening=previewEpoch.value;if(label==='附件管理')record.attachmentOpen=true;try{await hydrated();if(!active||!c.formOpen||opening!==previewEpoch.value)return;if(label==='报告填写'&&!c.formReadOnly)await c.refreshPreview(false);if(!active||!c.formOpen||opening!==previewEpoch.value)return;if(label==='报告填写'&&(c.formReadOnly||['queued','running','ready'].includes(c.previewState.status))){reportTab.value='preview';await preview(true);}if(label==='编辑报告内容')c.openPages();if(label==='刷新关联资料')await c.refreshLinkedData();if(label==='重新生成表单')await c.regenerateForm()}catch(e){error.value={code:'UNAVAILABLE',message:String(e)}}}},
  statusAction,completingFromList,actionBusy:computed(()=>working.value||statusBusy.value),statusError:'',statusValidation:undefined,statusFieldMessages:[],runStatusAction:async()=>{
   const item=statusAction.value;if(!item||statusBusy.value||c.saving||c.uploading||c.compositionSaving||c.attachmentDeleting||c.returnBusy||previewBusy.value)return
   statusBusy.value=true;list.statusError='';error.value=''
   try{
    if(item.action==='undo')await c.undoDataEntryCompletion(item.row)
    else if(item.row.status==='检测录入中'){
     completingFromList.value=true
     statusAction.value=undefined
     try {
      c.onListSelection([item.row])
      c.openSelectedForm(false)
      await hydrated()
      if(!active||!c.formOpen||c.formReadOnly||c.selected?.reportNo!==item.row.reportNo)throw Error('报告已切换，本次完成操作已取消')
      await c.saveAndDone()
     } finally {
      if(c.selected?.reportNo===item.row.reportNo)c.formOpen=false
     }
    }
    else{
     open(item.row);await hydrated()
     if(!active||!c.formOpen||c.formReadOnly||c.selected?.reportNo!==item.row.reportNo)throw Error('报告已切换，本次完成操作已取消')
     const completed=c.isChangeRound?await c.completeChange():await c.saveAndDone()
     if(completed===false&&!c.completionFeedback)throw Error('录入尚未完成，请按提示补全或修正检测数据后重试。')
    }
    statusAction.value=undefined
   }catch(e){const failure={code:'UNAVAILABLE',message:e instanceof Error?e.message:String(e)};if(completingFromList.value)ElMessage.error(failure.message);else{list.statusError=failure;if(c.formOpen){error.value=failure;statusAction.value=undefined}}}
   finally{statusBusy.value=false;completingFromList.value=false}
  },
  exportRows:async(onlySelected=false)=>{
   const exportData=c.serverPaging?mappedRows(await c.exportEntryRows()):rows.value
   const fields=list.columns
   const csvValue=(value:unknown)=>'"'+String(value??'').replaceAll('"','""')+'"'
   const lines=[fields.map((field:any)=>csvValue(field.label)).join(','),
    ...exportData.filter((r:any)=>!onlySelected||selected.value.includes(r.id)).map((r:any)=>fields.map((field:any)=>csvValue(r[field.key])).join(','))]
   downloadBlob(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}),'检测数据录入.csv')
  },
  drawer:false,plans:selectedPlans,applyPlans:(v:any)=>{selectedPlans.value=v.selection;list.planState=v},planState:undefined,planError:'',exportError:'',voidError:'',voidLoading:false,voidRecord:undefined,returnBusy:working,returnError:'',returnTarget:undefined,load:c.load,resetVoid:()=>{},resetReturn:()=>{},syncAttachment:()=>{},
 })
 watch(()=>c.isChangePage,()=>{if(c.serverPaging){draft.status=handlingDefault(c.isChangePage?'data_change':'data_entry');applied.value={...draft};page.value=1;selected.value=[]}},{flush:'sync'})
 watch(()=>JSON.stringify([applied.value,appliedPlans.value,page.value,size.value,sortOrder]),()=>{if(c.serverPaging)c.setEntryQuery({...handlingQuery(applied.value),plans:appliedPlans.value,page:page.value,pageSize:size.value,...sortOrder})},{immediate:true})
 watch([()=>c.selected?.reportNo,()=>c.formOpen,()=>c.reportDetailView,()=>c.session.account,()=>c.route.path],()=>{previewEpoch.value++;previewBusy.value=false;previewSaving.value=false;if(pdfUrl.value)URL.revokeObjectURL(pdfUrl.value);pdfUrl.value='';previewReceipt.value='';confirmed.value=false;error.value=''}, {flush:'sync'})
 onBeforeUnmount(()=>{active=false;previewEpoch.value++;if(pdfUrl.value)URL.revokeObjectURL(pdfUrl.value)})
 const liveSearch = useLiveSearch(() => draft.contains, () => list.search())
 return {record,list}
}

const dataEntryColumns = sortableBusinessColumns([...baseDataEntryColumns,
 {key:'commissionCode',label:'委托编号',default:false},
 {key:'dataSavedAt',label:'检测数据保存操作时间',default:false},
 {key:'dataCompletedAt',label:'检测录入完成操作时间',default:false},
])
