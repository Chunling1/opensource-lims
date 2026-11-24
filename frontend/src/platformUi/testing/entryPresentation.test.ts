import { createRouter, createMemoryHistory, matchedRouteKey, type Router } from 'vue-router'
vi.mock('@/services/pipeline',()=>({fetchAuthorizedReportPeople:vi.fn(async()=>({testers:[{code:'A',name:'Tester'}],reviewers:[{code:'B',name:'Reviewer'}],approvers:[{code:'C',name:'Approver'}]}))}))
import {fetchAuthorizedReportPeople} from '@/services/pipeline'
import {fetchReportEquipment} from '@/services/quality'
vi.mock('@/services/quality',()=>({fetchReportEquipment:vi.fn(()=>new Promise(()=>{}))}))
import {describe,it,expect,vi,afterEach,beforeEach} from 'vitest'
import {defineComponent,reactive,nextTick,inject,computed} from 'vue'
import {mount,shallowMount,flushPromises} from '@vue/test-utils'
vi.mock('@/services/attachments',()=>({confirmCompleteReportPreview:vi.fn(async()=>({})),completePreviewState:vi.fn(),completeReportObjectUrl:vi.fn(),attachmentObjectUrl:vi.fn(),listUploadedAttachments:vi.fn(async()=>[])}))
vi.mock('../../services/reports/reportPdf',()=>({downloadBlob:vi.fn()}))
vi.mock('@/services/reportAssurance',()=>({artifactObjectUrl:vi.fn()}))
import {artifactObjectUrl} from '@/services/reportAssurance'
import {confirmCompleteReportPreview,completePreviewState,completeReportObjectUrl} from '@/services/attachments'
import {useCompletePreview} from '@/composables/useCompletePreview'
import {createEntryPresentation} from './entryPresentation'
import {ElMessage, feedback} from '../controls'
import {ApiError} from '@/services/http'
import {emptyTrialForm} from '../../types/testing/dataEntryDetail'
import {downloadBlob} from '../../services/reports/reportPdf'
import EntryReportFiles from './EntryReportFiles.vue'
import EntryTrialForm from './EntryTrialForm.vue'
import EntryRecordPresentation from './EntryRecordPresentation.vue'
const wrappers:any[]=[]

