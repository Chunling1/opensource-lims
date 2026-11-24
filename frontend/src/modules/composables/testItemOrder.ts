import type { CapabilityItemRow } from '@/services/pipeline'

export type TestItemRef = { kind: 'library'; id: number } | { kind: 'manual'; name: string }
export const testItemKey = (item: TestItemRef) => item.kind === 'library' ? `library:${item.id}` : `manual:${item.name}`

// Old records start with their saved library order, then their manual items.
// Reconcile removed/new items without changing the remaining mixed order.
export function reconcileTestItemOrder(order: TestItemRef[] = [], ids: number[] = [], manual: string[] = []): TestItemRef[] {
  const available: TestItemRef[] = [...ids.map(id => ({ kind: 'library' as const, id })), ...manual.map(name => ({ kind: 'manual' as const, name }))]
  const byKey = new Map(available.map(item => [testItemKey(item), item]))
  const result: TestItemRef[] = []
  for (const item of [...order, ...available]) {
    const key = testItemKey(item), found = byKey.get(key)
    if (found) { result.push(found); byKey.delete(key) }
  }
  return result
}
export function testItemRows(order: TestItemRef[], rows: CapabilityItemRow[]) {
  const byId = new Map(rows.map(row => [row.id, row]))
  return order.map(item => {
    const row = item.kind === 'library' ? byId.get(item.id) : undefined
    return { key: testItemKey(item), label: item.kind === 'manual' ? item.name : row?.itemName || `历史参数 ${item.id}`,
      detail: row ? `${row.standardCode} · ${row.objectName || row.accreditation || ''}` : '', manual: item.kind === 'manual' }
  })
}
