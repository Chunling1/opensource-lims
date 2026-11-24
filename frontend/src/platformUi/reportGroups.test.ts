import {describe,it,expect,vi} from 'vitest'
import {reactive,nextTick,effectScope,defineComponent} from 'vue'
import {mount} from '@vue/test-utils'
import config from './reportGroups.json'
import {matchesReportGroup,reportGroupChoices,reportGroupOptions} from './reportGroups'
import {createReportStagePresentation} from './reports/reportStagePresentation'
import {useRegistrationPresentation,filterRegistration} from './commissions/registrationPresentation'
import {useListPresentation,filterList,listRow} from './lists/listPresentation'
import RegistrationFilters from '../components/commissions/RegistrationFilters.vue'
const department='空调设备检测部'
const session={dataScope:{department,scopeType:'department'},can:()=>true,canAction:()=>true}

describe('AC report grouping',()=>{
 it('covers every approved code with exact boundaries and department scope',()=>{
  for(const group of config.groups)for(const code of group.codes){
   const row={reportNo:`LAB-2026${code}-0001(E)`,department}
   expect(matchesReportGroup(row,group.value)).toBe(true)
   expect(matchesReportGroup({...row,department:'其他部门'},group.value)).toBe(false)
  }
  expect(matchesReportGroup({reportNo:'2026G（Ⅱ）-0010',department},'工程组')).toBe(true)
  for(const code of ['ZX-JH','QCFS3','QCAY1','G(I)','DFJ','YP'])expect(matchesReportGroup({reportNo:`LAB-2026${code}-0010`,department},'未归组')).toBe(true)
  expect(matchesReportGroup({reportNo:'2026HC-0010',department},'净化组')).toBe(false)
  expect(matchesReportGroup({reportNo:'2026H-0010-1',department},'净化组')).toBe(true)
  expect(reportGroupOptions).not.toContain('声学组');expect(reportGroupOptions).not.toContain('示例站点H')
 })
 it('moves every Shunyi code into thermal-humidity and removes the location group',()=>{
  expect(reportGroupOptions).not.toContain('示例站点C')
  for(const code of ['SYR','SYHP','SYC','SYHR']) {
   const row={reportNo:`LAB-2026${code}-0001(E)`,department}
   expect(matchesReportGroup(row,'热湿组')).toBe(true)
   expect(matchesReportGroup(row,'示例站点C')).toBe(false)
   expect(matchesReportGroup(row,'未归组')).toBe(false)
   expect(matchesReportGroup({...row,department:'其他部门'},'热湿组')).toBe(false)
   expect(matchesReportGroup({...row,reportNo:`2026${code}A-0001`},'热湿组')).toBe(false)
  }
 })
 it('uses one filter for all departments with their own default name',()=>{
  expect(reportGroupChoices(session)[0]).toEqual({value:'',label:department})
  expect(reportGroupChoices(session).map(v=>v.label)).toEqual([department,...reportGroupOptions])
  expect(reportGroupChoices({dataScope:{department:'围护结构检测部',scopeType:'department'}})).toEqual([{value:'',label:'围护结构检测部'}])
  expect(reportGroupChoices({dataScope:{department:'信息中心',scopeType:'all'}})).toContainEqual({value:'__ac_department__',label:department})
  expect(reportGroupChoices(undefined)).toEqual([{value:'',label:'当前部门'}])
 })
 it('submits group alongside the existing registration filters and can clear it',async()=>{
  const DateStub=defineComponent({setup(_, {expose}){expose({validate:()=>true});return()=>null}})
  const wrapper=mount(RegistrationFilters,{props:{kind:'samples',query:{searchField:'reportCode',contains:'0105',dataStatus:'合同评审中',reportGroup:''},reportGroupOptions:reportGroupChoices(session)},global:{stubs:{TemplateDateRange:DateStub}}})
  await wrapper.get('#sample-report-group').setValue('净化组');await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('search')?.[0]?.[0]).toMatchObject({reportGroup:'净化组',contains:'0105',dataStatus:'合同评审中'})
  await wrapper.get('#sample-report-group').setValue('');await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('search')?.[1]?.[0]).toMatchObject({reportGroup:''})
  await wrapper.setProps({reportGroupOptions:reportGroupChoices({dataScope:{department:'围护结构检测部',scopeType:'department'}})});expect(wrapper.get('#sample-report-group').text()).toBe('围护结构检测部');wrapper.unmount()
 })
 it('passes the report filter to the server and resets pagination',async()=>{
  const scope=effectScope();const setReportQuery=vi.fn()
  const c=reactive<any>({pageKey:'query',pageName:'报告查询',workRows:[],session,serverPaging:true,reportPageState:{total:0},setReportQuery,undoReport:vi.fn()})
  const m=scope.run(()=>createReportStagePresentation(c))!
  m.query.page=5;m.draft.reportGroup='校准组';m.search();await nextTick()
  expect(m.query.page).toBe(1);expect(setReportQuery.mock.lastCall?.[0]).toMatchObject({reportGroup:'校准组',page:1})
  scope.stop()
 })
 it('passes registration and stock filters through their existing server requests',async()=>{
  const scope=effectScope(),setRegistrationQuery=vi.fn(),setListQuery=vi.fn()
  const c=reactive<any>({mode:'review',samplesOnly:true,backendEntrust:[],registrationPageSamples:[],serverPaging:true,session,setRegistrationQuery,setListQuery,rows:[],title:'出库',listPage:{total:0},activeListKind:'outbound'})
  const m=scope.run(()=>useRegistrationPresentation(c))!,stock=scope.run(()=>useListPresentation(c,'outbound'))!
  m.sampleQuery.page=8;m.search('s',{reportGroup:'热湿组'});stock.query.page=9;stock.draft.reportGroup='检验';stock.search();await nextTick()
  expect(setRegistrationQuery.mock.lastCall).toEqual(['s',expect.objectContaining({reportGroup:'热湿组',page:1})])
  expect(setListQuery.mock.lastCall?.[0]).toMatchObject({reportGroup:'检验',page:1})
  scope.stop()
 })
 it('keeps client-side complete-list paths consistent',()=>{
  const rows=['H','HC','HR'].map(code=>listRow({reportNo:`LAB-2026${code}-0001`,sampleNo:code,department}))
  expect(filterRegistration(rows,{reportGroup:'净化组'}).map(r=>r.code)).toEqual(['H'])
  expect(filterList(rows,{reportGroup:'校准组'},'task').map(r=>r.code)).toEqual(['HC'])
 })
})