describe('500 MB native file upload boundary',()=>{
 it('passes original and attachment Files directly without base64 or FileReader',async()=>{
  const {c,surface,services}=setup()
  const reader=vi.spyOn(FileReader.prototype,'readAsDataURL')
  c.uploadRawRecord=vi.fn(async({onSuccess}:any)=>onSuccess())
  c.uploadOtherAttachment=vi.fn(async({onSuccess}:any)=>onSuccess())
  const file=new File(['synthetic'], 'large.pdf', {type:'application/pdf'})
  Object.defineProperty(file,'size',{value:500*1024*1024})
  const originals=await services.originalAction('R1','upload',{file})
  await services.attachSample('R1',0,file)
  expect(originals.maxFileSize).toBe(500*1024*1024)
  expect(surface.record.detail.options.maxFileSize).toBe(500*1024*1024)
  expect(c.uploadRawRecord.mock.calls[0][0].file).toBe(file)
  expect(c.uploadOtherAttachment.mock.calls[0][0].file).toBe(file)
  expect(reader).not.toHaveBeenCalled()
 })
 it('rejects stale base64 payloads instead of allocating another large decoded copy',async()=>{
  const {c,services}=setup();c.uploadRawRecord=vi.fn()
  await expect(services.originalAction('R1','upload',{file:{name:'old.pdf',dataUrl:'data:application/pdf;base64,WA=='}})).rejects.toThrow('请选择本地文件')
  expect(c.uploadRawRecord).not.toHaveBeenCalled()
 })
})
beforeEach(()=>{vi.clearAllMocks();vi.stubGlobal('URL',class extends URL{static revokeObjectURL=vi.fn()})})
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());vi.restoreAllMocks();vi.unstubAllGlobals();vi.useRealTimers()})
function setup(renderForm=false,serverPaging=false,isChangePage=false,navigationRouter?:Router){
 navigationRouter ??= createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{template:'<div />'}}]})
 vi.spyOn(window,'scrollTo').mockImplementation(()=>{})
 const row={reportNo:'R1',sampleNo:'S1',project:'Test',client:'Customer',status:'检测录入中',sampleStatus:'已领取',allowedActions:['testing.data_entry.return']}
 const c:any=reactive({serverPaging,isChangePage,entryPage:{total:0},setEntryQuery:vi.fn(),t:{...emptyTrialForm(),calibrationTime:'',specialReportDate:false,standards:['GB 1'],primaryTester1Code:'A',primaryTester2Code:'',reviewerCode:'B',approverCode:'C',resultStatus:'判定合格',unqualifiedParams:'',remark:'original',testIntervals:[{start:'2026-10-14 09:15:23',end:'2026-10-14 15:45:56'}],equipmentIds:[42],equipmentDisplay:{archiveNo:true,spec:true,maker:false,factoryNo:false}},selected:row,detail:{rawSample:{}},formReadOnly:false,formOpen:true,preparationLoading:false,preparationError:'',entryRows:[row],statusOptions:['检测录入中'],pageName:'检测数据录入',route:{path:'/inspection/testing/data_entry'},session:{roleKey:'admin',canAction:()=>true},equipment:[{id:42,name:'Meter'}],testerOptions:[{code:'A',name:'Tester'}],reviewerOptions:[{code:'B',name:'Reviewer'}],approverOptions:[{code:'C',name:'Approver'}],documentContent:{compositionOptions:{}},documentPreflight:{},uploaded:[],completedReportAttachments:[],orderedOtherAttachments:[],rawRecordAttachments:[],reportPageAttachments:[],includedOtherAttachmentIds:[],previewState:{status:'pending'},elnStatus:{records:[],canLaunch:false},equipmentValidityReason:()=>'',equipmentCoversIntervals:()=>true,nextTick,load:vi.fn(),onListSelection:vi.fn(),openSelectedForm:vi.fn(),canReturnReport:()=>true,persistTestInfo:vi.fn(async()=>true),saveAndDone:vi.fn(),completeChange:vi.fn(),undoDataEntryCompletion:vi.fn(),saveDocumentOption:vi.fn(),refreshPreview:vi.fn(),loadElnStatus:vi.fn()})
 let surface:any,services:any,fields:any
 const Child=defineComponent({setup(){services=inject('platform-entry-services');fields=inject('platform-entry-presentation');return()=>null}})
 const parent=mount(defineComponent({setup(){surface=createEntryPresentation(c);return{surface,renderForm}},components:{Child,EntryTrialForm},template:'<Child /><EntryTrialForm v-if="renderForm" :form="surface.record.form" :detail="surface.record.detail" :readonly="false" :errors="surface.record.fieldErrors" :people-scopes="{}" />'}),{global:{stubs:{TemplateDate:true,DataEntryDates:true},...(navigationRouter?{plugins:[navigationRouter],provide:{[matchedRouteKey as symbol]:computed(()=>navigationRouter.currentRoute.value.matched[0] || navigationRouter.getRoutes()[0])}}:{})}});wrappers.push(parent)
 return {c,surface,services,fields,row,parent}
}
describe('entry list business field mapping',()=>{
 it.each([[false,false],[true,false],[false,true],[true,true]])('maps distinct sample, parameters and scheme fields (paging %s, change %s)',async(paging,change)=>{
  const {c,surface}=setup(false,paging,change)
  c.entryRows=[{...c.entryRows[0],project:'旧检测参数',testItems:'风量、噪声',sampleOrProjectName:'空气处理机组',projectName:'工程甲',schemeName:'设备检测方案',reportTitle:'LAB',sampleRegisteredAt:'2026-11-01'}]
  const row=surface.list.rows.items[0]
  expect(row).toMatchObject({name:'空气处理机组',parameters:'风量、噪声',engineeringName:'工程甲',projectName:'设备检测方案',reportTitle:'LAB',commissionDate:'2026-11-01'})
  expect(surface.list.dataEntrySearchFields).toContainEqual({value:'name',label:'样品/工程名称'})
  expect(surface.list.dataEntrySearchFields).toContainEqual({value:'engineeringName',label:'项目名称'})
  if(!paging){
   Object.assign(surface.list.draft,{searchField:'engineeringName',contains:'工程甲'});surface.list.search()
   expect(surface.list.rows.items).toHaveLength(1)
   Object.assign(surface.list.draft,{searchField:'name',contains:'旧检测参数'});surface.list.search()
   expect(surface.list.rows.items).toHaveLength(0)
  }
 })
 it('uses the engineering name for missing sample names and leaves absent names and schemes empty',()=>{
  const {c,surface}=setup()
  c.entryRows=[{...c.entryRows[0],projectName:'历史工程',schemeName:''}]
  expect(surface.list.rows.items[0]).toMatchObject({name:'历史工程',projectName:''})
  c.entryRows=[{...c.entryRows[0],projectName:''}]
  expect(surface.list.rows.items[0]).toMatchObject({name:'',projectName:''})
 })
 it.each([false,true])('exports selected columns with the same field values as the list (paging %s)',async(paging)=>{
  const {c,surface}=setup(false,paging)
  const row={...c.entryRows[0],project:'旧检测参数',testItems:'风量、噪声',sampleOrProjectName:'空气处理机组',projectName:'工程甲',schemeName:'设备检测方案'}
  c.entryRows=[row];c.exportEntryRows=vi.fn(async()=>[row])
  surface.list.toggleColumn('projectName')
  await surface.list.exportRows()
  const blob=vi.mocked(downloadBlob).mock.calls[0][0]
  const reader=new FileReader()
  const text=await new Promise<string>((resolve,reject)=>{reader.onload=()=>resolve(String(reader.result));reader.onerror=reject;reader.readAsText(blob)})
  expect(text).toContain('样品/工程名称');expect(text).toContain('检测方案')
  expect(text).toContain('空气处理机组');expect(text).toContain('设备检测方案');expect(text).toContain('风量、噪声')
  expect(text).not.toContain('旧检测参数');expect(text).not.toContain('工程甲')
 })
})
describe('Full-template entry event/data contract',()=>{
 it('refreshes personnel on every search and confirmation, rejecting a revoked selection',async()=>{
  const {c,services}=setup()
  Object.defineProperty(c,'reviewerOptions',{get:()=>c.authorizedPeople?.reviewers||[]})
  vi.mocked(fetchAuthorizedReportPeople).mockResolvedValueOnce({reviewers:[{code:'B',name:'新姓名'}]} as any)
  expect((await services.entryPeople('R1',{role:'reviewer',page:1,pageSize:10})).items[0].name).toBe('新姓名')
  vi.mocked(fetchAuthorizedReportPeople).mockResolvedValueOnce({reviewers:[]} as any)
  await expect(services.entryPerson('R1',{role:'reviewer',id:'B'})).rejects.toThrow('授权范围')
 })
 it('discards a live personnel response after switching reports',async()=>{
  const {c,services}=setup();let resolve!:(value:any)=>void
  vi.mocked(fetchAuthorizedReportPeople).mockReturnValueOnce(new Promise(r=>resolve=r))
  const pending=services.entryPeople('R1',{role:'reviewer',page:1,pageSize:10})
  c.selected={...c.selected,reportNo:'R2'};resolve({reviewers:[{code:'B',name:'旧报告人员'}]})
  await expect(pending).rejects.toThrow('报告已切换');expect(c.authorizedPeople).toBeUndefined()
 })
 it('refreshes live equipment before returning picker detail and surfaces network failure',async()=>{
  const {c,services}=setup()
  vi.mocked(fetchReportEquipment).mockResolvedValueOnce({rows:[{id:42,name:'更新仪器',lastCalDate:'2025-12-17',planCalDate:'2026-12-16',eligibility:{selectable:true}}],total:1} as any)
  const result=await services.entryDetail('R1')
  expect(result.options.equipment[0]).toMatchObject({name:'更新仪器',lastCalibrationDate:'2025-12-17'})
  vi.mocked(fetchReportEquipment).mockRejectedValueOnce(new Error('network'))
  await expect(services.entryDetail('R1')).rejects.toThrow('network')
  expect(c.equipment[0].eligibility).toBeUndefined()
 })
 it('keeps every authorized instrument visible regardless of current status or test eligibility',async()=>{
  const {c,surface}=setup()
  c.equipment=[
   {id:1,archiveNo:'M',name:'正常仪器',eligibility:{selectable:true,message:'覆盖试验区间'},status:'可用',lastCalDate:'2026-01-01',planCalDate:'2099-12-31'},
   {id:2,archiveNo:'M',name:'Expired meter',eligibility:{selectable:true,message:'覆盖试验区间'},status:'限制使用',lastCalDate:'2026-01-01',planCalDate:'2026-10-31'},
   {id:3,archiveNo:'S',name:'停用仪器',eligibility:{selectable:false,message:'停用'},status:'停用',lastCalDate:'2026-01-01',planCalDate:'2099-12-31'},
  ]
  c.equipmentCoversIntervals=()=>false
  expect(surface.record.detail.equipmentConfig.associatedIds).toEqual(['1','2','3'])
  expect(surface.record.detail.options.equipment.map((e:any)=>e.selectable)).toEqual([true,true,false])
  expect(surface.record.detail.options.equipment[1].lastCalibrationDate).toBe('2026-01-01')
  c.t.testIntervals[0].end='2026-11-01 12:00:00'
  await nextTick()
  expect(surface.record.detail.options.equipment[1].selectable).toBe(false)
  expect(surface.record.detail.equipmentConfig.associatedIds).toEqual(['1','2','3'])
 })
 it.each([{selection:[] as string[]}, {selection:['R-other']}])('returns the clicked row independently of checkbox selection $selection',async ({selection})=>{
  const {c,surface,row}=setup();c.formOpen=false;surface.list.selected=selection
  c.returnToEntrust=vi.fn(async()=>{})
  await surface.list.rowAction(row,'退回')
  expect(c.returnToEntrust).toHaveBeenCalledExactlyOnceWith(row)
  expect(c.onListSelection).not.toHaveBeenCalled()
  expect(c.openSelectedForm).not.toHaveBeenCalled()
 })
 it('preserves the rollback form four independent environment fields and saves exact backend values',async()=>{const {c,surface,parent}=setup(true);expect(parent.find('#trial-environment').exists()).toBe(false);const values={calibrationPlace:'实验室',temperature:'23.00',humidity:'50',pressure:'1000'};for(const [key,value]of Object.entries(values))await parent.get('#platform-trial-'+key).setValue(value);await surface.record.save();expect(c.persistTestInfo).toHaveBeenCalledOnce();for(const [key,value]of Object.entries(values))expect(c.t[key]).toBe(value)})
 it('does not allow readonly environment field bindings to overwrite data',()=>{const {c,fields}=setup();c.t.temperature='22';c.formReadOnly=true;fields.environmentFields.find((f:any)=>f.id==='platform-trial-temperature').binding.set({},'99');expect(c.t.temperature).toBe('22')})
 it('reads a frozen report in read-only mode without saving or generating a draft',async()=>{const {c,surface}=setup();c.formReadOnly=true;c.previewState={status:'failed',message:'old draft failed'};vi.mocked(artifactObjectUrl).mockResolvedValue('blob:controlled');await surface.record.finalPreview();expect(artifactObjectUrl).toHaveBeenCalledWith('R1',c.reportDetailView);expect(c.persistTestInfo).not.toHaveBeenCalled();expect(c.refreshPreview).not.toHaveBeenCalled();expect(surface.record.pdfUrl).toBe('blob:controlled');expect(surface.record.detail.reportStatus).toBe('ready');expect(surface.record.canConfirmReport).toBe(false);await surface.record.finalPreview();expect(artifactObjectUrl).toHaveBeenCalledTimes(1)})
 it('shows a missing historic version as a business prerequisite with a real diagnostic object',async()=>{const {c,surface}=setup();c.formReadOnly=true;vi.mocked(artifactObjectUrl).mockRejectedValue(new Error('尚无当前受控正式版本；请返回报告制作流程'));await surface.record.finalPreview();expect(surface.record.error.code).toBe('BUSINESS_RULE');expect(surface.record.error.diagnosticId).toMatch(/^ERR-/);expect(c.refreshPreview).not.toHaveBeenCalled();expect(surface.record.pdfUrl).toBe('')})
 it('discards preview bytes when the report changes before the read completes',async()=>{const {c,surface}=setup();c.formReadOnly=true;let resolve!:(v:string)=>void;vi.mocked(artifactObjectUrl).mockReturnValue(new Promise(r=>resolve=r));const revoke=vi.fn();vi.stubGlobal('URL',class extends URL{static revokeObjectURL=revoke});const pending=surface.record.finalPreview();c.selected={...c.selected,reportNo:'R2'};await nextTick();resolve('blob:old');await pending;expect(surface.record.pdfUrl).toBe('');expect(revoke).toHaveBeenCalledWith('blob:old');vi.unstubAllGlobals()})
 it('keeps editable preview on the original validation and generation contract',async()=>{const {c,surface}=setup();c.previewReady=true;vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:draft',name:'R1.pdf',receipt:'proof-current'});await surface.record.finalPreview();expect(c.persistTestInfo).toHaveBeenCalledWith(true);expect(c.refreshPreview).toHaveBeenCalledExactlyOnceWith(false);expect(surface.record.pdfUrl).toBe('blob:draft')})
 it('maps trial fields bidirectionally without changing backend meanings',()=>{const {c,surface}=setup();const f=surface.record.form;expect(f.conclusionStatus).toBe('判定合格');f.notes='changed';f.tester1Id='Z';f.showEquipmentModel=false;expect(c.t.remark).toBe('changed');expect(c.t.primaryTester1Code).toBe('Z');expect(c.t.equipmentDisplay.spec).toBe(false)})
 it('preserves time precision and multiple date intervals',()=>{const {c,surface}=setup();const f=surface.record.form;expect(f.testDates[0].from).toBe('2026-10-14 09:15:23');f.testDates[0].to='2026-10-14 16:12:59';expect(c.t.testIntervals[0].end).toBe('2026-10-14 16:12:59');f.testDates=[...f.testDates,{kind:'range',from:'2026-10-15 01:00:00',to:'2026-10-15 03:00:00'}];expect(c.t.testIntervals).toHaveLength(2)})
 it('cannot edit through the template value adapter in read-only mode',()=>{const {c,surface}=setup();c.formReadOnly=true;surface.record.form.notes='bad';surface.record.form.equipmentIds=['99'];surface.record.form.testDates[0].from='bad';expect(c.t.remark).toBe('original');expect(c.t.equipmentIds).toEqual([42]);expect(c.t.testIntervals[0].start).toBe('2026-10-14 09:15:23')})
 it('person selection stays within backend project authorization for every scope',async()=>{const {services}=setup();const rows=await services.entryPeople('R1',{role:'reviewer',scope:'all',page:1,pageSize:10});expect(rows.items.map((r:any)=>r.id)).toEqual(['B']);await expect(services.entryPerson('R1',{role:'reviewer',id:'A'})).rejects.toThrow('授权范围')})
 it('report confirmation does not advance the workflow',()=>{const {c,surface}=setup();surface.record.confirmReport();expect(c.saveAndDone).not.toHaveBeenCalled();expect(surface.record.reportConfirmed).toBe(false)})
 it('completion waits for hydration and delegates to the existing controller',async()=>{const {c,surface,row}=setup();c.preparationLoading=true;surface.list.statusAction={row,action:'complete'};const pending=surface.list.runStatusAction();await nextTick();expect(c.saveAndDone).not.toHaveBeenCalled();c.preparationLoading=false;await nextTick();await pending;expect(c.saveAndDone).toHaveBeenCalledOnce()})
 it('reports the loading failure and restores the list',async()=>{const {c,surface,row}=setup();c.preparationError='load failed';surface.list.statusAction={row,action:'complete'};await surface.list.runStatusAction();expect(c.saveAndDone).not.toHaveBeenCalled();expect(c.formOpen).toBe(false);expect(surface.list.completingFromList).toBe(false);expect(feedback.message).toBe('load failed')})
 it('keeps cancelled workflow actions unavailable',()=>{const {surface,row}=setup();expect(surface.list.actionAllowed(row,'作废')).toBe(false);expect(surface.list.actionAllowed({...row,status:'待审核'},'数据录入')).toBe(false)})
 it('keeps report language, optional appendix inclusion and no-body decisions on existing handlers',()=>{const {c,fields}=setup();const section=fields.extraSections[0];section.fields.find((f:any)=>f.id==='platform-report-language').binding.set({},'EN');expect(c.saveDocumentOption).toHaveBeenCalledWith('reportLanguage','EN')})
 it('does not mislabel a backend timeliness status as a date',()=>{const {c,surface}=setup();c.entryRows[0].deadline='正常';expect(surface.list.rows.items[0].requestedTestDate).toBe('');c.entryRows[0].deadline='2026-10-15';expect(surface.list.rows.items[0].requestedTestDate).toBe('2026-10-15')})
 it('uses the existing change-completion branch for a change round',async()=>{const {c,surface,row}=setup();c.isChangeRound=true;surface.list.statusAction={row:{...row,status:'检测更改中'},action:'complete'};await surface.list.runStatusAction();expect(c.completeChange).toHaveBeenCalledOnce();expect(c.saveAndDone).not.toHaveBeenCalled()})
 it('cancels a pending completion when the selected report changes',async()=>{const {c,surface,row}=setup();c.preparationLoading=true;surface.list.statusAction={row,action:'complete'};const pending=surface.list.runStatusAction();await nextTick();c.selected={...row,reportNo:'R2'};c.preparationLoading=false;await nextTick();await pending;expect(c.saveAndDone).not.toHaveBeenCalled();expect(feedback.message).toContain('已取消')})
 it('shows change-completion failures in the opened form and permits retry',async()=>{const {c,surface,row}=setup();c.isChangeRound=true;c.completeChange.mockRejectedValueOnce(new Error('报告生成失败'));const item={row:{...row,status:'检测更改中'},action:'complete'};surface.list.statusAction=item;await surface.list.runStatusAction();expect(surface.record.error.message).toBe('报告生成失败');expect(surface.list.actionBusy).toBeFalsy();surface.list.statusAction=item;await surface.list.runStatusAction();expect(c.completeChange).toHaveBeenCalledTimes(2)})
 it('shows unsuccessful change validation rather than silently dismissing completion',async()=>{const {c,surface,row}=setup();c.isChangeRound=true;c.completeChange.mockResolvedValue(false);surface.list.statusAction={row:{...row,status:'检测更改中'},action:'complete'};await surface.list.runStatusAction();expect(surface.record.error.message).toContain('录入尚未完成')})
 it('keeps filters and page while waiting for completion or a signing choice', async () => {
  const {c,surface,row}=setup(false,true)
  surface.list.draft.contains='yp'
  surface.list.search()
  surface.list.patch({page:2,sort:'reportCode',direction:'desc'})
  surface.list.patch({page:2})
  let finish!: () => void
  c.saveAndDone.mockReturnValue(new Promise<void>(resolve => { finish=resolve }))
  surface.list.statusAction={row,action:'complete'}
  const pending=surface.list.runStatusAction()
  await nextTick()
  expect(surface.list.statusAction).toBeUndefined()
  expect(surface.list.completingFromList).toBe(true)
  expect(surface.list.actionAllowed(row,'录入完成')).toBe(false)
  finish()
  await pending
  expect(c.formOpen).toBe(false)
  expect(surface.list.completingFromList).toBe(false)
  expect(surface.list.rows.page).toBe(2)
  expect(surface.list.draft.contains).toBe('yp')
  expect(surface.list.query).toMatchObject({sort:'reportCode',direction:'desc'})
 })
 it('keeps the original validation message after a rejected list submission', async () => {
  const {c,surface,row}=setup()
  c.saveAndDone.mockImplementation(async () => {
   ElMessage.warning('请先确认最新完整报告')
   return false
  })
  surface.list.statusAction={row,action:'complete'}
  await surface.list.runStatusAction()
  expect(feedback.message).toBe('请先确认最新完整报告')
  expect(surface.list.statusError).toBe('')
  expect(surface.list.statusAction).toBeUndefined()
  expect(c.formOpen).toBe(false)
 })
 it('blocks duplicate completion while hydration is pending',async()=>{const {c,surface,row}=setup();c.preparationLoading=false;surface.list.statusAction={row,action:'complete'};const first=surface.list.runStatusAction();await surface.list.runStatusAction();await first;expect(c.saveAndDone).toHaveBeenCalledOnce()})
 it('does not silently omit Word records from a combined original-record preview',async()=>{const {c,services}=setup();c.rawRecordAttachments=[{name:'one.pdf'},{name:'two.docx'}];await expect(services.entryDownload('R1','/preview?version=1')).rejects.toThrow('不能生成完整合并预览')})
 it('maps real sample and commission keys without injecting demo defaults',()=>{const {c,surface}=setup();expect(surface.record.sampleForm.commissionInfo.invoiceType).toBe('');expect(surface.record.sampleForm.quantity).toBe('');c.detail={entrustSnapshot:{info:{invoiceType:'专票',handleDept:'D',taxNo:'T'}},rawSample:{sampleAmount:'12',produceDate:'2026-01-03',sampleUnit:'U',sampleTime:'2026-01-04',reportType:'产品报告',centerPrefix:'NCSA',reportTitle:'检测报告',subItems:[{projectName:'P',amount:'12.30'}]}};const f=surface.record.sampleForm;expect(f.quantity).toBe('12');expect(f.details.productionDate).toBe('2026-01-03');expect(f.details.samplingOrganization).toBe('U');expect(f.details.subprojects[0].amount).toBe('12.30');expect(f.commissionInfo.invoiceType).toBe('专票');expect(f.commissionInfo.handlingDepartmentId).toBe('D');expect(f.details.reportSettings.formatId).toBe('产品报告');expect(f.details.reportSettings.titleId).toBe('检测报告')})
 it('shows actual attachment bytes and official inclusion independently',()=>{const {c,surface,fields}=setup();c.orderedOtherAttachments=[{id:7,name:'a.pdf',sizeBytes:512}];expect(surface.record.detail.files[0].size).toBe(512);expect(fields.fileDisposition({id:'7',kind:'appendix'})).toContain('未选入');c.includedOtherAttachmentIds=[7];expect(fields.fileDisposition({id:'7',kind:'appendix'})).toContain('已选入')})
})

describe('explicit rework submission from the open form',()=>{
 it('renders the real completion button and calls the owning controller',async()=>{
  const {c,surface}=setup();c.isChangeRound=true;c.isChangePage=true;c.completeChange.mockResolvedValue(true)
  const view=shallowMount(EntryRecordPresentation,{props:{context:surface.record},global:{stubs:{DataEntryTrialForm:{inheritAttrs:false,template:'<div />'}}}});wrappers.push(view)
  const button=view.findAll('button').find(b=>b.text()==='完成更改并提交审核')!
  expect(button).toBeTruthy();await button.trigger('click');await flushPromises()
  expect(c.completeChange).toHaveBeenCalledOnce();expect(c.saveAndDone).not.toHaveBeenCalled()
 })
 it('preview confirmation does not claim submission or call completion',async()=>{
  const {c,surface}=setup();c.isChangeRound=true;c.previewReady=true
  vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:ready',name:'R1.pdf',receipt:'proof-current'})
  await surface.record.finalPreview();await surface.record.confirmReport()
  expect(surface.record.reportConfirmed).toBe(true);expect(c.completeChange).not.toHaveBeenCalled()
 })
 it('blocks duplicate form and list completion while the request is in flight',async()=>{
  const {c,surface,row}=setup();c.isChangeRound=true
  let resolve!:(v:boolean)=>void;c.completeChange.mockImplementation(()=>new Promise(r=>resolve=r))
  const pending=surface.record.completeChange();expect(surface.record.working).toBe(true)
  expect(await surface.record.completeChange()).toBe(false)
  surface.list.statusAction={row,action:'complete'};await surface.list.runStatusAction()
  expect(c.completeChange).toHaveBeenCalledOnce();resolve(true);await pending
  expect(surface.record.working).toBe(false)
 })
 it.each(['readonly','closed','adminEdit','originalBusy','notChange'])('does not submit while %s',async reason=>{
  const {c,surface}=setup();c.isChangeRound=reason!=='notChange'
  c.formReadOnly=reason==='readonly';c.formOpen=reason!=='closed';c.adminEditing=reason==='adminEdit';surface.record.originalBusy=reason==='originalBusy'
  expect(await surface.record.completeChange()).toBe(false);expect(c.completeChange).not.toHaveBeenCalled()
 })
 it('keeps validation and server failures visible and allows an explicit retry',async()=>{
  const {c,surface}=setup();c.isChangeRound=true;c.completeChange.mockResolvedValueOnce(false).mockRejectedValueOnce(new Error('当前报告 PDF 未就绪')).mockResolvedValueOnce(true)
  expect(await surface.record.completeChange()).toBe(false);expect(surface.record.error.message).toContain('更改尚未提交')
  expect(await surface.record.completeChange()).toBe(false);expect(surface.record.error.message).toContain('PDF 未就绪')
  expect(await surface.record.completeChange()).toBe(true);expect(surface.record.error).toBe('')
 })
})

describe('asynchronous complete report preview',()=>{
 function queue(){
  const result=setup(),{c}=result
  c.previewReady=false
  c.refreshPreview.mockImplementation(async()=>{c.previewState={status:'queued',sourceHash:'v1',message:'排队中'}})
  vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:current',name:'R1.pdf',receipt:'proof-current'})
  return result
 }
 it('waits through queued and running, then loads the PDF without another save or click',async()=>{
  const {c,surface}=queue()
  const pending=surface.record.finalPreview();await flushPromises()
  expect(surface.record.working).toBe(true)
  expect(surface.record.detail.reportStatus).toBe('running')
  expect(surface.record.error).toBe('')
  expect(completeReportObjectUrl).not.toHaveBeenCalled()
  await surface.record.finalPreview()
  c.previewState={status:'running',sourceHash:'v1',message:'转换中'};await nextTick()
  expect(surface.record.detail.reportStatus).toBe('running')
  c.previewState={status:'ready',sourceHash:'v1'};c.previewReady=true
  await pending
  expect(c.persistTestInfo).toHaveBeenCalledTimes(1)
  expect(completeReportObjectUrl).toHaveBeenCalledTimes(1)
  expect(surface.record.pdfUrl).toBe('blob:current')
  expect(surface.record.canConfirmReport).toBe(true)
 })
 it('shows the actual failure and explicitly retries a failed job',async()=>{
  const {c,surface}=queue()
  const pending=surface.record.finalPreview();await flushPromises()
  c.previewState={status:'failed',sourceHash:'v1',message:'文件转换失败：缺少字体'}
  await pending
  expect(surface.record.error.message).toContain('缺少字体')
  expect(surface.record.detail.job.error).toContain('缺少字体')
  expect(surface.record.detail.reportStatus).toBe('failed')
  expect(surface.record.working).toBe(false)
  const retry=surface.record.finalPreview();await flushPromises()
  expect(c.refreshPreview).toHaveBeenLastCalledWith(true)
  c.previewState={status:'ready',sourceHash:'v1'};c.previewReady=true
  await retry
  expect(surface.record.pdfUrl).toBe('blob:current')
  expect(surface.record.error).toBe('')
 })
 it.each(['close','report','view','account','route','edit','unmount'])('discards queued work after %s',async(kind)=>{
  const {c,surface,parent}=queue()
  const pending=surface.record.finalPreview();await flushPromises()
  if(kind==='close')c.formOpen=false
  if(kind==='report')c.selected={...c.selected,reportNo:'R2'}
  if(kind==='view')c.reportDetailView='changed-view'
  if(kind==='account')c.session.account='someone-else'
  if(kind==='route')c.route.path='/other'
  if(kind==='edit')c.t.remark='changed'
  if(kind==='unmount')parent.unmount()
  await pending
  c.previewState={status:'ready',sourceHash:'v1'};c.previewReady=true;await flushPromises()
  expect(completeReportObjectUrl).not.toHaveBeenCalled()
  expect(surface.record.pdfUrl).toBe('')
 })
 it('rejects downloaded bytes if the source changed while loading',async()=>{
  const {c,surface}=queue()
  let resolve!:(value:any)=>void
  vi.mocked(completeReportObjectUrl).mockReturnValue(new Promise(r=>resolve=r))
  const pending=surface.record.finalPreview();await flushPromises()
  c.previewState={status:'ready',sourceHash:'v1'};c.previewReady=true;await flushPromises()
  c.previewState={status:'queued',sourceHash:'v2'};c.previewReady=false
  resolve({url:'blob:old',name:'R1.pdf',receipt:'proof-current'});await pending
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:old')
  expect(surface.record.pdfUrl).toBe('')
  expect(surface.record.canConfirmReport).toBe(false)
 })
 it('does not submit twice while the initial save is pending',async()=>{
  const {c,surface}=queue();let resolve!:(value:boolean)=>void
  c.persistTestInfo.mockReturnValue(new Promise(r=>resolve=r))
  const pending=surface.record.finalPreview()
  await surface.record.finalPreview()
  expect(c.persistTestInfo).toHaveBeenCalledTimes(1)
  resolve(false);await pending
  expect(c.refreshPreview).not.toHaveBeenCalled()
  expect(surface.record.working).toBe(false)
 })
 it('shows a failed background job in the actual preview panel',async()=>{
  const {c,surface}=queue()
  c.previewState={status:'failed',sourceHash:'v1',message:'报告编号与当前报告不一致'}
  const rec=surface.record
  const view=mount(EntryReportFiles,{props:{detail:rec.detail,layoutId:rec.layoutId,activeTab:'preview',busy:false,readonly:false,dirty:false,canConfirm:false,confirmed:false,previewUrl:'',previewName:'R1.pdf',upload:rec.uploadReportFile},global:{stubs:{DataEntryFiles:true}}})
  wrappers.push(view)
  expect(view.get('#report-panel-preview').text()).toContain('报告生成失败')
  expect(view.get('#report-panel-preview').text()).toContain('报告编号与当前报告不一致')
 })
 it.each(['ready','failed'] as const)('follows the real controller polling until %s',async(finalStatus)=>{
  vi.useFakeTimers()
  const {c,surface}=setup()
  vi.mocked(completePreviewState).mockResolvedValue({status:'queued',sourceHash:'source-1',message:'排队'})
  const host=mount(defineComponent({setup(){
   const flow=useCompletePreview(computed(()=>c.selected.reportNo),computed(()=>c.reportDetailView),computed(()=>c.formOpen))
   c.previewState=flow.state;c.previewReady=flow.ready;c.refreshPreview=flow.refresh
   return()=>null
  }}));wrappers.push(host)
  await flushPromises()
  vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:polled',name:'R1.pdf',receipt:'proof-current'})
  const pending=surface.record.finalPreview();await flushPromises()
  expect(completeReportObjectUrl).not.toHaveBeenCalled()
  vi.mocked(completePreviewState).mockResolvedValue({status:finalStatus,sourceHash:'source-1',message:finalStatus==='failed'?'实际转换失败':'完成'})
  await vi.advanceTimersByTimeAsync(3000);await pending
  expect(c.persistTestInfo).toHaveBeenCalledTimes(1)
  if(finalStatus==='ready')expect(surface.record.pdfUrl).toBe('blob:polled')
  else{
   expect(surface.record.error.message).toContain('实际转换失败')
   expect(surface.record.canConfirmReport).toBe(false)
  }
 })
})

describe('loaded report preview lifetime',()=>{
 it('explains missing body without a fake job and recovers when a body is uploaded',async()=>{
  const {c,surface}=setup()
  const enabled=reactive({value:false})
  const host=mount(defineComponent({setup(){
   const flow=useCompletePreview(computed(()=>c.selected.reportNo),computed(()=>c.reportDetailView),computed(()=>enabled.value),computed(()=>'请先上传完整报告正文，再生成预览。'))
   c.previewState=flow.state;c.previewReady=flow.ready;c.refreshPreview=flow.refresh
   return()=>null
  }}));wrappers.push(host)
  await flushPromises()
  await surface.record.finalPreview()
  expect(completePreviewState).not.toHaveBeenCalled()
  expect(completeReportObjectUrl).not.toHaveBeenCalled()
  expect(surface.record.working).toBe(false)
  expect(surface.record.canConfirmReport).toBe(false)
  expect(surface.record.error.message).toContain('请先上传完整报告正文')
  vi.mocked(completePreviewState).mockResolvedValue({status:'ready',sourceHash:'uploaded',message:'完成'})
  vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:uploaded',name:'R1.pdf',receipt:'proof-current'})
  enabled.value=true;await flushPromises()
  await surface.record.finalPreview()
  expect(surface.record.pdfUrl).toBe('blob:uploaded')
  expect(surface.record.canConfirmReport).toBe(true)
 })
 it('retains the PDF and confirmation through two minutes of real status polling',async()=>{
  vi.useFakeTimers()
  const {c,surface}=setup(),rec=surface.record
  let sourceHash='source-1'
  // HTTP JSON produces a fresh object on every response, even for the same version.
  vi.mocked(completePreviewState).mockImplementation(async()=>({status:'ready',sourceHash,message:'完成'}))
  const host=mount(defineComponent({setup(){
   const flow=useCompletePreview(computed(()=>c.selected.reportNo),computed(()=>c.reportDetailView),computed(()=>c.formOpen))
   c.previewState=flow.state;c.previewReady=flow.ready;c.refreshPreview=flow.refresh
   return()=>null
  }}));wrappers.push(host)
  await flushPromises()
  vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:stable',name:'R1.pdf',receipt:'proof-current'})
  await rec.finalPreview()
  await rec.confirmReport()
  const initialPolls=vi.mocked(completePreviewState).mock.calls.length
  for(let i=0;i<12;i++){
   await vi.advanceTimersByTimeAsync(10000)
   expect(rec.pdfUrl).toBe('blob:stable')
   expect(rec.reportConfirmed).toBe(true)
   expect(rec.canConfirmReport).toBe(true)
  }
  expect(completePreviewState).toHaveBeenCalledTimes(initialPolls+12)
  expect(URL.revokeObjectURL).not.toHaveBeenCalled()
  expect(completeReportObjectUrl).toHaveBeenCalledTimes(1)
  expect(c.persistTestInfo).toHaveBeenCalledTimes(1)
  // Polling must still invalidate an actually changed report version.
  sourceHash='source-2'
  await vi.advanceTimersByTimeAsync(10000)
  expect(rec.pdfUrl).toBe('')
  expect(rec.reportConfirmed).toBe(false)
  expect(rec.canConfirmReport).toBe(false)
  expect(URL.revokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:stable')
 })
 it('retains the preview when refreshed context objects still identify the same report and account',async()=>{
  const {c,surface}=setup(),rec=surface.record
  c.previewReady=true
  vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:same-context',name:'R1.pdf',receipt:'proof-current'})
  await rec.finalPreview();await rec.confirmReport()
  c.selected={...c.selected};c.session={...c.session};c.route={...c.route};c.t={...c.t}
  c.documentContent={...c.documentContent,compositionOptions:{...c.documentContent.compositionOptions}}
  await nextTick()
  expect(rec.pdfUrl).toBe('blob:same-context')
  expect(rec.reportConfirmed).toBe(true)
  expect(URL.revokeObjectURL).not.toHaveBeenCalled()
 })
 it.each(['input','mode','report','view','account','route','close','unmount'])('releases a loaded preview when %s changes',async(kind)=>{
  const {c,surface,parent}=setup(),rec=surface.record
  c.previewReady=true
  vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:obsolete',name:'R1.pdf',receipt:'proof-current'})
  await rec.finalPreview();await rec.confirmReport()
  if(kind==='input')c.t.remark='changed'
  if(kind==='mode')c.documentContent.compositionOptions.preserveUploadedReport=true
  if(kind==='report')c.selected={...c.selected,reportNo:'R2'}
  if(kind==='view')c.reportDetailView='changed'
  if(kind==='account')c.session.account='other'
  if(kind==='route')c.route.path='/other'
  if(kind==='close')c.formOpen=false
  if(kind==='unmount')parent.unmount()
  await nextTick()
  expect(URL.revokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:obsolete')
  if(kind!=='unmount'){
   expect(rec.pdfUrl).toBe('')
   expect(rec.reportConfirmed).toBe(false)
   expect(rec.canConfirmReport).toBe(false)
  }
 })
})

describe('data entry administrator switch surface',()=>{
 it('shows an explicit button in data entry and report writing, without enabling it on entry',async()=>{
  const {c,surface}=setup()
  c.previewReady=false;c.canAdminEdit=true;c.adminEditing=false;c.toggleAdminEditing=vi.fn(()=>{c.adminEditing=!c.adminEditing})
  const view=shallowMount(EntryRecordPresentation,{props:{context:surface.record},global:{stubs:{DataEntryTrialForm:{inheritAttrs:false,template:'<div />'}}}});wrappers.push(view)
  const button=()=>view.findAll('button').find(b=>b.text().includes('管理员编辑'))!
  expect(button().text()).toBe('管理员编辑')
  expect(c.toggleAdminEditing).not.toHaveBeenCalled()
  await surface.record.openReport()
  await nextTick()
  expect(surface.record.reportOnly).toBe(true)
  expect(c.adminEditing).toBe(false)
  expect(button().text()).toBe('管理员编辑')
  await button().trigger('click')
  expect(c.adminEditing).toBe(true)
  expect(button().text()).toBe('退出管理员编辑')
  expect(view.text()).toContain('保存检测数据时需填写修订说明')
  await button().trigger('click')
  expect(c.adminEditing).toBe(false)
  c.canAdminEdit=false
  await nextTick()
  expect(button()).toBeUndefined()
 })
 it('cannot switch the save mode with unsaved edits or during a request',async()=>{
  const {c,surface}=setup()
  c.canAdminEdit=true;c.adminEditing=true;c.toggleAdminEditing=vi.fn()
  c.preparationLoading=true;await nextTick();c.preparationLoading=false;await nextTick()
  c.t.remark='changed'
  surface.record.toggleAdminEditing()
  expect(c.toggleAdminEditing).not.toHaveBeenCalled()
  expect(surface.record.error.message).toContain('请先保存')
  await surface.record.save()
  c.saving=true
  surface.record.toggleAdminEditing()
  expect(c.toggleAdminEditing).not.toHaveBeenCalled()
  c.saving=false
  surface.record.toggleAdminEditing()
  expect(c.toggleAdminEditing).toHaveBeenCalledOnce()
 })
 it('readonly save events do not dispatch a write',async()=>{
  const {c,surface}=setup();c.formReadOnly=true
  await surface.record.save()
  expect(c.persistTestInfo).not.toHaveBeenCalled()
 })
})

describe('uploaded complete report administrator button',()=>{
 function render(){
  const state=setup(), rec=state.surface.record
  const view=mount(defineComponent({components:{EntryReportFiles},setup:()=>({rec}),template:`<EntryReportFiles v-if="rec.detail" :detail="rec.detail" :layout-id="rec.layoutId" :active-tab="rec.reportTab" :busy="!!rec.working" :readonly="!rec.editable" :dirty="rec.dirty" :can-confirm="false" :confirmed="rec.reportConfirmed" preview-url="" preview-name="" :upload="rec.uploadReportFile" :can-preserve-uploaded-report="rec.canPreserveUploadedReport" :preserve-uploaded-report="rec.preserveUploadedReport" :preserve-option-unavailable="rec.preserveOptionUnavailable" @toggle-preserve-uploaded-report="rec.togglePreserveUploadedReport()" />`}),{global:{stubs:{DataEntryFiles:true,DataEntryPreview:true}}})
  wrappers.push(view)
  const button=()=>view.find('button[aria-describedby="preserve-report-hint"]')
  return {...state,rec,view,button}
 }
 it('shows an explicit button in template and upload steps; changes only on successful saved state',async()=>{
  const {c,rec,view,button}=render()
  expect(button().exists()).toBe(true);expect(button().attributes('aria-pressed')).toBe('false')
  expect(c.saveDocumentOption).not.toHaveBeenCalled()
  await button().trigger('click')
  expect(c.saveDocumentOption).toHaveBeenLastCalledWith('preserveUploadedReport',true)
  expect(button().attributes('aria-pressed')).toBe('false') // A failed or pending save must not claim enabled.
  c.documentContent.compositionOptions.preserveUploadedReport=true
  rec.reportTab='files';await nextTick()
  expect(button().attributes('aria-pressed')).toBe('true');expect(view.text()).toContain('不替换封面、首页和注意事项')
  await button().trigger('click');expect(c.saveDocumentOption).toHaveBeenLastCalledWith('preserveUploadedReport',false)
 })
 it('hides the control and refuses programmatic writes from ordinary and company-wide non-admin accounts',async()=>{
  const {c,rec,button}=render()
  c.session.roleKey='tester';c.session.fullPlatformAuthority=true;c.session.canCorrectBusinessData=true
  await nextTick();expect(button().exists()).toBe(false)
  await rec.togglePreserveUploadedReport();expect(c.saveDocumentOption).not.toHaveBeenCalled()
  c.session.account='admin';await nextTick();expect(button().exists()).toBe(true)
 })
 it('blocks readonly, pending requests, unloaded settings and unsaved trial edits',async()=>{
  const {c,rec,button}=render()
  for(const key of ['formReadOnly','compositionSaving','uploading']){
   c[key]=true;await nextTick();expect(button().attributes('disabled')).toBeDefined()
   await rec.togglePreserveUploadedReport();c[key]=false
  }
  const content=c.documentContent;c.documentContent=null;await nextTick()
  expect(button().attributes('disabled')).toBeDefined();await rec.togglePreserveUploadedReport();c.documentContent=content
  c.preparationLoading=true;await nextTick();c.preparationLoading=false;await nextTick();c.t.remark='unsaved'
  await rec.togglePreserveUploadedReport();expect(rec.error.message).toContain('请先保存检测数据')
  expect(c.saveDocumentOption).not.toHaveBeenCalled()
 })
 it('invalidates the previous PDF and report confirmation when the saved mode changes',async()=>{
  const {c,rec}=render();rec.pdfUrl='blob:old';rec.reportConfirmed=true
  c.documentContent.compositionOptions.preserveUploadedReport=true;await nextTick()
  expect(rec.pdfUrl).toBe('');expect(rec.reportConfirmed).toBe(false)
 })
})


describe('Business data status display and filtering',()=>{
 it.each(['报告签发中','报告盖章中','报告已盖章，归档中，未发放'])('keeps %s distinct from internal pending-print state',(dataStatus)=>{
  const {c,surface}=setup();c.entryRows=[{reportNo:'R-sign',sampleNo:'S',status:'待打印',dataStatus}];
  expect(surface.list.rows.items[0]).toMatchObject({status:'待打印',dataStatus});
  expect(surface.list.dataEntryStates).toContain(dataStatus);
  expect(surface.list.dataEntryStates).not.toContain('待打印');
  surface.list.draft.status=dataStatus;surface.list.search();expect(surface.list.rows.total).toBe(1);
  expect(surface.list.actionAllowed(surface.list.rows.items[0],'录入完成')).toBe(false);
  surface.list.draft.status='报告审核中';surface.list.search();expect(surface.list.rows.total).toBe(0);
 });
 it('keeps filters available on empty lists and falls back only when the API has no label',()=>{
  const {c,surface}=setup();c.entryRows=[];
  expect(surface.list.dataEntryStates).toContain('合同评审中');
  c.entryRows=[{reportNo:'legacy',status:'历史状态'}];
  surface.list.draft.status='历史状态';surface.list.search();
  expect(surface.list.rows.items[0]).toMatchObject({status:'历史状态',dataStatus:'历史状态'});
 });
});

it.each([false,true])('entry/change server default and off-page status (%s)',async(change)=>{
 const {c,surface}=setup(false,true,change);
 expect(c.setEntryQuery.mock.calls[0][0]).toMatchObject({rowProjection:'active',status:''});
 c.entryRows=[];expect(surface.list.dataEntryStates).toContain(change?'检测更改中':'报告审核中');
 surface.list.draft.status=change?'检测更改中':'报告审核中';surface.list.draft.contains='needle';surface.list.search();await nextTick();
 expect(c.setEntryQuery.mock.calls.at(-1)[0]).toMatchObject({rowProjection:'',status:change?'检测更改中':'报告审核中',contains:'needle',page:1});
 surface.list.draft.status='';surface.list.search();await nextTick();expect(c.setEntryQuery.mock.calls.at(-1)[0].rowProjection).toBe('');
});

it('reinitializes pending when reusing entry component for data change',async()=>{
 const {c,surface}=setup(false,true,false);
 surface.list.draft.status='报告审核中';surface.list.search();await nextTick();
 c.isChangePage=true;await nextTick();
 expect(surface.list.draft.status).toBe('待处理');
 expect(surface.list.dataEntryStates).toContain('检测数据录入中');
 expect(surface.list.dataEntryStates).not.toContain('退回待重传');
 expect(c.setEntryQuery.mock.calls.at(-1)[0]).toMatchObject({rowProjection:'active',status:'',page:1});
});


describe('entry report groups',()=>{
 it.each([false,true])('preserves group and resets page for entry/change=%s',async change=>{
  const {c,surface}=setup(false,true,change);c.session.dataScope={department:'空调设备检测部',scopeType:'department'}
  surface.list.patch({page:5});surface.list.draft.reportGroup='热湿组';surface.list.search();await nextTick()
  expect(c.setEntryQuery.mock.lastCall?.[0]).toMatchObject({reportGroup:'热湿组',page:1})
  expect(surface.list.reportGroupOptions[0]).toEqual({value:'',label:'空调设备检测部'})
 })
})

 it.each([false,true])('sorts entry/change by saved/completed time and retains filters (%s)',async(change)=>{
  const {c,surface}=setup(false,true,change);const m=surface.list;
  for(const key of ['reportCode','commissionCode','testStartDate','testEndDate','dataSavedAt','dataCompletedAt'])expect(m.dataEntryColumns.find((col:any)=>col.key===key)?.sort).toBe(key);
  m.draft.contains='KEEP';m.search();m.patch({page:4});m.patch({sort:'dataCompletedAt',direction:'desc'});await nextTick();
  expect(c.setEntryQuery.mock.lastCall[0]).toMatchObject({page:1,sort:'dataCompletedAt',direction:'desc',contains:'KEEP'});
 })


describe('server-bound report confirmation',()=>{
 it.each(['data','upload','composition'])('invalidates the confirmed preview immediately after %s changes',async kind=>{
  const {c,surface}=setup();c.previewReady=true
  vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:confirmed',name:'R1.pdf',receipt:'fresh-proof'})
  await surface.record.finalPreview();await surface.record.confirmReport()
  expect(confirmCompleteReportPreview).toHaveBeenCalledWith('R1','fresh-proof')
  expect(surface.record.reportConfirmed).toBe(true)
  if(kind==='data')c.t.remark='new'
  if(kind==='upload')c.uploaded=[{id:88,name:'replacement.pdf'}]
  if(kind==='composition')c.documentContent.compositionOptions.reportLanguage='EN'
  expect(surface.record.reportConfirmed).toBe(false)
  expect(surface.record.pdfUrl).toBe('')
  await surface.record.confirmReport()
  expect(confirmCompleteReportPreview).toHaveBeenCalledTimes(1)
 })
 it('does not confirm a background-ready PDF without opening it',async()=>{
  const {c,surface}=setup();c.previewReady=true
  await surface.record.confirmReport()
  expect(confirmCompleteReportPreview).not.toHaveBeenCalled()
  expect(surface.record.reportConfirmed).toBe(false)
 })
 it('keeps a stale-preview server rejection visible',async()=>{
  const {c,surface}=setup();c.previewReady=true
  vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:old',name:'R1.pdf',receipt:'old-proof'})
  vi.mocked(confirmCompleteReportPreview).mockRejectedValueOnce(new ApiError('报告已修改，请重新预览',200,1))
  await surface.record.finalPreview();await surface.record.confirmReport()
  expect(surface.record.reportConfirmed).toBe(false)
  expect(surface.record.error.message).toContain('报告已修改')
 })
 it('discards downloaded bytes when an upload changes before the status poll',async()=>{
  const {c,surface}=setup();c.previewReady=true
  let resolve!:(v:any)=>void
  vi.mocked(completeReportObjectUrl).mockReturnValueOnce(new Promise(r=>resolve=r))
  const pending=surface.record.finalPreview();await flushPromises()
  c.uploaded=[{id:99,name:'new.pdf'}]
  resolve({url:'blob:old',name:'R1.pdf',receipt:'old-proof'});await pending
  expect(surface.record.pdfUrl).toBe('')
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:old')
 })
})

describe('preview navigation and original list preservation',()=>{
 async function navigation(){
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/entry',component:{template:'<div />'}},{path:'/other',component:{template:'<div />'}}]})
  await router.push('/entry');await router.isReady()
  const result=setup(false,true,false,router),{c}=result
  c.previewReady=false
  c.refreshPreview.mockImplementation(async()=>{c.previewState={status:'running',sourceHash:'v1',message:'转换中'}})
  vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:result',name:'R1.pdf',receipt:'proof'})
  return {...result,router}
 }
 it('returns during generation with exact filters, sorting, and page retained, then resumes without another save',async()=>{
  const {c,surface,router}=await navigation()
  Object.assign(surface.list.draft,{contains:'XTS',status:'检测录入中',from:'2026-01-01'})
  surface.list.search();surface.list.patch({sort:'reportCode',direction:'desc'});surface.list.patch({page:'3',size:'20'})
  await nextTick()
  const query=JSON.parse(JSON.stringify(c.setEntryQuery.mock.calls.at(-1)))
  const pending=surface.record.finalPreview();await flushPromises()
  expect(surface.record.working).toBe(true);expect(surface.record.navigationBusy).toBe(false)
  const view=shallowMount(EntryRecordPresentation,{props:{context:surface.record},global:{stubs:{DataEntryTrialForm:{inheritAttrs:false,template:'<div />'}}}});wrappers.push(view)
  const back=view.findAll('button').find(button=>button.text()==='返回检测数据录入')!
  expect(back.attributes('disabled')).toBeUndefined();await back.trigger('click');await pending
  expect(c.formOpen).toBe(false)
  expect(surface.list.rows).toMatchObject({page:3,pageSize:20})
  expect(surface.list.draft).toMatchObject({contains:'XTS',from:'2026-01-01'})
  expect(surface.list.query).toMatchObject({sort:'reportCode',direction:'desc'})
  expect(c.setEntryQuery.mock.calls.at(-1)).toEqual(query)
  c.openSelectedForm.mockImplementation(()=>{c.formOpen=true})
  const reopened=surface.list.rowAction(c.entryRows[0],'报告填写');await flushPromises()
  expect(surface.record.reportTab).toBe('preview')
  expect(c.persistTestInfo).toHaveBeenCalledTimes(1)
  c.previewState={status:'ready',sourceHash:'v1',message:'完成'};c.previewReady=true
  await reopened
  expect(surface.record.pdfUrl).toBe('blob:result')
  expect(surface.record.canConfirmReport).toBe(true)
  expect(router.currentRoute.value.path).toBe('/entry')
 })
 it('leaves for another module during generation without confirming or cancelling the job',async()=>{
  const {c,surface,router}=await navigation()
  const pending=surface.record.finalPreview();await flushPromises()
  expect(await router.push('/other')).toBeUndefined()
  c.route.path='/other';await pending
  expect(c.previewState.status).toBe('running')
  expect(confirmCompleteReportPreview).not.toHaveBeenCalled()
  expect(completeReportObjectUrl).not.toHaveBeenCalled()
 })
 it('allows Back during PDF download and discards late bytes after a different report opens',async()=>{
  const {c,surface}=await navigation();c.previewReady=true
  let finish!:(value:{url:string;name:string;receipt:string})=>void
  vi.mocked(completeReportObjectUrl).mockReturnValue(new Promise(resolve=>{finish=resolve}))
  const pending=surface.record.finalPreview();await flushPromises()
  expect(surface.record.navigationBusy).toBe(false)
  surface.record.back();expect(c.formOpen).toBe(false)
  c.selected={...c.selected,reportNo:'R2'};c.formOpen=true
  finish({url:'blob:old',name:'R1.pdf',receipt:'old'});await pending
  expect(surface.record.pdfUrl).toBe('')
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:old')
  expect(surface.record.canConfirmReport).toBe(false)
 })
 it('ignores a stale status refresh after leaving and reopening another report',async()=>{
  const {c,surface}=await navigation()
  let finish!:()=>void
  c.refreshPreview.mockReturnValueOnce(new Promise<void>(resolve=>{finish=resolve}))
  c.openSelectedForm.mockImplementation(()=>{c.formOpen=true})
  const opening=surface.list.rowAction(c.entryRows[0],'报告填写');await flushPromises()
  surface.record.back();c.selected={...c.selected,reportNo:'R2'};c.formOpen=true
  c.previewState={status:'ready',sourceHash:'r2'};c.previewReady=true
  finish();await opening
  expect(surface.record.reportTab).toBe('template')
  expect(completeReportObjectUrl).not.toHaveBeenCalled()
 })
 it('protects the initial save until it finishes, then permits navigation',async()=>{
  const {c,surface,router}=await navigation()
  let finish!:(value:boolean)=>void
  c.persistTestInfo.mockReturnValue(new Promise(resolve=>{finish=resolve}))
  const pending=surface.record.finalPreview();await flushPromises()
  surface.record.back();expect(c.formOpen).toBe(true)
  expect(await router.push('/other')).toBeDefined();expect(router.currentRoute.value.path).toBe('/entry')
  finish(true);await flushPromises()
  surface.record.back();await pending;expect(c.formOpen).toBe(false)
 })
 it.each(['saving','uploading','compositionSaving','attachmentDeleting','returnBusy'])('blocks navigation during %s but not after it completes',async(key)=>{
  const {c,surface,router}=await navigation();c[key]=true
  surface.record.back();expect(c.formOpen).toBe(true)
  expect(await router.push('/other')).toBeDefined();expect(router.currentRoute.value.path).toBe('/entry')
  c[key]=false
  expect(await router.push('/other')).toBeUndefined()
 })
 it('requires explicit discard for unsaved edits when switching modules',async()=>{
  const {c,surface,router}=await navigation()
  await surface.record.save();c.t.remark='unsaved'
  expect(await router.push('/other')).toBeDefined()
  expect(surface.record.discard).toBe('/other')
  surface.record.discard=''
  expect(router.currentRoute.value.path).toBe('/entry')
  await router.push('/other');surface.record.abandon();await flushPromises()
  expect(router.currentRoute.value.path).toBe('/other')
 })
 it('keeps upload and confirmation controls locked while exposing the generation Back button',async()=>{
  const {c,surface}=await navigation()
  const pending=surface.record.finalPreview();await flushPromises()
  surface.record.reportOnly=true;surface.record.reportTab='preview'
  const view=shallowMount(EntryRecordPresentation,{props:{context:surface.record},global:{stubs:{DataEntryReportFiles:false,DataEntryPreview:{template:'<div><slot name="empty" /></div>'},DataEntryTrialForm:{inheritAttrs:false,template:'<div />'}}}});wrappers.push(view)
  const back=view.findAll('button').find(button=>button.text()==='返回列表')!
  expect(back.element.matches(':disabled')).toBe(false)
  expect(view.get('#report-tab-files').element.matches(':disabled')).toBe(true)
  expect(view.get('#entry-report-layout').element.matches(':disabled')).toBe(true)
  expect(view.text()).not.toContain('正在确认')
  expect(view.text()).toContain('后台继续生成')
  c.uploading=true;await nextTick()
  expect(back.element.matches(':disabled')).toBe(true)
  c.uploading=false
  c.formOpen=false;await pending
 })
})

describe('background preview across route remount',()=>{
 it.each(['running','ready'] as const)('returns to the same server task when it is %s, with no extra prepare or save',async(statusOnReturn)=>{
  vi.useFakeTimers()
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/entry',component:{template:'<div />'}},{path:'/other',component:{template:'<div />'}}]})
  await router.push('/entry')
  const first=setup(false,true,false,router)
  let phase:'running'|'ready'='running'
  vi.mocked(completePreviewState).mockImplementation(async()=>({status:phase,sourceHash:'unchanged-source',message:phase}))
  const flowHost=mount(defineComponent({setup(){
   const flow=useCompletePreview(computed(()=>first.c.selected.reportNo),computed(()=>first.c.reportDetailView),computed(()=>first.c.formOpen))
   first.c.previewState=flow.state;first.c.previewReady=flow.ready;first.c.refreshPreview=flow.refresh
   return()=>null
  }}));wrappers.push(flowHost)
  await flushPromises()
  const generating=first.surface.record.finalPreview();await flushPromises()
  expect(first.surface.record.navigationBusy).toBe(false)
  await router.push('/other');first.parent.unmount();flowHost.unmount();await generating
  phase=statusOnReturn
  await router.push('/entry')
  const second=setup(false,true,false,router)
  second.c.formOpen=false
  const reopenedHost=mount(defineComponent({setup(){
   const flow=useCompletePreview(computed(()=>second.c.selected.reportNo),computed(()=>second.c.reportDetailView),computed(()=>second.c.formOpen))
   second.c.previewState=flow.state;second.c.previewReady=flow.ready;second.c.refreshPreview=flow.refresh
   return()=>null
  }}));wrappers.push(reopenedHost)
  second.c.openSelectedForm.mockImplementation(()=>{second.c.formOpen=true})
  vi.mocked(completeReportObjectUrl).mockResolvedValue({url:'blob:resumed',name:'R1.pdf',receipt:'same-source-proof'})
  const opening=second.surface.list.rowAction(second.c.entryRows[0],'报告填写');await flushPromises()
  expect(second.surface.record.reportTab).toBe('preview')
  phase='ready';await vi.advanceTimersByTimeAsync(3000);await opening
  expect(second.surface.record.pdfUrl).toBe('blob:resumed')
  expect(second.c.persistTestInfo).not.toHaveBeenCalled()
  expect(vi.mocked(completePreviewState).mock.calls.every(call=>call[2]!==true)).toBe(true)
  await second.surface.record.confirmReport()
  expect(confirmCompleteReportPreview).toHaveBeenCalledWith('R1','same-source-proof')
  second.c.t.remark='changed after preview'
  expect(second.surface.record.canConfirmReport).toBe(false)
  expect(second.surface.record.pdfUrl).toBe('')
 })
})

it.each(['待打印','待发放','已发放','已归档'])('does not refresh completed %s through picker services',async status=>{
 const {c,services}=setup();c.selected.status=status
 vi.mocked(fetchReportEquipment).mockClear();vi.mocked(fetchAuthorizedReportPeople).mockClear()
 await services.entryDetail('R1')
 await services.entryPeople('R1',{role:'reviewer',page:1,pageSize:10})
 expect(fetchReportEquipment).not.toHaveBeenCalled()
 expect(fetchAuthorizedReportPeople).not.toHaveBeenCalled()
})
