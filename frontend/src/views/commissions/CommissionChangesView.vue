<script setup lang="ts">
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import { completionFieldMessages } from '../../services/testing/completionFeedback'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import { emptyPlanSelection, type PlanSelectionState } from '../../types/samples/inbound'
import { canChangeData, type DataChangeQuery, type DataChangePage } from '../../types/testing/dataChanges'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import RegistrationActionModal from '../../components/commissions/RegistrationActionModal.vue'
import RegistrationAttachmentManager from '../../components/commissions/RegistrationAttachmentManager.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { changesRoot, workspaceCanEdit } from '../../services/commissions/registrationService'
import { parseTableColumns } from '../../services/common/table'
import { clientYearRange } from '../../services/common/date'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { sampleTypes, type RegistrationPage, type RegistrationSample } from '../../types/commissions/registration'
import { commissionChangeColumns, changeProblemSources, changeProcessingResults, type CommissionChangeColumnKey, type CommissionChangeQuery, type CommissionChangeRow } from '../../types/commissions/commissionChanges'

const props = defineProps<{ testingMode?: boolean }>()
const title = computed(() => props.testingMode ? '检测数据更改' : '委托更改')
const root = computed(() => props.testingMode ? '/testing/data-changes' : changesRoot)
const allowed = (row: CommissionChangeRow | RegistrationSample) => props.testingMode ? canChangeData(currentActor.value, row) : workspaceCanEdit(currentActor.value, 'samples', row, 'changes')
const route = useRoute(), router = useRouter(), dates = clientYearRange()
const drawer = ref(false), plans = ref(emptyPlanSelection()), planState = ref<PlanSelectionState>(), planBusy = ref(false), planError = ref<ErrorValue>('')
const planFilter = ref<InstanceType<typeof TestPlanFilterDrawer>>()
const dateInput = ref<InstanceType<typeof TemplateDateRange>>()
function applyPlans(value: PlanSelectionState) { plans.value = value.selection; planState.value = value }
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const query = computed<DataChangeQuery>(() => ({
  from: text('from', dates.from), to: text('to', dates.to), source: text('source'), result: text('result') === '问题已处理' ? '问题已处理' : '问题处理中', sampleType: text('sampleType'),
  sort: (['commissionCode', 'code', 'problemSubmittedAt'].includes(text('sort')) ? text('sort') : 'commissionCode') as CommissionChangeQuery['sort'],
  direction: text('direction') === 'desc' ? 'desc' : 'asc',
  page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10,
  ...(props.testingMode ? { plans: { groupIds: text('planGroups').split(',').filter(Boolean), planIds: text('planIds').split(',').filter(Boolean), excludedPlanIds: text('planExclude').split(',').filter(Boolean) } } : {}),
}))
const draft = reactive({ from: dates.from, to: dates.to, source: '', result: '问题处理中', sampleType: '' })
watch(query, value => Object.assign(draft, { from: value.from, to: value.to, source: value.source || '', result: value.result || '', sampleType: value.sampleType || '' }), { immediate: true })
const rows = ref<RegistrationPage<CommissionChangeRow>>({ items: [], total: 0, page: 1, pageSize: 10 })
const selected = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>('')
const attachmentId = ref<string>()
watch(() => [route.fullPath, currentActor.value], () => { attachmentId.value = undefined })
function syncAttachmentVersion(updated: Pick<RegistrationSample, 'id' | 'version'> & { attachmentCount: number }) {
  const row = rows.value.items.find(item => item.id === updated.id)
  if (row) { row.version = Math.max(row.version, updated.version); row.attachmentCount = updated.attachmentCount }
}
const columnKeys = computed(() => parseTableColumns(commissionChangeColumns, route.query.columns))
const columns = computed(() => commissionChangeColumns.filter(column => columnKeys.value.includes(column.key)))
const completing = ref<RegistrationSample>(), actionLoading = ref(false), actionError = ref<ErrorValue>('')
const exporting = ref(false), completingBusy = ref(false), completeError = ref<ErrorValue>('')
const missingOriginalWarning = ref(false)
const completeValidation = computed(() => completeError.value && ['VALIDATION', 'BUSINESS_RULE'].includes(completeError.value.code) ? completeError.value : undefined)
const completeFieldMessages = computed(() => completionFieldMessages(completeValidation.value?.fieldErrors))
async function submitCompletion() {
  if (!completing.value || completingBusy.value || !allowed(completing.value)) return
  const token = actionRequest
  completingBusy.value = true; completeError.value = ''
  try {
    await registrationDemo.completeDataChange(completing.value.id, completing.value.version, missingOriginalWarning.value)
    if (token === actionRequest) { completing.value = undefined; await load() }
  } catch (issue) { if (token === actionRequest) {
    const failure = normalizeError(issue)
    completeError.value = failure
    missingOriginalWarning.value = !!failure.fieldErrors?.originalRecords
  } }
  finally { if (token === actionRequest) completingBusy.value = false }
}
let request = 0, actionRequest = 0, exportRequest = 0, controller: AbortController | undefined
async function load() {
  const token = ++request, appliedPlans = JSON.stringify(query.value.plans)
  controller?.abort(); controller = new AbortController()
  loading.value = true; error.value = ''; selected.value = []
  try {
    const result = props.testingMode ? await registrationDemo.dataChanges(query.value, controller.signal) : await registrationDemo.sampleChanges(query.value, controller.signal)
    if (token === request) {
      rows.value = result
      if (props.testingMode && JSON.stringify(plans.value) === appliedPlans) { const selection = (result as DataChangePage).planSelection; planState.value = selection; plans.value = selection.selection }
    }
  } catch (issue) {
    if (token === request && !controller.signal.aborted) { error.value = normalizeError(issue); rows.value.items = [] }
  } finally { if (token === request) loading.value = false }
}
function patch(values: Record<string, string | undefined>) { return router.push({ path: root.value, query: { ...route.query, ...values } }) }
async function search() {
  if (loading.value || planBusy.value || !dateInput.value?.validate()) return
  const previous = route.fullPath
  await patch({ from: draft.from, to: draft.to, source: draft.source || undefined, result: draft.result, sampleType: draft.sampleType || undefined, page: '1', ...(props.testingMode ? { planGroups: plans.value.groupIds.join(',') || undefined, planIds: plans.value.planIds.join(',') || undefined, planExclude: plans.value.excludedPlanIds.join(',') || undefined } : {}) })
  if (previous === route.fullPath) void load()
}
function sort(key: string) { void patch({ sort: key, direction: query.value.sort === key && query.value.direction === 'asc' ? 'desc' : 'asc', page: '1' }) }
function toggleColumn(key: string, checked: boolean) {
  const next = new Set(columnKeys.value)
  if (checked) next.add(key as CommissionChangeColumnKey); else next.delete(key as CommissionChangeColumnKey)
  void patch({ columns: [...next].join(',') })
}
function edit(row: CommissionChangeRow | RegistrationSample) {
  if (!loading.value && allowed(row)) void router.push({ path: props.testingMode ? `${root.value}/${encodeURIComponent(row.id)}` : `${changesRoot}/samples/${row.id}/edit`, query: { returnTo: route.fullPath } })
}
async function complete(row: CommissionChangeRow) {
  if (loading.value || actionLoading.value || !allowed(row)) return
  const token = ++actionRequest
  actionLoading.value = true; actionError.value = ''; completeError.value = ''; missingOriginalWarning.value = false
  try { const record = await registrationDemo.sample(row.id); if (token === actionRequest) completing.value = record }
  catch (issue) { if (token === actionRequest) actionError.value = normalizeError(issue) }
  finally { if (token === actionRequest) actionLoading.value = false }
}
async function exportRows(onlySelected: boolean) {
  if (exporting.value || loading.value || error.value || onlySelected && !selected.value.length) return
  const token = ++exportRequest
  exporting.value = true; actionError.value = ''
  try {
    const input = { ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) }
    const csv = props.testingMode ? await registrationDemo.exportDataChanges(input) : await registrationDemo.exportSampleChanges(input)
    if (token === exportRequest) downloadBlob(csv, `${title.value}.csv`)
  } catch (issue) { if (token === exportRequest) actionError.value = normalizeError(issue) }
  finally { if (token === exportRequest) exporting.value = false }
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id], (value, old) => {
  actionRequest++; actionLoading.value = false; completing.value = undefined; actionError.value = ''
  completingBusy.value = false; completeError.value = ''
  plans.value = query.value.plans || emptyPlanSelection(); planState.value = undefined
  if (old && value[1] !== old[1]) { drawer.value = false; planBusy.value = false; planError.value = '' }
  exportRequest++; exporting.value = false
  if (old && value[1] !== old[1]) rows.value.items = []
  void load()
}, { immediate: true })
onBeforeUnmount(() => { request++; actionRequest++; exportRequest++; controller?.abort() })
</script>

