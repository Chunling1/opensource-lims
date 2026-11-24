<script setup lang="ts" generic="Row extends object, Key extends Extract<keyof Row, string>">
import { computed } from 'vue'
import LoadState from '../LoadState.vue'
import TablePagination from './TablePagination.vue'
import TableRowMenu from './TableRowMenu.vue'
import type { TableColumn, TablePaginationState } from '../../../types/common/table'
import type { ErrorValue } from '../../../services/common/errors'
import { tableColumnClasses, tableCellText, tableCellPreview, tableSelectionState } from '../../../services/common/table'

const props = withDefaults(defineProps<{
  label: string
  rows: readonly Row[]
  columns: readonly TableColumn<Key>[]
  rowKey: (row: Row) => string
  rowLabel: (row: Row) => string
  selected?: readonly string[]
  selectable?: (row: Row) => boolean
  selectionDisabledReason?: (row: Row) => string | undefined
  highlightSelected?: boolean
  sortKey?: string
  direction?: string
  pagination?: TablePaginationState
  loading?: boolean
  error?: ErrorValue
  preserveRowsOnLoading?: boolean
  actionsDisabled?: boolean
  /** Pin the action column to the scroll container's right edge. */
  stickyActions?: boolean
}>(), { stickyActions: true })
const emit = defineEmits<{
  'update:selected': [ids: string[]]
  sort: [key: string]
  page: [page: number]
  size: [size: number]
  retry: []
  rowClick: [row: Row, event: MouseEvent]
}>()
const eligible = computed(() => props.rows.filter(canSelect).map(props.rowKey))
const selection = computed(() => tableSelectionState(eligible.value, props.selected ?? []))
const showLoadState = computed(() => !!props.error || props.loading && (!props.preserveRowsOnLoading || !props.rows.length))
function canSelect(row: Row) { return props.selectable?.(row) ?? true }
function toggle(row: Row, checked: boolean) {
  if (props.loading || !canSelect(row)) return
  const id = props.rowKey(row), next = new Set(props.selected)
  if (checked) next.add(id); else next.delete(id)
  emit('update:selected', [...next])
}
function selectPage() {
  if (!props.loading) emit('update:selected', selection.value.all ? [] : [...eligible.value])
}
function rowClick(row: Row, event: MouseEvent) {
  if (!props.loading && !(event.target as Element).closest('a, button, input, label, select, textarea, [role="button"]')) emit('rowClick', row, event)
}
function ariaSort(key: string): 'none' | 'ascending' | 'descending' {
  return props.sortKey !== key ? 'none' : props.direction === 'asc' ? 'ascending' : 'descending'
}
function sortIcon(key: string) { return props.sortKey !== key ? 'ti ti-arrows-sort' : props.direction === 'asc' ? 'ti ti-arrow-up' : 'ti ti-arrow-down' }
</script>

<template>
  <slot name="toolbar" />
  <div v-if="showLoadState" class="p-3"><LoadState :loading="loading" :error="error" @retry="emit('retry')" /></div>
  <div v-else class="position-relative">
    <div :inert="loading" :aria-busy="!!loading">
    <div class="table-responsive">
      <table class="table table-nowrap table-hover align-middle mb-0" :aria-label="`${label}列表`">
        <thead class="table-light"><tr>
          <th v-if="selected !== undefined" scope="col"><input class="form-check-input" type="checkbox" :aria-label="`全选当前页${label}`" :disabled="!eligible.length || loading" :checked="selection.all" :indeterminate="selection.partial" @change="selectPage" /></th>
          <th v-for="column in columns" :key="column.key" scope="col" :class="tableColumnClasses(column, true)" :aria-sort="column.sort ? ariaSort(column.sort) : undefined">
            <button v-if="column.sort" type="button" class="btn btn-link p-0 text-body-emphasis text-nowrap" :disabled="loading" @click="emit('sort', column.sort)">{{ column.label }} <i :class="sortIcon(column.sort)" aria-hidden="true"></i></button>
            <template v-else>{{ column.label }}</template>
          </th>
          <th v-if="$slots.actions" class="text-center" :class="{ 'position-sticky end-0 z-1 bg-light': stickyActions }" scope="col" aria-label="操作" title="操作"><i class="ti ti-menu-2 fs-4 text-muted" aria-hidden="true"></i></th>
        </tr></thead>
        <tbody :class="{ 'opacity-25': loading }">
          <tr v-for="row in rows" :key="rowKey(row)" :class="{ 'table-active': highlightSelected && selected?.includes(rowKey(row)) }" @click="rowClick(row, $event)">
            <td v-if="selected !== undefined"><input class="form-check-input" type="checkbox" :checked="selected.includes(rowKey(row))" :disabled="!canSelect(row) || loading" :title="selectionDisabledReason?.(row)" :aria-label="`选择${label} ${rowLabel(row)}`" @change="toggle(row, ($event.target as HTMLInputElement).checked)" /></td>
            <td v-for="column in columns" :key="column.key" :class="tableColumnClasses(column)">
              <slot :name="`cell-${column.key}`" :row="row" :column="column" :text="tableCellText(row[column.key], column)">
                <span v-if="column.truncate || column.fullTitle" :title="column.fullTitle ? tableCellText(row[column.key], column) : undefined">{{ tableCellPreview(tableCellText(row[column.key], column), column.truncate) }}</span>
                <template v-else>{{ tableCellText(row[column.key], column) }}</template>
              </slot>
            </td>
            <td v-if="$slots.actions" class="text-center" :class="{ 'position-sticky end-0 z-1 bg-body-secondary': stickyActions }"><div class="dropdown"><TableRowMenu :label="`${rowLabel(row)} 更多操作`" :disabled="actionsDisabled || loading"><slot name="actions" :row="row" /></TableRowMenu></div></td>
          </tr>
          <tr v-if="!rows.length"><td :colspan="columns.length + Number(selected !== undefined) + Number(!!$slots.actions)" class="text-center py-5"><i class="ti ti-inbox display-6 text-muted" aria-hidden="true"></i><slot name="empty"><p class="mt-2 mb-0">暂无符合条件的{{ label }}</p></slot></td></tr>
        </tbody>
      </table>
    </div>
    <TablePagination v-if="pagination" :label="label" v-bind="pagination" @page="emit('page', $event)" @size="emit('size', $event)" />
    </div>
    <div v-if="loading" class="position-absolute top-0 start-0 w-100 h-100 z-2 d-flex align-items-center justify-content-center">
      <LoadState loading />
    </div>
  </div>
</template>
