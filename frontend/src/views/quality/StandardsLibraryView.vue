<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import StandardModal from '../../components/quality/StandardModal.vue'
import StandardGroupsModal from '../../components/quality/StandardGroupsModal.vue'
import StandardImportModal from '../../components/quality/StandardImportModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { canManageStandards, canEditStandard, standardColumns, standardQualifications, type StandardQuery, type StandardPage, type StandardRow } from '../../types/quality/standards'
const props = defineProps<{ departmentMode?: boolean }>()
const title = computed(() => props.departmentMode ? '检测标准基础信息库[科室]' : '检测标准基础信息库')
const route = useRoute(), router = useRouter()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const query = computed<StandardQuery>(() => ({ code: text('code'), name: text('name'), category: text('category'), qualification: text('qualification'), controlNumber: text('controlNumber'), location: text('location'), departmentId: text('departmentId'), ownDepartment: props.departmentMode || text('ownDepartment') === '1', page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10 }))
const draft = reactive({ code: '', name: '', category: '', qualification: '', controlNumber: '', location: '', departmentId: '', ownDepartment: false })
watch(query, value => { Object.assign(draft, value) }, { immediate: true })
const more = ref(false), groupIds = ref<string[]>(), importing = ref(false)
const textFields = [{ key: 'code', label: '标准编号' }, { key: 'name', label: '标准名称' }, { key: 'category', label: '类别' }] as const
const activeFilters = computed(() => [draft.controlNumber, draft.location, draft.departmentId, draft.ownDepartment].filter(Boolean).length)
const canWrite = computed(() => canManageStandards(currentActor.value))
const data = ref<StandardPage>({ items: [], total: 0, page: 1, pageSize: 10, departments: [], locations: [] }), selected = ref<string[]>([])
const toolbarActions = computed(() => [
  { key: 'groups', label: '分组关联', icon: 'ti ti-link', disabled: !canWrite.value || loading.value || !selected.value.length },
  { key: 'template', label: '下载模板', icon: 'ti ti-download', disabled: exporting.value },
  { key: 'import', label: '导入', icon: 'ti ti-upload', disabled: !canWrite.value || loading.value },
].filter(action => !props.departmentMode || action.key === 'groups'))
function action(index: number) { const key = toolbarActions.value[index]?.key; if (key === 'template') void exportRows(false, true); else if (key === 'groups' && canWrite.value && selected.value.length) groupIds.value = [...selected.value]; else if (key === 'import' && canWrite.value) importing.value = true }
async function relatedSaved(count?: number) { groupIds.value = undefined; importing.value = false; message.value = count === undefined ? '分组关联已保存。' : `成功导入 ${count} 条标准。`; void load(); await nextTick(); toast.value?.show() }
const loading = ref(false), exporting = ref(false), error = ref<ErrorValue>(''), exportError = ref<ErrorValue>('')
const columnKeys = computed(() => parseTableColumns(standardColumns, route.query.columns))
const columns = computed(() => standardColumns.filter(column => columnKeys.value.includes(column.key)))
const modal = ref<{ mode: 'new' | 'edit' | 'view' | 'delete'; row?: StandardRow }>(), toast = ref<InstanceType<typeof TemplateToast>>(), message = ref('')
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
let epoch = 0, exportEpoch = 0, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.standards(query.value, request.signal, props.departmentMode); if (token === epoch) data.value = result }
  catch (issue) { if (token === epoch && !request.signal.aborted) { error.value = normalizeError(issue); data.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() {
  if (loading.value) return
  const previous = route.fullPath
  await patch({ ...Object.fromEntries(textFields.map(field => [field.key, draft[field.key].trim() || undefined])), qualification: draft.qualification || undefined, controlNumber: draft.controlNumber.trim() || undefined, location: draft.location || undefined, departmentId: draft.departmentId || undefined, ownDepartment: draft.ownDepartment ? '1' : undefined, page: '1' })
  if (previous === route.fullPath) void load()
}
function toggleColumn(key: string, checked: boolean) {
  const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key)
  void patch({ columns: [...keys].join(',') })
}
async function saved() {
  message.value = modal.value?.mode === 'delete' ? '检测标准已删除。' : '检测标准已保存。'
  modal.value = undefined; void load(); await nextTick(); toast.value?.show()
}
async function exportRows(onlySelected: boolean, template = false) {
  if (exporting.value || !template && (loading.value || error.value || onlySelected && !selected.value.length)) return
  const token = ++exportEpoch; exporting.value = true; exportError.value = ''
  try {
    const blob = template ? await registrationDemo.standardTemplate() : await registrationDemo.exportStandards({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) }, props.departmentMode)
    if (token === exportEpoch) downloadBlob(blob, template ? '检测标准导入模板.csv' : `${title.value}.csv`)
  } catch (issue) { if (token === exportEpoch) exportError.value = normalizeError(issue) }
  finally { if (token === exportEpoch) exporting.value = false }
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id, () => props.departmentMode], (values, old) => {
  exportEpoch++; exporting.value = false; exportError.value = ''
  if (old && (values[1] !== old[1] || values[2] !== old[2])) { modal.value = undefined; groupIds.value = undefined; importing.value = false; more.value = false; data.value.items = [] }
  void load()
}, { immediate: true })
onBeforeUnmount(() => { epoch++; exportEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ data.total }}</span></div>
      <TableToolbar :label="title" :adaptive-actions="toolbarActions" @action="action" :columns="standardColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows"><button v-if="!departmentMode" type="button" class="btn btn-primary text-nowrap" :disabled="!canWrite || loading" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button></TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}查询`" @submit.prevent="search"><QueryFormLayout>
      <div class="row g-3"><div v-for="field in textFields" :key="field.key" class="col-12 col-sm-6 col-xl-3"><label :for="`standard-query-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`standard-query-${field.key}`" v-model="draft[field.key]" class="form-control" maxlength="200" /></div>
        <div class="col-12 col-sm-6 col-xl-3"><label for="standard-query-qualification" class="form-label">标准资质类别</label><select id="standard-query-qualification" v-model="draft.qualification" class="form-select"><option value="">全部</option><option v-for="value in standardQualifications" :key="value" :value="value">{{ value }}</option></select></div>
      </div>
      <div v-show="more" id="standard-more-filters" class="row g-3 mt-0">
        <div class="col-12 col-sm-6 col-xl-3"><label for="standard-query-controlNumber" class="form-label">受控号</label><input id="standard-query-controlNumber" v-model="draft.controlNumber" class="form-control" maxlength="200" /></div>
        <div class="col-12 col-sm-6 col-xl-3"><label for="standard-query-location" class="form-label">存放地点</label><select id="standard-query-location" v-model="draft.location" class="form-select"><option value="">全部</option><option v-for="value in data.locations" :key="value" :value="value">{{ value }}</option></select></div>
        <div class="col-12 col-sm-6 col-xl-3"><label for="standard-query-department" class="form-label">使用部门</label><select id="standard-query-department" v-model="draft.departmentId" class="form-select"><option value="">全部</option><option v-for="department in data.departments" :key="department.id" :value="department.id">{{ department.name }}</option></select></div>
        <div class="col-12 col-sm-6 col-xl-3 d-flex align-items-end"><label class="form-check mb-2"><input v-model="draft.ownDepartment" type="checkbox" class="form-check-input" :disabled="departmentMode" /><span class="form-check-label">本部门标准</span></label></div>
      </div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button type="button" class="btn btn-link text-nowrap" :aria-expanded="more" aria-controls="standard-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
    </QueryFormLayout></form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable :label="title" :rows="data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.name" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :pagination="{ ...data, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })">
      <template #cell-outsideScope="{ row }">{{ row.outsideScope ? '是' : '否' }}</template><template #cell-english="{ row }">{{ row.english ? '是' : '否' }}</template>
      <template #actions="{ row }">
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button v-if="!departmentMode" type="button" class="dropdown-item" role="menuitem" :disabled="!canEditStandard(currentActor, row)" @click="modal = { mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button v-if="!departmentMode" type="button" class="dropdown-item" role="menuitem" :disabled="!canEditStandard(currentActor, row)" @click="modal = { mode: 'delete', row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
      </template>
    </DataTable>
  </section>
  <StandardModal v-if="modal" :mode="modal.mode" :row="modal.row" @close="modal = undefined" @saved="saved" />
  <StandardGroupsModal v-if="groupIds?.length" :ids="groupIds" @close="groupIds = undefined" @saved="relatedSaved()" />
  <StandardImportModal v-if="importing" @close="importing = false" @saved="relatedSaved" />
  <TemplateToast ref="toast" :message="message" />
</template>
