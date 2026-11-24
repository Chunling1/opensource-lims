<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import EquipmentGroupDefinitionModal from '../../components/quality/EquipmentGroupDefinitionModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { equipmentGroupColumns, canManageDefinitions, definitionSubject, type DefinitionModule, type EquipmentGroupQuery, type EquipmentGroupPage, type EquipmentGroupRow } from '../../types/quality/equipmentGroups'
const props = withDefaults(defineProps<{ definitionModule?: DefinitionModule }>(), { definitionModule: 'equipment' })
const subject = computed(() => definitionSubject(props.definitionModule)), title = computed(() => `${subject.value}定义`)
const route = useRoute(), router = useRouter()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const query = computed<EquipmentGroupQuery>(() => ({ name: text('name'), page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10 }))
const draft = ref('')
watch(query, value => { draft.value = value.name || '' }, { immediate: true })
const canWrite = computed(() => canManageDefinitions(currentActor.value))
const data = ref<EquipmentGroupPage>({ items: [], total: 0, page: 1, pageSize: 10 }), selected = ref<string[]>([])
const loading = ref(false), exporting = ref(false), error = ref<ErrorValue>(''), exportError = ref<ErrorValue>('')
const columnKeys = computed(() => parseTableColumns(equipmentGroupColumns, route.query.columns))
const columns = computed(() => equipmentGroupColumns.filter(column => columnKeys.value.includes(column.key)))
const modal = ref<{ mode: 'new' | 'edit' | 'view' | 'delete'; row?: EquipmentGroupRow }>(), toast = ref<InstanceType<typeof TemplateToast>>(), message = ref('')
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
let epoch = 0, exportEpoch = 0, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.equipmentGroupDefinitions(query.value, request.signal, props.definitionModule); if (token === epoch) data.value = result }
  catch (issue) { if (token === epoch && !request.signal.aborted) { error.value = normalizeError(issue); data.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() {
  if (loading.value) return
  const previous = route.fullPath
  await patch({ name: draft.value.trim() || undefined, page: '1' })
  if (previous === route.fullPath) void load()
}
function toggleColumn(key: string, checked: boolean) {
  const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key)
  void patch({ columns: [...keys].join(',') })
}
async function saved() {
  message.value = modal.value?.mode === 'delete' ? `${subject.value}已删除。` : `${subject.value}已保存。`
  modal.value = undefined; void load(); await nextTick(); toast.value?.show()
}
async function exportRows(onlySelected: boolean) {
  if (exporting.value || loading.value || error.value || onlySelected && !selected.value.length) return
  const token = ++exportEpoch; exporting.value = true; exportError.value = ''
  try {
    const blob = await registrationDemo.exportEquipmentGroupDefinitions({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) }, props.definitionModule)
    if (token === exportEpoch) downloadBlob(blob, `${title.value}.csv`)
  } catch (issue) { if (token === exportEpoch) exportError.value = normalizeError(issue) }
  finally { if (token === exportEpoch) exporting.value = false }
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id, () => props.definitionModule], (values, old) => {
  exportEpoch++; exporting.value = false; exportError.value = ''
  if (old && (values[1] !== old[1] || values[2] !== old[2])) { modal.value = undefined; data.value.items = [] }
  void load()
}, { immediate: true })
onBeforeUnmount(() => { epoch++; exportEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ data.total }}</span></div>
      <TableToolbar :label="title" :columns="equipmentGroupColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows"><button type="button" class="btn btn-primary text-nowrap" :disabled="!canWrite || loading" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button></TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}查询`" @submit.prevent="search"><QueryFormLayout>
      <div class="row g-3"><div class="col-12"><label for="group-filter-name" class="form-label">列表项值</label><input id="group-filter-name" v-model="draft" class="form-control" maxlength="200" /></div></div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
    </QueryFormLayout></form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable :label="title" :rows="data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.name" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :pagination="{ ...data, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })">
      <template #actions="{ row }">
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'delete', row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
      </template>
    </DataTable>
  </section>
  <EquipmentGroupDefinitionModal v-if="modal" :definition-module="definitionModule" :mode="modal.mode" :row="modal.row" @close="modal = undefined" @saved="saved" />
  <TemplateToast ref="toast" :message="message" />
</template>
