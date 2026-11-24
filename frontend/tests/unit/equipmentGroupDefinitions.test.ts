import { describe, it, expect } from 'vitest'
import { createEquipmentGroupDefinitions } from '../../server/equipmentGroupDefinitions'
import { createEquipmentGroups } from '../../server/equipmentGroups'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
function setup(module: 'equipment' | 'standards' = 'equipment') {
  let user: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
  let state: RegistrationState = { commissions: [], samples: [], equipmentLedger: [{ ...emptyEquipment(), id: 'device', code: 'DEVICE-1', name: '设备', departmentId: 'lab', department: '实验室', version: 1 }] }
  const deps = { actor: () => user, read: () => state, write: (next: RegistrationState) => { state = next } }
  return { service: createEquipmentGroupDefinitions(deps, module), other: createEquipmentGroupDefinitions(deps, module === 'equipment' ? 'standards' : 'equipment'), associations: createEquipmentGroups(deps), state: () => state, actor: (next: Partial<Actor>) => { user = { ...user, ...next } } }
}
describe.each(['equipment', 'standards'] as const)('%s definitions', module => {
  it('assigns the current department, trims names, rejects duplicates and versions edits', () => {
    const t = setup(module), group = t.service.save({ name: ' 检测设备 ', departmentId: 'lab2' })
    expect(group).toMatchObject({ name: '检测设备', departmentId: 'lab', version: 1 })
    expect(() => t.service.save({ name: '检测设备' })).toThrow('相同')
    expect(() => t.service.save({ name: '   ' })).toThrow('列表项值')
    const updated = t.service.save({ id: group.id, version: 1, name: '新分组', departmentId: 'lab2' })
    expect(updated).toMatchObject({ departmentId: 'lab', name: '新分组', version: 2 })
    expect(t.service.save({ id: group.id, version: 1, name: '后提交覆盖' })).toMatchObject({ name: '后提交覆盖', version: 3 })
    expect(t.service.detail(group.id).name).toBe('后提交覆盖')
    t.service.remove({ id: group.id, version: 1 })
    expect(t.service.query({}).total).toBe(0)
  })
  it('scopes reads, exports and writes by department and role', () => {
    const t = setup(module), group = t.service.save({ name: '一组' })
    t.actor({ departmentId: 'lab2', scope: 'department' })
    expect(t.service.query({}).total).toBe(0)
    expect(t.service.export({})).not.toContain('一组')
    expect(() => t.service.detail(group.id)).toThrow('无权')
    expect(() => t.service.remove({ id: group.id, version: 1 })).toThrow('无权')
    expect(() => t.service.save({ id: group.id, version: 1, name: '越权' })).toThrow('无权')
    expect(t.service.save({ name: '一组' }).departmentId).toBe('lab2')
    t.actor({ roles: ['quality', 'reviewer'] })
    expect(t.service.query({}).total).toBe(1)
    expect(() => t.service.save({ name: '只读' })).toThrow('无权')
  })
  it('isolates records from the other definition module', () => {
    const t = setup(module), row = t.service.save({ name: '相同列表项值' }), other = t.other.save({ name: '相同列表项值' })
    expect(t.service.query({}).total).toBe(1); expect(t.other.query({}).total).toBe(1)
    expect(() => t.other.detail(row.id)).toThrow('不存在')
    expect(() => t.service.remove({ id: other.id, version: other.version })).toThrow('不存在')
    t.service.remove({ id: row.id, version: row.version })
    expect(t.other.detail(other.id).version).toBe(1)
    expect(t.state().equipmentLedger![0]!.version).toBe(1)
  })
  it('queries, paginates and exports only the requested results', () => {
    const t = setup(module)
    const rows = Array.from({ length: 12 }, (_, i) => t.service.save({ name: `分组${i}` }))
    expect(t.service.query({ page: 2, pageSize: 10 }).items).toHaveLength(2)
    expect(t.service.query({ name: '分组1' }).total).toBe(3)
    const csv = t.service.export({ ids: [rows[0]!.id, rows[1]!.id] })
    expect(csv).toContain('部门名称'); expect(csv).toContain('列表项值')
    expect(csv).toContain('"分组0"'); expect(csv).not.toContain('"分组2"')
    expect(() => t.service.query({ pageSize: 7 })).toThrow('分页')
  })
  if (module === 'equipment') it('shares groups with associations and removes links without deleting devices', () => {
    const t = setup(module), group = t.service.save({ name: '关联分组' })
    const context = t.associations.context({ ids: ['device'] })
    expect(context.groups[0]!.id).toBe(group.id)
    t.associations.save({ ...context, groups: context.groups.map(item => ({ ...item, state: 'checked' })) })
    const stale = t.associations.context({ ids: ['device'] })
    t.service.remove({ id: group.id, version: group.version })
    expect(t.service.query({}).total).toBe(0)
    expect(t.state().equipmentLedger).toHaveLength(1)
    expect(t.state().equipmentGroupLinks?.device).toEqual([])
    expect(t.state().equipmentLedger![0]!.version).toBe(3)
    expect(() => t.associations.save(stale)).toThrow('不存在')
  })
})
