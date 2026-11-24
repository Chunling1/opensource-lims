import type { EquipmentLedgerRow } from './equipmentLedger'
import type { OverallPlanQuery } from './equipmentOverallPlan'
import type { TableColumn } from '../common/table'
export interface InterimPlanDraft {
  equipmentId: string; year: number; testDate: string; checkDate: string
  points: string; method: string; departmentId: string; notes: string
}
export interface InterimPlanRecord extends InterimPlanDraft { id: string; version: number }
export interface InterimPlanRow extends InterimPlanRecord, Pick<EquipmentLedgerRow, 'code' | 'name' | 'status' | 'model' | 'accuracy' | 'range'> { department: string }
export type InterimPlanQuery = OverallPlanQuery
export interface InterimPlanPage { items: InterimPlanRow[]; total: number; page: number; pageSize: number }
export interface InterimPlanEquipmentRow extends EquipmentLedgerRow { validity: string }
export interface InterimPlanEquipmentPage { items: InterimPlanEquipmentRow[]; total: number; page: number; pageSize: number }
export const interimPlanColumns = [
  { key: 'year', label: '年度', default: true }, { key: 'code', label: '设备编号', required: true },
  { key: 'name', label: '设备名称', default: true }, { key: 'model', label: '规格型号', default: true },
  { key: 'testDate', label: '检定日期', default: false }, { key: 'checkDate', label: '核查时间', default: true },
  { key: 'points', label: '检测点', default: false, truncate: 18, fullTitle: true },
  { key: 'method', label: '核查方法', default: true, truncate: 18, fullTitle: true },
  { key: 'department', label: '实施部门', default: true }, { key: 'notes', label: '备注', default: false, truncate: 18, fullTitle: true },
] as const satisfies readonly TableColumn<keyof InterimPlanRow>[]
