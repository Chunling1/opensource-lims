import { numberInputValue, type FormField, type FormFieldBase, type FormSchema, type FormTab } from '../../../types/forms'
import type { RegistrationSampleInput } from '../../../types/commissions/registration'
import type { SampleTextKey, SampleFlagKey, SampleFormOptions } from '../../../types/commissions/sampleForm'
import { demoCategories } from '../../../services/commissions/registrationService'
export interface SampleFormModel {
  form: RegistrationSampleInput; options: SampleFormOptions; code?: string; reportCode?: string; commissionCode?: string
}
export const sampleFormTabs = [
  { key: 'order', label: '委托信息', tabId: 'sample-order-tab', panelId: 'sample-order-panel' },
  { key: 'sample', label: '样品信息', tabId: 'sample-info-tab', panelId: 'sample-info-panel' },
] as const satisfies readonly FormTab[]
export const optionalSampleDates: Record<string, { key: SampleTextKey; toggle: SampleFlagKey }> = {
  'sample-externalDueDate': { key: 'externalDueDate', toggle: 'hasExternalDueDate' },
  'sample-internalDueDate': { key: 'internalDueDate', toggle: 'hasInternalDueDate' },
  'sample-appointmentDate': { key: 'appointmentDate', toggle: 'hasAppointment' },
}
type Field = FormField<SampleFormModel>
type DetailOptions = Partial<FormFieldBase<SampleFormModel>> & { type?: 'date' | 'number' | 'tel' | 'textarea'; rows?: number; step?: number | 'any' }
export function sampleSchema(options: SampleFormOptions): FormSchema<SampleFormModel> {
  function detail(key: SampleTextKey, label: string, extra: DetailOptions = {}): Field {
    const { type = 'text', ...rest } = extra
    const base = { id: `sample-${key}`, label, ...rest }
    const binding = { get: (m: SampleFormModel) => m.form.details![key], set: (m: SampleFormModel, value: string) => { m.form.details![key] = value } }
    const choices = options.choices[key]
    if (choices) return { ...base, control: 'select', binding, emptyLabel: '请选择', options: choices.map(value => ({ value, label: value })) }
    return { ...base, control: type, binding, maxlength: 2000, min: type === 'number' ? 0 : undefined, step: type === 'number' ? extra.step || 'any' : undefined }
  }
  const custom = (id: string, label: string, slot: string, width?: string, ownLabel = false): Field => ({ id, label, control: 'custom', slot, width, ownLabel })
  const system = (id: string, label: string, get: (m: SampleFormModel) => string | undefined): Field => ({ id, label, width: 'col-md-4', control: 'text', binding: { get: m => get(m) || '' }, readonly: true, placeholder: '保存后自动生成' })
  const root = (key: 'name' | 'notes', label: string, width: string, control: 'text' | 'textarea', maxlength: number, required = false): Field => ({ id: `sample-${key}`, label, width, control, maxlength, required, rows: 3, binding: { get: m => m.form[key], set: (m, value) => { m.form[key] = value } } })
  const date = (key: SampleTextKey, label: string): Field => detail(key, label, { type: 'date', labelSlot: 'optional-date-label', disabled: m => !m.form.details![optionalSampleDates[`sample-${key}`]!.toggle] })
  return { sections: [
    { id: 'sample-public', title: '公共信息', fields: [
      system('sample-code', '样品编号', m => m.code), system('sample-report', '报告编号', m => m.reportCode),
      custom('sample-commission', '委托编号', 'commission', 'col-md-4'),
      custom('sample-projects', '检测项目', 'projects', 'col-md-6'),
      custom('sample-assessment', '是否使用评定标准', 'assessment', 'col-md-6', true),
      detail('testingDepartment', '检测部门', { width: 'col-md-4' }),
      custom('sample-testingLocation', '检测地点', 'testing-location', 'col-md-4'),
      { id: 'sample-category', label: '检测类别', control: 'select', width: 'col-md-4', required: true, emptyLabel: '请选择', options: demoCategories.map(value => ({ value, label: value })), binding: { get: m => m.form.category, set: (m, value) => { m.form.category = value } } },
      root('name', '工程/产品名称', 'col-md-8', 'text', 150, true),
      detail('deliveryDate', '送样日期', { type: 'date', width: 'col-md-4' }),
      detail('nameplate', '铭牌', { width: 'col-md-4' }), detail('appearance', '外观', { width: 'col-md-4' }), detail('appearanceNotes', '其他', { width: 'col-md-4' }),
      detail('taskRecipient', '任务单领取人'), detail('inspectorPhone', '主检人联系电话', { type: 'tel' }), detail('inspector', '指定主检人'),
      custom('sample-trademark', '商标', 'trademark'),
      { id: 'sample-urgent', label: '是否加急', control: 'boolean-select', binding: { get: m => m.form.details!.urgent, set: (m, value) => { m.form.details!.urgent = value } } },
    ] },
    { id: 'sample-report-settings', title: '报告设置', fields: [], slot: 'report-settings' },
    { id: 'sample-project-info', title: '项目信息', fields: [
      detail('productCode', '编号'), custom('sample-manufacturer', '生产单位', 'manufacturer', 'col-md-6 col-xl-8'),
      detail('productionDate', '生产日期', { placeholder: 'YYYY-MM 或 YYYY-MM-DD', width: 'col-md-6 col-xl-3' }),
      { id: 'sample-quantity', label: '样品数量', control: 'number', width: 'col-md-6 col-xl-3', min: 0.000001, step: 'any', required: true, requiredMark: false, binding: { get: m => String(m.form.quantity), set: (m, value) => { m.form.quantity = numberInputValue(value) as number } } },
      detail('specification', '规格型号', { width: 'col-md-6 col-xl-3' }), detail('requestedTestDate', '要求试验日期', { type: 'date', width: 'col-md-6 col-xl-3' }),
      root('notes', '备注', 'col-md-6', 'textarea', 2000), detail('internalNotes', '备注（内部）', { type: 'textarea', rows: 3, width: 'col-md-6' }),
    ] },
    { id: 'sample-sampling', title: '抽样信息', fields: [
      detail('samplingOrganization', '抽样单位'), detail('samplingLocation', '抽样地点'), detail('sampler', '抽样人'),
      detail('samplingTime', '抽样时间', { type: 'date' }), detail('samplingQuantity', '抽样数量', { type: 'number' }), detail('samplingBase', '基数', { type: 'number' }),
      detail('inspectedOrganization', '受检单位'), detail('taskSource', '任务来源'),
    ] },
    { id: 'sample-fees', title: '检测费用', fields: [
      detail('standardPrice', '标准价格', { type: 'number' }),
      ...['折扣价格', '实际价格'].map((label, index): Field => ({ id: `sample-calculated-price-${index}`, label, control: 'text', binding: { get: () => '' }, readonly: true, muted: true })),
      detail('paymentMethod', '付款方式', { labelNote: '为空默认银行转账' }), detail('paymentStatus', '交费情况'), detail('paidAmount', '已缴费（元）', { type: 'number' }), detail('feeNotes', '其他', { width: 'col-md-8' }),
    ] },
    { id: 'sample-subprojects', title: '子项目信息', fields: [], slot: 'subprojects' },
    { id: 'sample-client-requirements', title: '委托方要求', fields: [
      date('externalDueDate', '报告承诺时间（对外）'), date('internalDueDate', '报告承诺时间（内部）'),
      detail('disposalMethod', '样品处理方式'), detail('reportDelivery', '报告交付方式'), detail('mailingAddress', '邮寄地址'), detail('reportCopies', '报告交付份数', { type: 'number', step: 1 }),
      detail('reportForm', '报告形式'), detail('onsiteArrangement', '现场检测时间约定'), date('appointmentDate', '约定检测日期'),
    ] },
  ] }
}
