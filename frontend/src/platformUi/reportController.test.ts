import {readFileSync} from 'node:fs'
import ts from 'typescript'
import {parse} from '@vue/compiler-sfc'
import {describe,it,expect,vi} from 'vitest'
import {mount} from '@vue/test-utils'
import SchemaForm from '../components/forms/SchemaForm.vue'
import {TestCompletionUncertain} from '@/services/pipeline'
import {completePreviewState} from '@/services/attachments'
vi.mock('@/services/attachments', async original => ({...await original<typeof import('@/services/attachments')>(), completePreviewState: vi.fn(async () => ({status:'ready'}))}))
// Execute the retained owning-controller functions with isolated dependencies.
// The tests do not reimplement their guards and never contact a backend.
const script=parse(readFileSync('src/modules/pages/ReportDataEntryPage.vue','utf8')).descriptor.scriptSetup!.content
const ast=ts.createSourceFile('controller.ts',script,ts.ScriptTarget.Latest,true)
function controller(name:string,context:Record<string,unknown>){
 const declaration=ast.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text===name)!
 const js=ts.transpileModule(declaration.getText(ast),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
 return new Function(...Object.keys(context),js+`;return ${name}`)(...Object.values(context)) as (...args:unknown[])=>unknown
}
function preparation(context:Record<string,unknown>){
 const declaration=ast.statements.find(node=>ts.isVariableStatement(node)&&node.declarationList.declarations.some(item=>item.name.getText(ast)==='reportPreparationSchema'))!
 const js=ts.transpileModule(declaration.getText(ast),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
 const schema=new Function('computed',...Object.keys(context),js+';return reportPreparationSchema')((fn:()=>unknown)=>fn(),...Object.values(context))
 return mount(SchemaForm as any,{props:{schema,model:{}},slots:{preparation:'原有准备操作'}})
}
describe('Report content edit readonly boundary',()=>{
 for(const reason of ['readonly','closed','deleting'])it(`prevents opening or saving content when ${reason}`,async()=>{
  const save=vi.fn(),pagesOpen={value:false},context={formReadOnly:{value:reason==='readonly'},formOpen:{value:reason!=='closed'},attachmentDeleting:{value:reason==='deleting'},pagesOpen,reportPages:{value:[]},editPages:{value:[]},selected:{value:{reportNo:'R-1'}},savingPages:{value:false},saveReportPages:save}
  controller('openPages',context)();await controller('savePages',context)()
  expect(pagesOpen.value).toBe(false);expect(save).not.toHaveBeenCalled()
 })
 it('keeps editable page content preparation available without writing',()=>{
  const pagesOpen={value:false},editPages={value:[]},context={formReadOnly:{value:false},formOpen:{value:true},attachmentDeleting:{value:false},pagesOpen,reportPages:{value:[{title:'正文',content:'内容'}]},editPages}
  controller('openPages',context)();expect(pagesOpen.value).toBe(true);expect(editPages.value).toEqual([{title:'正文',content:'内容'}])
 })
})
describe('Report preparation options use template control events',()=>{
 const context=()=>({documentContent:{value:{compositionOptions:{reportLanguage:'CN',reportTemplateVariant:'Standard',preserveUploadedReport:false}}},documentPreflight:{value:{}},formReadOnly:{value:false},compositionSaving:{value:false},uploading:{value:false},isCalibrationReport:{value:false},supportsExtendedTemplate:{value:true},session:{roleKey:'admin'},saveDocumentOption:vi.fn()})
 it('does not save during render and forwards explicit language and layout changes',async()=>{
  const ctx=context(),wrapper=preparation(ctx);expect(ctx.saveDocumentOption).not.toHaveBeenCalled()
  await wrapper.get('#report-language').setValue('EN');expect(ctx.saveDocumentOption).toHaveBeenLastCalledWith('reportLanguage','EN')
  await wrapper.get('#report-template-variant').setValue('Extended');expect(ctx.saveDocumentOption).toHaveBeenLastCalledWith('reportTemplateVariant','Extended')
  await wrapper.get('#report-preserve-uploaded').setValue(true);expect(ctx.saveDocumentOption).toHaveBeenLastCalledWith('preserveUploadedReport',true)
 })
 it('preserves readonly, calibration-language and administrator restrictions',async()=>{
  const ctx=context();ctx.formReadOnly.value=true;const readonly=preparation(ctx)
  await readonly.get('#report-language').setValue('EN');expect(ctx.saveDocumentOption).not.toHaveBeenCalled()
  ctx.formReadOnly.value=false;ctx.isCalibrationReport.value=true;ctx.session.roleKey='tester';const calibrated=preparation(ctx)
  expect((calibrated.get('#report-language').element as HTMLSelectElement).disabled).toBe(true)
  expect(calibrated.find('#report-preserve-uploaded').exists()).toBe(false)
 })
})

describe('Report detail loading during page initialization',()=>{
 const source=parse(readFileSync('src/modules/pages/ReportPage.vue','utf8')).descriptor.scriptSetup!.content
 const tree=ts.createSourceFile('report.ts',source,ts.ScriptTarget.Latest,true)
 const statement=tree.statements.find(node=>ts.isExpressionStatement(node)&&node.getText(tree).startsWith('watchEffect(')&&node.getText(tree).includes('detailCache.value[no]'))!
 const js=ts.transpileModule(statement.getText(tree),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
 async function initialize(view:string,no='R1'){
  const fetchReportDetail=vi.fn(async()=>({sampleName:'风机'})),detailCache={value:{} as Record<string,unknown>}
  let pending:Promise<unknown>|undefined
  const ctx={watchEffect:(fn:any)=>{pending=fn(()=>{})},captureFormContext:()=>({}),isCurrentForm:()=>true,selectedReport:{value:no?{reportNo:no}:undefined},reportDetailView:{value:view},detailCache,fetchReportDetail}
  // The retained watcher runs before this later page declaration exists.
  new Function(...Object.keys(ctx),js+'; const isDecisionNode = {value:false};')(...Object.values(ctx))
  await pending
  return {fetchReportDetail,detailCache}
 }
 it.each(['review','approval','interim_report'])('loads %s once for the restored modal controller without an early reference',async view=>{
  const ctx=await initialize(view);expect(ctx.fetchReportDetail).toHaveBeenCalledExactlyOnceWith('R1',view);expect(ctx.detailCache.value.R1).toEqual({sampleName:'风机'})
 })
 it('still fetches and caches details for the report query page',async()=>{
  const ctx=await initialize('query');expect(ctx.fetchReportDetail).toHaveBeenCalledWith('R1','query');expect(ctx.detailCache.value.R1).toEqual({sampleName:'风机'})
 })
 it('does not fetch when no report is selected',async()=>{
  const ctx=await initialize('query','');expect(ctx.fetchReportDetail).not.toHaveBeenCalled()
 })
})


describe('Change completion executes the real draft-saving controller',()=>{
 function setup(){
  const ctx:any={selected:{value:{reportNo:'R1'}},selectedNo:{value:'R1'},formOpen:{value:true},formReadOnly:{value:false},saving:{value:false},adminEditing:{value:false},hasCompleteIntervals:{value:true},isCalibrationReport:{value:false},session:{canOverrideWorkflowDate:true},testPreviousDate:{value:'2026-10-01'},equipment:{value:[{id:1}]},equipmentCoversIntervals:()=>true,equipmentLabel:()=> 'Meter',isWorkflowDateValid:()=>true,isWorkflowDateBefore:()=>false,
   documentContent:{value:{compositionOptions:{reportLanguage:'CN'}}},
   t:{judgmentDisplay:{standardShowName:true,standardTitleStyles:{'ISO 1234:2024':'none'},standardSeparatorText:'；\n'},standards:['GB 1'],standardTitleStyles:{'GB 1':'CN'},standardSeparatorText:'；',equipmentSeparatorText:'、',equipmentIds:[1],resultStatus:'判定合格',testIntervals:[{start:'2026-10-21',end:'2026-10-21'}]},
   loadReferenceData:vi.fn(),loadStandardOptions:vi.fn(),testEditVersion:{value:'form-v3'},prepareReportQuery:vi.fn(),updateTestInfo:vi.fn(async()=>({testEditVersion:'form-v4'})),fetchReportDetail:vi.fn(async()=>({checks:[]})),detail:{value:{}},reportDetailView:{value:'data_change'},loadElnStatus:vi.fn(),refreshDocumentWorkflow:vi.fn(),refreshPreview:vi.fn(),preparationError:{value:''},checksDanger:{value:false},checksText:{value:''},
   changeTestComplete:vi.fn(async()=>({status:'待审核'})),completeTestInfo:vi.fn(async()=>({status:'待审核'})),
   completionFeedback:{value:''},unconfirmedCompletion:new Map(),signingChoiceReport:{value:''},entryListState:{error:''},
   readTestCompletion:vi.fn(),TestCompletionUncertain,completePreviewState,nextTick:vi.fn(),load:vi.fn(),ElMessage:{success:vi.fn(),warning:vi.fn(),error:vi.fn()}}
  ctx.persistTestInfo=controller('persistTestInfo',ctx)
  ctx.closeCompletedEntry=controller('closeCompletedEntry',ctx)
  ctx.checkCompletion=controller('checkCompletion',ctx)
  ctx.finishDataEntry=controller('finishDataEntry',ctx)
  return {ctx,complete:controller('completeChange',ctx),saveAndDone:controller('saveAndDone',ctx)}
 }
 it('saves before submitting completion, closes the form and refreshes the list',async()=>{
  const {ctx,complete}=setup();expect(await complete()).toBe(true)
  expect(ctx.updateTestInfo).toHaveBeenCalledOnce();expect(ctx.changeTestComplete).toHaveBeenCalledExactlyOnceWith('R1')
  expect(ctx.updateTestInfo.mock.calls[0][1]).toMatchObject({testEditVersion:'form-v3',standardTitleStyles:{'GB 1':'CN'},standardSeparatorText:'；',equipmentSeparatorText:'、'})
  expect(ctx.updateTestInfo.mock.calls[0][1].judgmentDisplay).toEqual(ctx.t.judgmentDisplay)
  expect(ctx.updateTestInfo.mock.invocationCallOrder[0]).toBeLessThan(ctx.changeTestComplete.mock.invocationCallOrder[0])
  expect(ctx.formOpen.value).toBe(false);expect(ctx.selectedNo.value).toBe('');expect(ctx.load).toHaveBeenCalledOnce();expect(ctx.saving.value).toBe(false)
 })
 it('locks duplicate saves before live refresh and does not save after a refresh failure',async()=>{
  const {ctx}=setup();let reject!:(error:Error)=>void
  ctx.loadReferenceData.mockImplementation(()=>new Promise((_,r)=>reject=r))
  const first=ctx.persistTestInfo(false)
  expect(ctx.saving.value).toBe(true);expect(await ctx.persistTestInfo(false)).toBe(false)
  reject(new Error('库读取失败'));expect(await first).toBe(false)
  expect(ctx.updateTestInfo).not.toHaveBeenCalled();expect(ctx.saving.value).toBe(false)
 })
 it('keeps current unsaved notes while refreshing linked library data',async()=>{
  const {ctx}=setup();ctx.t.remark='我的未保存备注';ctx.preparationEpoch=1;ctx.setInheritedStandards=vi.fn()
  await controller('refreshLinkedData',ctx)()
  expect(ctx.t.remark).toBe('我的未保存备注');expect(ctx.loadReferenceData).toHaveBeenCalledOnce()
 })
 it('displays saved instrument and personnel snapshots in readonly mode without library calls',async()=>{
  const {ctx}=setup();ctx.formReadOnly.value=true;ctx.authorizedPeople={value:{}}
  ctx.detail.value={checkInput:{equipmentSnapshots:[{id:1,name:'历史仪器',lastCalDate:'2020-01-01',validUntil:'2021-01-01'}],people:{primaryTester1:{code:'OLD',name:'历史姓名'}}}}
  await controller('loadReferenceData',ctx)()
  expect(ctx.equipment.value[0]).toMatchObject({name:'历史仪器',planCalDate:'2021-01-01'})
  expect(ctx.authorizedPeople.value.testers[0].name).toBe('历史姓名')
 })
 it('keeps invalid input open and never completes',async()=>{
  const {ctx,complete}=setup();ctx.t.standards=[];expect(await complete()).toBe(false)
  expect(ctx.changeTestComplete).not.toHaveBeenCalled();expect(ctx.formOpen.value).toBe(true);expect(ctx.ElMessage.warning).toHaveBeenCalled()
 })
 it('keeps failed saves open without completing',async()=>{
  const {ctx,complete}=setup();ctx.updateTestInfo.mockRejectedValue(new Error('保存失败'));expect(await complete()).toBe(false);expect(ctx.changeTestComplete).not.toHaveBeenCalled();expect(ctx.saving.value).toBe(false)
 })
 it('surfaces preview or backend failure and permits retry',async()=>{
  const {ctx,complete}=setup();ctx.changeTestComplete.mockRejectedValueOnce(new Error('当前报告 PDF 尚未生成'))
  expect(await complete()).toBe(false);expect(ctx.completionFeedback.value).toContain('PDF 尚未生成');expect(ctx.formOpen.value).toBe(true);expect(ctx.load).not.toHaveBeenCalled();expect(ctx.saving.value).toBe(false)
  expect(await complete()).toBe(true)
 })
 it('rejects readonly or already saving requests without side effects',async()=>{
  const {ctx,complete}=setup();ctx.saving.value=true;expect(await complete()).toBe(false);ctx.saving.value=false;ctx.formReadOnly.value=true;expect(await complete()).toBe(false);expect(ctx.updateTestInfo).not.toHaveBeenCalled();expect(ctx.changeTestComplete).not.toHaveBeenCalled()
 })
 it('does not complete a switched report after draft saving',async()=>{
  const {ctx,complete}=setup();ctx.updateTestInfo.mockImplementation(async()=>{ctx.selected.value={reportNo:'R2'};return {testEditVersion:'form-v4'}});expect(await complete()).toBe(false);expect(ctx.changeTestComplete).not.toHaveBeenCalled()
 })
 it('uses backend next stage and separates refresh failure from completion failure',async()=>{
  const {ctx,complete}=setup();ctx.changeTestComplete.mockResolvedValue({status:'待校核'});ctx.load.mockImplementation(()=>{ctx.entryListState.error='network'});expect(await complete()).toBe(true);expect(ctx.ElMessage.success).toHaveBeenLastCalledWith('检测更改完成，已进入「待校核」');expect(ctx.ElMessage.warning).toHaveBeenCalledWith('已收到服务器结果，列表刷新失败，请重新查询。');expect(ctx.formOpen.value).toBe(false)
 })
 it('acknowledges the draft even if the follow-up detail read fails',async()=>{
  const {ctx}=setup();ctx.fetchReportDetail.mockRejectedValueOnce(new Error('连接超时'))
  expect(await ctx.persistTestInfo(false)).toBe(true)
  expect(ctx.testEditVersion.value).toBe('form-v4')
  expect(ctx.preparationError.value).toContain('检测数据已保存，关联资料刷新失败')
  expect(ctx.ElMessage.error).not.toHaveBeenCalled()
 })
 it('does not wait for document refresh before opening workflow selection, then completes with the selected mode',async()=>{
  const {ctx,saveAndDone}=setup();ctx.reportDetailView.value='data_entry'
  ctx.refreshDocumentWorkflow.mockImplementation(()=>new Promise(()=>{}))
  ctx.completeTestInfo.mockResolvedValueOnce({esignWorkflowRequired:true})
  await saveAndDone()
  expect(ctx.signingChoiceReport.value).toBe('R1');expect(ctx.formOpen.value).toBe(true)
  expect(ctx.refreshDocumentWorkflow).not.toHaveBeenCalled()
  ctx.formOpen.value=false
  ctx.completeTestInfo.mockResolvedValueOnce({esignPending:true,message:'等待主检签署'})
  expect(await ctx.finishDataEntry('R1','business_stages_v1')).toBe(true)
  expect(ctx.completeTestInfo).toHaveBeenLastCalledWith('R1','business_stages_v1')
  expect(ctx.ElMessage.success).toHaveBeenLastCalledWith('R1 已提交录入，等待主检签署')
  expect(ctx.updateTestInfo).toHaveBeenCalledOnce()
 })
 it('clearly reports a saved draft when preview preflight fails before the completion POST',async()=>{
  const {ctx,saveAndDone}=setup()
  vi.mocked(completePreviewState).mockRejectedValueOnce(new Error('读取超时'))
  expect(await saveAndDone()).toBe(false)
  expect(ctx.completionFeedback.value).toContain('检测数据已保存，录入尚未完成。读取超时')
  expect(ctx.completeTestInfo).not.toHaveBeenCalled()
  expect(ctx.saving.value).toBe(false)
 })
 it('recovers a lost completion response by reading the server result once',async()=>{
  const {ctx,saveAndDone}=setup()
  ctx.completeTestInfo.mockRejectedValueOnce(new TestCompletionUncertain())
  ctx.readTestCompletion.mockResolvedValueOnce({status:'待审核',stillEditable:false,esignPending:false})
  await saveAndDone()
  expect(ctx.completeTestInfo).toHaveBeenCalledOnce()
  expect(ctx.readTestCompletion).toHaveBeenCalledExactlyOnceWith('R1','data_entry')
  expect(ctx.formOpen.value).toBe(false);expect(ctx.ElMessage.success).toHaveBeenLastCalledWith('已核对服务器，报告当前为「待审核」。')
 })
 it('retains the open form and only rechecks the result while the previous submission is uncertain',async()=>{
  const {ctx,complete}=setup();ctx.changeTestComplete.mockRejectedValueOnce(new TestCompletionUncertain())
  ctx.readTestCompletion.mockRejectedValueOnce(new Error('连接中断'))
  await complete()
  expect(ctx.formOpen.value).toBe(true);expect(ctx.completionFeedback.value).toContain('提交结果仍待核对')
  ctx.readTestCompletion.mockResolvedValueOnce({status:'检测更改中',stillEditable:true,esignPending:false})
  await complete()
  expect(ctx.changeTestComplete).toHaveBeenCalledOnce()
  expect(ctx.updateTestInfo).toHaveBeenCalledOnce()
  expect(ctx.readTestCompletion).toHaveBeenCalledTimes(2)
  expect(ctx.completionFeedback.value).toContain('如需再次提交，请确认后重新点击完成')
 })
})


it.each(['待打印','待发放','已发放','已归档'])('keeps saved references when administrator edits completed %s', async status=>{
 const ctx={selected:{value:{reportNo:'R1',status}},formReadOnly:{value:false},
  detail:{value:{checkInput:{equipmentSnapshots:[{id:1,name:'历史仪器'}],people:{primaryTester1:{code:'A',name:'历史人员'}}}}},
  equipment:{value:[]},authorizedPeople:{value:{testers:[] as {name:string}[]}},
  t:{standardRecords:[{id:1,code:'GB 1',name:'历史标准'}]},standardOptions:{value:[] as {name:string}[]}}
 await controller('loadReferenceData',ctx)()
 await controller('loadStandardOptions',ctx)()
 expect(ctx.equipment.value).toEqual([{id:1,name:'历史仪器',planCalDate:''}])
 expect(ctx.authorizedPeople.value.testers[0].name).toBe('历史人员')
 expect(ctx.standardOptions.value[0].name).toBe('历史标准')
})

it('prefers saved standard names to raw library references in readonly history',()=>{
 const ctx={formReadOnly:{value:true},selected:{value:{status:'已发放'}},
  detail:{value:{checkInput:{standardNames:{'QA 1':'历史名称'},standardRecords:[{code:'QA 1',name:'历史名称'}]},rawSample:{standardNames:{'QA 1':'当前名称'}}}},
  t:{testIntervals:[],equipmentDisplay:{}},setInheritedStandards:vi.fn(),summaryValue:()=>'',sourceRemark:()=>''}
 controller('applyExistingInput',ctx)()
 expect(ctx.t).toMatchObject({standardNames:{'QA 1':'历史名称'}})
})
