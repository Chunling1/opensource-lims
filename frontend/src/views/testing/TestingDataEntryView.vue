<script lang="ts">
const entryListSelections = new Map<string, string[]>()
</script>
<script setup lang="ts">
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import { completionFieldMessages } from '../../services/testing/completionFeedback'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TaskReturnModal from '../../components/testing/TaskReturnModal.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import { emptyPlanSelection, type PlanSelectionState } from '../../types/samples/inbound'
import { normalizeConclusion } from '../../types/testing/dataEntryDetail'
import { assignmentConclusions } from '../../types/testing/assignment'
import { dataEntryColumns, dataEntryStates, dataEntrySearchFields, dataEntryDateFields, dataEntryActions, type DataEntryQuery, type DataEntryPage, type DataEntryRow } from '../../types/testing/dataEntry'
import RegistrationAttachmentManager from '../../components/commissions/RegistrationAttachmentManager.vue'
import RegistrationActionModal from '../../components/commissions/RegistrationActionModal.vue'
import type { OutboundReturn } from '../../types/samples/outbound'
import { sampleTypes, type RegistrationSample } from '../../types/commissions/registration'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { clientYearRange } from '../../services/common/date'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { parseTableColumns } from '../../services/common/table'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'

const title = '检测数据录入', root = '/testing/data-entry', route = useRoute(), router = useRouter(), dates = clientYearRange()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const ids = (key: string) => text(key).split(',').filter(Boolean)
const plans = ref(emptyPlanSelection()), planState = ref<PlanSelectionState>()
const drawer = ref(false), planFilter = ref<InstanceType<typeof TestPlanFilterDrawer>>(), planBusy = ref(false), planError = ref<ErrorValue>('')
function applyPlans(value: PlanSelectionState) { plans.value = value.selection; planState.value = value }
const query = computed<DataEntryQuery>(() => ({
  searchField: text('searchField', 'code') as DataEntryQuery['searchField'], contains: text('contains'),
  status: text('status', '检测数据录入中'), sampleType: text('sampleType'), conclusion: normalizeConclusion(text('conclusion')),
  dateField: text('dateField', 'commissionDate') as DataEntryQuery['dateField'], from: text('from', dates.from), to: text('to', dates.to),
  plans: { groupIds: ids('planGroups'), planIds: ids('planIds'), excludedPlanIds: ids('planExclude') },
  sort: text('sort', 'code') as DataEntryQuery['sort'], direction: text('direction') === 'desc' ? 'desc' : 'asc',
  page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10,
}))
const draft = ref({ searchField: 'code', contains: '', status: '检测数据录入中', sampleType: '', conclusion: '', dateField: 'commissionDate', ...dates })
const more = ref(false)
const activeFilters = computed(() => Number(!!draft.value.conclusion) + Number(!!(draft.value.from || draft.value.to)))
const dateInput = ref<InstanceType<typeof TemplateDateRange>>()
const emptyPage = (): DataEntryPage => ({ items: [], total: 0, page: 1, pageSize: 10, planSelection: { selection: emptyPlanSelection(), count: 0, total: 0, previews: [], groups: {} } })
const rows = ref<DataEntryPage>(emptyPage()), selected = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>('')
const exporting = ref(false), exportError = ref<ErrorValue>('')
const returnTarget = ref<DataEntryRow>(), returnBusy = ref(false), returnError = ref<ErrorValue>('')
const attachmentId = ref<string>()
const voidRecord = ref<RegistrationSample>(), voidLoading = ref(false), voidError = ref<ErrorValue>('')
let voidSequence = 0
function resetVoid() { voidSequence++; voidRecord.value = undefined; voidLoading.value = false; voidError.value = '' }
async function openVoid(row: DataEntryRow) {
  if (!row.canVoid || voidLoading.value) return
  const token = ++voidSequence
  voidLoading.value = true; voidError.value = ''
  try {
    const sample = await registrationDemo.sample(row.id)
    if (token === voidSequence) voidRecord.value = sample
  } catch (issue) { if (token === voidSequence) voidError.value = normalizeError(issue) }
  finally { if (token === voidSequence) voidLoading.value = false }
}
function syncAttachment(updated: { id: string; version: number; attachmentCount: number }) {
  const row = rows.value.items.find(item => item.id === updated.id)
  if (row) { row.version = Math.max(row.version, updated.version); row.attachmentCount = updated.attachmentCount }
}
watch(() => [route.fullPath, currentActor.value.id], () => { attachmentId.value = undefined; resetVoid() })
const statusAction = ref<{ row: DataEntryRow; action: 'complete' | 'undo' }>()
const actionBusy = ref(false), statusError = ref<ErrorValue>('')
const statusValidation = computed(() => statusError.value && ['VALIDATION', 'BUSINESS_RULE'].includes(statusError.value.code) ? statusError.value : undefined)
const missingOriginalWarning = computed(() => statusAction.value?.action === 'complete' && statusValidation.value?.code === 'BUSINESS_RULE' && !!statusValidation.value.fieldErrors?.originalRecords)
const repairTarget = computed(() => statusValidation.value?.fieldErrors?.originalRecords ? { action: '上传原始记录', label: '打开原始记录，上传文件' } : statusValidation.value?.fieldErrors?.finalReport ? { action: '报告填写', label: '打开报告填写，生成最终报告' } : { action: '数据录入', label: '打开数据录入，检查并补充资料' })
const statusFieldMessages = computed(() => completionFieldMessages(statusValidation.value?.fieldErrors))
function actionAllowed(row: DataEntryRow, label: string) {
  if (label === '数据录入') return row.canEdit || row.canManageOriginals
  if (label === '报告填写') return row.canView
  if (label === '录入完成') return row.canComplete
  if (label === '撤销完成') return row.canUndo
  if (label === '退回') return row.canReturn
  if (label === '作废') return row.canVoid
  return true
}
function openEntry(row: DataEntryRow, label: string) {
  entryListSelections.set(currentActor.value.id + route.fullPath, [...selected.value])
  void router.push({ path: `${root}/${encodeURIComponent(row.id)}${label === '报告填写' ? '/report' : ''}`, query: { returnTo: route.fullPath, ...(label === '查看数据' || label === '报告填写' && !row.canEdit ? { mode: 'view' } : {}), ...(label === '上传原始记录' ? { tab: 'original' } : {}) } })
}
async function runStatusAction() {
  const target = statusAction.value
  if (!target || actionBusy.value) return
  const actor = currentActor.value.id
  const acknowledgeMissingOriginals = missingOriginalWarning.value
  actionBusy.value = true; statusError.value = ''
  try {
    const detail = await registrationDemo.entryDetail(target.row.id)
    if (actor !== currentActor.value.id) return
    await registrationDemo.entryAction(target.row.id, target.action, { version: detail.version, sampleVersion: target.row.version, requestId: crypto.randomUUID(), ...(acknowledgeMissingOriginals ? { acknowledgeMissingOriginals: true } : {}) })
    if (actor !== currentActor.value.id) return
    statusAction.value = undefined; await load()
  } catch (issue) {
    if (actor === currentActor.value.id) {
      const failure = normalizeError(issue)
      if (['NETWORK', 'UNAVAILABLE', 'FORBIDDEN'].includes(failure.code)) { statusAction.value = undefined; await load(); error.value = failure }
      else statusError.value = failure
    }
  }
  finally { actionBusy.value = false }
}
function rowAction(row: DataEntryRow, label: string) {
  if (loading.value || returnBusy.value || actionBusy.value || voidLoading.value || !actionAllowed(row, label)) return
  if (label === '退回') openReturn(row)
  else if (label === '作废') void openVoid(row)
  else if (label === '附件管理') attachmentId.value = row.id
  else if (label === '录入完成' || label === '撤销完成') { statusError.value = ''; statusAction.value = { row, action: label === '录入完成' ? 'complete' : 'undo' } }
  else if (['数据录入', '报告填写', '查看数据'].includes(label)) openEntry(row, label)
}
let actionSequence = 0
function resetReturn() { actionSequence++; returnTarget.value = undefined; returnBusy.value = false; returnError.value = '' }
function openReturn(row: DataEntryRow) {
  if (loading.value || returnBusy.value || !row.canReturn) return
  returnError.value = ''; returnTarget.value = row
}
async function submitReturn(receipt: OutboundReturn) {
  const row = returnTarget.value
  if (!row?.canReturn || returnBusy.value || loading.value) return
  const token = ++actionSequence
  returnBusy.value = true; returnError.value = ''
  try {
    await registrationDemo.taskQueryReturn(row.id, row.version, receipt)
    if (token !== actionSequence) return
    await load()
  } catch (issue) { if (token === actionSequence) returnError.value = normalizeError(issue) }
  finally { if (token === actionSequence) returnBusy.value = false }
}
const columnKeys = computed(() => parseTableColumns(dataEntryColumns, route.query.columns))
const columns = computed(() => dataEntryColumns.filter(column => columnKeys.value.includes(column.key)))
let sequence = 0, exportSequence = 0, controller: AbortController | undefined
async function load() {
  resetReturn()
  const token = ++sequence, appliedPlans = JSON.stringify(query.value.plans)
  controller?.abort(); const active = controller = new AbortController()
  loading.value = true; error.value = ''; selected.value = []
  try {
    const result = await registrationDemo.dataEntrySamples(query.value, active.signal)
    if (token !== sequence) return
    rows.value = result
    const remembered = entryListSelections.get(currentActor.value.id + route.fullPath)
    if (remembered) { selected.value = remembered.filter(id => result.items.some(row => row.id === id)); entryListSelections.delete(currentActor.value.id + route.fullPath) }
    if (JSON.stringify(plans.value) === appliedPlans) { planState.value = result.planSelection; plans.value = result.planSelection.selection }
  } catch (issue) { if (token === sequence && !active.signal.aborted) { error.value = normalizeError(issue); rows.value.items = [] } }
  finally { if (token === sequence) loading.value = false }
}
const patch = (values: Record<string, string | undefined>) => router.push({ path: root, query: { ...route.query, ...values } })
async function search() {
  if (loading.value || planBusy.value) return
  if (!dateInput.value?.validate()) { more.value = true; return }
  const previous = JSON.stringify(query.value)
  await patch({ ...draft.value, contains: draft.value.contains.trim(), page: '1',
    planGroups: plans.value.groupIds.join(',') || undefined, planIds: plans.value.planIds.join(',') || undefined, planExclude: plans.value.excludedPlanIds.join(',') || undefined })
  if (previous === JSON.stringify(query.value)) void load()
}
function toggleColumn(key: string, checked: boolean) {
  const next = new Set<keyof DataEntryRow>(columnKeys.value)
  if (checked) next.add(key as keyof DataEntryRow); else next.delete(key as keyof DataEntryRow)
  void patch({ columns: [...next].join(',') })
}
async function exportRows(onlySelected: boolean) {
  if (loading.value || error.value || exporting.value || onlySelected && !selected.value.length) return
  const token = ++exportSequence
  exporting.value = true; exportError.value = ''
  try {
    const blob = await registrationDemo.exportDataEntrySamples({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) })
    if (token === exportSequence) downloadBlob(blob, `${title}.csv`)
  } catch (issue) { if (token === exportSequence) exportError.value = normalizeError(issue) }
  finally { if (token === exportSequence) exporting.value = false }
}
watch(() => JSON.stringify(query.value), () => {
  draft.value = { searchField: query.value.searchField || 'code', contains: query.value.contains || '', status: query.value.status || '', sampleType: query.value.sampleType || '', conclusion: query.value.conclusion || '', dateField: query.value.dateField || 'commissionDate', from: query.value.from || '', to: query.value.to || '' }
  plans.value = query.value.plans!; planState.value = undefined
  exportSequence++; exporting.value = false; exportError.value = ''
  void load()
}, { immediate: true })
watch(() => currentActor.value.id, async () => {
  statusAction.value = undefined
  resetReturn()
  sequence++; controller?.abort(); exportSequence++; exporting.value = false; selected.value = []; rows.value = emptyPage()
  drawer.value = false; planBusy.value = false; planError.value = ''; planState.value = undefined; plans.value = emptyPlanSelection()
  error.value = ''; exportError.value = ''; more.value = false
  const previous = route.fullPath
  await router.replace({ path: root })
  if (previous === route.fullPath) void load()
})
onBeforeUnmount(() => { sequence++; exportSequence++; controller?.abort(); resetReturn(); resetVoid() })
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :columns="dataEntryColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows">
        <button type="button" class="btn btn-light text-body text-nowrap" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-haspopup="dialog" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}<span v-if="planBusy" class="spinner-border spinner-border-sm ms-1" aria-label="正在更新方案选择"></span></button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}条件`" @submit.prevent="search">
      <QueryFormLayout>
        <div class="row g-3 align-items-end">
          <div class="col-12 col-xl-6">
            <div class="row g-2">
              <div class="col-12 col-sm-5"><label for="data-entry-field" class="form-label">查询内容</label><select id="data-entry-field" v-model="draft.searchField" class="form-select"><option v-for="field in dataEntrySearchFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div>
              <div class="col-12 col-sm-7"><label for="data-entry-contains" class="form-label">包含</label><input id="data-entry-contains" v-model="draft.contains" class="form-control" maxlength="200" /></div>
            </div>
          </div>
          <div class="col-6 col-xl-3"><label for="data-entry-status" class="form-label">数据状态</label><select id="data-entry-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in dataEntryStates" :key="status">{{ status }}</option></select></div>
          <div class="col-6 col-xl-3"><label for="data-entry-type" class="form-label">样品类型</label><select id="data-entry-type" v-model="draft.sampleType" class="form-select"><option value="">全部</option><option v-for="type in sampleTypes" :key="type">{{ type }}</option></select></div>
        </div>
      <div v-show="more" id="data-entry-more-filters" class="row g-3 align-items-start mt-0">
          <div class="col-12 col-md-4 col-xl-3"><label for="data-entry-conclusion" class="form-label">结论状态</label><select id="data-entry-conclusion" v-model="draft.conclusion" class="form-select"><option value="">全部</option><option v-for="conclusion in assignmentConclusions" :key="conclusion">{{ conclusion }}</option></select></div>
          <div class="col-12 col-md-8 col-xl-9">
            <label for="data-entry-dates" class="form-label">日期</label>
            <div class="row g-2"><div class="col-12 col-sm-4"><select v-model="draft.dateField" class="form-select" aria-label="日期字段"><option v-for="field in dataEntryDateFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div><div class="col-12 col-sm-8"><TemplateDateRange id="data-entry-dates" ref="dateInput" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div></div>
          </div>
      </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="data-entry-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
      <div v-if="planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" type="button" class="btn btn-link btn-sm p-0" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <div v-if="voidError" class="px-3 pt-3"><ErrorNotice :error="voidError" /></div>
    <div v-if="voidLoading" class="px-3 py-2 text-muted" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在加载样品…</div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load()">
      <template #cell-attachmentCount="{ row }">{{ row.attachmentCount > 0 ? '有' : '' }}</template>
      <template #actions="{ row }">
        <button v-for="action in dataEntryActions" :key="action.label" type="button" role="menuitem" class="dropdown-item" :disabled="loading || returnBusy || actionBusy || voidLoading || !actionAllowed(row, action.label)" @click="rowAction(row, action.label)">
          <i :class="action.icon" class="me-2 text-muted" aria-hidden="true"></i>{{ action.label }}
        </button>
      </template>
    </DataTable>
  </section>
  <BootstrapModal v-if="statusAction" open :title="statusAction.action === 'complete' ? '录入完成' : '撤销完成'" :busy="actionBusy" scrollable @close="!actionBusy && (statusAction = undefined)">
    <p class="text-break"><strong>{{ statusAction.row.code }}</strong> · {{ statusAction.row.name }}</p>
    <FeedbackNotice v-if="statusValidation" :message="statusValidation.message" :trigger="statusValidation">
      <div class="text-break">{{ statusValidation.message }}</div>
      <ul v-if="statusFieldMessages.length" class="mt-2 mb-0 ps-3"><li v-for="message in statusFieldMessages" :key="message" class="text-break">{{ message }}</li></ul>
    </FeedbackNotice>
    <ErrorNotice v-else :error="statusError" />
    <p v-if="!statusValidation">{{ statusAction.action === 'complete' ? '请确认试验信息及最终报告内容无误。完成录入后将进入后续流程，是否继续？' : '确认对这条样品执行“撤销完成”？' }}</p>
    <button v-if="statusValidation && statusAction.action === 'complete'" type="button" class="btn btn-link p-0" :disabled="actionBusy" @click="openEntry(statusAction.row, repairTarget.action)">{{ repairTarget.label }}</button>
    <template #footer><button type="button" class="btn btn-light" :disabled="actionBusy" @click="statusAction = undefined">取消</button><button type="button" class="btn btn-primary" :disabled="actionBusy" @click="runStatusAction">{{ actionBusy ? '正在保存…' : missingOriginalWarning ? '继续完成' : '确认' }}</button></template>
  </BootstrapModal>
  <TestPlanFilterDrawer ref="planFilter" sample-scope="data-entry" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
  <RegistrationAttachmentManager v-if="attachmentId" :id="attachmentId" kind="samples" @close="attachmentId = undefined" @changed="syncAttachment" />
  <RegistrationActionModal kind="samples" :record="voidRecord" initial-action="void" @close="resetVoid()" @saved="load()" />
  <TaskReturnModal :row="returnTarget" :busy="returnBusy" :error="returnError" @close="!returnBusy && resetReturn()" @submit="submitReturn" @refresh="load()" />
</template>
