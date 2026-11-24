import {afterEach,describe,expect,it,vi} from 'vitest'
vi.mock('@/stores/session',()=>({useSessionStore:()=>({canOverrideWorkflowDate:false})}))
import {defineComponent,reactive,inject} from 'vue'
import {mount,flushPromises} from '@vue/test-utils'
vi.mock('@/services/customerDirectory',()=>({fetchCustomerPage:vi.fn(async()=>({rows:[],total:0,page:1,size:10}))}))
vi.mock('@/services/pipeline',()=>({fetchSchemes:vi.fn(async()=>[])}))
vi.mock('@/services/quality',()=>({searchStdLib:vi.fn(async()=>[]),searchStdLibPage:vi.fn(async()=>({rows:[{code:'GB1',controlledNo:'K1',sites:['A'],cma:true}],total:31,page:2,size:10}))}))
vi.mock('@/services/businessSupplement',()=>({fetchSubprojects:vi.fn(async()=>[]),fetchErpSubprojects:vi.fn(async()=>({rows:[]}))}))
vi.mock('@/services/technicalSubprojects',()=>({listTechnicalSubprojects:vi.fn(async()=>[{id:8,code:'T8',name:'目录项目',projectName:'项目',revision:2,parameters:[]}])}))
import {searchStdLibPage} from '@/services/quality'
import {createRegistrationFormPresentation,commissionBindings} from './registrationFormPresentation'
import Page from './RegistrationFormPresentation.vue'
import {isLegacySystemCover} from '../reportAttachments'
const wrappers:any[]=[]
afterEach(()=>wrappers.splice(0).forEach(w=>w.unmount()))
function context(mode='entrust'){
 return reactive<any>({mode,modelValue:true,readOnly:false,submitting:false,sampleFormLoading:false,sampleFormError:'',legacyMigrationHold:false,route:{path:'/inspection/entrust/registration'},session:{userName:'测试',dataScope:{department:'测试部'}},f:{contractNo:'P001',erpContractNo:'P001',erpProjectNo:'C001',client:'客户',handler:'登记人'},sampleEntrust:{contractNo:'P002',erpContractNo:'P002',erpProjectNo:'',client:'样品客户'},s:{schemeCode:'G',schemeName:'方案',projectList:['参数'],subItems:[],testBases:[],standardJudge:'',reportType:'产品报告',centerPrefix:'NCSA',reportLanguage:'CN',reportTemplateVariant:'Standard',reportCategory:'普通',baseReportNo:'',capabilityEntryIds:[],capabilitySnapshots:[],manualCapabilityItems:[],sampleAmount:'2'},selectedBasisCodes:()=>[],selectedBasisIds:()=>[],onBasisIdsChange:vi.fn(),splitBasisValues:(s:any)=>String(s||'').split('；').filter(Boolean),syncBasisFields:vi.fn(),onBasesChange:vi.fn(),onPickContract:vi.fn(),onPickClient:vi.fn(),onPickSampleClient:vi.fn(),visibleClaimedContracts:[],entrustOptions:[],stdOptions:[],mergeStandardOptions:vi.fn(),handleDepts:[{name:'测试部',fullName:'机构 / 测试部'}],centers:[{name:'空调中心',prefix:'NCSA',types:['产品报告']},{name:'示例检测',prefix:'LAB',types:['产品报告','校准报告']}],centerTypes:['产品报告'],derivableReports:[],schemeLocked:false,saveEntrust:vi.fn(async()=>{}),saveSampleDraft:vi.fn(async()=>true),requestClose:vi.fn(),dialogTitle:'新增委托',SAMPLE_OPTS:{},sampleDepartmentOptions:[],onOnsiteTestingChange:vi.fn(),syncParameterLocations:vi.fn(),onManualCapabilityChange:vi.fn(),capabilityOptions:[],capabilityLoading:false,capabilityError:'',loadCapabilityItems:vi.fn(),confirmCapabilitySelection:vi.fn(),hasUnsavedChanges:false})
}
function setup(c:any){let p:any;wrappers.push(mount(defineComponent({setup(){p=createRegistrationFormPresentation(c);return()=>null}})));return p}
describe('full registration template data adapter',()=>{
 it('merges historical quantity and unit and clears the legacy unit on edit',()=>{const c=context('samples');c.s.unit='台';const p=setup(c);expect(p.form.quantity).toBe('2 台');expect(c.s.sampleAmount).toBe('2');p.form.quantity='2台、3套';expect(c.s.sampleAmount).toBe('2台、3套');expect(c.s.unit).toBe('');expect(p.form.quantity).toBe('2台、3套');expect(p.backendSchema.sections.flatMap((s:any)=>s.fields).some((f:any)=>f.id==='platform-unit')).toBe(false);c.readOnly=true;p.form.quantity='9台';expect(c.s.sampleAmount).toBe('2台、3套')})
 it('reopens merged, cleared and already suffixed quantities without duplicate units',()=>{const c=context('samples');c.s.sampleAmount='3台';c.s.unit='台';const p=setup(c);expect(p.form.quantity).toBe('3台');p.form.quantity='';expect(p.form.quantity).toBe('');expect(c.s.unit).toBe('');c.s.sampleAmount='0.5 m²';expect(p.form.quantity).toBe('0.5 m²')})

 it('retains six approved backend fields and technical snapshots',async()=>{const c=context('samples');c.s.detectionSubprojects=[{id:8,code:'T8',name:'历史项目',projectName:'项目',revision:1,parameters:[{name:'原参数',method:'原方法'}],extension:'保留'}];const p=setup(c);await flushPromises();const fields=p.backendSchema.sections[0].fields;for(const key of ['deadline','sampleArrivalDate','sampleGrade','sealChecker']){const f=fields.find((x:any)=>x.id==='platform-'+key);f.binding.set(c,'test:'+key);expect(c.s[key]).toBe('test:'+key)}expect(fields.find((x:any)=>x.id==='platform-seal').disabled).toBe(false);p.chooseTechnical(p.technicalLabels[0]);expect(c.s.detectionSubprojects[0]).toMatchObject({revision:1,extension:'保留',parameters:[{method:'原方法'}]});p.chooseTechnical('无效选项');expect(c.s.detectionSubprojects).toHaveLength(1);c.readOnly=true;p.chooseTechnical('');expect(c.s.detectionSubprojects).toHaveLength(1)})
 it('uses server pagination and qualification filter without losing later standards',async()=>{let service:any;const child=defineComponent({setup(){service=inject('platform-registration-services');return()=>null}});wrappers.push(mount(defineComponent({components:{child},setup(){createRegistrationFormPresentation(context('samples'))},template:'<child />'})));const page=await service.testBases({page:2,pageSize:10,qualification:'CMA',ownDepartment:true});expect(searchStdLibPage).toHaveBeenCalledWith('',undefined,expect.objectContaining({page:2,size:10,scopeFilter:'cma'}));expect(page.total).toBe(31);expect(page.items[0].controlNumber).toBe('K1');expect(page.items[0].location).toBe('授权场所：A')})
 it('refreshes asynchronously loaded department choices and delegates failed-load retry',async()=>{const c=context('samples');c.retryLoad=vi.fn();const p=setup(c);c.sampleDepartmentOptions=['第二部门'];expect(p.sampleOptions.choices.testingDepartment).toEqual(['第二部门']);p.load();expect(c.retryLoad).toHaveBeenCalledOnce()})
 it('separates actual contract number and project number without changing backend key',()=>{const c=context(),p=setup(c);expect(p.form.contract).toBe('C001');expect(p.form.erpContract).toBe('P001');expect(p.form.contractId).toBe('P001');c.f.erpProjectNo='';expect(p.form.contract).toBe('');expect(p.form.erpContract).toBe('P001');p.form.contractId='P003';expect(c.f.contractNo).toBe('P003');expect(c.onPickContract).toHaveBeenCalledWith('P003')})
 it('enables an initially empty assessment and preserves subproject source metadata',()=>{const c=context('samples');c.s.subItems=[{projectName:'项目',dept:'原部门',businessCategory:'业务',amount:'5',source:'erp',catalogCode:'K001',sourceProof:'proof'}];const p=setup(c);p.form.details.useAssessmentStandard=true;expect(p.form.details.useAssessmentStandard).toBe(true);const rows=p.form.details.subprojects.map((r:any)=>({...r,amount:'8',accountingDepartment:'误改'}));expect(rows[0].name).toBe('项目');p.form.details.subprojects=rows;expect(c.s.subItems[0]).toMatchObject({amount:'8',dept:'原部门',sourceProof:'proof',catalogCode:'K001'});expect(p.form.details.subprojects[0].id).toBe(rows[0].id)})
 it('does not close on rejected save even when the form is unchanged',async()=>{const c=context(),p=setup(c);const submitter=document.createElement('button');submitter.value='return';const event=new SubmitEvent('submit',{submitter});await p.submitCommission(event);expect(c.requestClose).not.toHaveBeenCalled();c.saveEntrust.mockResolvedValue(true);await p.submitCommission(event);expect(c.requestClose).toHaveBeenCalledOnce()})
 it('round trips all mapped commission values without clearing unrelated backend fields',()=>{const c=context();c.f.otherBackendField='preserved';const p=setup(c);for(const [template,backend] of Object.entries(commissionBindings)){if(template==='contractId')continue;p.form[template]='value:'+template;expect(c.f[backend]).toBe('value:'+template);expect(p.form[template]).toBe('value:'+template)}expect(c.f.otherBackendField).toBe('preserved')})
 it('does not mutate read-only form or locked contract party',()=>{const c=context(),p=setup(c);c.readOnly=true;p.form.customer='changed';expect(c.f.client).toBe('客户');c.readOnly=false;c.contractPartyALocked=true;p.form.contractParty='changed';expect(c.f.contractPartyA).toBeUndefined()})
 it('saves sample drafts with existing controller and preserves unrendered data',async()=>{const c=context('samples');c.s.actualTestLocations=['原地址'];const p=setup(c);p.form.name='风机';p.form.quantity=3;await p.submitSample(new Event('submit'));expect(c.saveSampleDraft).toHaveBeenCalledOnce();expect(c.s.sampleName).toBe('风机');expect(c.s.sampleAmount).toBe('3');expect(c.s.actualTestLocations).toEqual(['原地址'])})
 it('retains backend report format and language restrictions',()=>{const p=setup(context('samples'));expect(p.reportConfig.combinations.some((r:any)=>r.formatId==='校准报告'&&r.languageId==='EN')).toBe(false);expect(p.reportConfig.combinations.some((r:any)=>r.formatId==='校准报告'&&r.titleId==='NCSA')).toBe(false)})
 it('does not silently drop custom capability choices',()=>{const c=context('samples');c.capabilityOptions=[{id:42,standardCode:'GB1',objectName:'风机',itemName:'温升',site:'A'}];const p=setup(c);p.chooseCapabilities(p.capabilityLabels[0]);expect(c.confirmCapabilitySelection).toHaveBeenCalledWith([42]);c.confirmCapabilitySelection.mockClear();p.chooseCapabilities('自由输入的无效参数');expect(c.confirmCapabilitySelection).not.toHaveBeenCalled()})
 it.each(['entrust','samples'])('mounts intact %s form with schema slots',async(mode)=>{Object.defineProperty(document,'fonts',{configurable:true,value:{ready:Promise.resolve()}});vi.stubGlobal('ResizeObserver',class{observe(){}disconnect(){}unobserve(){}});const w=mount(Page,{props:{context:context(mode)},global:{stubs:{RouterLink:true,PageHeading:true,RegistrationReviewModal:true,BootstrapModal:true,RegistrationContractPicker:true,RegistrationOrganizationPicker:true,RegistrationCommissionPicker:true,RegistrationTestPlanPicker:true,RegistrationTestBasisPicker:true,TemplateToast:true,TemplateEditableSelect:true,RegistrationTrademarkField:true}}});wrappers.push(w);await flushPromises();expect(w.find('form').exists()).toBe(true);expect(w.find('style').exists()).toBe(false);if(mode==='samples'){expect(w.find('#sample-taskRecipient').attributes('disabled')).toBeDefined();const quantity=w.find('#sample-quantity');expect(quantity.attributes('type')).toBe('text');await quantity.setValue('2台、3套');expect((w.props('context') as any).s.sampleAmount).toBe('2台、3套');expect((w.props('context') as any).s.unit).toBe('');expect(w.find('#platform-unit').exists()).toBe(false)}})
})
describe('legacy cover visibility',()=>{
 const file={name:'系统生成封面.docx',source:'模板生成',category:'other',selectedForOfficial:false} as any
 it('hides generated covers and preserves user uploads',()=>{expect(isLegacySystemCover(file)).toBe(true);expect(isLegacySystemCover({...file,source:'用户上传'})).toBe(false);expect(isLegacySystemCover({...file,selectedForOfficial:true})).toBe(true);expect(isLegacySystemCover({...file,category:'completed_report'})).toBe(true);expect(isLegacySystemCover({...file,name:'正式报告.docx'})).toBe(false)})
})

