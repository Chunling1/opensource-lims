import {afterEach,describe,it,expect,vi} from 'vitest'
import {mount,flushPromises} from '@vue/test-utils'
import {profile} from '../services/platform/auth'
import {currentActor,sessionLocked} from '../stores/session'
import {allowedWorkbench,defaultWorkbench} from '../types/dashboard'
import Dashboard from '../views/workspace/DashboardView.vue'
vi.mock('vue-router',()=>({useRoute:()=>({path:'/dashboard/general',meta:{title:'业务工作台',workbench:'general'}})}))
vi.mock('../services/platform/http',()=>({platformRequest:vi.fn(async()=>({pending:1,overdue:0,returned:0,completedToday:0,queues:[{id:'all',title:'全部',total:1}],queue:'all',items:[{id:'R1',code:'S1',reportCode:'R1',name:'待评审样品',status:'合同评审中',to:'/inspection/entrust/contract_review'}],total:1,page:1,pageSize:10,urgent:[],recent:[],trend:[],workload:[],updatedAt:'2026-11-11T00:00:00Z'}))}))
afterEach(()=>{profile.value=undefined;vi.clearAllMocks()})
function identity(permissions:string[],full=false,roles:string[]=[]){
 profile.value={account:'fixture',userName:'测试',roleKey:'operator',roleName:'测试',homePath:'/dashboard',permissions,actionPermissions:[],dataScope:{department:'测试科',scopeType:'department',description:'本部门'},features:{fullPlatformAuthority:full}}
 currentActor.value={id:'fixture',name:'测试',roles,departmentId:'测试科',scope:'department'};sessionLocked.value=false
}
describe('workbench authority matches server profile',()=>{
 it.each([
  [[],false,[],['general']],
  [['entrust.contract_review.view'],false,[],['general']],
  [['testing.data_entry.view'],false,['testing'],['general','analyst']],
  [['report.review.view'],false,['reviewer'],['general','reviewer']],
  [['report.approval.view'],false,['approver'],['general','approver']],
  [[],true,[],['general','admin','analyst','reviewer','approver']],
  [[],false,['admin'],['general']],
 ] as [string[],boolean,string[],string[]][])('uses profile grants %j / full=%s', (permissions,full,roles,expected)=>{
  identity(permissions,full,roles)
  expect(['general','admin','analyst','reviewer','approver'].filter(id=>allowedWorkbench(currentActor.value,id))).toEqual(expected)
  if(full)expect(defaultWorkbench(currentActor.value)).toBe('/dashboard/admin')
 })
 it('renders ordinary contract reviewer tasks returned by the backend',async()=>{
  identity(['entrust.contract_review.view'])
  const w=mount(Dashboard,{global:{stubs:{ScrollableTabs:true,RouterLink:{template:'<a><slot/></a>'}}}})
  await flushPromises()
  expect(w.find('[aria-label="工作台待办区域"]').exists()).toBe(true)
  expect(w.text()).toContain('合同评审中');expect(w.text()).toContain('待评审样品')
  expect(w.text()).not.toContain('在办任务主检分布')
  w.unmount()
 })
})
