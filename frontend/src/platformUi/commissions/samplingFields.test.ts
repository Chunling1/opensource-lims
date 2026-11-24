import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {shallowMount,flushPromises,type VueWrapper} from '@vue/test-utils'
import Form from '@/components/PipelineWizard.vue'
const api=vi.hoisted(()=>({detail:vi.fn(),copy:vi.fn(),edit:vi.fn(),preview:vi.fn()}))
vi.mock('@/services/reports',()=>({fetchReportDetail:api.detail,fetchSampleFormImage:vi.fn()}))
vi.mock('@/services/sampleCopies',()=>({fetchSampleCopySource:api.copy,fetchSampleCopyPage:vi.fn().mockResolvedValue({rows:[],total:0})}))
vi.mock('@/services/pipeline',async original=>({...await original<typeof import('@/services/pipeline')>(),fetchEntrustOptions:vi.fn().mockResolvedValue([]),fetchDepartments:vi.fn().mockResolvedValue([]),fetchDerivableReports:vi.fn().mockResolvedValue([]),fetchCapabilityItems:vi.fn().mockResolvedValue([]),editReportInPlace:api.edit,previewSampleEntrust:api.preview}))
vi.mock('@/stores/session',()=>({useSessionStore:()=>({dataScope:{department:'QA'},userName:'QA',can:()=>true,canAction:()=>true,canOverrideWorkflowDate:false})}))
vi.mock('element-plus',async original=>({...await original<typeof import('element-plus')>(),ElMessage:{error:vi.fn(),warning:vi.fn(),success:vi.fn()},ElMessageBox:{confirm:vi.fn()}}))
vi.mock('@/services/quality',()=>({searchStdLib:vi.fn().mockResolvedValue([]),searchStdLibPage:vi.fn().mockResolvedValue({rows:[]})}))
let wrapper:VueWrapper
const record=()=>({reportNo:'LAB-QA-01',sampleNo:'QA-01',sampleRegState:'登记中',rawSample:{sampleName:'样品乙',engineeringName:'幕墙甲',testCategory:'抽样',testBases:[]},summary:[],entrustSnapshot:{entrustNo:'WT-QA',projectName:'合同丙',info:{entrustDate:'2026-09-10'}}})
async function start(readOnly=false){wrapper=shallowMount(Form,{props:{modelValue:false,pageView:true,mode:'samples',changeReportNo:'LAB-QA-01',inPlace:true,readOnly},global:{stubs:{SampleFormSurface:{template:'<section><slot/><slot name="footer"/></section>'},TemplateEditableSelect:false},directives:{loading:{}},config:{warnHandler:()=>undefined}}});await wrapper.setProps({modelValue:true});await flushPromises();return(wrapper.vm as any).$.setupState}
beforeEach(()=>{vi.clearAllMocks();api.detail.mockResolvedValue(record());api.copy.mockResolvedValue(record());api.edit.mockResolvedValue({reportNo:'LAB-QA-01'})})
afterEach(()=>wrapper?.unmount())
it('initializes arrival date from the default delivery date',async()=>{
 const x=await start();Object.assign(x.s,x.sampleBlank());expect(x.s.sendDate).toBeTruthy();expect(x.s.sampleArrivalDate).toBe(x.s.sendDate)
})
it.each(['', '2026-09-01'])('repairs a loaded arrival date %s even when delivery date does not change',async arrival=>{
 const x=await start();const delivery=x.s.sendDate
 api.detail.mockResolvedValue({...record(),rawSample:{...record().rawSample,sendDate:delivery,sampleArrivalDate:arrival}})
 await wrapper.setProps({modelValue:false});await wrapper.setProps({modelValue:true});await flushPromises()
 expect(x.s.sampleArrivalDate).toBe(delivery)
})
it('keeps delivery changes, clearing and same-day reset synchronized before saving',async()=>{
 const x=await start();x.s.sendDate='2026-09-12';expect(x.currentSampleItem().sampleArrivalDate).toBe('2026-09-12')
 x.s.sendDate='';expect(x.currentSampleItem().sampleArrivalDate).toBe('')
 Object.assign(x.s,x.sampleBlank());expect(x.s.sampleArrivalDate).toBe(x.s.sendDate)
})
it('copies legacy dates using delivery as the source without changing the copied record',async()=>{
 const x=await start();const source={...record(),rawSample:undefined,summary:[{title:'送样信息',fields:[['送样日期','2026-09-12']]},{title:'抽样信息',fields:[['样品到达日期','2026-09-01'],['任务来源','甲方现场委托']]}]}
 api.copy.mockResolvedValue(source);x.copyDialogOpen=true;await x.copyFromSample({reportNo:'LAB-QA-02',sampleNo:'QA-02'})
 expect(x.s.sampleArrivalDate).toBe('2026-09-12');expect(x.s.taskSource).toBe('甲方现场委托');expect(source.summary[1]!.fields[0]![1]).toBe('2026-09-01')
})
it('retains typed task source on blur, saves raw data and summary, and reopens the saved values',async()=>{
 const x=await start();x.sampleEntrustNo='WT-QA';x.s.sendDate='2026-09-12'
 const input=wrapper.get('input[aria-label="任务来源"]');await input.setValue('甲方委托 / QA-中文');await input.trigger('blur')
 expect(x.s.taskSource).toBe('甲方委托 / QA-中文')
 await x.saveSampleChange('save');expect(api.edit).toHaveBeenCalledOnce()
 const detail=api.edit.mock.calls.at(-1)![1].fullDetail
 expect(detail.rawSample).toMatchObject({sendDate:'2026-09-12',sampleArrivalDate:'2026-09-12',taskSource:'甲方委托 / QA-中文'})
 expect(detail.summary.find((s:any)=>s.title==='抽样信息').fields).toEqual(expect.arrayContaining([['样品到达日期','2026-09-12'],['任务来源','甲方委托 / QA-中文']]))
 api.detail.mockResolvedValue({...record(),...detail});await wrapper.setProps({modelValue:false});await wrapper.setProps({modelValue:true});await flushPromises()
 expect(x.s.taskSource).toBe('甲方委托 / QA-中文');expect(x.s.sampleArrivalDate).toBe('2026-09-12')
 await wrapper.get('input[aria-label="任务来源"]').setValue('');await x.saveSampleChange('save')
 expect(api.edit.mock.calls.at(-1)![1].fullDetail.rawSample.taskSource).toBe('')
})
it('keeps task source choices usable and arrival date readonly',async()=>{
 const x=await start();const field=wrapper.getComponent({name:'TemplateEditableSelect'})
 const option=field.findAll('.dropdown-menu button')[0]!;await option.trigger('click');expect(x.s.taskSource).toBe(option.text())
 expect(wrapper.get('input[aria-label="样品到达日期"]').attributes()).toHaveProperty('readonly')
})
it('does not save changes from a readonly sample',async()=>{
 await start(true);expect(wrapper.get('input[aria-label="任务来源"]').attributes()).toHaveProperty('readonly')
 const x=(wrapper.vm as any).$.setupState;await x.saveSampleChange('save');expect(api.edit).not.toHaveBeenCalled()
})


it.each(['CNAS','CMA + CNAS'])('preserves NCSA seal choice %s through load/save/reopen',async seal=>{
 api.detail.mockResolvedValue({...record(),rawSample:{...record().rawSample,centerPrefix:'NCSA',seal}})
 const x=await start();expect(x.s.seal).toBe(seal);x.sampleEntrustNo='WT-QA';x.s.sendDate='2026-09-12'
 await x.saveSampleChange('save');expect(api.edit).toHaveBeenCalledOnce()
 const detail=api.edit.mock.calls.at(-1)![1].fullDetail;expect(detail.rawSample.seal).toBe(seal)
 api.detail.mockResolvedValue({...record(),...detail});await wrapper.setProps({modelValue:false});await wrapper.setProps({modelValue:true});await flushPromises()
 expect(x.s.seal).toBe(seal)
})
