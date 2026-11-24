import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { createDataEntryService } from '../../server/dataEntryDetail'
import { demoActors } from '../../src/services/storage/demoActors'
import { parseDataChangeQuery } from '../../server/testingDataChanges'
function prepareEntry(dependencies: Parameters<typeof createDataEntryService>[0], id: string) {
  const service = createDataEntryService(dependencies, () => Date.now() - 60000)
  const mutate = (action: string, values: Record<string, unknown>) => {
    const detail = service.detail(id)
    return service.mutate(id, action, { version: detail.version, sampleVersion: detail.sample.version, requestId: crypto.randomUUID(), ...values })
  }
  mutate('save', { form: { ...service.detail(id).form, conclusion: service.detail(id).form.conclusion || '符合要求', tester1Id: 'analyst', testDates: [{ kind: 'range', from: '2026-10-01', to: '2026-10-02' }] } })
  return mutate('combine', {})
}

describe('testing data changes', () => {
  it('rejects incomplete, ungenerated and stale reports atomically even with an originals acknowledgement', async () => {
    let state = seedRegistration()
    const id = 'demo-yp-79', deps = { actor: () => demoActors[0]!, read: () => state, write: (next: typeof state) => { state = next } }
    const service = createRegistrationService(deps), entry = createDataEntryService(deps)
    const reject = async (code: string) => {
      const before = structuredClone(state)
      await expect(service.completeDataChange(id, entry.detail(id).sample.version, true)).rejects.toMatchObject({ code })
      expect(state).toEqual(before)
    }
    await reject('VALIDATION')
    prepareEntry(deps, id)
    const job = structuredClone(state.dataEntries![id]!.job!)
    delete state.dataEntries![id]!.job
    await reject('BUSINESS_RULE')
    state.dataEntries![id]!.job = job
    state.dataEntries![id]!.reportRevision++
    expect(entry.detail(id).reportStatus).toBe('stale')
    await reject('BUSINESS_RULE')
    expect(entry.detail(id).capabilities.canEdit).toBe(true)
  })
  it('uses commission-change fields and applies plan, issue and date filters before export and paging', async () => {
    const state = seedRegistration(), service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const plans = { groupIds: [], planIds: ['general-1'], excludedPlanIds: [] }
    const result = await service.dataChanges({ plans, result: '问题处理中' })
    expect(result.total).toBe(1)
    expect(result.items[0]).toMatchObject({ id: 'demo-yp-79', problemType: '检测数据更正', processingResult: '问题处理中' })
    expect(result.planSelection.count).toBe(1)
    expect((await service.dataChanges({ plans, source: '报告更改' })).total).toBe(0)
    expect((await service.dataChanges({ plans, from: '2099-01-01' })).total).toBe(0)
    expect((await service.exportDataChanges({ plans })).split('\r\n')).toHaveLength(2)
    expect((await service.exportDataChanges({ ids: ['demo-yp-80'] })).split('\r\n')).toHaveLength(2)
    expect((await service.sampleChanges()).items.every(row => row.dataStatus === '委托更改中')).toBe(true)
    const selection = await service.testPlanSelection({ groupIds: [], planIds: [], excludedPlanIds: [] }, undefined, 'data-changes')
    expect(selection.populated?.total).toBe(3)
    expect(() => parseDataChangeQuery({ plans: { planIds: 'bad' } })).toThrow()
  })
  it('edits detection data, then completes only the target change and prevents further editing', async () => {
    let state = seedRegistration()
    const dependencies = { actor: () => demoActors[0]!, read: () => state, write: (next: typeof state) => { state = next } }
    const service = createRegistrationService(dependencies), entry = createDataEntryService(dependencies)
    const id = 'demo-yp-79', detail = entry.detail(id), other = structuredClone(state.samples.find(row => row.id === 'demo-yp-80'))
    expect(detail.capabilities).toMatchObject({ canEdit: true, canComplete: false, canManageOriginals: true })
    const saved = entry.mutate(id, 'save', { version: detail.version, sampleVersion: detail.sample.version, requestId: crypto.randomUUID(), form: { ...detail.form, notes: '检测更改后的备注', conclusion: '更正后的结论' }, layoutId: detail.layoutId })
    expect(saved.sample.dataStatus).toBe('检测更改中')
    expect(saved.form.notes).toBe('检测更改后的备注')
    expect(() => entry.mutate(id, 'complete', { version: saved.version, sampleVersion: saved.sample.version, requestId: crypto.randomUUID() })).toThrow()
    await expect(service.completeDataChange(id, detail.sample.version)).rejects.toMatchObject({ code: 'VALIDATION' })
    const before = structuredClone(state)
    await expect(service.completeDataChange(id, saved.sample.version, true)).rejects.toMatchObject({ code: 'VALIDATION' })
    expect(state).toEqual(before)
    const ready = prepareEntry(dependencies, id)
    await expect(service.completeDataChange(id, ready.sample.version)).rejects.toMatchObject({ fieldErrors: { originalRecords: expect.any(String) } })
    const completed = await service.completeDataChange(id, ready.sample.version, true)
    expect(completed).toMatchObject({ dataStatus: '检测数据录入完成', dataChange: { result: '问题已处理', completedBy: { id: 'admin' } } })
    expect(completed.events.at(-1)?.action).toBe('完成检测数据更改')
    expect((await service.dataChanges()).items.some(row => row.id === id)).toBe(false)
    expect(entry.detail(id).capabilities.canEdit).toBe(false)
    expect(state.dataEntries?.[id]?.form.notes).toBe('检测更改后的备注')
    expect(state.samples.find(row => row.id === 'demo-yp-80')).toEqual(other)
    await expect(service.completeDataChange(id, completed.version)).rejects.toMatchObject({ code: 'FORBIDDEN' })
  })
  it('enforces roles, department scope and source workflow', async () => {
    const state = seedRegistration()
    for (const actorId of ['approver', 'other', 'business']) {
      const actor = demoActors.find(row => row.id === actorId)!
      const service = createRegistrationService({ actor: () => actor, read: () => state })
      await expect(service.completeDataChange('demo-yp-79', 1)).rejects.toMatchObject({ code: actorId === 'other' ? 'NOT_FOUND' : 'FORBIDDEN' })
      if (actorId === 'business') await expect(service.dataChanges()).rejects.toMatchObject({ code: 'FORBIDDEN' })
    }
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    await expect(service.completeDataChange('demo-yp-61', 1)).rejects.toMatchObject({ code: 'FORBIDDEN' })
    state.samples.find(row => row.id === 'demo-yp-79')!.status = 'voided'
    await expect(service.completeDataChange('demo-yp-79', 1)).rejects.toMatchObject({ code: 'FORBIDDEN' })
  })
  it('allows testing staff to manage change attachments and closes writes after completion', async () => {
    let state = seedRegistration(), actor = demoActors.find(row => row.id === 'analyst')!
    const dependencies = { actor: () => actor, read: () => state, write: (next: typeof state) => { state = next } }
    const service = createRegistrationService(dependencies)
    const file = { name: 'change.txt', type: 'text/plain', size: 1, dataUrl: 'data:text/plain;base64,YQ==' }
    const added = await service.attach('demo-yp-79', 1, file, 'samples')
    expect(added.canManageAttachments).toBe(true)
    actor = demoActors.find(row => row.id === 'business')!
    expect((await service.attachments(added.id, 'samples')).canManageAttachments).toBe(false)
    await expect(service.deleteAttachment(added.id, added.version, added.attachments[0]!.id, 'samples')).rejects.toThrow()
    actor = demoActors.find(row => row.id === 'analyst')!
    const ready = prepareEntry(dependencies, added.id)
    const completed = await service.completeDataChange(added.id, ready.sample.version, true)
    expect((await service.attachments(added.id, 'samples')).canManageAttachments).toBe(false)
    await expect(service.attach(added.id, completed.version, file, 'samples')).rejects.toThrow()
    expect((await service.sample(added.id)).attachments).toEqual(added.attachments)
  })
})
