import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'
import { emptyTrialForm } from '../../src/types/testing/dataEntryDetail'
import { sampleCopyStates, sampleCopyNextState, sampleCopyTargetStates, availableSampleCopyStates } from '../../src/types/testing/sampleCopy'
import { parseSampleCopyQuery, parseSampleCopyInput } from '../../server/testingSampleCopy'
import { seedReportLifecycleDemo } from '../../server/reportLifecycleDemo'

describe('sample copy list', () => {
  it('resets later approvals on copied drafts and entry tasks while preserving source files and earlier review facts', async () => {
    let state = seedRegistration()
    await seedReportLifecycleDemo(state)
    const source = state.samples.find(row => row.id === 'demo-yp-91')!
    source.workflow = { ...source.workflow, checkDate: '2026-10-01', auditDate: '2026-10-01', approvalDate: '2026-10-01', issueDate: '2026-10-02', archiveDate: '2026-10-02' }
    const original = structuredClone(source)
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state, write: next => { state = next } })
    for (const [index, status] of ['委托登记中', '委托登记完成', '检测数据录入中', '检测数据录入完成', '报告审核完成'].entries()) {
      const copy = await service.copySample(source.id, { requestId: crypto.randomUUID(), version: source.version, sampleType: '分项/阶段性报告样品', dataStatus: status, testingDepartment: '', reportSuffix: `-RESET-${index}` })
      expect(copy.reportApprovalInfo).toBeUndefined()
      expect(copy.reportRelease).toBeUndefined()
      expect(copy.workflow?.approvalDate).toBeUndefined()
      expect(copy.workflow?.issueDate).toBeUndefined()
      expect(copy.workflow?.archiveDate).toBeUndefined()
      expect(state.dataEntries?.[copy.id]?.files).toEqual(state.dataEntries?.[source.id]?.files)
      if (status.startsWith('委托登记')) {
        expect(copy.reviewStatus).toBe('unreviewed')
        expect(copy.contractReview).toBeUndefined()
      }
      if (status === '委托登记中') expect(await service.act('samples', copy.id, 'complete', copy.version)).toMatchObject({ dataStatus: '完成登记' })
      if (status === '检测数据录入完成') expect((await service.dataCheckSamples({ ids: [copy.id] })).items[0]?.canCheck).toBe(true)
      if (status === '报告审核完成') {
        expect(copy.reportReviewInfo).toEqual(source.reportReviewInfo)
        expect((await service.reportCheckSamples({ ids: [copy.id] }, 'approval')).items[0]?.canCheck).toBe(true)
      } else {
        expect(copy.reportCheckInfo).toBeUndefined()
        expect(copy.reportReviewInfo).toBeUndefined()
        expect(copy.workflow?.checkDate).toBeUndefined()
        expect(copy.workflow?.auditDate).toBeUndefined()
      }
    }
    expect(state.samples.find(row => row.id === source.id)).toEqual(original)
  })
  it('exports current printing and distribution facts, excluding recipients, undone operations and old report versions', async () => {
    const state = seedRegistration()
    await seedReportLifecycleDemo(state)
    const sample = state.samples.find(row => row.id === 'demo-yp-91')!, release = sample.reportRelease!
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const row = async () => (await service.sampleCopySamples({ ids: [sample.id] })).items[0]!
    const empty = { printDate: '', printPerson: '', distributionDate: '', distributionPerson: '' }
    expect(await row()).toMatchObject(empty)
    release.printStatus = '打印完成'
    release.history.push(
      { at: '2026-10-01T00:00:00Z', actorId: 'old', actorName: '原打印员', action: '打印完成', reason: '' },
      { at: '2026-10-01T17:00:00Z', actorId: 'printer', actorName: '打印员', action: '打印完成', reason: '' },
    )
    release.distributionStatus = '已发放'
    release.receipt = { recipient: '客户接收人', method: '领取', date: '2026-10-03', notes: '', at: '2026-10-03T01:00:00Z', actorId: 'distributor', actorName: '发放员' }
    expect(await row()).toMatchObject({ printDate: '2026-10-02', printPerson: '打印员', distributionDate: '2026-10-03', distributionPerson: '发放员' })
    const csv = await service.exportSampleCopySamples({ ids: [sample.id] })
    expect(csv.split('\r\n')[0]).toContain('"批准人","打印日期","打印人","发放日期","发放人","归档日期"')
    expect(csv.split('\r\n')[0]).not.toMatch(/签发日期|签发人/)
    expect(csv).toContain('"2026-10-02","打印员","2026-10-03","发放员"')
    release.form = '电子'; release.printStatus = '不适用'
    expect(await row()).toMatchObject({ printDate: '', printPerson: '', distributionDate: '2026-10-03', distributionPerson: '发放员' })
    release.form = '纸质'; release.printStatus = '待打印'; release.distributionStatus = '未发放'
    expect(await row()).toMatchObject(empty)
    sample.reportReleaseHistory = [structuredClone(release)]
    delete sample.reportRelease
    expect(await row()).toMatchObject(empty)
  })
  it('limits copy destinations to the source report progress, including approval completion', async () => {
    for (const [sourceStatus, count] of [['委托登记中', 1], ['完成登记', 2], ['委托复核中', 2], ['检测数据录入中', 3], ['检测数据录入完成', 4], ['报告审核中', 4], ['报告审核完成', 5], ['报告批准中', 5], ['报告批准完成', 6], ['报告打印完成', 6]] as const) {
      let state = seedRegistration()
      const source = state.samples[75]!
      source.dataStatus = sourceStatus
      const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state, write: next => { state = next } })
      const row = (await service.sampleCopySamples({ ids: [source.id] })).items[0]!
      expect(availableSampleCopyStates(row.dataStatus)).toEqual(sampleCopyTargetStates.slice(0, count))
      for (const [index, dataStatus] of sampleCopyTargetStates.entries()) {
        const input = { requestId: crypto.randomUUID(), version: source.version, sampleType: '分项/阶段性报告样品', dataStatus, testingDepartment: '', reportSuffix: `-PROGRESS-${index}` }
        const before = state.samples.length
        if (index < count) expect(await service.copySample(source.id, input)).toMatchObject({ dataStatus })
        else {
          await expect(service.copySample(source.id, input)).rejects.toThrow('不能超过原报告当前进度')
          expect(state.samples).toHaveLength(before)
        }
      }
    }
    expect(sampleCopyNextState('报告批准完成')).toBe('报告打印中')
  })
  it('copies all stored sample content independently, sets destination fields, and makes retries idempotent', async () => {
    let state = seedRegistration()
    const source = state.samples[75]!, id = source.id
    source.details!.testingDepartment = '原检测部门'
    source.attachments = [{ id: 'file-source', name: '附件.txt', type: 'text/plain', dataUrl: 'data:text/plain;base64,YQ==', size: 1 }]
    state.dataEntries = { [id]: { version: 2, reportRevision: 1, form: emptyTrialForm(), files: [], events: [], requests: [] } }
    state.dataEntries[id]!.form.conclusion = '复制检测结论'
    state.originalRecords = { [id]: { version: 1, records: [{ id: 'original', name: '原始记录', source: 'file', files: structuredClone(source.attachments) }], migratedFileIds: [], requests: [], events: [] } }
    const sourceBefore = structuredClone(source)
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state, write: next => { state = next } })
    const input = { requestId: 'copy-test-request-0001', version: source.version, sampleType: '分项/阶段性报告样品', dataStatus: '委托登记中', testingDepartment: '实验室', reportSuffix: '-PART' }
    for (const [dataStatus, next] of [['委托登记中', '委托登记完成'], ['委托登记完成', '委托复核中'], ['检测数据录入中', '检测数据录入完成'], ['检测数据录入完成', '检测数据校核中'], ['报告审核完成', '报告批准中']]) {
      expect(parseSampleCopyInput({ ...input, dataStatus }).dataStatus).toBe(dataStatus)
      expect(sampleCopyNextState(dataStatus!)).toBe(next)
    }
    const copy = await service.copySample(id, input)
    expect(copy).toMatchObject({ reportCode: source.reportCode + '-PART', sampleType: input.sampleType, status: 'pending', dataStatus: '委托登记中', copyInfo: { sourceId: id, pendingStatus: '委托登记完成' } })
    expect(copy.id).not.toBe(id); expect(copy.code).not.toBe(source.code)
    expect(copy.attachments).toEqual(source.attachments)
    expect(copy.details?.testingDepartment).toBe('实验室')
    expect(state.dataEntries?.[copy.id]).toEqual(state.dataEntries?.[id])
    expect(state.originalRecords?.[copy.id]).toEqual(state.originalRecords?.[id])
    expect(state.samples.find(row => row.id === id)).toEqual(sourceBefore)
    expect((await service.copySample(id, input)).id).toBe(copy.id)
    await expect(service.copySample(id, { ...input, reportSuffix: 'changed' })).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    await expect(service.copySample(id, { ...input, requestId: 'copy-test-duplicate-1' })).rejects.toThrow('报告编号已存在')
    state.dataEntries![copy.id]!.form.conclusion = '只更改复制件'
    expect(state.dataEntries![id]!.form.conclusion).toBe('复制检测结论')
    for (const [sampleType, suffix] of [['英文报告样品', '(E)'], ['补充报告', 'BC']]) {
      const result = await service.copySample(id, { ...input, requestId: crypto.randomUUID(), sampleType, testingDepartment: '无效部门', reportSuffix: '-IGNORE' })
      expect(result.reportCode).toBe(source.reportCode + suffix)
      expect(result.details?.testingDepartment).toBe('原检测部门')
    }
  })
  it('rejects unauthorized, stale and invalid copy submissions without changing storage', async () => {
    const state = seedRegistration(), source = state.samples[75]!
    const input = { requestId: 'copy-test-request-0002', version: source.version, sampleType: '分项/阶段性报告样品', dataStatus: '委托登记中', testingDepartment: '', reportSuffix: '-TEST' }
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state, write: () => { throw new Error('must not write') } })
    for (const patch of [{ reportSuffix: ' ' }, { dataStatus: '终止' }, { dataStatus: '委托复核中' }, { dataStatus: '检测数据校核中' }, { dataStatus: '报告批准中' }, { sampleType: '原始样品' }, { version: -1 }, { requestId: '' }, { testingDepartment: '不存在' }]) {
      await expect(service.copySample(source.id, { ...input, ...patch })).rejects.toThrow()
    }
    const noWrite = createRegistrationService({ actor: () => demoActors.find(actor => actor.id === 'approver')!, read: () => state })
    await expect(noWrite.copySample(source.id, input)).rejects.toMatchObject({ code: 'FORBIDDEN' })
    const other = createRegistrationService({ actor: () => demoActors.find(actor => actor.id === 'other')!, read: () => state })
    await expect(other.copySample(source.id, input)).rejects.toMatchObject({ code: 'NOT_FOUND' })
    source.status = 'voided'
    await expect(service.copySample(source.id, input)).rejects.toThrow('状态不允许复制')
  })
  it('filters saved workflow dates before pagination and export without falling back to commission dates', async () => {
    for (const dateField of ['checkDate', 'auditDate', 'approvalDate', 'issueDate', 'archiveDate'] as const) {
      const state = seedRegistration(), source = state.samples[75]!
      state.samples = Array.from({ length: 14 }, (_, index) => ({ ...structuredClone(source), id: `date-${index}`, code: `DATE${index}`, workflow: { ...source.workflow, [dateField]: index < 11 ? '2026-10-01' : index === 11 ? '2026-10-02' : undefined } }))
      const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
      const query = { dateField, from: '2026-10-01', to: '2026-10-01', page: 2, pageSize: 10 }
      expect(parseSampleCopyQuery(query).dateField).toBe(dateField)
      expect(await service.sampleCopySamples(query)).toMatchObject({ total: 11, page: 2 })
      expect((await service.sampleCopySamples(query)).items).toHaveLength(1)
      expect((await service.exportSampleCopySamples(query)).split('\r\n')).toHaveLength(12)
      expect((await service.sampleCopySamples({ dateField, from: '2026-10-02' })).total).toBe(1)
      expect((await service.sampleCopySamples({ dateField })).total).toBe(14)
    }
    for (const dateField of ['printDate', 'requestedTestDate']) expect(() => parseSampleCopyQuery({ dateField })).toThrow()
    expect(() => parseSampleCopyQuery({ dateField: 'issueDate', from: '2026-02-30' })).toThrow()
  })
  it('queries every screenshot workflow state and uses matching plan counts without changing stored state names', async () => {
    const state = seedRegistration(), source = state.samples[75]!
    state.samples = sampleCopyStates.map((status, index) => ({ ...structuredClone(source), id: `state-${index}`, code: `STATE${index}`, dataStatus: status }))
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    for (const status of sampleCopyStates) {
      expect(parseSampleCopyQuery({ status }).status).toBe(status)
      expect((await service.sampleCopySamples({ status })).items.map(row => row.dataStatus)).toEqual([status])
      expect((await service.exportSampleCopySamples({ status })).split('\r\n')).toHaveLength(2)
    }
    for (const [stored, displayed] of [['完成登记', '委托登记完成'], ['合同评审中', '委托复核中'], ['评审完成', '委托复核完成']]) {
      state.samples = [{ ...structuredClone(source), dataStatus: stored! }]
      expect((await service.sampleCopySamples({ status: displayed })).total).toBe(1)
      expect(state.samples[0]!.dataStatus).toBe(stored)
    }
    for (const status of ['voided', 'void_pending'] as const) {
      state.samples = [{ ...structuredClone(source), status }]
      expect((await service.sampleCopySamples()).items[0]).toMatchObject({ canCopy: false, dataStatus: status === 'voided' ? '委托已作废' : '委托作废申请中' })
      expect((await service.dataEntrySamples()).total).toBe(0)
    }
    state.samples = [{ ...structuredClone(source), dataStatus: '报告审核中' }]
    const selection = await service.testPlanSelection({ groupIds: [], planIds: [], excludedPlanIds: [] }, undefined, 'sample-copy')
    expect(selection.populated?.total).toBe(1)
    expect((await service.testPlans({ parentId: 'general' })).items.find(row => row.id === 'general-1')?.sampleCopySampleCount).toBe(1)
    for (const searchField of ['contact', 'dataEntryPerson']) expect(() => parseSampleCopyQuery({ searchField })).toThrow()
  })
  it('maps saved lifecycle, trial and price facts without inventing missing values or modifying samples', async () => {
    const state = seedRegistration(), sample = state.samples[75]!
    sample.flowInfo = { collection: { name: '领样员', date: '2026-09-20' } }
    sample.outboundInfo = { receipt: { account: 'admin', name: '出库员', date: '2026-09-19', recordedAt: '', recordedBy: { id: 'admin', name: '演示用户' } } }
    sample.details!.standardPrice = '125.50'; sample.details!.paymentStatus = '已收费'
    state.dataEntries = { [sample.id]: { version: 1, reportRevision: 1, form: { ...emptyTrialForm(), conclusion: '检测结果满足要求', failedParameters: '参数甲' }, files: [], events: [], requests: [] } }
    const before = structuredClone(state)
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const row = (await service.sampleCopySamples({ contains: sample.code })).items[0]!
    expect(row).toMatchObject({ collectionPerson: '领样员', collectionDate: '2026-09-20', outboundPerson: '出库员', outboundDate: '2026-09-19', standardPrice: 125.5, paymentStatus: '已收费', conclusion: '检测结果满足要求', failedParameters: '参数甲', changeCount: null, reportDeliveryStatus: '', reportArchiveStatus: '', auditor: '', discountPrice: null, actualPrice: null })
    const csv = await service.exportSampleCopySamples({ ids: [sample.id] })
    expect(csv).toContain('"125.50"'); expect(csv).toContain('检测结果满足要求')
    expect(csv.split('\r\n')[0]!.split(',')).toHaveLength(47)
    expect(state).toEqual(before)
  })
  it('uses entry filters, scoped pagination and complete exports with independent copy permissions', async () => {
    const state = seedRegistration(), source = state.samples[75]!
    state.samples = Array.from({ length: 23 }, (_, index) => ({ ...structuredClone(source), id: `copy-${index}`, code: `COPY${String(index).padStart(2, '0')}` }))
    let actor = demoActors[0]!
    const service = createRegistrationService({ actor: () => actor, read: () => state })
    expect((await service.sampleCopySamples({ page: 3, pageSize: 10 })).items).toHaveLength(3)
    expect((await service.sampleCopySamples({ contains: 'COPY03' })).items[0]).toMatchObject({ id: 'copy-3', canCopy: true })
    expect((await service.sampleCopySamples({ dateField: 'commissionDate', from: '2000-01-01', to: '2000-12-31' })).total).toBe(0)
    expect((await service.sampleCopySamples({ plans: { groupIds: [], planIds: ['thermal-1'], excludedPlanIds: [] } })).total).toBe(0)
    expect((await service.exportSampleCopySamples({ page: 3 })).split('\r\n')).toHaveLength(24)
    expect(await service.exportSampleCopySamples({ ids: ['copy-3'] })).not.toContain('COPY04')
    actor = demoActors.find(row => row.id === 'approver')!
    expect((await service.sampleCopySamples()).items.every(row => !row.canCopy)).toBe(true)
    actor = demoActors.find(row => row.id === 'other')!
    expect((await service.sampleCopySamples()).total).toBe(0)
    expect(await service.exportSampleCopySamples()).not.toContain('COPY03')
    actor = demoActors.find(row => row.id === 'business')!
    await expect(service.sampleCopySamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
    await expect(service.exportSampleCopySamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
  })
})
