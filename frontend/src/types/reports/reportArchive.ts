import type { TableColumn } from '../common/table'
import type { ReportPrintRow } from './reportPrint'

export const reportArchiveStatuses = ['待归档', '已归档'] as const
export const reportArchiveDateFields = [
  { value: 'approvalDate', label: '批准日期' },
  { value: 'archiveDate', label: '归档日期' },
  { value: 'commissionDate', label: '委托日期' },
] as const
export const reportArchiveStatusLabels: Record<string, string> = { 待归档: '报告归档中', 已归档: '报告已归档' }
export const reportArchiveColumns: readonly TableColumn<keyof ReportPrintRow>[] = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'changeCount', label: '更改次数' },
  { key: 'commissionCode', label: '委托编号' },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 12, fullTitle: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 12, fullTitle: true },
  { key: 'dataStatus', label: '当前数据状态', default: true },
  { key: 'testPlan', label: '检测方案', truncate: 14, fullTitle: true },
  { key: 'archiveStatus', label: '归档状态', default: true },
  { key: 'form', label: '报告形式' },
  { key: 'archivePerson', label: '归档人', default: true },
  { key: 'archiveDate', label: '归档日期', default: true },
  { key: 'approvalDate', label: '批准日期' },
  { key: 'conclusion', label: '结论' },
  { key: 'commissionDate', label: '委托日期', sort: 'commissionDate' },
  { key: 'customer', label: '委托单位', truncate: 14, fullTitle: true },
  { key: 'contact', label: '委托人' },
  { key: 'engineeringName', label: '项目名称', truncate: 14, fullTitle: true },
]
