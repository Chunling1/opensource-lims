import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { createReviewChecks } from '../../server/reviewChecks'
import { parseReportStage, reportCheckCapabilities } from '../../server/reportCheck'
import { reportStages, type ReportStage } from '../../src/types/reports/reportCheck'
import { demoActors } from '../../src/services/storage/demoActors'

function setup() {
  let state = seedRegistration(), actor = demoActors[0]!
  const checks = createReviewChecks(0)
  const service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { state = next } }, checks)
  return { service, state: () => state, actor: (id: string) => { actor = demoActors.find(row => row.id === id)! } }
}
async function pass(t: ReturnType<typeof setup>, id: string, stage: ReportStage, recipientId?: string) {
  const sample = t.state().samples.find(row => row.id === id)!
  const result = await t.service.reportComplianceCheck(id, sample.version, stage)
  return t.service.reportCheckAction(id, 'check', sample.version, { reviewCheckId: result.id, readConfirmed: true, nextAction: recipientId ? 'transfer' : 'next', ...(recipientId ? { recipientId } : {}) }, undefined, stage)
}
describe('report review and approval', () => {
  it('filters approval queries and exports by the preceding review date', async () => {
    const t = setup(), sample = t.state().samples.find(row => row.id === 'demo-yp-88')!
    sample.reportReviewInfo!.date = '2026-09-15'
    const query = { ids: [sample.id], dateField: 'reportReviewDate' as const, from: '2026-09-15', to: '2026-09-15' }
    expect((await t.service.reportCheckSamples(query, 'approval')).items[0]).toMatchObject({ reportReviewDate: '2026-09-15', checkDate: '' })
    expect(await t.service.exportReportCheckSamples(query, 'approval')).toContain(sample.code)
    expect((await t.service.reportCheckSamples({ ...query, from: '2026-09-16', to: '2026-09-17' }, 'approval')).total).toBe(0)
    expect(await t.service.exportReportCheckSamples({ ...query, to: '2026-09-14', from: '2026-09-13' }, 'approval')).not.toContain(sample.code)
    delete sample.reportReviewInfo
    expect((await t.service.reportCheckSamples(query, 'approval')).total).toBe(0)
    await expect(t.service.reportCheckSamples(query, 'review')).rejects.toMatchObject({ code: 'BAD_REQUEST' })
  })
  it.each(['review', 'approval'] as const)('%s supports its own facts, filters, transfer, reversal and rejection', async stage => {
    const t = setup(), config = reportStages[stage], id = stage === 'review' ? 'demo-yp-85' : 'demo-yp-88'
    const before = structuredClone(t.state().samples.find(row => row.id === id)!)
    expect((await t.service.reportCheckSamples({ contains: before.code, status: config.pending }, stage)).total).toBe(1)
    const transferred = await pass(t, id, stage, config.role)
    expect(transferred.dataStatus).toBe(config.pending)
    expect(transferred[config.infoKey]?.recipient?.id).toBe(config.role)
    const completed = await pass(t, id, stage)
    expect(completed.dataStatus).toBe(config.completed)
    expect(completed.reportCheckInfo).toEqual(before.reportCheckInfo)
    expect(completed.workflow?.[stage === 'review' ? 'auditDate' : 'approvalDate']).toBeTruthy()
    const date = completed[config.infoKey]!.date!
    expect((await t.service.reportCheckSamples({ contains: before.code, dateField: 'checkDate', from: date, to: date }, stage)).items[0]).toMatchObject({ checker: '演示用户', checkDate: date })
    const csv = await t.service.exportReportCheckSamples({ ids: [id] }, stage)
    expect(csv).toContain(`${config.label}人`); expect(csv).toContain(`${config.label}日期`)
    if (stage === 'approval') {
      const state = structuredClone(t.state())
      expect(reportCheckCapabilities(demoActors[0]!, completed, stage).canUndoCheck).toBe(false)
      await expect(t.service.reportCheckAction(id, 'undo', completed.version, undefined, undefined, stage)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
      expect(t.state()).toEqual(state)
      return
    }
    const undone = await t.service.reportCheckAction(id, 'undo', completed.version, undefined, undefined, stage)
    expect(undone[config.infoKey]).toBeUndefined()
    expect(undone.reportCheckInfo).toEqual(before.reportCheckInfo)
    expect(undone.workflow?.[stage === 'review' ? 'auditDate' : 'approvalDate']).toBeUndefined()
    const rejected = await t.service.reportCheckAction(id, 'reject', undone.version, undefined, { reason: '', problemType: '其他问题', destination: 'testing', handler: '', opinion: '' }, stage)
    expect(rejected.dataStatus).toBe('检测更改中')
    expect(rejected.reportCheckIssues?.at(-1)).toMatchObject({ stage, reason: '' })
    expect((await t.service.dataChanges({ ids: [id] })).total).toBe(1)
    expect((await t.service.completeDataChange(id, rejected.version, true)).reportReviewInfo).toBeUndefined()
  })
  it('moves completed reports through the next queues and never accepts a proof from another stage', async () => {
    const t = setup(), id = 'demo-yp-82'
    const checked = await pass(t, id, 'check')
    expect((await t.service.reportCheckSamples({ contains: checked.code, status: '报告审核中' }, 'review')).total).toBe(1)
    await expect(t.service.reportCheckAction(id, 'check', checked.version, { reviewCheckId: checked.reportCheckInfo!.reviewConfirmation!.result.id, readConfirmed: true, nextAction: 'next' }, undefined, 'review')).rejects.toMatchObject({ code: 'VALIDATION' })
    const reviewed = await pass(t, id, 'review')
    expect((await t.service.reportCheckSamples({ contains: checked.code, status: '报告批准中' }, 'approval')).total).toBe(1)
    expect(reportCheckCapabilities(demoActors[0]!, reviewed).canUndoCheck).toBe(false)
    const approved = await pass(t, id, 'approval')
    expect(approved.reportCheckInfo).toEqual(checked.reportCheckInfo)
    expect(approved.reportReviewInfo).toEqual(reviewed.reportReviewInfo)
    await expect(t.service.reportCheckAction(id, 'undo', approved.version, undefined, undefined, 'review')).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
  })
  it('enforces stage roles, department scope, final workflow locks and fresh versions', async () => {
    const t = setup(), sample = t.state().samples.find(row => row.id === 'demo-yp-88')!
    t.actor('reviewer')
    await expect(t.service.reportComplianceCheck(sample.id, sample.version, 'approval')).rejects.toMatchObject({ code: 'FORBIDDEN' })
    t.actor('approver')
    expect((await t.service.reportCheckRecipients(sample.id, { scope: 'all' }, false, 'approval'))).toMatchObject({ items: expect.arrayContaining([expect.objectContaining({ id: 'approver' })]) })
    await expect(t.service.reportCheckRecipients(sample.id, { id: 'reviewer' }, true, 'approval')).rejects.toMatchObject({ code: 'VALIDATION' })
    await expect(t.service.reportComplianceCheck(sample.id, sample.version + 1, 'approval')).resolves.toMatchObject({ sampleId: sample.id })
    sample.workflow = { ...sample.workflow, issueDate: '2026-10-02' }
    await expect(t.service.reportComplianceCheck(sample.id, sample.version, 'approval')).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    expect(reportCheckCapabilities({ ...demoActors[0]!, scope: 'department', departmentId: 'lab2' }, sample, 'approval').canCheck).toBe(false)
    expect(() => parseReportStage('other')).toThrow()
  })
})
