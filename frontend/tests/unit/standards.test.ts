import { describe, expect, it } from 'vitest'
import { migrateStandardGroups } from '../../server/standardGroupMigration'
import { createStandards, seedStandards } from '../../server/standards'
import { createEquipmentGroupDefinitions, seedStandardGroups } from '../../server/equipmentGroupDefinitions'
import { emptyStandard, standardExtensionDays } from '../../src/types/quality/standards'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
import { registrationCsv } from '../../server/registrationDomain'
import { parsePersonnelCsv } from '../../server/personnel'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }
  let actor: Actor = { id: 'admin', name: '管理员', departmentId: 'lab', roles: ['admin'], scope: 'all' }
  seedStandardGroups(state); seedStandards(state)
  const deps = { actor: () => actor, read: () => state, write: (next: RegistrationState) => { state = next } }
  return { api: createStandards(deps), categories: createEquipmentGroupDefinitions(deps, 'standards'), state: () => state, actor: (next: Partial<Actor>) => { actor = { ...actor, ...next } } }
}
const draft = { ...emptyStandard(), code: 'TEST-2026', name: '测试标准', implementedAt: '2026-01-01', departmentIds: ['lab'], category: '用户输入类别' }
describe('testing standards', () => {
  it('validates metadata, obsolete dates, duplicate identifiers and stale edits', () => {
    const t = setup(), row = t.api.save(draft)
    expect(() => t.api.save(draft)).toThrow('已存在')
    for (const data of [{ name: '' }, { code: '' }, { implementedAt: '2026-02-30' }, { quantity: -1 }, { quantity: 1.5 }, { qualification: '其他' }, { departmentIds: ['missing'] }, { category: 'x'.repeat(201) }, { abolished: true, abolishedAt: '2025-12-31' }]) expect(() => t.api.save({ ...draft, code: 'NEW', ...data })).toThrow()
    const updated = t.api.save({ ...row, abolished: true, abolishedAt: '2026-10-01', replacementCode: 'NEW-2026', extensionDays: 999 })
    expect(updated.extensionDays).not.toBe(999)
    expect(t.api.save({ ...row, name: '后提交覆盖' })).toMatchObject({ name: '后提交覆盖', version: 3 })
    const active = t.api.save({ ...updated, abolished: false })
    expect(active.abolishedAt).toBe(''); expect(active.replacementCode).toBe(''); expect(active.extensionDays).toBeNull()
    t.api.remove({ id: row.id, version: row.version }); expect(() => t.api.detail(row.id)).toThrow('不存在')
  })
  it('stores arbitrary category text separately from all group operations', () => {
    const t = setup(), value = '自行输入;不在定义中、任意类别', row = t.api.save({ ...draft, category: value, groupIds: ['standard-category-1'] })
    expect(row.category).toBe(value); expect(row.groupIds).toEqual([])
    const context = t.api.context([row.id])
    t.api.associations({ records: context.records, groups: [{ ...context.groups[0], state: 'checked' }] })
    const grouped = t.api.detail(row.id)
    expect(grouped.category).toBe(value)
    const edited = t.api.save({ ...grouped, category: '新自由文本', groupIds: [] })
    expect(edited.groupIds).toEqual(['standard-category-1'])
    expect(t.api.query({ category: '新自由文本' }).items.map(row => row.id)).toEqual([row.id])
    expect(t.api.query({ category: '国家标准', ids: [row.id] }).total).toBe(0)
    const csv = t.api.export({ ids: [row.id] }); expect(csv).toContain('新自由文本'); expect(csv).not.toContain('国家标准')
    t.categories.remove({ ...t.categories.detail('standard-category-1') })
    expect(t.api.detail(row.id).category).toBe('新自由文本'); expect(t.api.detail(row.id).groupIds).toEqual([])
  })
  it('migrates legacy grouping without losing existing display text, only once', () => {
    const state = { commissions: [], samples: [], standardCategories: [{ id: 'legacy', name: '原类别', version: 1, departmentId: 'lab' }], standards: [{ id: 'record', categoryIds: ['legacy'] }] } as unknown as RegistrationState
    migrateStandardGroups(state)
    expect(state.standardGroups?.[0]?.id).toBe('legacy'); expect(state.standardCategories).toBeUndefined()
    expect(state.standards?.[0]).toMatchObject({ groupIds: ['legacy'], category: '原类别' })
    state.standardGroups![0]!.name = '修改分组'; migrateStandardGroups(state)
    expect(state.standards![0]!.category).toBe('原类别')
  })
  it('allows unassigned standards in forms and CSV without granting access to other departments', () => {
    const t = setup(); t.actor({ roles: ['quality'], scope: 'department', departmentId: 'lab' })
    const row = t.api.save({ ...draft, departmentIds: [], ownerDepartmentId: 'lab2' })
    expect(row.departmentIds).toEqual([]); expect(row.departments).toBe(''); expect(row.ownerDepartmentId).toBe('lab')
    expect(t.api.query({ ids: [row.id] }).total).toBe(1)
    expect(t.api.query({ ids: [row.id], ownDepartment: true }).total).toBe(0)
    expect(t.api.query({ ids: [row.id], departmentId: 'lab' }).total).toBe(0)
    const edited = t.api.save({ ...row, notes: '无部门仍可修改' })
    const csv = parsePersonnelCsv(t.api.export({ ids: [row.id] }))
    csv[1]![csv[0]!.indexOf('标准编号')] = 'UNASSIGNED-IMPORT'
    expect(t.api.importCsv(registrationCsv(csv)).count).toBe(1)
    const imported = t.api.query({ code: 'UNASSIGNED-IMPORT' }).items[0]!
    expect(imported.departmentIds).toEqual([])
    t.actor({ departmentId: 'lab2' })
    expect(t.api.query({ ids: [row.id, imported.id] }).total).toBe(0)
    expect(() => t.api.detail(row.id)).toThrow('无权')
    t.actor({ departmentId: 'lab' })
    t.api.remove({ ...edited }); t.api.remove({ ...imported })
    expect(t.api.query({ ids: [row.id, imported.id] }).total).toBe(0)
  })
  it('calculates elapsed calendar days, clamps future dates and handles leap years', () => {
    expect(standardExtensionDays(true, '2026-10-01', '2026-10-07')).toBe(6)
    expect(standardExtensionDays(true, '2026-10-08', '2026-10-07')).toBe(0)
    expect(standardExtensionDays(true, '2024-02-28', '2024-03-01')).toBe(2)
    expect(standardExtensionDays(false, '2026-10-01', '2026-10-07')).toBeNull()
  })
  it('filters combined fields, scopes departments, paginates and exports full business columns', () => {
    const t = setup()
    expect(t.api.query({ category: '方法', qualification: '检验', location: '实验室', ownDepartment: true }).total).toBe(1)
    expect(t.api.query({ departmentId: 'lab2' }).total).toBe(1)
    for (let i = 0; i < 7; i++) t.api.save({ ...draft, code: `NEW-${i}` })
    expect(t.api.query({ page: 2, pageSize: 10 }).items).toHaveLength(3)
    const csv = t.api.export({ ids: ['standard-1'] })
    expect(csv).toContain('是否在资质范围外'); expect(csv).toContain('是否英文标准'); expect(csv).toContain('DEMO-1-2026'); expect(csv).not.toContain('DEMO-2-2026')
    t.actor({ roles: ['quality'], scope: 'department', departmentId: 'lab2' })
    expect(t.api.query({}).total).toBe(1); expect(t.api.context(['standard-6']).groups).toHaveLength(0)
    expect(() => t.api.detail('standard-1')).toThrow('无权')
    expect(() => t.api.save(draft)).toThrow('使用部门')
    t.actor({ roles: ['quality', 'reviewer'] })
    expect(t.api.query({}).total).toBe(1); expect(() => t.api.save(draft)).toThrow('无权'); expect(() => t.api.context(['standard-6'])).toThrow('无权')
  })
  it('preserves mixed associations and applies a batch atomically with both versions checked', () => {
    const t = setup(), context = t.api.context(['standard-1', 'standard-2'])
    expect(context.groups[0]!.state).toBe('mixed')
    const original = structuredClone(t.state().standards)
    expect(() => t.api.associations({ records: context.records, groups: [{ ...context.groups[0], state: 'checked' }, { id: 'bad', version: 1, state: 'checked' }] })).toThrow('不存在')
    expect(t.state().standards).toEqual(original)
    t.api.associations({ records: context.records, groups: context.groups.map(group => group.id === 'standard-category-3' ? { ...group, state: 'checked' } : group) })
    expect(t.api.detail('standard-1').groupIds).toEqual(['standard-category-1', 'standard-category-3'])
    expect(t.api.detail('standard-2').groupIds).toEqual(['standard-category-2', 'standard-category-3'])
    expect(() => t.api.associations({ ...context })).not.toThrow()
    const fresh = t.api.context(['standard-1']), category = t.categories.detail('standard-category-1')
    t.categories.save({ ...category, name: '新类别名' })
    expect(t.api.detail('standard-1').category).toBe('方法标准')
    expect(t.api.context(['standard-1']).groups[0]!.name).toBe('新类别名')
    expect(() => t.api.associations(fresh as unknown as Record<string, unknown>)).not.toThrow()
    t.categories.remove({ ...t.categories.detail(category.id) })
    expect(t.api.detail('standard-1').groupIds).not.toContain(category.id)
    expect(t.api.detail('standard-1').category).toBe('方法标准')
  })
  it('validates all CSV rows before committing, resolves categories and departments, and accepts exports', () => {
    const t = setup(), csv = parsePersonnelCsv(t.api.export({ ids: ['standard-1', 'standard-2'] }))
    const code = csv[0]!.indexOf('标准编号'), control = csv[0]!.indexOf('受控号'), department = csv[0]!.indexOf('使用部门')
    csv[1]![code] = 'IMPORT-1'; csv[1]![control] = 'IMPORT-1'; csv[2]![code] = 'IMPORT-2'; csv[2]![control] = 'IMPORT-2'
    csv[2]![department] = '不存在的部门'
    expect(() => t.api.importCsv(registrationCsv(csv))).toThrow('第 3 行'); expect(t.api.query({}).total).toBe(6)
    csv[2]![department] = '实验室'; csv[1]![csv[0]!.indexOf('类别')] = '任意;自由、文本'
    expect(t.api.importCsv(registrationCsv(csv)).count).toBe(2)
    expect(t.api.query({ code: 'IMPORT' }).total).toBe(2)
    expect(t.api.query({ code: 'IMPORT-1' }).items[0]).toMatchObject({ category: '任意;自由、文本', groupIds: [] })
    expect(() => t.api.importCsv(registrationCsv(csv))).toThrow('受控号已存在')
    expect(() => t.api.importCsv('错误模板\n值')).toThrow('模板列')
  })
})
