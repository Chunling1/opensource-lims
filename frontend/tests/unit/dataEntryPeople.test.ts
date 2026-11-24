import { describe, expect, it } from 'vitest'
import { queryEntryPeople, entryPeople } from '../../server/dataEntryPeople'
import { createDataEntryService } from '../../server/dataEntryDetail'
import { seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'
import type { Actor } from '../../src/types/lims'

describe('data entry personnel selection', () => {
  const sample = () => seedRegistration().samples[75]!
  const admin = demoActors[0]!
  it('defaults to plan presets, falls back only when unconfigured, and filters role candidates', () => {
    expect(queryEntryPeople(sample(), admin, { role: 'tester' })).toMatchObject({ scope: 'preset', presetConfigured: true, items: [{ id: 'analyst', certificateNumber: '', phone: '' }] })
    expect(queryEntryPeople(sample(), admin, { role: 'tester', keyword: '不存在' })).toMatchObject({ scope: 'preset', total: 0 })
    expect(queryEntryPeople(sample(), admin, { role: 'reviewer' })).toMatchObject({ scope: 'department', presetConfigured: false })
    expect(queryEntryPeople(sample(), admin, { role: 'approver', scope: 'preset' })).toMatchObject({ scope: 'preset', total: 0 })
    expect(queryEntryPeople(sample(), admin, { role: 'reviewer', scope: 'preset' }, demoActors, ['reviewer', 'analyst']).items.map(row => row.id)).toEqual(['reviewer'])
    expect(entryPeople('approver').map(row => row.id)).toEqual(['admin', 'approver'])
  })
  it('uses the signed-in department, permits eligible cross-department candidates in all, and excludes duplicate testers', () => {
    expect(queryEntryPeople(sample(), { ...admin, departmentId: 'lab2' }, { role: 'tester', scope: 'department' }).items.map(row => row.id)).toEqual(['other'])
    expect(queryEntryPeople(sample(), admin, { role: 'tester', scope: 'all', keyword: 'OTHER' }).items[0]!.id).toBe('other')
    expect(queryEntryPeople(sample(), admin, { role: 'tester', scope: 'all', keyword: '第二实验室' }).total).toBe(1)
    expect(queryEntryPeople(sample(), admin, { role: 'tester', excludeId: 'analyst' }).items[0]!.disabledReason).toBeTruthy()
  })
  it('paginates deterministically and supplies staff details without inventing missing values', () => {
    const people: Actor[] = Array.from({ length: 25 }, (_, i) => ({ ...admin, id: `T${i + 1}`, name: `试验员${i + 1}`, roles: ['testing'], certificateNumber: i === 0 ? 'CERT-1' : undefined, phone: i === 0 ? '010-12345678' : undefined }))
    const first = queryEntryPeople(sample(), admin, { role: 'tester', scope: 'all', pageSize: 10 }, people)
    expect(first.total).toBe(25); expect(first.items).toHaveLength(10)
    expect(first.items[0]).toMatchObject({ certificateNumber: 'CERT-1', phone: '010-12345678' })
    expect(queryEntryPeople(sample(), admin, { role: 'tester', scope: 'all', page: 3 }, people).items).toHaveLength(5)
    expect(queryEntryPeople(sample(), admin, { role: 'tester', scope: 'all', pageSize: 20 }, people).items).toHaveLength(20)
    expect(queryEntryPeople(sample(), admin, { role: 'tester', scope: 'all', pageSize: 50 }, people).items).toHaveLength(25)
    people[0]!.active = false
    expect(entryPeople('tester', people).some(row => row.id === 'T1')).toBe(false)
  })
  it('rejects malformed scopes, roles, keyword and pagination', () => {
    for (const change of [{ role: 'admin' }, { role: ['tester'] }, { scope: ['all'] }, { scope: 'unknown' }, { keyword: 1 }, { keyword: 'x'.repeat(201) }, { page: 0 }, { page: '1' }, { pageSize: 5 }, { excludeId: [] }]) expect(() => queryEntryPeople(sample(), admin, { role: 'tester', ...change })).toThrow()
  })
  it('checks permissions on query, confirmation and save, retaining sample scope restrictions', () => {
    let state = seedRegistration(), actor = admin
    const id = 'demo-yp-76', service = createDataEntryService({ actor: () => actor, read: () => state, write: next => { state = next } })
    const before = structuredClone(state)
    expect(service.resolvePerson(id, { role: 'tester', id: 'other' }).id).toBe('other')
    expect(state).toEqual(before)
    expect(() => service.resolvePerson(id, { role: 'reviewer', id: 'analyst' })).toThrow()
    expect(() => service.resolvePerson(id, { role: 'tester', id: 'analyst', excludeId: 'analyst' })).toThrow()
    const detail = service.detail(id)
    const saved = service.mutate(id, 'save', { version: detail.version, sampleVersion: detail.sample.version, requestId: 'cross-department', form: { ...detail.form, tester1Id: 'other' } })
    expect(saved.form.tester1Id).toBe('other')
    expect(() => service.mutate(id, 'save', { version: saved.version, sampleVersion: saved.sample.version, requestId: 'bad-role', form: { ...saved.form, reviewerId: 'analyst' } })).toThrow()
    actor = demoActors.find(row => row.id === 'other')!
    expect(() => service.people(id, { role: 'tester', scope: 'all' })).toThrowError(expect.objectContaining({ code: 'NOT_FOUND' }))
    actor = demoActors.find(row => row.id === 'approver')!
    expect(() => service.resolvePerson(id, { role: 'approver', id: 'approver' })).toThrowError(expect.objectContaining({ code: 'FORBIDDEN' }))
    actor = admin; state.samples[75]!.dataStatus = '检测数据录入完成'
    expect(() => service.resolvePerson(id, { role: 'tester', id: 'analyst' })).toThrowError(expect.objectContaining({ code: 'FORBIDDEN' }))
  })
})
