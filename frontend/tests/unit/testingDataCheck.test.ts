import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { parseDataCheckQuery } from '../../server/testingDataCheck'
import { demoActors } from '../../src/services/storage/demoActors'
import { entryCapabilities } from '../../server/dataEntryDetail'

function setup() {
  let state = seedRegistration(), actor = demoActors[0]!
  const service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { state = next } })
  return { service, get state() { return state }, setActor(id: string) { actor = demoActors.find(row => row.id === id)! } }
}
describe('testing data check', () => {
  it('filters check dates inclusively before pagination and export, independently of commission dates', async () => {
    const context = setup(), { service } = context, source = context.state.samples[76]!
    context.state.samples = Array.from({ length: 15 }, (_, index) => ({ ...structuredClone(source), id: `date-${index}`, code: `DATE${index}`, workflow: { ...source.workflow, checkDate: index < 12 ? '2026-10-01' : index === 12 ? '2026-10-02' : undefined } }))
    const query = { dateField: 'checkDate', from: '2026-10-01', to: '2026-10-01', page: 2, pageSize: 10 } as const
    expect(parseDataCheckQuery(query).dateField).toBe('checkDate')
    expect(await service.dataCheckSamples(query)).toMatchObject({ total: 12, page: 2 })
    expect((await service.dataCheckSamples(query)).items).toHaveLength(2)
    expect((await service.exportDataCheckSamples(query)).split('\r\n')).toHaveLength(13)
    expect((await service.dataCheckSamples({ dateField: 'checkDate', from: '2026-10-02' })).total).toBe(1)
    expect((await service.dataCheckSamples({ dateField: 'checkDate', to: '2026-10-01' })).total).toBe(12)
    expect((await service.dataCheckSamples({ dateField: 'checkDate' })).total).toBe(15)
    expect(() => parseDataCheckQuery({ ...query, from: '2026-10-02' })).toThrow()
  })
  it('returns failed checks to editable entry without losing data and prevents stale or repeated decisions', async () => {
    for (const status of ['检测数据录入完成', '检测数据校核中']) {
      const context = setup(), { service } = context, sample = context.state.samples[76]!
      sample.dataStatus = status
      const before = structuredClone(sample)
      expect(context.state.samples[76]).toEqual(before)
      context.setActor('approver')
      await expect(service.dataCheckAction(sample.id, 'reject', sample.version)).rejects.toMatchObject({ code: 'FORBIDDEN' })
      context.setActor('admin')
      const returned = await service.dataCheckAction(sample.id, 'reject', 999)
      expect(returned.dataStatus).toBe('检测数据录入中')
      expect(returned.dataCheckInfo).toBeUndefined()
      expect(returned.workflow?.checkDate).toBeUndefined()
      expect(returned.dataEntryInfo).toEqual(before.dataEntryInfo)
      expect(returned.attachments).toEqual(before.attachments)
      expect(returned.events.at(-1)).toMatchObject({ action: '数据校核不通过', actor: '演示用户', reason: '退回检测数据录入' })
      expect(entryCapabilities(demoActors[0]!, returned)).toMatchObject({ canEdit: true, canCheck: false })
      expect((await service.dataCheckSamples()).total).toBe(0)
      expect((await service.dataEntrySamples({ status: '检测数据录入中', contains: returned.code })).total).toBe(1)
      await expect(service.dataCheckAction(sample.id, 'reject', returned.version)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
      await expect(service.dataCheckAction(sample.id, 'check', returned.version)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    }
  })
  it('checks completed entries, records the actual actor, and reverses without losing test data', async () => {
    const context = setup(), { service } = context
    const before = structuredClone(context.state.samples[76]!)
    expect(entryCapabilities(demoActors[0]!, before)).toMatchObject({ canEdit: false, canCheck: true })
    const row = (await service.dataCheckSamples({ status: '检测数据校核中' })).items[0]!
    expect(row).toMatchObject({ id: before.id, checker: '', checkDate: '', canCheck: true, canUndoCheck: false })
    expect(context.state.samples[76]).toEqual(before)
    expect(context.state.samples[76]).toEqual(before)
    const checked = await service.dataCheckAction(row.id, 'check', 999)
    expect(checked).toMatchObject({ dataStatus: '检测数据校核完成', dataCheckInfo: { actorId: 'admin', actorName: '演示用户' } })
    expect(checked.workflow?.checkDate).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(entryCapabilities(demoActors[0]!, checked).canCheck).toBe(false)
    expect((await service.dataCheckSamples({ status: '检测数据校核中' })).total).toBe(0)
    expect((await service.dataCheckSamples({ status: '检测数据校核完成' })).items[0]).toMatchObject({ checker: '演示用户', canCheck: false, canUndoCheck: true })
    await expect(service.dataCheckAction(row.id, 'check', checked.version)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    const undone = await service.dataCheckAction(row.id, 'undo', checked.version)
    expect(undone.dataStatus).toBe(before.dataStatus)
    expect(undone.dataCheckInfo).toBeUndefined()
    expect(undone.workflow).toEqual(before.workflow)
    expect(undone.dataEntryInfo).toEqual(before.dataEntryInfo)
    expect(undone.events.slice(-2).map(event => event.action)).toEqual(['数据校核', '撤销校核'])
  })
  it('rejects invalid stages, roles, department access and downstream reversals', async () => {
    const context = setup(), { service } = context, sample = context.state.samples[76]!
    await expect(service.dataCheckAction(context.state.samples[75]!.id, 'check', 1)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    context.setActor('approver')
    expect(entryCapabilities(demoActors.find(actor => actor.id === 'approver')!, sample).canCheck).toBe(false)
    expect((await service.dataCheckSamples()).items[0]).toMatchObject({ canCheck: false, canUndoCheck: false })
    await expect(service.dataCheckAction(sample.id, 'check', 1)).rejects.toMatchObject({ code: 'FORBIDDEN' })
    context.setActor('other')
    expect((await service.dataCheckSamples()).total).toBe(0)
    expect(await service.exportDataCheckSamples()).not.toContain(sample.code)
    await expect(service.dataCheckAction(sample.id, 'check', 1)).rejects.toMatchObject({ code: 'NOT_FOUND' })
    context.setActor('business')
    await expect(service.dataCheckSamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
    context.setActor('admin')
    const checked = await service.dataCheckAction(sample.id, 'check', 1)
    context.state.samples[76]!.workflow!.auditDate = '2026-10-01'
    await expect(service.dataCheckAction(sample.id, 'undo', checked.version)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    context.state.samples[76]!.status = 'void_pending'
    expect((await service.dataCheckSamples()).total).toBe(0)
  })
  it('filters, paginates and exports scoped data with screenshot columns', async () => {
    const context = setup(), { service } = context, source = context.state.samples[76]!
    context.state.samples = Array.from({ length: 23 }, (_, index) => ({ ...structuredClone(source), id: `check-${index}`, code: `CHECK${String(index).padStart(2, '0')}` }))
    expect((await service.dataCheckSamples({ page: 3, pageSize: 10 })).items).toHaveLength(3)
    expect((await service.dataCheckSamples({ searchField: 'code', contains: 'CHECK03' })).total).toBe(1)
    expect((await service.dataCheckSamples({ plans: { groupIds: [], planIds: ['thermal-1'], excludedPlanIds: [] } })).total).toBe(0)
    expect((await service.dataCheckSamples({ dateField: 'testStartDate', from: '2000-01-01', to: '2000-12-31' })).total).toBe(0)
    expect((await service.testPlanSelection({ groupIds: ['general'], planIds: [], excludedPlanIds: [] }, undefined, 'data-check')).populated?.total).toBeGreaterThan(0)
    const csv = await service.exportDataCheckSamples({ ids: ['check-3'] })
    expect(csv).toContain('CHECK03'); expect(csv).not.toContain('CHECK04')
    expect(csv.split('\r\n')[0]).toContain('"检测方案","校核人","校核日期","附件","结论状态"')
    expect(csv.split('\r\n')[0]).toContain('"试验人1","试验人2","试验开始日期","试验结束日期","委托日期"')
    expect((await service.exportDataCheckSamples({ page: 3 })).split('\r\n')).toHaveLength(24)
    for (const input of [{ status: '检测数据录入中' }, { dateField: 'unknown' }, { from: '2026-02-30' }]) expect(() => parseDataCheckQuery(input)).toThrow()
  })
})
