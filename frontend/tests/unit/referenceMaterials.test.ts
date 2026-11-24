import { describe, expect, it } from 'vitest'
import { createReferenceMaterials, seedReferenceMaterials } from '../../server/referenceMaterials'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
import { emptyAcceptance, emptyMaterial, type MaterialRecord, type AcceptanceRecord } from '../../src/types/quality/referenceMaterials'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }, actor: Actor = { id: 'admin', name: '管理员', departmentId: 'lab', roles: ['admin'], scope: 'all' }
  seedReferenceMaterials(state)
  const api = createReferenceMaterials({ read: () => state, write: next => { state = next }, actor: () => actor })
  return { api, state: () => state, actor: (patch: Partial<Actor>) => { actor = { ...actor, ...patch } } }
}
const inputFor = (row: MaterialRecord) => ({ ...emptyAcceptance(), materialId: row.id, materialVersion: row.version, useDepartmentId: 'lab', status: '不合格', acceptedAt: '2026-10-07', acceptorId: 'admin', keeperId: 'inventory' })
describe('reference materials', () => {
  it('accepts once, preserves result and versions, and restores registration when acceptance is deleted', () => {
    const t = setup(), material = t.api.detail('materials', 'reference-material-1') as MaterialRecord, input = inputFor(material)
    const accepted = t.api.save('acceptances', input) as AcceptanceRecord
    expect(accepted).toMatchObject({ status: '不合格', name: material.name, acceptor: '演示用户', keeper: '吴物资', departmentId: 'lab' })
    expect(t.api.detail('materials', material.id)).toMatchObject({ accepted: true, acceptanceStatus: '已验收', version: material.version + 1 })
    const before = structuredClone(t.state())
    expect(() => t.api.save('acceptances', input)).toThrow('已验收')
    expect(() => t.api.remove('materials', { ...material, version: material.version + 1 })).toThrow('存在验收记录')
    expect(t.state()).toEqual(before)
    const edited = t.api.save('acceptances', { ...accepted, status: '合格' }) as AcceptanceRecord
    t.api.remove('acceptances', { ...accepted })
    const restored = t.api.detail('materials', material.id) as MaterialRecord
    expect(restored).toMatchObject({ accepted: false, version: material.version + 3 })
    t.api.save('acceptances', input)
    expect(t.api.query('acceptances', { materialIds: [material.id] }).total).toBe(1)
  })
  it('validates both forms before mutation, freezes the parent relation and allows parent version changes', () => {
    const t = setup(), row = t.api.save('materials', { ...emptyMaterial(), name: '测试', purchasedQuantity: 10 }) as MaterialRecord
    const before = structuredClone(t.state())
    for (const patch of [{ name: ' ' }, { purchasedAt: '2026-02-30' }, { purchasedQuantity: -1 }, { receivedQuantity: 11 }, { purchasedAt: '2026-10-07', receivedAt: '2026-10-01' }]) expect(() => t.api.save('materials', { ...row, ...patch })).toThrow()
    for (const patch of [{ status: '未验收' }, { acceptedAt: '' }, { acceptorId: '' }, { keeperId: 'missing' }, { useDepartmentId: 'missing' }]) expect(() => t.api.save('acceptances', { ...inputFor(row), ...patch })).toThrow()
    expect(t.state()).toEqual(before)
    const accepted = t.api.save('acceptances', inputFor(row)) as AcceptanceRecord
    expect(() => t.api.save('acceptances', { ...accepted, materialId: 'reference-material-1' })).toThrow('不能更换')
    const parent = t.api.detail('materials', row.id) as MaterialRecord
    t.api.save('materials', { ...parent, notes: '登记已修改' })
    expect(() => t.api.save('acceptances', { ...accepted })).not.toThrow()
    t.api.remove('acceptances', { ...accepted })
    t.api.remove('materials', { ...t.api.detail('materials', row.id) })
    expect(() => t.api.detail('materials', row.id)).toThrow('不存在')
  })
  it('supports association, filters, pagination and complete CSV exports', () => {
    const { api } = setup()
    expect(api.query('materials', {}).items).toHaveLength(5)
    expect(api.query('materials', { page: 2 }).items).toHaveLength(2)
    expect(api.query('materials', { name: '镉', manufacturer: '研究所' }).total).toBe(1)
    expect(api.query('acceptances', { materialIds: ['reference-material-2'], useDepartment: '实验室' }).total).toBe(1)
    expect(api.query('acceptances', { materialIds: [] }).total).toBe(0)
    const csv = api.export('acceptances', { ids: ['material-acceptance-2'] })
    expect(csv).toContain('供货单位地址'); expect(csv).toContain('不合格'); expect(csv).toContain('吴物资'); expect(csv).not.toContain('镉标准溶液')
    for (const input of [{ page: 0 }, { pageSize: 3 }, { ids: ['x', 'x'] }, { name: 23 }]) expect(() => api.query('materials', input)).toThrow()
  })
  it('enforces role and department scope for records, people and writes', () => {
    const t = setup()
    t.actor({ id: 'inventory', scope: 'department', roles: ['inventory'] })
    expect(t.api.query('materials', {}).total).toBe(6)
    expect(t.api.queryUsers({}).items.every(person => person.departmentId === 'lab')).toBe(true)
    expect(() => t.api.person('other')).toThrow('权限范围')
    expect(() => t.api.detail('materials', 'reference-material-7')).toThrow('无权访问')
    expect(() => t.api.query('acceptances', { materialIds: ['reference-material-7'] })).toThrow('无权访问')
    expect(t.api.export('materials', { ids: ['reference-material-7'] })).not.toContain('分部标准溶液')
    const material = t.api.detail('materials', 'reference-material-1') as MaterialRecord
    expect(() => t.api.save('acceptances', { ...inputFor(material), useDepartmentId: 'lab2' })).toThrow('使用部门')
    expect(() => t.api.save('acceptances', { ...inputFor(material), acceptorId: 'other' })).toThrow('权限范围')
    t.actor({ roles: ['quality', 'reviewer'] })
    expect(t.api.query('acceptances', {}).total).toBe(2)
    expect(() => t.api.save('materials', { name: '禁止' })).toThrow('无权')
    expect(() => t.api.remove('materials', { id: material.id, version: material.version })).toThrow('无权')
  })
})
