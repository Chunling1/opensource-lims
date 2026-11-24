import { describe, expect, it } from 'vitest'
import { seedRegistration, createRegistrationService } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'
import { emptyPlanSelection } from '../../src/types/samples/inbound'

describe.each(['assignment', 'pickup'] as const)('%s plan filters', scope => {
  it('filters query and export by accessible plans and keeps populated selection within the workflow scope', async () => {
    const state = seedRegistration(), actor = { ...demoActors[0]! }
    const service = createRegistrationService({ actor: () => actor, read: () => state })
    const query = scope === 'assignment' ? service.assignmentSamples : service.pickupSamples
    const csv = scope === 'assignment' ? service.exportAssignmentSamples : service.exportPickupSamples
    const initial = await query({ pageSize: 50 }), sample = state.samples.find(sample => sample.id === initial.items[0]!.id)!
    sample.details!.testPlanId = 'general-2'; sample.details!.testPlan = '工程材料检测方案'
    const before = structuredClone(state), plans = { ...emptyPlanSelection(), planIds: ['general-2'] }
    const filtered = await query({ plans })
    expect(filtered.items.map(row => row.id)).toEqual([sample.id])
    expect(filtered.planSelection).toMatchObject({ count: 1, selection: plans })
    expect((await csv({ plans })).trim().split('\r\n')).toHaveLength(2)
    expect(await csv({ plans })).toContain(sample.code)
    const excluded = await query({ plans: { groupIds: ['general'], planIds: [], excludedPlanIds: ['general-2'] }, pageSize: 50 })
    expect(excluded.items.some(row => row.id === sample.id)).toBe(false)
    const selection = await service.testPlanSelection(emptyPlanSelection(), { kind: 'group', id: 'general', checked: true, populatedOnly: true }, scope)
    const eligibleStates = scope === 'assignment' ? ['样品入库完成', '任务分配中', '任务分配完成'] : ['样品待领取', '样品已领取']
    const expected = [...new Set(state.samples.filter(row => eligibleStates.includes(row.dataStatus) && !['voided', 'void_pending'].includes(row.status) && row.details?.testPlanId.startsWith('general-')).map(row => row.details!.testPlanId))]
    expect(selection.selection.planIds.sort()).toEqual(expected.sort())
    expect(selection.selection.planIds).not.toContain('general-3')
    const nodes = await service.testPlans({ parentId: 'general' })
    expect(nodes.items.find(row => row.id === 'general-2')?.[scope === 'assignment' ? 'assignmentSampleCount' : 'pickupSampleCount']).toBe(1)
    sample.status = 'voided'
    expect((await query({ plans })).total).toBe(0)
    sample.status = before.samples.find(row => row.id === sample.id)!.status
    expect(state).toEqual(before)
    await expect(query({ plans: { ...plans, planIds: ['missing'] } })).rejects.toMatchObject({ code: 'NOT_FOUND' })
    actor.scope = 'department'; actor.departmentId = 'lab'
    await expect(query({ plans: { ...plans, planIds: ['branch-1'] } })).rejects.toMatchObject({ code: 'NOT_FOUND' })
    await expect(csv({ plans: { ...plans, planIds: ['branch-1'] } })).rejects.toMatchObject({ code: 'NOT_FOUND' })
  })
})
