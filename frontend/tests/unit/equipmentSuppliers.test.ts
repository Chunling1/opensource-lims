import { describe, expect, it } from 'vitest'
import { createEquipmentSuppliers, seedEquipmentSuppliers } from '../../server/equipmentSuppliers'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }, actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
  seedEquipmentSuppliers(state)
  const api = createEquipmentSuppliers({ read: () => state, write: next => { state = next }, actor: () => actor })
  return { api, state: () => state, actor: (patch: Partial<Actor>) => { actor = { ...actor, ...patch } } }
}
describe('equipment suppliers and evaluations', () => {
  it('supports independent filters, pagination, association and full or selected exports', () => {
    const { api } = setup()
    expect(api.query('suppliers', {}).items).toHaveLength(5)
    expect(api.query('suppliers', { page: 2 }).items).toHaveLength(2)
    expect(api.query('suppliers', { field: 'address', value: '产业园' }).total).toBe(7)
    expect(api.query('evaluations', { field: 'services', value: '仪器销售' }).total).toBe(3)
    expect(api.query('evaluations', { supplierIds: ['equipment-supplier-1'] }).total).toBe(2)
    expect(api.query('evaluations', { supplierIds: [] }).total).toBe(0)
    const csv = api.export('suppliers', { ids: ['equipment-supplier-7'] })
    expect(csv).toContain('邮编'); expect(csv).toContain('GYS-007'); expect(csv).not.toContain('GYS-001')
    expect(api.export('evaluations', { supplierIds: ['equipment-supplier-1'] })).toContain('持续跟踪服务质量')
    for (const input of [{ field: 'departmentId' }, { page: -1 }, { pageSize: 9 }, { ids: ['x', 'x'] }]) expect(() => api.query('suppliers', input)).toThrow()
  })
  it('validates, versions and deletes both record types without orphaning evaluations', () => {
    const { api, state } = setup()
    expect(() => api.save('suppliers', { name: ' ' })).toThrow('单位名称')
    const supplier = api.save('suppliers', { name: '测试供应商', code: 'TEST', departmentId: 'lab2' })
    expect(supplier).toMatchObject({ departmentId: 'lab', version: 1, updatedBy: '管理员' })
    expect(() => api.save('suppliers', { name: '重复', code: 'test' })).toThrow('已存在')
    const input = { supplierId: supplier.id, reviewDate: '2026-10-07', quality: '优', conclusion: '合格' }
    for (const patch of [{ supplierId: '' }, { reviewDate: '2026-02-30' }, { quality: 'x'.repeat(501) }]) expect(() => api.save('evaluations', { ...input, ...patch })).toThrow()
    const evaluation = api.save('evaluations', input)
    expect(() => api.remove('suppliers', { ...supplier })).toThrow('存在评价记录')
    const edited = api.save('evaluations', { ...evaluation, conclusion: '需改进' })
    expect(edited.version).toBe(2)
    expect(api.save('evaluations', { ...evaluation })).toMatchObject({ conclusion: '合格', version: 3 })
    api.remove('evaluations', { ...evaluation })
    const renamed = api.save('suppliers', { ...supplier, name: '新名称' })
    api.remove('suppliers', { ...supplier })
    expect(() => api.detail('suppliers', supplier.id)).toThrow('不存在')
  })
  it('enforces department scope and read-only roles for all entry points', () => {
    const t = setup(), other = 'equipment-supplier-7'
    t.actor({ scope: 'department', roles: ['quality'] })
    expect(t.api.query('suppliers', {}).total).toBe(6)
    expect(t.api.options()).toHaveLength(6)
    expect(() => t.api.detail('suppliers', other)).toThrow('无权访问')
    expect(() => t.api.query('evaluations', { supplierIds: [other] })).toThrow('无权访问')
    expect(() => t.api.save('evaluations', { supplierId: other, reviewDate: '2026-10-07' })).toThrow('无权访问')
    expect(t.api.export('suppliers', { ids: [other] })).not.toContain('GYS-007')
    t.actor({ roles: ['quality', 'reviewer'] })
    expect(t.api.query('evaluations', {}).total).toBe(5)
    expect(() => t.api.save('suppliers', { name: '禁止' })).toThrow('无权')
    expect(() => t.api.remove('evaluations', { id: 'equipment-evaluation-0-0', version: 1 })).toThrow('无权')
    t.actor({ roles: ['sampler'] })
    expect(() => t.api.options()).toThrow('无权')
  })
})
