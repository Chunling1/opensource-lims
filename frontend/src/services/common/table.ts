import type { TableColumn } from '../../types/common/table'

export function tableColumnClasses(column: TableColumn, header = false) {
  return [header || !column.wrap ? 'text-nowrap' : 'text-wrap text-break', {
    'w-xl': !!column.wrap, 'w-25': header && !!column.wrap, 'text-end': !!column.money,
  }]
}

export function tableCellText(value: unknown, column: Pick<TableColumn, 'money'>): string {
  if (column.money) return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '—'
  if (typeof value === 'string') return value.trim() ? value : '—'
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : '—'
}

export function tableCellPreview(text: string, limit?: number): string {
  if (!limit || limit < 1) return text
  const characters = Array.from(text)
  return characters.length > limit ? characters.slice(0, limit).join('') + '…' : text
}

export function parseTableColumns<Key extends string>(columns: readonly TableColumn<Key>[], value: unknown): Key[] {
  const defaults = () => columns.filter(column => column.required || column.default).map(column => column.key)
  if (typeof value !== 'string') return defaults()
  const requested = new Set(value.split(','))
  if (value && !columns.some(column => requested.has(column.key))) return defaults()
  return columns.filter(column => column.required || requested.has(column.key)).map(column => column.key)
}

/** Selection is controlled by the page; select-all replaces it with eligible rows on this page. */
export function tableSelectionState(eligible: readonly string[], selected: readonly string[]) {
  const ids = new Set(selected), count = eligible.filter(id => ids.has(id)).length
  return { all: eligible.length > 0 && count === eligible.length, partial: count > 0 && count < eligible.length }
}
