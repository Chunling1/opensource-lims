import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import View from '../views/quality/ErpContentView.vue'
import { platformRequest } from '../services/platform/http'

vi.mock('../services/platform/http', () => ({ platformRequest: vi.fn(), getSessionToken: vi.fn(() => ''), setToken: vi.fn() }))
vi.mock('../services/platform/auth', () => ({ profile: { value: { features: { businessDataCorrection: true } } } }))
const request = vi.mocked(platformRequest)
const record = { label: 'QA-001 · 测试客户', warning: '普通账户不可修改的信息，使用管理员权限修订。',
  revision: 'original-version', fields: [{ key: 'client', label: '委托单位', type: 'text', nullable: true }],
  values: { client: '原客户' } }
const Modal = defineComponent({ props: ['open'], setup: (p, { slots }) => () => p.open ? h('section', [slots.default?.(), slots.footer?.()]) : null })
let wrapper: ReturnType<typeof mount>
function button(text: string) { return wrapper.findAll('button').find(b => b.text().includes(text))! }
beforeEach(() => {
  request.mockImplementation(async (path) => {
    if (String(path).endsWith('/catalog')) return { modules: [{ key: 'contracts', label: '合同' }] } as never
    if (String(path).endsWith('/1')) return structuredClone(record) as never
    return { rows: [{ id: '1', label: 'QA-001 · 测试客户', status: '已发放' }], total: 1 } as never
  })
})
afterEach(() => { wrapper?.unmount(); vi.clearAllMocks(); vi.useRealTimers() })

async function open() {
  wrapper = mount(View, { global: { stubs: { BootstrapModal: Modal, RouterLink: true, CustomerPicker: defineComponent({ props: ['modelValue', 'disabled'], emits: ['update:modelValue'], template: `<div><input id="source-client" :value="modelValue" readonly /><button :disabled="disabled" @click="$emit('update:modelValue', '修订客户')">选择合同客户</button></div>` }) } } })
  await flushPromises()
  await button('管理员修订').trigger('click')
  await flushPromises()
}
describe('administrator corrections', () => {
  it('requires change review, reason and explicit confirmation before writing', async () => {
    await open()
    await button('选择合同客户').trigger('click')
    await button('核对修改').trigger('click')
    expect(button('确认保存').attributes('disabled')).toBeDefined()
    await wrapper.get('#correction-confirm').setValue(true)
    await button('确认保存').trigger('click')
    expect(wrapper.text()).toContain('至少2字')
    expect(request.mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(false)
    await wrapper.get('#correction-reason').setValue('核对原始资料')
    request.mockImplementationOnce(async (_path, options) => {
      expect(options?.body).toEqual({ revision: 'original-version', changes: { client: '修订客户' }, confirmed: true, reason: '核对原始资料' })
      return { message: '已保存管理员修订' } as never
    })
    await button('确认保存').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('已保存管理员修订')
  })
  it('preserves edits after concurrent-save rejection without claiming success', async () => {
    await open()
    await button('选择合同客户').trigger('click')
    await button('核对修改').trigger('click')
    await wrapper.get('#correction-reason').setValue('资料纠正')
    await wrapper.get('#correction-confirm').setValue(true)
    request.mockRejectedValueOnce(new Error('数据已被修改，请重新打开后核对'))
    await button('确认保存').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('数据已被修改')
    await button('返回修改').trigger('click')
    expect(wrapper.get<HTMLInputElement>('#source-client').element.value).toBe('修订客户')
    expect(wrapper.text()).not.toContain('已保存管理员修订')
  })
  it('debounces typing and searches a visible page instead of loading every record', async () => {
    await open()
    await button('关闭').trigger('click')
    vi.useFakeTimers()
    request.mockClear()
    await wrapper.get('#correction-search').setValue('甲')
    await wrapper.get('#correction-search').setValue('甲方')
    await vi.advanceTimersByTimeAsync(301)
    expect(request).toHaveBeenCalledTimes(1)
    expect(request.mock.calls[0]?.[0]).toContain('keyword=%E7%94%B2%E6%96%B9&page=1')
  })
  it('only exposes contract and customer source maintenance', async () => {
    await open()
    expect(wrapper.text()).toContain('外部ERP内容管理')
    expect(request.mock.calls[0]?.[0]).toBe('/api/erp-content/catalog')
    expect(wrapper.find('fieldset').exists()).toBe(false)
  })
})
