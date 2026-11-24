import type { RegistrationPage } from '../commissions/registration'
import type { TableColumn } from '../common/table'
import type { PlanSelectionState } from '../samples/inbound'
import type { AssignmentQuery, AssignmentRow } from './assignment'

export const pickupStates = ['样品待领取', '样品已领取'] as const
export type PickupQuery = AssignmentQuery
export interface PickupReceipt { account: string; name: string; date: string }
export type PickupRow = Omit<AssignmentRow, 'canAssign' | 'canUndoAssign' | 'canPrintTask'> & { inspector: string; canPickup: boolean }
export interface PickupPage extends RegistrationPage<PickupRow> { planSelection: PlanSelectionState }
export const pickupColumns = [
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
  { key: 'commissionDate', label: '委托日期', default: true, sort: 'commissionDate' },
  { key: 'requestedTestDate', label: '要求试验日期', default: false },
] as const satisfies readonly TableColumn<keyof PickupRow>[]
