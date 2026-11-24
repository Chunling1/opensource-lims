<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import EquipmentModal from '../../components/quality/EquipmentModal.vue'
import EquipmentDeleteModal from '../../components/quality/EquipmentDeleteModal.vue'
import EquipmentBatchModal from '../../components/quality/EquipmentBatchModal.vue'
import EquipmentGroupsModal from '../../components/quality/EquipmentGroupsModal.vue'
import EquipmentImportModal from '../../components/quality/EquipmentImportModal.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import { emptyEquipment, type EquipmentDraft, type EquipmentRecord } from '../../types/quality/equipmentForm'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { clientYearRange } from '../../services/common/date'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { equipmentLedgerColumns, equipmentStates, equipmentStatusClasses, equipmentDateFields, type EquipmentLedgerPage, type EquipmentLedgerQuery, type EquipmentLedgerRow } from '../../types/quality/equipmentLedger'

const props = defineProps<{ departmentMode?: boolean }>()
const title = computed(() => props.departmentMode ? '设备台账[部门]' : '设备台账')
const route = useRoute(), router = useRouter(), dates = clientYearRange()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const appliedDateField = computed(() => text('dateField', text('from') || text('to') ? 'lastTestDate' : '') as EquipmentLedgerQuery['dateField'])
const query = computed<EquipmentLedgerQuery>(() => ({
  code: text('code'), name: text('name'), manufacturer: text('manufacturer'), serial: text('serial'), departmentId: text('departmentId'), status: text('status'),
  dateField: appliedDateField.value, from: appliedDateField.value ? text('from', dates.from) : undefined, to: appliedDateField.value ? text('to', dates.to) : undefined,
  ownDepartment: props.departmentMode || text('ownDepartment') === '1', unassociated: text('unassociated') === '1', sort: text('sort', 'code'), direction: text('direction') === 'desc' ? 'desc' : 'asc',
  page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10,
}))
const draft = reactive({ code: '', name: '', manufacturer: '', serial: '', departmentId: '', status: '', dateField: '', from: dates.from, to: dates.to, ownDepartment: false, unassociated: false })
watch(query, q => {
  for (const key of Object.keys(draft) as (keyof typeof draft)[]) Object.assign(draft, { [key]: q[key] })
  draft.from = q.from ?? dates.from; draft.to = q.to ?? dates.to
}, { immediate: true })
const more = ref(false), dateInput = ref<InstanceType<typeof TemplateDateRange>>()
const activeFilters = computed(() => [draft.serial, draft.departmentId, draft.status, draft.ownDepartment, draft.unassociated, draft.dateField].filter(Boolean).length)
const textFields = [{ key: 'code', label: '档案号' }, { key: 'name', label: '仪器设备名称' }, { key: 'manufacturer', label: '生产厂家' }] as const
const toolbarActions = computed(() => [
  { key: 'batch', label: '批量修改', icon: 'ti ti-edit', hint: selected.value.length ? undefined : '请至少选择一台设备', disabled: !canWrite.value || loading.value || !selected.value.length },
  { key: 'groups', label: '分组关联', icon: 'ti ti-link', hint: selected.value.length ? undefined : '请至少选择一台设备', disabled: !canWrite.value || loading.value || !selected.value.length },
  { key: 'template', label: '下载模板', icon: 'ti ti-download', disabled: exporting.value },
  { key: 'import', label: '导入', icon: 'ti ti-upload', disabled: !canWrite.value || loading.value },
].filter(action => !props.departmentMode || action.key === 'groups'))
const rows = ref<EquipmentLedgerPage>({ items: [], total: 0, page: 1, pageSize: 10, departments: [] })
const selected = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>(''), exportError = ref<ErrorValue>(''), exporting = ref(false)
const modal = ref<{ key: number; mode?: 'new' | 'edit' | 'view'; recordId?: string; initial?: EquipmentDraft }>(), modalKey = ref(0), message = ref(''), toast = ref<InstanceType<typeof TemplateToast>>()
const canWrite = computed(() => currentActor.value.roles.some(role => ['admin', 'quality'].includes(role)))
const deleting = ref<EquipmentLedgerRow>()
const batchRecords = ref<EquipmentLedgerRow[]>()
const groupIds = ref<string[]>()
const importing = ref(false)
function openBatch(index: number) {
  const action = toolbarActions.value[index]?.key
  if (action === 'template') { void exportRows(false, true); return }
  if (!canWrite.value || loading.value) return
  if (action === 'import') { importing.value = true; return }
  if (!selected.value.length) return
  if (action === 'batch') batchRecords.value = rows.value.items.filter(row => selected.value.includes(row.id)).map(row => ({ ...row }))
  else if (action === 'groups') groupIds.value = [...selected.value]
}
async function imported(count: number) {
  importing.value = false; message.value = `成功导入 ${count} 条设备记录。`; void load()
  await nextTick(); toast.value?.show()
}
async function groupsSaved() {
  groupIds.value = undefined; message.value = '分组关联已保存。'; void load()
  await nextTick(); toast.value?.show()
}
async function batchSaved(count: number) {
  batchRecords.value = undefined; message.value = `已修改 ${count} 台设备。`; void load()
  await nextTick(); toast.value?.show()
}
function refreshBatch() { batchRecords.value = undefined; void load() }
async function equipmentDeleted() {
  deleting.value = undefined; message.value = '设备已删除。'
  if (rows.value.items.length === 1 && rows.value.page > 1) await patch({ page: String(rows.value.page - 1) })
  else void load()
  await nextTick(); toast.value?.show()
}
async function equipmentSaved(record: EquipmentRecord, copy: boolean) {
  const oldModal = document.querySelector('.modal.show[aria-label="新增设备"]')
  const hidden = copy && oldModal ? new Promise<void>(resolve => oldModal.addEventListener('hidden.bs.modal', () => resolve(), { once: true })) : Promise.resolve()
  const key = modalKey.value
  modal.value = undefined; message.value = '设备已保存。'; void load()
  if (copy) {
    const initial = JSON.parse(JSON.stringify(record)) as EquipmentDraft
    initial.code = ''; initial.serial = ''
    const empty = emptyEquipment()
    initial.profile = { ...empty.profile, equipmentType: record.profile.equipmentType, tester: record.profile.tester, validity: record.profile.validity, projects: record.profile.projects.map(row => ({ ...row })) }
    initial.usageRecordCount = 0; initial.manualCount = 0; initial.certificateCount = 0; initial.acceptanceCount = 0
    await hidden
    if (key === modalKey.value && !modal.value) modal.value = { key: ++modalKey.value, initial }
  }
  await nextTick(); toast.value?.show()
}
const columnKeys = computed(() => parseTableColumns(equipmentLedgerColumns, route.query.columns))
const columns = computed(() => equipmentLedgerColumns.filter(c => columnKeys.value.includes(c.key)))
let epoch = 0, exportEpoch = 0, controller: AbortController | undefined
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
async function load() {
  controller?.abort(); const active = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const data = await registrationDemo.equipmentLedger(query.value, active.signal, props.departmentMode); if (token === epoch) rows.value = data }
  catch (issue) { if (token === epoch && !active.signal.aborted) { error.value = normalizeError(issue); rows.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() {
  if (loading.value) return
  if (!dateInput.value?.validate()) { more.value = true; return }
  const previous = route.fullPath
  await patch({ code: draft.code.trim() || undefined, name: draft.name.trim() || undefined, manufacturer: draft.manufacturer.trim() || undefined, serial: draft.serial.trim() || undefined,
    departmentId: draft.departmentId || undefined, status: draft.status || undefined, dateField: draft.dateField, from: draft.dateField ? draft.from : undefined, to: draft.dateField ? draft.to : undefined,
    ownDepartment: props.departmentMode || draft.ownDepartment ? '1' : undefined, unassociated: draft.unassociated ? '1' : undefined, page: '1' })
  if (previous === route.fullPath) void load()
}
function toggleColumn(key: string, checked: boolean) {
  const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key)
  void patch({ columns: [...keys].join(',') })
}
async function exportRows(onlySelected: boolean, template = false) {
  if (template && props.departmentMode || exporting.value || !template && (loading.value || error.value || onlySelected && !selected.value.length)) return
  const token = ++exportEpoch; exporting.value = true; exportError.value = ''
  try {
    const blob = template ? await registrationDemo.equipmentTemplate() : await registrationDemo.exportEquipmentLedger({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) }, props.departmentMode)
    if (token === exportEpoch) downloadBlob(blob, template ? '设备台账导入模板.csv' : `${title.value}.csv`)
  } catch (issue) { if (token === exportEpoch) exportError.value = normalizeError(issue) }
  finally { if (token === exportEpoch) exporting.value = false }
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id, () => route.path], (values, old) => {
  exportEpoch++; exporting.value = false; exportError.value = ''
  if (old && (values[1] !== old[1] || values[2] !== old[2])) { rows.value.items = []; rows.value.departments = []; more.value = false; modal.value = undefined; deleting.value = undefined; batchRecords.value = undefined; groupIds.value = undefined; importing.value = false }
  void load()
}, { immediate: true })
onBeforeUnmount(() => { epoch++; exportEpoch++; controller?.abort() })
</script>

