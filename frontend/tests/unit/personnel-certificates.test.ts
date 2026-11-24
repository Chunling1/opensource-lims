import { describe, it, expect } from 'vitest'
import { createPersonnelCertificates, seedPersonnelCertificates } from '../../server/personnelCertificates'
import { createPersonnelService } from '../../server/personnel'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'

function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }
  let actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], scope: 'all', departmentId: 'lab' }
  seedPersonnelCertificates(state)
  const deps = { actor: () => actor, read: () => state, write: (next: RegistrationState) => { state = next } }
  return { api: createPersonnelCertificates(deps), personnel: createPersonnelService(deps), state: () => state, actor: (next: Partial<Actor>) => { actor = { ...actor, ...next } } }
}
const first = 'demo-person-1-certificate-1', second = 'demo-person-2-certificate-1'
const fields = { code: 'NEW', item: '新增项目', category: '材料', notes: '' }
describe('personnel certificate backend', () => {
  it('queries independent scopes, filters, pages and scoped exports using live personnel', () => {
    const t = setup(), api = t.api
    expect(api.query('people', {}).total).toBe(12)
    expect(api.query('certificates', {}).total).toBe(0)
    expect(api.query('certificates', { scope: 'all', page: 2, pageSize: 10 })).toMatchObject({ total: 72, page: 2, items: expect.any(Array) })
    expect(api.query('certificates', { parentIds: ['demo-person-1', 'demo-person-2'] }).total).toBe(12)
    expect(api.query('projects', { parentIds: [first, second], filters: { code: 'p1' } }).total).toBe(2)
    const csv = api.export('certificates', { parentIds: ['demo-person-1'], columns: ['name', 'number'] })
    expect(csv).toContain('DEMO-C001-6'); expect(csv).not.toContain('DEMO-C002')
    expect(() => api.export('people', { columns: ['__proto__'] })).toThrow()
    const p = t.personnel.detail('demo-person-1'); t.personnel.save({ ...p, name: '更名人员' }, p.id)
    expect(api.certificate(first).name).toBe('更名人员')
    expect(api.project(`${first}-project-1`).name).toBe('更名人员')
    expect(api.query('certificates', { scope: 'all', filters: { name: '更名' } }).total).toBe(6)
  })
  it('creates batches atomically, checks versions and deletes only the intended tree', () => {
    const t = setup(), api = t.api, before = api.certificate(first)
    expect(() => api.saveProjects({ ...fields, certificateIds: [first, 'missing'] })).toThrow()
    expect(api.query('projects', { scope: 'all' }).total).toBe(432)
    expect(api.saveProjects({ ...fields, certificateIds: [first, second] }).count).toBe(2)
    const snapshot = structuredClone(t.state())
    expect(() => api.saveProjects({ ...fields, certificateIds: ['demo-person-3-certificate-1', first] })).toThrow('已存在')
    expect(t.state()).toEqual(snapshot)
    expect(() => api.remove('certificates', first, before)).toThrow('变化')
    const projects = api.query('projects', { scope: 'all', filters: { code: 'NEW' } }).items
    api.saveProjects({ ...fields, item: '只改一个', version: 1 }, projects[0]!.id)
    expect(api.project(projects[1]!.id).item).toBe('新增项目')
    expect(() => api.saveProjects({ ...fields, version: 1 }, projects[0]!.id)).not.toThrow()
    api.remove('projects', projects[0]!.id, { version: 2 })
    const latest = api.certificate(first)
    api.remove('certificates', first, latest)
    expect(api.query('projects', { parentIds: [first] }).total).toBe(0)
    expect(api.query('projects', { parentIds: [second] }).total).toBe(7)
    expect(() => api.certificate(first)).toThrow('不存在')
  })
  it('validates attachments, duplicate numbers and permissions without partial writes', () => {
    const t = setup(), api = t.api
    const input = { personId: 'demo-person-1', category: '材料', number: 'NEW-C', notes: '', files: [{ id: 'file', name: 'a.txt', type: 'text/plain', size: 3, dataUrl: 'data:text/plain;base64,YWJj' }] }
    const saved = api.saveCertificate(input)
    expect(saved.files[0]!.dataUrl).toBe('')
    expect(api.certificate(saved.id).files[0]!.dataUrl).toContain('YWJj')
    expect(() => api.saveCertificate(input)).toThrow('已存在')
    expect(() => api.saveCertificate({ ...input, number: 'BAD', files: [{ ...input.files[0], size: 4 }] })).toThrow('大小')
    expect(api.query('certificates', { scope: 'all' }).total).toBe(73)
    t.actor({ roles: ['quality'], scope: 'department' })
    expect(api.query('people', {}).total).toBe(6)
    expect(() => api.certificate(second)).toThrow()
    expect(() => api.saveProjects({ ...fields, certificateIds: [first, second] })).toThrow()
    expect(api.query('projects', { parentIds: [first], filters: { code: 'NEW' } }).total).toBe(0)
    t.actor({ roles: ['reviewer'] })
    expect(() => api.saveCertificate(input)).toThrow('无权')
    t.actor({ roles: ['testing'] })
    expect(() => api.query('people', {})).toThrow('无权')
  })
})