it('maps same-code records to distinct picker IDs and resolves the chosen name', async()=>{
 const c=context('samples')
 c.stdOptions=[{id:101,code:'EN 442-1:2014',name:'中文名称'},{id:102,code:'EN 442-1:2014',name:'English title'}]
 let service:any
 const child=defineComponent({setup(){service=inject('platform-registration-services');return()=>null}})
 wrappers.push(mount(defineComponent({components:{child},setup(){createRegistrationFormPresentation(c)},template:'<child />'})))
 const page=await service.testBases({ids:['102'],pageSize:50})
 expect(page.items).toMatchObject([{id:'102',code:'EN 442-1:2014',name:'English title'}])
 expect((await service.resolveTestBases('', ['102'],false,null,[])).text).toBe('EN 442-1:2014')
 expect((await service.resolveTestBases('', ['101','102'],false,null,[])).ids).toEqual(['101','102'])
})


it('supports optional CMA for NCSA and preserves saved choices during loading',()=>{
 const c=context('samples');c.s.seal='CMA + CNAS';const p=setup(c)
 const field=()=>p.backendSchema.sections.flatMap((x:any)=>x.fields).find((x:any)=>x.id==='platform-seal')
 expect(field().control).toBe('select');expect(c.s.seal).toBe('CMA + CNAS')
 field().binding.set({},'CNAS');expect(c.s.seal).toBe('CNAS')
 field().binding.set({},'CMA + CNAS');expect(c.s.seal).toBe('CMA + CNAS')
 c.readOnly=true;field().binding.set({},'CNAS');expect(c.s.seal).toBe('CMA + CNAS')
 c.readOnly=false;c.s.centerPrefix='NCSA';expect(field().disabled).toBe(true)
 field().binding.set({},'CNAS');expect(c.s.seal).toBe('CMA + CNAS')
})


it('defaults a newly chosen NCSA title to CMA plus CNAS and keeps explicit omission on same-title updates',()=>{
 const c=context('samples');c.s.centerPrefix='';c.s.seal='CMA + CNAS';const p=setup(c)
 p.form.details.reportSettings.titleId='NCSA';expect(c.s.seal).toBe('CMA + CNAS')
 c.s.seal='CNAS';p.form.details.reportSettings.titleId='NCSA';expect(c.s.seal).toBe('CNAS')
})
