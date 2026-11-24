import { describe, it, expect } from 'vitest'
import { createEquipmentLedger, seedEquipmentLedger } from '../../server/equipmentLedger'
import { equipmentDateFields, equipmentLedgerColumns } from '../../src/types/quality/equipmentLedger'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'

function setup() {
  const state: RegistrationState = { commissions: [], samples: [], equipmentLedger: seedEquipmentLedger(new Date('2026-10-06')) }
  const actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], scope: 'all', departmentId: 'lab' }
  return { state, actor, api: createEquipmentLedger({ actor: () => actor, read: () => state }) }
}
describe('equipment ledger', () => {
  it('paginates, filters and exports the same scoped results', () => {
    const { api } = setup()
    expect(api.query({})).toMatchObject({ total: 24, page: 1, pageSize: 10 })
    expect(api.query({ page: 3 }).items).toHaveLength(4)
    expect(api.query({ page: 99 }).page).toBe(3)
    expect(api.query({ code: 'demo-001', name: '多参数', manufacturer: '演示', serial: 'equipment-1' }).total).toBe(1)
    expect(api.query({ status: '停用', pageSize: 50 }).items.every(r => r.status === '停用')).toBe(true)
    expect(api.query({ sort: 'code', direction: 'desc' }).items[0]!.code).toBe('DEMO-024')
    const csv = api.export({ ids: ['equipment-1'], code: 'DEMO-001' })
    expect(equipmentLedgerColumns).toHaveLength(23)
    expect(csv).toContain('购入价格'); expect(csv).toContain('DEMO-001'); expect(csv).not.toContain('DEMO-002')
    expect(api.export({ ids: ['equipment-1'], code: 'DEMO-002' }).trim().split('\n')).toHaveLength(1)
  })
  it('uses the selected date field, inclusive endpoints and validated ranges', () => {
    const { api, state } = setup()
    for (const { key } of equipmentDateFields) {
      const value = state.equipmentLedger![0]![key]
      const result = api.query({ dateField: key, from: value, to: value, pageSize: 50 })
      expect(result.total).toBeGreaterThan(0)
      expect(result.items.every(r => r[key] === value)).toBe(true)
    }
    for (const input of [{ dateField: 'bad' }, { from: '2026-02-30' }, { from: '2026-10-02', to: '2026-10-01' }, { pageSize: '10' }, { status: 'bad' }, { unassociated: 'true' }]) expect(() => api.query(input)).toThrow()
  })
  it('ignores dates in unlimited mode, including missing dates and export', () => {
    const { api, state } = setup()
    state.equipmentLedger![0]!.lastTestDate = ''
    state.equipmentLedger![1]!.lastTestDate = '2000-01-01'
    const limits = { from: '2025-01-01', to: '2027-12-31' }
    expect(api.query({}).total).toBe(24)
    expect(api.query({ dateField: 'lastTestDate', ...limits }).total).toBe(22)
    expect(api.query({ dateField: '', ...limits }).total).toBe(24)
    expect(api.export({ dateField: '', ...limits })).toContain('DEMO-001')
    expect(api.export({ dateField: 'lastTestDate', ...limits })).not.toContain('DEMO-001')
  })
  it('filters equipment without a department independently of detection plans, including exports', () => {
    const { api, state, actor } = setup()
    state.equipmentPlans = { 'lab:plan-a': { version: 1, associatedIds: ['equipment-1', 'ledger-equipment-22'], defaultIds: [] } }
    const result = api.query({ unassociated: true, pageSize: 50 })
    expect(result.total).toBe(3)
    expect(result.items.map(r => r.code)).toEqual(['DEMO-022', 'DEMO-023', 'DEMO-024'])
    expect(result.items.every(r => !r.departmentId && !r.department)).toBe(true)
    expect(api.query({ unassociated: true, code: 'DEMO-001' }).total).toBe(0)
    expect(api.query({ unassociated: true, code: 'DEMO-002' }).total).toBe(0)
    expect(api.query({ unassociated: true, departmentId: 'lab' }).total).toBe(0)
    expect(api.query({ unassociated: true, ownDepartment: true }).total).toBe(0)
    const csv = api.export({ unassociated: true })
    expect(csv).toContain('DEMO-022'); expect(csv).not.toContain('DEMO-001')
    expect(api.query({ ownDepartment: true, pageSize: 50 }).items.every(r => r.departmentId === 'lab')).toBe(true)
    actor.scope = 'department'; actor.roles = ['quality']
    expect(api.query({ unassociated: true }).total).toBe(0)
    expect(api.query({ departmentId: 'lab2' }).total).toBe(0)
    expect(api.query({}).departments).toHaveLength(1)
    expect(api.export({ ids: ['equipment-3'] })).not.toContain('DEMO-003')
    actor.roles = ['registrar']
    expect(() => api.query({})).toThrow('无权')
  })
})
