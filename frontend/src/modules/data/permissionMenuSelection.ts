import { modules } from './modules'
import { groupPermissions } from './permissionDisplayOrder'

interface PermissionItem { code: string; name: string; ptype: string }

const menus = new Map(modules.flatMap((module) => [
  [module.permission, module.name] as const,
  ...module.pages.filter((page) => !page.hidden && page.key !== 'interim_report' && page.permission !== module.permission)
    .map((page) => [page.permission, page.name] as const),
]))

// Only these verified page-implied actions may disappear from the editor.
// Future independent action permissions must remain explicitly configurable.
const pageActions = new Set([
  'sample.inbound.confirm', 'sample.out_warehouse.sign', 'sample.out_warehouse.return',
  'sample.return_stock', 'sample.register.undo', 'report.review.undo',
  'report.approval.undo', 'report.report_check.undo', 'testing.data_entry.return',
])

/** Display projection only: retain stored legacy grants in the save payload. */
export function permissionMenuSections<T extends PermissionItem>(items: readonly T[]) {
  const selectable = items.filter((item) => !pageActions.has(item.code))
  return {
    menus: groupPermissions(selectable.filter((item) => menus.has(item.code))
      .map((item) => ({ ...item, name: menus.get(item.code)! }))),
    independent: groupPermissions(selectable.filter((item) => !menus.has(item.code))),
    impliedActionCount: items.length - selectable.length,
  }
}

/** Bulk selection changes only this section; never grants unrelated/hidden codes. */
export function setPermissionSection(selected: readonly string[], section: readonly string[], checked: boolean) {
  const scope = new Set(section)
  return checked ? [...new Set([...selected, ...section])]
    : selected.filter((code) => !scope.has(code))
}
