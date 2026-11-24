<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import { emptyPlanSelection, type PlanSelectionState } from '../../types/samples/inbound'
import { normalizeConclusion } from '../../types/testing/dataEntryDetail'
import { assignmentConclusions } from '../../types/testing/assignment'
import { dataCheckColumns, dataCheckStates, dataCheckActions, dataCheckDateFields, type DataCheckQuery, type DataCheckPage, type DataCheckRow } from '../../types/testing/dataCheck'
import { dataEntrySearchFields } from '../../types/testing/dataEntry'
import RegistrationAttachmentManager from '../../components/commissions/RegistrationAttachmentManager.vue'
import { sampleTypes } from '../../types/commissions/registration'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { clientYearRange } from '../../services/common/date'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { parseTableColumns } from '../../services/common/table'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'

const title = '检测数据校核', root = '/testing/data-check', route = useRoute(), router = useRouter(), dates = clientYearRange()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const ids = (key: string) => text(key).split(',').filter(Boolean)
const plans = ref(emptyPlanSelection()), planState = ref<PlanSelectionState>()
const drawer = ref(false), planFilter = ref<InstanceType<typeof TestPlanFilterDrawer>>(), planBusy = ref(false), planError = ref<ErrorValue>('')
function applyPlans(value: PlanSelectionState) { plans.value = value.selection; planState.value = value }
const query = computed<DataCheckQuery>(() => ({
  searchField: text('searchField', 'code') as DataCheckQuery['searchField'], contains: text('contains'),
  status: text('status', '检测数据校核中'), sampleType: text('sampleType'), conclusion: normalizeConclusion(text('conclusion')),
  dateField: text('dateField', 'commissionDate') as DataCheckQuery['dateField'], from: text('from', dates.from), to: text('to', dates.to),
  plans: { groupIds: ids('planGroups'), planIds: ids('planIds'), excludedPlanIds: ids('planExclude') },
  sort: text('sort', 'code') as DataCheckQuery['sort'], direction: text('direction') === 'desc' ? 'desc' : 'asc',
  page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10,
}))
const draft = ref({ searchField: 'code', contains: '', status: '检测数据校核中', sampleType: '', conclusion: '', dateField: 'commissionDate', ...dates })
const more = ref(false)
const activeFilters = computed(() => Number(!!draft.value.conclusion) + Number(!!(draft.value.from || draft.value.to)))
const dateInput = ref<InstanceType<typeof TemplateDateRange>>()
const emptyPage = (): DataCheckPage => ({ items: [], total: 0, page: 1, pageSize: 10, planSelection: { selection: emptyPlanSelection(), count: 0, total: 0, previews: [], groups: {} } })
const rows = ref<DataCheckPage>(emptyPage()), selected = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>('')
const exporting = ref(false), exportError = ref<ErrorValue>('')
const attachmentId = ref<string>()
watch(() => [route.fullPath, currentActor.value.id], () => { attachmentId.value = undefined; statusAction.value = undefined })
const statusAction = ref<{ row: DataCheckRow; action: 'undo' }>()
const actionBusy = ref(false), statusError = ref<ErrorValue>('')
function actionAllowed(row: DataCheckRow, label: string) {
  if (label === '数据校核') return row.canCheck
  if (label === '撤销校核') return row.canUndoCheck
  return label === '查看附件'
}
async function runStatusAction() {
  const target = statusAction.value
  if (!target || actionBusy.value) return
  const actor = currentActor.value.id
  actionBusy.value = true; statusError.value = ''
  try {
    await registrationDemo.dataCheckAction(target.row.id, target.action, target.row.version)
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
function rowAction(row: DataCheckRow, label: string) {
  if (loading.value || actionBusy.value || !actionAllowed(row, label)) return
  if (label === '查看附件') attachmentId.value = row.id
  else if (label === '数据校核') void router.push({ path: `${root}/${encodeURIComponent(row.id)}`, query: { returnTo: route.fullPath } })
  else { statusError.value = ''; statusAction.value = { row, action: 'undo' } }
}
const columnKeys = computed(() => parseTableColumns(dataCheckColumns, route.query.columns))
const columns = computed(() => dataCheckColumns.filter(column => columnKeys.value.includes(column.key)))
let sequence = 0, exportSequence = 0, controller: AbortController | undefined
async function load() {
  const token = ++sequence, appliedPlans = JSON.stringify(query.value.plans)
  controller?.abort(); const active = controller = new AbortController()
  loading.value = true; error.value = ''; selected.value = []
  try {
    const result = await registrationDemo.dataCheckSamples(query.value, active.signal)
    if (token !== sequence) return
    rows.value = result
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
  const next = new Set<keyof DataCheckRow>(columnKeys.value)
  if (checked) next.add(key as keyof DataCheckRow); else next.delete(key as keyof DataCheckRow)
  void patch({ columns: [...next].join(',') })
}
async function exportRows(onlySelected: boolean) {
  if (loading.value || error.value || exporting.value || onlySelected && !selected.value.length) return
  const token = ++exportSequence
  exporting.value = true; exportError.value = ''
  try {
    const blob = await registrationDemo.exportDataCheckSamples({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) })
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
  sequence++; controller?.abort(); exportSequence++; exporting.value = false; selected.value = []; rows.value = emptyPage()
  drawer.value = false; planBusy.value = false; planError.value = ''; planState.value = undefined; plans.value = emptyPlanSelection()
  error.value = ''; exportError.value = ''; more.value = false
  const previous = route.fullPath
  await router.replace({ path: root })
  if (previous === route.fullPath) void load()
})
onBeforeUnmount(() => { sequence++; exportSequence++; controller?.abort() })
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :columns="dataCheckColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows">
        <button type="button" class="btn btn-light text-body text-nowrap" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-haspopup="dialog" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}<span v-if="planBusy" class="spinner-border spinner-border-sm ms-1" aria-label="正在更新方案选择"></span></button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}条件`" @submit.prevent="search">
      <QueryFormLayout>
        <div class="row g-3 align-items-end">
          <div class="col-12 col-xl-6">
            <div class="row g-2">
              <div class="col-12 col-sm-5"><label for="data-check-field" class="form-label">查询内容</label><select id="data-check-field" v-model="draft.searchField" class="form-select"><option v-for="field in dataEntrySearchFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div>
              <div class="col-12 col-sm-7"><label for="data-check-contains" class="form-label">包含</label><input id="data-check-contains" v-model="draft.contains" class="form-control" maxlength="200" /></div>
            </div>
          </div>
          <div class="col-6 col-xl-3"><label for="data-check-status" class="form-label">数据状态</label><select id="data-check-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in dataCheckStates" :key="status">{{ status }}</option></select></div>
          <div class="col-6 col-xl-3"><label for="data-check-type" class="form-label">样品类型</label><select id="data-check-type" v-model="draft.sampleType" class="form-select"><option value="">全部</option><option v-for="type in sampleTypes" :key="type">{{ type }}</option></select></div>
        </div>
      <div v-show="more" id="data-check-more-filters" class="row g-3 align-items-start mt-0">
          <div class="col-12 col-md-4 col-xl-3"><label for="data-check-conclusion" class="form-label">结论状态</label><select id="data-check-conclusion" v-model="draft.conclusion" class="form-select"><option value="">全部</option><option v-for="conclusion in assignmentConclusions" :key="conclusion">{{ conclusion }}</option></select></div>
          <div class="col-12 col-md-8 col-xl-9">
            <label for="data-check-dates" class="form-label">日期</label>
            <div class="row g-2"><div class="col-12 col-sm-4"><select v-model="draft.dateField" class="form-select" aria-label="日期字段"><option v-for="field in dataCheckDateFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div><div class="col-12 col-sm-8"><TemplateDateRange id="data-check-dates" ref="dateInput" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div></div>
          </div>
      </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="data-check-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
      <div v-if="planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" type="button" class="btn btn-link btn-sm p-0" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load()">
      <template #cell-attachmentCount="{ row }">{{ row.attachmentCount > 0 ? '有' : '' }}</template>
      <template #actions="{ row }">
        <button v-for="action in dataCheckActions" :key="action.label" type="button" role="menuitem" class="dropdown-item" :disabled="loading || actionBusy || !actionAllowed(row, action.label)" @click="rowAction(row, action.label)">
          <i :class="action.icon" class="me-2 text-muted" aria-hidden="true"></i>{{ action.label }}
        </button>
      </template>
    </DataTable>
  </section>
  <BootstrapModal v-if="statusAction" open title="撤销校核" :busy="actionBusy" scrollable @close="!actionBusy && (statusAction = undefined)">
    <p class="text-break"><strong>{{ statusAction.row.code }}</strong> · {{ statusAction.row.name }}</p>
    <ErrorNotice :error="statusError" />
    <p>确认撤销此条数据校核？撤销后将清除本次校核人和校核日期。</p>
    <template #footer><button type="button" class="btn btn-light" :disabled="actionBusy" @click="statusAction = undefined">取消</button><button type="button" class="btn btn-primary" :disabled="actionBusy" @click="runStatusAction">{{ actionBusy ? '正在保存…' : '确认' }}</button></template>
  </BootstrapModal>
  <TestPlanFilterDrawer ref="planFilter" sample-scope="data-check" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
  <RegistrationAttachmentManager v-if="attachmentId" :id="attachmentId" kind="samples" @close="attachmentId = undefined" readonly title="查看附件" />
</template>
