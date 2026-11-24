import { describe, expect, it } from 'vitest'
import { seedRegistration, createRegistrationService } from '../../server/registrationDomain'
import { parsePickupQuery, pickupRows } from '../../server/testingPickup'
import { demoActors } from '../../src/services/storage/demoActors'
import { pickupColumns } from '../../src/types/testing/pickup'
import { sampleReportConfig } from '../../server/sampleReportSettings'

describe('testing sample pickup queries', () => {
  it('validates pickup fields, state, permissions and scope without writing on failure', async () => {
    let state = seedRegistration(), actor = { ...demoActors[2]! }, locked = false
    const service = createRegistrationService({ actor: () => actor, locked: () => locked, read: () => state, write: next => { state = next } })
    const receipt = { account: 'business', name: '张受理', date: '2026-09-27' }
    async function rejected(code: string, input: unknown = receipt, version = 1) {
      const before = structuredClone(state)
      await expect(service.pickupAction('demo-yp-20', version, input)).rejects.toMatchObject({ code })
      expect(state).toEqual(before)
    }
    for (const field of ['account', 'name', 'date']) await rejected('VALIDATION', { ...receipt, [field]: '' })
    await rejected('VALIDATION', { ...receipt, account: 'unknown' })
    await rejected('VALIDATION', { ...receipt, name: '错误姓名' })
    await rejected('VALIDATION', { ...receipt, date: '2026-02-30' })
    await rejected('BAD_REQUEST', receipt, 0)
    actor = { ...actor, roles: ['approver'] }; await rejected('FORBIDDEN')
    expect((await service.pickupSamples()).items.every(row => !row.canPickup)).toBe(true)
    actor = { ...demoActors[10]! }; await rejected('NOT_FOUND')
    actor = { ...demoActors[2]! }
    for (const status of ['voided', 'void_pending'] as const) { state.samples[19]!.status = status; await rejected('BUSINESS_RULE') }
    state.samples[19]!.status = 'completed'
    for (const status of ['样品已领取', '样品出库中', '任务分配完成']) { state.samples[19]!.dataStatus = status; await rejected('BUSINESS_RULE') }
    state.samples[19]!.dataStatus = '样品待领取'; locked = true; await rejected('LOCKED'); locked = false
    expect((await service.pickupSamples()).items.find(row => row.id === 'demo-yp-20')!.canPickup).toBe(true)
    const result = await service.pickupAction('demo-yp-20', 1, receipt)
    expect(result).toMatchObject({ dataStatus: '样品已领取', version: 2, flowInfo: { collection: { ...receipt, recordedBy: { id: 'analyst', name: '李检测' } } } })
    expect(result.flowInfo!.collection!.recordedAt).toBeTruthy()
    expect(result.events.at(-1)).toMatchObject({ action: '领取样品', actor: '李检测' })
    expect((await service.flowSamples({ code: result.code })).items[0]).toMatchObject({ collectionPerson: '张受理', collectionDate: receipt.date, flowStatus: '样品已领取' })
    await rejected('BUSINESS_RULE')
    await rejected('BUSINESS_RULE', receipt, 2)
  })
  it('filters actual pickup workflow states without changing assignment queries or source facts', async () => {
    const state = seedRegistration(), before = structuredClone(state)
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const all = await service.pickupSamples({}), pending = await service.pickupSamples({ status: '样品待领取' }), collected = await service.pickupSamples({ status: '样品已领取' })
    expect(pending.total).toBe(3); expect(collected.total).toBe(3); expect(all.total).toBe(6)
    expect(pending.items.every(row => row.dataStatus === '样品待领取')).toBe(true)
    expect((await service.assignmentSamples({})).total).toBe(15)
    expect(state).toEqual(before)
    const item = pending.items[0]!
    expect(item.inspector).toBe('')
    expect(item).not.toHaveProperty('canAssign')
    expect((await service.pickupSamples({ contains: item.code.toLowerCase() })).items.map(row => row.id)).toEqual([item.id])
    const exported = await service.exportPickupSamples({ ids: [item.id] })
    expect(exported).not.toContain('采集状态'); expect(exported).toContain('指定主检人'); expect(exported).toContain(item.code)
    expect(exported.trim().split('\r\n')).toHaveLength(2)
    expect(exported.split('\r\n')[0]).not.toContain('检测人2')
  })
  it('uses the saved inspector field and shared content, conclusion and date filters', () => {
    const state = seedRegistration(), sample = state.samples[19]!
    sample.details!.inspector = '样品单主检人'
    sample.details!.requestedTestDate = '2026-09-27'
    sample.assignmentInfo = { assignedBy: '分配人员', tester1: '另一检测人', dataEntryPerson: '数据录入人员', conclusion: '复检' }
    sample.details!.reportSettings.titleId = sampleReportConfig.options.titleId[0]!.id
    const sources = [{ ...sample, commissionCode: 'WT-PICKUP', commissionName: '项目名称示例' }]
    const query = { status: '样品待领取', conclusion: '复检', dateField: 'requestedTestDate' as const, from: '2026-09-27', to: '2026-09-27' }
    const row = pickupRows(sources, query)[0]!
    expect(row).toMatchObject({ inspector: '样品单主检人', assignedBy: '分配人员', reportTitle: sampleReportConfig.options.titleId[0]!.label })
    expect(pickupRows(sources, { ...query, from: '2026-09-28' })).toHaveLength(0)
    for (const [searchField, contains] of [['commissionCode', 'WT-PICKUP'], ['engineeringName', '项目名称'], ['dataEntryPerson', '录入人员']] as const) expect(pickupRows(sources, { ...query, searchField, contains })).toHaveLength(1)
    sample.details!.requestedTestDate = ''
    expect(pickupRows([{ ...sample, commissionCode: '', commissionName: '' }], query)).toHaveLength(0)
    for (const status of ['void_pending', 'voided'] as const) expect(pickupRows([{ ...sources[0]!, status }], {})).toHaveLength(0)
    expect(pickupColumns.map(column => column.label)).toEqual(['样品编号', '报告编号', '样品类型', '样品/工程名称', '检测参数', '当前数据状态', '检测方案', '报告标题', '分配人', '指定主检人', '委托日期', '要求试验日期'])
  })
  it('validates query input and enforces read roles and department scope', async () => {
    for (const input of [{ status: '任务分配中' }, { dateField: 'unknown' }, { searchField: 'inspector' }, { from: '2026-02-30' }, { from: '2026-09-28', to: '2026-09-27' }]) expect(() => parsePickupQuery(input)).toThrow()
    const denied = createRegistrationService({ actor: () => demoActors.find(actor => actor.id === 'business')! })
    await expect(denied.pickupSamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
    await expect(denied.exportPickupSamples()).rejects.toMatchObject({ code: 'FORBIDDEN' })
    const other = createRegistrationService({ actor: () => demoActors.find(actor => actor.id === 'other')! })
    expect((await other.pickupSamples()).total).toBe(0)
    for (const name of ['analyst', 'reviewer', 'approver']) {
      const allowed = createRegistrationService({ actor: () => demoActors.find(actor => actor.id === name)! })
      expect((await allowed.pickupSamples()).total).toBe(6)
    }
  })
})