<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :columns="commissionChangeColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows">
        <button v-if="testingMode" class="btn btn-light text-body text-nowrap" type="button" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}</button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}查询`" @submit.prevent="search">
      <QueryFormLayout>
      <div class="row g-3 align-items-start">
        <div class="col-12 col-md-6 col-xl-4"><label class="form-label" for="change-dates">问题提交日期</label><TemplateDateRange ref="dateInput" id="change-dates" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div>
        <div class="col-12 col-md-6 col-xl"><label class="form-label" for="change-source">问题来源</label><select id="change-source" v-model="draft.source" class="form-select"><option value="">全部</option><option v-for="source in changeProblemSources" :key="source">{{ source }}</option></select></div>
        <div class="col-12 col-md-6 col-xl"><label class="form-label" for="change-result">处理结果</label><select id="change-result" v-model="draft.result" class="form-select"><option v-for="result in changeProcessingResults" :key="result">{{ result }}</option></select></div>
        <div class="col-12 col-md-6 col-xl"><label class="form-label" for="change-type">样品类型</label><select id="change-type" v-model="draft.sampleType" class="form-select"><option value="">全部</option><option v-for="type in sampleTypes" :key="type">{{ type }}</option></select></div>
      </div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
      </QueryFormLayout>
      <div v-if="testingMode && planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" class="btn btn-link btn-sm" type="button" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="actionError" class="px-3 pt-3"><ErrorNotice :error="actionError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected"
      :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading :actions-disabled="actionLoading"
      @sort="sort" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load">
      <template #cell-dataStatus="{ row }"><span class="badge bg-info-subtle text-info">{{ row.dataStatus }}</span></template>
      <template #cell-processingResult="{ row }"><span class="badge bg-warning-subtle text-warning">{{ row.processingResult || '—' }}</span></template>
      <template #cell-attachmentCount="{ row }">{{ row.attachmentCount > 0 ? '有' : '' }}</template>
      <template #actions="{ row }">
        <button class="dropdown-item" type="button" role="menuitem" :disabled="!allowed(row)" @click="edit(row)"><i class="ti ti-edit align-bottom me-2 text-muted" aria-hidden="true"></i>更改</button>
        <button class="dropdown-item" type="button" role="menuitem" :disabled="!allowed(row)" @click="complete(row)"><i class="ti ti-circle-check align-bottom me-2 text-muted" aria-hidden="true"></i>完成</button>
        <button class="dropdown-item" type="button" role="menuitem" @click="attachmentId = row.id"><i class="ti ti-paperclip align-bottom me-2 text-muted" aria-hidden="true"></i>附件管理</button>
      </template>
    </DataTable>
  </section>
  <RegistrationActionModal v-if="!testingMode" kind="samples" workspace="changes" :record="completing" initial-action="complete-change" @close="completing = undefined" @saved="load" />
  <RegistrationAttachmentManager :id="attachmentId" kind="samples" @close="attachmentId = undefined" @changed="syncAttachmentVersion" />
  <BootstrapModal v-if="testingMode && completing" open title="完成" :busy="completingBusy" @close="!completingBusy && (completing = undefined)">
    <p class="text-break"><strong>{{ completing.code }}</strong> · {{ completing.name }}</p>
    <p>确认对这条样品执行“完成更改”？</p>
    <FeedbackNotice v-if="completeValidation" :message="completeValidation.message" :trigger="completeValidation">
      <div class="text-break">{{ completeValidation.message }}</div>
      <ul v-if="completeFieldMessages.length" class="mt-2 mb-0 ps-3"><li v-for="message in completeFieldMessages" :key="message" class="text-break">{{ message }}</li></ul>
    </FeedbackNotice>
    <ErrorNotice v-else :error="completeError" @reload="completing = undefined; load()" />
    <button v-if="completeValidation" type="button" class="btn btn-link p-0" :disabled="completingBusy" @click="edit(completing)">打开检测数据更改，检查并补充资料</button>
    <template #footer><button type="button" class="btn btn-light" :disabled="completingBusy" @click="completing = undefined">取消</button><button type="button" class="btn btn-primary" :disabled="completingBusy || !allowed(completing)" @click="submitCompletion">{{ completingBusy ? '正在保存…' : missingOriginalWarning ? '继续完成' : '确认' }}</button></template>
  </BootstrapModal>
  <TestPlanFilterDrawer v-if="testingMode" ref="planFilter" sample-scope="data-changes" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
</template>
