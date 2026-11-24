import type { FormField, FormSchema } from '../../../types/forms'
import { commissionSections, sampleCommissionSections, type CommissionField } from '../../../types/commissions/commissionFields'
import type { CommissionFieldsInput } from '../../../types/commissions/sampleCommission'
import { registrationInvoiceTypes } from '../../../types/commissions/commissionForm'
export interface CommissionFormModel {
  form: CommissionFieldsInput; code?: string; owner?: string; readonly?: boolean; sample?: boolean
  bulkFields?: string[]; mixedFields?: string[]; displayOwner: string
  departments: readonly { id: string; name: string }[]
}
export const commissionFieldKey = (id: string) => id.slice('commission-'.length) as CommissionField['key']
export function commissionValue(model: CommissionFormModel, key: CommissionField['key']): string {
  if (key === 'code') return model.code || ''
  if (key === 'owner') return model.displayOwner
  if (key === 'handlingDepartmentId' && model.readonly) return model.departments.find(d => d.id === model.form.handlingDepartmentId)?.name || ''
  return model.form[key] ?? ''
}
export function commissionSchema(model: CommissionFormModel): FormSchema<CommissionFormModel> {
  return { sections: (model.sample ? sampleCommissionSections : commissionSections).map((section, index) => ({
    id: `commission-section-${index}`, title: section.title,
    fields: section.fields.map((source): FormField<CommissionFormModel> => {
      const key = source.key
      const base = {
        id: `commission-${key}`, label: source.label, width: source.width,
        labelHidden: (m: CommissionFormModel) => !!m.bulkFields && !source.locked,
        disabled: (m: CommissionFormModel) => !!m.bulkFields && !m.bulkFields.includes(key),
        hint: model.bulkFields && model.mixedFields?.includes(key) && !model.bulkFields.includes(key) ? '所选样品的值不同' : undefined,
      }
      if (key === 'customer') return { ...base, control: 'custom', slot: 'customer' }
      const binding = { get: (m: CommissionFormModel) => commissionValue(m, key), set: (m: CommissionFormModel, value: string) => { if (!source.locked && key !== 'code' && key !== 'owner') m.form[key] = value } }
      if (model.readonly) return { ...base, control: 'text', binding, readonly: true, muted: true }
      if (key === 'code' && model.sample) return { ...base, control: 'custom', slot: 'commission-code' }
      if (key === 'contract') return { ...base, control: 'custom', slot: 'contract' }
      if (key === 'contractParty' || key === 'payer') return { ...base, control: 'custom', slot: key }
      if (key === 'invoiceType') return { ...base, control: 'select', binding, emptyLabel: '请选择发票类型', options: registrationInvoiceTypes.map(value => ({ value, label: value })) }
      if (key === 'handlingDepartmentId') return { ...base, control: 'select', binding, emptyLabel: '请选择经办部门', options: model.departments.map(d => ({ value: d.id, label: d.name })) }
      return { ...base, control: source.type === 'tel' ? 'tel' : 'text', binding, readonly: source.locked, muted: source.locked, maxlength: source.max || 500, placeholder: key === 'code' && !model.code ? '首次保存后自动生成' : undefined }
    }),
  })) }
}
