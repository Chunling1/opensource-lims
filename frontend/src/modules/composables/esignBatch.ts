export interface SignableTask { id: number; status: string; myStatus?: string; canSign?: boolean }
export function canSignTask(row: SignableTask) { return row.canSign !== false && row.status === 'signing' && ['pending', 'signing'].includes(row.myStatus || '') }
export function selectedSignableIds(rows: SignableTask[]) { return [...new Set(rows.filter(canSignTask).map(row => row.id))] }
export function groupSignTasks<T extends SignableTask & { myRole?: string }>(rows: T[]): T[] {
  const groups = new Map<number, T[]>()
  rows.forEach(row => groups.set(row.id, [...(groups.get(row.id) || []), row]))
  return [...groups.values()].map(group => {
    const row = group.find(canSignTask) || group.find(r => r.myStatus !== 'signed') || group[0]!
    return { ...row, myRole: [...new Set(group.map(r => r.myRole).filter(Boolean))].join(' / ') }
  })
}
