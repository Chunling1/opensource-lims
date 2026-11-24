import { describe, expect, it } from 'vitest'
import { createEquipmentLoans, seedEquipmentLoans } from '../../server/equipmentLoans'
import { createEquipmentForms } from '../../server/equipmentForm'
import { seedEquipmentLedger } from '../../server/equipmentLedger'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
import type { EquipmentLoanRow } from '../../src/types/quality/equipmentLoans'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }, actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
  const deps = { read: () => state, write: (value: RegistrationState) => { state = value }, actor: () => actor }
  const forms = createEquipmentForms(deps), loans = createEquipmentLoans(deps)
  const devices = ['lab', 'lab', 'lab2'].map((departmentId, index) => forms.save({ ...emptyEquipment(), code: `LOAN-${index}`, name: '测试设备', manufacturer: '测试厂', keeper: '保管员', departmentId }))
  return { loans, forms, devices, state: () => state, actor: (patch: Partial<Actor>) => { actor = { ...actor, ...patch } } }
}
const target = (row: EquipmentLoanRow) => ({ id: row.id, version: row.version, equipmentVersion: row.equipmentVersion })
function borrow(t: ReturnType<typeof setup>, ids = [t.devices[0]!.id]) {
  const context = t.loans.context({ mode: 'borrow', ids })
  return t.loans.borrow({ records: context.items.map(target), borrower: '手工填写领用人', borrowedStatus: '异常', date: '2026-10-01', notes: '测试领用' })
}
describe('equipment loans', () => {
  it('filters history by inclusive loan/return dates and conditions and exports matching records', () => {
    const t = setup(); borrow(t, t.devices.map(row => row.id))
    const rows = t.loans.query('records', {}).items
    t.loans.returnDevices({ returner: '手工归还人', records: rows.slice(0, 2).map(target), date: '2026-10-03', returnedStatus: '故障', notes: '送检' })
    const all = { status: 'all' }
    expect(t.loans.query('records', { ...all, dateField: 'borrowedAt', from: '2026-10-01', to: '2026-10-01' }).total).toBe(3)
    expect(t.loans.query('records', { ...all, dateField: 'returnedAt', from: '2026-10-03', to: '2026-10-03' }).total).toBe(2)
    expect(t.loans.query('records', { ...all, dateField: 'returnedAt', from: '2026-10-01', to: '2026-10-02' }).total).toBe(0)
    expect(t.loans.query('records', { ...all, field: 'borrowedStatus', value: '异' }).total).toBe(3)
    expect(t.loans.query('records', { ...all, field: 'returnedStatus', value: '故' }).total).toBe(2)
    expect(t.loans.query('records', { ...all, field: 'code', value: rows[0]!.code }).total).toBe(1)
    const csv = t.loans.exportHistory({ field: 'returnedStatus', value: '故', ids: [rows[0]!.id] })
    expect(csv).toContain('领用前设备状态'); expect(csv).toContain('归还人'); expect(csv).toContain('送检'); expect(csv).toContain('手工归还人'); expect(csv).toContain('归还操作人')
    expect(csv).toContain(rows[0]!.code); expect(csv).not.toContain(rows[1]!.code)
    for (const input of [{ field: 'departmentId' }, { dateField: 'createdAt' }, { dateField: 'borrowedAt', from: '2026-10-04', to: '2026-10-01' }, { dateField: 'returnedAt', from: '2026-02-30', to: '2026-10-01' }]) expect(() => t.loans.query('records', input)).toThrow()
    const other = rows.find(row => row.departmentId === 'lab2')!
    t.actor({ scope: 'department', roles: ['reviewer'] })
    expect(t.loans.exportHistory({ ids: [other.id] })).not.toContain(other.code)
  })
  it('lends available devices atomically, records the borrower and operator and blocks duplicate borrowing', () => {
    const t = setup(), ids = t.devices.slice(0, 2).map(row => row.id), context = t.loans.context({ mode: 'borrow', ids })
    const input = { records: context.items.map(target), borrower: '手工填写领用人', borrowedStatus: '异常', date: '2026-10-01', notes: '批量' }
    expect(t.loans.borrow(input)).toEqual({ count: 2 })
    expect(t.loans.query('available', {}).total).toBe(1)
    expect(t.forms.detail(ids[0]!).status).toBe('可用')
    expect(t.loans.query('records', {}).items).toHaveLength(2)
    const row = t.loans.query('records', {}).items[0]!
    expect(row).toMatchObject({ borrowerId: '', borrower: '手工填写领用人', borrowedById: 'admin', borrowedBy: '管理员', borrowedStatus: '异常', loanStatus: '未归还', keeper: '保管员' })
    expect(() => t.loans.borrow(input)).toThrow('已被领用')
    expect(t.state().equipmentLoans).toHaveLength(2)
    expect(() => t.forms.remove(row.equipmentId, { version: row.equipmentVersion })).toThrow('领用历史')
  })
  it('applies a common return condition and notes to the batch without changing ledger statuses', () => {
    const t = setup(); borrow(t, t.devices.slice(0, 2).map(row => row.id))
    const records = t.loans.query('records', {}).items
    const changes = records.map(target)
    t.loans.returnDevices({ returner: ' 手工归还人 ', returnedBy: '忽略客户端操作人', returnedById: 'other', records: changes, date: '2026-10-02', returnedStatus: '异常', notes: '同批归还' })
    expect(t.loans.query('records', {}).total).toBe(0)
    const history = t.loans.query('records', { status: 'returned' }).items
    expect(history.every(row => row.borrowedStatus === '异常' && row.loanStatus === '已归还' && row.returnedById === 'admin')).toBe(true)
    history.forEach(row => expect(t.forms.detail(row.equipmentId).status).toBe('可用'))
    expect(history.every(row => row.returnedStatus === '异常' && row.returnNotes === '同批归还' && row.returner === '手工归还人' && row.returnedBy === '管理员')).toBe(true)
    expect(t.loans.query('available', {}).total).toBe(3)
    const available = history.find(row => row.returnedStatus === '异常')!
    borrow(t, [available.equipmentId])
    expect(t.loans.query('records', { status: 'all' }).total).toBe(3)
    expect(() => t.loans.returnDevices({ returner: '手工归还人', records: changes, date: '2026-10-02', returnedStatus: '异常', notes: '同批归还' })).toThrow('已归还')
    expect(() => t.forms.remove(available.equipmentId, { version: t.forms.detail(available.equipmentId).version })).toThrow('领用历史')
  })
  it('validates every return before writing and preserves scrapped devices', () => {
    const t = setup(); borrow(t, t.devices.slice(0, 2).map(row => row.id))
    let rows = t.loans.query('records', {}).items
    const before = structuredClone(t.state())
    expect(() => t.loans.returnDevices({ returner: '手工归还人', records: rows.map(target), date: '2026-09-30', returnedStatus: '正常', notes: '' })).toThrow('不能早于')
    expect(() => t.loans.returnDevices({ returner: '手工归还人', records: rows.map(target), date: '2026-10-02', returnedStatus: '可用', notes: '' })).toThrow('归还时的设备状态')
    for (const returner of ['', '   ', 'x'.repeat(101), undefined]) expect(() => t.loans.returnDevices({ records: rows.map(target), date: '2026-10-02', returnedStatus: '正常', notes: '', returner })).toThrow()
    expect(t.state()).toEqual(before)
    const device = t.forms.detail(rows[0]!.equipmentId)
    t.forms.save({ ...device, status: '报废' }, device.id)
    t.loans.returnDevices({ returner: '手工归还人', records: rows.map(target), date: '2026-10-02', returnedStatus: '待检查', notes: '' })
    expect(t.forms.detail(device.id).status).toBe('报废')
    expect(t.loans.query('available', {}).items.some(row => row.id === device.id)).toBe(false)
    expect(t.loans.query('records', { status: 'returned' }).items.every(row => row.returnedStatus === '待检查')).toBe(true)
  })
  it('rejects stale and invalid batch borrowing without partial writes', () => {
    const t = setup(), ids = t.devices.slice(0, 2).map(row => row.id), rows = t.loans.context({ mode: 'borrow', ids }).items
    const input = { records: rows.map(target), borrower: '管理员', borrowedStatus: '正常', date: '2026-10-01', notes: '' }
    for (const patch of [{ borrower: '   ' }, { borrower: 'x'.repeat(101) }, { borrowedStatus: '无效状态' }, { borrowedStatus: '可用' }, { date: '2026-02-30' }, { notes: 'x'.repeat(1001) }, { records: [target(rows[0]!), target(rows[0]!)] }]) expect(() => t.loans.borrow({ ...input, ...patch })).toThrow()
    const device = t.forms.detail(ids[1]!)
    t.forms.save({ ...device, status: '停用' }, device.id)
    expect(() => t.loans.borrow(input)).toThrow('不可用')
    expect(t.state().equipmentLoans || []).toHaveLength(0)
  })
  it('applies department and role restrictions to queries, people, details, export and writes', () => {
    const t = setup(); borrow(t, t.devices.map(row => row.id))
    const other = t.loans.query('records', { status: 'all' }).items.find(row => row.departmentId === 'lab2')!
    t.actor({ scope: 'department', roles: ['quality'] })
    expect(t.loans.query('records', {}).total).toBe(2)
    expect(t.loans.options().some(row => row.id === 'other')).toBe(false)
    expect(() => t.loans.detail(other.id)).toThrow('无权')
    expect(t.loans.export('records', { ids: [other.id] })).not.toContain('LOAN-2')
    t.actor({ roles: ['quality', 'reviewer'] })
    expect(t.loans.query('records', {}).total).toBe(2)
    expect(() => t.loans.context({ mode: 'return', ids: [t.state().equipmentLoans![0]!.id] })).toThrow('无权')
    expect(() => t.loans.borrow({})).toThrow('无权')
    t.actor({ roles: ['testing'] })
    expect(() => t.loans.query('records', {})).toThrow('无权')
  })
  it('filters, pages and exports all matching rows including fields hidden by default', () => {
    const t = setup()
    for (let i = 3; i < 15; i++) t.forms.save({ ...emptyEquipment(), code: `LOAN-${i}`, name: '其他设备', manufacturer: '其他厂', departmentId: 'lab' })
    expect(t.loans.query('available', {}).items).toHaveLength(10)
    expect(t.loans.query('available', { page: 2 }).items).toHaveLength(5)
    expect(t.loans.query('available', { code: 'LOAN-', name: '测试', manufacturer: '测试厂' }).total).toBe(3)
    expect(t.loans.export('available', {})).toContain('LOAN-14')
    expect(t.loans.export('available', { ids: [t.devices[0]!.id] })).not.toContain('LOAN-1')
    expect(t.loans.export('available', {})).toContain('所属部门')
    for (const input of [{ page: '1' }, { pageSize: '10' }, { status: 'bad' }, { ids: ['x', 'x'] }]) expect(() => t.loans.query('available', input)).toThrow()
  })
  it('seeds open and returned conditions idempotently without changing ledger statuses', () => {
    const state: RegistrationState = { commissions: [], samples: [], equipmentLedger: seedEquipmentLedger() }
    const ledger = structuredClone(state.equipmentLedger)
    seedEquipmentLoans(state)
    expect(state.equipmentLoans).toHaveLength(4)
    expect(state.equipmentLoans!.filter(row => !row.returnedAt)).toHaveLength(2)
    expect(state.equipmentLoans!.some(row => row.returnedStatus === '异常')).toBe(true)
    expect(state.equipmentLedger).toEqual(ledger)
    const copy = structuredClone(state); seedEquipmentLoans(state); expect(state).toEqual(copy)
  })
  it('keeps the previous displayed returner for historical records without the new field', () => {
    const t = setup(); borrow(t)
    const row = t.loans.query('records', {}).items[0]!
    t.loans.returnDevices({ records: [target(row)], returner: '代归还人', date: '2026-10-02', returnedStatus: '正常', notes: '' })
    delete t.state().equipmentLoans![0]!.returner
    expect(t.loans.detail(row.id)).toMatchObject({ returner: '管理员', returnedBy: '管理员' })
  })
})
