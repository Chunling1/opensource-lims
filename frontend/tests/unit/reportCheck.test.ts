import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { parseReportCheckQuery } from '../../server/reportCheck'
import { reportCheckColumns } from '../../src/types/reports/reportCheck'
import { demoActors } from '../../src/services/storage/demoActors'
import type { Actor } from '../../src/types/lims'
import { entryCapabilities, createDataEntryService } from '../../server/dataEntryDetail'
import { createReviewChecks } from '../../server/reviewChecks'
import { emptyContractReview } from '../../src/types/commissions/contractReview'
const rejection = { reason: '请校正检测数据', problemType: '检测数据问题', destination: 'testing', handler: '李检测', opinion: '核对原始记录后更正' } as const

describe('report checking list', () => {
  it('requires a fresh actor-bound report check and acknowledgement instead of historical proof', async () => {
    let state = seedRegistration()
    let current = demoActors[0]!
    const checks = createReviewChecks(0)
    const service = createRegistrationService({ actor: () => current, read: () => state, write: next => { state = next } }, checks)
    const sample = state.samples.find(row => row.id === 'demo-yp-82')!, proofId = sample.contractReview!.compliance!.result.id
    const before = structuredClone(state)
    for (const confirmation of [undefined, {}, { readConfirmed: false, reviewCheckId: proofId }, { readConfirmed: 'true', reviewCheckId: proofId }, { readConfirmed: true, reviewCheckId: proofId }]) {
      await expect(service.reportCheckAction(sample.id, 'check', sample.version, confirmation)).rejects.toMatchObject({ code: 'VALIDATION' })
      expect(state).toEqual(before)
    }
    delete sample.contractReview
    const proof = await service.reportComplianceCheck(sample.id, sample.version)
    expect(proof).toMatchObject({ sampleId: sample.id, sampleVersion: sample.version })
    const newer = await service.reportComplianceCheck(sample.id, sample.version)
    for (const readConfirmed of [false, 'true', undefined]) {
      await expect(service.reportCheckAction(sample.id, 'check', sample.version, { reviewCheckId: newer.id, readConfirmed })).rejects.toMatchObject({ code: 'VALIDATION' })
    }
    await expect(service.reportCheckAction(sample.id, 'check', sample.version, { reviewCheckId: proof.id, readConfirmed: true })).rejects.toMatchObject({ code: 'VALIDATION' })
    const contractProof = await checks.run(current.id, sample, () => {}, emptyContractReview())
    await expect(service.reportCheckAction(sample.id, 'check', sample.version, { reviewCheckId: contractProof.id, readConfirmed: true })).rejects.toMatchObject({ code: 'VALIDATION' })
    current = { ...current, id: 'another-reviewer' }
    await expect(service.reportCheckAction(sample.id, 'check', sample.version, { reviewCheckId: newer.id, readConfirmed: true })).rejects.toMatchObject({ code: 'VALIDATION' })
    current = demoActors[0]!
    sample.version++
    await expect(service.reportCheckAction(sample.id, 'check', sample.version, { reviewCheckId: newer.id, readConfirmed: true })).rejects.toMatchObject({ code: 'VALIDATION' })
    const returned = await service.reportCheckAction(sample.id, 'reject', sample.version, undefined, { ...rejection, reason: '  ' })
    expect(returned.dataStatus).toBe('检测更改中')
    expect(returned.reportCheckIssues?.at(-1)?.reason).toBe('')
  })
  it('checks, undoes and rejects reports independently, preserving saved testing facts and files', async () => {
    let state = seedRegistration()
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state, write: next => { state = next } }, createReviewChecks(0))
    const sample = state.samples.find(row => row.id === 'demo-yp-82')!
    sample.dataCheckInfo = { actorId: 'analyst', actorName: '李检测', at: '2026-09-01', previousDataStatus: '检测数据录入完成' }
    sample.workflow = { ...sample.workflow, checkDate: '2026-09-01' }
    sample.attachments = [{ id: 'kept-file', name: '说明.txt', size: 1, type: 'text/plain', dataUrl: 'data:text/plain;base64,YQ==' }]
    const before = structuredClone(sample)
    expect(entryCapabilities(demoActors[0]!, sample)).toMatchObject({ canReportCheck: true, canCheck: false, canEdit: false, canManageOriginals: false })
    const proof = await service.reportComplianceCheck(sample.id, sample.version)
    expect(sample).toEqual(before)
    const checked = await service.reportCheckAction(sample.id, 'check', sample.version, { reviewCheckId: proof.id, readConfirmed: true, nextAction: 'next' })
    expect(checked).toMatchObject({ dataStatus: '报告校核完成', version: sample.version + 1, reportCheckInfo: { actorId: 'admin', actorName: '演示用户' } })
    expect(checked.reportCheckInfo?.date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(checked.reportCheckInfo?.reviewConfirmation).toMatchObject({ result: proof, readConfirmed: true, confirmedBy: { id: 'admin', name: '演示用户' } })
    expect(checked.workflow).toEqual(before.workflow)
    expect(checked.dataCheckInfo).toEqual(before.dataCheckInfo)
    await expect(service.reportCheckAction(sample.id, 'check', checked.version)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    const undone = await service.reportCheckAction(sample.id, 'undo', sample.version)
    expect(undone.dataStatus).toBe('报告校核中')
    expect(undone.reportCheckInfo).toBeUndefined()
    const rejected = await service.reportCheckAction(sample.id, 'reject', undone.version, undefined, rejection)
    expect(rejected.dataStatus).toBe('检测更改中')
    expect(entryCapabilities(demoActors[0]!, rejected)).toMatchObject({ canReportCheck: false, canEdit: true })
    expect(rejected.dataEntryInfo).toEqual(before.dataEntryInfo)
    expect(rejected.attachments).toEqual(before.attachments)
    expect(rejected.events.at(-1)).toMatchObject({ action: '报告校核不通过', reason: '退回检测数据更改：请校正检测数据' })
    expect((await service.reportCheckSamples({ contains: sample.code })).total).toBe(0)
    expect((await service.dataChanges({ ids: [sample.id] })).total).toBe(1)
    await expect(service.reportCheckAction(sample.id, 'undo', rejected.version)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
  })
  it('validates rejection fields atomically and keeps both return routes and issue history', async () => {
    let state = seedRegistration()
    const deps = { actor: () => demoActors[0]!, read: () => state, write: (next: typeof state) => { state = next } }
    const service = createRegistrationService(deps), entries = createDataEntryService(deps)
    const sample = state.samples.find(row => row.id === 'demo-yp-82')!, before = structuredClone(state)
    for (const input of [undefined, {}, { ...rejection, problemType: '未知' }, { ...rejection, destination: ['testing'] }, { ...rejection, reason: '长'.repeat(2001) }, { ...rejection, opinion: '长'.repeat(2001) }, { ...rejection, handler: 12 }]) {
      await expect(service.reportCheckAction(sample.id, 'reject', sample.version, undefined, input)).rejects.toMatchObject({ code: 'VALIDATION' })
      expect(state).toEqual(before)
    }
    const first = await service.reportCheckAction(sample.id, 'reject', sample.version, undefined, { ...rejection, destination: 'commission', problemType: '委托信息问题' })
    expect(first).toMatchObject({ dataStatus: '委托更改中', commissionChange: { result: '问题处理中', type: '委托信息问题', description: rejection.reason } })
    expect((await service.sampleChanges({ ids: [sample.id] })).total).toBe(1)
    const completed = await service.act('samples', sample.id, 'complete-change', first.version)
    expect(state.samples.find(row => row.id === sample.id)!.reportCheckIssues?.[0].completedBy).toEqual({ id: 'admin', name: '演示用户' })
    state.samples.find(row => row.id === sample.id)!.dataStatus = '报告校核中'
    const second = await service.reportCheckAction(sample.id, 'reject', completed.version, undefined, rejection)
    expect(second.reportCheckIssues).toHaveLength(2)
    expect((await service.dataChanges({ ids: [sample.id] })).items[0]).toMatchObject({ problemDescription: rejection.reason, problemType: rejection.problemType })
    const records = entries.records(sample.id, { kind: 'issues' })
    expect(records.total).toBe(2)
    expect(records.items[0]).toMatchObject({ description: rejection.reason, type: rejection.problemType, handler: rejection.handler, opinion: rejection.opinion, destination: '退回检测数据更改' })
    const done = await service.completeDataChange(sample.id, second.version, true)
    expect(done.reportCheckIssues?.[1].completedAt).toBeTruthy()
    expect(entries.records(sample.id, { kind: 'issues' }).total).toBe(2)
  })
  it('requires an explicit next action, validates recipients, and records transfer without completing the check', async () => {
    let state = seedRegistration(), current = demoActors[0]!
    const service = createRegistrationService({ actor: () => current, read: () => state, write: next => { state = next } }, createReviewChecks(0))
    const sample = state.samples.find(row => row.id === 'demo-yp-82')!
    const proof = await service.reportComplianceCheck(sample.id, sample.version)
    const confirmation = { reviewCheckId: proof.id, readConfirmed: true }
    const before = structuredClone(state)
    for (const next of [{}, { nextAction: 'unknown' }, { nextAction: 'transfer' }, { nextAction: 'transfer', recipientId: 'analyst' }, { nextAction: 'transfer', recipientId: 'missing' }, { nextAction: 'next', recipientId: 'reviewer' }]) {
      await expect(service.reportCheckAction(sample.id, 'check', sample.version, { ...confirmation, ...next })).rejects.toMatchObject({ code: 'VALIDATION' })
      expect(state).toEqual(before)
    }
    const people = await service.reportCheckRecipients(sample.id, { scope: 'all', keyword: '王' })
    expect(people).toMatchObject({ total: 1, items: [{ id: 'reviewer' }] })
    await expect(service.reportCheckRecipients(sample.id, { id: 'analyst' }, true)).rejects.toMatchObject({ code: 'VALIDATION' })
    const transferred = await service.reportCheckAction(sample.id, 'check', sample.version, { ...confirmation, nextAction: 'transfer', recipientId: 'reviewer' })
    expect(transferred).toMatchObject({ dataStatus: '报告校核中', version: sample.version + 1, reportCheckInfo: { nextAction: 'transfer', recipient: { id: 'reviewer', name: '王复核' } } })
    expect(transferred.events.at(-1)).toMatchObject({ action: '报告转交校核', reason: '接收人：王复核（reviewer）' })
    current = demoActors.find(actor => actor.id === 'reviewer')!
    const checked = await service.reportComplianceCheck(sample.id, transferred.version)
    const completed = await service.reportCheckAction(sample.id, 'check', transferred.version, { reviewCheckId: checked.id, readConfirmed: true, nextAction: 'next' })
    expect(completed).toMatchObject({ dataStatus: '报告校核完成', reportCheckInfo: { actorId: 'reviewer', nextAction: 'next' } })
    expect(completed.reportCheckInfo?.recipient).toBeUndefined()
    await expect(service.reportCheckRecipients(sample.id, {}, false)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
  })
  it('denies wrong roles, out-of-scope, voided, later-stage and stale report decisions without writes', async () => {
    let state = seedRegistration(), current: Actor = demoActors.find(actor => actor.id === 'analyst')!
    const service = createRegistrationService({ actor: () => current, read: () => state, write: next => { state = next } })
    const sample = state.samples.find(row => row.id === 'demo-yp-82')!, before = structuredClone(state)
    await expect(service.reportComplianceCheck(sample.id, sample.version)).rejects.toMatchObject({ code: 'FORBIDDEN' })
    await expect(service.reportCheckAction(sample.id, 'check', sample.version)).rejects.toMatchObject({ code: 'FORBIDDEN' })
    current = { ...demoActors[0]!, roles: ['reports'], scope: 'department', departmentId: 'lab2' }
    await expect(service.reportComplianceCheck(sample.id, sample.version)).rejects.toMatchObject({ code: 'NOT_FOUND' })
    await expect(service.reportCheckAction(sample.id, 'check', sample.version)).rejects.toMatchObject({ code: 'NOT_FOUND' })
    current = demoActors[0]!
    await expect(service.reportComplianceCheck(sample.id, 999)).resolves.toMatchObject({ sampleId: sample.id })
    await expect(service.reportCheckAction(sample.id, 'check', 999)).rejects.toMatchObject({ code: 'VALIDATION' })
    await expect(service.reportCheckAction(sample.id, 'check', 0)).rejects.toMatchObject({ code: 'BAD_REQUEST' })
    await expect(service.reportCheckAction(sample.id, 'unknown', sample.version)).rejects.toMatchObject({ code: 'BAD_REQUEST' })
    expect(state).toEqual(before)
    sample.workflow = { ...sample.workflow, auditDate: '2026-09-30' }
    await expect(service.reportComplianceCheck(sample.id, sample.version)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    expect((await service.reportCheckSamples({ contains: sample.code })).items[0]).toMatchObject({ canCheck: false, canUndoCheck: false })
    await expect(service.reportCheckAction(sample.id, 'check', sample.version)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    delete sample.workflow.auditDate; sample.status = 'voided'
    await expect(service.reportCheckAction(sample.id, 'check', sample.version)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
  })
  it('filters report check dates inclusively before pagination and export without using testing check dates', async () => {
    const state = seedRegistration(), source = state.samples.find(row => row.id === 'demo-yp-83')!
    state.samples = Array.from({ length: 15 }, (_, index) => ({ ...structuredClone(source), id: `report-date-${index}`, code: `REPORT${index}`,
      reportCheckInfo: index === 14 ? undefined : { actorId: 'reviewer', actorName: '王复核', at: `${index < 12 ? '2026-10-01' : '2026-10-02'}T10:00:00+08:00` },
      workflow: { ...source.workflow, checkDate: '2026-10-03' } }))
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const query = { dateField: 'checkDate', from: '2026-10-01', to: '2026-10-01', page: 2, pageSize: 10 } as const
    expect(parseReportCheckQuery(query).dateField).toBe('checkDate')
    const result = await service.reportCheckSamples(query)
    expect(result).toMatchObject({ total: 12, page: 2 })
    expect(result.items).toHaveLength(2)
    expect((await service.exportReportCheckSamples(query)).split('\r\n')).toHaveLength(13)
    expect((await service.reportCheckSamples({ ...query, from: '2026-10-03', to: '2026-10-03' })).total).toBe(0)
    expect((await service.reportCheckSamples({ dateField: 'checkDate', to: '2026-10-02' })).total).toBe(14)
    expect(() => parseReportCheckQuery({ dateField: 'requestedTestDate' })).toThrow()
    expect(() => parseReportCheckQuery({ searchField: 'dataEntryPerson' })).toThrow()
  })
  it('uses the screenshot columns and keeps report checking facts separate from data checking', async () => {
    const state = seedRegistration(), before = structuredClone(state)
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    expect(reportCheckColumns.map(column => column.label)).toEqual(['样品编号', '报告编号', '样品类型', '委托编号', '更改次数', '样品/工程名称', '检测参数', '当前数据状态', '检测方案', '校核人', '校核日期', '附件', '结论', '委托单位', '委托人', '项目名称', '试验人1', '试验人2', '试验开始日期', '试验结束日期', '委托日期'])
    expect((await service.reportCheckSamples({ checkStatus: '未校核' })).items.some(row => row.id === 'demo-yp-82')).toBe(true)
    const checked = (await service.reportCheckSamples({ contains: '0083', checkStatus: '已校核' })).items[0]!
    expect(checked).toMatchObject({ checker: '王复核', changeCount: 1, canCheck: false, canUndoCheck: true })
    expect(state).toEqual(before)
    const sample = state.samples.find(row => row.id === 'demo-yp-83')!
    delete sample.reportCheckInfo; delete sample.reportChangeCount
    sample.dataCheckInfo = { actorId: 'analyst', actorName: '数据校核人', at: '2026-01-01', previousDataStatus: '检测数据录入完成' }
    expect((await service.reportCheckSamples({ contains: '0083' })).items[0]).toMatchObject({ checker: '', checkDate: '', changeCount: null })
  })
  it('filters status, dates, plans and exports only the same matching rows', async () => {
    const state = seedRegistration(), service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const query = { checkStatus: '未校核', plans: { groupIds: [], planIds: ['general-1'], excludedPlanIds: [] } } as const
    const input = { ...query, plans: { groupIds: [], planIds: ['general-1'], excludedPlanIds: [] } }
    const rows = await service.reportCheckSamples(input)
    expect(rows.items.some(row => row.id === 'demo-yp-82')).toBe(true)
    expect(rows.items.every(row => row.checkStatus === '未校核' && row.projectName === '常规检测方案')).toBe(true)
    expect((await service.exportReportCheckSamples(input)).split('\r\n')).toHaveLength(rows.total + 1)
    expect((await service.exportReportCheckSamples({ ...input, ids: ['demo-yp-82'] })).split('\r\n')).toHaveLength(2)
    expect((await service.reportCheckSamples({ status: '报告校核中', checkStatus: '已校核' })).total).toBe(0)
    expect((await service.reportCheckSamples({ dateField: 'testEndDate', from: '2099-01-01' })).total).toBe(0)
    const selection = await service.testPlanSelection({ groupIds: [], planIds: [], excludedPlanIds: [] }, undefined, 'report-check')
    expect(selection.populated!.total).toBeGreaterThan(0)
  })
  it('validates filters, excludes voided rows and applies report read permissions and department scope', async () => {
    for (const input of [{ checkStatus: '通过' }, { status: '检测数据校核中' }, { dateField: '打印日期' }, { from: '2026-02-30' }]) expect(() => parseReportCheckQuery(input)).toThrow()
    const state = seedRegistration(), current: Actor = { id: 'reports-only', name: '报告人员', roles: ['reports'], scope: 'department', departmentId: 'lab' }
    const service = createRegistrationService({ actor: () => current, read: () => state })
    expect((await service.reportCheckSamples({ contains: '0084' })).total).toBe(0)
    expect((await service.reportCheckSamples({ contains: '0082' })).total).toBe(1)
    state.samples.find(row => row.id === 'demo-yp-82')!.status = 'void_pending'
    expect((await service.reportCheckSamples({ contains: '0082' })).total).toBe(0)
    current.roles = ['commissions']
    await expect(service.reportCheckSamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
    await expect(service.exportReportCheckSamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
  })
})
