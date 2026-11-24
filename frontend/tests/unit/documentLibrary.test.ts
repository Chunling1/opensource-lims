import { describe, expect, it } from 'vitest'
import { createDocumentLibrary, seedDocumentLibrary } from '../../server/documentLibrary'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }, actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
  seedDocumentLibrary(state, new Date('2026-10-07'))
  return { api: createDocumentLibrary({ actor: () => actor, read: () => state, write: next => { state = next } }), state: () => state, actor: (patch: Partial<Actor>) => { actor = { ...actor, ...patch } } }
}
const draft = { code: 'TEST-01', category: '程序文件', name: '测试文件', quantity: 10, notes: '备注' }
describe('document library', () => {
  it('records manually entered people separately from the actual operator', () => {
    const t = setup(), row = t.api.save(draft), command = { id: row.id, version: row.version, quantity: 1, date: '2026-10-07' }
    for (const person of ['', '   ', 'x'.repeat(201), 123]) expect(() => t.api.move('issue', { ...command, person })).toThrow('领用人')
    expect(t.api.detail(row.id).remaining).toBe(10)
    const issued = t.api.move('issue', { ...command, person: ' 张领用 ', operator: '伪造', operatorId: 'other' })
    expect(issued.person).toBe('张领用'); expect(issued.operator).toBe('管理员'); expect(issued.operatorId).toBe('admin')
    const current = t.api.detail(row.id)
    expect(() => t.api.move('recover', { ...command, version: current.version, person: ' ' })).toThrow('回收人')
    const recovered = t.api.move('recover', { ...command, version: current.version, person: '李回收' })
    expect(recovered.person).toBe('李回收'); expect(recovered.operator).toBe('管理员')
    expect(t.api.exportHistory('issue', { documentId: row.id })).toContain('领用人')
    expect(t.api.exportHistory('recover', { documentId: row.id })).toContain('回收人')
    // Historical rows created before this field existed retain their original person.
    const legacy = t.state().documentMovements![0]!; delete (legacy as Partial<typeof legacy>).person
    expect(t.api.history(legacy.kind, { ids: [legacy.id] }).items[0]!.person).toBe(legacy.operator)
  })
  it('validates identity and quantity, protects versions and preserves issued history', () => {
    const { api } = setup(), row = api.save(draft)
    expect(() => api.save({ ...draft, code: ' test-01 ' })).toThrow('已存在')
    for (const patch of [{ code: '' }, { name: '' }, { quantity: -1 }, { quantity: 0.5 }]) expect(() => api.save({ ...draft, ...patch })).toThrow()
    api.move('issue', { ...row, quantity: 3, date: '2026-10-07', operator: '伪造' })
    expect(() => api.move('issue', { ...row, quantity: 1, date: '2026-10-07' })).not.toThrow()
    expect(() => api.remove({ ...row })).toThrow('已有领用')
    let changed = api.detail(row.id)
    expect(changed.remaining).toBe(6); expect(changed.usage).toBe('部分领用')
    expect(() => api.save({ ...changed, quantity: 2 })).toThrow('不能少于')
    changed = api.save({ ...changed, name: '新文件名称', code: 'NEW-01', quantity: 12 })
    const history = api.history('issue', { documentId: row.id }).items[0]!
    expect(history.name).toBe('测试文件'); expect(history.operator).toBe('管理员'); expect(history.code).toBe('TEST-01')
    expect(() => api.remove({ ...changed })).toThrow('已有领用')
    const fresh = api.save({ ...draft, code: 'DELETE' }); api.remove({ ...fresh }); expect(() => api.detail(fresh.id)).toThrow('不存在')
  })
  it('enforces conservation across full issue and recovery and validates dates', () => {
    const t = setup(), row = t.api.save(draft), command = { ...row, date: '2026-10-07' }
    expect(() => t.api.move('issue', { ...command, quantity: 11 })).toThrow('超量')
    expect(() => t.api.move('recover', { ...command, quantity: 1 })).toThrow('超量')
    for (const date of ['', '2026-02-30']) expect(() => t.api.move('issue', { ...command, date, quantity: 1 })).toThrow()
    t.api.move('issue', { ...command, quantity: 10 }); let changed = t.api.detail(row.id)
    expect(changed.remaining).toBe(0); expect(changed.usage).toBe('全部领用')
    const before = structuredClone(t.state())
    expect(() => t.api.move('recover', { ...changed, date: '2026-10-06', quantity: 1 })).toThrow('不能早于')
    expect(t.state()).toEqual(before)
    t.api.move('recover', { ...changed, date: '2026-10-08', quantity: 4 }); changed = t.api.detail(row.id)
    expect(changed.remaining).toBe(4); expect(changed.outstanding).toBe(6)
    t.api.move('recover', { ...changed, date: '2026-10-08', quantity: 6 }); changed = t.api.detail(row.id)
    expect(changed.remaining).toBe(10); expect(changed.outstanding).toBe(0); expect(changed.historyCount).toBe(3)
  })
  it('filters, paginates and exports files and immutable records', () => {
    const { api } = setup()
    for (let i = 0; i < 12; i++) api.save({ ...draft, code: `TEST-${i}` })
    expect(api.query({ name: '测试', category: '程序' }).total).toBe(12); expect(api.query({ name: '测试', page: 2 }).items).toHaveLength(2)
    const row = api.query({ name: '测试' }).items[0]!
    expect(api.export({ ids: [row.id] })).toContain('备注')
    api.move('issue', { ...row, quantity: 2, date: '2026-10-07' })
    expect(api.history('issue', { documentId: row.id, name: '测试' }).total).toBe(1)
    expect(api.exportHistory('issue', { documentId: row.id })).toContain('管理员')
    for (const bad of [{ ids: [row.id, row.id] }, { page: 0 }, { pageSize: 2 }, { name: 4 }]) expect(() => api.query(bad)).toThrow()
  })
  it('validates attachments, retains them on metadata edits, and isolates department data', () => {
    const t = setup(), row = t.api.save(draft), file = { id: 'file-1', name: 'a.txt', size: 3, type: 'text/plain', dataUrl: 'data:text/plain;base64,YWJj' }
    let changed = t.api.saveFiles({ ...row, files: [file] })
    expect(t.api.query({ name: '测试' }).items[0]!.files).toEqual([])
    changed = t.api.save({ ...changed, notes: '保留附件' }); expect(changed.files).toEqual([file])
    expect(() => t.api.saveFiles({ ...changed, files: [{ ...file, size: 5 }] })).toThrow('内容')
    expect(() => t.api.saveFiles({ ...changed, files: [file, file] })).toThrow()
    t.actor({ roles: ['quality'], scope: 'department', departmentId: 'lab2' })
    expect(t.api.query({}).items.every(item => item.departmentId === 'lab2')).toBe(true)
    expect(() => t.api.detail(row.id)).toThrow('无权'); expect(() => t.api.history('issue', { documentId: row.id })).toThrow('无权')
    expect(t.api.export({ ids: [row.id] })).not.toContain('测试文件')
    for (const roles of [['reviewer', 'quality'], ['approver', 'quality']]) {
      t.actor({ roles, scope: 'all' }); expect(t.api.detail(row.id).files).toHaveLength(1)
      expect(() => t.api.save(draft)).toThrow('无权'); expect(() => t.api.move('issue', { ...changed, quantity: 1, date: '2026-10-07' })).toThrow('无权')
      expect(() => t.api.saveFiles({ ...changed, files: [] })).toThrow('无权')
    }
    t.actor({ roles: ['equipment'] }); expect(() => t.api.query({})).toThrow('无权')
  })
})


