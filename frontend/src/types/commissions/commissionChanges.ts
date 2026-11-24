import type { RegistrationSampleRow } from './registration'
import type { TableColumn } from '../common/table'

export interface CommissionChangeInfo {
  reportIssueId?: string
  source: string; submittedBy: string; submittedAt: string; type: string; description: string
  result: '问题处理中' | '问题已处理'
  completedAt?: string; completedBy?: { id: string; name: string }
}
export interface CommissionChangeRow extends RegistrationSampleRow {
  problemSource: string; problemSubmitter: string; problemSubmittedAt: string
  problemType: string; problemDescription: string; processingResult: string
}
export interface CommissionChangeQuery {
  from?: string; to?: string; source?: string; result?: string; sampleType?: string
  sort?: 'commissionCode' | 'code' | 'problemSubmittedAt'; direction?: 'asc' | 'desc'
  page?: number; pageSize?: number; ids?: string[]
}
// Mock problem categories; replace with service dictionaries when the issue workflow is connected.
export const changeProblemSources = ['问题处理', '报告更改'] as const
export const changeProcessingResults = ['问题处理中', '问题已处理'] as const
export const commissionChangeColumns = [
  { key: 'commissionCode', label: '委托编号', default: false, sort: 'commissionCode' },
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 14, fullTitle: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 24, fullTitle: true },
  { key: 'dataStatus', label: '数据状态', default: false },
  { key: 'testPlan', label: '检测方案', default: false, truncate: 20, fullTitle: true },
  { key: 'processingResult', label: '处理结果', default: true },
  { key: 'problemSource', label: '问题来源', default: true },
  { key: 'problemSubmitter', label: '问题提交人', default: true },
  { key: 'problemSubmittedAt', label: '问题提交日期', default: true, sort: 'problemSubmittedAt' },
  { key: 'problemType', label: '问题类型', default: false },
  { key: 'problemDescription', label: '问题描述', default: false, truncate: 20, fullTitle: true },
  { key: 'attachmentCount', label: '附件', default: false },
] as const satisfies readonly TableColumn<Extract<keyof CommissionChangeRow, string>>[]
export type CommissionChangeColumnKey = typeof commissionChangeColumns[number]['key']
