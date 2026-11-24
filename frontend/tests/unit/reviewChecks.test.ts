import { emptyContractReview } from '../../src/types/commissions/contractReview'
import { afterEach, expect, it, vi } from 'vitest'
import { createReviewChecks } from '../../server/reviewChecks'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'

afterEach(() => vi.useRealTimers())
it('report checks discard superseded requests and reject samples changed while checking', async () => {
  vi.useFakeTimers()
  let state = seedRegistration()
  const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state, write: next => { state = next } }, createReviewChecks(1500))
  const sample = state.samples.find(row => row.id === 'demo-yp-82')!
  const first = service.reportComplianceCheck(sample.id, sample.version)
  const second = service.reportComplianceCheck(sample.id, sample.version)
  const settled = Promise.allSettled([first, second])
  await vi.runAllTimersAsync()
  const results = await settled
  expect(results[0]).toMatchObject({ status: 'rejected', reason: { code: 'VALIDATION' } })
  expect(results[1].status).toBe('fulfilled')
  const pending = Promise.allSettled([service.reportComplianceCheck(sample.id, sample.version)])
  await service.reportCheckAction(sample.id, 'reject', sample.version, undefined, { reason: '数据有误', problemType: '检测数据问题', destination: 'testing', handler: '', opinion: '' })
  const changed = structuredClone(state)
  await vi.runAllTimersAsync()
  expect((await pending)[0]).toMatchObject({ status: 'rejected', reason: { code: 'BUSINESS_RULE' } })
  expect(state).toEqual(changed)
})
it('invalidates older in-flight checks and revalidates sample state before publishing results', async () => {
  vi.useFakeTimers()
  let state = seedRegistration()
  const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state, write: next => { state = next } }, createReviewChecks(1500))
  const initial = await service.sample('demo-yp-2')
  const started = await service.act('samples', initial.id, 'start-review', initial.version)
  const version = started.version
  const before = structuredClone(state)
  const first = service.reviewCheck(initial.id, version, emptyContractReview())
  const second = service.reviewCheck(initial.id, version, emptyContractReview())
  const settled = Promise.allSettled([first, second])
  await vi.runAllTimersAsync()
  const results = await settled
  expect(results[0].status).toBe('rejected')
  expect(results[1].status).toBe('fulfilled')
  expect(state).toEqual(before)
  const stale = service.reviewCheck(initial.id, version, emptyContractReview())
  const staleResult = Promise.allSettled([stale])
  await service.act('samples', initial.id, 'unreview', version)
  const changed = structuredClone(state)
  await vi.runAllTimersAsync()
  expect((await staleResult)[0]).toMatchObject({ status: 'rejected', reason: { code: 'BUSINESS_RULE' } })
  expect(state).toEqual(changed)
})
