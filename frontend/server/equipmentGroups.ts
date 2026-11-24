import { AppError } from '../src/services/common/errors'
import type { RegistrationDependencies, RegistrationState } from '../src/types/commissions/registration'
import type { EquipmentGroupContext, EquipmentGroupState } from '../src/types/quality/equipmentGroups'

export function seedEquipmentGroups(state: RegistrationState) {
  state.equipmentGroups = [
    { id: 'equipment-group-lab', name: '实验室设备（示例）', version: 1, departmentId: 'lab' },
    { id: 'equipment-group-field', name: '现场检测设备（示例）', version: 1, departmentId: 'lab' },
    { id: 'equipment-group-backup', name: '备用设备（示例）', version: 1, departmentId: 'lab' },
  ]
  state.equipmentGroupLinks = Object.fromEntries((state.equipmentLedger || []).map((row, index) => [row.id, ['equipment-group-lab', ...(index % 2 === 0 ? ['equipment-group-field'] : [])]]))
}
const invalid = (): never => { throw new AppError('VALIDATION', '设备分组关联参数有误。') }
const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : invalid()
export function createEquipmentGroups(deps: RegistrationDependencies) {
  function targets(ids: unknown) {
    const actor = deps.actor()
    if (deps.locked?.() || !actor.roles.some(role => ['admin', 'quality'].includes(role))) throw new AppError('FORBIDDEN', '无权修改设备分组关联。')
    if (!Array.isArray(ids) || !ids.length || ids.length > 200 || ids.some(id => typeof id !== 'string' || !id || id.length > 100) || new Set(ids).size !== ids.length) return invalid()
    const state = deps.read!()!
    return ids.map(id => {
      const row = state.equipmentLedger?.find(row => row.id === id)
      if (!row || actor.scope !== 'all' && row.departmentId !== actor.departmentId) throw new AppError('NOT_FOUND', '所选设备不存在或无权访问，请刷新列表后重新选择。')
      return row
    })
  }
  function context(input: unknown): EquipmentGroupContext {
    const rows = targets(object(input).ids), state = deps.read!()!
    return {
      records: rows.map(row => ({ id: row.id, version: row.version || 1 })),
      groups: (state.equipmentGroups || []).map(group => {
        const count = rows.filter(row => state.equipmentGroupLinks?.[row.id]?.includes(group.id)).length
        return { ...group, state: count === rows.length ? 'checked' : count === 0 ? 'unchecked' : 'mixed' }
      }),
    }
  }
  function save(input: unknown) {
    const raw = object(input)
    if (!Array.isArray(raw.records) || !Array.isArray(raw.groups)) return invalid()
    const records = raw.records.map(object), rows = targets(records.map(row => row.id)), current = deps.read!()!
    const ids = new Set<string>()
    const groups = raw.groups.map(value => {
      const item = object(value)
      if (typeof item.id !== 'string' || ids.has(item.id) || typeof item.state !== 'string' || !['checked', 'unchecked', 'mixed'].includes(item.state)) return invalid()
      ids.add(item.id)
      const group = current.equipmentGroups?.find(group => group.id === item.id)
      if (!group) throw new AppError('NOT_FOUND', '设备分组不存在，请重新选择。')
      return { id: group.id, state: item.state as EquipmentGroupState }
    })
    // Validate all selected devices and groups before one write. Mixed groups are untouched.
    const next = structuredClone(current), links = next.equipmentGroupLinks ||= {}
    let count = 0
    for (const row of rows) {
      const previous = new Set(links[row.id] || []), updated = new Set(previous)
      for (const group of groups) {
        if (group.state === 'checked') updated.add(group.id)
        else if (group.state === 'unchecked') updated.delete(group.id)
      }
      if (updated.size === previous.size && [...updated].every(id => previous.has(id))) continue
      links[row.id] = [...updated]
      next.equipmentLedger!.find(item => item.id === row.id)!.version = (row.version || 1) + 1
      count++
    }
    if (count) deps.write!(next)
    return { count }
  }
  return { context, save }
}
