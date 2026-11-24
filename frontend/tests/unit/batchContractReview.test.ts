import { afterEach, describe, expect, it, vi } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { createReviewChecks } from '../../server/reviewChecks'
import { demoActors } from '../../src/services/storage/demoActors'
import { emptyContractReview, type BatchReviewTarget } from '../../src/types/commissions/contractReview'

function setup(delay = 0) {
  let state = seedRegistration(), actor = demoActors[0]!
  const service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { state = next } }, createReviewChecks(delay))
  const targets = (ids = ['demo-yp-2', 'demo-yp-5']) => ids.map(id => ({ id, version: state.samples.find(sample => sample.id === id)!.version }))
  return { service, targets, state: () => state, actor: (id: string) => { actor = demoActors.find(actor => actor.id === id)! } }
}
const review = () => ({ ...emptyContractReview(), decision: 'approved' as const, readConfirmed: true })
const proofs = (items: { sampleId: string; id: string }[]) => items.map(item => ({ sampleId: item.sampleId, checkId: item.id }))
afterEach(() => vi.useRealTimers())

describe('batch contract review', () => {
  it('checks every sample and atomically saves its own proof, notes and audit', async () => {
    const t = setup()
    t.state().samples.find(sample => sample.id === 'demo-yp-2')!.contractReview = { ...emptyContractReview(), notes: '原有备注' }
    const started = await t.service.startBatchReview(t.targets())
    expect(started.every(sample => sample.reviewStatus === 'reviewed')).toBe(true)
    const before = structuredClone(t.state()), checked = await t.service.batchReviewCheck(t.targets(), emptyContractReview())
    expect(t.state()).toEqual(before)
    expect(checked.items.map(item => item.sampleCode)).toEqual(['SP2026090002', 'SP2026090005'])
    expect(checked.items.every(item => item.messages.some(message => message.text.includes(item.sampleCode)))).toBe(true)
    const saved = await t.service.submitBatchReview(t.targets(), review(), proofs(checked.items))
    expect(saved.every(sample => sample.reviewStatus === 'approved' && sample.dataStatus === '评审完成')).toBe(true)
    expect(saved[0]!.contractReview!.notes).toBe('原有备注')
    for (const sample of saved) {
      expect(sample.contractReview!.compliance).toMatchObject({ result: { sampleId: sample.id, id: checked.items.find(item => item.sampleId === sample.id)!.id }, readConfirmed: true, confirmedBy: { id: 'admin' } })
      expect(sample.events.at(-1)).toMatchObject({ action: '评审通过', reason: '批量快速评审' })
    }
  })
  it('rejects malformed, duplicate, unauthorized or ineligible selections without starting any sample', async () => {
    const t = setup(), before = structuredClone(t.state())
    for (const input of [[], [t.targets()[0], t.targets()[0]], [{ id: 'demo-yp-2', version: '1' }], Array.from({ length: 51 }, (_, i) => ({ id: String(i), version: 1 }))]) {
      await expect(t.service.startBatchReview(input)).rejects.toMatchObject({ code: 'BAD_REQUEST' })
    }
    await expect(t.service.startBatchReview(t.targets(['demo-yp-2', 'demo-yp-1']))).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    t.actor('reviewer')
    await expect(t.service.startBatchReview(t.targets())).rejects.toMatchObject({ code: 'FORBIDDEN' })
    t.actor('business')
    const hidden = t.state().samples.find(sample => sample.departmentId === 'lab2')!
    await expect(t.service.startBatchReview(t.targets(['demo-yp-2', hidden.id]))).rejects.toMatchObject({ code: 'NOT_FOUND' })
    expect(t.state()).toEqual(before)
  })
  it('requires complete fresh proofs bound to the exact selection, actor and options; failures never partially submit', async () => {
    const t = setup()
    await t.service.startBatchReview(t.targets())
    const first = await t.service.batchReviewCheck(t.targets(), emptyContractReview())
    const second = await t.service.batchReviewCheck(t.targets(), emptyContractReview())
    const before = structuredClone(t.state())
    const rejects: [BatchReviewTarget[], unknown, unknown][] = [
      [t.targets(), review(), proofs(first.items)],
      [t.targets(), review(), proofs(second.items).slice(0, 1)],
      [t.targets().slice(0, 1), review(), proofs(second.items).slice(0, 1)],
      [t.targets(), { ...review(), cma: true }, proofs(second.items)],
      [t.targets(), { ...review(), readConfirmed: false }, proofs(second.items)],
      [t.targets(), { ...review(), technicalCapability: false }, proofs(second.items)],
      [t.targets(), review(), proofs(second.items).map((item, i, all) => ({ ...item, checkId: all[1 - i]!.checkId }))],
    ]
    for (const args of rejects) {
      await expect(t.service.submitBatchReview(...args)).rejects.toMatchObject({ code: 'VALIDATION' })
      expect(t.state()).toEqual(before)
    }
    const single = await t.service.reviewCheck(t.targets()[0]!.id, t.targets()[0]!.version, emptyContractReview())
    await expect(t.service.submitBatchReview(t.targets(), review(), [{ sampleId: single.sampleId, checkId: single.id }, proofs(second.items)[1]])).rejects.toMatchObject({ code: 'VALIDATION' })
    t.actor('business')
    await expect(t.service.submitBatchReview(t.targets(), review(), proofs(second.items))).rejects.toMatchObject({ code: 'VALIDATION' })
    t.actor('admin')
    t.state().samples.find(sample => sample.id === 'demo-yp-5')!.version++
    const saved = await t.service.submitBatchReview(t.targets(), review(), proofs(second.items))
    expect(saved.every(sample => sample.reviewStatus === 'approved')).toBe(true)
  })
  it('refreshes all versions and permits rejection without verification', async () => {
    const t = setup()
    await t.service.startBatchReview(t.targets())
    t.state().samples.find(sample => sample.id === 'demo-yp-5')!.version++
    const context = await t.service.batchReviewContext(t.targets().map(item => item.id))
    expect(context.map(({ id, version }) => ({ id, version }))).toEqual(t.targets())
    const rejected = await t.service.submitBatchReview(t.targets(), { ...review(), decision: 'rejected' }, [])
    expect(rejected.every(sample => sample.dataStatus === '完成登记' && sample.reviewStatus === 'unreviewed')).toBe(true)
  })
  it('discards superseded checks and revalidates the entire batch after asynchronous verification', async () => {
    vi.useFakeTimers()
    const t = setup(1500)
    await t.service.startBatchReview(t.targets())
    const results = Promise.allSettled([t.service.batchReviewCheck(t.targets(), emptyContractReview()), t.service.batchReviewCheck(t.targets(), emptyContractReview())])
    await vi.runAllTimersAsync()
    expect((await results).map(result => result.status)).toEqual(['rejected', 'fulfilled'])
    const pending = Promise.allSettled([t.service.batchReviewCheck(t.targets(), emptyContractReview())])
    t.state().samples.find(sample => sample.id === 'demo-yp-5')!.version++
    await vi.runAllTimersAsync()
    expect((await pending)[0]).toMatchObject({ status: 'fulfilled' })
  })
})
