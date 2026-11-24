<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import PersonnelModal from '../../components/quality/PersonnelModal.vue'
import PersonnelImportModal from '../../components/quality/PersonnelImportModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { personnelColumns, personnelOptions, type PersonnelFilterKey, type PersonnelPage, type PersonnelQuery, type PersonnelRecord } from '../../types/quality/personnel'
const props = defineProps<{ queryMode?: boolean }>()
const title = computed(() => props.queryMode ? '人员查询' : '人员登记')
const queryLabel = computed(() => props.queryMode ? '人员查询条件' : '人员登记查询')
const route = useRoute(), router = useRouter()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const fields = computed<{ key: PersonnelFilterKey; label: string; options?: string[] }[]>(() => props.queryMode ? [
  { key: 'name', label: '姓名' }, { key: 'qualification', label: '职称', options: personnelOptions.qualification },
  { key: 'education', label: '文化程度' }, { key: 'major', label: '所学专业' }, { key: 'department', label: '所在部门' },
] : [{ key: 'name', label: '姓名' }, { key: 'code', label: '编号' }, { key: 'school', label: '毕业院校' }, { key: 'major', label: '所学专业' }])
const query = computed<PersonnelQuery>(() => ({ ...Object.fromEntries(fields.value.map(f => [f.key, text(f.key)])), sort: text('sort', 'code'), direction: text('direction') === 'desc' ? 'desc' : 'asc', page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10 }))
const draft = reactive<Record<PersonnelFilterKey, string>>({ name: '', code: '', school: '', major: '', qualification: '', education: '', department: '' })
const more = ref(false)
const primaryFields = computed(() => props.queryMode ? fields.value.slice(0, 3) : fields.value)
const extraFields = computed(() => props.queryMode ? fields.value.slice(3) : [])
const activeFilters = computed(() => extraFields.value.filter(f => draft[f.key].trim()).length)
watch(() => route.path, () => { more.value = false })
watch(query, q => { for (const key of Object.keys(draft) as PersonnelFilterKey[]) draft[key] = q[key] || '' }, { immediate: true })
const rows = ref<PersonnelPage>({ items: [], total: 0, page: 1, pageSize: 10 }), loading = ref(false), error = ref<ErrorValue>(''), actionError = ref<ErrorValue>(''), exporting = ref(false), selected = ref<string[]>([]), message = ref('')
const successToast = ref<InstanceType<typeof TemplateToast>>()
const columnKeys = computed(() => parseTableColumns(personnelColumns, route.query.columns)), columns = computed(() => personnelColumns.filter(c => columnKeys.value.includes(c.key)))
const modal = ref<{ mode: 'new' | 'edit' | 'view' | 'delete'; record?: PersonnelRecord }>(), importing = ref(false)
const canWrite = computed(() => currentActor.value.roles.some(r => ['admin', 'quality'].includes(r)))
const toolbarActions = computed(() => props.queryMode ? [] : [
  { label: '下载模板', icon: 'ti ti-download', disabled: exporting.value },
  { label: '导入', icon: 'ti ti-upload', disabled: !canWrite.value || loading.value },
])
function toolbarAction(index: number) { if (index === 0) void download(true); else importing.value = true }
let epoch = 0, actionEpoch = 0, controller: AbortController | undefined
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
async function load() {
  controller?.abort(); const active = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.personnel(query.value, active.signal); if (token === epoch) rows.value = result }
  catch (issue) { if (token === epoch && !active.signal.aborted) { error.value = normalizeError(issue); rows.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() {
  if (loading.value) return
  const previous = route.fullPath
  await patch({ ...Object.fromEntries((Object.keys(draft) as PersonnelFilterKey[]).map(key => [key, fields.value.some(f => f.key === key) ? draft[key].trim() || undefined : undefined])), page: '1' })
  if (previous === route.fullPath) void load()
}
function toggleColumn(key: string, checked: boolean) { const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key); void patch({ columns: [...keys].join(',') }) }
async function download(template = false, onlySelected = false) {
  if (exporting.value || !template && (loading.value || error.value || onlySelected && !selected.value.length)) return
  const token = ++actionEpoch; exporting.value = true; actionError.value = ''
  try {
    const blob = template ? await registrationDemo.personnelTemplate() : await registrationDemo.exportPersonnel({ ...query.value, ...(onlySelected ? { ids: selected.value } : {}) })
    if (token === actionEpoch) downloadBlob(blob, template ? '人员登记导入模板.csv' : `${title.value}.csv`)
  } catch (issue) { if (token === actionEpoch) actionError.value = normalizeError(issue) }
  finally { if (token === actionEpoch) exporting.value = false }
}
async function saved(text: string) { modal.value = undefined; importing.value = false; message.value = text; void load(); await nextTick(); if (message.value === text) successToast.value?.show() }
watch([() => JSON.stringify(query.value), () => currentActor.value.id, () => route.path], (values, old) => { modal.value = undefined; importing.value = false; actionEpoch++; exporting.value = false; actionError.value = ''; message.value = ''; successToast.value?.hide(); if (old && values[1] !== old[1]) rows.value.items = []; void load() }, { immediate: true })
onBeforeUnmount(() => { epoch++; actionEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :adaptive-actions="toolbarActions" :columns="personnelColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @action="toolbarAction" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="download(false, $event)">
        <button v-if="!queryMode" type="button" class="btn btn-primary text-nowrap" :disabled="!canWrite || loading" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="queryLabel" @submit.prevent="search">
      <QueryFormLayout>
        <div class="row g-3 align-items-end"><div v-for="f in primaryFields" :key="f.key" class="col-12 col-sm-6" :class="queryMode ? 'col-xl-4' : 'col-xl-3'">
          <label :for="`personnel-query-${f.key}`" class="form-label">{{ f.label }}</label>
          <select v-if="f.options" :id="`personnel-query-${f.key}`" v-model="draft[f.key]" class="form-select"><option value="">全部</option><option v-for="option in f.options" :key="option" :value="option">{{ option }}</option></select>
          <input v-else :id="`personnel-query-${f.key}`" v-model="draft[f.key]" class="form-control" maxlength="200" />
        </div></div>
        <div v-if="queryMode" v-show="more" id="personnel-query-more-filters" class="row g-3 align-items-end mt-0">
          <div v-for="f in extraFields" :key="f.key" class="col-12 col-sm-6 col-xl-4"><label :for="`personnel-query-${f.key}`" class="form-label">{{ f.label }}</label><input :id="`personnel-query-${f.key}`" v-model="draft[f.key]" class="form-control" maxlength="200" /></div>
        </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button v-if="queryMode" class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="personnel-query-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
    </form>
    <div v-if="actionError" class="px-3 pt-3"><ErrorNotice :error="actionError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="r => r.id" :row-label="r => r.name" v-model:selected="selected" :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })">
      <template #actions="{ row }">
        <button v-if="!queryMode" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'edit', record: row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', record: row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button v-if="!queryMode" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'delete', record: row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
      </template>
    </DataTable>
  </section>
  <TemplateToast ref="successToast" :message="message" tone="success" />
  <PersonnelModal v-if="modal" :key="`${modal.mode}:${modal.record?.id || ''}`" v-bind="modal" @close="modal = undefined" @saved="saved(modal?.mode === 'delete' ? '人员已删除。' : '人员已保存。')" />
  <PersonnelImportModal v-if="importing" @close="importing = false" @saved="saved(`成功导入 ${$event} 条人员记录。`)" />
</template>
