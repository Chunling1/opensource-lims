import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { parseSampleCompletionQuery } from '../../server/testingSampleCompletion'
import { sampleCompletionColumns } from '../../src/types/testing/sampleCompletion'
import { demoActors } from '../../src/services/storage/demoActors'

describe('completed sample handling list', () => {
  it('saves handling, exports its result and reverses it without changing physical disposal facts', async () => {
    let state = seedRegistration()
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state, write: next => { state = next } })
    const sample = state.samples.find(row => row.id === 'demo-yp-29')!, disposal = structuredClone(sample.disposalInfo)
    const saved = await service.sampleCompletionAction(sample.id, 'process', sample.version, '  已检毕，留样待处置  ')
    expect(saved.version).toBe(sample.version + 1)
    expect(saved.sampleCompletionInfo).toMatchObject({ status: '样品已处理', receipt: { result: '已检毕，留样待处置', retentionTime: disposal!.retentionTime, processedBy: { id: 'admin' } } })
    expect(saved.sampleCompletionInfo!.processedAt).toBeTruthy()
    expect(saved.disposalInfo).toEqual(disposal)
    expect(saved.dataStatus).toBe(sample.dataStatus)
    expect(saved.events.at(-1)?.action).toBe('样品处理')
    const row = (await service.sampleCompletionSamples({ code: sample.code })).items[0]!
    expect(row).toMatchObject({ disposalResult: '已检毕，留样待处置', canProcess: false, canUndoProcess: true })
    expect(await service.exportSampleCompletionSamples({ code: sample.code })).toContain('已检毕，留样待处置')
    await expect(service.sampleCompletionAction(sample.id, 'process', saved.version, '重复')).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    const undone = await service.sampleCompletionAction(sample.id, 'undo', sample.version)
    expect(undone.sampleCompletionInfo).toMatchObject({ status: '样品待处理', history: [saved.sampleCompletionInfo!.receipt] })
    expect(undone.sampleCompletionInfo!.processedAt).toBeUndefined()
    expect(undone.sampleCompletionInfo!.receipt).toBeUndefined()
    expect(undone.disposalInfo).toEqual(disposal)
    expect((await service.sampleCompletionSamples({ code: sample.code })).items[0]).toMatchObject({ processingTime: '', canProcess: true, canUndoProcess: false })
    await expect(service.sampleCompletionAction(sample.id, 'undo', undone.version)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
  })
  it('validates handling results, versions, eligibility and write permissions without partial updates', async () => {
    let state = seedRegistration(), current = demoActors[0]!
    const service = createRegistrationService({ actor: () => current, read: () => state, write: next => { state = next } })
    const sample = state.samples.find(row => row.id === 'demo-yp-29')!, before = structuredClone(state)
    for (const result of ['', '   ', '长'.repeat(501), undefined, { result: '错误类型' }]) {
      await expect(service.sampleCompletionAction(sample.id, 'process', sample.version, result)).rejects.toMatchObject({ code: 'VALIDATION', fieldErrors: { result: expect.any(String) } })
    }
    await expect(service.sampleCompletionAction(sample.id, 'process', 0, '完成')).rejects.toMatchObject({ code: 'BAD_REQUEST' })
    for (const id of ['business', 'approver', 'other']) {
      current = demoActors.find(actor => actor.id === id)!
      await expect(service.sampleCompletionAction(sample.id, 'process', sample.version, '完成')).rejects.toMatchObject({ code: id === 'other' ? 'NOT_FOUND' : 'FORBIDDEN' })
    }
    expect(state).toEqual(before)
    current = demoActors[0]!
    sample.status = 'voided'
    await expect(service.sampleCompletionAction(sample.id, 'process', sample.version, '完成')).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
  })
  it('keeps handling and disposal states independent and exports exactly the filtered rows', async () => {
    const state = seedRegistration(), service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const all = await service.sampleCompletionSamples()
    expect(all.total).toBe(10)
    expect(sampleCompletionColumns.map(column => column.label)).toEqual(['样品编号', '处理状态', '检测方案', '样品/工程名称', '入库人', '入库时间', '出库人', '出库时间', '领样人', '领样时间', '留置时间', '客户处置要求', '处置结果', '处置时间', '处置人', '处置状态'])
    const pending = await service.sampleCompletionSamples({ processingStatus: '样品待处理', disposalStatus: '样品已处置', from: 'invalid' })
    expect(pending.total).toBe(3)
    expect(pending.items.every(row => row.canProcess && !row.canUndoProcess)).toBe(true)
    const handled = await service.sampleCompletionSamples({ processingStatus: '样品已处理', disposalStatus: '样品待处置' })
    expect(handled.total).toBe(2)
    expect(handled.items.every(row => row.canUndoProcess && row.disposalStatus === '样品待处置')).toBe(true)
    const query = { processingStatus: '样品已处理', disposalStatus: '样品已处置', from: '2000-01-01', to: '2100-01-01' }
    const disposed = await service.sampleCompletionSamples(query)
    expect(disposed.total).toBe(5)
    expect((await service.exportSampleCompletionSamples(query)).split('\r\n')).toHaveLength(disposed.total + 1)
    expect((await service.exportSampleCompletionSamples({ ...query, ids: [disposed.items[0]!.id] })).split('\r\n')).toHaveLength(2)
    expect((await service.sampleCompletionSamples({ ...query, from: '2099-01-01' })).total).toBe(0)
  })
  it('uses saved facts, plans and codes without fabricating dates or signatures', async () => {
    const state = seedRegistration(), sample = state.samples.find(row => row.id === 'demo-yp-29')!
    sample.inboundInfo = undefined; sample.outboundInfo = undefined; sample.flowInfo = undefined
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const result = await service.sampleCompletionSamples({ code: '0029', plans: { planIds: ['general-1'], groupIds: [], excludedPlanIds: [] } })
    expect(result.total).toBe(1)
    expect(result.items[0]).toMatchObject({ id: sample.id, testPlanName: sample.details!.testPlan, inboundDate: '', outboundDate: '', collectionDate: '', customerSignature: '' })
    expect((await service.sampleCompletionSamples({ code: '0029', plans: { planIds: ['pressure-1'], groupIds: [], excludedPlanIds: [] } })).total).toBe(0)
    sample.status = 'voided'
    expect((await service.sampleCompletionSamples({ code: '0029' })).total).toBe(0)
  })
  it('validates filters and enforces read permissions and department scope', async () => {
    expect(() => parseSampleCompletionQuery({ processingStatus: '不支持' })).toThrow()
    expect(() => parseSampleCompletionQuery({ disposalStatus: '不支持' })).toThrow()
    expect(() => parseSampleCompletionQuery({ processingStatus: '样品已处理', from: '2026-02-30' })).toThrow(/处理时间/)
    expect(() => parseSampleCompletionQuery({ page: -1 })).toThrow()
    const state = seedRegistration()
    for (const id of ['business', 'other', 'approver']) {
      const actor = demoActors.find(actor => actor.id === id)!, service = createRegistrationService({ actor: () => actor, read: () => state })
      if (id === 'business') {
        await expect(service.sampleCompletionSamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
        await expect(service.exportSampleCompletionSamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
      } else {
        const result = await service.sampleCompletionSamples()
        if (id === 'other') expect(result.items.every(row => state.samples.find(sample => sample.id === row.id)?.departmentId === actor.departmentId)).toBe(true)
        else expect(result.items.every(row => !row.canProcess && !row.canUndoProcess)).toBe(true)
      }
    }
  })
  it('filters by handling time independently of disposal time and excludes missing handling dates', async () => {
    const state = seedRegistration(), sample = state.samples.find(row => row.id === 'demo-yp-30')!
    sample.sampleCompletionInfo = { status: '样品已处理', processedAt: '2026-04-10T10:00:00+08:00' }
    sample.disposalInfo!.receipt!.date = '2026-05-20'
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const query = { code: sample.code, processingStatus: '样品已处理', from: '2026-04-10', to: '2026-04-10' }
    expect((await service.sampleCompletionSamples(query)).total).toBe(1)
    expect((await service.exportSampleCompletionSamples(query)).split('\r\n')).toHaveLength(2)
    expect((await service.sampleCompletionSamples({ ...query, from: '2026-05-20', to: '2026-05-20' })).total).toBe(0)
    delete sample.sampleCompletionInfo.processedAt
    expect((await service.sampleCompletionSamples(query)).total).toBe(0)
  })
})
