import { describe, expect, it } from 'vitest'
import { createMonthlyCalibration } from '../../server/monthlyCalibration'
import { seedEquipmentLedger } from '../../server/equipmentLedger'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'

function setup() {
  let actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
  const dates = ['2024-01-31', '2024-02-01', '2024-02-29', '2024-03-01', '', '2024-12-31', '2025-01-01']
  const state: RegistrationState = { commissions: [], samples: [], equipmentLedger: dates.map((date, i) => ({ ...emptyEquipment(), id: `id-${i}`, code: `MONTH-${i}`, name: `设备${i}`, departmentId: i === 2 ? 'lab2' : 'lab', department: i === 2 ? '第二实验室' : '实验室', plannedTestDate: date, actualTestDate: '2024-02-01', serial: `SN-${i}`, manufacturer: '厂家' })) }
  return { service: createMonthlyCalibration({ actor: () => actor, read: () => state }), actor: (value: Partial<Actor>) => { actor = { ...actor, ...value } } }
}
describe('monthly calibration', () => {
  it.each(['2026-10-07', '2026-01-07', '2026-12-07'])('seeds visible current and adjacent month plans at %s', date => {
    const now = new Date(`${date}T00:00:00Z`)
    const actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
    const state: RegistrationState = { commissions: [], samples: [], equipmentLedger: seedEquipmentLedger(now) }
    const service = createMonthlyCalibration({ actor: () => actor, read: () => state })
    for (const [offset, count] of [[-1, 6], [0, 12], [1, 6]] as const) {
      const month = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + offset, 1))
      const query = { year: month.getUTCFullYear(), month: month.getUTCMonth() + 1 }
      expect(service.query(query).total).toBe(count)
      if (!offset) {
        for (const departmentId of ['lab', 'lab2']) {
          actor.departmentId = departmentId
          const own = service.query({ ...query, ownDepartment: true })
          expect(own.total).toBeGreaterThan(0)
          expect(own.items.every(row => row.departmentId === departmentId)).toBe(true)
        }
      }
    }
  })
  it('uses planned dates, including the leap day and year boundaries, ignoring other date overrides', () => {
    const { service } = setup()
    expect(service.query({ year: 2024, month: 2, dateField: 'actualTestDate', from: '2000-01-01', to: '2099-01-01' }).items.map(row => row.code)).toEqual(['MONTH-1', 'MONTH-2'])
    expect(service.query({ year: 2024, month: 12 }).items.map(row => row.code)).toEqual(['MONTH-5'])
    expect(service.query({ year: 2025, month: 1 }).items.map(row => row.code)).toEqual(['MONTH-6'])
    expect(service.query({ year: 2023, month: 2 }).total).toBe(0)
  })
  it('combines filters and scopes the query and selected export consistently', () => {
    const t = setup(), query = { year: 2024, month: 2 }
    expect(t.service.query({ ...query, name: '设备2', manufacturer: '厂家', serial: 'SN-2', departmentId: 'lab2' }).total).toBe(1)
    expect(t.service.query({ ...query, ownDepartment: true }).items.map(row => row.code)).toEqual(['MONTH-1'])
    const csv = t.service.export({ ...query, ids: ['id-0', 'id-2'] })
    expect(csv).toContain('MONTH-2'); expect(csv).not.toContain('MONTH-0'); expect(csv).not.toContain('MONTH-1')
    t.actor({ scope: 'department' })
    expect(t.service.query(query).items.map(row => row.code)).toEqual(['MONTH-1'])
    expect(t.service.export(query)).not.toContain('MONTH-2')
    t.actor({ roles: ['testing'] })
    expect(() => t.service.query(query)).toThrow('无权')
  })
  it('rejects missing, malformed and out-of-range year and month', () => {
    const { service } = setup()
    for (const query of [{}, { year: 2024 }, { year: '2024', month: 2 }, { year: 999, month: 2 }, { year: 10000, month: 2 }, { year: 2024, month: 0 }, { year: 2024, month: 13 }, { year: 2024, month: 2.5 }]) expect(() => service.query(query)).toThrow('年份和月份')
  })
})
