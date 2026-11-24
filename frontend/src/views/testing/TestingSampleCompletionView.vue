<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import SampleCompletionActionModal from '../../components/testing/SampleCompletionActionModal.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { clientYearRange } from '../../services/common/date'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { parseTableColumns } from '../../services/common/table'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { emptyPlanSelection, type PlanSelectionState } from '../../types/samples/inbound'
import { disposalStates } from '../../types/samples/disposal'
import { sampleCompletionColumns, completionStates, completionDisposalEnabled, completionDateEnabled, type SampleCompletionAction, type SampleCompletionSubmission, type SampleCompletionQuery, type SampleCompletionPage, type SampleCompletionRow } from '../../types/testing/sampleCompletion'

const title = '检毕样品处理', root = '/testing/sample-completion', route = useRoute(), router = useRouter(), dates = clientYearRange()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const ids = (key: string) => text(key).split(',').filter(Boolean)
const query = computed<SampleCompletionQuery>(() => ({
  code: text('code'), processingStatus: text('processingStatus', '样品待处理'), disposalStatus: text('disposalStatus', '样品待处置'),
  from: text('from', dates.from), to: text('to', dates.to),
  plans: { groupIds: ids('planGroups'), planIds: ids('planIds'), excludedPlanIds: ids('planExclude') },
  sort: 'code', direction: text('direction') === 'desc' ? 'desc' : 'asc',
  page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10,
}))
const draft = ref({ code: '', processingStatus: '样品待处理', disposalStatus: '样品待处置', ...dates })
const dateInput = ref<InstanceType<typeof TemplateDateRange>>()
const disposalEnabled = computed(() => completionDisposalEnabled(draft.value.processingStatus))
const datesEnabled = computed(() => completionDateEnabled(draft.value.processingStatus))
const plans = ref(emptyPlanSelection()), planState = ref<PlanSelectionState>(), drawer = ref(false)
const planFilter = ref<InstanceType<typeof TestPlanFilterDrawer>>(), planBusy = ref(false), planError = ref<ErrorValue>('')
function applyPlans(value: PlanSelectionState) { plans.value = value.selection; planState.value = value }
const emptyPage = (): SampleCompletionPage => ({ items: [], total: 0, page: 1, pageSize: 10, planSelection: { selection: emptyPlanSelection(), count: 0, total: 0, previews: [], groups: {} } })
const rows = ref(emptyPage()), selected = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>('')
const exporting = ref(false), exportError = ref<ErrorValue>('')
const operation = ref<{ row: SampleCompletionRow; action: SampleCompletionAction }>()
const operationBusy = ref(false), operationError = ref<ErrorValue>(''), success = ref('')
let operationSequence = 0
const columnKeys = computed(() => parseTableColumns(sampleCompletionColumns, route.query.columns))
const columns = computed(() => sampleCompletionColumns.filter(column => columnKeys.value.includes(column.key)))
let sequence = 0, exportSequence = 0, controller: AbortController | undefined
async function load() {
  const token = ++sequence, appliedPlans = JSON.stringify(query.value.plans)
  controller?.abort(); const active = controller = new AbortController()
  loading.value = true; error.value = ''; selected.value = []; operation.value = undefined
  operationSequence++; operationBusy.value = false; operationError.value = ''
  try {
    const result = await registrationDemo.sampleCompletionSamples(query.value, active.signal)
    if (token !== sequence) return
    rows.value = result
    if (JSON.stringify(plans.value) === appliedPlans) { planState.value = result.planSelection; plans.value = result.planSelection.selection }
  } catch (issue) { if (token === sequence && !active.signal.aborted) { error.value = normalizeError(issue); rows.value = emptyPage() } }
  finally { if (token === sequence) loading.value = false }
}
const patch = (values: Record<string, string | undefined>) => router.push({ path: root, query: { ...route.query, ...values } })
async function search() {
  if (loading.value || planBusy.value || datesEnabled.value && !dateInput.value?.validate()) return
  const previous = route.fullPath
  await patch({ ...draft.value, code: draft.value.code.trim(), page: '1', planGroups: plans.value.groupIds.join(',') || undefined, planIds: plans.value.planIds.join(',') || undefined, planExclude: plans.value.excludedPlanIds.join(',') || undefined })
  if (previous === route.fullPath) void load()
}
function toggleColumn(key: string, checked: boolean) {
  const next = new Set<keyof SampleCompletionRow>(columnKeys.value)
  if (checked) next.add(key as keyof SampleCompletionRow); else next.delete(key as keyof SampleCompletionRow)
  void patch({ columns: [...next].join(',') })
}
async function exportRows(onlySelected: boolean) {
  if (loading.value || error.value || exporting.value || onlySelected && !selected.value.length) return
  const token = ++exportSequence
  exporting.value = true; exportError.value = ''
  try {
    const blob = await registrationDemo.exportSampleCompletionSamples({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) })
    if (token === exportSequence) downloadBlob(blob, `${title}.csv`)
  } catch (issue) { if (token === exportSequence) exportError.value = normalizeError(issue) }
  finally { if (token === exportSequence) exporting.value = false }
}
function openOperation(row: SampleCompletionRow, undo = false) {
  if (loading.value || operationBusy.value || !(undo ? row.canUndoProcess : row.canProcess)) return
  operationError.value = ''; success.value = ''
  operation.value = { row, action: undo ? 'undo' : 'process' }
}
async function submitOperation(submission: SampleCompletionSubmission) {
  if (!operation.value || operationBusy.value || operation.value.action !== submission.action) return
  const token = ++operationSequence, { row } = operation.value
  operationBusy.value = true; operationError.value = ''
  try {
    await registrationDemo.sampleCompletionAction(row.id, row.version, submission)
    if (token !== operationSequence) return
    success.value = submission.action === 'process' ? '样品处理成功。' : '已撤销样品处理。'
    operation.value = undefined
    await load()
  } catch (issue) { if (token === operationSequence) operationError.value = normalizeError(issue) }
  finally { if (token === operationSequence) operationBusy.value = false }
}
watch(() => JSON.stringify(query.value), () => {
  draft.value = { code: query.value.code || '', processingStatus: query.value.processingStatus || '', disposalStatus: query.value.disposalStatus || '', from: query.value.from || '', to: query.value.to || '' }
  plans.value = query.value.plans!; planState.value = undefined
  exportSequence++; exporting.value = false; exportError.value = ''
  void load()
}, { immediate: true })
watch(() => currentActor.value.id, async () => {
  sequence++; controller?.abort(); exportSequence++; exporting.value = false; selected.value = []; rows.value = emptyPage(); operation.value = undefined
  operationSequence++; operationBusy.value = false; operationError.value = ''; success.value = ''
  drawer.value = false; planBusy.value = false; planError.value = ''; planState.value = undefined; plans.value = emptyPlanSelection(); error.value = ''; exportError.value = ''
  const previous = route.fullPath
  await router.replace({ path: root })
  if (previous === route.fullPath) void load()
})
onBeforeUnmount(() => { sequence++; exportSequence++; operationSequence++; controller?.abort() })
</script>

