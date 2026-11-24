import type { TableColumn } from '../common/table'
import { reportPrintColumns, type ReportPrintRow } from './reportPrint'

export const reportSigningStates = ['报告签章中', '报告签章完成'] as const
export const reportSigningStatuses = ['待签章', '签章中', '待确认', '签章失败', '签章完成'] as const
export const reportSigningColumns: readonly TableColumn<keyof ReportPrintRow>[] = reportPrintColumns.flatMap(column => {
  if (column.key === 'printPerson') return [
    { key: 'signingStatus', label: '签章状态', default: true },
  ] as TableColumn<keyof ReportPrintRow>[]
  if (column.key === 'printDate') return [{ key: 'signingDate', label: '签章日期', default: true }]
  return [column]
})
