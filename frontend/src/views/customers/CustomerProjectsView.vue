<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import ProjectImportModal from '../../components/customers/ProjectImportModal.vue'
import CustomerProjectModal from '../../components/customers/CustomerProjectModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { canManageProjects, projectColumns, type ProjectQuery, type ProjectPage, type CustomerProject } from '../../types/customers/projects'
const route = useRoute(), router = useRouter()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const query = computed<ProjectQuery>(() => ({ name: text('name'), code: text('code'), supervisionNumber: text('supervisionNumber'), page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10 }))
const draft = reactive({ name: '', code: '', supervisionNumber: '' })
const fields = [{ key: 'name', label: '工程名称' }, { key: 'code', label: '工程编号' }, { key: 'supervisionNumber', label: '监督登记号' }] as const
watch(query, value => { Object.assign(draft, { name: value.name || '', code: value.code || '', supervisionNumber: value.supervisionNumber || '' }) }, { immediate: true })
const canWrite = computed(() => canManageProjects(currentActor.value))
const data = ref<ProjectPage>({ items: [], total: 0, page: 1, pageSize: 10 }), selected = ref<string[]>([])
const loading = ref(false), exporting = ref(false), error = ref<ErrorValue>(''), exportError = ref<ErrorValue>('')
const columnKeys = computed(() => parseTableColumns(projectColumns, route.query.columns))
const columns = computed(() => projectColumns.filter(column => columnKeys.value.includes(column.key)))
const modal = ref<{ mode: 'new' | 'edit' | 'view' | 'delete' | 'batch'; row?: CustomerProject; ids?: string[]; key?: number }>(), toast = ref<InstanceType<typeof TemplateToast>>(), message = ref('')
const importing = ref(false)
let modalKey = 0
const toolbarActions = computed(() => [{ label: '批量修改', icon: 'ti ti-edit', disabled: !canWrite.value || loading.value || !selected.value.length }, { label: '下载模板', icon: 'ti ti-download', disabled: exporting.value }, { label: '导入', icon: 'ti ti-upload', disabled: !canWrite.value || loading.value }])
function toolbarAction(index: number) { if (index === 0) modal.value = { mode: 'batch', ids: [...selected.value] }; else if (index === 1) void exportRows(false, true); else importing.value = true }
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
let epoch = 0, exportEpoch = 0, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.customerProjects(query.value, request.signal); if (token === epoch) data.value = result }
  catch (issue) { if (token === epoch && !request.signal.aborted) { error.value = normalizeError(issue); data.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() {
  if (loading.value) return
  const previous = route.fullPath
  await patch({ ...Object.fromEntries(fields.map(field => [field.key, String(draft[field.key]).trim() || undefined])), page: '1' })
  if (previous === route.fullPath) void load()
}
function toggleColumn(key: string, checked: boolean) {
  const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key)
  void patch({ columns: [...keys].join(',') })
}
async function saved(again = false, count?: number) {
  message.value = count !== undefined ? `成功导入 ${count} 条工程记录。` : modal.value?.mode === 'delete' ? '工程已删除。' : '工程已保存。'
  modal.value = again ? { mode: 'new', key: ++modalKey } : undefined; importing.value = false; void load(); await nextTick(); toast.value?.show()
}
async function exportRows(onlySelected: boolean, template = false) {
  if (exporting.value || !template && (loading.value || error.value || onlySelected && !selected.value.length)) return
  const token = ++exportEpoch; exporting.value = true; exportError.value = ''
  try {
    const blob = template ? await registrationDemo.projectTemplate() : await registrationDemo.exportCustomerProjects({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) })
    if (token === exportEpoch) downloadBlob(blob, template ? '工程导入模板.csv' : '工程.csv')
  } catch (issue) { if (token === exportEpoch) exportError.value = normalizeError(issue) }
  finally { if (token === exportEpoch) exporting.value = false }
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id], (values, old) => {
  exportEpoch++; exporting.value = false; exportError.value = ''
  if (old && values[1] !== old[1]) { modal.value = undefined; importing.value = false; data.value.items = [] }
  void load()
}, { immediate: true })
onBeforeUnmount(() => { epoch++; exportEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading title="工程登记" />
  <section class="card" aria-label="工程列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">工程</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ data.total }}</span></div>
      <TableToolbar label="工程" :adaptive-actions="toolbarActions" @action="toolbarAction" :columns="projectColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows"><button type="button" class="btn btn-primary text-nowrap" :disabled="!canWrite || loading" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button></TableToolbar>
    </div>
    <form class="card-body border-bottom" aria-label="工程查询" @submit.prevent="search"><QueryFormLayout>
      <div class="row g-3"><div v-for="field in fields" :key="field.key" class="col-12 col-md-4"><label :for="`project-filter-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`project-filter-${field.key}`" v-model="draft[field.key]" class="form-control" type="text" maxlength="200" /></div></div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
    </QueryFormLayout></form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable label="工程" :rows="data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.name || row.code" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :pagination="{ ...data, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })">
      <template #actions="{ row }">
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'delete', row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
      </template>
    </DataTable>
  </section>
  <CustomerProjectModal v-if="modal" :key="modal.key" :mode="modal.mode" :row="modal.row" :ids="modal.ids" @close="modal = undefined" @saved="saved" />
  <ProjectImportModal v-if="importing" @close="importing = false" @saved="saved(false, $event)" />
  <TemplateToast ref="toast" :message="message" />
</template>
