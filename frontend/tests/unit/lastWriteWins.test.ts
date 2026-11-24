import { describe, expect, it } from 'vitest'
import { createEquipmentForms } from '../../server/equipmentForm'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { approvalSource } from '../../server/reportLifecycle'
import { demoActors } from '../../src/services/storage/demoActors'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'

function setup() {
  let state = seedRegistration()
  const deps = { actor: () => demoActors[0]!, read: () => state, write: (next: typeof state) => { state = next } }
  return { deps, state: () => state, registration: createRegistrationService(deps), equipment: createEquipmentForms(deps) }
}

describe('last successful submission wins', () => {
  it('lets two previously opened sample forms save in order without losing attachments or audit history', async () => {
    const t = setup(), first = await t.registration.sample('demo-yp-1'), second = structuredClone(first)
    await t.registration.saveSample({ ...first, name: '先提交' }, first.id, first.version)
    const file = { name: '说明.txt', type: 'text/plain', size: 1, dataUrl: 'data:text/plain;base64,YQ==' }
    await t.registration.attach(first.id, first.version, file, 'samples')
    const saved = await t.registration.saveSample({ ...second, name: '后提交覆盖' }, second.id, second.version)
    expect(saved).toMatchObject({ name: '后提交覆盖', version: first.version + 3 })
    expect(saved.attachments).toHaveLength(1)
    expect(saved.events.filter(event => event.action === '修改样品')).toHaveLength(2)
    expect((await t.registration.sample(first.id)).name).toBe('后提交覆盖')
  })

  it('accepts old versions in atomic batch edits and deletion, changing only submitted batch fields', () => {
    const t = setup(), a = t.equipment.save({ ...emptyEquipment(), code: 'LAST-A', name: '设备A', departmentId: 'lab' })
    const b = t.equipment.save({ ...emptyEquipment(), code: 'LAST-B', name: '设备B', departmentId: 'lab' })
    t.equipment.save({ ...a, name: '先修改的名称', keeper: '先提交' }, a.id)
    t.equipment.batchUpdate({ records: [a, b], changes: { keeper: '后提交' } })
    expect(t.equipment.detail(a.id)).toMatchObject({ name: '先修改的名称', keeper: '后提交', version: a.version + 2 })
    expect(t.equipment.detail(b.id).keeper).toBe('后提交')
    t.equipment.remove(a.id, { version: a.version })
    expect(() => t.equipment.detail(a.id)).toThrow()
    expect(t.equipment.detail(b.id).name).toBe('设备B')
  })

  it('ignores record counters in report preparation but still detects content changes', () => {
    const t = setup(), sample = t.state().samples[0]!, source = approvalSource(t.state(), sample)
    sample.version++
    expect(approvalSource(t.state(), sample)).toBe(source)
    sample.name = '报告内容发生变化'
    expect(approvalSource(t.state(), sample)).not.toBe(source)
  })
})
