import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {shallowMount,flushPromises,type VueWrapper} from '@vue/test-utils'
import Form from '@/components/PipelineWizard.vue'
import {fetchCapabilityItems} from '@/services/pipeline'
import {searchStdLib} from '@/services/quality'
const api=vi.hoisted(()=>({detail:vi.fn(),copy:vi.fn(),edit:vi.fn(),preview:vi.fn()}))
vi.mock('@/services/reports',()=>({fetchReportDetail:api.detail,fetchSampleFormImage:vi.fn()}))
vi.mock('@/services/sampleCopies',()=>({fetchSampleCopySource:api.copy,fetchSampleCopyPage:vi.fn().mockResolvedValue({rows:[],total:0})}))
vi.mock('@/services/pipeline',async original=>({...await original<typeof import('@/services/pipeline')>(),fetchEntrustOptions:vi.fn().mockResolvedValue([]),fetchDepartments:vi.fn().mockResolvedValue([]),fetchDerivableReports:vi.fn().mockResolvedValue([]),fetchCapabilityItems:vi.fn().mockResolvedValue([]),editReportInPlace:api.edit,previewSampleEntrust:api.preview}))
vi.mock('@/stores/session',()=>({useSessionStore:()=>({dataScope:{department:'QA'},userName:'QA',can:()=>true,canAction:()=>true,canOverrideWorkflowDate:false})}))
vi.mock('element-plus',async original=>({...await original<typeof import('element-plus')>(),ElMessage:{error:vi.fn(),warning:vi.fn(),success:vi.fn()},ElMessageBox:{confirm:vi.fn()}}))
vi.mock('@/services/quality',()=>({searchStdLib:vi.fn().mockResolvedValue([]),searchStdLibPage:vi.fn().mockResolvedValue({rows:[]})}))
let wrapper:VueWrapper
const record=()=>({reportNo:'LAB-QA-01',sampleNo:'QA-01',sampleRegState:'登记中',rawSample:{sampleName:'样品乙',engineeringName:'幕墙甲',testCategory:'抽样',testBases:[]},summary:[],entrustSnapshot:{entrustNo:'WT-QA',projectName:'合同丙',info:{entrustDate:'2026-09-10'}}})
async function start(readOnly=false){wrapper=shallowMount(Form,{props:{modelValue:false,mode:'samples',changeReportNo:'LAB-QA-01',inPlace:true,readOnly},global:{stubs:{ElDialog:true},directives:{loading:{}},config:{warnHandler:()=>undefined}}});await wrapper.setProps({modelValue:true});await flushPromises();return(wrapper.vm as any).$.setupState}
beforeEach(()=>{vi.clearAllMocks();api.detail.mockResolvedValue(record());api.copy.mockResolvedValue(record());api.edit.mockResolvedValue({reportNo:'LAB-QA-01'})})
afterEach(()=>wrapper?.unmount())
it('loads independent field, saves changes and explicit clearing with the actual controller',async()=>{const x=await start();expect(x.s.engineeringName).toBe('幕墙甲');expect(x.s.sampleName).toBe('样品乙');expect(x.s.testCategory).toBe('抽样');x.s.engineeringName='幕墙修改';x.sampleEntrustNo='WT-QA';await x.saveSampleChange('save');expect(api.edit).toHaveBeenCalled();let d=api.edit.mock.calls.at(-1)![1].fullDetail;expect(d.rawSample.engineeringName).toBe('幕墙修改');expect(d.rawSample.testCategory).toBe('抽样');expect(d.rawSample.sampleName).toBe('样品乙');x.s.engineeringName='';await x.saveSampleChange('save');d=api.edit.mock.calls.at(-1)![1].fullDetail;expect(d.rawSample.engineeringName).toBe('')})
it('copies independent field and preserves category without modifying source',async()=>{const x=await start();const original=record();api.copy.mockResolvedValue(original);x.copyDialogOpen=true;await x.copyFromSample({reportNo:'LAB-QA-02',sampleNo:'QA-02'});expect(x.s.engineeringName).toBe('幕墙甲');expect(x.s.testCategory).toBe('抽样');expect(original.rawSample.testCategory).toBe('抽样');expect(x.s.sampleNo).toBe('QA-01')})
it('loads summary-only curtain value and never substitutes sample name',async()=>{api.detail.mockResolvedValue({...record(),rawSample:undefined,summary:[{title:'送样信息',fields:[['样品名称','样品乙'],['工程名称（幕墙）','幕墙摘要']]}]});const x=await start();expect(x.s.engineeringName).toBe('幕墙摘要');api.copy.mockResolvedValue({rawSample:{sampleName:'另一件样品'},summary:[]});x.copyDialogOpen=true;await x.copyFromSample({reportNo:'LAB-QA-02',sampleNo:'QA-02'});expect(x.s.engineeringName).toBe('')})
it('preserves historical category in readonly view',async()=>{const x=await start(true);expect(x.s.testCategory).toBe('抽样');expect(x.s.engineeringName).toBe('幕墙甲');await x.saveSampleChange('save');expect(api.edit).not.toHaveBeenCalled()})

