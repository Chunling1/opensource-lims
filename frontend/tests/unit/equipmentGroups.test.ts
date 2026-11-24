import { describe, it, expect } from 'vitest'
import { createEquipmentForms } from '../../server/equipmentForm'
import { createEquipmentGroups, seedEquipmentGroups } from '../../server/equipmentGroups'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'

function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }
  let actor: Actor = { id: 'admin', name: '管理员', roles: ['admin'], scope: 'all', departmentId: 'lab' }
  const deps = { actor: () => actor, read: () => state, write: (next: RegistrationState) => { state = next } }
  const form = createEquipmentForms(deps), groups = createEquipmentGroups(deps)
  const rows = [1, 2, 3].map(i => form.save({ ...emptyEquipment(), code: `GROUP-${i}`, name: `设备${i}`, departmentId: i === 3 ? 'lab2' : 'lab' }))
  seedEquipmentGroups(state)
  return { form, groups, rows, state: () => state, actor: (next: Partial<Actor>) => { actor = { ...actor, ...next } }, context: () => groups.context({ ids: rows.slice(0, 2).map(row => row.id) }) }
}

describe('equipment group association', () => {
  it('computes all, none and partial membership for selected devices only', () => {
    const t = setup()
    expect(t.context().groups.map(group => group.state)).toEqual(['checked', 'mixed', 'unchecked'])
    expect(t.groups.context({ ids: [t.rows[0]!.id] }).groups.map(group => group.state)).toEqual(['checked', 'checked', 'unchecked'])
  })
  it('applies checked/unchecked to every target and preserves mixed and unselected devices', () => {
    const t = setup(), context = t.context(), before = structuredClone(t.state())
    const data = { ...context, groups: context.groups.map(group => ({ ...group, state: group.state === 'checked' ? 'unchecked' : group.state === 'unchecked' ? 'checked' : 'mixed' })) }
    expect(t.groups.save(data)).toEqual({ count: 2 })
    expect(t.state().equipmentGroupLinks?.[t.rows[0]!.id]).toEqual(['equipment-group-field', 'equipment-group-backup'])
    expect(t.state().equipmentGroupLinks?.[t.rows[1]!.id]).toEqual(['equipment-group-backup'])
    expect(t.state().equipmentGroupLinks?.[t.rows[2]!.id]).toEqual(before.equipmentGroupLinks?.[t.rows[2]!.id])
    expect(t.state().equipmentProfiles).toEqual(before.equipmentProfiles)
    expect(t.state().equipmentLedger!.map(row => row.version)).toEqual([2, 2, 1])
  })
  it('supports changing mixed to unchecked and leaves no-op versions unchanged', () => {
    const t = setup(), context = t.context(), before = structuredClone(t.state())
    expect(t.groups.save(context)).toEqual({ count: 0 })
    expect(t.state()).toEqual(before)
    context.groups[1]!.state = 'unchecked'
    expect(t.groups.save(context)).toEqual({ count: 1 })
    expect(t.context().groups[1]!.state).toBe('unchecked')
  })
  it('rejects missing groups and invalid states atomically', () => {
    const t = setup(), context = t.context(), before = structuredClone(t.state())
    const variants = [
      { ...context, groups: [...context.groups, context.groups[0]] },
      { ...context, groups: [{ ...context.groups[0], state: 'invalid' }] },
      { ...context, groups: [{ id: 'missing', version: 1, state: 'checked' }] },
      { ...context, records: [] },
    ]
    for (const data of variants) { expect(() => t.groups.save(data)).toThrow(); expect(t.state()).toEqual(before) }
  })
  it('checks write permissions and every selected device scope', () => {
    const t = setup(), context = t.context(), before = structuredClone(t.state())
    t.actor({ roles: ['reviewer'] })
    expect(() => t.groups.save(context)).toThrow('无权')
    t.actor({ roles: ['quality'], scope: 'department' })
    expect(() => t.groups.context({ ids: t.rows.map(row => row.id) })).toThrow('无权')
    expect(t.state()).toEqual(before)
  })
  it('removes membership when the device is deleted', () => {
    const t = setup(), row = t.rows[0]!
    t.form.remove(row.id, { version: row.version })
    expect(t.state().equipmentGroupLinks?.[row.id]).toBeUndefined()
    expect(t.state().equipmentGroupLinks?.[t.rows[1]!.id]).toBeDefined()
  })
})
