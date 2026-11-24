import { describe, expect, it } from 'vitest'
import { createDataEntryService } from '../../server/dataEntryDetail'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'

function setup() {
  let state = seedRegistration(), actor = demoActors[0]!
  const deps = { actor: () => actor, read: () => state, write: (next: typeof state) => { state = next } }
  const entry = createDataEntryService(deps), registration = createRegistrationService(deps), id = 'demo-yp-76'
  function save(conclusion: string, requestId = crypto.randomUUID()) { const detail = entry.detail(id); return entry.mutate(id, 'save', { form: { ...detail.form, conclusion }, version: detail.version, sampleVersion: detail.sample.version, requestId }) }
  return { entry, registration, id, save, state: () => state, actor: (id: string) => { actor = demoActors.find(row => row.id === id)! } }
}
describe('data entry supporting records', () => {
  it('stores field values per successful save, preserves old snapshots and skips unchanged saves', () => {
    const t = setup(); t.save('第一版'); t.save('第二版'); t.save('第二版')
    const records = t.entry.records(t.id, { kind: 'testing' })
    expect(records.items).toHaveLength(2)
    expect(records.items[0]).toMatchObject({ field: '结论', before: '第一版', after: '第二版', sequence: 2, type: '保存试验信息' })
    expect(records.items[1]).toMatchObject({ before: '', after: '第一版', sequence: 1 })
    const detail = t.entry.detail(t.id)
    expect(() => t.entry.mutate(t.id, 'save', { version: 0, sampleVersion: detail.sample.version, requestId: crypto.randomUUID(), form: detail.form })).not.toThrow()
    expect(t.entry.records(t.id, { kind: 'testing' }).total).toBe(2)
  })
  it('reads actual issues, leaving absent handling values empty and protecting department scope', () => {
    const t = setup(), sample = t.state().samples.find(row => row.id === t.id)!
    sample.taskReturns = [{ type: 'assignment', reason: '人员错误', details: '请重新分配', date: '2026-09-28', recordedAt: '2026-09-28T12:00:00Z', recordedBy: { id: 'analyst', name: '李检测' }, previousDataStatus: '检测数据录入中' }]
    expect(t.entry.records(t.id, { kind: 'issues' }).items[0]).toMatchObject({ submitterId: 'analyst', description: '人员错误；请重新分配', handler: '', opinion: '', sequence: 1 })
    t.actor('analyst2'); expect(() => t.entry.records(t.id, { kind: 'issues' })).toThrow()
  })
  it('paginates records and rejects invalid queries without fabricating legacy before/after values', () => {
    const t = setup(), sample = t.state().samples.find(row => row.id === t.id)!
    sample.events.push({ at: '2026-09-20', actor: '李受理', action: '修改样品', reason: '' })
    expect(t.entry.records(t.id, { kind: 'commission' }).items[0]).toMatchObject({ before: '', after: '' })
    for (let index = 0; index < 12; index++) t.save(`结论${index}`)
    expect(t.entry.records(t.id, { kind: 'testing', page: 2, pageSize: 10 }).items).toHaveLength(2)
    expect(() => t.entry.records(t.id, { kind: 'missing' })).toThrow()
    expect(() => t.entry.records(t.id, { kind: 'testing', page: -1 })).toThrow()
  })
  it('records sample edits and bulk commission edits with exact old and new values', async () => {
    const t = setup(), sample = t.state().samples.find(row => row.id === 'demo-yp-1')!
    const { id, version, ...input } = structuredClone(sample)
    await t.registration.saveSample({ ...input, name: '修改后的样品名称', details: sample.details }, id, version)
    expect(t.entry.records(id, { kind: 'commission' }).items).toEqual(expect.arrayContaining([expect.objectContaining({ field: '名称', before: sample.name, after: '修改后的样品名称' })]))
    const saved = t.state().samples.find(row => row.id === id)!
    await t.registration.saveBulkCommission([{ id, version: saved.version }], { customer: '新委托单位' })
    expect(t.entry.records(id, { kind: 'commission' }).items).toEqual(expect.arrayContaining([expect.objectContaining({ field: '委托信息 / 委托单位', before: sample.customer, after: '新委托单位' })]))
  })
})
