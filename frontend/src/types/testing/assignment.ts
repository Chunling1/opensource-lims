import type { TableColumn } from '../common/table'
import type { RegistrationPage } from '../commissions/registration'
import type { PlanSelection, PlanSelectionState } from '../samples/inbound'

export const assignmentStates = ['任务分配中', '任务分配完成'] as const
export const assignmentConclusions = ['不判定', '复检', '合格', '不合格'] as const
export const assignmentSearchFields = [
  { value: 'code', label: '样品编号' }, { value: 'commissionCode', label: '委托编号' },
  { value: 'customer', label: '委托单位' }, { value: 'engineeringName', label: '项目名称' },
  { value: 'projectAddress', label: '工程地址' }, { value: 'contact', label: '委托人' },
  { value: 'dataEntryPerson', label: '数据录入人' }, { value: 'reportTitle', label: '报告标题' },
] as const
export const assignmentDateFields = [{ value: 'commissionDate', label: '委托日期' }, { value: 'requestedTestDate', label: '要求试验日期' }] as const
export const assignmentActions = [
  { label: '分配', icon: 'ti ti-user-plus' }, { label: '自动分配', icon: 'ti ti-wand' },
  { label: '撤销分配', icon: 'ti ti-arrow-back-up' }, { label: '打印任务单', icon: 'ti ti-printer' },
  { label: '任务处理记录', icon: 'ti ti-file-description' }, { label: '附件管理', icon: 'ti ti-paperclip' },
] as const
export interface AssignmentSubmission { account: string; name: string; dataEntryPerson: string; tester1: string; tester2: string; date: string }
// Optional fields keep previously saved assignment examples readable.
export interface AssignmentInfo {
  assignedBy?: string; dataEntryPerson?: string; tester1?: string; tester2?: string
  assignedById?: string; dataEntryPersonId?: string; tester1Id?: string; tester2Id?: string
  assignedDate?: string; recordedAt?: string
  recordedBy?: { id: string; name: string }
  conclusion?: typeof assignmentConclusions[number] | '其它'
}
export interface AssignmentQuery {
  plans?: PlanSelection
  searchField?: typeof assignmentSearchFields[number]['value']; contains?: string
  status?: string; sampleType?: string; conclusion?: string
  dateField?: typeof assignmentDateFields[number]['value']; from?: string; to?: string
  page?: number; pageSize?: number; sort?: 'code' | 'commissionDate'; direction?: 'asc' | 'desc'; ids?: string[]
}
export interface AssignmentRow {
  version: number; canAssign: boolean; canUndoAssign: boolean; canPrintTask: boolean
  id: string; code: string; commissionCode: string; reportCode: string; sampleType: string; name: string
  parameters: string; dataStatus: string; projectName: string; contact: string; phone: string
  commissionDate: string; appointmentDate: string; customer: string; engineeringName: string; projectAddress: string
  assignedBy: string; dataEntryPerson: string; tester1: string; tester2: string
  requestedTestDate: string; reportTitle: string; conclusion: string
  attachmentCount: number
}
export interface AssignmentPage extends RegistrationPage<AssignmentRow> { planSelection: PlanSelectionState }
export const assignmentColumns = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'commissionCode', label: '委托编号', default: false },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 12, fullTitle: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 12, fullTitle: true },
  { key: 'dataStatus', label: '数据状态', default: true },
  { key: 'projectName', label: '检测方案', default: false, truncate: 14, fullTitle: true },
  { key: 'contact', label: '委托人', default: false },
  { key: 'phone', label: '委托人电话', default: false },
  { key: 'commissionDate', label: '委托日期', default: false, sort: 'commissionDate' },
  { key: 'appointmentDate', label: '约定检测日期', default: false },
  { key: 'customer', label: '委托单位', default: true, truncate: 14, fullTitle: true },
  { key: 'engineeringName', label: '项目名称', default: false, truncate: 14, fullTitle: true },
  { key: 'projectAddress', label: '工程地址', default: false, truncate: 18, fullTitle: true },
  { key: 'assignedBy', label: '分配人', default: false },
  { key: 'dataEntryPerson', label: '数据录入人', default: false },
  { key: 'tester1', label: '检测人1', default: false },
  { key: 'tester2', label: '检测人2', default: false },
  { key: 'attachmentCount', label: '附件', default: false },
] as const satisfies readonly TableColumn<keyof AssignmentRow>[]
