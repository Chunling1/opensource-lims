import { businessAreas, modules } from './modules'

interface PermissionItem {
  code: string
  name: string
  ptype: string
}

// Display anchors only, not permission implication or authorization rules.
// Legacy action names do not always share the current menu page's prefix.
const actionPageAnchors: Record<string, string> = {
  'sample.out_warehouse.sign': 'sample.outbound.view',
  'sample.out_warehouse.return': 'sample.outbound.view',
  'sample.return_stock': 'sample.outbound.view',
  'sample.dispose': 'sample.disposal.view',
}

const menuModules = businessAreas.flatMap((area) => modules.filter((item) => item.area === area.key))
const moduleRank = new Map(menuModules.map((item, index) => [item.key, index]))

/** Keep every code/object and its group; sort only the presentation copy. */
export function groupPermissions<T extends PermissionItem>(items: readonly T[]) {
  const grouped = new Map<string, T[]>()
  for (const item of items) {
    const key = item.code.split('.')[0] || 'other'
    const group = grouped.get(key) ?? []
    group.push(item)
    grouped.set(key, group)
  }
  return [...grouped].sort(([left], [right]) =>
    (moduleRank.get(left) ?? Infinity) - (moduleRank.get(right) ?? Infinity)
    || left.localeCompare(right),
  ).map(([key, group]) => {
    const module = menuModules.find((item) => item.key === key)
    const visiblePages = module?.pages.filter((item) => !item.hidden) ?? []
    const hiddenPages = module?.pages.filter((item) => item.hidden) ?? []
    const rank = (item: T): number => {
      if (item.code === module?.permission || item.ptype === 'module') return -1
      const visible = visiblePages.findIndex((page) => page.permission === item.code)
      if (visible >= 0) return visible * 2
      if (item.ptype === 'action') {
        const anchor = actionPageAnchors[item.code] ?? `${item.code.slice(0, item.code.lastIndexOf('.'))}.view`
        const pageIndex = visiblePages.findIndex((page) => page.permission === anchor)
        if (pageIndex >= 0) return pageIndex * 2 + 1
      }
      const hidden = hiddenPages.findIndex((page) => page.permission === item.code)
      // Internal/legacy entries follow the visible menu; never discard them.
      return hidden >= 0 ? visiblePages.length * 2 + hidden : Infinity
    }
    const sorted = [...group].sort((a, b) => rank(a) - rank(b) || a.code.localeCompare(b.code))
    return {
      key,
      name: module?.name ?? group.find((item) => item.ptype === 'module')?.name ?? key,
      items: sorted,
      codes: sorted.map((item) => item.code),
    }
  })
}
