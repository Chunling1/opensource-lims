import type { DataScope } from '@/services/auth'

/**
 * Semantic list scope used by the data-entry workbench.
 * Profile refreshes replace DataScope with a new object even when the effective
 * scope is unchanged, so object identity must never be used as a reload signal.
 */
export function reportDataEntryScopeKey(
  scope: Pick<DataScope, 'scopeType' | 'department'>,
  userName: string,
  changePage: boolean,
) {
  return JSON.stringify([
    scope.scopeType || '',
    scope.department || '',
    userName || '',
    changePage ? 'data_change' : 'data_entry',
  ])
}
