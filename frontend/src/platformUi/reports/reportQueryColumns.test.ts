import { describe, it, expect, vi } from 'vitest'
import { reactive, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { createReportOutputPresentation } from './reportOutputPresentation'
import { reportQueryColumns } from './reportQueryColumns'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import { exportRowsXlsx } from '@/services/xlsxExport'
vi.mock('@/services/xlsxExport',()=>({exportRowsXlsx:vi.fn()}))

describe('Report query columns',()=>{
 it('exposes business and actual-operator fields only on query and exports selected columns',()=>{
  const c=reactive<any>({pageKey:'query',pageName:'报告查询',workRows:[{reportNo:'QA-R',sampleNo:'QA-S',reportReviewedBy:'实际审核人',sampleInboundDate:'2026-10-22'}],session:{canAction:()=>true},openForm:vi.fn(),refreshReportList:vi.fn()})
  const m=createReportOutputPresentation(c)
  expect(m.reportQueryColumns.length).toBeGreaterThan(70)
  expect(m.columns).toHaveLength(8)
  m.toggleColumn('reportReviewedBy',true)
  m.draft.searchField='reportReviewedBy';m.draft.contains='实际审核人';m.search()
  expect(m.rows.total).toBe(1)
  m.exportRows()
  const fields=vi.mocked(exportRowsXlsx).mock.calls.at(-1)![1]
  expect(fields.some(f=>f.key==='reportReviewedBy')).toBe(true)
  expect(fields.some(f=>f.key==='sampleInboundDate')).toBe(false)
  c.pageKey='review'
  expect(m.reportCheckColumns).toHaveLength(8)
 })
 it('has unique keys, grouped operator pairs and no assignment masquerading as actual action',()=>{
  expect(new Set(reportQueryColumns.map(c=>c.key)).size).toBe(reportQueryColumns.length)
  const actors=reportQueryColumns.filter(c=>c.group==='流程操作人')
  expect(actors).toHaveLength(16)
  for(const actor of actors)expect(reportQueryColumns.some(c=>c.key===actor.key.replace(/By$/,'At'))).toBe(true)
 })
 it('filters many columns without losing selection; required sample number stays locked',async()=>{
  const wrapper=mount(TableToolbar,{props:{label:'报告查询',columns:reportQueryColumns,selected:['code','reportReviewedBy'],count:0,exportDisabled:false},global:{stubs:{AdaptiveTableActions:true,BootstrapModal:{template:'<div><slot/><slot name="footer"/></div>'}}}})
  expect(wrapper.find('input[type="checkbox"]').attributes('disabled')).toBeDefined()
  await wrapper.get('#column-group').setValue('流程操作人')
  await wrapper.get('#column-search').setValue('审核')
  expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(1)
  expect((wrapper.get('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true)
  await wrapper.get('input[type="checkbox"]').setValue(false)
  expect(wrapper.emitted('column')?.at(-1)).toEqual(['reportReviewedBy',false])
  await wrapper.get('#column-search').setValue('不存在');await nextTick()
  expect(wrapper.text()).toContain('没有匹配字段')
  expect(wrapper.props('selected')).toEqual(['code','reportReviewedBy'])
  wrapper.unmount()
 })
})
