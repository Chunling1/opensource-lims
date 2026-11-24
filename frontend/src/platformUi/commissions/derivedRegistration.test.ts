import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {shallowMount, flushPromises, type VueWrapper} from '@vue/test-utils'
import Form from '@/components/PipelineWizard.vue'
import {fetchSampleCopySource} from '@/services/sampleCopies'
import {fetchReportDetail} from '@/services/reports'
import SourceReportSelect from './SourceReportSelect.vue'
import {createReport} from '@/services/pipeline'
vi.mock('@/services/pipeline', async original => ({...await original<typeof import('@/services/pipeline')>(),
 validateSampleConfiguration:vi.fn().mockResolvedValue({ready:true,errors:[]}),
 fetchEntrustOptions: vi.fn().mockResolvedValue([]), fetchContractSelectionPage: vi.fn().mockResolvedValue({rows:[]}),
 fetchHandleDepartments: vi.fn().mockResolvedValue({rows:[]}), fetchDepartments: vi.fn().mockResolvedValue([]),
 createReport: vi.fn().mockResolvedValue({reportNo:'LAB-2026YP-0017(E)',sampleNo:'2026YP-0017',editVersion:1})}))
vi.mock('@/services/reports',()=>({fetchReportDetail:vi.fn(),fetchSampleFormImage:vi.fn()}))
vi.mock('@/services/quality', () => ({searchStdLib:vi.fn().mockResolvedValue([{id:11,code:'STD',name:'中文'},{id:12,code:'STD',name:'English'}]),searchStdLibPage:vi.fn()}))
vi.mock('@/services/sampleCopies', () => ({fetchSampleCopySource:vi.fn(),fetchSampleCopyPage:vi.fn()}))
vi.mock('@/stores/session', () => ({useSessionStore:()=>({dataScope:{department:'CURRENT'},userName:'QA',account:'qa',can:()=>true,canAction:()=>true})}))
vi.mock('element-plus', async original => ({...await original<typeof import('element-plus')>(),ElMessage:{error:vi.fn(),warning:vi.fn(),success:vi.fn()}}))
let w:VueWrapper
const reportNo='LAB-2026YP-0017'
const source = (no=reportNo) => ({reportNo:no,sampleNo:'2026YP-0017',department:'SOURCE',summary:[],requestedSeal:'CNAS',
 rawSample:{schemeCode:'YP',schemeName:'焓差',testPlan:'焓差(YP)',testDept:'SOURCE',sampleName:'完整样品',spec:'ABC',
 trademarkImage:'data:image/png;base64,AA',productionDates:[{name:'室内机',precision:'day',value:'2026-01-01',note:''}],sendDate:'2026-02-01',
 testBases:['STD'],testBasis:'STD',standardItemIds:[11,12],standardRecords:[{id:11,code:'STD'},{id:12,code:'STD'}],reportCategory:'普通',reportLanguage:'CN',
 innerRemark:'保留备注',testLocation:'原完整地址',locationWorkflowVersion:0,manualCapabilityItems:['温度'],projectList:['温度'],subItems:[{projectName:'检测',dept:'SOURCE',businessCategory:'检测',amount:'100',receivedAmount:'0',paymentDescription:'按合同'}],stdPrice:'100',reportType:'产品报告',centerPrefix:'NCSA'},
 entrustSnapshot:{sourceEntrustId:17,amount:'1234',entrustNo:'WT-SOURCE',contractNo:'ACTUAL',client:'客户',projectName:'工程',projectType:'虚拟框架',department:'SOURCE',owner:'原登记人',info:{entrustDate:'2026-02-01',clientPhone:'123',payWay:'BT'}}})
async function start(){
 w=shallowMount(Form,{props:{modelValue:false,mode:'samples',pageView:true},global:{renderStubDefaultSlot:true,directives:{loading:{}},config:{warnHandler:()=>undefined}}})
 await w.setProps({modelValue:true});await flushPromises()
 const x=(w.vm as any).$.setupState
 x.s.reportCategory='英文';x.s.baseReportNo=reportNo
 return x
}
beforeEach(()=>vi.clearAllMocks());afterEach(()=>w?.unmount())
it('inherits complete form and entrust, keeps English identity and locks source scheme',async()=>{
 const d=source();vi.mocked(fetchSampleCopySource).mockResolvedValue(d as any)
 const x=await start();await x.selectSourceReport(d);await flushPromises()
 expect(x.s.sampleName).toBe('完整样品');expect(x.s.trademarkImage).toContain('base64')
 expect(x.s.standardItemIds).toEqual([11,12]);expect(x.s.productionDates).toEqual(d.rawSample.productionDates)
 expect(x.s.sendDate).toBe('2026-02-01');expect(x.sampleEntrust.clientPhone).toBe('123')
 expect(x.sampleEntrust.contractNo).toBe('ACTUAL');expect(x.sampleEntrustNo).toBe('WT-SOURCE')
 expect(x.s.reportLanguage).toBe('EN');expect(x.sampleReportNo).toBe(reportNo+'(E)')
 expect(x.s.testDept).toBe('SOURCE');expect(x.schemeLocked).toBe(true)
 await x.pickScheme({code:'OTHER',dept:'OTHER'});expect(x.s.schemeCode).toBe('YP')
 x.s.sampleName='Translated';expect(d.rawSample.sampleName).toBe('完整样品')
})
it('ignores stale source responses after another source is selected',async()=>{
 let resolveFirst:any;vi.mocked(fetchSampleCopySource).mockImplementationOnce(()=>new Promise(r=>resolveFirst=r)).mockResolvedValueOnce(source('OTHER') as any)
 const x=await start();const first=x.selectSourceReport(source());x.s.baseReportNo='OTHER'
 await x.selectSourceReport(source('OTHER'));resolveFirst(source());await first
 expect(x.s.baseReportNo).toBe('OTHER');expect(x.sourceSample.reportNo).toBe('OTHER')
})
it('blocks draft submission after source loading failure',async()=>{
 vi.mocked(fetchSampleCopySource).mockRejectedValue(new Error('读取失败'))
 const x=await start();await x.selectSourceReport(source());await x.saveSamples('登记中')
 expect(x.sampleFormError).toBe('读取失败');expect(createReport).not.toHaveBeenCalled()
})

