import { emptyPlanSelection, type PlanSelection, type PlanSelectionCatalogue, type PlanSelectionState, type PlanSelectionToggle } from '../../types/samples/inbound'

// A server-authorized catalogue snapshot lets unopened branches participate in
// local all/group selection. Business queries and saves still validate IDs.
export function localPlanSelection(catalogue: PlanSelectionCatalogue, value: PlanSelection, toggle?: PlanSelectionToggle): PlanSelectionState {
  const { groups, plans } = catalogue
  const groupIds = new Set(value.groupIds), planIds = new Set(value.planIds), excluded = new Set(value.excludedPlanIds)
  const populated = catalogue.populatedPlanIds === undefined ? undefined : new Set(catalogue.populatedPlanIds)
  if (toggle) {
    const targets = plans.filter(plan => (!toggle.populatedOnly || populated?.has(plan.id)) && (toggle.kind === 'all' || (toggle.kind === 'group' ? plan.parentId === toggle.id : plan.id === toggle.id)))
    if (toggle.populatedOnly || toggle.kind === 'plan') {
      for (const plan of targets) {
        if (groupIds.has(plan.parentId)) { if (toggle.checked) excluded.delete(plan.id); else excluded.add(plan.id) }
        else if (toggle.checked) planIds.add(plan.id); else planIds.delete(plan.id)
      }
    } else if (toggle.kind === 'all') {
      groupIds.clear(); planIds.clear(); excluded.clear()
      if (toggle.checked) for (const group of groups) groupIds.add(group.id)
    } else {
      if (toggle.checked) groupIds.add(toggle.id); else groupIds.delete(toggle.id)
      for (const plan of targets) { planIds.delete(plan.id); excluded.delete(plan.id) }
    }
  }
  const chosen = plans.filter(plan => groupIds.has(plan.parentId) ? !excluded.has(plan.id) : planIds.has(plan.id))
  const ids = new Set(chosen.map(plan => plan.id))
  const selection = chosen.length ? {
    groupIds: [...groupIds],
    planIds: [...planIds].filter(id => !groupIds.has(plans.find(plan => plan.id === id)?.parentId || '')),
    excludedPlanIds: [...excluded].filter(id => groupIds.has(plans.find(plan => plan.id === id)?.parentId || '')),
  } : emptyPlanSelection()
  const groupStates = (visible: typeof plans) => Object.fromEntries(groups.map(group => {
    const children = visible.filter(plan => plan.parentId === group.id), count = children.filter(plan => ids.has(plan.id)).length
    return [group.id, { checked: !!children.length && count === children.length, indeterminate: count > 0 && count < children.length }]
  }))
  const visible = populated && plans.filter(plan => populated.has(plan.id))
  return { selection, count: chosen.length, total: plans.length, previews: chosen.slice(0, 3).map(({ id, name }) => ({ id, name })), groups: groupStates(plans),
    ...(visible ? { populated: { count: visible.filter(plan => ids.has(plan.id)).length, total: visible.length, groups: groupStates(visible) } } : {}) }
}