it.each(['委托', '委托（有见证送检）', '型式检验', '型式试验', '抽样检测', '抽样型式检验'])('preserves %s in draft save, summary and copy', async category => {
  api.detail.mockResolvedValue({...record(), rawSample:{...record().rawSample, testCategory:category}})
  const x = await start()
  expect(x.s.testCategory).toBe(category)
  x.sampleEntrustNo = 'WT-QA'
  await x.saveSampleChange('save')
  const detail = api.edit.mock.calls.at(-1)![1].fullDetail
  expect(detail.rawSample.testCategory).toBe(category)
  expect(detail.summary.find((s:any) => s.title === '送样信息').fields).toContainEqual(['检测类别', category])
  api.copy.mockResolvedValue({...record(), rawSample:{...record().rawSample, testCategory:category}})
  x.copyDialogOpen = true
  await x.copyFromSample({reportNo:'LAB-QA-02',sampleNo:'QA-02'})
  expect(x.currentSampleItem().testCategory).toBe(category)
})
it('keeps a user-selected category when changing other sample fields', async () => {
  const x = await start()
  x.s.testCategory = '抽样型式检验'
  x.s.sampleName = '修改样品'
  await flushPromises()
  expect(x.currentSampleItem().testCategory).toBe('抽样型式检验')
})

it('saves and reloads mixed item order and basis order through the sample controller',async()=>{
  const x=await start();x.sampleEntrustNo='WT-QA'
  const rows=[{id:11,itemName:'温度',standardCode:'GB-A',objectName:'样品'}, {id:22,itemName:'湿度',standardCode:'GB-B',objectName:'样品'}]
  x.capabilityOptions=rows;x.s.capabilitySnapshots=rows;x.s.capabilityEntryIds=[11,22];x.s.manualCapabilityItems=['库外温差']
  x.s.testBases=['GB-A','GB-B'];x.s.standardJudge='GB-A；GB-B';x.s.testItemOrder=[{kind:'library',id:11},{kind:'library',id:22},{kind:'manual',name:'库外温差'}]
  x.reorderTestItems(['library:22','manual:库外温差','library:11']);x.reorderBases(['GB-B','GB-A'])
  expect(x.s.standardJudge).toBe('GB-B；GB-A');expect(x.s.project).toBe('湿度、库外温差、温度')
  await x.saveSampleChange('save')
  const detail=api.edit.mock.calls.at(-1)![1].fullDetail
  expect(detail.rawSample.testItemOrder).toEqual([{kind:'library',id:22},{kind:'manual',name:'库外温差'},{kind:'library',id:11}])
  expect(detail.rawSample.testBases).toEqual(['GB-B','GB-A'])
  vi.mocked(fetchCapabilityItems).mockResolvedValue(rows as any)
  api.copy.mockResolvedValue({...record(),rawSample:detail.rawSample});x.copyDialogOpen=true
  await x.copyFromSample({reportNo:'LAB-QA-02',sampleNo:'QA-02'})
  expect(x.currentSampleItem().testItemOrder).toEqual(detail.rawSample.testItemOrder)
  x.s.standardJudge='自定义判定';x.reorderBases(['GB-A','GB-B']);expect(x.s.standardJudge).toBe('自定义判定')
})

