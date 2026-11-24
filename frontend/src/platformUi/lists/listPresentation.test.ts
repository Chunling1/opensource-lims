import {describe,it,expect,vi} from 'vitest'
import {reactive} from 'vue'
vi.mock('@/services/pipeline',()=>({submitSampleDispose:vi.fn(),voidSample:vi.fn(),changeResubmit:vi.fn()}))
vi.mock('../controls',()=>({ElMessageBox:{confirm:vi.fn().mockResolvedValue(true)}}))
import {canDisposeState,listRow,filterList,useListPresentation} from './listPresentation'
import {planMatches,planCounts} from './planCatalogue'
import {submitSampleDispose,changeResubmit} from '@/services/pipeline'
describe('Template list business adapters',()=>{
 it('uses disposal and void dates and lets all flow date ranges constrain all states',()=>{
  const rows=[listRow({reportNo:'R1',sampleNo:'S1',disposalDate:'2026-11-01 08:00:00',voidedAt:'2026-11-02 09:00:00',inboundTime:'2026-10-01',samplePickup:{outTime:'2026-10-02',pickupTime:'2026-10-03'}})]
  expect(filterList(rows,{dateField:'disposalDate',from:'2026-11-01',to:'2026-11-01'},'disposal')).toHaveLength(1)
  expect(filterList(rows,{dateField:'voidedAt',from:'2026-11-03'},'cancel')).toHaveLength(0)
  expect(filterList(rows,{status:'',dates:{inbound:{from:'2026-10-02'}}},'flow')).toHaveLength(0)
 })
 it.each(['flow','disposal'])('shows the report number in %s and keeps it in available columns',kind=>{
  const c=reactive<any>({rows:[{reportNo:'LAB-TEST-1',sampleNo:'TEST-1',status:'待审核',sampleStatus:'已领取'}],title:'列表',session:{can:()=>true,canAction:()=>true},load:vi.fn()})
  const m=useListPresentation(c,kind)
  expect(m.columns.find((column:any)=>column.key==='reportCode')).toMatchObject({label:'报告编号'})
  expect(m.rows.items[0].reportCode).toBe('LAB-TEST-1')
  m.toggleColumn('reportCode',false);expect(m.columns.some((column:any)=>column.key==='reportCode')).toBe(false)
  m.patch({columns:undefined});expect(m.columns.some((column:any)=>column.key==='reportCode')).toBe(true)
 })
 it('keeps logistics operators, dates, sample names and personnel in their own fields',()=>{
  const row=listRow({reportNo:'R',sampleNo:'S',project:'检测参数',projectName:'工程',sampleOrProjectName:'样品',schemeName:'方案',testItems:'风量',registrar:'登记人',owner:'录入人',workflowDates:{sampleInboundAt:'2026-11-01',samplePickupAt:'2026-11-03'},samplePickup:{managerName:'出库人',outTime:'2026-11-02',receiverName:'领样人',pickupTime:'2026-11-03'}})
  expect(row).toMatchObject({name:'样品',parameters:'风量',projectName:'方案',engineeringName:'工程',owner:'登记人',dataEntryPerson:'录入人',inboundDate:'2026-11-01',outboundDate:'2026-11-02',outboundPerson:'出库人',collectionDate:'2026-11-03',collectionPerson:'领样人'})
  expect(listRow({project:'检测参数'}).name).toBe('')
 })
 const report=(status='检测录入中')=>({reportNo:'R1',sampleNo:'S1',sampleStatus:'已领取',status,schemeCode:'A',department:'科室甲'})
 const controller=(rows:any[])=>reactive<any>({rows,title:'列表',session:{can:()=>true,canAction:()=>true},load:vi.fn(),view:vi.fn(),edit:vi.fn()})
 it('does not enable disposal when the display status replaced the report workflow state',()=>{expect(canDisposeState({...report(),status:'已领取',workflowStatus:'检测录入中'})).toBe(false);expect(canDisposeState(report('待审核'))).toBe(true);expect(canDisposeState({...report('待审核'),sampleStatus:'已入库'})).toBe(false)})
 it('uses actual report identifiers for disposal, preserves unsupported undo as disabled',async()=>{const c=controller([report('待审核')]),m=useListPresentation(c,'disposal'),r=m.rows.items[0];expect(m.canDispose(r,'undo')).toBe(false);m.openDisposal(r,'dispose');await m.submitDisposal();expect(submitSampleDispose).toHaveBeenCalledWith('R1');expect(c.load).toHaveBeenCalledOnce()})
 it('submits complete-change through backend transition rather than opening the edit form',async()=>{const c=controller([report('委托更改中')]),m=useListPresentation(c,'change');await m.complete(m.rows.items[0]);expect(changeResubmit).toHaveBeenCalledWith('R1',{});expect(c.edit).not.toHaveBeenCalled()})
 it('keeps unsupported task transitions disabled and respects backend return-stock capability',()=>{const m=useListPresentation(controller([report()]),'task'),r=m.rows.items[0];expect(r.canReturn).toBe(false);expect(r.canPrintTask).toBe(false);expect(m.canRestock(r)).toBe(false);r.source.canReturnStock=true;expect(m.canRestock(r)).toBe(true)})
 it('distinguishes identical plan codes across departments and applies exclusions',()=>{const selection={groupIds:['科室甲'],planIds:[],excludedPlanIds:[JSON.stringify(['科室甲','A'])]};expect(planMatches(report(),selection)).toBe(false);expect(planMatches({...report(),schemeCode:'B'},selection)).toBe(true);expect(planMatches({...report(),department:'科室乙'},selection)).toBe(false)})
 it('counts disposal and task scopes from different actual eligibility conditions',()=>{const counts=planCounts([report(),report('待审核'),{...report('待归档'),sampleStatus:'已处置'}]);expect(counts.flowSampleCount).toBe(3);expect(counts.taskQuerySampleCount).toBe(2);expect(counts.disposalSampleCount).toBe(2)})
 it('filters and sorts the complete authorized list before pagination',()=>{const rows=[listRow({...report(),sampleNo:'S10'}),listRow({...report(),sampleNo:'S2'})];expect(filterList(rows,{sort:'code',direction:'asc'},'task').map(r=>r.code)).toEqual(['S2','S10']);expect(filterList(rows,{searchField:'reportCode',contains:'missing'},'task')).toEqual([])})
 it('routes stock receipt through the existing controller and disables unsupported undo',async()=>{const receive=vi.fn(),c=reactive<any>({...controller([{...report(),sampleStatus:'待入库'}]),canReceive:(r:any)=>r.sampleStatus==='待入库',receive}),m=useListPresentation(c,'inbound'),r=m.rows.items[0];expect(m.mode).toBe('inbound');expect(m.canOperate(r,'undo')).toBe(false);await m.openOperation(r,'receive');expect(receive).toHaveBeenCalledWith(r.source);expect(m.operation).toBeUndefined()})
 it('opens the existing outbound form and only recalls a backend-eligible sample',async()=>{const dispatch=vi.fn(),recall=vi.fn(),c=reactive<any>({...controller([{...report(),sampleStatus:'已入库'}]),canDispatch:(r:any)=>r.sampleStatus==='已入库',canRecall:(r:any)=>r.canRecallSampleOutbound===true,canReturn:()=>true,dispatch,recall}),m=useListPresentation(c,'outbound'),r=m.rows.items[0];expect(m.canOutbound(r,'undo')).toBe(false);m.openOutbound(r,'dispatch');expect(dispatch).toHaveBeenCalledWith(r.source);expect(m.outboundOperation).toBeUndefined();await m.openOutbound(r,'undo');expect(recall).not.toHaveBeenCalled();r.source.canRecallSampleOutbound=true;await m.openOutbound(r,'undo');expect(recall).toHaveBeenCalledWith(r.source)})
})
