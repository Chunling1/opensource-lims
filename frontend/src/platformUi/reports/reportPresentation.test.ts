import {describe,it,expect,vi} from 'vitest'
import {reactive} from 'vue'
import {createReportStagePresentation} from './reportStagePresentation'
import {createReportOutputPresentation} from './reportOutputPresentation'
describe('Full report list presentation',()=>{
 it.each(['query','review','approval','print','release','archive'])('uses current test items for the testing-project column in %s',pageKey=>{
  const c=controller();c.pageKey=pageKey;Object.assign(c.workRows[0],{project:'旧参数',testItems:'当前参数'})
  const m=createReportStagePresentation(c)
  expect(m.rows.items[0].name).toBe('当前参数')
  m.draft.searchField='name';m.draft.contains='当前参数';m.search();expect(m.rows.total).toBe(1)
 })
 const controller=()=>reactive<any>({pageKey:'review',pageName:'报告审核',workRows:[{reportNo:'R1',sampleNo:'S1',client:'甲',project:'检测',status:'待审核',rowProjection:'active'},{reportNo:'R2',sampleNo:'S2',client:'乙',status:'待批准',rowProjection:'recall'}],session:{canAction:(p:string)=>p==='report.review.pass'},openForm:vi.fn(),refreshReportList:vi.fn()});
 it('preserves report identity and active/recall permissions',()=>{const c=controller(),m=createReportStagePresentation(c);expect(m.rows.items[0].reportCode).toBe('R1');expect(m.actionAllowed(m.rows.items[0],'审核')).toBe(true);expect(m.actionAllowed(m.rows.items[1],'审核')).toBe(false);expect(m.actionAllowed(m.rows.items[1],'撤销审核')).toBe(false);m.rowAction(m.rows.items[0],'查看');expect(c.openForm).toHaveBeenCalledWith(c.workRows[0],true)});
 it('filters by concrete field and opens archive workflow only with row permission',()=>{const c=controller();c.pageKey='archive';const m=createReportOutputPresentation(c);m.draft.searchField='customer';m.draft.contains='乙';m.search();expect(m.rows.total).toBe(1);m.emit('action',m.rows.items[0],'workflow');expect(c.openForm).not.toHaveBeenCalled();c.workRows[1].allowedActions=['report.archive.pass'];m.emit('action',m.rows.items[0],'workflow');expect(c.openForm).toHaveBeenCalledWith(c.workRows[1],false)});
 it('applies combined conclusion, dates and review status filters',()=>{const c=controller();Object.assign(c.workRows[0],{entrustDate:'2026-11-01',resultStatus:'合格'});const m=createReportStagePresentation(c);Object.assign(m.draft,{from:'2026-11-01',to:'2026-11-01',conclusion:'合格',checkStatus:'未审核'});m.search();expect(m.error).toBe('');expect(m.rows.items.map((r:any)=>r.id)).toEqual(['R1']);m.draft.conclusion='不合格';m.search();expect(m.rows.total).toBe(0);expect(c.openForm).not.toHaveBeenCalled();expect(m.canQuickReview).toBe(false)});
 it.each(['review','approval','print','archive','release','query'])('submits expanded filters to the backend in %s',async pageKey=>{
  const c=controller();Object.assign(c,{pageKey,serverPaging:true,reportPageState:{total:1},setReportQuery:vi.fn()})
  const m=createReportOutputPresentation(c)
  Object.assign(m.draft,{conclusion:'合格',dateField:'testEndDate',from:'2026-10-01',to:'2026-11-01',checkStatus:pageKey==='review'?'已审核':pageKey==='approval'?'已批准':'',state:pageKey==='release'?'已发放':'',collectionMethod:pageKey==='release'?'邮寄':''})
  m.search();await import('vue').then(v=>v.nextTick())
  expect(c.setReportQuery).toHaveBeenLastCalledWith(expect.objectContaining({conclusion:'合格',dateField:'testEndDate',from:'2026-10-01',to:'2026-11-01'}))
  expect(m.reportCheckDateFields.length).toBeGreaterThan(5);expect(m.activeFilters).toBeGreaterThan(1)
  if(pageKey==='release')expect(c.setReportQuery).toHaveBeenLastCalledWith(expect.objectContaining({releaseStatus:'已发放',collectionMethod:'邮寄',rowProjection:''}))
 })
})


describe('issuance stage filters',()=>{
 it('offers completed releases even with no rows and submits that status outside the pending scope',async()=>{
  const c=reactive<any>({pageKey:'release',pageName:'报告发放',workRows:[],serverPaging:true,reportPageState:{total:0},setReportQuery:vi.fn(),session:{canAction:()=>true},refreshReportList:vi.fn(),openForm:vi.fn()})
  const m=createReportOutputPresentation(c)
  expect(m.states).toEqual(['待处理','报告已归档，发放中','报告发放完成'])
  expect(m.draft.status).toBe('待处理')
  m.draft.status='报告发放完成';m.search();await import('vue').then(v=>v.nextTick())
  expect(c.setReportQuery).toHaveBeenLastCalledWith(expect.objectContaining({status:'报告发放完成',rowProjection:''}))
  c.workRows=[{reportNo:'DONE',status:'已发放',dataStatus:'报告发放完成',rowProjection:'recall',allowedActions:[]}]
  const row=m.rows.items[0]
  expect(row.actions.find((a:any)=>a.id==='workflow').enabled).toBe(false)
  m.emit('action',row,'preview');expect(c.openForm).toHaveBeenCalledWith(c.workRows[0],true)
 })
 it.each(['print','query'])('filters each display stage on %s without changing workflow status',pageKey=>{
  const stages=['报告签发中','报告盖章中','报告已盖章，归档中，未发放','报告已归档，发放中','报告发放完成'];
  const c=reactive<any>({pageKey,pageName:'报告',workRows:stages.map((dataStatus,i)=>({reportNo:'R'+i,status:i===3?'待发放':'待打印',dataStatus})),session:{canAction:()=>true},refreshReportList:vi.fn(),openForm:vi.fn()});
  const m=createReportOutputPresentation(c);
  expect(m.states).toEqual(expect.arrayContaining(stages.slice(0,3)));
  for(const stage of stages){m.draft.status=stage;m.search();expect(m.rows.total).toBe(1);expect(m.rows.items[0].dataStatus).toBe(stage)}
  c.workRows=[];expect(m.states).toEqual(expect.arrayContaining(stages.slice(0,3)));
 });
});