it('keeps selected standards despite parameter source text and ignores a delayed confirmation after cancel',async()=>{
  const x=await start();x.s.testBases=['GB-A'];x.stdOptions=[{id:1,code:'GB-A',singleList:true}]
  x.capabilityOptions=[{id:11,itemName:'温度',standardCode:'GB-B',objectName:'样品'}]
  vi.mocked(searchStdLib).mockResolvedValue([{id:2,code:'GB-B',singleList:true}] as any)
  x.capabilityDialogOpen=true;await flushPromises()
  await x.confirmCapabilitySelection([11],['温差'],[{kind:'manual',name:'温差'},{kind:'library',id:11}])
  expect(x.s.testBases).toEqual(['GB-A']);expect(x.s.project).toBe('温差、温度');expect(x.capabilityDialogOpen).toBe(false)
  x.s.testBases=['GB-A'];x.stdOptions=[]
  let resolve:any;vi.mocked(searchStdLib).mockImplementationOnce(()=>new Promise(r=>{resolve=r}))
  x.capabilityDialogOpen=true;await flushPromises()
  const pending=x.confirmCapabilitySelection([11],['取消的项目'],[{kind:'manual',name:'取消的项目'}])
  x.capabilityDialogOpen=false;await flushPromises();resolve([{id:1,code:'GB-A',singleList:true}]);await pending
  expect(x.s.manualCapabilityItems).toEqual(['温差']);expect(x.s.testBases).toEqual(['GB-A'])
})


it('revalidates the current sample before selected-page downloads and rejects a changed PDF',async()=>{
  const x=await start();x.sampleEntrustNo='WT-QA'
  const original={type:'pdf',url:'blob:original',name:'QA.pdf',sourceHash:'same',expectedPages:4,etag:'same'}
  const revoke=vi.fn();vi.stubGlobal('URL',class extends URL { static revokeObjectURL=revoke })
  try {
    api.preview.mockResolvedValue(original)
    await x.openEntrustPreview()
    expect(x.coverPdfUrl).toBe('blob:original')
    expect(api.preview.mock.calls.at(-1)![0].outputLanguage).toBe('CN')
    expect(await x.validateEntrustPreviewDownload()).toBe(true)
    expect(api.preview.mock.calls.at(-1)![4]).toEqual(original)
    x.previewLanguage='EN'
    api.preview.mockResolvedValue({...original,url:'blob:english',etag:'english'})
    await x.onPreviewEntrust()
    expect(api.preview.mock.calls.at(-1)![0].outputLanguage).toBe('EN')
    expect(api.preview.mock.calls.at(-1)![4]).toBeUndefined()
    expect(x.coverPdfUrl).toBe('blob:english')
    expect(revoke).toHaveBeenCalledWith('blob:original')
    api.preview.mockResolvedValue({...original,url:'blob:updated',sourceHash:'changed'})
    expect(await x.validateEntrustPreviewDownload()).toBe(false)
    expect(x.coverPdfUrl).toBe('blob:updated')
    api.preview.mockRejectedValue(new Error('无预览权限'))
    expect(await x.validateEntrustPreviewDownload()).toBe(false)
    expect(x.coverPdfUrl).toBe('')
  } finally { vi.unstubAllGlobals() }
})


