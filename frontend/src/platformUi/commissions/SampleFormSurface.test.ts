import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import Surface from './SampleFormSurface'

describe('Sample registration page presentation', () => {
  it('renders existing form and action slots without a modal', () => {
    const wrapper = mount(Surface, { props: { modelValue: true }, slots: { default: '<input value="原字段值" />', footer: '<button>保存样品单</button>' } })
    expect(wrapper.find('input').element.value).toBe('原字段值')
    expect(wrapper.text()).toContain('保存样品单')
    expect(wrapper.find('.modal').exists()).toBe(false)
    wrapper.unmount()
  })
  it('cannot leave until the original unsaved-draft guard completes', async () => {
    let approve: (() => void) | undefined
    const guard=vi.fn((done: () => void) => { approve=done })
    const wrapper=mount(Surface,{props:{modelValue:true,beforeClose:guard}})
    await wrapper.get('button').trigger('click')
    expect(guard).toHaveBeenCalledOnce()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    approve!()
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    wrapper.unmount()
  })
  it('does not display or mount fields while the form is closed', () => {
    const wrapper=mount(Surface,{props:{modelValue:false},slots:{default:'<input value="历史资料" />'}})
    expect(wrapper.find('input').exists()).toBe(false)
    wrapper.unmount()
  })
  it('uses the entrust page labels with the same close guard', async () => {
    const guard = vi.fn()
    const wrapper = mount(Surface, { props: { modelValue: true, returnLabel: '返回委托登记', formLabel: '委托信息表单', beforeClose: guard } })
    expect(wrapper.attributes('aria-label')).toBe('委托信息表单')
    expect(wrapper.get('button').text()).toBe('返回委托登记')
    await wrapper.get('button').trigger('click')
    expect(guard).toHaveBeenCalledOnce()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    wrapper.unmount()
  })
  it('embeds the same fields without duplicate navigation or footer actions', () => {
    const wrapper=mount(Surface,{props:{modelValue:true,embedded:true},slots:{default:'<input value="已保存资料" />',header:'不重复标题',footer:'不重复保存'}})
    expect(wrapper.get('input').element.value).toBe('已保存资料')
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('不重复')
    wrapper.unmount()
  })
})
