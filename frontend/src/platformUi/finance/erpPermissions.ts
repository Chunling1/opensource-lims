export const erpRoles = ['view', 'review', 'send', 'reverse'] as const
export function canOperateErp(roles: readonly string[] | undefined, mode: 'send' | 'reverse') {
  return erpRoles.slice(0, mode === 'send' ? 3 : 4).every(role => roles?.includes(role))
}
export function toggleErpRole(roles: readonly string[], role: string, selected: boolean): string[] {
  const index = erpRoles.indexOf(role as typeof erpRoles[number])
  if (index < 0) return [...roles]
  const result = new Set(roles)
  for (const item of selected ? erpRoles.slice(0, index + 1) : erpRoles.slice(index)) {
    if (selected) result.add(item)
    else result.delete(item)
  }
  return erpRoles.filter(item => result.has(item))
}
