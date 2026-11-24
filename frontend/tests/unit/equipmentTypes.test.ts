import { describe, expect, it } from 'vitest'
import { createEquipmentTypes, seedEquipmentTypes } from '../../server/equipmentTypes'
import { createEquipmentForms } from '../../server/equipmentForm'
import { createEquipmentLoans } from '../../server/equipmentLoans'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }, actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
  seedEquipmentTypes(state)
  const deps = { actor: () => actor, read: () => state, write: (next: RegistrationState) => { state = next } }
  return { api: createEquipmentTypes(deps), forms: createEquipmentForms(deps), loans: createEquipmentLoans(deps), state: () => state, actor: (patch: Partial<Actor>) => { actor = { ...actor, ...patch } } }
}
describe('equipment type definitions', () => {
  it('validates fields, uniqueness and versions and protects data on failure', () => {
    const t = setup(), input = { name: '测试类型', lendable: true, notes: '备注' }
    for (const patch of [{ name: '  ' }, { name: 'x'.repeat(201) }, { lendable: 'yes' }, { notes: 'x'.repeat(2001) }]) expect(() => t.api.save({ ...input, ...patch })).toThrow()
    const first = t.api.save(input)
    expect(() => t.api.save({ ...input, name: ' 测试类型 ' })).toThrow('已存在')
    const changed = t.api.save({ ...first, name: '改名', lendable: false })
    expect(t.api.save({ ...first })).toMatchObject({ name: first.name, lendable: first.lendable, version: 3 })
    t.api.remove({ ...first }); expect(() => t.api.detail(first.id)).toThrow('不存在')
  })
  it('provides ledger options, propagates renames and blocks deletion while referenced', () => {
    const t = setup(), type = t.api.save({ name: '测试类型', lendable: true, notes: '' })
    const draft = emptyEquipment(); draft.profile.equipmentType = type.name
    const device = t.forms.save({ ...draft, code: 'TYPE-TEST', name: '设备', departmentId: 'lab' })
    expect(t.forms.options().equipmentTypes).toContain(type.name)
    expect(t.api.detail(type.id).usedCount).toBe(1)
    expect(() => t.api.remove({ ...type })).toThrow('台账引用')
    const renamed = t.api.save({ ...type, name: '更新类型' })
    expect(t.forms.detail(device.id).profile.equipmentType).toBe('更新类型')
    expect(t.forms.detail(device.id).version).toBe(device.version + 1)
    expect(t.forms.options().equipmentTypes).not.toContain(type.name)
    const before = t.forms.detail(device.id)
    const disabled = t.api.save({ ...renamed, lendable: false })
    expect(t.forms.detail(device.id)).toEqual(before)
    expect(t.loans.query('available', { code: 'TYPE-TEST' }).total).toBe(1)
    const deviceInput = { ...before, profile: { ...before.profile, equipmentType: '' } }
    t.forms.save(deviceInput, device.id)
    t.api.remove({ ...disabled })
    expect(t.forms.options().equipmentTypes).not.toContain('更新类型')
  })
  it('filters, paginates and exports booleans as readable values', () => {
    const { api } = setup()
    for (let index = 0; index < 12; index++) api.save({ name: `TEST-${index}`, lendable: index % 2 === 0, notes: '完整备注' })
    expect(api.query({ name: 'test-' }).items).toHaveLength(10)
    expect(api.query({ name: 'test-', page: 2 }).items).toHaveLength(2)
    const row = api.query({ name: 'TEST-1' }).items[0]!
    const csv = api.export({ ids: [row.id] })
    expect(csv).toContain('是否可借出'); expect(csv).toContain('否'); expect(csv).toContain('完整备注'); expect(csv).not.toContain('TEST-0')
    for (const query of [{ page: -1 }, { pageSize: 9 }, { name: 12 }, { ids: [row.id, row.id] }]) expect(() => api.query(query)).toThrow()
  })
  it('keeps shared dictionary readable and enforces write permissions', () => {
    const t = setup(), row = t.api.query({}).items[0]!
    for (const roles of [['reviewer', 'quality'], ['approver', 'quality'], ['equipment']]) {
      t.actor({ roles, scope: 'department', departmentId: 'lab2' })
      expect(t.api.query({}).total).toBe(3)
      expect(() => t.api.save({ ...row })).toThrow('无权')
      expect(() => t.api.remove({ ...row })).toThrow('无权')
    }
    t.actor({ roles: ['quality'] }); expect(t.api.save({ name: '共享类型', lendable: false, notes: '' }).name).toBe('共享类型')
    t.actor({ roles: ['sampling'] }); expect(() => t.api.query({})).toThrow('无权')
  })
})
