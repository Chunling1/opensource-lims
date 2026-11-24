import { describe, expect, it } from 'vitest'
import { createConsumables, seedConsumables } from '../../server/consumables'
import { registrationCsv } from '../../server/registrationDomain'
import { consumableColumns, consumableTotal } from '../../src/types/quality/consumables'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }, actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
  seedConsumables(state)
  return { api: createConsumables({ actor: () => actor, read: () => state, write: next => { state = next } }), state: () => state, actor: (patch: Partial<Actor>) => { actor = { ...actor, ...patch } } }
}
const draft = { name: '测试耗材', specification: '50 mL', purchasedAt: '2026-10-07', unitPrice: 10.05, quantity: 2, departmentId: 'lab', notes: '备注' }
const csv = (rows: unknown[][]) => registrationCsv([consumableColumns.map(field => field.label), ...rows])
describe('consumables', () => {
  it('calculates totals, validates fields and protects concurrent edits and deletions', () => {
    const t = setup(), row = t.api.save({ ...draft, totalAmount: 999 })
    expect(row.totalAmount).toBe(20.1)
    expect(consumableTotal(0.29, 100)).toBe(29); expect(consumableTotal(1.01, 0.5)).toBe(0.51)
    expect(consumableTotal(1000000, 1000000)).toBe(1000000000000)
    for (const patch of [{ name: ' ' }, { purchasedAt: '2026-02-30' }, { purchasedAt: '' }, { unitPrice: -1 }, { unitPrice: 0.001 }, { quantity: 1.0001 }, { quantity: Infinity }, { departmentId: 'missing' }, { notes: 'x'.repeat(2001) }]) expect(() => t.api.save({ ...draft, ...patch })).toThrow()
    const updated = t.api.save({ ...row, quantity: 3 }); expect(updated.totalAmount).toBe(30.15)
    expect(t.api.save({ ...row })).toMatchObject({ quantity: row.quantity, version: updated.version + 1 })
    t.api.remove({ ...row }); expect(() => t.api.detail(row.id)).toThrow('不存在')
    expect(t.api.save({ ...draft, unitPrice: null }).totalAmount).toBeNull()
  })
  it('filters exact quantities, paginates and exports all business columns', () => {
    const { api } = setup()
    for (let i = 0; i < 12; i++) api.save({ ...draft, name: `TEST-${i}` })
    expect(api.query({ name: 'TEST-', quantity: '2.000', department: '实验' }).total).toBe(12)
    expect(api.query({ name: 'TEST-', page: 2 }).items).toHaveLength(2)
    expect(api.query({ name: 'TEST-', quantity: '20' }).total).toBe(0)
    for (const bad of [{ quantity: 'xx' }, { quantity: '-2' }, { pageSize: 7 }, { page: 0 }, { ids: [1] }]) expect(() => api.query(bad)).toThrow()
    const row = api.query({ name: 'TEST-0' }).items[0]!, exported = api.export({ ids: [row.id] })
    expect(exported).toContain('备注'); expect(exported).toContain('10.05'); expect(exported).toContain('20.10'); expect(exported).not.toContain('TEST-1')
  })
  it('imports atomically with row errors, total checks and CSV quoting', () => {
    const t = setup(), values = ['导入,"耗材"', '型号', '2026-10-07', '2.5', '3', '', '实验室', '第一行\n第二行']
    expect(t.api.importCsv(csv([values]))).toEqual({ count: 1 })
    const row = t.api.query({ name: '导入' }).items[0]!
    expect(row.totalAmount).toBe(7.5); expect(row.notes).toBe('第一行\n第二行')
    const before = structuredClone(t.state())
    expect(() => t.api.importCsv(csv([values, [...values.slice(0, 2), '错误日期', ...values.slice(3)]]))).toThrow('第 3 行')
    expect(() => t.api.importCsv(csv([[...values.slice(0, 5), '100', ...values.slice(6)]]))).toThrow('总金额')
    expect(t.state()).toEqual(before)
    expect(() => t.api.importCsv('错误表头\n123')).toThrow('模板')
    expect(() => t.api.importCsv(t.api.template())).toThrow('1 至 1000')
    expect(t.api.importCsv(t.api.export({ ids: [row.id] })).count).toBe(1)
  })
  it('enforces roles and department scope across reads, writes, exports and imports', () => {
    const t = setup(), other = t.api.save({ ...draft, departmentId: 'lab2' })
    t.actor({ roles: ['inventory'], scope: 'department' })
    expect(t.api.query({}).items.every(row => row.departmentId === 'lab')).toBe(true)
    expect(() => t.api.detail(other.id)).toThrow('无权'); expect(() => t.api.remove({ ...other })).toThrow('无权')
    expect(() => t.api.save({ ...draft, departmentId: 'lab2' })).toThrow('权限范围')
    expect(t.api.export({ ids: [other.id] })).not.toContain(other.name)
    expect(() => t.api.importCsv(csv([['跨部门', '', '2026-10-07', '1', '2', '', '第二实验室', '']]))).toThrow('权限范围')
    for (const roles of [['reviewer', 'quality'], ['approver', 'quality']]) {
      t.actor({ roles }); expect(t.api.query({}).total).toBeGreaterThan(0)
      expect(() => t.api.save(draft)).toThrow('无权'); expect(() => t.api.importCsv(csv([]))).toThrow('无权')
    }
    t.actor({ roles: ['testing'] }); expect(() => t.api.query({})).toThrow('无权')
  })
})
