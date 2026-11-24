import type { Actor } from '../lims'
import type { TableColumn } from '../common/table'
export interface ConsumableDraft { name: string; specification: string; purchasedAt: string; unitPrice: number | null; quantity: number | null; departmentId: string; notes: string }
export interface ConsumableRecord extends ConsumableDraft { id: string; version: number; department: string; totalAmount: number | null }
export interface ConsumableQuery { name?: string; quantity?: string; department?: string; page?: number; pageSize?: number; ids?: string[] }
export interface ConsumablePage { items: ConsumableRecord[]; total: number; page: number; pageSize: number }
export const emptyConsumable = (): ConsumableDraft => ({ name: '', specification: '', purchasedAt: '', unitPrice: null, quantity: null, departmentId: '', notes: '' })
export const canManageConsumables = (actor: Actor) => actor.roles.includes('admin') || actor.roles.some(role => ['quality', 'inventory'].includes(role)) && !actor.roles.some(role => ['reviewer', 'approver'].includes(role))
export { calculateLineTotal as consumableTotal } from '../../services/common/amount'
export const consumableColumns = [
  { key: 'name', label: '物质名称', required: true, truncate: 20, fullTitle: true },
  { key: 'specification', label: '规格型号', default: true, truncate: 18, fullTitle: true },
  { key: 'purchasedAt', label: '购买日期', default: true },
  { key: 'unitPrice', label: '单价', default: true },
  { key: 'quantity', label: '数量', default: true },
  { key: 'totalAmount', label: '总金额', default: true },
  { key: 'department', label: '购置部门', default: true },
  { key: 'notes', label: '备注', truncate: 30, fullTitle: true },
] as const satisfies readonly TableColumn<keyof ConsumableRecord>[]
