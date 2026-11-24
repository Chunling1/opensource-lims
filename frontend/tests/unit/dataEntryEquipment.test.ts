import { describe, expect, it } from 'vitest'
import { createDataEntryService } from '../../server/dataEntryDetail'
import { seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'

function setup() {
  let state = seedRegistration(), actor = demoActors[0]!
  const service = createDataEntryService({ read: () => state, write: next => { state = next }, actor: () => actor }), id = 'demo-yp-76'
  function write(action: string, values: Record<string, unknown> = {}, sampleId = id) {
    const detail = service.detail(sampleId)
    return service.mutate(sampleId, action, { version: detail.version, sampleVersion: detail.sample.version, equipmentVersion: detail.equipmentConfig.version, requestId: crypto.randomUUID(), ...values })
  }
  function clone(id: string, plan?: string) { const sample = structuredClone(state.samples.find(row => row.id === 'demo-yp-76')!); sample.id = id; if (plan) sample.details!.testPlanId = plan; state.samples.push(sample) }
  return { service, id, write, clone, actor: (id: string) => { actor = demoActors.find(row => row.id === id)! } }
}
describe('equipment association and defaults by test plan', () => {
  it('sets and unsets only checked defaults, preserves selections, and permits clearing all defaults', () => {
    const t = setup(); t.clone('future')
    t.write('equipment-associate', { ids: ['equipment-2'] })
    t.write('equipment-defaults', { ids: ['equipment-1'] })
    const both = t.write('equipment-defaults', { ids: ['equipment-2'] })
    expect(both.equipmentConfig.defaultIds).toEqual(['equipment-1', 'equipment-2'])
    expect(() => t.write('equipment-unset-defaults', { ids: ['equipment-3'] })).toThrow()
    const one = t.write('equipment-unset-defaults', { ids: ['equipment-1'] })
    expect(one.equipmentConfig.defaultIds).toEqual(['equipment-2'])
    expect(one.form).toEqual(both.form)
    expect(one.reportRevision).toBe(both.reportRevision)
    expect(one.equipmentConfig.associatedIds).toEqual(both.equipmentConfig.associatedIds)
    expect(t.service.detail('future').form.equipmentIds).toEqual(['equipment-2'])
    t.actor('business'); expect(() => t.write('equipment-unset-defaults', { ids: ['equipment-2'] })).toThrowError(expect.objectContaining({ code: 'FORBIDDEN' }))
    t.actor('admin'); t.write('equipment-unset-defaults', { ids: ['equipment-2'], equipmentVersion: both.equipmentConfig.version })
    expect(t.service.detail('future').form.equipmentIds).toEqual([])
  })
  it('shares associations and defaults with subsequent same-plan records, without overwriting saved selections', () => {
    const t = setup(); t.clone('existing'); t.clone('future'); t.clone('different-plan', 'pressure-1')
    t.write('save', { form: t.service.detail('existing').form }, 'existing')
    const first = t.write('equipment-associate', { ids: ['equipment-2'] })
    expect(first.equipmentConfig.associatedIds).toEqual(['equipment-1', 'equipment-2'])
    const configured = t.write('equipment-defaults', { ids: ['equipment-2'] })
    expect(configured.form.equipmentIds).toEqual([])
    expect(t.service.detail('future').form.equipmentIds).toEqual(['equipment-2'])
    expect(t.service.detail('existing').form.equipmentIds).toEqual([])
    expect(t.service.detail('different-plan').form.equipmentIds).toEqual([])
    expect(t.service.detail('future').equipmentConfig).toEqual(configured.equipmentConfig)
    expect(configured.reportRevision).toBe(first.reportRevision)
    const otherPlan = t.write('equipment-associate', { ids: ['equipment-2'] }, 'different-plan')
    expect(otherPlan.equipmentConfig.associatedIds).toContain('equipment-2')
    expect(otherPlan.equipmentConfig.defaultIds).toEqual([])
    expect(t.service.detail(t.id).equipmentConfig).toEqual(configured.equipmentConfig)
  })
  it('checks equipment ownership, association, permissions and concurrent plan edits', () => {
    const t = setup()
    expect(() => t.write('equipment-associate', { ids: ['equipment-3'] })).toThrow()
    expect(() => t.write('equipment-defaults', { ids: ['equipment-2'] })).toThrow()
    expect(() => t.write('equipment-associate', { ids: ['equipment-1', 'equipment-1'] })).toThrow()
    const old = t.service.detail(t.id)
    t.write('equipment-associate', { ids: ['equipment-2'] })
    expect(() => t.write('equipment-defaults', { ids: ['equipment-1'], equipmentVersion: old.equipmentConfig.version })).not.toThrow()
    t.actor('business'); expect(() => t.write('equipment-defaults', { ids: ['equipment-1'] })).toThrowError(expect.objectContaining({ code: 'FORBIDDEN' }))
    t.actor('other'); expect(() => t.service.detail(t.id)).toThrowError(expect.objectContaining({ code: 'NOT_FOUND' }))
  })
  it('deduplicates a repeated request and does not change source data or report results', () => {
    const t = setup(), before = t.service.detail(t.id)
    const payload = { version: before.version, sampleVersion: before.sample.version, equipmentVersion: before.equipmentConfig.version, requestId: crypto.randomUUID(), ids: ['equipment-2'] }
    const first = t.service.mutate(t.id, 'equipment-associate', payload)
    expect(t.service.mutate(t.id, 'equipment-associate', payload).equipmentConfig).toEqual(first.equipmentConfig)
    expect(first.form).toEqual(before.form)
    expect(first.sample.version).toBe(before.sample.version)
    expect(first.reportRevision).toBe(before.reportRevision)
  })
})