it('saves template text exactly with composed separators and restores it on copy',async()=>{
  const x=await start();x.sampleEntrustNo='WT-QA'
  const rows=[{id:11,itemName:'温度',standardCode:'GB-A',objectName:'样品'}]
  const standards=[{id:1,code:'GB-A',name:'甲标准',singleList:true},{id:2,code:'GB-B',name:'乙标准',singleList:true}]
  x.capabilityOptions=rows;x.s.capabilitySnapshots=rows;x.s.capabilityEntryIds=[11];x.s.manualCapabilityItems=['库外温差']
  x.s.testItemOrder=[{kind:'manual',name:'库外温差'},{kind:'library',id:11}]
  x.s.testBases=['GB-B','GB-A'];x.stdOptions=standards
  x.s.basisSeparator='； \n';x.s.itemsSeparator='，\n'
  const expected={basis:'GB-B 乙标准； \nGB-A 甲标准',items:'库外温差，\n温度'}
  expect(x.commissionBasisText).toBe(expected.basis);expect(x.commissionItemsText).toBe(expected.items)
  await x.saveSampleChange('save')
  const detail=api.edit.mock.calls.at(-1)![1].fullDetail
  expect(detail.rawSample.commissionText).toEqual(expected)
  expect(detail.summary.find((s:any)=>s.title==='实验信息').fields).toContainEqual(['检测依据',expected.basis])
  expect(detail.summary.find((s:any)=>s.title==='实验信息').fields).toContainEqual(['检测项目',expected.items])
  vi.mocked(fetchCapabilityItems).mockResolvedValue(rows as any);vi.mocked(searchStdLib).mockResolvedValue(standards as any)
  api.copy.mockResolvedValue({...record(),rawSample:detail.rawSample});x.copyDialogOpen=true
  await x.copyFromSample({reportNo:'LAB-QA-02',sampleNo:'QA-02'})
  expect(x.s.basisSeparator).toBe('； \n');expect(x.s.itemsSeparator).toBe('，\n')
  expect(x.currentSampleItem().commissionText).toEqual(expected)
})

it('keeps detection-basis order in the dialog draft until confirmed',async()=>{
  const x=await start();x.s.testBases=['GB-A','GB-B'];x.s.standardJudge='GB-A；GB-B'
  x.stdOptions=[{id:1,code:'GB-A',singleList:true},{id:2,code:'GB-B',singleList:true}]
  await x.openBasisDialog();x.basisDraftCodes=['GB-B','GB-A'];x.basisDialogOpen=false
  expect(x.s.testBases).toEqual(['GB-A','GB-B'])
  await x.openBasisDialog();expect(x.basisDraftCodes).toEqual(['GB-A','GB-B'])
  x.basisDraftCodes=['GB-B','GB-A'];await x.confirmBasisSelection()
  expect(x.s.testBases).toEqual(['GB-B','GB-A'])
})

it('saves independent commission title styles, restores them on reopen and copy, and keeps report preferences separate',async()=>{
  const x=await start();x.sampleEntrustNo='WT-QA'
  const standards=[{id:1,code:'GB-A',name:'甲标准',singleList:true},{id:2,code:'GB-B',name:'乙标准',singleList:true},{id:3,code:'GB-C',name:'丙标准',singleList:true}]
  x.s.testBases=['GB-A','GB-B','GB-C'];x.stdOptions=standards
  x.s.basisTitleStyles={'GB-A':'CN','GB-B':'EN','GB-C':'none'}
  x.s.basisSeparator='；\n'
  const expected='GB-A 《甲标准》；\nGB-B <乙标准>；\nGB-C 丙标准'
  expect(x.commissionBasisText).toBe(expected)
  await x.saveSampleChange('save')
  const detail=api.edit.mock.calls.at(-1)![1].fullDetail
  expect(detail.rawSample.basisTitleStyles).toEqual({'GB-A':'CN','GB-B':'EN','GB-C':'none'})
  expect(detail.rawSample.commissionText.basis).toBe(expected)
  vi.mocked(searchStdLib).mockResolvedValue(standards as any)
  api.detail.mockResolvedValue({...record(),rawSample:detail.rawSample})
  wrapper.unmount();const reopened=await start()
  expect(reopened.s.basisTitleStyles).toEqual(detail.rawSample.basisTitleStyles)
  expect(reopened.commissionBasisText).toBe(expected)
  api.copy.mockResolvedValue({...record(),rawSample:detail.rawSample});reopened.copyDialogOpen=true
  await reopened.copyFromSample({reportNo:'LAB-QA-02',sampleNo:'QA-02'})
  expect(reopened.commissionBasisText).toBe(expected)
  reopened.s.basisTitleStyles['GB-A']='none'
  expect(detail.rawSample.basisTitleStyles['GB-A']).toBe('CN')
  expect(reopened.s.standardTitleStyles).toBeUndefined()
})

