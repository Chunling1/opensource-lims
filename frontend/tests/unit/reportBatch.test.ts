import { afterEach, describe, expect, it, vi } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { createReviewChecks } from '../../server/reviewChecks'
import { demoActors } from '../../src/services/storage/demoActors'
import { reportStages, type ReportStage } from '../../src/types/reports/reportCheck'

const stages = [
  { stage: 'check', ids: ['demo-yp-82', 'demo-yp-84'] },
  { stage: 'review', ids: ['demo-yp-85', 'demo-yp-87'] },
  { stage: 'approval', ids: ['demo-yp-88', 'demo-yp-90'] },
] as const
function setup(delay = 0) {
  let state = seedRegistration(), actor = demoActors[0]!
  const service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { state = next } }, createReviewChecks(delay))
  const targets = (ids: readonly string[]) => ids.map(id => ({ id, version: state.samples.find(sample => sample.id === id)!.version }))
  return { service, targets, state: () => state, actor: (id: string) => { actor = demoActors.find(actor => actor.id === id)! } }
}
const proofIds = (items: { sampleId: string; id: string }[]) => items.map(item => ({ sampleId: item.sampleId, checkId: item.id }))
afterEach(() => vi.useRealTimers())
describe('report batch actions', () => {
  it.each(stages)('$stage checks each sample, transfers and completes atomically using stage-specific facts', async ({ stage, ids }) => {
    const t = setup(), config = reportStages[stage], before = structuredClone(t.state())
    const context = await t.service.reportBatchContext([...ids], stage)
    expect(context.map(sample => sample.id)).toEqual(ids)
    const checked = await t.service.reportBatchCheck(t.targets(ids), stage)
    expect(t.state()).toEqual(before)
    expect(checked.items.map(item => item.sampleId)).toEqual(ids)
    const transferred = await t.service.reportBatchSubmit(t.targets(ids), 'check', { readConfirmed: true, nextAction: 'transfer', recipientId: config.role }, proofIds(checked.items), undefined, stage)
    expect(transferred.every(sample => sample.dataStatus === config.pending && sample[config.infoKey]?.recipient?.id === config.role)).toBe(true)
    const latest = await t.service.reportBatchCheck(t.targets(ids), stage)
    const completed = await t.service.reportBatchSubmit(t.targets(ids), 'check', { readConfirmed: true, nextAction: 'next' }, proofIds(latest.items), undefined, stage)
    for (const sample of completed) {
      expect(sample.dataStatus).toBe(config.completed)
      expect(sample[config.infoKey]?.reviewConfirmation?.result.sampleId).toBe(sample.id)
      if (stage !== 'check') expect(sample.reportCheckInfo).toEqual(before.samples.find(item => item.id === sample.id)!.reportCheckInfo)
    }
  })
  it.each(stages)('$stage rejects all samples with separate issues and allows an empty reason', async ({ stage, ids }) => {
    const t = setup(), rejected = await t.service.reportBatchSubmit(t.targets(ids), 'reject', undefined, [], { problemType: '其他问题', destination: 'testing', reason: '', handler: '', opinion: '更正后重提' }, stage)
    expect(rejected.every(sample => sample.dataStatus === '检测更改中' && sample.reportCheckIssues?.at(-1)?.stage === stage)).toBe(true)
    expect(new Set(rejected.map(sample => sample.dataChange?.reportIssueId)).size).toBe(ids.length)
  })
  it('never partially commits when proofs, selection, version, actor, stage or recipient are invalid', async () => {
    const t = setup(), ids = stages[0].ids, targets = t.targets(ids)
    const first = await t.service.reportBatchCheck(targets, 'check')
    const latest = await t.service.reportBatchCheck(targets, 'check')
    const before = structuredClone(t.state()), confirmation = { readConfirmed: true, nextAction: 'next' }
    for (const checks of [proofIds(first.items), proofIds(latest.items).slice(0, 1), proofIds(latest.items).map((item, i, all) => ({ ...item, checkId: all[1 - i]!.checkId }))]) {
      await expect(t.service.reportBatchSubmit(targets, 'check', confirmation, checks, undefined)).rejects.toMatchObject({ code: 'VALIDATION' })
      expect(t.state()).toEqual(before)
    }
    await expect(t.service.reportBatchSubmit(targets.slice(0, 1), 'check', confirmation, proofIds(latest.items).slice(0, 1), undefined)).rejects.toMatchObject({ code: 'VALIDATION' })
    await expect(t.service.reportBatchSubmit(targets, 'check', { ...confirmation, readConfirmed: false }, proofIds(latest.items), undefined)).rejects.toMatchObject({ code: 'VALIDATION' })
    await expect(t.service.reportBatchSubmit(targets, 'check', { ...confirmation, nextAction: 'transfer', recipientId: 'analyst' }, proofIds(latest.items), undefined)).rejects.toMatchObject({ code: 'VALIDATION' })
    const single = await t.service.reportComplianceCheck(targets[0]!.id, targets[0]!.version)
    await expect(t.service.reportBatchSubmit(targets, 'check', confirmation, [{ sampleId: single.sampleId, checkId: single.id }, proofIds(latest.items)[1]], undefined)).rejects.toMatchObject({ code: 'VALIDATION' })
    await expect(t.service.reportBatchCheck(targets, 'review')).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    t.actor('reviewer')
    await expect(t.service.reportBatchSubmit(targets.slice(0, 1), 'check', confirmation, proofIds(latest.items).slice(0, 1), undefined)).rejects.toMatchObject({ code: 'VALIDATION' })
    await expect(t.service.reportBatchCheck(t.targets(stages[2].ids), 'approval')).rejects.toMatchObject({ code: 'FORBIDDEN' })
    t.actor('admin')
    expect(t.state()).toEqual(before)
    t.state().samples.find(sample => sample.id === ids[1])!.version++
    await expect(t.service.reportBatchSubmit(targets, 'check', confirmation, proofIds(latest.items), undefined)).resolves.toHaveLength(targets.length)
    await expect(t.service.reportBatchContext([...ids])).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
  })
  it('validates bounds, duplicates, visibility and invalidates asynchronous stale checks', async () => {
    const t = setup(1500), targets = t.targets(stages[0].ids)
    for (const input of [[], [targets[0], targets[0]], [{ id: targets[0]!.id, version: '1' }], Array.from({ length: 51 }, (_, i) => ({ id: String(i), version: 1 }))]) await expect(t.service.reportBatchCheck(input)).rejects.toMatchObject({ code: 'BAD_REQUEST' })
    await expect(t.service.reportBatchContext(['missing'])).rejects.toMatchObject({ code: 'NOT_FOUND' })
    vi.useFakeTimers()
    const overlap = Promise.allSettled([t.service.reportBatchCheck(targets), t.service.reportBatchCheck(targets)])
    await vi.runAllTimersAsync()
    expect((await overlap).map(result => result.status)).toEqual(['rejected', 'fulfilled'])
    const pending = Promise.allSettled([t.service.reportBatchCheck(targets)])
    t.state().samples.find(sample => sample.id === targets[1]!.id)!.version++
    await vi.runAllTimersAsync()
    expect((await pending)[0]).toMatchObject({ status: 'fulfilled' })
  })
})
