import type { RegistrationState } from '../src/types/commissions/registration'
export function migrateStandardGroups(state: RegistrationState) {
  if (!state.standardGroups && state.standardCategories) state.standardGroups = state.standardCategories
  for (const row of state.standards || []) {
    const legacy = row as typeof row & { categoryIds?: string[] }
    row.groupIds ??= [...(legacy.categoryIds || [])]
    row.category ??= (legacy.categoryIds || []).map(id => state.standardGroups?.find(group => group.id === id)?.name).filter(Boolean).join('、')
    delete legacy.categoryIds
  }
  delete state.standardCategories
}
