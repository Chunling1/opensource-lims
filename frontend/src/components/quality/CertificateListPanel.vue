<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import QueryFormLayout from '../common/QueryFormLayout.vue'
import DataTable from '../common/table/DataTable.vue'
import TableToolbar from '../common/table/TableToolbar.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { parseTableColumns } from '../../services/common/table'
import { downloadBlob } from '../../services/reports/reportPdf'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import type { TableColumn } from '../../types/common/table'
import type { CertificateListKind, CertificateListRow, CertificatePage } from '../../types/quality/certificates'

const props = defineProps<{
  label: string; kind: CertificateListKind; columns: TableColumn[]
  fields: { key: string; label: string; options?: string[] }[]
  selected: string[]; parentIds?: string[]; scope?: 'related' | 'all'; relationKey?: string
  emptyPrompt?: string; collapsible?: boolean; selectionCaption?: string; activeScopeTab?: string; rowFiltersChildren?: boolean; disabled?: boolean
}>()
const emit = defineEmits<{ 'update:selected': [ids: string[]]; loaded: [rows: CertificateListRow[]]; loading: [value: boolean] }>()
const collapsed = ref(false), page = ref(1), pageSize = ref(5)
const toolbarActions = computed(() => props.collapsible ? [{ label: collapsed.value ? '展开' : '收起', icon: collapsed.value ? 'ti ti-chevron-down' : 'ti ti-chevron-up', expanded: !collapsed.value, controls: `${props.label}-content` }] : [])
const draft = reactive<Record<string, string>>({}), applied = ref<Record<string, string>>({})
const result = ref<CertificatePage>({ items: [], total: 0, page: 1, pageSize: 5 })
const loading = ref(false), error = ref<ErrorValue>(''), exportError = ref<ErrorValue>(''), exporting = ref(false)
const columnChoice = ref<string>()
const columnKeys = computed(() => parseTableColumns(props.columns, columnChoice.value))
const visibleColumns = computed(() => props.columns.filter(c => columnKeys.value.includes(c.key)))
const query = () => ({ filters: { ...applied.value }, page: page.value, pageSize: pageSize.value, scope: props.scope || 'related', parentIds: props.parentIds || [] })
let controller: AbortController | undefined, epoch = 0, alive = true
async function load() {
  controller?.abort(); const active = controller = new AbortController(), token = ++epoch
  error.value = ''; exportError.value = ''
  if (props.emptyPrompt) { result.value = { items: [], total: 0, page: 1, pageSize: pageSize.value }; loading.value = false; emit('loading', false); return }
  loading.value = true; emit('loading', true)
  try {
    const data = await registrationDemo.certificateList(props.kind, query(), active.signal)
    if (token === epoch) { result.value = data; page.value = data.page; emit('loaded', data.items) }
  } catch (issue) { if (token === epoch && !active.signal.aborted) { error.value = normalizeError(issue); result.value.items = [] } }
  finally { if (token === epoch) { loading.value = false; emit('loading', false) } }
}
watch(() => JSON.stringify([props.kind, props.scope, props.parentIds, props.relationKey, currentActor.value.id]), () => { page.value = 1; void load() }, { immediate: true })
onBeforeUnmount(() => { alive = false; epoch++; controller?.abort() })
function search() { if (loading.value) return; applied.value = Object.fromEntries(Object.entries(draft).map(([key, value]) => [key, value?.trim() || ''])); page.value = 1; emit('update:selected', []); void load() }
function resize(size: number) { pageSize.value = size; page.value = 1; void load() }
function turn(next: number) { page.value = next; void load() }
function rowLabel(row: CertificateListRow) { return row.number ? row.number + (row.item ? ` · ${row.code}` : '') : row.code || row.id }
function selectRow(row: CertificateListRow) {
  if (props.rowFiltersChildren && !props.selected.includes(row.id)) emit('update:selected', [row.id])
}
function toggleColumn(key: string, checked: boolean) {
  const next = new Set(columnKeys.value)
  if (checked) next.add(key); else next.delete(key)
  columnChoice.value = [...next].join(',')
}
async function exportRows(onlySelected: boolean) {
  if (loading.value || error.value || exporting.value || !result.value.total) return
  const actorId = currentActor.value.id
  const input = { ...query(), columns: visibleColumns.value.map(c => c.key), ...(onlySelected ? { ids: [...props.selected] } : {}) }
  exporting.value = true; exportError.value = ''
  try {
    const blob = await registrationDemo.exportCertificateList(props.kind, input)
    if (alive && actorId === currentActor.value.id) downloadBlob(blob, `${props.label}.csv`)
  } catch (issue) { if (alive && actorId === currentActor.value.id) exportError.value = normalizeError(issue) }
  finally { exporting.value = false }
}
</script>

<template>
  <section class="card" :aria-label="`${label}区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex flex-wrap align-items-center gap-2">
        <h5 class="card-title mb-0">{{ label }}列表</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ result.total }}</span>
        <span v-if="collapsible ? collapsed : selected.length" class="text-muted text-break">{{ selectionCaption || `已选 ${selected.length} 条` }}</span>
      </div>
      <TableToolbar :label="label" :adaptive-actions="toolbarActions" :columns="columns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting || !result.total" @action="collapsed = !collapsed" @column="toggleColumn" @reset="columnChoice = undefined" @export="exportRows"><template v-if="$slots['header-actions']" #default><slot name="header-actions" /></template></TableToolbar>
    </div>
    <div v-show="!collapsed" :id="`${label}-content`">
      <div v-if="$slots.scope" class="d-flex flex-wrap align-items-center gap-3 px-3 border-bottom"><slot name="scope" /></div>
      <div :id="`${label}-panel`" :role="activeScopeTab ? 'tabpanel' : undefined" :aria-labelledby="activeScopeTab">
      <form class="card-body border-bottom" :aria-label="`${label}查询`" @submit.prevent="search">
        <QueryFormLayout>
          <div class="row g-3"><div v-for="field in fields" :key="field.key" class="col-12 col-sm-6" :class="{ 'col-xl-3': collapsible, 'col-lg-4': !collapsible && fields.length === 3 }">
            <label class="form-label" :for="`${label}-${field.key}`">{{ field.label }}</label>
            <select v-if="field.options" :id="`${label}-${field.key}`" v-model="draft[field.key]" class="form-select"><option :value="undefined">全部</option><option v-for="option in field.options" :key="option" :value="option">{{ option }}</option></select>
            <input v-else :id="`${label}-${field.key}`" v-model="draft[field.key]" class="form-control" maxlength="200" />
          </div></div>
          <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
        </QueryFormLayout>
      </form>
      <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
      <DataTable :label="label" :rows="result.items" :loading="loading" :error="error" preserve-rows-on-loading :actions-disabled="disabled" @retry="load" :columns="visibleColumns" :row-key="row => row.id" :row-label="rowLabel" :selected="selected" highlight-selected :pagination="{ total: result.total, page, pageSize, sizes: [5, 10, 20] }" @update:selected="emit('update:selected', $event)" @row-click="selectRow" @page="turn" @size="resize">
        <template #empty><p class="mt-2 mb-0 text-muted">{{ emptyPrompt || `暂无符合条件的${label}` }}</p></template>
        <template v-if="$slots.attachments" #cell-attachments="{ row }"><slot name="attachments" :row="row" /></template>
        <template v-if="$slots.actions" #actions="{ row }"><slot name="actions" :row="row" /></template>
      </DataTable>
      </div>
    </div>
  </section>
</template>
