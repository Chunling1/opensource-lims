import {beforeEach,describe,it,expect,vi} from 'vitest'
import {mount,flushPromises} from '@vue/test-utils'
import {request} from '@/services/http'
import {runManualFinance} from './manualFinance'
import ManualFinanceAction from './ManualFinanceAction.vue'
import { profile, type Profile } from '../../services/platform/auth'
vi.mock('@/services/http',()=>({request:vi.fn()}))
const financeProfile = (roles: string[]): Profile => ({account:'qa',userName:'虚拟验收人员',roleKey:'operator',roleName:'测试',homePath:'/home',dataScope:{department:'虚拟部门',scopeType:'department',description:''},permissions:[],actionPermissions:[],erpPermissions:roles})
beforeEach(()=>{vi.resetAllMocks();profile.value=financeProfile(['view','review','send','reverse'])})
const ready={intakeId:'task',done:false,blocked:false,retryable:false,message:''}
describe('manual finance without automatic retries',()=>{
 it.each([3,4])('completes an acknowledged issuance chain of %i steps',async steps=>{
  vi.mocked(request).mockResolvedValueOnce(ready)
  for(let i=0;i<steps;i++) vi.mocked(request).mockResolvedValueOnce({...ready,done:i===steps-1})
  expect((await runManualFinance('R1','reverse')).done).toBe(true)
  expect(request).toHaveBeenCalledTimes(steps+1)
 })
 it('stops immediately on an intermediate failure without automatic retry',async()=>{
  vi.mocked(request).mockResolvedValueOnce(ready).mockResolvedValueOnce(ready).mockResolvedValueOnce({...ready,blocked:true,retryable:true})
  expect((await runManualFinance('R1','reverse')).blocked).toBe(true)
  expect(request).toHaveBeenCalledTimes(3)
 })
 it('reports each acknowledged step and stops on a transport error without resending',async()=>{
  const progress=vi.fn()
  vi.mocked(request).mockResolvedValueOnce(ready).mockResolvedValueOnce({...ready,message:'反审核：完成'})
    .mockRejectedValueOnce(new Error('来源读取失败'))
  await expect(runManualFinance('R1','reverse',progress)).rejects.toThrow('来源读取失败')
  expect(progress.mock.calls.map(call=>call[0].message)).toEqual(['','反审核：完成'])
  expect(request).toHaveBeenCalledTimes(3)
 })
 it.each([
  {...ready,blocked:false,retryable:false,message:'报告回传：待发送',label:'继续核对并处理'},
  {...ready,blocked:true,retryable:true,retry:{intakeId:'task',attemptId:'attempt',label:'重新发送报告回传'},message:'报告回传：失败',label:'重新发送报告回传'},
 ])('distinguishes continued work from failed steps: $label',async result=>{
  vi.mocked(request).mockResolvedValueOnce({send:{allowed:true,done:false,message:''}})
    .mockResolvedValueOnce(ready).mockResolvedValueOnce(result)
  const wrapper=mount(ManualFinanceAction,{props:{reportNo:'R1',mode:'send'},global:{stubs:{BootstrapModal:{template:'<div><slot/><slot name="footer"/></div>'},FeedbackNotice:{props:['message'],template:'<p>{{ message }}</p>'},LoadState:true,ErrorNotice:true}}})
  await wrapper.find('button').trigger('click');await flushPromises()
  await wrapper.findAll('button').at(-1)!.trigger('click');await flushPromises()
  expect(wrapper.findAll('button').at(-1)!.text()).toBe(result.label)
  expect(wrapper.get('[role="status"]').text()).toContain(result.message)
  wrapper.unmount()
 })
 it('shows progress while awaiting the next ACK and blocks a second click',async()=>{
  let finish:(result:typeof ready)=>void=()=>{}
  vi.mocked(request).mockResolvedValueOnce({reverse:{allowed:true,done:false,message:''}})
    .mockResolvedValueOnce(ready).mockResolvedValueOnce({...ready,message:'反审核：完成；订单同步：待发送'})
    .mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve}))
    .mockResolvedValueOnce({...ready,done:true,message:'签发回传接口全部完成'})
  const wrapper=mount(ManualFinanceAction,{props:{reportNo:'R1',mode:'reverse'},global:{stubs:{BootstrapModal:{template:'<div><slot/><slot name="footer"/></div>'},FeedbackNotice:{props:['message'],template:'<p>{{ message }}</p>'},LoadState:true,ErrorNotice:true}}})
  await wrapper.find('button').trigger('click');await flushPromises()
  await wrapper.findAll('button').at(-1)!.trigger('click');await flushPromises()
  expect(wrapper.get('[role="status"]').text()).toContain('反审核：完成')
  expect(wrapper.findAll('button').at(-1)!.text()).toBe('处理中…')
  expect(wrapper.findAll('button').at(-1)!.attributes('disabled')).toBeDefined()
  await wrapper.findAll('button').at(-1)!.trigger('click');expect(request).toHaveBeenCalledTimes(4)
  finish({...ready,message:'订单同步：完成'});await flushPromises()
  expect(wrapper.findAll('button').at(-1)!.text()).toBe('接口处理完成')
  expect(request).toHaveBeenCalledTimes(5);wrapper.unmount()
 })
 it('retries only the displayed frozen step on an explicit click',async()=>{
  const retry={intakeId:'task',attemptId:'attempt-1',label:'重新发送订单更新'}
  vi.mocked(request).mockResolvedValueOnce({reverse:{done:false,allowed:true,retry,message:'外部ERP可能已收到上次请求'}})
    .mockResolvedValueOnce({...ready,message:'订单更新已收到回执'})
  const wrapper=mount(ManualFinanceAction,{props:{reportNo:'R1',mode:'reverse'},global:{stubs:{BootstrapModal:{template:'<div><slot/><slot name="footer"/></div>'},LoadState:true,ErrorNotice:true}}})
  await wrapper.get('button').trigger('click');await flushPromises()
  const button=wrapper.findAll('button').at(-1)!
  expect(button.text()).toBe(retry.label)
  await button.trigger('click');await flushPromises()
  expect(request).toHaveBeenCalledTimes(2)
  expect(vi.mocked(request).mock.calls[1]![0]).toBe('/api/erp-outbound/one-click/task/retry/attempt-1')
  expect(button.text()).toBe('继续核对并处理')
  wrapper.unmount()
 })
 it('opens, refreshes and reopens an unconfirmed issuance using only status reads',async()=>{
  const message='反审核接口已确认，外部ERP审核状态待核对；订单同步：结果待核对'
  vi.mocked(request).mockResolvedValue({reverse:{done:false,allowed:false,refreshOnly:true,message}})
  const wrapper=mount(ManualFinanceAction,{props:{reportNo:'R1',mode:'reverse'},global:{stubs:{BootstrapModal:{props:['open'],template:'<div v-if="open"><slot/><slot name="footer"/></div>'},LoadState:true,ErrorNotice:true}}})
  await wrapper.get('button').trigger('click');await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain(message)
  const refresh=wrapper.findAll('button').at(-1)!
  expect(refresh.text()).toBe('刷新状态')
  await refresh.trigger('click');await flushPromises()
  await wrapper.findAll('button').find(button=>button.text()==='关闭')!.trigger('click')
  await wrapper.get('button').trigger('click');await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain(message)
  expect(wrapper.findAll('button').at(-1)!.text()).toBe('刷新状态')
  expect(vi.mocked(request).mock.calls).toEqual(Array(3).fill(['/api/erp-outbound/reports/R1/manual-status']))
  wrapper.unmount()
 })
 it('hides the operation for an unassigned account and never requests finance data',()=>{
  profile.value=financeProfile([])
  const w=mount(ManualFinanceAction,{props:{reportNo:'R1',mode:'send'},global:{stubs:{BootstrapModal:true}}})
  expect(w.find('button').exists()).toBe(false)
  expect(request).not.toHaveBeenCalled()
 })
 it('does not expose reversal to a send-only account',()=>{
  profile.value=financeProfile(['view','review','send'])
  const w=mount(ManualFinanceAction,{props:{reportNo:'R1',mode:'reverse'},global:{stubs:{BootstrapModal:true}}})
  expect(w.find('button').exists()).toBe(false)
 })
 it('starts one explicit send and advances once with the finance header',async()=>{
  vi.mocked(request).mockResolvedValueOnce(ready).mockResolvedValueOnce({...ready,done:true})
  expect((await runManualFinance('R1','send')).done).toBe(true)
  const calls=vi.mocked(request).mock.calls
  expect(JSON.parse(calls[0]![1]!.body as string)).toMatchObject({phase:'contract',mode:'send'})
  expect(calls[0]![1]!.headers).toEqual({'X-Erp-Outbound':'1'})
  expect(calls[1]![0]).toContain('/one-click/task/advance');expect(calls).toHaveLength(2)
 })
 it.each([{done:true,blocked:false},{done:false,blocked:true}])('never advances completed/unknown tasks %j',async flags=>{
  vi.mocked(request).mockResolvedValue({...ready,...flags})
  await runManualFinance('R1','reverse');expect(request).toHaveBeenCalledTimes(1)
  expect(JSON.parse(vi.mocked(request).mock.calls[0]![1]!.body as string).phase).toBe('issuance')
 })
 it.each([
  '标准合同和框架合同无需首次合同回传，请在签发完成后使用“外部ERP签发回传”。',
  '此合同为不回传外部ERP合同，仅用于内部业务，不回传外部ERP，也不进行外部ERP反审核。',
 ])('shows ineligibility immediately and disables confirmation: %s',async message=>{
  vi.mocked(request).mockResolvedValueOnce({send:{allowed:false,done:false,message}})
  const wrapper=mount(ManualFinanceAction,{props:{reportNo:'R1',mode:'send'},global:{stubs:{BootstrapModal:{template:'<div><slot/><slot name="footer"/></div>'},FeedbackNotice:{props:['message'],template:'<p>{{ message }}</p>'},LoadState:true,ErrorNotice:true}}})
  await wrapper.find('button').trigger('click');await flushPromises()
  expect(wrapper.text()).toContain(message)
  const confirm=wrapper.findAll('button').at(-1)!
  expect(confirm.attributes('disabled')).toBeDefined()
  await confirm.trigger('click');await flushPromises()
  expect(request).toHaveBeenCalledTimes(1)
  expect(vi.mocked(request).mock.calls[0]![0]).toContain('/manual-status')
  wrapper.unmount()
 })
 it('does not send on opening; explicit success disables repeated submission',async()=>{
  vi.mocked(request).mockResolvedValueOnce({send:{allowed:true,done:false,message:''}}).mockResolvedValueOnce(ready).mockResolvedValueOnce({...ready,done:true,message:'回传成功'})
  const wrapper=mount(ManualFinanceAction,{props:{reportNo:'R1',mode:'send'},global:{stubs:{BootstrapModal:{template:'<div><slot/><slot name="footer"/></div>'},FeedbackNotice:true,LoadState:true,ErrorNotice:true}}})
  await wrapper.find('button').trigger('click');await flushPromises()
  expect(request).toHaveBeenCalledTimes(1)
  const confirm=wrapper.findAll('button').at(-1)!
  await confirm.trigger('click');await flushPromises()
  expect(request).toHaveBeenCalledTimes(3);expect(confirm.attributes('disabled')).toBeDefined()
  await confirm.trigger('click');expect(request).toHaveBeenCalledTimes(3)
  wrapper.unmount()
 })
})
