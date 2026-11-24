import type { Actor } from '../lims'
import type { TableColumn } from '../common/table'
export interface MaintenanceCostDraft { name: string; maintainedAt: string; unitPrice: number | null; quantity: number | null; departmentId: string; notes: string }
export interface MaintenanceCostRecord extends MaintenanceCostDraft { id: string; version: number; department: string; totalAmount: number | null }
export interface MaintenanceCostQuery { name?: string; quantity?: string; department?: string; page?: number; pageSize?: number; ids?: string[] }
export interface MaintenanceCostPage { items: MaintenanceCostRecord[]; total: number; page: number; pageSize: number }
export const emptyMaintenanceCost = (): MaintenanceCostDraft => ({ name: '', maintainedAt: '', unitPrice: null, quantity: null, departmentId: '', notes: '' })
export const canManageMaintenanceCosts = (actor: Actor) => actor.roles.includes('admin') || actor.roles.includes('quality') && !actor.roles.some(role => ['reviewer', 'approver'].includes(role))
export { calculateLineTotal as maintenanceCostTotal } from '../../services/common/amount'
export const maintenanceCostColumns = [
  { key: 'name', label: '维护项目', required: true, truncate: 20, fullTitle: true },
  { key: 'maintainedAt', label: '维护日期', default: true },
  { key: 'unitPrice', label: '单价', default: true },
  { key: 'quantity', label: '数量', default: true },
  { key: 'totalAmount', label: '总金额', default: true },
  { key: 'department', label: '部门', default: true },
  { key: 'notes', label: '备注', truncate: 30, fullTitle: true },
] as const satisfies readonly TableColumn<keyof MaintenanceCostRecord>[]
