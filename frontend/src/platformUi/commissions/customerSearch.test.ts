import {afterEach,describe,expect,it,vi} from 'vitest'
import {mount,flushPromises} from '@vue/test-utils'
import {defineComponent} from 'vue'
import Picker from '@/components/CustomerPicker.vue'
import {fetchCustomerPage} from '@/services/customerDirectory'
import {ElButton,ElInput,ElTag} from '../controls'
vi.mock('@/services/customerDirectory',()=>({fetchCustomerPage:vi.fn(),splitCustomerNames:(v:string)=>v.split('、').filter(Boolean)}))
const wrappers:ReturnType<typeof mount>[]=[]
function setup(){
 const wrapper=mount(Picker,{props:{modelValue:'已保存客户',label:'合同甲方'},global:{components:{ElButton,ElInput,ElTag},stubs:{ElDialog:defineComponent({props:['modelValue'],template:'<div v-if="modelValue"><slot/><slot name="footer"/></div>'}),ElTable:true,ElTableColumn:true,ElPagination:true,ElAlert:true},config:{warnHandler:()=>undefined}}})
 wrappers.push(wrapper);return wrapper
}
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());vi.useRealTimers();vi.clearAllMocks()})
describe('customer server search',()=>{
 it('submits the current keyword on the first click, aborts the previous read and ignores its late result',async()=>{
  const pending:{resolve:(value:any)=>void;signal:AbortSignal}[]=[]
  vi.mocked(fetchCustomerPage).mockImplementation((_q,_p,_s,_r,signal)=>new Promise(resolve=>pending.push({resolve,signal:signal!})))
  const wrapper=setup()
  await wrapper.get('button[aria-label="选择合同甲方"]').trigger('click')
  expect(pending).toHaveLength(1)
  await wrapper.get('input[aria-label="客户名称或编码"]').setValue('测试单位')
  expect(pending[0].signal.aborted).toBe(true)
  await wrapper.get('form').trigger('submit')
  expect(fetchCustomerPage).toHaveBeenLastCalledWith('测试单位',1,20,true,expect.any(AbortSignal))
  pending[1].resolve({rows:[{code:'C2',name:'测试单位'}],total:1,page:1,size:20});await flushPromises()
  pending[0].resolve({rows:[{code:'OLD',name:'旧请求'}],total:58146,page:1,size:20});await flushPromises()
  const state=(wrapper.vm as any).$.setupState
  expect(state.rows.map((r:any)=>r.code)).toEqual(['C2']);expect(state.total).toBe(1);expect(state.loading).toBe(false)
  expect(state.selected[0].name).toBe('已保存客户')
 })
 it('stops periodic reloads and releases loading on timeout without losing selection',async()=>{
  vi.useFakeTimers()
  vi.mocked(fetchCustomerPage).mockImplementation((_q,_p,_s,_r,signal)=>new Promise((_resolve,reject)=>signal!.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')))))
  const wrapper=setup(),state=(wrapper.vm as any).$.setupState
  await wrapper.get('button[aria-label="选择合同甲方"]').trigger('click')
  await vi.advanceTimersByTimeAsync(12001)
  expect(state.loading).toBe(false);expect(state.error).toContain('超时');expect(state.selected[0].name).toBe('已保存客户')
  await vi.advanceTimersByTimeAsync(60000);expect(fetchCustomerPage).toHaveBeenCalledTimes(1)
 })
 it('refresh searches the current input even while debounce is pending',async()=>{
  vi.useFakeTimers();vi.mocked(fetchCustomerPage).mockResolvedValue({rows:[],total:0,page:1,size:20})
  const wrapper=setup();await wrapper.get('button[aria-label="选择合同甲方"]').trigger('click');await flushPromises()
  await wrapper.get('input[aria-label="客户名称或编码"]').setValue('新名称')
  await wrapper.findAll('button').find(b=>b.text()==='刷新客户库')!.trigger('click');await flushPromises()
  expect(fetchCustomerPage).toHaveBeenLastCalledWith('新名称',1,20,true,expect.any(AbortSignal))
  await vi.advanceTimersByTimeAsync(400);expect(fetchCustomerPage).toHaveBeenCalledTimes(2)
 })
})


it('renders removable selected tags, preserves cancelled selection and confirms an empty selection',async()=>{
 vi.mocked(fetchCustomerPage).mockResolvedValue({rows:[],total:0,page:1,size:20})
 const wrapper=setup()
 await wrapper.get('button[aria-label="选择合同甲方"]').trigger('click');await flushPromises()
 await wrapper.get('button[aria-label="移除 已保存客户"]').trigger('click')
 expect(wrapper.find('button[aria-label="移除 已保存客户"]').exists()).toBe(false)
 await wrapper.findAll('button').find(b=>b.text()==='取消选择')!.trigger('click')
 expect(wrapper.emitted('update:modelValue')).toBeUndefined()
 await wrapper.get('button[aria-label="选择合同甲方"]').trigger('click');await flushPromises()
 expect(wrapper.find('button[aria-label="移除 已保存客户"]').exists()).toBe(true)
 await wrapper.get('button[aria-label="移除 已保存客户"]').trigger('click')
 await wrapper.findAll('button').find(b=>b.text()==='确认选择')!.trigger('click')
 expect(wrapper.emitted('update:modelValue')).toEqual([['']]);expect(wrapper.emitted('picked')).toEqual([[[]]])
})


it('permits manual client text without looking up or rewriting contacts; read-only blocks it',async()=>{
 const w=setup();await w.setProps({label:'委托单位',allowManual:true,multiple:true})
 await w.get('input[aria-label="委托单位"]').setValue('手写委托单位')
 expect(w.emitted('update:modelValue')!.at(-1)).toEqual(['手写委托单位'])
 expect(fetchCustomerPage).not.toHaveBeenCalled();expect(w.emitted('picked')).toBeUndefined()
 await w.setProps({disabled:true});expect(w.get('input[aria-label="委托单位"]').attributes('readonly')).toBeDefined()
 await w.get('input[aria-label="委托单位"]').setValue('不能改');expect(w.emitted('update:modelValue')).toHaveLength(1)
})
it('debounces typing and retains selection across bounded pages without duplicate submit',async()=>{
 vi.useFakeTimers();vi.mocked(fetchCustomerPage).mockResolvedValue({rows:[{code:'C2',name:'第二客户'}],total:58154,page:1,size:20})
 const w=setup();await w.setProps({multiple:true});await w.get('button[aria-label="选择合同甲方"]').trigger('click');await flushPromises()
 const input=w.get('input[aria-label="客户名称或编码"]');await input.setValue('客');await input.setValue('客户');await input.setValue('客户甲')
 await vi.advanceTimersByTimeAsync(250);await flushPromises();expect(fetchCustomerPage).toHaveBeenCalledTimes(2)
 expect(fetchCustomerPage).toHaveBeenLastCalledWith('客户甲',1,20,false,expect.any(AbortSignal))
 const state=(w.vm as any).$.setupState;state.toggle({code:'C2',name:'第二客户'});state.changePage(2);await flushPromises()
 expect(fetchCustomerPage).toHaveBeenLastCalledWith('客户甲',2,20,false,expect.any(AbortSignal));expect(state.selected.map((x:any)=>x.name)).toEqual(['已保存客户','第二客户'])
 await input.setValue('客户乙');await w.get('form').trigger('submit');await vi.advanceTimersByTimeAsync(300);expect(fetchCustomerPage).toHaveBeenCalledTimes(4)
 await w.findAll('button').find(b=>b.text()==='取消选择')!.trigger('click');await vi.advanceTimersByTimeAsync(60000);expect(fetchCustomerPage).toHaveBeenCalledTimes(4)
})
