import { randomUUID } from 'node:crypto'
import { AppError, problem } from '../src/services/common/errors'
import type { RegistrationDependencies, RegistrationState } from '../src/types/commissions/registration'
import { canManageEquipmentTypes, equipmentTypeColumns, type EquipmentType, type EquipmentTypeRow } from '../src/types/quality/equipmentTypes'
import { registrationCsv } from './registrationDomain'
const key = (name: string) => name.trim().toLocaleLowerCase()
export function seedEquipmentTypes(state: RegistrationState) {
  if (state.equipmentTypes) return
  const names = [...new Set(['检测设备', '辅助设备', '现场检测设备', ...Object.values(state.equipmentProfiles || {}).map(profile => profile.equipmentType).filter(Boolean)])]
  state.equipmentTypes = names.map((name, index) => ({ id: `equipment-type-${index + 1}`, name, lendable: true, notes: '', version: 1 }))
}
export function createEquipmentTypes(deps: RegistrationDependencies) {
  const read = () => deps.read!()!
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || (write ? !canManageEquipmentTypes(user) : !user.roles.some(role => ['admin', 'quality', 'equipment', 'reviewer', 'approver'].includes(role)))) throw new AppError('FORBIDDEN', '无权执行设备类型操作。')
    return user
  }
  function targets(type: EquipmentType, state = read()) {
    return (state.equipmentLedger || []).filter(device => key(state.equipmentProfiles?.[device.id]?.equipmentType || '') === key(type.name))
  }
  const row = (type: EquipmentType): EquipmentTypeRow => ({ ...type, usedCount: targets(type).length })
  function detail(id: unknown) {
    actor(); const type = read().equipmentTypes?.find(type => type.id === id)
    if (!type) throw new AppError('NOT_FOUND', '设备类型不存在，请刷新列表。')
    return row(type)
  }
  function query(input: Record<string, unknown>, all = false) {
    actor()
    if (input.name !== undefined && (typeof input.name !== 'string' || input.name.length > 200)) throw new AppError('VALIDATION', '设备类型查询条件有误。')
    const pageSize = input.pageSize ?? 10, requested = input.page ?? 1
    if (typeof pageSize !== 'number' || ![10, 20, 50].includes(pageSize) || !Number.isSafeInteger(requested) || Number(requested) < 1) throw new AppError('VALIDATION', '分页参数有误。')
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.length > 1000 || input.ids.some(id => typeof id !== 'string' || !id || id.length > 100) || new Set(input.ids).size !== input.ids.length)) throw new AppError('VALIDATION', '所选类型有误。')
    const ids = input.ids as string[] | undefined, name = key(String(input.name || ''))
    const items = (read().equipmentTypes || []).filter(type => key(type.name).includes(name) && (!ids || ids.includes(type.id))).map(row)
    const page = Math.min(Number(requested), Math.max(1, Math.ceil(items.length / pageSize)))
    return { items: all ? items : items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, pageSize }
  }
  function save(input: Record<string, unknown>) {
    actor(true); const previous = input.id === undefined ? undefined : detail(input.id)
    
    if (typeof input.name !== 'string' || !input.name.trim() || input.name.trim().length > 200) throw problem('VALIDATION', '请填写设备类型，最多 200 个字符。', 'name')
    if (typeof input.lendable !== 'boolean') throw problem('VALIDATION', '是否可借出参数有误。', 'lendable')
    if (typeof input.notes !== 'string' || input.notes.length > 2000) throw problem('VALIDATION', '备注不能超过 2000 个字符。', 'notes')
    const state = structuredClone(read()), name = input.name.trim()
    if ((state.equipmentTypes || []).some(type => type.id !== previous?.id && key(type.name) === key(name))) throw problem('VALIDATION', '设备类型已存在。', 'name')
    const saved: EquipmentType = { id: previous?.id || randomUUID(), name, lendable: input.lendable, notes: input.notes.trim(), version: (previous?.version || 0) + 1 }
    const types = state.equipmentTypes ||= []
    if (previous) types[types.findIndex(type => type.id === previous.id)] = saved; else types.push(saved)
    if (previous && previous.name !== name) {
      for (const device of targets(previous, state)) {
        state.equipmentProfiles![device.id]!.equipmentType = name
        device.version = (device.version || 1) + 1
      }
    }
    deps.write!(state); return row(saved)
  }
  function remove(input: Record<string, unknown>) {
    actor(true); const type = detail(input.id)
    
    if (type.usedCount) throw new AppError('VALIDATION', '该设备类型已被台账引用，请先修改相关设备的类型。')
    const state = structuredClone(read()); state.equipmentTypes = state.equipmentTypes!.filter(item => item.id !== type.id); deps.write!(state)
    return { id: type.id }
  }
  return { query, detail, save, remove, export: (input: Record<string, unknown>) => registrationCsv([equipmentTypeColumns.map(column => column.label), ...query(input, true).items.map(item => equipmentTypeColumns.map(column => column.key === 'lendable' ? item.lendable ? '是' : '否' : item[column.key]))]) }
}
