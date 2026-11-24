import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'
import { emptyTrialForm } from '../../src/types/testing/dataEntryDetail'
import { dataQueryColumns } from '../../src/types/testing/dataQuery'
import { parseDataQueryQuery } from '../../server/testingDataQuery'

describe('testing data inquiry', () => {
  it('returns saved conclusions instead of conclusion status and filters before pagination/export', async () => {
    const state = seedRegistration(), source = state.samples[75]!
    state.samples = Array.from({ length: 13 }, (_, index) => ({ ...structuredClone(source), id: `query-${index}`, code: `QUERY${String(index).padStart(2, '0')}`, dataStatus: index === 12 ? '报告批准完成' : '检测数据录入完成', workflow: { ...source.workflow, checkDate: '2026-10-01' }, dataCheckInfo: { actorId: 'admin', actorName: '校核人甲', previousDataStatus: '检测数据录入完成', at: '2026-10-01' } }))
    state.dataEntries = Object.fromEntries(state.samples.map((sample, index) => [sample.id, { version: 1, reportRevision: 1, form: { ...emptyTrialForm(), conclusionStatus: index < 12 ? '不合格' : '合格', conclusion: `完整检测结论-${index}`, failedParameters: index < 12 ? '压力；温度' : '' }, files: [], requests: [], events: [] }]))
    const before = structuredClone(state)
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const result = await service.dataQuerySamples({ conclusion: '不合格', page: 2, pageSize: 10 })
    expect(result).toMatchObject({ total: 12, page: 2 })
    expect(result.items).toHaveLength(2)
    expect(result.items[0]).toMatchObject({ conclusion: '完整检测结论-10', failedParameters: '压力；温度', checkDate: '2026-10-01', checker: '校核人甲', pendingStatus: '检测数据校核中', canView: true })
    const approved = await service.dataQuerySamples({ status: '报告批准完成' })
    expect(approved.items[0]).toMatchObject({ conclusion: '完整检测结论-12', pendingStatus: '报告打印中', canPrintTask: true })
    expect(await service.taskPrintSource(approved.items[0]!.id)).toMatchObject({ canPrint: true })
    const csv = await service.exportDataQuerySamples({ conclusion: '不合格', page: 2, pageSize: 10 })
    expect(csv.split('\r\n')).toHaveLength(13)
    expect(csv.split('\r\n')[0]!.split(',')).toHaveLength(22)
    expect(csv).toContain('完整检测结论-0'); expect(csv).not.toContain('完整检测结论-12')
    const selected = await service.exportDataQuerySamples({ ids: ['query-12'] })
    expect(selected.split('\r\n')).toHaveLength(2)
    expect(selected).toContain('完整检测结论-12')
    expect(dataQueryColumns.find(column => column.key === 'conclusion')?.label).toBe('检测结果')
    expect(state).toEqual(before)
  })
  it('keeps scope, plan filtering, date filters and access checks on the server', async () => {
    const state = seedRegistration(), analyst = demoActors.find(actor => actor.id === 'analyst')!
    const service = createRegistrationService({ actor: () => analyst, read: () => state })
    const result = await service.dataQuerySamples({ pageSize: 50 })
    expect(result.items.every(row => state.samples.find(sample => sample.id === row.id)?.departmentId === analyst.departmentId)).toBe(true)
    const source = state.samples[75]!
    expect((await service.dataQuerySamples({ ids: [source.id], plans: { groupIds: [], planIds: ['pressure-1'], excludedPlanIds: [] } })).total).toBe(0)
    expect((await service.dataQuerySamples({ contains: source.code, dateField: 'commissionDate', from: '2099-01-01' })).total).toBe(0)
    const forbidden = createRegistrationService({ actor: () => demoActors.find(actor => actor.id === 'finance')!, read: () => state })
    await expect(forbidden.dataQuerySamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
    await expect(forbidden.exportDataQuerySamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
    expect(() => parseDataQueryQuery({ dateField: 'unknown' })).toThrow()
    expect(() => parseDataQueryQuery({ status: 'unknown' })).toThrow()
  })
})
