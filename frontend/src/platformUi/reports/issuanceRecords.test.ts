import {describe,it,expect,vi,beforeEach} from 'vitest'
import {reactive,nextTick} from 'vue'
import {flushPromises,mount,shallowMount} from '@vue/test-utils'
import {ElMessageBox} from 'element-plus'
import {ApiError} from '@/services/http'
import ReportOutput from './ReportOutputListPresentation.vue'
import {createReportOutputPresentation} from './reportOutputPresentation'
const api=vi.hoisted(()=>({download:vi.fn()}))
vi.mock('@/services/issuanceRecords',()=>({downloadIssuanceRecord:api.download}))
function setup(pageKey='release'){
 const c=reactive<any>({pageKey,pageName:'报告发放',workRows:[],session:{canAction:()=>true},refreshReportList:vi.fn(),undoReport:vi.fn()})
 return {c,m:createReportOutputPresentation(c)}
}
describe('selected issuance register export',()=>{
 beforeEach(()=>{vi.clearAllMocks();api.download.mockResolvedValue(undefined)})
 it.each([['A'],['B','A']])('sends exact selected report numbers %s',async(...args)=>{
  const {m}=setup();m.selected=args;await m.exportIssuanceRecord('engineering')
  expect(api.download).toHaveBeenCalledWith(args,'engineering');expect(m.selected).toEqual(args)
 })
 it('never exports all records implicitly or on another module',async()=>{
  const {m,c}=setup();await m.exportIssuanceRecord('product');m.selected=['A'];c.pageKey='print';await m.exportIssuanceRecord('product');expect(api.download).not.toHaveBeenCalled()
 })
 it('prevents duplicate requests and retains errors for retry',async()=>{
  const {m}=setup();m.selected=['A'];let reject:any;api.download.mockImplementation(()=>new Promise((_,r)=>reject=r))
  const first=m.exportIssuanceRecord('product');await m.exportIssuanceRecord('engineering');expect(api.download).toHaveBeenCalledTimes(1)
  reject(new Error('无权限'));await first;expect(m.issuanceExportBusy).toBe(false);expect(m.issuanceExportError.message).toBe('无权限');expect(m.selected).toEqual(['A'])
 })
 it('renders two selection-gated toolbar buttons only on release',async()=>{
  const {m,c}=setup()
  const w=shallowMount(ReportOutput,{props:{context:m},global:{stubs:{
   TableToolbar:{template:'<div><slot /></div>'},QueryFormLayout:{template:'<div><slot/><slot name="actions"/></div>'}
  }}})
  const buttons=()=>w.findAll('button').filter(b=>['产品类发放表','工程类发放表'].includes(b.text()))
  expect(buttons()).toHaveLength(2);expect(buttons().every(b=>b.attributes('disabled')!==undefined)).toBe(true)
  m.selected=['A','B'];await nextTick();expect(buttons().every(b=>b.attributes('disabled')===undefined)).toBe(true)
  await buttons()[0].trigger('click');expect(api.download).toHaveBeenCalledWith(['A','B'],'product')
  m.issuanceExportBusy=true;await nextTick();expect(buttons().every(b=>b.attributes('disabled')!==undefined)).toBe(true)
  c.pageKey='archive';await nextTick();expect(buttons()).toHaveLength(0);w.unmount()
 })
})

describe('batch report output',()=>{
 it.each([
  ['archive','归档','report.archive.pass','report.archive.undo'],
  ['release','发放','report.distribution.complete','report.archive.pass'],
 ])('submits only eligible current-page %s selections and reports partial success',async(stage,label,action,otherAction)=>{
  const c=reactive({
   pageKey:stage,pageName:'报告'+label,serverPaging:true,reportPageState:{total:10},setReportQuery:vi.fn(),
   workRows:[{reportNo:'A',allowedActions:[action]},{reportNo:'B',allowedActions:[action]},{reportNo:'C',allowedActions:[otherAction]}],
   session:{account:'tester',canAction:():boolean=>true},refreshReportList:vi.fn(),undoReport:vi.fn(),
   completeOutput:vi.fn(async(reportNo:string)=>{if(reportNo==='A')throw new ApiError('盖章文件缺失',200,1)}),
  })
  const confirm=vi.spyOn(ElMessageBox,'confirm').mockResolvedValue('confirm')
  const m=createReportOutputPresentation(c)
  const w=mount(ReportOutput,{props:{context:m},global:{stubs:{
   TableToolbar:{template:'<div><slot /></div>'},TestPlanFilterDrawer:true,TemplateDateRange:true,
  }}})
  try {
   const button=()=>w.findAll('button').find(item=>item.text().startsWith('批量'+label))!
   expect(button().attributes('disabled')).toBeDefined()
   await w.get(`input[aria-label="全选当前页报告${label}"]`).setValue(true)
   m.selected.push('OFF-PAGE')
   await nextTick()
   expect(button().text()).toBe(`批量${label}（2）`)
   await button().trigger('click')
   await flushPromises()
   expect(confirm.mock.calls[0][0]).toContain('其余 1 份当前不可办理')
   expect(c.completeOutput.mock.calls).toEqual([['A',action],['B',action]])
   expect(c.refreshReportList).toHaveBeenCalledTimes(1)
   expect(w.text()).toContain('成功 1 份，未确认成功 1 份')
   expect(w.text()).toContain('A · 盖章文件缺失')
   expect(m.selected).not.toContain('B')
   c.session.canAction=()=>false
   await nextTick()
   expect(button()).toBeUndefined()
   await m.completeSelected()
   expect(c.completeOutput).toHaveBeenCalledTimes(2)
  } finally { w.unmount();confirm.mockRestore() }
 })
})
