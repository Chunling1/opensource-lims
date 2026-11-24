import type { TableColumn } from '../common/table'
import type { RegistrationPage } from '../commissions/registration'
import type { PlanSelectionState } from '../samples/inbound'
import type { DataEntryQuery, DataEntryRow } from './dataEntry'
export { dataEntrySearchFields as dataQuerySearchFields, dataEntryDateFields as dataQueryDateFields } from './dataEntry'
export { sampleCopyStates as dataQueryStates } from './sampleCopy'

export type DataQueryQuery = DataEntryQuery
export interface DataQueryRow extends DataEntryRow {
  canPrintTask: boolean
  pendingStatus: string; checkDate: string; checker: string; failedParameters: string
}
export const dataQueryActions = [
  { label: '报告预览', icon: 'ti ti-file-search' },
  { label: '查看数据', icon: 'ti ti-eye' },
  { label: '原始记录预览', icon: 'ti ti-file-description' },
  { label: '打印任务单', icon: 'ti ti-printer' },
] as const
export interface DataQueryPage extends RegistrationPage<DataQueryRow> { planSelection: PlanSelectionState }
export const dataQueryColumns = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 12, fullTitle: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 12, fullTitle: true },
  { key: 'dataStatus', label: '当前数据状态', default: true },
  { key: 'pendingStatus', label: '待处理状态', default: false },
  { key: 'engineeringName', label: '项目名称', default: false, truncate: 14, fullTitle: true },
  { key: 'reportTitle', label: '报告标题', default: false, truncate: 14, fullTitle: true },
  { key: 'assignedBy', label: '分配人', default: false },
  { key: 'inspector', label: '指定主检人', default: false },
  { key: 'commissionDate', label: '委托日期', default: false, sort: 'commissionDate' },
  { key: 'customer', label: '委托单位', default: false, truncate: 14, fullTitle: true },
  { key: 'requestedTestDate', label: '要求试验日期', default: true },
  { key: 'testStartDate', label: '试验开始日期', default: false },
  { key: 'testEndDate', label: '试验结束日期', default: false },
  { key: 'tester1', label: '试验人1', default: false },
  { key: 'tester2', label: '试验人2', default: false },
  { key: 'checkDate', label: '校核日期', default: false },
  { key: 'checker', label: '校核人', default: false },
  { key: 'conclusion', label: '检测结果', default: false, truncate: 18, fullTitle: true },
  { key: 'failedParameters', label: '不合格参数项', default: false, truncate: 14, fullTitle: true },
] as const satisfies readonly TableColumn<keyof DataQueryRow>[]