describe('document module isolation', () => {
  it('isolates quantities, history, attachments and code uniqueness between both modules', () => {
    let state: RegistrationState = { commissions: [], samples: [] }
    const actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
    seedDocumentLibrary(state, new Date('2026-10-07'))
    seedDocumentLibrary(state, new Date('2026-10-07'), 'monitoring')
    const deps = { actor: () => actor, read: () => state, write: (next: RegistrationState) => { state = next } }
    const library = createDocumentLibrary(deps), monitoring = createDocumentLibrary(deps, 'monitoring')
    const before = structuredClone(state.libraryDocuments), historyBefore = structuredClone(state.documentMovements)
    const row = monitoring.save(draft), other = library.save(draft)
    expect(() => library.detail(row.id)).toThrow('不存在')
    expect(() => monitoring.detail(other.id)).toThrow('不存在')
    monitoring.move('issue', { id: row.id, version: row.version, quantity: 2, date: '2026-10-07', person: '代领人' })
    expect(monitoring.detail(row.id).remaining).toBe(8)
    expect(library.detail(other.id).remaining).toBe(10)
    expect(library.history('issue', {}).items.some(item => item.documentId === row.id)).toBe(false)
    expect(() => library.history('issue', { documentId: row.id })).toThrow('不存在')
    const file = { id: 'monitoring-file', name: 'plan.txt', size: 4, type: 'text/plain', dataUrl: 'data:text/plain;base64,cGxhbg==' }
    const saved = monitoring.saveFiles({ ...monitoring.detail(row.id), files: [file] })
    expect(saved.files).toEqual([file]); expect(library.detail(other.id).files).toEqual([])
    expect(() => library.saveFiles({ ...saved, files: [file] })).toThrow('不存在')
    monitoring.move('recover', { ...row, quantity: 2, date: '2026-10-07', person: '回收人' })
    expect(monitoring.detail(row.id).remaining).toBe(10)
    expect(() => monitoring.remove({ ...monitoring.detail(row.id) })).toThrow('不能删除')
    expect(monitoring.export({})).toContain('年度质量监控计划')
    expect(library.export({})).not.toContain('年度质量监控计划')
    library.remove({ ...other })
    expect(state.libraryDocuments).toEqual(before); expect(state.documentMovements).toEqual(historyBefore)
    actor.scope = 'department'; actor.departmentId = 'lab2'; actor.roles = ['quality']
    expect(monitoring.query({}).items.every(item => item.departmentId === 'lab2')).toBe(true)
    expect(() => monitoring.detail(row.id)).toThrow('不存在')
    actor.scope = 'all'; actor.roles = ['reviewer']
    expect(monitoring.detail(row.id).name).toBe(draft.name)
    expect(() => monitoring.save(draft)).toThrow('无权')
  })
})