<template>
  <PageHeading :title="title" />
  <section class="card" aria-label="设备台账列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex flex-wrap align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar label="设备台账" :adaptive-actions="toolbarActions" :columns="equipmentLedgerColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows" @action="openBatch">
        <button v-if="!departmentMode" type="button" class="btn btn-primary text-nowrap" :disabled="!canWrite || loading" @click="modal = { key: ++modalKey }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" aria-label="设备台账查询" @submit.prevent="search">
      <QueryFormLayout>
        <div class="row g-3 align-items-start"><div v-for="field in textFields" :key="field.key" class="col-12 col-sm-6 col-xl-4"><label class="form-label" :for="`ledger-${field.key}`">{{ field.label }}</label><input :id="`ledger-${field.key}`" v-model="draft[field.key]" class="form-control" maxlength="200" /></div></div>
        <div v-show="more" id="equipment-ledger-more-filters" class="row g-3 align-items-start mt-0">
          <div class="col-12 col-sm-6 col-xl-4"><label for="ledger-serial" class="form-label">仪器出厂号</label><input id="ledger-serial" v-model="draft.serial" class="form-control" maxlength="200" /></div>
          <div class="col-12 col-sm-6 col-xl-4"><label for="ledger-department" class="form-label">所属部门</label><select id="ledger-department" v-model="draft.departmentId" class="form-select"><option value="">全部</option><option v-for="department in rows.departments" :key="department.id" :value="department.id">{{ department.name }}</option></select></div>
          <div class="col-12 col-sm-6 col-xl-4"><label for="ledger-status" class="form-label">设备状态</label><select id="ledger-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in equipmentStates" :key="status" :value="status">{{ status }}</option></select></div>
          <div class="col-12 col-sm-6 col-xl-4"><label for="ledger-date-field" class="form-label">日期类型</label><select id="ledger-date-field" v-model="draft.dateField" class="form-select"><option value="">不限</option><option v-for="field in equipmentDateFields" :key="field.key" :value="field.key">{{ field.label }}</option></select></div>
          <div class="col-12 col-sm-6 col-xl-4"><label for="ledger-dates" class="form-label">日期范围</label><TemplateDateRange id="ledger-dates" ref="dateInput" :from="draft.from" :to="draft.to" :disabled="!draft.dateField" @change="Object.assign(draft, $event)" /></div>
          <div class="col-12 col-xl-4">
            <span class="form-label d-none d-xl-block invisible" aria-hidden="true">筛选范围</span>
            <div class="d-flex flex-wrap align-items-center gap-3 py-2"><label class="form-check mb-0 text-nowrap"><input v-model="draft.ownDepartment" type="checkbox" class="form-check-input" :disabled="departmentMode" /><span class="form-check-label">本部门设备</span></label><label class="form-check mb-0 text-nowrap"><input v-model="draft.unassociated" type="checkbox" class="form-check-input" /><span class="form-check-label">未关联部门设备</span></label></div>
          </div>
        </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button type="button" class="btn btn-link text-nowrap" :aria-expanded="more" aria-controls="equipment-ledger-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable label="设备台账" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })">
      <template #cell-status="{ row }"><span class="badge" :class="equipmentStatusClasses[row.status]">{{ row.status }}</span></template>
      <template v-for="key in ['usageRecordCount', 'manualCount', 'certificateCount', 'acceptanceCount'] as const" :key="key" #[`cell-${key}`]="{ row }">{{ row[key] || '—' }}</template>
      <template #actions="{ row }">
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { key: ++modalKey, mode: 'view', recordId: row.id }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button v-if="!departmentMode" type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { key: ++modalKey, mode: 'edit', recordId: row.id }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button v-if="!departmentMode" type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="deleting = row"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
      </template>
    </DataTable>
  </section>
  <EquipmentModal v-if="modal" :key="modal.key" :mode="modal.mode" :record-id="modal.recordId" :initial="modal.initial" @close="modal = undefined" @saved="equipmentSaved" />
  <EquipmentDeleteModal v-if="deleting" :key="deleting.id" :row="deleting" @close="deleting = undefined" @deleted="equipmentDeleted" />
  <EquipmentBatchModal v-if="batchRecords?.length" :records="batchRecords" @close="batchRecords = undefined" @saved="batchSaved" @refresh="refreshBatch" />
  <EquipmentGroupsModal v-if="groupIds?.length" :ids="groupIds" @close="groupIds = undefined" @saved="groupsSaved" />
  <EquipmentImportModal v-if="importing" @close="importing = false" @saved="imported" />
  <TemplateToast ref="toast" :message="message" />
</template>
