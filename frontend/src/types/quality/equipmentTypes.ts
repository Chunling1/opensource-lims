import type { Actor } from '../lims'
import type { TableColumn } from '../common/table'
export interface EquipmentType { id: string; name: string; lendable: boolean; notes: string; version: number }
export interface EquipmentTypeRow extends EquipmentType { usedCount: number }
export interface EquipmentTypeQuery { name?: string; page?: number; pageSize?: number; ids?: string[] }
export interface EquipmentTypePage { items: EquipmentTypeRow[]; total: number; page: number; pageSize: number }
export const canManageEquipmentTypes = (actor: Actor) => actor.roles.includes('admin') || actor.roles.includes('quality') && !actor.roles.some(role => ['reviewer', 'approver'].includes(role))
export const equipmentTypeColumns = [
  { key: 'name', label: '设备类型', required: true, truncate: 24, fullTitle: true },
  { key: 'lendable', label: '是否可借出', default: true },
  { key: 'notes', label: '备注', default: true, truncate: 36, fullTitle: true },
] as const satisfies readonly TableColumn<keyof EquipmentTypeRow>[]
