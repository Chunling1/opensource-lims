import {describe,it,expect,vi} from 'vitest'
import {reactive,nextTick,effectScope} from 'vue'
import {mount} from '@vue/test-utils'
import DataTable from '../components/common/table/DataTable.vue'
import {sortableBusinessColumns} from './listSorting'
import {createReportStagePresentation} from './reports/reportStagePresentation'
import {useListPresentation} from './lists/listPresentation'
import {useRegistrationPresentation} from './commissions/registrationPresentation'

describe('business header sorting',()=>{
 it('renders only approved sort buttons and emits the selected key',async()=>{
  const columns=sortableBusinessColumns([{key:'reportCode',label:'报告编号'},{key:'dataSavedAt',label:'检测保存时间'},{key:'customer',label:'委托单位'},{key:'restockDate',label:'回库日期'}])
  const table=mount(DataTable as any,{props:{label:'报告',rows:[] as any[],columns,rowKey:(r:any)=>r.id,rowLabel:(r:any)=>r.id,sortKey:'reportCode',direction:'asc'}})
  const headers=table.findAll('thead th');expect(headers[0].attributes('aria-sort')).toBe('ascending')
  await headers[1].find('button').trigger('click');expect(table.emitted('sort')).toEqual([['dataSavedAt']])
  expect(headers[2].find('button').exists()).toBe(false);expect(headers[3].find('button').exists()).toBe(false)
 })
 it.each(['review','approval','print','archive','release','query'])('%s transmits sorting for the entire filtered result and resets page',async(pageKey)=>{
  const scope=effectScope(),setReportQuery=vi.fn()
  const m=scope.run(()=>createReportStagePresentation(reactive<any>({pageKey,route:{},session:{canAction:()=>true},workRows:[],serverPaging:true,reportPageState:{total:40},setReportQuery,undoReport:vi.fn()})))!
  const fields=['code','reportCode','entrustNo','entrustDate','contractReviewedAt','dataSavedAt','dataCompletedAt','reportCheckedAt','reportReviewedAt','reportApprovedAt','reportIssuedAt','reportArchivedAt','reportReleasedAt']
  for(const key of fields)expect(m.reportCheckColumns.find((c:any)=>c.key===key)?.sort).toBe(key)
  m.draft.contains='needle';m.search();m.patch({page:3});m.patch({sort:'reportApprovedAt',direction:'desc'});await nextTick()
  expect(setReportQuery.mock.lastCall?.[0]).toMatchObject({contains:'needle',sort:'reportApprovedAt',direction:'desc',page:1})
  m.search();await nextTick();expect(setReportQuery.mock.lastCall?.[0].sort).toBe('reportApprovedAt');scope.stop()
 })
 it.each(['flow','inbound','outbound','disposal','task','change','cancel'])('%s exposes identifiers and changes sort without losing filters',async(kind)=>{
  const scope=effectScope(),setListQuery=vi.fn()
  const m=scope.run(()=>useListPresentation(reactive<any>({serverPaging:true,listPage:{total:30},setListQuery,rows:[],session:{canAction:()=>true}}),kind))!
  expect(m.allColumns.find((c:any)=>c.key==='code')?.sort).toBe('code')
  for(const key of ['reportCode','commissionCode']){const col=m.allColumns.find((c:any)=>c.key===key);if(col)expect(col.sort).toBe(key)}
  m.draft.contains='keep';m.search();m.patch({page:3});m.sort('reportCode');await nextTick()
  expect(setListQuery.mock.lastCall?.[0]).toMatchObject({contains:'keep',sort:'reportCode',direction:'asc',page:1})
  m.sort('reportCode');await nextTick();expect(setListQuery.mock.lastCall?.[0].direction).toBe('desc');scope.stop()
 })
 it('registration sorts both tables from page one',async()=>{
  const scope=effectScope(),setRegistrationQuery=vi.fn()
  const m=scope.run(()=>useRegistrationPresentation(reactive<any>({mode:'review',serverPaging:true,commissionPage:{total:30},registrationSamplePage:{total:30},registrationPageSamples:[],backendEntrust:[],setRegistrationQuery,session:{can:()=>true},onWorkbenchSelectionChange:vi.fn()})))!
  expect(m.sampleColumns.find((c:any)=>c.key==='contractReviewedAt')?.sort).toBe('contractReviewedAt')
  for(const prefix of ['c','s']){m.patch({[prefix+'Page']:3});m.sort(prefix,prefix==='c'?'code':'reportCode');await nextTick();expect(setRegistrationQuery.mock.calls.filter(x=>x[0]===prefix).at(-1)?.[1]).toMatchObject({page:1,direction:'asc'})}scope.stop()
 })
 it('local report fallback sorts the full filtered collection before paging',()=>{
  const scope=effectScope();const m=scope.run(()=>createReportStagePresentation(reactive<any>({pageKey:'query',route:{},session:{canAction:()=>true},workRows:[{reportNo:'R10',sampleNo:'S10'},{reportNo:'R2',sampleNo:'S2'},{reportNo:'R1',sampleNo:'S1'}]})))!
  m.patch({size:1,sort:'reportCode',direction:'asc'});expect(m.rows.items[0].reportCode).toBe('R1');m.patch({page:2});expect(m.rows.items[0].reportCode).toBe('R2');scope.stop()
 })
})
