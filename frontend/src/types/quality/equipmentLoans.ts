import type { Actor } from '../lims'
import type { EquipmentStatus } from './equipmentLedger'
import type { TableColumn } from '../common/table'
export const equipmentConditionStates = ['正常', '异常', '故障', '损坏', '待检查'] as const
export type EquipmentCondition = typeof equipmentConditionStates[number]
export type LoanTab = 'available' | 'records'
export const canManageEquipmentLoans = (actor: Actor) => actor.roles.includes('admin') || actor.roles.includes('quality') && !actor.roles.some(role => ['reviewer', 'approver'].includes(role))
export interface EquipmentLoanRecord {
  id: string; version: number; equipmentId: string; departmentId: string; department: string
  code: string; name: string; model: string; manufacturer: string; keeper: string
  borrowerId: string; borrower: string; borrowedAt: string; borrowedStatus: EquipmentCondition; notes: string
  borrowedById: string; borrowedBy: string; createdAt: string
  returner?: string; returnedAt: string; returnedStatus: EquipmentCondition | ''; returnNotes: string
  returnedById: string; returnedBy: string; updatedAt: string
}
export interface EquipmentLoanRow extends EquipmentLoanRecord { returner: string; equipmentVersion: number; currentStatus: EquipmentStatus; loanStatus: '未领用' | '未归还' | '已归还' }
export const loanRecordDateFields = [{ key: 'borrowedAt', label: '领用日期' }, { key: 'returnedAt', label: '归还日期' }] as const
export const loanRecordSearchFields = [{ key: 'borrowedStatus', label: '领用前状态' }, { key: 'returnedStatus', label: '归还时状态' }, { key: 'code', label: '设备编号' }] as const
export interface EquipmentLoanQuery { dateField?: '' | 'borrowedAt' | 'returnedAt'; from?: string; to?: string; field?: '' | 'borrowedStatus' | 'returnedStatus' | 'code'; value?: string; code?: string; name?: string; manufacturer?: string; status?: 'all' | 'open' | 'returned'; page?: number; pageSize?: number; ids?: string[] }
export interface EquipmentLoanPage { items: EquipmentLoanRow[]; total: number; page: number; pageSize: number }
export interface EquipmentLoanTarget { id: string; version: number; equipmentVersion: number }
export interface EquipmentLoanContext { items: EquipmentLoanRow[] }
export interface EquipmentBorrowInput { records: EquipmentLoanTarget[]; borrower: string; borrowedStatus: EquipmentCondition; date: string; notes: string }
export interface EquipmentReturnInput { records: EquipmentLoanTarget[]; returner: string; date: string; returnedStatus: EquipmentCondition; notes: string }
export const availableEquipmentColumns = [
  { key: 'code', label: '设备编号', required: true }, { key: 'name', label: '设备名称', default: true, truncate: 18, fullTitle: true },
  { key: 'model', label: '规格型号', default: true }, { key: 'loanStatus', label: '领用状态', default: true }, { key: 'keeper', label: '设备管理员', default: true },
  { key: 'department', label: '所属部门' }, { key: 'manufacturer', label: '生产厂家', truncate: 18, fullTitle: true },
] as const satisfies readonly TableColumn<keyof EquipmentLoanRow>[]
export const equipmentLoanColumns = [
  { key: 'borrowedAt', label: '领用日期', default: true }, { key: 'code', label: '设备编号', required: true },
  { key: 'name', label: '设备名称', default: true, truncate: 18, fullTitle: true }, { key: 'borrower', label: '领用人', default: true },
  { key: 'borrowedStatus', label: '领用时设备状态', default: true }, { key: 'loanStatus', label: '归还状态', default: true }, { key: 'keeper', label: '设备管理员', default: true },
  { key: 'model', label: '规格型号' }, { key: 'returnedAt', label: '归还日期' }, { key: 'returnedStatus', label: '归还时设备状态' },
  { key: 'manufacturer', label: '生产厂家', truncate: 18, fullTitle: true }, { key: 'notes', label: '领用备注', truncate: 18, fullTitle: true },
  { key: 'returner', label: '归还人' }, { key: 'returnNotes', label: '归还备注', truncate: 18, fullTitle: true }, { key: 'borrowedBy', label: '领用操作人' }, { key: 'returnedBy', label: '归还操作人' },
] as const satisfies readonly TableColumn<keyof EquipmentLoanRow>[]

export const equipmentLoanRecordColumns = [
  { key: 'code', label: '设备编号', required: true }, { key: 'name', label: '设备名称', default: true, truncate: 18, fullTitle: true },
  { key: 'borrowedAt', label: '领用日期', default: true }, { key: 'borrowedStatus', label: '领用前设备状态', default: true },
  { key: 'borrower', label: '领用人', default: true }, { key: 'returnedAt', label: '归还日期', default: true },
  { key: 'returnedStatus', label: '归还时设备状态', default: true }, { key: 'returner', label: '归还人', default: true },
  { key: 'keeper', label: '设备管理员', default: true }, { key: 'model', label: '规格型号' },
  { key: 'department', label: '所属部门' }, { key: 'manufacturer', label: '生产厂家', truncate: 18, fullTitle: true },
  { key: 'notes', label: '领用备注', truncate: 18, fullTitle: true }, { key: 'returnNotes', label: '归还备注', truncate: 18, fullTitle: true },
  { key: 'borrowedBy', label: '领用操作人' }, { key: 'returnedBy', label: '归还操作人' },
] as const satisfies readonly TableColumn<keyof EquipmentLoanRow>[]
