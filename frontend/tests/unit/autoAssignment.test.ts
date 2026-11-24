import { describe, expect, it } from 'vitest'
import { createAutoAssignment, type AssignmentRule } from '../../server/autoAssignment'
import { createRegistrationService, seedRegistration, serverDate } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'
import type { Actor } from '../../src/types/lims'

const request = { action: 'auto', version: 1 }
describe('one-click automatic assignment', () => {
  it('uses current presets, the actual actor and server date within the write', async () => {
    let state = seedRegistration()
    const rules: Record<string, AssignmentRule> = { 'general-1': { revision: 1, dataEntryPerson: 'analyst', tester1: 'analyst' } }
    const helper = createAutoAssignment(() => rules), actor = demoActors.find(person => person.id === 'analyst')!
    const service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { state = next } }, undefined, helper)
    rules['general-1'] = { revision: 2, dataEntryPerson: 'reviewer', tester1: 'analyst', tester2: 'approver' }
    const saved = await service.assignmentAction('demo-yp-51', 1, request, 'auto')
    expect(saved).toMatchObject({ dataStatus: '任务分配完成', version: 2, assignmentInfo: { assignedById: 'analyst', assignedBy: '李检测', recordedBy: { id: 'analyst', name: '李检测' }, dataEntryPersonId: 'reviewer', tester1Id: 'analyst', tester2Id: 'approver', assignedDate: serverDate(), recordedAt: expect.any(String) } })
    expect(saved.events.at(-1)).toMatchObject({ action: '自动分配', actor: '李检测' })
    await expect(service.assignmentAction('demo-yp-51', 1, request, 'auto')).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    await expect(service.assignmentAction('demo-yp-51', 2, { action: 'auto', version: 2 }, 'auto')).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
  })
  it('never writes missing or invalid presets and accepts entry/test overlap', async () => {
    let state = seedRegistration(), rules: Record<string, AssignmentRule> = {}, people = structuredClone(demoActors)
    const helper = createAutoAssignment(() => rules, () => people)
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state, write: next => { state = next } }, undefined, helper)
    const before = structuredClone(state)
    async function invalid(message: string) {
      await expect(service.assignmentAction('demo-yp-51', 1, request, 'auto')).rejects.toThrow(message)
      expect(state).toEqual(before)
    }
    await invalid('尚未配置')
    for (const rule of [{ revision: 1, tester1: 'analyst' }, { revision: 1, dataEntryPerson: 'analyst' }]) {
      rules = { 'general-1': rule }; await invalid('未配置')
    }
    for (const key of ['dataEntryPerson', 'tester1', 'tester2']) {
      rules = { 'general-1': { revision: 1, dataEntryPerson: 'analyst', tester1: 'analyst', [key]: 'unknown' } }
      await invalid('已不存在')
    }
    rules = { 'general-1': { revision: 1, dataEntryPerson: 'analyst', tester1: 'analyst', tester2: 'analyst' } }
    await invalid('重复')
    rules = { 'general-1': { revision: 1, dataEntryPerson: 'analyst', tester1: 'analyst' } }
    people = people.filter(person => person.id !== 'analyst')
    await invalid('已不存在')
    people = structuredClone(demoActors)
    const saved = await service.assignmentAction('demo-yp-51', 1, request, 'auto')
    expect(saved.assignmentInfo).toMatchObject({ dataEntryPersonId: 'analyst', tester1Id: 'analyst', tester2Id: '' })
    const noPlan = structuredClone(before.samples[50]!)
    noPlan.details!.testPlanId = ''
    expect(() => helper.resolve(noPlan, demoActors[0]!, serverDate())).toThrow('未设置检测方案')
  })
  it('rejects invalid states, actor scope, locked workspaces and obsolete payloads without writes', async () => {
    let state = seedRegistration(), locked = false
    let actor: Actor = demoActors[0]!
    const service = createRegistrationService({ actor: () => actor, locked: () => locked, read: () => state, write: next => { state = next } })
    async function rejected(code: string, input: unknown = request) {
      const before = structuredClone(state)
      await expect(service.assignmentAction('demo-yp-51', 1, input, 'auto')).rejects.toMatchObject({ code })
      expect(state).toEqual(before)
    }
    for (const field of ['account', 'name', 'date', 'dataEntryPerson', 'tester1', 'tester2', 'previewToken', 'recordedBy']) await rejected('BAD_REQUEST', { ...request, [field]: '' })
    for (const status of ['voided', 'void_pending'] as const) { state.samples[50]!.status = status; await rejected('BUSINESS_RULE') }
    state.samples[50]!.status = 'completed'
    for (const dataStatus of ['任务分配完成', '样品出库中', '样品已处置']) { state.samples[50]!.dataStatus = dataStatus; await rejected('BUSINESS_RULE') }
    state.samples[50]!.dataStatus = '任务分配中'
    actor = demoActors.find(person => person.id === 'approver')!; await rejected('FORBIDDEN')
    actor = demoActors.find(person => person.id === 'other')!; await rejected('NOT_FOUND')
    actor = demoActors[0]!; locked = true; await rejected('LOCKED')
  })
})
