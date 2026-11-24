import { AppError } from '../src/services/common/errors'
import type { Actor } from '../src/types/lims'
import { emptyPlanSelection, type PlanSelection, type PlanSelectionState, type PlanSelectionToggle, type PlanSelectionCatalogue } from '../src/types/samples/inbound'
import { testPlanGroups, testPlans } from './samplePlans'
export function parsePlanSelection(value: unknown): PlanSelection {
  if (value === undefined) return emptyPlanSelection()
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new AppError('BAD_REQUEST', '检测方案筛选格式有误。')
  const input = value as Record<string, unknown>, result = emptyPlanSelection()
  for (const key of ['groupIds', 'planIds', 'excludedPlanIds'] as const) {
    if (!Array.isArray(input[key]) || input[key].length > 500 || input[key].some(id => typeof id !== 'string' || !id || id.length > 100)) throw new AppError('BAD_REQUEST', '检测方案筛选格式有误。')
    result[key] = [...new Set(input[key] as string[])]
  }
  return result
}
export function resolvePlanSelection(actor: Actor, value: unknown, toggleValue?: unknown, populatedIds?: Set<string>): { state: PlanSelectionState; ids: Set<string>; restricted: boolean; catalogue: PlanSelectionCatalogue } {
  const selection = parsePlanSelection(value)
  const allowed = (row: { departmentId: string }) => actor.scope === 'all' || row.departmentId === actor.departmentId
  const groups = testPlanGroups.filter(allowed), plans = testPlans.filter(allowed)
  if (selection.groupIds.some(id => !groups.some(group => group.id === id)) || [...selection.planIds, ...selection.excludedPlanIds].some(id => !plans.some(plan => plan.id === id))) throw new AppError('NOT_FOUND', '检测方案不存在或已不可访问，请重新选择。')
  const groupIds = new Set(selection.groupIds), planIds = new Set(selection.planIds), excluded = new Set(selection.excludedPlanIds)
  if (toggleValue !== undefined) {
    if (!toggleValue || typeof toggleValue !== 'object' || Array.isArray(toggleValue)) throw new AppError('BAD_REQUEST', '方案勾选格式有误。')
    const toggle = toggleValue as PlanSelectionToggle
    if (typeof toggle.checked !== 'boolean' || typeof toggle.id !== 'string' || !['all', 'group', 'plan'].includes(toggle.kind)) throw new AppError('BAD_REQUEST', '方案勾选格式有误。')
    if (toggle.populatedOnly !== undefined && typeof toggle.populatedOnly !== 'boolean' || toggle.populatedOnly && !populatedIds) throw new AppError('BAD_REQUEST', '方案勾选范围有误。')
    if (toggle.populatedOnly) {
      if (toggle.kind === 'group' && !groups.some(group => group.id === toggle.id) || toggle.kind === 'plan' && !plans.some(plan => plan.id === toggle.id)) throw new AppError('NOT_FOUND', '检测方案已不可访问。')
      // Expand the complete eligible group on the server, independent of loaded pages.
      for (const plan of plans.filter(plan => populatedIds!.has(plan.id) && (toggle.kind === 'all' || (toggle.kind === 'group' ? plan.parentId === toggle.id : plan.id === toggle.id)))) {
        if (groupIds.has(plan.parentId)) { if (toggle.checked) excluded.delete(plan.id); else excluded.add(plan.id) }
        else if (toggle.checked) planIds.add(plan.id); else planIds.delete(plan.id)
      }
    } else if (toggle.kind === 'all') {
      groupIds.clear(); planIds.clear(); excluded.clear()
      if (toggle.checked) for (const group of groups) groupIds.add(group.id)
    } else if (toggle.kind === 'group') {
      if (!groups.some(group => group.id === toggle.id)) throw new AppError('NOT_FOUND', '检测方案分组已不可访问。')
      if (toggle.checked) groupIds.add(toggle.id); else groupIds.delete(toggle.id)
      for (const plan of plans.filter(plan => plan.parentId === toggle.id)) { planIds.delete(plan.id); excluded.delete(plan.id) }
    } else {
      const plan = plans.find(plan => plan.id === toggle.id)
      if (!plan) throw new AppError('NOT_FOUND', '检测方案已不可访问。')
      if (groupIds.has(plan.parentId)) { if (toggle.checked) excluded.delete(plan.id); else excluded.add(plan.id) }
      else if (toggle.checked) planIds.add(plan.id); else planIds.delete(plan.id)
    }
  }
  const chosen = plans.filter(plan => groupIds.has(plan.parentId) ? !excluded.has(plan.id) : planIds.has(plan.id))
  const ids = new Set(chosen.map(plan => plan.id))
  // Drop redundant explicit IDs but keep exclusions compact; whole groups stay on the server.
  const normalized = !chosen.length ? emptyPlanSelection() : { groupIds: [...groupIds], planIds: [...planIds].filter(id => !groupIds.has(plans.find(p => p.id === id)!.parentId)), excludedPlanIds: [...excluded].filter(id => groupIds.has(plans.find(p => p.id === id)!.parentId)) }
  const groupStates = (visiblePlans: typeof plans) => Object.fromEntries(groups.map(group => {
    const children = visiblePlans.filter(plan => plan.parentId === group.id), count = children.filter(plan => ids.has(plan.id)).length
    return [group.id, { checked: children.length > 0 && count === children.length, indeterminate: count > 0 && count < children.length }]
  }))
  const populated = populatedIds ? plans.filter(plan => populatedIds.has(plan.id)) : undefined
  return { state: { selection: normalized, count: chosen.length, total: plans.length, previews: chosen.slice(0, 3).map(({ id, name }) => ({ id, name })), groups: groupStates(plans),
    ...(populated ? { populated: { count: populated.filter(plan => ids.has(plan.id)).length, total: populated.length, groups: groupStates(populated) } } : {}) }, ids, restricted: normalized.groupIds.length > 0 || normalized.planIds.length > 0,
    catalogue: { groups: groups.map(({ id }) => ({ id })), plans: plans.map(({ id, parentId, name }) => ({ id, parentId, name })), ...(populated ? { populatedPlanIds: populated.map(plan => plan.id) } : {}) } }
}
