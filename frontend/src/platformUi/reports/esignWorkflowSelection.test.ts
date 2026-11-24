import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import EsignWorkflowSelector from '@/components/EsignWorkflowSelector.vue'

const options = {
  props: { busy: false },
  global: { stubs: { ConfirmationModal: { template: '<section><slot /><slot name="footer" /></section>' } } },
}

describe('completion signing workflow dialog', () => {
  it('defaults to the original workflow and emits only on confirmation', async () => {
    const wrapper = mount(EsignWorkflowSelector, options)
    expect(wrapper.get<HTMLInputElement>('input[value="legacy"]').element.checked).toBe(true)
    expect(wrapper.emitted('confirm')).toBeUndefined()
    await wrapper.get('button.btn-primary').trigger('click')
    expect(wrapper.emitted('confirm')).toEqual([['legacy']])
    wrapper.unmount()
  })

  it('allows selecting staged signing and cancelling without saving', async () => {
    const wrapper = mount(EsignWorkflowSelector, options)
    await wrapper.get('input[value="business_stages_v1"]').setValue(true)
    await wrapper.get('button.btn-light').trigger('click')
    expect(wrapper.emitted('close')).toEqual([[]])
    expect(wrapper.emitted('confirm')).toBeUndefined()
    await wrapper.get('button.btn-primary').trigger('click')
    expect(wrapper.emitted('confirm')).toEqual([['business_stages_v1']])
    wrapper.unmount()
  })

  it('disables both choices and actions while submitting', () => {
    const wrapper = mount(EsignWorkflowSelector, { ...options, props: { busy: true } })
    expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('button:disabled')).toHaveLength(2)
    wrapper.unmount()
  })
})
