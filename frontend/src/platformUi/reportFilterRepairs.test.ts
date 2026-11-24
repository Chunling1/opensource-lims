import {describe,it,expect,vi} from 'vitest'
import {reactive,nextTick,effectScope} from 'vue'
import {mount,flushPromises} from '@vue/test-utils'
import PlanBranch from './commissions/RegistrationTestPlanBranch.vue'
const transport=vi.hoisted(()=>({request:vi.fn()}))
vi.mock('../services/platform/http',()=>({platformRequest:transport.request,getSessionToken:()=>'',setToken:vi.fn()}))
import {planRequest} from './lists/planCatalogue'
import {createReportOutputPresentation} from './reports/reportOutputPresentation'

describe('report filter repairs',()=>{
 it('forwards the active module when the visible plan tree loads',async()=>{
  const testPlans=vi.fn(async(q:any)=>({items:q.sampleScope==='report-query'?[{id:'P',name:'Visible plan',kind:'plan',reportQuerySampleCount:1}]:[],total:1,page:1,pageSize:10}))
  const wrapper=mount(PlanBranch,{props:{keyword:'',sampleScope:'report-query',multiple:true,hideEmpty:true},global:{provide:{'platform-registration-services':{testPlans}}}})
  await flushPromises()
  expect(testPlans.mock.calls[0][0].sampleScope).toBe('report-query')
  expect(wrapper.text()).toContain('Visible plan')
  wrapper.unmount()
 })
 it.each(['report-query','report-review','report-approval','report-print','report-archive','report-distribution'])('shows available plans by default on %s',async sampleScope=>{
  transport.request.mockImplementation(async(path:string)=>path.includes('/lib/schemes')?{tree:[{dept:'QA',schemes:[{code:'P',name:'Plan'}]}]}:{rows:[{department:'QA',testDepartment:'QA',schemeCode:'P',sampleCount:1}]})
  const result:any=await planRequest('/test-plans/selection',{sampleScope,selection:{groupIds:[],planIds:[],excludedPlanIds:[]}})
  expect(result.catalogue.populatedPlanIds).toEqual([JSON.stringify(['QA','P'])])
  expect(transport.request.mock.calls.some(([path])=>path==='/api/samples/plan-counts')).toBe(false)
  const tree:any=await planRequest('/test-plans/query',{sampleScope,parentId:'QA'})
  const countKey=sampleScope.replace(/-([a-z])/g,(_,c)=>c.toUpperCase())+'SampleCount'
  expect(tree.items[0][countKey]).toBe(1)
  transport.request.mockClear()
 })
 it.each([['release','state','已发放'],['print','state','已签发'],['review','checkStatus','已审核'],['approval','checkStatus','已批准']])('synchronizes visible and submitted completed filters in %s',async(pageKey,field,value)=>{
  const scope=effectScope()
  const c=reactive<any>({pageKey,pageName:'Report',workRows:[],serverPaging:true,reportPageState:{total:0},setReportQuery:vi.fn(),session:{canAction:()=>true},refreshReportList:vi.fn(),openForm:vi.fn()})
  const m=scope.run(()=>createReportOutputPresentation(c))!
  m.draft[field]=value;m.search();await nextTick()
  const submitted=c.setReportQuery.mock.lastCall[0]
  scope.stop()
  expect(submitted.rowProjection).toBe('')
  expect(m.draft.status).toBe(submitted.status)
 })
})
