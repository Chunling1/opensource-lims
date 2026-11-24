import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {shallowMount,flushPromises,type VueWrapper} from '@vue/test-utils'
import Form from '@/components/PipelineWizard.vue'
import {fetchCapabilityItems} from '@/services/pipeline'
import {searchStdLib} from '@/services/quality'
const api=vi.hoisted(()=>({detail:vi.fn(),copy:vi.fn(),edit:vi.fn(),preview:vi.fn()}))
vi.mock('@/services/reports',()=>({fetchReportDetail:api.detail,fetchSampleFormImage:vi.fn()}))
vi.mock('@/services/sampleCopies',()=>({fetchSampleCopySource:api.copy,fetchSampleCopyPage:vi.fn().mockResolvedValue({rows:[],total:0})}))
vi.mock('@/services/pipeline',async original=>({...await original<typeof import('@/services/pipeline')>(),fetchEntrustOptions:vi.fn().mockResolvedValue([]),fetchDepartments:vi.fn().mockResolvedValue([]),fetchDerivableReports:vi.fn().mockResolvedValue([]),fetchCapabilityItems:vi.fn().mockResolvedValue([]),editReportInPlace:api.edit,previewSampleEntrust:api.preview}))
vi.mock('@/stores/session',()=>({useSessionStore:()=>({dataScope:{department:'QA'},userName:'QA',can:()=>true,canAction:()=>true,canOverrideWorkflowDate:false,canCorrectBusinessData:true,account:'demo_admin'})}))
vi.mock('element-plus',async original=>({...await original<typeof import('element-plus')>(),ElMessage:{error:vi.fn(),warning:vi.fn(),success:vi.fn()},ElMessageBox:{confirm:vi.fn()}}))
vi.mock('@/services/quality',()=>({searchStdLib:vi.fn().mockResolvedValue([]),searchStdLibPage:vi.fn().mockResolvedValue({rows:[]})}))
let wrapper:VueWrapper
const record=()=>({reportNo:'LAB-QA-01',sampleNo:'QA-01',sampleRegState:'登记完成',rawSample:{sampleName:'样品乙',projectList:['温度'],testBases:[]},summary:[],entrustSnapshot:{entrustNo:'WT-QA',contractNo:'OLD',projectName:'原合同',projectType:'虚拟框架',info:{entrustDate:'2026-09-10',erpType:'虚拟框架'}}})
async function start(){wrapper=shallowMount(Form,{props:{modelValue:false,pageView:true,mode:'samples',changeReportNo:'LAB-QA-01',inPlace:true},global:{stubs:{ElInput:{name:'ElInput',props:['modelValue','disabled'],template:'<input :value="modelValue" :disabled="disabled" />'},SampleFormSurface:{template:'<section><slot name="header"/><slot/><slot name="footer"/></section>'}},directives:{loading:{}},config:{warnHandler:()=>undefined}}});await wrapper.setProps({modelValue:true});await flushPromises();return(wrapper.vm as any).$.setupState}
beforeEach(()=>{vi.clearAllMocks();api.detail.mockResolvedValue(record());api.edit.mockResolvedValue({reportNo:'LAB-QA-01'})})
afterEach(()=>wrapper?.unmount())
it('requires the explicit administrator button, copies the selected contract into this sample, and cancels mode without leaking edits',async()=>{
 const x=await start();expect(x.readOnly).toBe(true);expect(wrapper.getComponent({name:'ContractSelection'}).props('disabled')).toBe(true)
 const button=()=>wrapper.findAll('button').find(b=>b.text().includes('管理员编辑'))!
 await button().trigger('click');expect(x.readOnly).toBe(false);expect(button().attributes('aria-pressed')).toBe('true')
 const contract:any={agreementNo:'NEW',erpType:'标准合同',projectCode:'KD-NEW',client:'合同甲方',projectName:'新合同项目'}
 wrapper.getComponent({name:'ContractSelection'}).vm.$emit('picked',contract);await flushPromises()
 expect(x.sampleEntrustPayload().contractNo).toBe('NEW');expect(x.sampleEntrustPayload().sourceEntrustNo).toBe('WT-QA')
 expect(x.sampleEntrustPayload().info.erpProjectNo).toBe('KD-NEW');expect(x.sampleContractPartyALocked).toBe(true)
 expect(api.edit).not.toHaveBeenCalled()
 await button().trigger('click');expect(x.sampleEntrustPayload().contractNo).toBe('OLD');expect(x.readOnly).toBe(true)
})
it('does not let the original entrust override a sample selection when building a save payload, and resets on reopening',async()=>{
 const x=await start();x.entrustOptions=[{entrustNo:'WT-QA',contractNo:'OLD'}]
 await x.toggleAdministratorEditing();x.onSampleContractSelected({agreementNo:'NEW',erpType:'不回传外部ERP合同',client:'甲方',projectName:'项目'})
 expect(x.currentSampleItem().entrustSnapshot.contractNo).toBe('NEW')
 await wrapper.setProps({modelValue:false});await wrapper.setProps({modelValue:true});await flushPromises()
 expect(x.administratorEditing).toBe(false);expect(x.sampleEntrust.contractNo).toBe('OLD')
})

it('retains saved registrar during editing and enables explicit administrator revision only',async()=>{
 const data=record();Object.assign(data.entrustSnapshot,{owner:'原登记人',department:'原部门'});api.detail.mockResolvedValue(data)
 const x=await start();expect(x.sampleEntrust.handler).toBe('原登记人');expect(x.sampleEntrust.handleDept).toBe('原部门')
 const field=(text:string)=>wrapper.findAllComponents({name:'RegistrarPicker'}).find(c=>c.props('value')===text)!
 expect(field('原登记人').props('disabled')).toBe(true)
 await x.toggleAdministratorEditing();expect(field('原登记人').props('disabled')).toBe(false)
 expect(x.sampleEntrustPayload().owner).toBe('原登记人')
 field('原登记人').vm.$emit('picked',{id:195,name:'修订登记人',account:'original',departmentId:7,department:'修订部门'});await flushPromises()
 expect(x.sampleEntrustPayload().info.sampleRegistrarUserId).toBe('195')
 expect(x.sampleEntrustPayload().info.sampleRegistrarDepartmentId).toBe('7')
 expect(x.sampleEntrustPayload().owner).toBe('修订登记人');expect(x.sampleEntrustPayload().department).toBe('修订部门')
 await x.toggleAdministratorEditing();expect(x.sampleEntrustPayload().owner).toBe('原登记人')
})
it('displays confirmed contract number separately from legacy project fields and resets on reopening',async()=>{
 api.detail.mockResolvedValue({...record(),erpContractNo:'PO-CONFIRMED'})
 const x=await start();expect(x.sampleConfirmedContractNo).toBe('PO-CONFIRMED')
 expect(wrapper.findAllComponents({name:'ElInput'}).some(c=>c.props('modelValue')==='PO-CONFIRMED')).toBe(true)
 expect(JSON.stringify(x.sampleEntrustPayload())).not.toContain('PO-CONFIRMED')
 api.detail.mockResolvedValue(record());await wrapper.setProps({modelValue:false});await wrapper.setProps({modelValue:true});await flushPromises()
 expect(x.sampleConfirmedContractNo).toBe('')
})
