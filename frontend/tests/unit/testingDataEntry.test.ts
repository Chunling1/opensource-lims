import { describe, it, expect } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { dataEntryRows, parseDataEntryQuery } from '../../server/testingDataEntry'
import { dataEntryColumns, dataEntryStates } from '../../src/types/testing/dataEntry'
import { demoActors } from '../../src/services/storage/demoActors'
import { createDataEntryService } from '../../server/dataEntryDetail'
import { isDataEntrySample } from '../../server/testingDataEntry'

describe('testing data-entry list', () => {
  it('provides valid report templates for every seeded data-entry sample, including collected samples', () => {
    const state = seedRegistration()
    const service = createDataEntryService({ actor: () => demoActors[0]!, read: () => state })
    const samples = state.samples.filter(isDataEntrySample)
    expect(samples.filter(sample => sample.dataStatus === '样品已领取')).toHaveLength(3)
    for (const sample of samples) {
      const detail = service.detail(sample.id)
      expect(detail.template.error, sample.code).toBeUndefined()
      expect(detail.layouts.map(layout => layout.id), sample.code).toContain(detail.layoutId)
    }
  })
  it('uses registration void permissions and application workflow for both entry stages', async () => {
    for (const index of [75, 76]) {
      let state = seedRegistration(), actor = demoActors.find(actor => actor.id === 'reviewer')!
      const sample = structuredClone(state.samples[index]!)
      const service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { state = next } })
      expect((await service.dataEntrySamples()).items.find(row => row.id === sample.id)?.canVoid).toBe(false)
      await expect(service.act('samples', sample.id, 'void', sample.version, '需作废')).rejects.toMatchObject({ code: 'BUSINESS_RULE', message: '当前身份或记录状态不允许此操作。' })
      actor = demoActors.find(actor => actor.id === 'analyst')!
      expect((await service.dataEntrySamples()).items.find(row => row.id === sample.id)?.canVoid).toBe(true)
      const before = structuredClone(state)
      await expect(service.act('samples', sample.id, 'void', sample.version, '')).rejects.toBeDefined()
      expect(state).toEqual(before)
      await service.act('samples', sample.id, 'void', 999, '重复登记，申请作废')
      const saved = state.samples.find(row => row.id === sample.id)!
      expect(saved).toMatchObject({ status: 'void_pending', dataStatus: '作废申请中', voidApplication: { reason: '重复登记，申请作废', previousStatus: sample.status, previousDataStatus: sample.dataStatus } })
      expect(saved.dataEntryInfo).toEqual(sample.dataEntryInfo)
      expect(saved.assignmentInfo).toEqual(sample.assignmentInfo)
      expect((await service.dataEntrySamples({ contains: sample.code })).total).toBe(0)
    }
  })
  it('maps saved fields without substituting assigned testers or missing dates', () => {
    const sample = seedRegistration().samples[75]!
    const source = { ...sample, commissionCode: 'WT-1', commissionName: '工程甲' }
    source.dataEntryInfo = { tester1: '实际试验员', tester2: '另一试验员' }
    const row = dataEntryRows([source], {})[0]!
    expect(row).toMatchObject({ projectName: '常规检测方案', engineeringName: '工程甲', inspector: '李检测', tester1: '实际试验员', tester2: '另一试验员', assignedDate: source.assignmentInfo!.assignedDate, testStartDate: source.workflow!.testStartDate, testEndDate: '' })
    expect(dataEntryRows([{ ...source, workflow: undefined, dataEntryInfo: undefined }], {})[0]).toMatchObject({ testStartDate: '', testEndDate: '', tester1: '', tester2: '' })
    for (const status of ['voided', 'void_pending'] as const) expect(dataEntryRows([{ ...source, status }], {})).toEqual([])
    expect(dataEntryRows([{ ...source, dataStatus: '任务分配中' }], {})).toEqual([])
    expect(dataEntryColumns).toHaveLength(20)
    expect(dataEntryColumns.find(column => column.key === 'projectName')!.default).toBe(false)
  })
  it('filters screenshot fields, all four dates, state and conclusion; validates query inputs', async () => {
    const state = seedRegistration(), before = structuredClone(state)
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    for (const status of dataEntryStates) expect((await service.dataEntrySamples({ status })).items).toHaveLength(status === '检测数据录入中' ? 4 : 1)
    const row = (await service.dataEntrySamples({ status: '检测数据录入完成' })).items[0]!
    for (const searchField of ['code', 'reportCode', 'commissionCode', 'customer', 'contact', 'engineeringName', 'dataEntryPerson'] as const) {
      expect(parseDataEntryQuery({ searchField }).searchField).toBe(searchField)
      expect((await service.dataEntrySamples({ status: row.dataStatus, searchField, contains: row[searchField].slice(0, 5) })).items[0]!.id).toBe(row.id)
      expect((await service.dataEntrySamples({ searchField, contains: '不存在的查询内容' })).total).toBe(0)
    }
    for (const dateField of ['commissionDate', 'requestedTestDate', 'testStartDate', 'testEndDate'] as const) {
      expect((await service.dataEntrySamples({ status: row.dataStatus, dateField, from: row[dateField], to: row[dateField] })).total).toBe(1)
      expect((await service.dataEntrySamples({ dateField, from: '2000-01-01', to: '2000-01-02' })).total).toBe(0)
    }
    expect((await service.dataEntrySamples({ conclusion: '合格' })).items[0]!.id).toBe(row.id)
    for (const input of [{ status: '任务分配中' }, { searchField: 'subprojectName' }, { dateField: 'assignedDate' }, { from: '2026-02-30' }, { from: '2026-09-28', to: '2026-09-01' }, { pageSize: 5 }]) expect(() => parseDataEntryQuery(input)).toThrow()
    expect(state).toEqual(before)
  })
  it('applies department, role and plan scopes to query, export and plan counts', async () => {
    const state = seedRegistration(); let actor = demoActors[0]!
    const service = createRegistrationService({ actor: () => actor, read: () => state })
    const result = await service.dataEntrySamples({ plans: { groupIds: [], planIds: ['general-1'], excludedPlanIds: [] } })
    expect(result.total).toBe(2)
    expect((await service.dataEntrySamples({ plans: { groupIds: [], planIds: ['thermal-1'], excludedPlanIds: [] } })).total).toBe(0)
    const csv = await service.exportDataEntrySamples({ ids: ['demo-yp-76'] })
    expect(csv).toContain('SP2026090076'); expect(csv).not.toContain('SP2026090077')
    expect(csv).toContain('试验开始日期'); expect(csv).toContain('检测方案')
    const plans = await service.testPlanSelection({ groupIds: [], planIds: [], excludedPlanIds: [] }, undefined, 'data-entry')
    expect(plans.populated?.total).toBe(2)
    actor = demoActors[10]!
    expect((await service.dataEntrySamples()).total).toBe(0)
    expect(await service.exportDataEntrySamples()).not.toContain('SP2026090076')
    actor = demoActors[4]!
    expect((await service.dataEntrySamples()).items.every(row => !row.canReturn)).toBe(true)
    actor = demoActors[1]!
    await expect(service.dataEntrySamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
    await expect(service.exportDataEntrySamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
  })
  it('reuses return validation for both entry stages and rejects stale versions without writing', async () => {
    for (const index of [75, 76]) {
      let state = seedRegistration(); const sample = state.samples[index]!
      const service = createRegistrationService({ actor: () => demoActors[2]!, read: () => state, write: next => { state = next } })
      const returned = { type: 'commission', reason: '需修正委托信息', details: '', date: '2026-09-28' }
      const before = structuredClone(state)
      expect(state).toEqual(before)
      const saved = await service.taskQueryReturn(sample.id, 999, returned)
      expect(saved.dataStatus).toBe('委托登记中')
      expect(saved.taskReturns?.at(-1)?.previousDataStatus).toBe(sample.dataStatus)
      expect(saved.dataEntryInfo).toEqual(sample.dataEntryInfo)
      expect(saved.assignmentInfo).toEqual(sample.assignmentInfo)
      expect((await service.dataEntrySamples({ contains: sample.code })).total).toBe(0)
    }
  })
  it('paginates after filtering and exports the full matching set', async () => {
    const state = seedRegistration(), sample = state.samples[75]!
    state.samples = Array.from({ length: 27 }, (_, index) => ({ ...structuredClone(sample), id: `entry-${index}`, code: `ENTRY${String(index).padStart(3, '0')}` }))
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const page = await service.dataEntrySamples({ page: 2, pageSize: 10, direction: 'desc' })
    expect(page.total).toBe(27); expect(page.items).toHaveLength(10)
    expect(page.items[0]!.code).toBe('ENTRY016')
    expect((await service.dataEntrySamples({ page: 2, pageSize: 20 })).items).toHaveLength(7)
    expect((await service.exportDataEntrySamples({ page: 2, pageSize: 10 })).trim().split('\r\n')).toHaveLength(28)
  })
})
