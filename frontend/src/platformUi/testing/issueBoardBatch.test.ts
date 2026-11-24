import {describe,it,expect,vi,afterEach} from 'vitest'
import {mount,shallowMount} from '@vue/test-utils'
import {reactive} from 'vue'
import {readFileSync} from 'node:fs'
import ts from 'typescript'
import {parse} from '@vue/compiler-sfc'
import Dates from '../../components/common/TemplateDateRange.vue'
import Editor from '../commissions/RegistrationSampleSubprojects.vue'
import {createReportOutputPresentation} from '../reports/reportOutputPresentation'
import {samplePricingErrors} from '@/composables/sampleSubprojects'
const wrappers:any[]=[]
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());vi.unstubAllGlobals()})
it('shows historic date-times as days without silently saving them; new selections emit days',async()=>{
 let opts:any;const picker={setDate:vi.fn(),destroy:vi.fn(),close:vi.fn(),formatDate:vi.fn((d:Date)=>d.toISOString().slice(0,10))}
 vi.stubGlobal('flatpickr',vi.fn((_el,o)=>{opts=o;return picker}))
 const w=mount(Dates,{props:{id:'date',from:'2026-10-14 12:23:34',to:'2026-10-15T15:30:00',allowPartial:true}});wrappers.push(w)
 expect((w.get('input').element as HTMLInputElement).value).toBe('2026-10-14 至 2026-10-15')
 expect(w.emitted('change')).toBeUndefined();expect(opts.enableTime).toBeUndefined()
 opts.onChange([new Date('2026-10-16'),new Date('2026-10-17')]);expect(w.emitted('change')?.[0]).toEqual([{from:'2026-10-16',to:'2026-10-17'}])
 await w.setProps({disabled:true});opts.onChange([new Date('2026-10-18')]);expect(w.emitted('change')).toHaveLength(1)
})
it('preserves ID styles in the actual test-info payload expression',()=>{
 const script=parse(readFileSync('src/modules/pages/ReportDataEntryPage.vue','utf8')).descriptor.scriptSetup!.content
 const ast=ts.createSourceFile('entry.ts',script,ts.ScriptTarget.Latest,true);let initializer:any
 function visit(n:ts.Node){if(ts.isPropertyAssignment(n)&&n.name.getText(ast)==='standardTitleStyles'&&n.initializer.getText(ast).includes('t.standardTitleStyles'))initializer=n.initializer;ts.forEachChild(n,visit)}visit(ast)
 const t={standards:['EN 1'],standardTitleStyles:{'EN 1':'CN','id:1':'EN','id:2':'none'}}
 const result=new Function('t','return '+initializer.getText(ast))(t)
 expect(JSON.parse(JSON.stringify(result))).toEqual(t.standardTitleStyles);expect(result).not.toBe(t.standardTitleStyles)
})
it('autofills receipts, respects manual overrides and rejects missing money including on drafts',async()=>{
 const w=shallowMount(Editor,{props:{modelValue:[],options:[{name:'P',accountingDepartment:'D',businessCategory:'B'}]},global:{provide:{'platform-registration-subprojects':{isLocked:()=>false}},stubs:{BootstrapModal:{template:'<div><slot/><slot name="footer"/></div>'},AdaptiveTableActions:{template:'<div><slot/></div>'}}}});wrappers.push(w)
 await w.get('button.btn-primary').trigger('click');await w.get('#subproject-name').setValue('P');await w.get('#subproject-paymentDescription').setValue('约定')
 await w.get('form').trigger('submit');expect(w.emitted('update:modelValue')).toBeUndefined()
 await w.get('#subproject-amount').setValue('100');expect((w.get('#subproject-receivedAmount').element as HTMLInputElement).value).toBe('100')
 await w.get('#subproject-amount').setValue('120');expect((w.get('#subproject-receivedAmount').element as HTMLInputElement).value).toBe('120')
 await w.get('#subproject-receivedAmount').setValue('0');await w.get('#subproject-amount').setValue('150');expect((w.get('#subproject-receivedAmount').element as HTMLInputElement).value).toBe('0')
 await w.get('form').trigger('submit');expect(w.emitted('update:modelValue')?.[0]?.[0]).toEqual([expect.objectContaining({amount:'150',receivedAmount:'0'})])
 const row={projectName:'P',dept:'D',businessCategory:'B',amount:'0',receivedAmount:'',paymentDescription:'约定',receiptType:'',remark:''}
 expect(samplePricingErrors([row],'',false).join()).toContain('收款金额');expect(samplePricingErrors([{...row,receivedAmount:'0'}],'0',true)).toEqual([])
})
it('archive filters all statuses but only actionable records can be archived',()=>{
 const c=reactive<any>({pageKey:'archive',pageName:'归档',workRows:[{reportNo:'R1',status:'待合同评审',dataStatus:'合同评审中',allowedActions:[]},{reportNo:'R2',status:'待打印',dataStatus:'报告已盖章，归档中，未发放',allowedActions:['report.archive.pass']}],session:{canAction:()=>true},openForm:vi.fn(),refreshReportList:vi.fn(),undoReport:vi.fn()})
 const m=createReportOutputPresentation(c);expect(m.rows.total).toBe(2);expect(m.statuses).toContain('合同评审中')
 const early=m.rows.items[0];m.emit('action',early,'workflow');expect(c.openForm).not.toHaveBeenCalled();m.emit('action',early,'preview');expect(c.openForm).toHaveBeenCalledWith(early.source,true)
 m.draft.status='合同评审中';m.search();expect(m.rows.total).toBe(1);m.draft.status='报告已盖章，归档中，未发放';m.search();expect(m.rows.total).toBe(1);m.emit('action',m.rows.items[0],'workflow');expect(c.openForm).toHaveBeenLastCalledWith(m.rows.items[0].source,false)
})

describe('project name warning on both commission and sample snapshots',()=>{
 const script=parse(readFileSync('src/modules/components/PipelineWizard.vue','utf8')).descriptor.scriptSetup!.content
 const ast=ts.createSourceFile('wizard.ts',script,ts.ScriptTarget.Latest,true)
 const fn=ast.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='confirmEntrustProjectName')!
 it.each([false,true])('allows cancellation and confirms the unchanged Erp name (sample=%s)',async sample=>{
  const form={contractNo:'C1',projectName:'自动项目'},confirm=vi.fn().mockRejectedValueOnce('cancel').mockResolvedValue(undefined)
  const ctx:any={f:form,sampleEntrust:form,selectedContract:{value:undefined},sampleSelectedContract:{value:undefined},sampleFormSession:()=>()=>true,fetchContractSelectionPage:vi.fn(async()=>({rows:[{agreementNo:'C1',projectName:'自动项目',info:{fromErp:'1'}}]})),ElMessageBox:{confirm},nextTick:async()=>{},document}
  const js=ts.transpileModule(fn.getText(ast),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
  const run=new Function(...Object.keys(ctx),js+';return confirmEntrustProjectName')(...Object.values(ctx))
  expect(await run(sample)).toBe(false);expect(await run(sample)).toBe(true);form.projectName='/';expect(await run(sample)).toBe(true);expect(confirm).toHaveBeenCalledTimes(2)
 })
})