it('saves, reopens and copies judgment display independently from detection standards',async()=>{
  const x=await start();x.sampleEntrustNo='WT-QA';x.s.standardJudge='ISO 1234:2024；GB 2-2024'
  x.s.judgmentDisplay={standardShowName:true,standardTitleStyles:{'ISO 1234:2024':'EN','GB 2-2024':'none'},standardSeparatorText:'；\n'}
  await x.saveSampleChange('save')
  const detail=api.edit.mock.calls.at(-1)![1].fullDetail
  expect(detail.rawSample.judgmentDisplay).toEqual(x.s.judgmentDisplay)
  api.detail.mockResolvedValue({...record(),rawSample:detail.rawSample});wrapper.unmount()
  const reopened=await start();expect(reopened.s.judgmentDisplay).toEqual(detail.rawSample.judgmentDisplay)
  api.copy.mockResolvedValue({...record(),rawSample:detail.rawSample});reopened.copyDialogOpen=true
  await reopened.copyFromSample({reportNo:'LAB-QA-02',sampleNo:'QA-02'})
  expect(reopened.s.judgmentDisplay).toEqual(detail.rawSample.judgmentDisplay)
  reopened.s.judgmentDisplay.standardShowName=false
  expect(detail.rawSample.judgmentDisplay.standardShowName).toBe(true)
})

it('does not bind the original entrust date to a later or missing contract registration date',async()=>{
  const x=await start()
  Object.assign(x.f,{contractNo:'LATER',client:'客户',projectName:'项目',entrustDate:'2026-10-12',handleDept:'QA',handler:'QA'})
  x.claimedContracts=[{agreementNo:'LATER',registeredAt:'2026-10-25',info:{regDate:'2026-10-25'}}]
  expect(x.validateEntrust()).toBe(true)
  x.claimedContracts=[{agreementNo:'LATER',info:{}}]
  expect(x.validateEntrust()).toBe(true)
  expect(x.f.entrustDate).toBe('2026-10-12')
  x.f.entrustDate='invalid'
  expect(x.validateEntrust()).toBe(false)
  expect(x.entrustErrors.entrustDate).toBe('委托日期格式无效')
})


it.each([['分项', '-1'], ['补充', 'BC'], ['英文', '(E)']])('shares source sample for %s and keeps report suffix', async (category, suffix) => {
  const x=await start()
  await wrapper.setProps({changeReportNo:''})
  x.activeSavedReportNo='';x.s.sampleNo='';x.s.reportCategory=category
  x.s.baseReportNo='LAB-2026HR-0053';x.s.subSuffix='1'
  x.sourceSample={reportNo:'LAB-2026HR-0053',sampleNo:'2026HR-0053'}
  expect(x.sampleAutoNo).toBe('2026HR-0053')
  expect(x.sampleReportNo).toBe('LAB-2026HR-0053'+suffix)
  expect(x.currentSampleItem().sampleNo).toBe('2026HR-0053')
  x.s.baseReportNo=''
  expect(x.sampleAutoNo).toBe('')
})
it('reopening a derivative keeps its report number independently of sample number', async () => {
  api.detail.mockResolvedValue({...record(),reportNo:'LAB-2026HR-0053-1',sampleNo:'2026HR-0053'})
  const x=await start()
  await wrapper.setProps({changeReportNo:'LAB-2026HR-0053-1'})
  await flushPromises()
  expect(x.sampleAutoNo).toBe('2026HR-0053')
  expect(x.sampleReportNo).toBe('LAB-2026HR-0053-1')
  x.s.centerPrefix='NCSA'
  expect(x.sampleReportNo).toBe('LAB-2026HR-0053-1')
})
