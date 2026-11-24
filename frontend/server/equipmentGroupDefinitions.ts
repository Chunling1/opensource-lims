import { migrateStandardGroups } from './standardGroupMigration'
import { randomUUID } from 'node:crypto'
import { AppError } from '../src/services/common/errors'
import type { RegistrationDependencies, RegistrationState } from '../src/types/commissions/registration'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import { equipmentGroupColumns, canManageDefinitions, definitionSubject, type DefinitionModule, type EquipmentGroup, type EquipmentGroupRow } from '../src/types/quality/equipmentGroups'
import { registrationCsv } from './registrationDomain'

export function seedStandardGroups(state: RegistrationState) {
  migrateStandardGroups(state)
  state.standardGroups ||= ['国家标准', '行业标准', '地方标准', '团体标准', '企业标准'].map((name, index) => ({ id: `standard-category-${index + 1}`, name, departmentId: 'lab', version: 1 }))
}

export function createEquipmentGroupDefinitions(deps: RegistrationDependencies, module: DefinitionModule = 'equipment') {
  if (module === 'standards') migrateStandardGroups(deps.read!()!)
  const key = module === 'standards' ? 'standardGroups' : 'equipmentGroups', subject = definitionSubject(module)
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || (write ? !canManageDefinitions(user) : !user.roles.some(role => ['admin', 'quality', 'reviewer', 'approver'].includes(role)))) throw new AppError('FORBIDDEN', `无权执行${subject}操作。`)
    return user
  }
  const visible = (group: EquipmentGroup) => deps.actor().scope === 'all' || group.departmentId === deps.actor().departmentId
  const row = (group: EquipmentGroup): EquipmentGroupRow => ({ ...group, department: registrationDepartments.find(item => item.id === group.departmentId)?.name || '无' })
  function detail(id: unknown) {
    actor()
    const group = deps.read!()![key]?.find(item => item.id === id)
    if (!group || !visible(group)) throw new AppError('NOT_FOUND', `${subject}不存在或无权访问，请刷新列表。`)
    return row(group)
  }
  function query(input: Record<string, unknown>, all = false) {
    actor()
    if (input.name !== undefined && (typeof input.name !== 'string' || input.name.length > 200)) throw new AppError('VALIDATION', '列表项值查询条件有误。')
    const pageSize = input.pageSize ?? 10, requestedPage = input.page ?? 1
    if (typeof pageSize !== 'number' || ![10, 20, 50].includes(pageSize) || typeof requestedPage !== 'number' || !Number.isSafeInteger(requestedPage) || requestedPage < 1) throw new AppError('VALIDATION', '分页参数有误。')
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.length > 1000 || input.ids.some(id => typeof id !== 'string'))) throw new AppError('VALIDATION', `${subject}选择有误。`)
    const ids = input.ids as string[] | undefined, name = String(input.name || '').trim().toLocaleLowerCase()
    const items = (deps.read!()![key] || []).filter(group => visible(group) && group.name.toLocaleLowerCase().includes(name) && (!ids || ids.includes(group.id))).map(row)
    const page = Math.min(requestedPage, Math.max(1, Math.ceil(items.length / pageSize)))
    return { items: all ? items : items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, pageSize }
  }
  function save(input: Record<string, unknown>) {
    const user = actor(true), previous = input.id === undefined ? undefined : detail(input.id)
    
    if (typeof input.name !== 'string' || !input.name.trim() || input.name.trim().length > 200) throw new AppError('VALIDATION', '请填写列表项值，最多 200 个字符。', { fieldErrors: { ['name']: '请填写列表项值，最多 200 个字符。' } })
    const name = input.name.trim(), departmentId = previous ? previous.departmentId : user.departmentId
    const state = structuredClone(deps.read!()!)
    if ((state[key] || []).some(group => group.id !== previous?.id && group.departmentId === departmentId && group.name.toLocaleLowerCase() === name.toLocaleLowerCase())) throw new AppError('VALIDATION', '该部门已存在相同的列表项值。', { fieldErrors: { ['name']: '该部门已存在相同的列表项值。' } })
    const saved: EquipmentGroup = { id: previous?.id || randomUUID(), departmentId, name, version: (previous?.version || 0) + 1 }
    const groups = state[key] ||= []
    if (previous) groups[groups.findIndex(group => group.id === previous.id)] = saved
    else groups.push(saved)
    deps.write!(state)
    return row(saved)
  }
  function remove(input: Record<string, unknown>) {
    actor(true)
    const group = detail(input.id)
    
    const state = structuredClone(deps.read!()!)
    state[key] = state[key]!.filter(item => item.id !== group.id)
    for (const [deviceId, ids] of Object.entries(module === 'equipment' ? state.equipmentGroupLinks || {} : {})) {
      if (!ids.includes(group.id)) continue
      state.equipmentGroupLinks![deviceId] = ids.filter(id => id !== group.id)
      const device = state.equipmentLedger?.find(item => item.id === deviceId)
      if (device) device.version = (device.version || 1) + 1
    }
    if (module === 'standards') for (const standard of state.standards || []) {
      if (standard.groupIds.includes(group.id)) { standard.groupIds = standard.groupIds.filter(id => id !== group.id); standard.version++ }
    }
    deps.write!(state)
    return { id: group.id }
  }
  return { query, detail, save, remove, export: (input: Record<string, unknown>) => registrationCsv([equipmentGroupColumns.map(column => column.label), ...query(input, true).items.map(item => equipmentGroupColumns.map(column => item[column.key]))]) }
}
