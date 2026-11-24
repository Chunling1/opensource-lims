import { expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'

function setup() {
  let state = seedRegistration(), actor = demoActors[0]!
  const service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { state = next } })
  return { service, state: () => state, actor: (id: string) => { actor = demoActors.find(row => row.id === id)! } }
}
it.each(['review', 'approval'] as const)('%s submits an existing cancellation application with stage permissions', async stage => {
  const t = setup(), id = stage === 'review' ? 'demo-yp-85' : 'demo-yp-88'
  t.actor(stage === 'review' ? 'reviewer' : 'approver')
  const sample = await t.service.sample(id), before = structuredClone(t.state())
  expect((await t.service.reportCheckSamples({ ids: [id] }, stage)).items[0]!.canVoid).toBe(true)
  for (const reason of ['', '  ', 'x'.repeat(501)]) await expect(t.service.reportVoidAction(id, sample.version, reason, stage)).rejects.toMatchObject({ code: 'VALIDATION' })
  expect(t.state()).toEqual(before)
  const saved = await t.service.reportVoidAction(id, sample.version + 1, '  客户撤销检测  ', stage)
  expect(saved).toMatchObject({ status: 'void_pending', dataStatus: '作废申请中', voidApplication: { reason: '客户撤销检测', previousStatus: sample.status, previousDataStatus: sample.dataStatus, appliedBy: { id: stage === 'review' ? 'reviewer' : 'approver' } } })
  expect(saved.reportCheckInfo).toEqual(sample.reportCheckInfo)
  expect(saved.reportReviewInfo).toEqual(sample.reportReviewInfo)
  expect(saved.events.at(-1)?.action).toBe('提交作废申请')
  expect((await t.service.reportCheckSamples({ ids: [id] }, stage)).total).toBe(0)
  await expect(t.service.reportVoidAction(id, saved.version, '重复申请', stage)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
  t.actor('admin')
  expect((await t.service.cancellationApprovals({ ids: [id] })).items[0]).toMatchObject({ approvalResult: '申请中', applicationReason: '客户撤销检测' })
})
it('does not enable the check page or grant another stage or department the right to void', async () => {
  const t = setup(), sample = await t.service.sample('demo-yp-88')
  t.actor('reviewer')
  expect((await t.service.reportCheckSamples({ ids: [sample.id] }, 'approval')).items[0]!.canVoid).toBe(false)
  await expect(t.service.reportVoidAction(sample.id, sample.version, '撤回', 'approval')).rejects.toMatchObject({ code: 'FORBIDDEN' })
  t.actor('other')
  await expect(t.service.reportVoidAction(sample.id, sample.version, '撤回', 'review')).rejects.toMatchObject({ code: 'FORBIDDEN' })
  t.actor('admin')
  await expect(t.service.reportVoidAction(sample.id, sample.version, '撤回', 'check')).rejects.toMatchObject({ code: 'BAD_REQUEST' })
  await expect(t.service.reportVoidAction(sample.id, sample.version, '撤回', 'review')).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
  expect(await t.service.sample(sample.id)).toEqual(sample)
})
