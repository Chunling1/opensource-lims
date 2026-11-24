import type { RegistrationPage } from '../commissions/registration'
import type { TableColumn } from '../common/table'
import type { PlanSelectionState } from '../samples/inbound'
import type { AssignmentQuery, AssignmentRow } from './assignment'

export const taskQueryStates = ['委托登记完成', '委托复核中', '委托复核完成', '样品入库中', '样品入库完成', '样品出库中', '样品出库完成', '样品待领取', '样品已领取', '任务分配中', '任务分配完成', '任务处理中', '任务处理完成', '检测数据录入中'] as const
export type TaskQuery = AssignmentQuery
export type TaskQueryRow = Omit<AssignmentRow, 'canAssign' | 'canUndoAssign'> & { inspector: string; canReturn: boolean }
export interface TaskQueryPage extends RegistrationPage<TaskQueryRow> { planSelection: PlanSelectionState }
export const taskQueryColumns = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 12, fullTitle: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 12, fullTitle: true },
  { key: 'dataStatus', label: '当前数据状态', default: true },
  { key: 'projectName', label: '检测方案', default: false, truncate: 14, fullTitle: true },
  { key: 'reportTitle', label: '报告标题', default: false, truncate: 14, fullTitle: true },
  { key: 'assignedBy', label: '分配人', default: false },
  { key: 'inspector', label: '指定主检人', default: false },
  { key: 'contact', label: '委托人', default: false },
  { key: 'phone', label: '委托人电话', default: false },
  { key: 'commissionDate', label: '委托日期', default: true, sort: 'commissionDate' },
  { key: 'customer', label: '委托单位', default: false, truncate: 14, fullTitle: true },
  { key: 'engineeringName', label: '项目名称', default: false, truncate: 14, fullTitle: true },
  { key: 'projectAddress', label: '工程地址', default: false, truncate: 18, fullTitle: true },
  { key: 'requestedTestDate', label: '要求试验日期', default: false },
] as const satisfies readonly TableColumn<keyof TaskQueryRow>[]
