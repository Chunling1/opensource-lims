import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import Checklist from '@/components/PermissionMenuChecklist.vue'

const permissions = [
  { code: 'dashboard.view', name: '首页', ptype: 'module' },
  { code: 'entrust.view', name: '委托管理', ptype: 'module' },
  { code: 'entrust.agreement.view', name: '合同登记', ptype: 'page' },
  { code: 'sample.return_stock', name: '隐含操作', ptype: 'action' },
  { code: 'legacy.action', name: '历史操作', ptype: 'action' },
]
function render(disabled = false) {
  const wrapper = mount(Checklist, {
    attachTo: document.body,
    props: { modelValue: ['dashboard.view', 'sample.return_stock', 'unknown.saved'], permissions, disabled },
    global: { stubs: {
      ElAlert: true,
      AdaptiveTableActions: { name: 'AdaptiveTableActions', props: ['actions'], emits: ['action'], template: '<div><button v-for="(action, i) in actions" :disabled="action.disabled" @click="$emit(\'action\', i)">{{ action.label }}</button></div>' },
    } },
  })
  return wrapper
}
describe('permission group controls', () => {
  it('starts collapsed and expansion never changes permissions', async () => {
    const wrapper = render()
    const header = wrapper.get('button[aria-expanded]')
    expect(header.attributes('aria-expanded')).toBe('false')
    expect(header.text()).toContain('已选 1 / 1')
    expect(wrapper.get('.accordion-body').isVisible()).toBe(false)
    await header.trigger('click')
    expect(header.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('.accordion-body').isVisible()).toBe(true)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    await header.trigger('click')
    expect(wrapper.get('.accordion-body').isVisible()).toBe(false)
    wrapper.unmount()
  })
  it('toggles only the clicked permission and displays its selected state', async () => {
    const wrapper = render()
    const option = wrapper.get('button[aria-pressed="true"]')
    await option.trigger('click')
    const next = wrapper.emitted('update:modelValue')![0]![0] as string[]
    expect(next).toEqual(['sample.return_stock', 'unknown.saved'])
    await wrapper.setProps({ modelValue: next })
    expect(option.attributes('aria-pressed')).toBe('false')
    expect(option.classes()).toContain('btn-outline-secondary')
    await option.trigger('click')
    expect(wrapper.emitted('update:modelValue')![1]![0]).toEqual([...next, 'dashboard.view'])
    wrapper.unmount()
  })
  it('bulk changes affect only their scope, preserving hidden and historical grants', async () => {
    const wrapper = render()
    const toolbar = wrapper.findAllComponents({ name: 'AdaptiveTableActions' })
    toolbar[0]!.vm.$emit('action', 0)
    const all = wrapper.emitted('update:modelValue')![0]![0] as string[]
    expect(all).toEqual(['dashboard.view', 'sample.return_stock', 'unknown.saved', 'entrust.view', 'entrust.agreement.view'])
    await wrapper.setProps({ modelValue: [...all, 'legacy.action'] })
    toolbar[2]!.vm.$emit('action', 1)
    expect(wrapper.emitted('update:modelValue')![1]![0]).toEqual(['dashboard.view', 'sample.return_stock', 'unknown.saved', 'legacy.action'])
    toolbar[0]!.vm.$emit('action', 1)
    expect(wrapper.emitted('update:modelValue')![2]![0]).toEqual(['sample.return_stock', 'unknown.saved', 'legacy.action'])
    expect(wrapper.text()).toContain('历史操作')
    expect(wrapper.findAll('button[aria-pressed]')).toHaveLength(4)
    wrapper.unmount()
  })
  it('allows readonly expansion but blocks individual and bulk writes', async () => {
    const wrapper = render(true)
    await wrapper.get('button[aria-expanded]').trigger('click')
    expect(wrapper.get('button[aria-expanded]').attributes('aria-expanded')).toBe('true')
    for (const option of wrapper.findAll('button[aria-pressed]')) {
      expect(option.attributes('disabled')).toBeDefined()
      await option.trigger('click')
    }
    wrapper.findAllComponents({ name: 'AdaptiveTableActions' })[0]!.vm.$emit('action', 0)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    wrapper.unmount()
  })
})
