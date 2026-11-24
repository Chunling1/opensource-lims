import { describe, it, expect } from 'vitest'
import { createEquipmentForms } from '../../server/equipmentForm'
import { equipmentImportFields } from '../../src/types/quality/equipmentImport'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import { registrationCsv } from '../../server/registrationDomain'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
const csv = (rows: Record<string, string>[]) => registrationCsv([equipmentImportFields.map(f => f.label), ...rows.map(row => equipmentImportFields.map(f => row[f.key] || ''))])
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }
  let actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], scope: 'all', departmentId: 'lab' }
  let writes = 0
  const forms = createEquipmentForms({ actor: () => actor, read: () => state, write: next => { state = next; writes++ } })
  return { forms, state: () => state, writes: () => writes, actor: (next: Partial<Actor>) => { actor = { ...actor, ...next } } }
}
const row = { code: '00001', name: '导入设备', department: '实验室' }
describe('equipment CSV import', () => {
  it('uses a BOM template and preserves identifiers, quoted fields, profile fields and blank dates', () => {
    const t = setup()
    expect(t.forms.template()).toBe(csv([]))
    expect(t.forms.template().startsWith('\uFEFF')).toBe(true)
    expect(t.forms.importCsv(csv([{ ...row, serial: '0000123', price: '0', notes: '含逗号,及"引号"\n多行备注', purchasedAt: '2024-02-29', equipmentType: '检测设备', tester: '检定员', validity: '一年' }, { ...row, code: '00002', department: '无' }]))).toEqual({ count: 2 })
    expect(t.writes()).toBe(1)
    const items = t.state().equipmentLedger!
    expect(items[0]).toMatchObject({ code: '00001', serial: '0000123', status: '可用', departmentId: 'lab', price: 0, purchasedAt: '2024-02-29', notes: '含逗号,及"引号"\n多行备注', manualCount: 0 })
    expect(t.forms.detail(items[0]!.id).profile).toMatchObject({ equipmentType: '检测设备', tester: '检定员', validity: '一年', projects: [], usage: [] })
    expect(items[1]).toMatchObject({ departmentId: '', department: '', price: null, lastTestDate: '' })
  })
  it('rejects invalid rows with a row number and no partial write', () => {
    const t = setup()
    for (const change of [{ code: '' }, { name: '' }, { department: '不存在' }, { status: '未知' }, { purchasedAt: '2026-02-30' }, { price: '-1' }, { price: 'NaN' }, { price: '1000000000001' }]) {
      expect(() => t.forms.importCsv(csv([row, { ...row, code: '00002', ...change }]))).toThrow('第 3 行')
      expect(t.writes()).toBe(0)
    }
  })
  it('rejects file duplicates and existing codes without overwriting records', () => {
    const t = setup()
    const saved = t.forms.save({ ...emptyEquipment(), code: 'Existing', name: '已有设备', departmentId: 'lab' })
    const before = structuredClone(t.state())
    for (const rows of [[row, row], [row, { ...row, code: 'existing' }]]) {
      expect(() => t.forms.importCsv(csv(rows))).toThrow('第 3 行：档案号重复')
      expect(t.state()).toEqual(before)
      expect(t.forms.detail(saved.id)).toEqual(saved)
    }
  })
  it('validates headers, syntax, file size, row limit and column count', () => {
    const t = setup()
    const inputs = ['', csv([]), csv([row]).replace('档案号', '编号'), '"unclosed', 'a'.repeat(2 * 1024 * 1024 + 1), csv(Array.from({ length: 1001 }, (_, i) => ({ ...row, code: `${i}` }))), `${csv([])}\r\nwrong,count`]
    for (const input of inputs) { expect(() => t.forms.importCsv(input)).toThrow(); expect(t.writes()).toBe(0) }
  })
  it('enforces writer and department scope permissions for every row', () => {
    const t = setup()
    t.actor({ roles: ['reviewer'] })
    expect(() => t.forms.importCsv(csv([row]))).toThrow('无权')
    t.actor({ roles: ['quality'], scope: 'department' })
    expect(() => t.forms.importCsv(csv([row, { ...row, code: 'other', department: '无' }]))).toThrow('第 3 行')
    expect(t.writes()).toBe(0)
    expect(t.forms.importCsv(csv([row]))).toEqual({ count: 1 })
  })
})
