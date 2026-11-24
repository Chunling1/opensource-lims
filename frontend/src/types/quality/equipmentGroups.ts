import type { Actor } from '../lims'
export const canManageDefinitions = (actor: Actor) => actor.roles.includes('admin') || actor.roles.includes('quality') && !actor.roles.some(role => ['reviewer', 'approver'].includes(role))
export type DefinitionModule = 'equipment' | 'standards'
export const definitionSubject = (module: DefinitionModule) => module === 'standards' ? '标准分组' : '设备分组'
export const definitionApiPath = (module: DefinitionModule) => module === 'standards' ? '/quality/standards/groups' : '/quality/equipment/groups'
export type EquipmentGroupState = 'checked' | 'unchecked' | 'mixed'
export interface EquipmentGroup { id: string; name: string; version: number; departmentId?: string }
export interface EquipmentGroupRow extends EquipmentGroup { department: string }
export interface EquipmentGroupQuery { name?: string; page?: number; pageSize?: number; ids?: string[] }
export interface EquipmentGroupPage { items: EquipmentGroupRow[]; total: number; page: number; pageSize: number }
export const equipmentGroupColumns = [
  { key: 'department', label: '部门名称', default: true },
  { key: 'name', label: '列表项值', required: true, wrap: true },
] as const
export interface EquipmentGroupContext {
  records: { id: string; version: number }[]
  groups: (EquipmentGroup & { state: EquipmentGroupState })[]
}
export interface EquipmentGroupSubmission {
  records: EquipmentGroupContext['records']
  groups: { id: string; version: number; state: EquipmentGroupState }[]
}
