import { describe, it, expect } from 'vitest'
import { createEquipmentInterimPlans } from '../../server/equipmentInterimPlan'
import { createEquipmentForms } from '../../server/equipmentForm'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
function setup() {
  let user: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
  let state: RegistrationState = { commissions: [], samples: [] }
  const deps = { actor: () => user, read: () => state, write: (next: RegistrationState) => { state = next } }
  const forms = createEquipmentForms(deps), plans = createEquipmentInterimPlans(deps)
  const devices = ['lab', 'lab2'].map((departmentId, i) => forms.save({ ...emptyEquipment(), code: `INTERIM-${i}`, name: `设备${i}`, departmentId, accuracy: String(i + 1) }))
  const draft = { equipmentId: devices[0]!.id, year: 2026, testDate: '2026-10-07', checkDate: '2026-11-07', points: '测试点', method: '标准物质', departmentId: 'lab', notes: '' }
  return { plans, forms, devices, draft, state: () => state, actor: (next: Partial<Actor>) => { user = { ...user, ...next } } }
}
describe('equipment interim plans', () => {
  it('queries equipment choices with shared matching, profile validity and department scope', () => {
    const t = setup(), original = t.devices[0]!
    t.forms.save({ ...original, manufacturer: '设备生产厂', cycle: '12个月', notes: '选型备注', profile: { ...original.profile, validity: '2027-10-07' } }, original.id)
    const result = t.plans.equipmentChoices({ field: 'code', operator: 'eq', value: original.code })
    expect(result).toMatchObject({ total: 1, page: 1, pageSize: 10 })
    expect(result.items[0]).toMatchObject({ id: original.id, manufacturer: '设备生产厂', cycle: '12个月', validity: '2027-10-07', notes: '选型备注' })
    expect(t.plans.equipmentChoices({ field: 'accuracy', operator: 'gte', value: '2' }).items.map(item => item.id)).toEqual([t.devices[1]!.id])
    expect(t.plans.equipmentChoices({ value: 'missing' }).total).toBe(0)
    for (const input of [{ field: 'unexpected' }, { operator: 'unexpected' }, { pageSize: 999 }]) expect(() => t.plans.equipmentChoices(input)).toThrow()
    t.actor({ scope: 'department' })
    expect(t.plans.equipmentChoices({}).items.map(item => item.id)).toEqual([original.id])
    expect(t.plans.equipmentChoices({ value: t.devices[1]!.code }).total).toBe(0)
    t.actor({ roles: ['registrar'] })
    expect(() => t.plans.equipmentChoices({})).toThrow('无权')
  })
  it('creates independent plans, preserves device fields and filters/pages/exports plans', () => {
    const t = setup(), devices = structuredClone(t.state().equipmentLedger)
    expect(t.plans.query({}).total).toBe(0)
    const first = t.plans.save({ ...t.draft, code: 'FAKE' })
    expect(first).toMatchObject({ code: 'INTERIM-0', version: 1, year: 2026 })
    for (let i = 0; i < 10; i++) t.plans.save({ ...t.draft, year: 2027 })
    t.plans.save({ ...t.draft, equipmentId: t.devices[1]!.id, departmentId: 'lab2' })
    expect(t.plans.query({}).total).toBe(12)
    expect(t.plans.query({ page: 2 }).items).toHaveLength(2)
    expect(t.plans.query({ field: 'accuracy', operator: 'gte', value: '2' }).total).toBe(1)
    expect(t.plans.query({ value: 'INTERIM-0' }).total).toBe(11)
    expect(t.plans.query({ ids: [first.id] }, true).items).toHaveLength(1)
    const csv = t.plans.export({ ids: [first.id] })
    expect(csv).toContain('实施部门'); expect(csv).toContain('INTERIM-0'); expect(csv).not.toContain('INTERIM-1')
    expect(t.state().equipmentLedger).toEqual(devices)
  })
  it('validates dates, year and departments without partial writes', () => {
    const t = setup()
    for (const patch of [{ testDate: '2026-02-30' }, { checkDate: 'bad' }, { year: 2026.1 }, { year: 0 }, { departmentId: 'missing' }, { notes: 'x'.repeat(1001) }]) expect(() => t.plans.save({ ...t.draft, ...patch })).toThrow()
    expect(() => t.plans.save({ ...t.draft, equipmentId: 'missing' })).toThrow('设备不存在')
    expect(t.plans.query({}).total).toBe(0)
    expect(() => t.plans.query({ pageSize: 100 })).toThrow('分页')
    expect(() => t.plans.query({ ids: [123] })).toThrow('所选计划')
    expect(t.plans.save({ ...t.draft, testDate: '', checkDate: '' }).testDate).toBe('')
  })
  it('checks versions on edit/delete and keeps referenced devices until the plan is removed', () => {
    const t = setup(), first = t.plans.save(t.draft)
    const updated = t.plans.save({ ...first, notes: ' updated ' })
    expect(updated).toMatchObject({ version: 2, notes: 'updated' })
    expect(t.plans.save({ ...first, notes: '后提交覆盖' })).toMatchObject({ notes: '后提交覆盖', version: 3 })
    expect(() => t.forms.remove(t.devices[0]!.id, { version: t.devices[0]!.version })).toThrow('期间核查计划引用')
    t.plans.remove({ ...first })
    expect(t.plans.query({}).total).toBe(0)
    expect(t.forms.detail(t.devices[0]!.id).code).toBe('INTERIM-0')
    t.forms.remove(t.devices[0]!.id, { version: t.devices[0]!.version })
    expect(() => t.plans.detail(first.id)).toThrow('不存在')
  })
  it('enforces device scope and read-only roles', () => {
    const t = setup(), own = t.plans.save(t.draft), other = t.plans.save({ ...t.draft, equipmentId: t.devices[1]!.id, departmentId: 'lab2' })
    t.actor({ scope: 'department' })
    expect(t.plans.query({}).total).toBe(1)
    expect(() => t.plans.detail(other.id)).toThrow('无权')
    expect(() => t.plans.save({ ...t.draft, departmentId: 'lab2' })).toThrow('实施部门')
    expect(() => t.plans.save({ ...t.draft, equipmentId: other.equipmentId })).toThrow('无权')
    expect(t.plans.query({ ids: [other.id] }, true).items).toHaveLength(0)
    t.actor({ roles: ['reviewer'] })
    expect(t.plans.detail(own.id).id).toBe(own.id)
    expect(() => t.plans.save({ ...own })).toThrow('无权')
    expect(() => t.plans.remove({ ...own })).toThrow('无权')
  })
})
