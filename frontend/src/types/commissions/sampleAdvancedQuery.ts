import type { SampleConclusion, SampleWorkflowDateDraft } from './sampleWorkflow'
import { inquirySampleSearchFields } from './registration'

// Pure field metadata shared by the form and the backend query whitelist.
export const sampleAdvancedFields = [
  { key: 'commissionCode', label: '委托编号' },
  { key: 'reportCode', label: '报告编号' },
  { key: 'code', label: '样品编号' },
  { key: 'contract', label: '合同号' },
  { key: 'projectRegistrationCode', label: '工程备案编号' },
  { key: 'projectTradingCode', label: '工程编码（交易中心）' },
  { key: 'erpContract', label: '外部ERP项目编号' },
  { key: 'projectName', label: '项目名称' },
  ...inquirySampleSearchFields.filter(field => ['name', 'customer', 'manufacturer'].includes(field.value)).map(field => ({ key: field.value, label: field.label })),
  { key: 'projects', label: '检测项目' },
  { key: 'specification', label: '规格型号' },
  ...inquirySampleSearchFields.filter(field => !['name', 'customer', 'manufacturer'].includes(field.value)).map(field => ({ key: field.value, label: field.label })),
  { key: 'inspector', label: '指定主检人' },
] as const
export type SampleAdvancedKey = typeof sampleAdvancedFields[number]['key']
export type SampleAdvancedFields = Partial<Record<SampleAdvancedKey, string>>
export interface SampleAdvancedDraft {
  fields: SampleAdvancedFields
  conclusion: SampleConclusion | ''
  workflowDates: SampleWorkflowDateDraft
  dataStatus: string
  sampleType: string
  useDate: boolean
  from: string
  to: string
}
