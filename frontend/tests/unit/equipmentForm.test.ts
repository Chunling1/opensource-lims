import { describe, it, expect } from 'vitest'
import { createEquipmentForms } from '../../server/equipmentForm'
import { createEquipmentLedger } from '../../server/equipmentLedger'
import { emptyEquipment, equipmentCheckMeasurements } from '../../src/types/quality/equipmentForm'
import { emptyTrialForm } from '../../src/types/testing/dataEntryDetail'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }, actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], scope: 'all', departmentId: 'lab' }
  const deps = { actor: () => actor, read: () => state, write: (next: RegistrationState) => { state = next } }
  return { form: createEquipmentForms(deps), ledger: createEquipmentLedger(deps), actor: (next: Partial<Actor>) => { actor = { ...actor, ...next } }, state: () => state }
}
const input = () => ({ ...emptyEquipment(), code: 'EQ-NEW', name: '测试设备', departmentId: 'lab' })
describe('equipment creation', () => {
  it('batch updates only checked fields and preserves all record and attachment identities', () => {
    const t = setup(), draft = input()
    draft.profile.usage = [{ id: 'draft', person: '使用人' }]
    draft.profile.attachments.manual = [{ id: 'file', name: 'manual.txt', type: 'text/plain', size: 2, dataUrl: 'data:text/plain;base64,b2s=' }]
    const first = t.form.save(draft), second = t.form.save({ ...input(), code: 'SECOND', keeper: '保管人' }), other = t.form.save({ ...input(), code: 'OTHER' })
    expect(t.form.batchUpdate({ records: [first, second].map(({ id, version }) => ({ id, version })), changes: { equipmentType: '检测设备', departmentId: '', keeper: '', status: '停用', purchasedAt: '', price: 0 } })).toEqual({ count: 2 })
    for (const original of [first, second]) {
      expect(t.form.detail(original.id)).toEqual({ ...original, version: original.version + 1, departmentId: '', department: '', keeper: '', status: '停用', purchasedAt: '', price: 0, profile: { ...original.profile, equipmentType: '检测设备' } })
    }
    expect(t.form.detail(other.id)).toEqual(other)
    t.form.batchUpdate({ records: [{ id: first.id, version: 2 }], changes: { price: null } })
    expect(t.form.detail(first.id).price).toBeNull()
  })
  it('rejects invalid batches atomically', () => {
    const t = setup(), first = t.form.save(input()), second = t.form.save({ ...input(), code: 'SECOND' })
    const records = [first, second].map(({ id, version }) => ({ id, version }))
    const before = structuredClone(t.state())
    for (const changes of [{}, { name: '不允许' }, { price: -1 }, { status: '' }, { purchasedAt: '2026-02-30' }, { departmentId: 'unknown' }]) {
      expect(() => t.form.batchUpdate({ records, changes })).toThrow()
      expect(t.state()).toEqual(before)
    }
    expect(() => t.form.batchUpdate({ records: [records[0], records[0]], changes: { keeper: '新版' } })).toThrow('不能重复')
    expect(() => t.form.batchUpdate({ records: [], changes: { keeper: '新版' } })).toThrow('请选择')
    expect(t.state()).toEqual(before)
  })
  it('checks batch writer roles, source scope and destination department before writing', () => {
    const t = setup(), first = t.form.save(input()), second = t.form.save({ ...input(), code: 'SECOND', departmentId: 'lab2' })
    const records = [first, second].map(({ id, version }) => ({ id, version })), before = structuredClone(t.state())
    t.actor({ roles: ['reviewer'] })
    expect(() => t.form.batchUpdate({ records, changes: { status: '停用' } })).toThrow('无权')
    t.actor({ roles: ['quality'], scope: 'department', departmentId: 'lab' })
    expect(() => t.form.batchUpdate({ records, changes: { status: '停用' } })).toThrow('无权')
    expect(() => t.form.batchUpdate({ records: [records[0]], changes: { departmentId: 'lab2' } })).toThrow('可访问')
    expect(t.state()).toEqual(before)
  })
  it('deletes only the selected equipment and its owned records and files', () => {
    const t = setup(), draft = input()
    draft.profile.usage = [{ id: 'draft-record', person: '使用人' }]
    draft.profile.attachments.manual = [{ id: 'draft-file', name: 'manual.txt', type: 'text/plain', size: 2, dataUrl: 'data:text/plain;base64,b2s=' }]
    const target = t.form.save(draft), other = t.form.save({ ...input(), code: 'KEEP' })
    expect(t.form.remove(target.id, { version: target.version })).toEqual({ id: target.id })
    expect(() => t.form.detail(target.id)).toThrow('不存在')
    expect(t.state().equipmentProfiles?.[target.id]).toBeUndefined()
    expect(t.form.detail(other.id)).toEqual(other)
    expect(t.ledger.query({}).total).toBe(1)
  })
  it('rejects stale, unauthorized and referenced equipment deletion without changing data', () => {
    const t = setup(), saved = t.form.save(input())
    t.actor({ roles: ['reviewer'] })
    expect(() => t.form.remove(saved.id, { version: saved.version })).toThrow('无权')
    t.actor({ roles: ['quality'], scope: 'department', departmentId: 'lab2' })
    expect(() => t.form.remove(saved.id, { version: saved.version })).toThrow('无权')
    t.actor({ roles: ['admin'], scope: 'all' })
    t.state().equipmentPlans = { plan: { version: 1, associatedIds: [saved.id], defaultIds: [] } }
    expect(() => t.form.remove(saved.id, { version: saved.version })).toThrow('引用')
    t.state().equipmentPlans = {}
    t.state().dataEntries = { sample: { version: 1, reportRevision: 1, form: { ...emptyTrialForm(), equipmentIds: [saved.id] }, files: [], events: [], requests: [] } }
    expect(() => t.form.remove(saved.id, { version: saved.version })).toThrow('引用')
    expect(t.form.detail(saved.id)).toEqual(saved)
  })
  it('updates the existing equipment and preserves record/file identities with optimistic version checks', () => {
    const t = setup(), draft = input()
    draft.profile.usage = [{ id: 'draft-row', person: '使用人', notes: '原备注' }]
    draft.profile.attachments.manual = [{ id: 'draft-file', name: 'manual.txt', type: 'text/plain', size: 2, dataUrl: 'data:text/plain;base64,b2s=' }]
    const saved = t.form.save(draft)
    const edited = t.form.save({ ...saved, name: '编辑后设备', profile: { ...saved.profile, usage: [{ ...saved.profile.usage[0]!, notes: '编辑后备注' }] } }, saved.id)
    expect(edited.id).toBe(saved.id)
    expect(edited.version).toBe(saved.version + 1)
    expect(edited.profile.usage[0]).toMatchObject({ id: saved.profile.usage[0]!.id, notes: '编辑后备注' })
    expect(edited.profile.attachments).toEqual(saved.profile.attachments)
    expect(t.state().equipmentLedger).toHaveLength(1)
    expect(t.form.detail(saved.id)).toEqual(edited)
    expect(t.form.save({ ...saved, name: '后提交覆盖' }, saved.id)).toMatchObject({ name: '后提交覆盖', version: edited.version + 1 })
    expect(t.form.detail(saved.id).name).toBe('后提交覆盖')
    const other = t.form.save({ ...input(), code: 'OTHER' })
    expect(() => t.form.save({ ...edited, code: other.code }, edited.id)).toThrow('档案号已存在')
    expect(() => t.form.save({ ...edited, price: -1 }, edited.id)).toThrow('非负金额')
    t.actor({ roles: ['reviewer'] })
    expect(() => t.form.save(edited, edited.id)).toThrow('无权')
    t.actor({ roles: ['quality'], scope: 'department', departmentId: 'lab2' })
    expect(() => t.form.save({ ...edited, departmentId: 'lab2' }, edited.id)).toThrow('无权')
  })
  it('uses the shared plan tree with group selection, pagination and department authorization', () => {
    const t = setup()
    t.actor({ roles: ['quality'], scope: 'department', departmentId: 'lab' })
    expect(t.form.plans().items.some(row => row.id === 'temperature')).toBe(true)
    expect(t.form.plans().items.some(row => row.id === 'branch')).toBe(false)
    expect(t.form.plans({ parentId: 'temperature', page: 3 }).items).toHaveLength(6)
    const all = t.form.planSelection(undefined, { kind: 'group', id: 'temperature', checked: true })
    expect(all.count).toBe(26)
    const subset = t.form.planSelection(all.selection, { kind: 'plan', id: 'temperature-21', checked: false })
    expect(subset.count).toBe(25)
    expect(subset.groups.temperature?.indeterminate).toBe(true)
    expect(t.form.plans({ keyword: 'WD021' }).items[0]?.id).toBe('temperature-21')
    expect(() => t.form.plans({ parentId: 'branch' })).toThrow('不可访问')
    expect(() => t.form.planSelection(undefined, { kind: 'plan', id: 'branch-1', checked: true })).toThrow('不可访问')
    const draft = input(); draft.profile.projects = [{ id: 'branch-1', code: '', name: '' }]
    expect(() => t.form.save(draft)).toThrow('不可访问')
    draft.profile.projects = [{ id: 'pressure-1', code: 'forged', name: 'forged' }]
    expect(t.form.save(draft).profile.projects[0]).toMatchObject({ id: 'pressure-1', code: 'FZ', name: '风量罩校准' })
  })
  it('persists basic fields, projects, records and attachments together and returns row counts', () => {
    const t = setup(), draft = input()
    draft.profile.projects = t.form.options().projects.slice(0, 2)
    draft.profile.calibrations.push({ id: 'draft', organization: '计量中心', certificate: 'C001', conclusion: '合格', date: '2026-10-01', cycle: '12个月', nextDate: '2027-10-01' })
    draft.profile.usage.push({ id: 'usage', date: '2026-10-06', person: '使用员', before: '正常', after: '已清洁', notes: '使用结束后断电' })
    draft.profile.attachments.manual.push({ id: 'file', name: 'manual.txt', size: 2, type: 'text/plain', dataUrl: 'data:text/plain;base64,b2s=' })
    const saved = t.form.save(draft)
    expect(t.form.detail(saved.id)).toEqual(saved)
    expect(t.ledger.query({}).items[0]).toMatchObject({ code: 'EQ-NEW', status: '可用', manualCount: 1, purchasedAt: '' })
    expect(saved.profile.calibrations[0]?.id).not.toBe('draft')
    expect(saved.profile.projects).toEqual(draft.profile.projects)
    expect(saved.profile.usage[0]).toMatchObject({ date: '2026-10-06', person: '使用员', before: '正常', after: '已清洁', notes: '使用结束后断电' })
  })
  it('rejects duplicates, invalid dates, prices, empty records and forged projects without partial writes', () => {
    const t = setup(); t.form.save(input())
    expect(() => t.form.save(input())).toThrow('档案号已存在')
    for (const change of [{ purchasedAt: '2026-02-30' }, { price: -1 }, { name: '' }]) expect(() => t.form.save({ ...input(), code: 'OTHER', ...change })).toThrow()
    const draft = input(); draft.code = 'OTHER'; draft.profile.projects = [{ id: 'forged', code: 'x', name: 'x' }]
    expect(() => t.form.save(draft)).toThrow('所选检测方案不存在')
    draft.profile.projects = []; draft.profile.usage = [{ id: 'empty' }]
    expect(() => t.form.save(draft)).toThrow('不能全部为空')
    expect(t.state().equipmentLedger).toHaveLength(1)
  })
  it('persists every check measurement and validates the additional equipment date', () => {
    const t = setup(), draft = input()
    const measurements = Object.fromEntries(equipmentCheckMeasurements.flatMap(field => Array.from({ length: 5 }, (_, i) => [`${field.key}${i + 1}`, `${field.label}-${i + 1}`])))
    const row = { id: 'check', equipmentDate: '2026-10-06', accuracyRequirement: '±0.1', standard: '参考标准', standardDate: '2026-10-06', person: '核查员', date: '2026-10-06', project: '示值核查', conclusion: '符合要求', ...measurements }
    draft.profile.checks = [row]
    const saved = t.form.save(draft)
    expect(t.form.detail(saved.id).profile.checks[0]).toEqual({ ...row, id: saved.profile.checks[0]!.id })
    draft.code = 'BAD-CHECK-DATE'; row.equipmentDate = '2026-02-30'
    expect(() => t.form.save(draft)).toThrow('设备检定日期须为有效日期')
    expect(t.state().equipmentLedger).toHaveLength(1)
  })
  it('enforces writer roles and department access', () => {
    const t = setup(), saved = t.form.save(input())
    t.actor({ roles: ['reviewer'] }); expect(() => t.form.save({ ...input(), code: 'NEW' })).toThrow('无权')
    t.actor({ scope: 'department', departmentId: 'lab2' }); expect(() => t.form.detail(saved.id)).toThrow('无权')
    t.actor({ roles: ['quality'] }); expect(() => t.form.save(input())).toThrow('所属部门')
  })
})
