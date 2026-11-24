<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import DocumentHistoryModal from '../../components/quality/DocumentHistoryModal.vue'
import LibraryDocumentModal from '../../components/quality/LibraryDocumentModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { canManageDocuments, documentModuleTitle, type DocumentModule, documentColumns, type DocumentQuery, type DocumentPage, type LibraryDocumentRow } from '../../types/quality/documentLibrary'
const props = withDefaults(defineProps<{ documentModule?: DocumentModule }>(), { documentModule: 'library' })
const title = computed(() => documentModuleTitle(props.documentModule))
const route = useRoute(), router = useRouter()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const query = computed<DocumentQuery>(() => ({ name: text('name'), category: text('category'), page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10 }))
const draft = reactive({ name: '', category: '' })
const fields = [{ key: 'category', label: '文件分类' }, { key: 'name', label: '文件名称' }] as const
watch(query, value => { Object.assign(draft, { name: value.name || '', category: value.category || '' }) }, { immediate: true })
const canWrite = computed(() => canManageDocuments(currentActor.value))
const data = ref<DocumentPage<LibraryDocumentRow>>({ items: [], total: 0, page: 1, pageSize: 10 }), selected = ref<string[]>([])
const loading = ref(false), exporting = ref(false), error = ref<ErrorValue>(''), exportError = ref<ErrorValue>('')
const columnKeys = computed(() => parseTableColumns(documentColumns, route.query.columns))
const columns = computed(() => documentColumns.filter(column => columnKeys.value.includes(column.key)))
const modal = ref<{ mode: 'new' | 'edit' | 'view' | 'delete' | 'issue' | 'recover' | 'files'; row?: LibraryDocumentRow }>(), toast = ref<InstanceType<typeof TemplateToast>>(), message = ref('')
const history = ref<{ kind: 'issue' | 'recover'; documentId?: string }>()
const toolbarActions = computed(() => [
  { label: '领用记录', icon: 'ti ti-file-text', disabled: loading.value },
  { label: '回收记录', icon: 'ti ti-history', disabled: loading.value },
])
function toolbarAction(index: number) {
  history.value = { kind: index === 0 ? 'issue' : 'recover' }
}
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
let epoch = 0, exportEpoch = 0, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.libraryDocuments(query.value, request.signal, props.documentModule); if (token === epoch) data.value = result }
  catch (issue) { if (token === epoch && !request.signal.aborted) { error.value = normalizeError(issue); data.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() {
  if (loading.value) return
  const previous = route.fullPath
  await patch({ name: draft.name.trim() || undefined, category: draft.category.trim() || undefined, page: '1' })
  if (previous === route.fullPath) void load()
}
function toggleColumn(key: string, checked: boolean) {
  const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key)
  void patch({ columns: [...keys].join(',') })
}
async function saved() {
  message.value = modal.value?.mode === 'issue' ? '领用已登记。' : modal.value?.mode === 'recover' ? '回收已登记。' : modal.value?.mode === 'delete' ? '文件已删除。' : '文件信息已保存。'
  modal.value = undefined; void load(); await nextTick(); toast.value?.show()
}
async function exportRows(onlySelected: boolean) {
  if (exporting.value || loading.value || error.value || onlySelected && !selected.value.length) return
  const token = ++exportEpoch; exporting.value = true; exportError.value = ''
  try {
    const blob = await registrationDemo.exportLibraryDocuments({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) }, props.documentModule)
    if (token === exportEpoch) downloadBlob(blob, `${title.value}.csv`)
  } catch (issue) { if (token === exportEpoch) exportError.value = normalizeError(issue) }
  finally { if (token === exportEpoch) exporting.value = false }
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id, () => props.documentModule], (values, old) => {
  exportEpoch++; exporting.value = false; exportError.value = ''
  if (old && (values[1] !== old[1] || values[2] !== old[2])) { modal.value = undefined; history.value = undefined; data.value.items = [] }
  void load()
}, { immediate: true })
onBeforeUnmount(() => { epoch++; exportEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ data.total }}</span></div>
      <TableToolbar :label="title" :adaptive-actions="toolbarActions" @action="toolbarAction" :columns="documentColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows"><button type="button" class="btn btn-primary text-nowrap" :disabled="!canWrite || loading" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button></TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}查询`" @submit.prevent="search"><QueryFormLayout>
      <div class="row g-3"><div v-for="field in fields" :key="field.key" class="col-12 col-sm-6"><label :for="`document-filter-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`document-filter-${field.key}`" v-model="draft[field.key]" class="form-control" maxlength="200" /></div></div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
    </QueryFormLayout></form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable :label="title" :rows="data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.name" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :pagination="{ ...data, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })">
      <template #actions="{ row }">
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite || !!row.historyCount" :title="row.historyCount ? '该文件已有领用或回收记录' : !canWrite ? '当前身份仅支持查看' : undefined" @click="modal = { mode: 'delete', row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite || !row.remaining" @click="modal = { mode: 'issue', row }"><i class="ti ti-download me-2 text-muted" aria-hidden="true"></i>领用登记</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite || !row.outstanding" @click="modal = { mode: 'recover', row }"><i class="ti ti-upload me-2 text-muted" aria-hidden="true"></i>回收登记</button>
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { mode: 'files', row }"><i class="ti ti-paperclip me-2 text-muted" aria-hidden="true"></i>附件管理</button>
      </template>
    </DataTable>
  </section>
  <LibraryDocumentModal v-if="modal" :document-module="documentModule" :mode="modal.mode" :row="modal.row" @close="modal = undefined" @saved="saved" />
  <DocumentHistoryModal v-if="history" :document-module="documentModule" v-bind="history" @close="history = undefined" />
  <TemplateToast ref="toast" :message="message" />
</template>
