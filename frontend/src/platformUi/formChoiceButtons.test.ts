import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, reactive } from 'vue'
import SchemaForm from '../components/forms/SchemaForm.vue'
import { ElCheckbox, ElCheckboxGroup } from './controls'
import type { FormSchema } from '../types/forms'

afterEach(() => { document.body.innerHTML = '' })
describe('shared form choice buttons', () => {
  it('clicking the complete labelled option changes the original boolean and retains required/error semantics', async () => {
    const model = reactive({ confirmed: false })
    const schema: FormSchema<typeof model> = { sections: [{ id: 'checks', title: '核对', fields: [{ id: 'confirmed', label: '技术能力', control: 'checkbox', required: true, hint: '确认后继续', binding: { get: m => m.confirmed, set: (m, value) => { m.confirmed = value } } }] }] }
    const wrapper = mount(SchemaForm<typeof model>, { attachTo: document.body, props: { model, schema, errors: { confirmed: '请确认' } } })
    expect(wrapper.findAll('label[for="confirmed"]')).toHaveLength(1)
    const input = wrapper.get<HTMLInputElement>('#confirmed')
    expect(input.attributes('required')).toBeDefined()
    expect(input.attributes('aria-describedby')).toBe('confirmed-hint confirmed-error')
    expect(input.attributes('aria-invalid')).toBe('true')
    wrapper.get<HTMLLabelElement>('label[for="confirmed"]').element.click(); await nextTick()
    expect(model.confirmed).toBe(true)
    expect(input.element.checked).toBe(true)
    await wrapper.setProps({ readonly: true })
    wrapper.get<HTMLLabelElement>('label[for="confirmed"]').element.click(); await nextTick()
    expect(model.confirmed).toBe(true)
    expect(input.element.disabled).toBe(true)
    wrapper.unmount()
  })
  it('labelled compatibility options preserve group values and block disabled selection', async () => {
    const model = reactive({ values: ['a'], disabled: false })
    const wrapper = mount(defineComponent({ setup: () => () => h(ElCheckboxGroup, { modelValue: model.values, disabled: model.disabled, 'onUpdate:modelValue': (value: string[]) => { model.values = value } }, () => [h(ElCheckbox, { value: 'a', label: '甲' }), h(ElCheckbox, { value: 'b', label: '乙' })]) }), { attachTo: document.body })
    const labels = wrapper.findAll<HTMLLabelElement>('label')
    const ids = wrapper.findAll('input').map(n => n.attributes('id'))
    expect(new Set(ids).size).toBe(2)
    expect(labels[1]!.attributes('for')).toBe(ids[1])
    labels[1]!.element.click(); await nextTick()
    expect(model.values).toEqual(['a', 'b'])
    labels[0]!.element.click(); await nextTick()
    expect(model.values).toEqual(['b'])
    model.disabled = true; await nextTick()
    labels[0]!.element.click(); await nextTick()
    expect(model.values).toEqual(['b'])
    wrapper.unmount()
  })
  it('keeps compact unlabelled row selection and custom true/false values', async () => {
    const compact = mount(ElCheckbox, { props: { modelValue: false }, attrs: { 'aria-label': '选择记录' } })
    expect(compact.get('input').classes()).toContain('form-check-input')
    expect(compact.find('.btn').exists()).toBe(false)
    expect(compact.get('input').attributes('aria-label')).toBe('选择记录')
    const labelled = mount(ElCheckbox, { props: { modelValue: 'off', trueValue: 'on', falseValue: 'off', label: '启用' } })
    await labelled.get('input').setValue(true)
    expect(labelled.emitted('update:modelValue')![0]).toEqual(['on'])
    expect(labelled.emitted('change')![0]).toEqual(['on'])
    await labelled.setProps({ modelValue: 'on' })
    await labelled.get('input').setValue(false)
    expect(labelled.emitted('update:modelValue')![1]).toEqual(['off'])
    compact.unmount(); labelled.unmount()
  })
})
