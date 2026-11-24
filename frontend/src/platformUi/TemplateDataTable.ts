import { defineComponent, h, isVNode, Fragment, Text, Comment, type VNode } from 'vue'
import DataTable from '../components/common/table/DataTable.vue'
import { tableCellPreview } from '../services/common/table'

// Match the supplied registration table: 20 characters, native full-text title.
export const DEFAULT_CELL_LIMIT = 20
const textTags = new Set(['span', 'strong', 'b', 'em', 'small', 'div', 'p'])
function plainText(node: unknown): string | undefined {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) {
    const parts = node.map(plainText)
    return parts.every(p => p !== undefined) ? parts.join('') : undefined
  }
  if (!isVNode(node)) return undefined
  if (node.type === Comment) return ''
  if (node.type !== Text && node.type !== Fragment && !(typeof node.type === 'string' && textTags.has(node.type))) return undefined
  if (Object.keys(node.props || {}).some(key => /^on[A-Z]/.test(key)) || node.props?.role || node.props?.tabindex != null || /badge/.test(String(node.props?.class || ''))) return undefined
  return plainText(node.children ?? '')
}
export function previewCell(nodes: VNode[], limit = DEFAULT_CELL_LIMIT): VNode[] {
  const value = plainText(nodes)
  // Interactive controls, status components and nested tables retain their slots.
  return value === undefined || Array.from(value).length <= limit ? nodes : [h('span', { title: value }, tableCellPreview(value, limit))]
}
const PlatformTemplateDataTable = defineComponent({
  name: 'PlatformTemplateDataTable', inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => {
      const columns = (attrs.columns as any[] || []).map(column => ({ ...column, truncate: column.truncate ?? DEFAULT_CELL_LIMIT, fullTitle: true, wrap: false }))
      const adapted = Object.fromEntries(Object.entries(slots).map(([name, slot]) => [name, name.startsWith('cell-') ? (scope: any) => previewCell(slot?.(scope) || [], columns.find(c => `cell-${c.key}` === name)?.truncate) : slot]))
      return h(DataTable as any, { ...attrs, columns }, adapted)
    }
  },
})
// Keep the supplied component's generic row, column and event contracts.
export default PlatformTemplateDataTable as unknown as typeof DataTable
