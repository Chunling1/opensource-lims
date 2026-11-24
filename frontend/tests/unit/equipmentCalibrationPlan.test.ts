import { describe, expect, it } from 'vitest'
import { createEquipmentCalibrationPlans, seedEquipmentCalibrationPlans } from '../../server/equipmentCalibrationPlan'
import { seedEquipmentLedger } from '../../server/equipmentLedger'
import { createEquipmentForms } from '../../server/equipmentForm'
import { createMonthlyCalibration } from '../../server/monthlyCalibration'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import { calibrationPlanFields, type CalibrationPlanRow, type CalibrationPlanValues } from '../../src/types/quality/equipmentCalibrationPlan'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }
  let user: Actor = { id: 'admin', name: '管理员', roles: ['admin'], scope: 'all', departmentId: 'lab' }
  const deps = { read: () => state, write: (value: RegistrationState) => { state = value }, actor: () => user }
  const forms = createEquipmentForms(deps), plans = createEquipmentCalibrationPlans(deps), monthly = createMonthlyCalibration(deps)
  const devices = ['lab', 'lab2'].map((departmentId, i) => forms.save({ ...emptyEquipment(), code: `CYCLE-${i}`, name: `设备${i}`, departmentId, plannedTestDate: '2026-10-07' }))
  return { forms, plans, monthly, devices, state: () => state, actor: (patch: Partial<Actor>) => { user = { ...user, ...patch } } }
}
const payload = (row: CalibrationPlanRow) => ({ id: row.id, version: row.version, equipmentVersion: row.equipmentVersion, values: Object.fromEntries(calibrationPlanFields.map(field => [field.key, row[field.key]])) as CalibrationPlanValues })
describe('independent equipment calibration plans', () => {
  it('seeds one row per device without creating ledger results or overwriting edits', () => {
    const t = setup(), now = new Date('2026-10-07T00:00:00Z')
    t.state().equipmentLedger = seedEquipmentLedger(now)
    const ledger = structuredClone(t.state().equipmentLedger), profiles = structuredClone(t.state().equipmentProfiles)
    seedEquipmentCalibrationPlans(t.state(), now)
    const rows = t.plans.query({ from: '2026-01-01', to: '2026-12-31', pageSize: 50 })
    expect(rows.total).toBe(24)
    expect(rows.items.some(row => row.submitted)).toBe(true)
    expect(rows.items.some(row => !row.submitted)).toBe(true)
    expect(t.state().equipmentLedger).toEqual(ledger)
    expect(t.state().equipmentProfiles).toEqual(profiles)
    const row = rows.items[0]!
    t.plans.save({ ...payload(row), values: { ...payload(row).values, notes: '用户输入' } })
    seedEquipmentCalibrationPlans(t.state(), now)
    expect(t.plans.detail(row.id).notes).toBe('用户输入')
  })
  it('saves, submits and resubmits the same device row while retaining snapshots', () => {
    const t = setup(), row = t.plans.detail(t.devices[0]!.id)
    const ledger = structuredClone(t.state().equipmentLedger), profiles = structuredClone(t.state().equipmentProfiles)
    const saved = t.plans.save({ ...payload(row), values: { ...payload(row).values, model: '计划型号', testDate: '2026-11-07', organization: '计量院', fee: 12.34 } })
    expect(saved).toMatchObject({ version: 1, submitted: false, model: '计划型号' })
    const submitted = t.plans.save(payload(saved), true)
    expect(submitted.submitted).toBe(true)
    const revised = t.plans.save({ ...payload(submitted), values: { ...payload(submitted).values, notes: '继续修改' } })
    expect(revised.submitted).toBe(false)
    const resubmitted = t.plans.save(payload(revised), true)
    expect(resubmitted.id).toBe(row.id)
    expect(resubmitted.submitted).toBe(true)
    expect(t.plans.query({}).total).toBe(2)
    expect(t.state().equipmentCalibrationPlans![row.id]!.submissions).toHaveLength(2)
    expect(t.state().equipmentCalibrationPlans![row.id]!.submissions[0]!.values.notes).toBe('')
    expect(t.state().equipmentLedger).toEqual(ledger)
    expect(t.state().equipmentProfiles).toEqual(profiles)
    expect(t.monthly.query({ year: 2026, month: 10 }).total).toBe(2)
    expect(t.monthly.query({ year: 2026, month: 11 }).total).toBe(0)
    expect(t.plans.query({ from: '2026-11-01', to: '2026-11-30' }).total).toBe(1)
  })
  it('keeps manual ledger records and date changes independent from saved plans', () => {
    const t = setup(), row = t.plans.detail(t.devices[0]!.id)
    t.plans.save({ ...payload(row), values: { ...payload(row).values, organization: '计量院' } }, true)
    const plan = t.plans.detail(row.id), device = t.forms.detail(row.id)
    device.plannedTestDate = '2026-12-01'
    device.profile.calibrations.push({ id: 'manual', date: '2026-10-01', organization: '其他单位', conclusion: '合格' })
    const saved = t.forms.save(device, device.id)
    expect(t.plans.detail(row.id)).toMatchObject({ version: plan.version, testDate: plan.testDate, organization: '计量院', submitted: true })
    saved.profile.calibrations = []
    t.forms.save(saved, saved.id)
    expect(t.plans.detail(row.id).submitted).toBe(true)
    expect(t.monthly.query({ year: 2026, month: 12 }).total).toBe(1)
  })
  it('validates dates, amounts, submission fields, scope and both versions atomically', () => {
    const t = setup(), row = t.plans.detail(t.devices[0]!.id), input = payload(row), before = structuredClone(t.state())
    for (const values of [{ fee: -1 }, { fee: 1.001 }, { testDate: '2026-02-30' }, { testDate: '2026-10-01', validDate: '2026-01-01' }, { notes: 'x'.repeat(1001) }]) expect(() => t.plans.save({ ...input, values: { ...input.values, ...values } })).toThrow()
    expect(() => t.plans.save(input, true)).toThrow('完善')
    expect(t.state()).toEqual(before)
    t.plans.save(input)
    expect(() => t.plans.save(input)).not.toThrow()
    const fresh = payload(t.plans.detail(row.id))
    t.forms.save({ ...t.forms.detail(row.id), notes: '更新台账' }, row.id)
    expect(() => t.plans.save(fresh)).not.toThrow()
    t.actor({ scope: 'department' })
    expect(t.plans.query({}).total).toBe(1)
    expect(() => t.plans.detail(t.devices[1]!.id)).toThrow('无权')
    t.actor({ roles: ['reviewer'] })
    expect(() => t.plans.save(payload(t.plans.detail(row.id)))).toThrow('无权')
  })
  it('exports all matches or selected rows using the displayed test date and scope', () => {
    const t = setup()
    for (let i = 2; i < 12; i++) t.forms.save({ ...emptyEquipment(), code: `CYCLE-${i}`, name: '设备', departmentId: 'lab' })
    expect(t.plans.query({}).items).toHaveLength(10)
    expect(t.plans.export({})).toContain('CYCLE-11')
    expect(t.plans.export({ ids: [t.devices[0]!.id] })).not.toContain('CYCLE-1')
    expect(t.plans.export({ from: '2027-01-01' }).trim().split('\n')).toHaveLength(1)
    t.actor({ scope: 'department' })
    expect(t.plans.export({ ids: [t.devices[1]!.id] }).trim().split('\n')).toHaveLength(1)
    for (const query of [{ ids: [123] }, { field: 'invalid' }, { operator: 'invalid' }, { pageSize: 100 }, { from: 'bad' }]) expect(() => t.plans.query(query)).toThrow()
  })
})
