import {describe,it,expect,vi} from 'vitest'
import {reactive,defineComponent} from 'vue'
import {shallowMount} from '@vue/test-utils'
import {createReportOutputPresentation} from './reports/reportOutputPresentation'
import {useListPresentation} from './lists/listPresentation'
import ReportStage from './reports/ReportStagePresentation.vue'
import ReportQuery from './reports/ReportQueryListPresentation.vue'
import ReportOutput from './reports/ReportOutputListPresentation.vue'
import Storage from './lists/StorageList.vue'
import Flow from './lists/FlowList.vue'
import Cancellation from './lists/CancellationList.vue'

const dateRange=defineComponent({props:['id','disabled','from','to'],template:'<input :id="id" :disabled="disabled" />'})
const options={global:{stubs:{QueryFormLayout:{template:'<div><slot/><slot name="actions"/></div>'},TemplateDateRange:dateRange}}}

describe('advanced search controls',()=>{
 it.each(['review','approval','print','archive','release','query'])('enables expanded date and conclusion controls on %s',async pageKey=>{
  const c=reactive<any>({pageKey,pageName:'报告',workRows:[],session:{canAction:()=>true},refreshReportList:vi.fn(),openForm:vi.fn()})
  const context=createReportOutputPresentation(c)
  const component=pageKey==='query'?ReportQuery:['review','approval'].includes(pageKey)?ReportStage:ReportOutput
  const wrapper=shallowMount(component,{props:{context},...options})
  const button=wrapper.findAll('button').find(b=>b.text().includes('更多筛选'))!
  await button.trigger('click')
  const section=wrapper.find('[id$="more-filters"]')
  expect(section.isVisible()).toBe(true)
  expect(section.findAll('select').length).toBeGreaterThanOrEqual(2)
  for(const field of section.findAll('select,input'))expect(field.attributes('disabled')).toBeUndefined()
  await section.get('select').setValue('合格')
  expect(context.draft.conclusion).toBe('合格')
  wrapper.unmount()
 })
 it.each(['cancel','disposal','flow'])('enables date controls on %s with all states selected',kind=>{
  const context=useListPresentation(reactive<any>({rows:[],title:'列表',session:{canAction:()=>true,can:()=>true},load:vi.fn()}),kind)
  const component=kind==='cancel'?Cancellation:kind==='disposal'?Storage:Flow
  const wrapper=shallowMount(component,{props:{context},...options})
  const dates=wrapper.findAll('input').filter(input=>input.attributes('id')?.includes('dates'))
  expect(dates.length).toBeGreaterThan(0)
  for(const date of dates)expect(date.attributes('disabled')).toBeUndefined()
  if(kind==='cancel')expect(wrapper.text()).toContain('作废日期')
  wrapper.unmount()
 })
})
