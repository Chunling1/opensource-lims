<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import MaintenanceCostImportModal from '../../components/quality/MaintenanceCostImportModal.vue'
import MaintenanceCostModal from '../../components/quality/MaintenanceCostModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { canManageMaintenanceCosts, maintenanceCostColumns, type MaintenanceCostQuery, type MaintenanceCostPage, type MaintenanceCostRecord } from '../../types/quality/maintenanceCosts'
const route = useRoute(), router = useRouter()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const query = computed<MaintenanceCostQuery>(() => ({ name: text('name'), quantity: text('quantity'), department: text('department'), page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10 }))
const draft = reactive({ name: '', quantity: '', department: '' })
const fields = [{ key: 'name', label: '维护项目' }, { key: 'quantity', label: '数量' }, { key: 'department', label: '部门' }] as const
watch(query, value => { Object.assign(draft, { name: value.name || '', quantity: value.quantity || '', department: value.department || '' }) }, { immediate: true })
const canWrite = computed(() => canManageMaintenanceCosts(currentActor.value))
const data = ref<MaintenanceCostPage>({ items: [], total: 0, page: 1, pageSize: 10 }), selected = ref<string[]>([])
const loading = ref(false), exporting = ref(false), error = ref<ErrorValue>(''), exportError = ref<ErrorValue>('')
const columnKeys = computed(() => parseTableColumns(maintenanceCostColumns, route.query.columns))
const columns = computed(() => maintenanceCostColumns.filter(column => columnKeys.value.includes(column.key)))
const modal = ref<{ mode: 'new' | 'edit' | 'view' | 'delete'; row?: MaintenanceCostRecord }>(), toast = ref<InstanceType<typeof TemplateToast>>(), message = ref('')
const importing = ref(false)
const toolbarActions = computed(() => [{ label: '下载模板', icon: 'ti ti-download', disabled: exporting.value }, { label: '导入', icon: 'ti ti-upload', disabled: !canWrite.value || loading.value }])
function toolbarAction(index: number) { if (index === 0) void exportRows(false, true); else importing.value = true }
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
let epoch = 0, exportEpoch = 0, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.maintenanceCosts(query.value, request.signal); if (token === epoch) data.value = result }
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
async function saved(count?: number) {
  message.value = count !== undefined ? `成功导入 ${count} 条设备维护费用记录。` : modal.value?.mode === 'delete' ? '设备维护费用已删除。' : '设备维护费用已保存。'
  modal.value = undefined; importing.value = false; void load(); await nextTick(); toast.value?.show()
}
async function exportRows(onlySelected: boolean, template = false) {
  if (exporting.value || !template && (loading.value || error.value || onlySelected && !selected.value.length)) return
  const token = ++exportEpoch; exporting.value = true; exportError.value = ''
  try {
    const blob = template ? await registrationDemo.maintenanceCostTemplate() : await registrationDemo.exportMaintenanceCosts({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) })
    if (token === exportEpoch) downloadBlob(blob, template ? '设备维护费用导入模板.csv' : '设备维护费用.csv')
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
  <PageHeading title="设备维护费用" />
  <section class="card" aria-label="设备维护费用列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">设备维护费用</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ data.total }}</span></div>
      <TableToolbar label="设备维护费用" :adaptive-actions="toolbarActions" @action="toolbarAction" :columns="maintenanceCostColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows"><button type="button" class="btn btn-primary text-nowrap" :disabled="!canWrite || loading" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button></TableToolbar>
    </div>
    <form class="card-body border-bottom" aria-label="设备维护费用查询" @submit.prevent="search"><QueryFormLayout>
      <div class="row g-3"><div v-for="field in fields" :key="field.key" class="col-12 col-md-4"><label :for="`maintenance-cost-filter-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`maintenance-cost-filter-${field.key}`" v-model="draft[field.key]" class="form-control" :type="field.key === 'quantity' ? 'number' : 'text'" :min="field.key === 'quantity' ? 0 : undefined" :step="field.key === 'quantity' ? '0.001' : undefined" :max="field.key === 'quantity' ? 1000000 : undefined" maxlength="200" /></div></div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
    </QueryFormLayout></form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable label="设备维护费用" :rows="data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.name" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :pagination="{ ...data, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })">
      <template #cell-unitPrice="{ row }">{{ row.unitPrice === null ? '—' : row.unitPrice.toFixed(2) }}</template>
      <template #cell-totalAmount="{ row }">{{ row.totalAmount === null ? '—' : row.totalAmount.toFixed(2) }}</template>
      <template #actions="{ row }">
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'delete', row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
      </template>
    </DataTable>
  </section>
  <MaintenanceCostModal v-if="modal" :mode="modal.mode" :row="modal.row" @close="modal = undefined" @saved="saved" />
  <MaintenanceCostImportModal v-if="importing" @close="importing = false" @saved="saved" />
  <TemplateToast ref="toast" :message="message" />
</template>
