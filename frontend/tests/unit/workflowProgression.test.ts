import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { createDataEntryService } from '../../server/dataEntryDetail'
import { createReviewChecks } from '../../server/reviewChecks'
import { createReportLifecycleService } from '../../server/reportLifecycle'
import { createDemoSigningProvider } from '../../server/reportSigning'
import { emptyContractReview } from '../../src/types/commissions/contractReview'
import { demoActors } from '../../src/services/storage/demoActors'
import { workspaceActions } from '../../src/services/commissions/registrationService'

describe('workflow handoffs', () => {
  it('takes one registered sample through review, stock, assignment, entry and report approval', async () => {
    let state = seedRegistration()
    const id = 'demo-yp-76', actor = demoActors[0]!, sample = () => state.samples.find(row => row.id === id)!
    Object.assign(sample(), { status: 'pending', dataStatus: '委托登记中', reviewStatus: 'unreviewed' })
    const deps = { actor: () => actor, read: () => state, write: (next: typeof state) => { state = next } }
    const service = createRegistrationService(deps, createReviewChecks(0))
    const entry = createDataEntryService(deps, () => Date.now() - 60000)
    const act = (action: string, values: Record<string, unknown> = {}) => {
      const detail = entry.detail(id)
      return entry.mutate(id, action, { version: detail.version, sampleVersion: detail.sample.version, requestId: crypto.randomUUID(), ...values })
    }
    await service.act('samples', id, 'complete', sample().version)
    await service.act('samples', id, 'start-review', sample().version)
    const review = emptyContractReview(), proof = await service.reviewCheck(id, sample().version, review)
    await service.act('samples', id, 'review', sample().version, '', { ...review, decision: 'approved', checkId: proof.id, readConfirmed: true })
    expect((await service.inboundSamples({ ids: [id], status: '样品入库中' })).items[0]?.dataStatus).toBe('样品入库中')
    expect(sample().dataStatus).toBe('评审完成')
    const receipt = { account: actor.id, name: actor.name, date: '2026-10-02' }
    await service.inboundAction(id, 'receive', sample().version, { ...receipt, location: '检测室', condition: '正常', notes: '' })
    const before = structuredClone(state)
    await expect(service.act('samples', id, 'unreview', sample().version)).rejects.toThrow()
    expect(state).toEqual(before)
    expect((await service.assignmentSamples({ ids: [id], status: '任务分配中' })).items[0]?.canAssign).toBe(true)
    await service.assignmentAction(id, sample().version, { ...receipt, dataEntryPerson: 'analyst', tester1: 'analyst', tester2: '' }, 'assign')
    expect((await service.outboundSamples({ ids: [id], status: '样品出库中' })).items[0]?.outboundActions).toContain('dispatch')
    await service.outboundAction(id, 'dispatch', sample().version, receipt)
    await expect(service.assignmentAction(id, sample().version, {}, 'undo')).rejects.toThrow()
    expect((await service.pickupSamples({ ids: [id] })).items[0]?.canPickup).toBe(true)
    await service.pickupAction(id, sample().version, receipt)
    expect((await service.dataEntrySamples({ ids: [id], status: '检测数据录入中' })).items[0]?.canEdit).toBe(true)
    act('save', { form: { ...entry.detail(id).form, conclusion: '符合要求', conclusionStatus: '合格', tester1Id: 'analyst', testDates: [{ kind: 'range', from: '2026-10-01', to: '2026-10-02' }] } })
    expect(sample().dataStatus).toBe('检测数据录入中')
    act('combine')
    // The same stored task is observed after its generation time, as in the API.
    const ready = createDataEntryService(deps)
    const detail = ready.detail(id)
    ready.mutate(id, 'complete', { version: detail.version, sampleVersion: sample().version, requestId: crypto.randomUUID(), acknowledgeMissingOriginals: true })
    expect((await service.dataCheckSamples({ ids: [id] })).items[0]?.canCheck).toBe(true)
    await service.dataCheckAction(id, 'check', sample().version)
    expect((await service.reportCheckSamples({ ids: [id], status: '报告校核中' })).items[0]?.canCheck).toBe(true)
    for (const stage of ['check', 'review', 'approval'] as const) {
      const check = await service.reportComplianceCheck(id, sample().version, stage)
      await service.reportCheckAction(id, 'check', sample().version, { reviewCheckId: check.id, readConfirmed: true, nextAction: 'next' }, undefined, stage)
    }
    expect(sample().reportRelease).toMatchObject({ form: '纸质', printStatus: '待打印' })
    expect(Buffer.from(sample().reportRelease!.original.base64, 'base64').subarray(0, 5).toString()).toBe('%PDF-')
    const printing = createReportLifecycleService(deps, createDemoSigningProvider('0123456789abcdef0123456789abcdef'))
    expect(printing.printList({ ids: [id] }).items[0]?.id).toBe(id)
    printing.action(id, { action: 'complete-print', version: sample().version, releaseId: sample().reportRelease!.id, confirmed: true })
    expect(sample().reportRelease?.printStatus).toBe('打印完成')
  })

  it('blocks contract review rollback at every later stage in both menus and the backend', async () => {
    let state = seedRegistration()
    const actor = demoActors[0]!, service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { state = next } })
    for (const status of ['样品入库完成', '任务分配中', '任务分配完成', '样品待领取', '样品已领取', '检测数据录入中', '检测数据校核完成', '报告校核中', '报告审核中']) {
      const sample = state.samples.find(row => row.id === 'demo-yp-76')!
      sample.dataStatus = status
      expect(workspaceActions(actor, 'samples', sample, 'review').find(action => action.id === 'unreview')?.disabled).toBe(true)
      const before = structuredClone(state)
      await expect(service.act('samples', sample.id, 'unreview', sample.version)).rejects.toThrow()
      expect(state).toEqual(before)
    }
    state.samples.find(row => row.id === 'demo-yp-76')!.dataStatus = '评审完成'
    expect(await service.act('samples', 'demo-yp-76', 'unreview', 1)).toMatchObject({ dataStatus: '完成登记' })
  })
})
