import { expect, it } from 'vitest'
import { localPlanSelection } from '../../src/services/common/localPlanSelection'
import { emptyPlanSelection, type PlanSelectionToggle } from '../../src/types/samples/inbound'
import { resolvePlanSelection } from '../../server/testPlanSelection'
import { demoActors } from '../../src/services/storage/demoActors'

it('keeps local group, individual, all and populated-only choices equivalent to server validation', () => {
  const actor = demoActors[0]!, populated = new Set(['temperature-1', 'temperature-11', 'pressure-1'])
  const catalogue = resolvePlanSelection(actor, emptyPlanSelection(), undefined, populated).catalogue
  let value = emptyPlanSelection()
  const toggles: PlanSelectionToggle[] = [
    { kind: 'group', id: 'temperature', checked: true, populatedOnly: true },
    { kind: 'group', id: 'temperature', checked: true },
    { kind: 'plan', id: 'temperature-21', checked: false },
    { kind: 'all', id: '', checked: false, populatedOnly: true },
    { kind: 'plan', id: 'temperature-1', checked: true },
    { kind: 'group', id: 'pressure', checked: true },
    { kind: 'group', id: 'temperature', checked: false },
    { kind: 'all', id: '', checked: true },
    { kind: 'all', id: '', checked: false },
  ]
  for (const toggle of toggles) {
    const before = structuredClone(value)
    const local = localPlanSelection(catalogue, value, toggle)
    expect(local).toEqual(resolvePlanSelection(actor, value, toggle, populated).state)
    expect(value).toEqual(before)
    value = local.selection
  }
})

it('uses a department-scoped catalogue and supports rapid repeated toggles without duplicates', () => {
  const actor = { ...demoActors[0]!, scope: 'department' as const, departmentId: 'lab2' }
  const context = resolvePlanSelection(actor, emptyPlanSelection())
  const first = localPlanSelection(context.catalogue, emptyPlanSelection(), { kind: 'all', id: '', checked: true })
  const second = localPlanSelection(context.catalogue, first.selection, { kind: 'plan', id: 'branch-1', checked: true })
  expect(first).toEqual(second)
  expect(second.count).toBe(1)
  expect(second.previews[0]?.id).toBe('branch-1')
  expect(localPlanSelection(context.catalogue, second.selection, { kind: 'plan', id: 'branch-1', checked: false }).count).toBe(0)
})
