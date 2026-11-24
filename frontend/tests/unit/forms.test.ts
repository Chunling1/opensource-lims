import { describe, expect, it } from 'vitest'
import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import SchemaForm from '../../src/components/forms/SchemaForm.vue'
import { formCondition, validateFormSchema, type FormSchema, type FormBinding } from '../../src/types/forms'
import { commissionSchema, type CommissionFormModel } from '../../src/views/commissions/forms/commissionSchema'
import { sampleSchema, type SampleFormModel } from '../../src/views/commissions/forms/sampleSchema'
import { emptySampleCommission } from '../../src/types/commissions/sampleCommission'
import { emptySampleDetails } from '../../src/types/commissions/sampleForm'
import { bulkCommissionFields } from '../../src/types/commissions/commissionFields'

interface Model { text: string; enabled: boolean }
const schema: FormSchema<Model> = { sections: [{ id: 'basic', title: '信息', fields: [
  { id: 'text', label: '名称', control: 'text', required: true, maxlength: 50, hint: '说明', binding: { get: m => m.text, set: (m, value) => { m.text = value } } },
  { id: 'conditional', label: '额外内容', control: 'textarea', visible: m => m.enabled, binding: { get: m => m.text } },
  { id: 'special', label: '选择', control: 'custom', slot: 'picker' },
] }] }
const binding: FormBinding<Model, string> = { get: m => m.text, set: (m, value) => { m.text = value } }
// These compile-time assertions protect binding types without widening to any/string paths.
const invalid: FormBinding<Model, boolean> = {
  // @ts-expect-error a text value cannot be bound to a boolean control
  get: m => m.text,
}
void invalid

describe('configured forms', () => {
  it('rejects duplicate IDs and missing controls before rendering', () => {
    expect(() => validateFormSchema(schema, ['picker'])).not.toThrow()
    expect(() => validateFormSchema(schema, [])).toThrow('Missing form slot')
    const duplicate = { sections: [{ ...schema.sections[0]!, fields: [...schema.sections[0]!.fields, schema.sections[0]!.fields[0]!] }] }
    expect(() => validateFormSchema(duplicate, ['picker'])).toThrow('Duplicate')
    expect(() => validateFormSchema({ sections: [{ id: 'section', title: '', fields: [], slot: 'absent' }] }, [])).toThrow('Missing form slot')
    expect(() => validateFormSchema({ sections: [{ ...schema.sections[0]!, slot: 'picker' }] }, ['picker'])).toThrow('two renderers')
  })
  it('renders one labelled control, a business slot, conditions, readonly and errors', async () => {
    const model = { text: '原值', enabled: false }
    binding.set!(model, '新值')
    const html = await renderToString(createSSRApp({ render: () => h(SchemaForm<Model>, { schema, model, readonly: true, errors: { text: '请检查名称' } }, { picker: () => h('input', { id: 'special', readonly: true }) }) }))
    expect(html.match(/id="text"/g)).toHaveLength(1)
    expect(html).toContain('for="text"')
    expect(html).toContain('value="新值"')
    expect(html).toContain('readonly')
    expect(html).toContain('aria-describedby="text-hint text-error"')
    expect(html).toContain('请检查名称')
    expect(html).not.toContain('id="conditional"')
    expect(html.match(/id="special"/g)).toHaveLength(1)
    expect(formCondition(m => m.enabled, model)).toBe(false)
    expect(formCondition(undefined, model, true)).toBe(true)
  })
  it('passes conditional readonly and disabled states to custom controls', async () => {
    const model = { text: '', enabled: true }
    const custom: FormSchema<Model> = { sections: [{ id: 'custom-section', title: '自定义', fields: [
      { id: 'custom-input', label: '内容', control: 'custom', slot: 'business', readonly: m => m.enabled, disabled: true },
    ] }] }
    const html = await renderToString(createSSRApp({ render: () => h(SchemaForm<Model>, { schema: custom, model }, { business: (props: { readonly: boolean; disabled: boolean }) => h('input', { id: 'custom-input', readonly: props.readonly, disabled: props.disabled }) }) }))
    expect(html).toContain('id="custom-input" readonly disabled')
  })
  it('keeps commission field variants and bulk eligibility backed by the same metadata', () => {
    const model: CommissionFormModel = { form: emptySampleCommission(), displayOwner: '经办人', departments: [], bulkFields: ['contact'], mixedFields: ['phone'] }
    const fields = commissionSchema(model).sections.flatMap(s => s.fields)
    expect(fields.find(f => f.id === 'commission-customerLegalRepresentative')).toBeDefined()
    expect(formCondition(fields.find(f => f.id === 'commission-contact')!.disabled, model)).toBe(false)
    expect(formCondition(fields.find(f => f.id === 'commission-phone')!.disabled, model)).toBe(true)
    expect(fields.find(f => f.id === 'commission-phone')!.hint).toBe('所选样品的值不同')
    const sampleFields = commissionSchema({ ...model, sample: true }).sections.flatMap(s => s.fields)
    expect(sampleFields.find(f => f.id === 'commission-customerLegalRepresentative')).toBeUndefined()
    expect(sampleFields.find(f => f.id === 'commission-contract')!.label).toBe('合同编号')
    for (const field of bulkCommissionFields) expect(sampleFields.some(f => f.id === `commission-${field.key}`)).toBe(true)
  })
  it('binds nested values without changing string amounts, booleans, or numeric quantity', () => {
    const model: SampleFormModel = { form: { details: emptySampleDetails(), quantity: 1 } as SampleFormModel['form'], options: { choices: {}, subprojectOptions: [] } }
    const fields = sampleSchema(model.options).sections.flatMap(s => s.fields)
    const amount = fields.find(f => f.id === 'sample-standardPrice')!
    if (amount.control !== 'number') throw new Error('Wrong amount control')
    amount.binding.set!(model, '00125.50')
    expect(model.form.details!.standardPrice).toBe('00125.50')
    const quantity = fields.find(f => f.id === 'sample-quantity')!
    if (quantity.control !== 'number') throw new Error('Wrong quantity control')
    quantity.binding.set!(model, '2.5')
    expect(model.form.quantity).toBe(2.5)
    quantity.binding.set!(model, '')
    expect(model.form.quantity).toBe('')
    const urgent = fields.find(f => f.id === 'sample-urgent')!
    if (urgent.control !== 'boolean-select') throw new Error('Wrong boolean control')
    urgent.binding.set!(model, true)
    expect(model.form.details!.urgent).toBe(true)
    expect(formCondition(fields.find(f => f.id === 'sample-externalDueDate')!.disabled, model)).toBe(true)
    expect(model.form.details!.externalDueDate).toBe('')
    const publicIds = sampleSchema(model.options).sections[0]!.fields.map(f => f.id)
    expect(publicIds.slice(0, 10)).toEqual(['sample-code', 'sample-report', 'sample-commission', 'sample-projects', 'sample-assessment', 'sample-testingDepartment', 'sample-testingLocation', 'sample-category', 'sample-name', 'sample-deliveryDate'])
    expect(publicIds.at(-1)).toBe('sample-urgent')
  })
})
