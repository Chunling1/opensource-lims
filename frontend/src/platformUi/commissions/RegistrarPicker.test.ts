import { afterEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Picker from './RegistrarPicker.vue'
import { fetchRegistrarOptions } from '@/services/registrarDirectory'
vi.mock('@/services/registrarDirectory', () => ({ fetchRegistrarOptions: vi.fn() }))
vi.mock('../../stores/session', () => ({ currentActor: { value: 'admin' } }))
const api = vi.mocked(fetchRegistrarOptions)
let wrapper: ReturnType<typeof mount>
const person = { id: 195, name: '同名人员', account: 'last', department: '其他部门', departmentId: 7, enabled: true }
function start(disabled = false) {
  return wrapper = mount(Picker, { props: { kind: 'people', value: '原登记人', disabled }, global: { stubs: {
    BootstrapModal: { props:['open'], template:'<section v-if="open"><slot name="toolbar"/><slot/><slot name="footer"/></section>' },
    TablePagination: { name: 'TablePagination', template:'<button @click="$emit(\'page\',10)">第十页</button>' },
  } } })
}
afterEach(() => { wrapper?.unmount(); vi.clearAllMocks(); vi.useRealTimers() })
it('loads only on explicit selection, searches and pages all people, then emits stable identity', async () => {
  api.mockResolvedValue({ rows:[person], total:195, page:1 })
  start(); expect(api).not.toHaveBeenCalled()
  await wrapper.get('button').trigger('click'); await flushPromises()
  expect(api).toHaveBeenCalledWith('people','',1,expect.any(AbortSignal))
  await wrapper.get('input[aria-label="搜索登记人"]').setValue('last')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(api).toHaveBeenLastCalledWith('people','last',1,expect.any(AbortSignal))
  await wrapper.getComponent({name:'TablePagination'}).vm.$emit('page',10); await flushPromises()
  expect(api).toHaveBeenLastCalledWith('people','last',10,expect.any(AbortSignal))
  await wrapper.get('.list-group-item').trigger('click')
  expect(wrapper.emitted('picked')?.[0]).toEqual([person])
})
it('ignores a delayed result after leaving administrator mode', async () => {
  let resolve!: (data: any) => void
  api.mockReturnValue(new Promise(r => { resolve = r }))
  start(); await wrapper.get('button').trigger('click')
  await wrapper.setProps({disabled:true})
  resolve({rows:[person],total:195,page:1}); await flushPromises()
  expect(wrapper.find('.list-group-item').exists()).toBe(false)
  expect(wrapper.emitted('picked')).toBeUndefined()
})
it('has no selection action in ordinary mode', () => {
  start(true); expect(wrapper.find('button').exists()).toBe(false); expect(api).not.toHaveBeenCalled()
})