it.each(['登记中','登记完成'])('submits the inherited full form through %s',async state=>{
 const d=source();vi.mocked(fetchSampleCopySource).mockResolvedValue(d as any)
 const x=await start()
 x.sampleEntrustNo='WT-TEMP';await flushPromises()
 const picker=w.findComponent(SourceReportSelect)
 picker.vm.$emit('update:modelValue',reportNo);picker.vm.$emit('selected',d)
 await flushPromises();await x.saveSamples(state)
 expect(createReport,JSON.stringify({errors:x.sampleConfigErrors,error:x.sampleFormError,loading:x.sampleFormLoading,blocked:x.sampleImageBlocked})).toHaveBeenCalledTimes(1)
 const payload=vi.mocked(createReport).mock.calls[0][0]
 expect(payload.department).toBe('SOURCE');expect(payload.entrustNo).toBe('WT-SOURCE')
 expect(payload.reportCategory).toBe('英文');expect(payload.baseReportNo).toBe(reportNo)
 expect(payload.detail.rawSample).toMatchObject({sampleNo:'2026YP-0017',schemeCode:'YP',testDept:'SOURCE',testRoom:'SOURCE',reportLanguage:'EN',innerRemark:'保留备注',testLocation:'原完整地址'})
 expect(payload.detail.entrustSnapshot!.info.clientPhone).toBe('123')
 expect(payload.detail.entrustSnapshot!.amount).toBe('1234');expect(payload.detail.entrustSnapshot!.sourceEntrustId).toBe(17)
})
it('reopens saved English translation without reloading or overwriting from the parent',async()=>{
 const d=source();vi.mocked(fetchReportDetail).mockResolvedValue({...d,reportNo:reportNo+'(E)',mainReportNo:reportNo,reportCategory:'英文',sampleRegState:'登记中',rawSample:{...d.rawSample,sampleName:'Translated sample',reportLanguage:'EN'}} as any)
 const x=await start();await w.setProps({changeReportNo:reportNo+'(E)',inPlace:true});await flushPromises()
 expect(x.s.sampleName).toBe('Translated sample');expect(x.s.reportCategory).toBe('英文')
 expect(x.s.baseReportNo).toBe(reportNo);expect(x.sampleAutoNo).toBe('2026YP-0017');expect(x.schemeLocked).toBe(true)
 expect(fetchSampleCopySource).not.toHaveBeenCalled()
})
it('retries a failed read and restores historical summary fields with authoritative source department',async()=>{
 const d={...source(),rawSample:undefined,summary:[{title:'送样信息',fields:[['样品名称','历史名称'],['送样日期','2026-02-01']]},{title:'实验信息',fields:[['检测方案','焓差(YP)']]}]}
 vi.mocked(fetchSampleCopySource).mockRejectedValueOnce(new Error('失败')).mockResolvedValueOnce(d as any)
 const x=await start();await x.selectSourceReport(source());expect(w.text()).toContain('重新读取原报告')
 await x.selectSourceReport(source());expect(x.sampleFormError).toBe('')
 expect(x.s.sampleName).toBe('历史名称');expect(x.s.schemeCode).toBe('YP');expect(x.s.testDept).toBe('SOURCE')
})

it('switching back to ordinary registration never submits a stale parent association',async()=>{
 const d=source();vi.mocked(fetchSampleCopySource).mockResolvedValue(d as any)
 const x=await start();await x.selectSourceReport(d);x.s.reportCategory='普通';await x.saveSamples('登记中')
 expect(vi.mocked(createReport).mock.calls[0][0].baseReportNo).toBeUndefined()
})


it('restores a missing raw department from saved report metadata on reopening',async()=>{
 const d=source();vi.mocked(fetchReportDetail).mockResolvedValue({...d,reportNo:reportNo+'(E)',mainReportNo:reportNo,reportCategory:'英文',sampleRegState:'登记中',rawSample:{...d.rawSample,testDept:'',testRoom:'',sampleName:'Translated sample'}} as any)
 const x=await start();await w.setProps({changeReportNo:reportNo+'(E)',inPlace:true});await flushPromises()
 expect(x.s.testDept).toBe('SOURCE');expect(x.s.testRoom).toBe('SOURCE')
 expect(x.s.sampleName).toBe('Translated sample');expect(x.schemeLocked).toBe(true)
})