<template>
  <PageHeading :title="title" />
  <TemplateToast :message="success" tone="success" auto-show />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :columns="sampleCompletionColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows">
        <button type="button" class="btn btn-light text-body text-nowrap" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-haspopup="dialog" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}</button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}条件`" @submit.prevent="search">
      <QueryFormLayout>
        <div class="row g-3 align-items-start">
          <div class="col-12 col-md-6 col-xl"><label for="completion-code" class="form-label">样品编号</label><input id="completion-code" v-model="draft.code" class="form-control" maxlength="200" /></div>
          <div class="col-12 col-md-6 col-xl"><label for="completion-processing" class="form-label">处理状态</label><select id="completion-processing" v-model="draft.processingStatus" class="form-select"><option value="">全部</option><option v-for="status in completionStates" :key="status">{{ status }}</option></select></div>
          <div class="col-12 col-md-6 col-xl-4"><label for="completion-dates" class="form-label">处理时间</label><TemplateDateRange id="completion-dates" ref="dateInput" :from="draft.from" :to="draft.to" :disabled="!datesEnabled" @change="Object.assign(draft, $event)" /></div>
          <div class="col-12 col-md-6 col-xl"><label for="completion-disposal" class="form-label">处置状态</label><select id="completion-disposal" v-model="draft.disposalStatus" class="form-select" :disabled="!disposalEnabled"><option value="">全部</option><option v-for="status in disposalStates" :key="status">{{ status }}</option></select></div>
        </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
      </QueryFormLayout>
      <div v-if="planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" class="btn btn-link btn-sm p-0" type="button" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" sort-key="code" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @sort="patch({ direction: query.direction === 'asc' ? 'desc' : 'asc', page: '1' })" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load()">
      <template #cell-processingStatus="{ row }"><span class="badge" :class="row.processingStatus === '样品已处理' ? 'bg-success-subtle text-success' : 'bg-warning-subtle text-warning'">{{ row.processingStatus }}</span></template>
      <template #cell-disposalStatus="{ row }"><span class="badge bg-info-subtle text-info">{{ row.disposalStatus }}</span></template>
      <template #cell-retentionTime="{ row }">{{ row.retentionTime ? new Date(row.retentionTime).toLocaleString('zh-CN', { hour12: false }) : '—' }}</template>
      <template #actions="{ row }">
        <button type="button" role="menuitem" class="dropdown-item" :disabled="loading || !row.canProcess" @click="openOperation(row)"><i class="ti ti-circle-check me-2 text-muted" aria-hidden="true"></i>样品处理</button>
        <button type="button" role="menuitem" class="dropdown-item" :disabled="loading || !row.canUndoProcess" @click="openOperation(row, true)"><i class="ti ti-arrow-back-up me-2 text-muted" aria-hidden="true"></i>撤销样品处理</button>
      </template>
    </DataTable>
  </section>
  <TestPlanFilterDrawer ref="planFilter" sample-scope="disposal" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
  <SampleCompletionActionModal :operation="operation" :busy="operationBusy" :error="operationError" @submit="submitOperation" @refresh="load" @close="!operationBusy && (operation = undefined)" />
</template>
