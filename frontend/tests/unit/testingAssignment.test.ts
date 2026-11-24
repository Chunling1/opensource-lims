import { describe, expect, it } from 'vitest'
import { assignmentRows, parseAssignmentQuery, parseAssignmentSubmission } from '../../server/testingAssignment'
import { seedRegistration, createRegistrationService } from '../../server/registrationDomain'
import type { Actor } from '../../src/types/lims'
import { emptySampleDetails } from '../../src/types/commissions/sampleForm'

describe('assignment saved facts and query boundaries', () => {
  it('reports sample attachment presence in the list and export without including file contents', async () => {
    let state = seedRegistration()
    const service = createRegistrationService({ actor: () => ({ id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }), locked: () => false, read: () => state, write: next => { state = next } })
    const sample = state.samples.find(row => row.id === 'demo-yp-51')!
    const query = { ids: [sample.id] }
    expect((await service.assignmentSamples(query)).items[0]!.attachmentCount).toBe(0)
    expect((await service.exportAssignmentSamples(query)).split('\r\n')[1]).toMatch(/,""$/)
    sample.attachments.push({ id: 'file1', name: '样品附件.txt', type: 'text/plain', size: 1, dataUrl: 'data:text/plain;base64,YQ==' })
    const row = (await service.assignmentSamples(query)).items[0]!
    expect(row.attachmentCount).toBe(1); expect(row).not.toHaveProperty('attachments')
    const csv = await service.exportAssignmentSamples(query)
    expect(csv.split('\r\n')[0]).toMatch(/,"附件"$/)
    expect(csv.split('\r\n')[1]).toMatch(/,"有"$/)
  })
  it('rejects undo outside completed assignments, actor scope or unlocked workspaces without writes', async () => {
    let state = seedRegistration(), locked = false
    let actor: Actor = { id: 'analyst', name: '李检测', roles: ['testing'], departmentId: 'lab', scope: 'department' }
    const service = createRegistrationService({ actor: () => actor, locked: () => locked, read: () => state, write: next => { state = next } })
    async function rejected(code: string) {
      const before = structuredClone(state)
      await expect(service.assignmentAction('demo-yp-51', 1, {}, 'undo')).rejects.toMatchObject({ code })
      expect(state).toEqual(before)
    }
    for (const dataStatus of ['任务分配中', '样品出库中', '样品已领取', '样品已处置']) {
      state.samples[50]!.dataStatus = dataStatus
      await rejected('BUSINESS_RULE')
    }
    state.samples[50]!.dataStatus = '任务分配完成'
    for (const status of ['voided', 'void_pending'] as const) {
      state.samples[50]!.status = status
      await rejected('BUSINESS_RULE')
    }
    state.samples[50]!.status = 'completed'
    state.samples[50]!.departmentId = 'lab2'
    await rejected('NOT_FOUND')
    state.samples[50]!.departmentId = 'lab'; locked = true
    await rejected('LOCKED')
    locked = false; actor = { ...actor, roles: ['reviewer'] }
    expect((await service.assignmentSamples({})).items.every(row => !row.canUndoAssign)).toBe(true)
    await rejected('FORBIDDEN')
  })
  it('resolves names and accounts, rejects ambiguity and duplicate testers but allows entry/test overlap', () => {
    const people = [{ id: 'one', name: '同名人员' }, { id: 'two', name: '同名人员' }, { id: 'three', name: '唯一姓名' }]
    const input = { account: 'one', name: '同名人员', dataEntryPerson: '唯一姓名', tester1: 'three', tester2: 'one', date: '2026-09-26' }
    expect(() => parseAssignmentSubmission({ ...input, name: '唯一姓名' }, people)).toThrow('工号与姓名不匹配')
    expect(() => parseAssignmentSubmission({ ...input, account: 'unknown' }, people)).toThrow('工号与姓名不匹配')
    expect(parseAssignmentSubmission(input, people)).toMatchObject({ dataEntryPersonId: 'three', tester1Id: 'three', tester2Id: 'one', tester2: '同名人员' })
    expect(() => parseAssignmentSubmission({ ...input, tester2: '同名人员' }, people)).toThrow('改填账号')
    expect(() => parseAssignmentSubmission({ ...input, tester2: '唯一姓名' }, people)).toThrow('重复')
    for (const key of ['account', 'name', 'dataEntryPerson', 'tester1']) {
      expect(() => parseAssignmentSubmission({ ...input, [key]: '' }, people)).toThrow('请检查')
    }
    expect(() => parseAssignmentSubmission({ ...input, tester1: '不存在' }, people)).toThrow('不存在')
    expect(parseAssignmentSubmission({ ...input, tester2: '' }, people).tester2Id).toBe('')
    expect(() => parseAssignmentSubmission({ ...input, date: '2026-02-30' }, people)).toThrow('分配日期')
  })
  it('does not write voided, pending-void, completed, out-of-scope or locked records', async () => {
    let state = seedRegistration(), locked = false
    let actor: Actor = { id: 'analyst', name: '李检测', roles: ['testing'], departmentId: 'lab', scope: 'department' }
    const service = createRegistrationService({ actor: () => actor, locked: () => locked, read: () => state, write: next => { state = next } })
    const input = { account: 'analyst', name: '李检测', dataEntryPerson: 'analyst', tester1: '李检测', tester2: '', date: '2026-09-26' }
    for (const status of ['voided', 'void_pending'] as const) {
      state.samples[50]!.status = status
      const before = structuredClone(state)
      await expect(service.assignmentAction('demo-yp-51', 1, input)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
      expect(state).toEqual(before)
    }
    state.samples[50]!.status = 'completed'; state.samples[50]!.dataStatus = '任务分配完成'
    await expect(service.assignmentAction('demo-yp-51', 1, input)).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    state.samples[50]!.dataStatus = '任务分配中'
    state.samples[50]!.departmentId = 'lab2'
    await expect(service.assignmentAction('demo-yp-51', 1, input)).rejects.toMatchObject({ code: 'NOT_FOUND' })
    state.samples[50]!.departmentId = 'lab'
    locked = true
    await expect(service.assignmentAction('demo-yp-51', 1, input)).rejects.toMatchObject({ code: 'LOCKED' })
    locked = false; actor = { ...actor, roles: ['approver'] }
    expect((await service.assignmentSamples({})).items.every(row => !row.canAssign)).toBe(true)
    await expect(service.assignmentAction('demo-yp-51', 1, input)).rejects.toMatchObject({ code: 'FORBIDDEN' })
  })
  it('searches address and report title and uses the chosen date without filling missing task staff', () => {
    const base = seedRegistration().samples[0]!
    const row = { ...base, dataStatus: '任务分配中', commissionCode: 'WT-001', commissionName: '工程名称示例',
      commissionInfo: { ...base.commissionInfo, commissionDate: '2026-01-01', projectAddress: '工程地址示例' },
      details: { ...emptySampleDetails(), requestedTestDate: '2026-02-01', appointmentDate: '2026-03-01', hasAppointment: true,
        reportSettings: { formatId: 'engineering', titleId: 'air-conditioning', languageId: 'zh', layoutId: 'standard' } } }
    const rows = [row, { ...row, id: 'void', status: 'voided' as const }, { ...row, id: 'pending-void', status: 'void_pending' as const }, { ...row, id: 'other-stage', dataStatus: '样品入库中' }]
    const result = assignmentRows(rows, {})
    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({ assignedBy: '', dataEntryPerson: '', tester1: '', tester2: '', reportTitle: '空调中心', appointmentDate: '2026-03-01' })
    expect(assignmentRows(rows, { searchField: 'projectAddress', contains: '地址示例' })).toHaveLength(1)
    expect(assignmentRows(rows, { searchField: 'reportTitle', contains: '空调' })).toHaveLength(1)
    expect(assignmentRows(rows, { dateField: 'requestedTestDate', from: '2026-02-01', to: '2026-02-01' })).toHaveLength(1)
    expect(assignmentRows(rows, { dateField: 'commissionDate', from: '2026-02-01', to: '2026-02-01' })).toHaveLength(0)
    row.details.requestedTestDate = ''
    expect(assignmentRows(rows, { dateField: 'requestedTestDate', from: '2026-01-01' })).toHaveLength(0)
    expect(() => parseAssignmentQuery({ dateField: 'requestedTestDate', from: '2026-03-01', to: '2026-02-01' })).toThrow('日期范围')
  })
})
