import type { CommissionFieldsInput } from './sampleCommission'
export type CommissionField = { key: keyof CommissionFieldsInput | 'code' | 'owner'; label: string; width?: string; type?: string; max?: number; locked?: boolean }
export const commissionSections: { title: string; fields: CommissionField[] }[] = [
  { title: '委托基本信息', fields: [
    { key: 'code', label: '委托编号', locked: true, width: 'col-md-6 col-xl-3' }, { key: 'contact', label: '委托人', max: 60, width: 'col-md-6 col-xl-3' }, { key: 'phone', label: '委托人电话', type: 'tel', max: 40, width: 'col-md-6 col-xl-3' },
    { key: 'commissionDate', label: '委托日期', locked: true, width: 'col-md-6 col-xl-3' }, { key: 'contract', label: '合同号' },
    { key: 'erpContract', label: '外部ERP项目编号', locked: true }, { key: 'erpProjectType', label: '外部ERP项目类型', locked: true },
  ] },
  { title: '委托单位信息', fields: [
    { key: 'contractParty', label: '合同甲方', width: 'col-md-6' }, { key: 'payer', label: '其他甲方（付款方）', width: 'col-md-6' },
    { key: 'customer', label: '委托单位', width: 'col-md-6' }, { key: 'customerAddress', label: '委托单位地址', width: 'col-md-6' },
    { key: 'customerLegalRepresentative', label: '委托单位法人' }, { key: 'customerPhone', label: '委托单位电话', type: 'tel', max: 40 }, { key: 'customerPostcode', label: '委托单位邮编', max: 20 },
  ] },
  { title: '工程基本属性', fields: [
    { key: 'projectRegistrationCode', label: '工程备案编号', width: 'col-md-6' }, { key: 'projectTradingCode', label: '工程编码（交易中心）', width: 'col-md-6' },
    { key: 'name', label: '项目名称', width: 'col-md-6', max: 150 }, { key: 'projectAddress', label: '工程地址', width: 'col-md-6' },
  ] },
  { title: '业务办理信息', fields: [
    { key: 'handlingDepartmentId', label: '经办部门' }, { key: 'owner', label: '经办人', locked: true }, { key: 'handlerPhone', label: '经办人联系电话', type: 'tel', max: 40 },
  ] },
  { title: '财务相关信息', fields: [
    { key: 'invoiceType', label: '发票类型' }, { key: 'taxpayerNumber', label: '纳税登记号' }, { key: 'invoiceCompany', label: '企业名称' },
    { key: 'invoiceAddress', label: '营业地址' }, { key: 'bankName', label: '开户银行' }, { key: 'bankAccount', label: '账号' },
  ] },
]
export const sampleCommissionSections = commissionSections.map(section => ({ ...section, fields: section.fields.filter(field => !['customerLegalRepresentative', 'customerPhone', 'customerPostcode'].includes(field.key)).map(field => field.key === 'contract' ? { ...field, label: '合同编号' } : field) }))
export const bulkCommissionFields = sampleCommissionSections.flatMap(section => section.fields).filter(field => !field.locked)
export const bulkCommissionKeys = bulkCommissionFields.map(field => field.key === 'contract' ? 'contractId' : field.key)
