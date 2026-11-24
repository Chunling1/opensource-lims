import { describe, it, expect } from 'vitest'
import { createEquipmentOverallPlans } from '../../server/equipmentOverallPlan'
import { createEquipmentForms } from '../../server/equipmentForm'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
function setup() {
  let user: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
  let state: RegistrationState = { commissions: [], samples: [] }
  const deps = { actor: () => user, read: () => state, write: (next: RegistrationState) => { state = next } }
  const forms = createEquipmentForms(deps), plans = createEquipmentOverallPlans(deps)
  const devices = Array.from({ length: 12 }, (_, i) => forms.save({ ...emptyEquipment(), code: `PLAN-${i + 1}`, name: `测试设备${i + 1}`, accuracy: String(i + 1), model: 'MODEL', departmentId: i === 11 ? 'lab2' : 'lab' }))
  return { plans, forms, devices, state: () => state, actor: (next: Partial<Actor>) => { user = { ...user, ...next } } }
}
describe('equipment overall plans', () => {
  it('derives one plan per ledger device and applies query operators and pagination', () => {
    const t = setup()
    expect(t.plans.query({}).total).toBe(12)
    expect(t.plans.query({ page: 2 }).items).toHaveLength(2)
    expect(t.plans.query({ field: 'name', value: '测试设备1' }).total).toBe(4)
    for (const [operator, total] of [['gt', 10], ['gte', 11], ['eq', 1], ['lt', 1], ['lte', 2]] as const) expect(t.plans.query({ field: 'accuracy', operator, value: '2.0' }).total).toBe(total)
    expect(t.plans.query({ field: 'code', operator: 'gt', value: 'PLAN-9' }).total).toBe(3)
    t.forms.save({ ...t.forms.detail(t.devices[0]!.id), accuracy: '以检定证书为准' }, t.devices[0]!.id)
    expect(t.plans.query({ field: 'accuracy', operator: 'gte', value: '3' }).total).toBe(10)
    expect(() => t.plans.query({ field: 'unknown' })).toThrow('查询')
    expect(() => t.plans.query({ operator: 'unknown' })).toThrow('查询')
    expect(() => t.plans.query({ pageSize: 99 })).toThrow('分页')
  })
  it('preserves unchecked fields and device data when editing or clearing a batch field', () => {
    const t = setup(), rows = t.devices.slice(0, 2).map(device => t.plans.detail(device.id)), devices = structuredClone(t.state().equipmentLedger)
    t.plans.save({ records: [rows[0]], changes: { traceMethod: '检定', maintenanceItems: '清洁', checkRequired: '是', traceCycle: '12个月' } })
    t.plans.save({ records: rows.map(row => t.plans.detail(row.id)), changes: { checkInterval: ' 6个月 ', maintenanceItems: '' } })
    const result = rows.map(row => t.plans.detail(row.id))
    expect(result[0]).toMatchObject({ traceMethod: '检定', traceCycle: '12个月', checkRequired: '是', checkInterval: '6个月', maintenanceItems: '', version: 2 })
    expect(result[1]).toMatchObject({ traceMethod: '', checkRequired: '', checkInterval: '6个月', version: 1 })
    expect(t.state().equipmentLedger).toEqual(devices)
    expect(() => t.plans.save({ records: [result[0]], changes: { code: 'ILLEGAL' } })).toThrow('字段')
    expect(() => t.plans.save({ records: [result[0]], changes: { checkRequired: '未知' } })).toThrow('字段')
  })
  it('rejects conflicting and inaccessible batch records without partial writes', () => {
    const t = setup(), rows = t.devices.slice(0, 2).map(device => t.plans.detail(device.id))
    t.plans.save({ records: [rows[1]], changes: { traceMethod: '校准' } })
    t.plans.save({ records: rows, changes: { traceMethod: '检定' } })
    expect(rows.map(row => t.plans.detail(row.id).traceMethod)).toEqual(['检定', '检定'])
    const fresh = t.plans.detail(rows[0]!.id)
    t.forms.save({ ...t.forms.detail(fresh.id), name: '设备已变更' }, fresh.id)
    expect(() => t.plans.save({ records: [fresh], changes: { traceMethod: '检定' } })).not.toThrow()
    t.actor({ scope: 'department' })
    expect(t.plans.query({}).total).toBe(11)
    expect(() => t.plans.detail(t.devices[11]!.id)).toThrow('无权')
    expect(() => t.plans.save({ records: [rows[0], { ...rows[0], id: t.devices[11]!.id }], changes: { traceMethod: '检定' } })).toThrow()
    t.actor({ roles: ['reviewer'] })
    expect(t.plans.query({}).total).toBe(11)
    expect(() => t.plans.save({ records: [t.plans.detail(rows[0]!.id)], changes: { traceMethod: '检定' } })).toThrow('无权')
  })
  it('exports and prints the filtered scope and removes stored plans with a deleted device', () => {
    const t = setup(), row = t.plans.detail(t.devices[0]!.id)
    t.plans.save({ records: [row], changes: { controlMeasures: '检查后使用' } })
    const csv = t.plans.export({ ids: [row.id] })
    expect(csv).toContain('检查后使用'); expect(csv).toContain('量值溯源周期'); expect(csv).not.toContain('"PLAN-2"')
    expect(t.plans.query({ ids: [row.id] }, true).items).toHaveLength(1)
    t.actor({ scope: 'department' })
    expect(t.plans.export({ ids: [t.devices[11]!.id] })).not.toContain('PLAN-12')
    t.forms.remove(row.id, { version: row.equipmentVersion })
    expect(t.state().equipmentOverallPlans?.[row.id]).toBeUndefined()
    expect(t.plans.query({}).total).toBe(10)
  })
})
