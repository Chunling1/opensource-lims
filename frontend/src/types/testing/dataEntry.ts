import type { RegistrationPage } from '../commissions/registration'
import type { TableColumn } from '../common/table'
import type { PlanSelectionState } from '../samples/inbound'
import type { AssignmentQuery, AssignmentRow } from './assignment'

export const dataEntryStates = ['检测数据录入中', '检测数据录入完成'] as const
export const dataEntrySearchFields = [
  { value: 'code', label: '样品编号' }, { value: 'reportCode', label: '报告编号' },
  { value: 'commissionCode', label: '委托编号' }, { value: 'customer', label: '委托单位' },
  { value: 'contact', label: '委托人' }, { value: 'engineeringName', label: '项目名称' },
  { value: 'dataEntryPerson', label: '数据录入人' },
  { value: 'reportTitle', label: '报告标题' },
] as const
export const dataEntryDateFields = [
  { value: 'commissionDate', label: '委托日期' }, { value: 'requestedTestDate', label: '要求试验日期' },
  { value: 'testStartDate', label: '试验开始日期' }, { value: 'testEndDate', label: '试验结束日期' },
] as const
// Saved testing facts supplied by the backend; not inferred from assigned personnel.
export interface DataEntryInfo { testDates?: import('./dataEntryDetail').TrialDate[]; tester1?: string; tester2?: string }
export interface DataEntryQuery extends Omit<AssignmentQuery, 'searchField' | 'dateField'> {
  searchField?: typeof dataEntrySearchFields[number]['value']
  dateField?: typeof dataEntryDateFields[number]['value']
}
export interface DataEntryRow extends Omit<AssignmentRow, 'canAssign' | 'canUndoAssign' | 'canPrintTask'> {
  inspector: string; assignedDate: string; testStartDate: string; testEndDate: string; canReturn: boolean; canVoid?: boolean; canEdit?: boolean; canComplete?: boolean; canUndo?: boolean; canView?: boolean; canManageOriginals?: boolean
}
export interface DataEntryPage extends RegistrationPage<DataEntryRow> { planSelection: PlanSelectionState }
export const dataEntryActions = [
  { label: '数据录入', icon: 'ti ti-edit' }, { label: '报告填写', icon: 'ti ti-file-pencil' }, { label: '录入完成', icon: 'ti ti-circle-check' },
  { label: '撤销完成', icon: 'ti ti-arrow-back-up' }, { label: '查看数据', icon: 'ti ti-file-search' },
  { label: '退回', icon: 'ti ti-arrow-back-up' },
  { label: '附件管理', icon: 'ti ti-paperclip' }, { label: '作废', icon: 'ti ti-circle-x' },
] as const
export const dataEntryColumns = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 12, fullTitle: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 12, fullTitle: true },
  { key: 'dataStatus', label: '当前数据状态', default: true },
  { key: 'projectName', label: '检测方案', default: false, truncate: 14, fullTitle: true },
  { key: 'reportTitle', label: '报告标题', default: false, truncate: 14, fullTitle: true },
  { key: 'customer', label: '委托单位', default: false, truncate: 14, fullTitle: true },
  { key: 'attachmentCount', label: '附件', default: false },
  { key: 'requestedTestDate', label: '要求试验日期', default: true },
  { key: 'commissionDate', label: '委托日期', default: false, sort: 'commissionDate' },
  { key: 'assignedBy', label: '分配人', default: false },
  { key: 'inspector', label: '指定主检人', default: false },
  { key: 'assignedDate', label: '分配日期', default: false },
  { key: 'testStartDate', label: '试验开始日期', default: false },
  { key: 'testEndDate', label: '试验结束日期', default: false },
  { key: 'tester1', label: '试验人1', default: false },
  { key: 'tester2', label: '试验人2', default: false },
  { key: 'conclusion', label: '结论状态', default: false },
] as const satisfies readonly TableColumn<keyof DataEntryRow>[]
