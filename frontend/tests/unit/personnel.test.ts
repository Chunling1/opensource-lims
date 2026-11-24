import { describe, it, expect } from 'vitest'
import { createPersonnelService, parsePersonnelCsv } from '../../server/personnel'
import { emptyPersonnelProfile, personnelFields } from '../../src/types/quality/personnel'
import { demoActors } from '../../src/services/storage/demoActors'
import type { Actor } from '../../src/types/lims'
import type { RegistrationState } from '../../src/types/commissions/registration'
const draft = { name: '测试人员', code: '001', gender: '男', qualification: '工程师', position: '检测员', department: '实验室', school: '测试大学', major: '检测', identityNumber: '012345678901234567', graduatedAt: '2020-06-01' }
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }, actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], scope: 'all', departmentId: 'lab' }
  return { service: createPersonnelService({ actor: () => actor, read: () => state, write: next => { state = next } }), state: () => state, actor: (next: Partial<Actor>) => { actor = { ...actor, ...next } } }
}
const csv = (rows: Record<string, string>[]) => [personnelFields.map(f => f.label), ...rows.map(r => personnelFields.map(f => r[f.key] || ''))].map(row => row.map(cell => `"${cell.replaceAll('"', '""')}"`).join(',')).join('\r\n')
describe('personnel registration', () => {
  it('combines personnel inquiry filters, matches qualification exactly and exports the same scope', () => {
    const t = setup(), input = { ...draft, name: '查询人员', education: '本科', major: '材料检测', department: '第二实验室' }
    const variations = [{}, { qualification: '高级工程师' }, { education: '大专' }, { major: '化学' }, { department: '实验室' }, { name: '其他人员' }]
    variations.forEach((change, i) => t.service.save({ ...input, ...change, code: `FILTER-${i}` }))
    const filters = { name: '查询', qualification: '工程师', education: '本科', major: '材料', department: '第二' }
    expect(t.service.query(filters)).toMatchObject({ total: 1, items: [{ code: 'FILTER-0' }] })
    expect(t.service.query({ qualification: '工程师' }).total).toBe(5)
    expect(t.service.query({ education: '本科' }).total).toBe(5)
    expect(t.service.query({ department: '第二' }).total).toBe(5)
    expect(t.service.query({ ...filters, qualification: '' }).total).toBe(2)
    const csv = t.service.export(filters)
    expect(csv).toContain('FILTER-0'); expect(csv).not.toContain('FILTER-1')
    for (const key of ['qualification', 'education', 'department']) expect(() => t.service.query({ [key]: [] })).toThrow('查询条件')
  })
  it('persists the full profile and nested records, preserves omitted profile on updates and validates every attachment', () => {
    const t = setup(), profile = emptyPersonnelProfile()
    const attachment = { id: 'test-file', name: '证明.txt', type: 'text/plain', size: 3, dataUrl: 'data:text/plain;base64,YWJj' }
    Object.assign(profile, { formerName: '曾用姓名', birthAddress: '测试地址', socialSecurityNumber: '00123', degree: '自定义学位' })
    profile.attachments.education.push(attachment)
    profile.awards.push({ id: 'award', name: '优秀奖', project: '检测项目', date: '2025-10-01', issuer: '测试协会', place: '', content: '', result: '', attachments: [attachment] })
    profile.trainings.push({ id: 'training', name: '', project: '', date: '2025-11-01', issuer: '', place: '培训中心', content: '质量培训', result: '合格', attachments: [attachment] })
    const row = t.service.save({ ...draft, profile })
    expect(t.service.query({}).items[0]!.profile).toBeUndefined()
    expect(t.service.detail(row.id).profile).toMatchObject({ formerName: '曾用姓名', degree: '自定义学位', awards: [{ name: '优秀奖', attachments: [{ dataUrl: attachment.dataUrl }] }], trainings: [{ result: '合格' }] })
    const next = t.service.save({ ...draft, version: row.version }, row.id)
    expect(next.profile!.attachments.education[0]!.name).toBe('证明.txt')
    const before = structuredClone(t.state())
    for (const invalid of [ { ...profile, attachments: { ...profile.attachments, education: [{ ...attachment, size: 99 }] } }, { ...profile, awards: [{ ...profile.awards[0], date: '2025-02-30' }] }, { ...profile, trainings: [{ ...profile.trainings[0], content: '' }] }, { ...profile, attachments: { ...profile.attachments, degree: Array.from({ length: 101 }, () => attachment) } } ]) {
      expect(() => t.service.save({ ...draft, version: next.version, profile: invalid }, row.id)).toThrow()
      expect(t.state()).toEqual(before)
    }
    const changed = t.service.save({ ...draft, version: next.version, profile: emptyPersonnelProfile() }, row.id)
    expect(changed.profile!.awards).toEqual([])
    for (const key of ['gender', 'qualification', 'position']) expect(() => t.service.save({ ...draft, code: 'new', [key]: '' })).toThrow('请填写')
  })
  it('filters selectable accounts, names and certificates and revalidates selected users', () => {
    const t = setup()
    demoActors.push({ id: 'test-personnel-user', name: '人员选择测试', roles: ['testing'], departmentId: 'lab2', scope: 'department', certificateNumber: 'CERT-123', email: 'test@example.com', phone: '123', position: '检测员', jobTitle: '技术负责人' })
    try {
      const result = t.service.queryUsers({ account: 'TEST-PERSONNEL', name: '选择测试', certificateNumber: 'cert-123' })
      expect(result.total).toBe(1)
      expect(result.items[0]).toMatchObject({ email: 'test@example.com', position: '检测员', certificateNumber: 'CERT-123', jobTitle: '技术负责人' })
      expect(t.service.queryUsers({ certificateNumber: 'missing' }).total).toBe(0)
      const profile = { ...emptyPersonnelProfile(), accountId: 'test-personnel-user' }
      expect(() => t.service.save({ ...draft, profile })).toThrow('姓名')
      const saved = t.service.save({ ...draft, name: '人员选择测试', profile })
      expect(saved.profile!.accountId).toBe('test-personnel-user')
      t.actor({ roles: ['quality'], scope: 'department' })
      expect(t.service.queryUsers({ account: 'test-personnel-user' }).total).toBe(0)
      expect(() => t.service.resolveUser('test-personnel-user')).toThrow('不可选')
      t.actor({ roles: ['admin'], scope: 'all' })
      demoActors.at(-1)!.active = false
      expect(t.service.queryUsers({ account: 'test-personnel-user' }).total).toBe(0)
      expect(() => t.service.save({ ...draft, name: '人员选择测试', code: '002', profile })).toThrow('不可选')
    } finally { demoActors.pop() }
  })
  it('saves, filters, sorts, edits with version checks and deletes without altering other records', () => {
    const t = setup(), r = t.service.save(draft)
    expect(r.identityNumber).toBe(draft.identityNumber)
    expect(t.service.query({ name: '测试', code: '00', school: '大学', major: '检测' }).total).toBe(1)
    expect(t.service.query({ major: '不匹配' }).total).toBe(0)
    expect(() => t.service.save({ ...draft, code: '001' })).toThrow('已存在')
    const next = t.service.save({ ...r, major: '化学' }, r.id)
    expect(next.version).toBe(2)
    expect(t.service.save({ ...r }, r.id)).toMatchObject({ major: r.major, version: 3 })
    t.service.remove(r.id, r.version)
    expect(t.service.query({}).total).toBe(0)
    expect(() => t.service.detail(r.id)).toThrow('不存在')
    expect(t.state().samples).toEqual([])
  })
  it('enforces role and department scope for every operation', () => {
    const t = setup(), other = t.service.save({ ...draft, department: '第二实验室' })
    t.actor({ roles: ['quality'], scope: 'department' })
    expect(t.service.query({}).total).toBe(0)
    expect(t.service.export({})).not.toContain('测试人员')
    expect(() => t.service.detail(other.id)).toThrow()
    expect(() => t.service.remove(other.id, 1)).toThrow()
    expect(() => t.service.save({ ...draft, code: 'other', department: '第二实验室' })).toThrow()
    expect(() => t.service.importCsv(csv([{ ...draft, code: 'other', department: '第二实验室' }]))).toThrow()
    t.actor({ roles: ['reviewer'], scope: 'all' })
    expect(t.service.detail(other.id).name).toBe(draft.name)
    expect(() => t.service.save(draft)).toThrow('无权修改')
    t.actor({ roles: ['testing'] })
    expect(() => t.service.query({})).toThrow('无权')
    expect(() => t.service.template()).toThrow('无权')
  })
  it('imports atomically and preserves quoted text, newlines and text numbers', () => {
    const t = setup(), row = { ...draft, notes: '含逗号,及"引号"\n第二行' }
    expect(t.service.importCsv('\uFEFF' + csv([row]))).toEqual({ count: 1 })
    expect(t.service.query({}).items[0]).toMatchObject(row)
    const before = structuredClone(t.state())
    expect(() => t.service.importCsv(csv([{ ...draft, code: '002' }, { ...draft, code: '001' }]))).toThrow('第 3 行')
    expect(t.state()).toEqual(before)
    expect(() => t.service.importCsv(csv([{ ...draft, code: '002' }, { ...draft, code: '002' }]))).toThrow('重复')
    expect(() => t.service.importCsv(csv([{ ...draft, code: '002', birthDate: '2026-02-30' }]))).toThrow('出生日期')
    expect(() => t.service.importCsv(t.service.template())).toThrow('1 至 1000')
    expect(() => t.service.importCsv('姓名,编号\n张三,002')).toThrow('模板列')
    expect(() => parsePersonnelCsv('"unterminated')).toThrow('未闭合')
    expect(() => parsePersonnelCsv('"name"bad')).toThrow('引号格式')
    expect(t.state()).toEqual(before)
  })
  it('pages queries and exports all matching or selected rows with formula protection', () => {
    const t = setup()
    for (let n = 0; n < 13; n++) t.service.save({ ...draft, code: String(n).padStart(3, '0'), notes: '=SUM(1,2)' })
    const page = t.service.query({ page: 2, pageSize: 10, direction: 'desc' })
    expect(page.total).toBe(13); expect(page.items).toHaveLength(3); expect(page.items[0]!.code).toBe('002')
    expect(parsePersonnelCsv(t.service.export({ page: 2 })).length).toBe(14)
    const exported = parsePersonnelCsv(t.service.export({ ids: [page.items[0]!.id] }))
    expect(exported.length).toBe(2)
    expect(exported[1]).toContain("'=SUM(1,2)")
    expect(parsePersonnelCsv(t.service.template())[0]).toEqual(personnelFields.map(f => f.label))
    expect(() => t.service.query({ page: -1 })).toThrow()
    expect(() => t.service.query({ sort: 'missing' })).toThrow()
  })
})
