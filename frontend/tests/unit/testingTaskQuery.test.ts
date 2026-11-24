import { describe, it, expect } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { taskQueryRows, parseTaskQuery } from '../../server/testingTaskQuery'
import { taskQueryColumns, taskQueryStates } from '../../src/types/testing/taskQuery'
import { demoActors } from '../../src/services/storage/demoActors'
import { emptyPlanSelection } from '../../src/types/samples/inbound'

describe('testing task query', () => {
  it('returns every listed stage to the backend destination and retains original facts', async () => {
    for (const stage of [...taskQueryStates, '完成登记', '合同评审中', '评审完成']) for (const type of ['commission', 'assignment'] as const) {
      let state = seedRegistration()
      const sample = state.samples[50]!
      sample.dataStatus = stage
      const before = structuredClone(state), returned = { type, reason: '信息需核对', details: '补充描述', date: '2026-09-27' }
      const service = createRegistrationService({ actor: () => demoActors[2]!, read: () => state, write: next => { state = next } })
      expect((await service.taskQuerySamples({ contains: sample.code })).items[0]!.canReturn).toBe(true)
      const result = await service.taskQueryReturn(sample.id, sample.version, returned)
      expect(result).toMatchObject({ version: sample.version + 1, dataStatus: type === 'commission' ? '委托登记中' : '完成登记', status: type === 'commission' ? 'pending' : 'completed', reviewStatus: 'unreviewed' })
      expect(result.taskReturns?.at(-1)).toMatchObject({ ...returned, previousDataStatus: stage, recordedBy: { id: 'analyst', name: '李检测' } })
      expect(result.events.at(-1)).toMatchObject({ action: '退回检测任务', actor: '李检测' })
      expect(result.assignmentInfo).toEqual(sample.assignmentInfo)
      expect(state.commissions).toEqual(before.commissions)
      const saved = structuredClone(state)
      if (type === 'commission') await expect(service.taskQueryReturn(sample.id, sample.version, returned)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
      if (type === 'commission') await expect(service.taskQueryReturn(sample.id, result.version, returned)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
      expect(state).toEqual(saved)
      if (type === 'assignment') {
        expect((await service.taskQuerySamples({ contains: sample.code })).items[0]!.canReturn).toBe(true)
        expect((await service.taskQueryReturn(sample.id, sample.version, { ...returned, type: 'commission' })).dataStatus).toBe('委托登记中')
      }
    }
  })
  it('rejects invalid fields, role, scope, void state and stale version without writes', async () => {
    let state = seedRegistration(), actor = { ...demoActors[2]! }
    const service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { state = next } })
    const returned = { type: 'commission', reason: '原因', details: '', date: '2026-09-27' }
    async function rejected(code: string, input: unknown = returned, version = 1) {
      const before = structuredClone(state)
      await expect(service.taskQueryReturn('demo-yp-51', version, input)).rejects.toMatchObject({ code })
      expect(state).toEqual(before)
    }
    await rejected('VALIDATION', { ...returned, type: 'unknown' })
    await rejected('VALIDATION', { ...returned, reason: '' })
    await rejected('VALIDATION', { ...returned, reason: 'x'.repeat(501) })
    await rejected('VALIDATION', { ...returned, details: 'x'.repeat(2001) })
    await rejected('VALIDATION', { ...returned, date: '2026-02-30' })
    await rejected('BAD_REQUEST', returned, 0)
    actor = { ...demoActors[4]! }; await rejected('FORBIDDEN')
    expect((await service.taskQuerySamples({ contains: 'SP2026090051' })).items[0]!.canReturn).toBe(false)
    actor = { ...demoActors[10]! }; await rejected('NOT_FOUND')
    actor = { ...demoActors[2]! }
    for (const status of ['void_pending', 'voided'] as const) { state.samples[50]!.status = status; await rejected('BUSINESS_RULE') }
    state.samples[50]!.status = 'completed'
    for (const status of ['委托登记中', '任务已取消', '终止', '未知状态']) { state.samples[50]!.dataStatus = status; await rejected('BUSINESS_RULE') }
  })
  it('prints from assignment onward, retaining saved personnel for later stages and blanking pending assignments', async () => {
    const state = seedRegistration(), sample = state.samples[50]!
    sample.assignmentInfo = { assignedBy: '分配员', assignedById: 'admin', dataEntryPerson: '录入员', tester1: '检测员1', tester2: '检测员2', assignedDate: '2026-09-26' }
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state })
    const printable = ['任务分配中', '任务分配完成', '任务处理中', '任务处理完成', '检测数据录入中']
    for (const stage of taskQueryStates) {
      sample.dataStatus = stage
      const row = (await service.taskQuerySamples({ contains: sample.code })).items[0]!
      const source = await service.taskPrintSource(sample.id)
      expect(row.canPrintTask).toBe(printable.includes(stage))
      expect(source.canPrint).toBe(row.canPrintTask)
      if (source.canPrint && stage !== '任务分配中') {
        expect(source.snapshot).toMatchObject(sample.assignmentInfo)
      } else {
        for (const field of ['assignedById', 'assignedBy', 'dataEntryPerson', 'tester1', 'tester2', 'assignedDate'] as const) expect(source.snapshot[field]).toBe('')
      }
    }
    for (const status of ['voided', 'void_pending'] as const) {
      sample.status = status
      expect((await service.taskQuerySamples({ contains: sample.code })).total).toBe(0)
      await expect(service.taskPrintSource(sample.id)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    }
  })
  it('maps screenshot labels to saved facts and supports every visible state', () => {
    const sample = seedRegistration().samples[19]!
    sample.details!.inspector = '指定人员'
    const source = { ...sample, commissionCode: 'WT-1', commissionName: '项目名称示例' }
    for (const dataStatus of taskQueryStates) {
      expect(taskQueryRows([{ ...source, dataStatus }], { status: dataStatus })[0]).toMatchObject({ dataStatus, inspector: '指定人员', engineeringName: '项目名称示例', projectName: sample.details!.testPlan })
    }
    for (const [raw, label] of [['完成登记', '委托登记完成'], ['合同评审中', '委托复核中'], ['评审完成', '委托复核完成']]) {
      expect(taskQueryRows([{ ...source, dataStatus: raw! }], { status: label })[0]!.dataStatus).toBe(label)
    }
    expect(taskQueryRows([{ ...source, status: 'void_pending' }], {})).toEqual([])
    expect(taskQueryRows([{ ...source, status: 'voided' }], {})).toEqual([])
    expect(taskQueryColumns.map(column => column.label)).toEqual(['样品编号', '报告编号', '样品类型', '样品/工程名称', '检测参数', '当前数据状态', '检测方案', '报告标题', '分配人', '指定主检人', '委托人', '委托人电话', '委托日期', '委托单位', '项目名称', '工程地址', '要求试验日期'])
    expect(() => parseTaskQuery({ status: 'invalid' })).toThrow()
    expect(() => parseTaskQuery({ from: '2026-02-30' })).toThrow()
  })
  it('uses shared query filters, export, department scope and task-print eligibility', async () => {
    const state = seedRegistration(), before = structuredClone(state)
    let actor = { ...demoActors[0]! }
    const service = createRegistrationService({ actor: () => actor, read: () => state })
    const all = await service.taskQuerySamples({ pageSize: 50 })
    expect(all.total).toBeGreaterThan(12)
    const assigned = await service.taskQuerySamples({ status: '任务分配完成' })
    expect(assigned.items.every(row => row.canPrintTask)).toBe(true)
    expect((await service.taskQuerySamples({ status: '样品已领取' })).items.every(row => !row.canPrintTask)).toBe(true)
    const first = assigned.items[0]!, plans = { ...emptyPlanSelection(), planIds: ['general-1'] }
    const query = { status: '任务分配完成', plans, contains: first.code, searchField: 'code' as const }
    expect((await service.taskQuerySamples(query)).items.map(row => row.id)).toEqual([first.id])
    expect((await service.exportTaskQuerySamples(query)).trim().split('\r\n')).toHaveLength(2)
    expect((await service.taskQuerySamples({ status: '委托登记完成' })).items.every(row => row.dataStatus === '委托登记完成')).toBe(true)
    expect(await service.testPlanSelection(emptyPlanSelection(), { kind: 'all', id: '', checked: true, populatedOnly: true }, 'task-query')).toHaveProperty('populated')
    actor = { ...demoActors[10]! }
    expect((await service.taskQuerySamples({ contains: first.code })).total).toBe(0)
    await expect(service.taskQuerySamples({ plans })).rejects.toMatchObject({ code: 'NOT_FOUND' })
    actor = { ...demoActors[1]! }
    await expect(service.taskQuerySamples({})).rejects.toMatchObject({ code: 'FORBIDDEN' })
    await expect(service.exportTaskQuerySamples({})).rejects.toMatchObject({ code: 'FORBIDDEN' })
    expect(state).toEqual(before)
  })
})
