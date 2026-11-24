<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import { flowColumns, flowStates, flowDateFields, flowDateEnabled, type FlowDateKey, type FlowDateRange, type FlowQuery, type FlowPage, type FlowRow } from '../../types/samples/flow'
import { emptyPlanSelection, type PlanSelectionState } from '../../types/samples/inbound'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { clientYearRange } from '../../services/common/date'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { parseTableColumns } from '../../services/common/table'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'

const title = '样品流转查询', root = '/samples/flow', route = useRoute(), router = useRouter(), dates = clientYearRange()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const ids = (key: string) => text(key).split(',').filter(Boolean)
const routeDates = () => Object.fromEntries(flowDateFields.map(field => [field.key, { from: text(`${field.key}From`, dates.from), to: text(`${field.key}To`, dates.to) }])) as Record<FlowDateKey, FlowDateRange>
const dateDraft = ref(routeDates()), dateInputs = ref<InstanceType<typeof TemplateDateRange>[]>([])
const query = computed<FlowQuery>(() => ({ code: text('code'), status: text('status'),
  dates: Object.fromEntries(flowDateFields.filter(field => flowDateEnabled(field.key, text('status'))).map(field => [field.key, routeDates()[field.key]])),
  plans: { groupIds: ids('planGroups'), planIds: ids('planIds'), excludedPlanIds: ids('planExclude') },
  sort: 'code', direction: text('direction') === 'desc' ? 'desc' : 'asc',
  page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10,
}))
const draft = ref({ code: '', status: '' }), plans = ref(emptyPlanSelection()), planState = ref<PlanSelectionState>()
const more = ref(false)
const activeFilters = computed(() => flowDateFields.filter(field => flowDateEnabled(field.key, draft.value.status) && (dateDraft.value[field.key].from || dateDraft.value[field.key].to)).length)
const drawer = ref(false), planFilter = ref<InstanceType<typeof TestPlanFilterDrawer>>(), planBusy = ref(false), planError = ref<ErrorValue>('')
const emptyPage = (): FlowPage => ({ items: [], total: 0, page: 1, pageSize: 10, planSelection: { selection: emptyPlanSelection(), count: 0, total: 0, previews: [], groups: {} } })
const rows = ref<FlowPage>(emptyPage()), selected = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>('')
const exporting = ref(false), exportError = ref<ErrorValue>('')
const columnKeys = computed(() => parseTableColumns(flowColumns, route.query.columns))
const columns = computed(() => flowColumns.filter(column => columnKeys.value.includes(column.key)))
let sequence = 0, exportSequence = 0, controller: AbortController | undefined
async function load() {
  const token = ++sequence, appliedPlans = JSON.stringify(query.value.plans)
  controller?.abort(); const active = controller = new AbortController()
  loading.value = true; error.value = ''; selected.value = []
  try {
    const result = await registrationDemo.flowSamples(query.value, active.signal)
    if (token !== sequence) return
    rows.value = result
    if (JSON.stringify(plans.value) === appliedPlans) { planState.value = result.planSelection; plans.value = result.planSelection.selection }
  } catch (issue) { if (token === sequence && !active.signal.aborted) { error.value = normalizeError(issue); rows.value.items = [] } }
  finally { if (token === sequence) loading.value = false }
}
const patch = (values: Record<string, string | undefined>) => router.push({ path: root, query: { ...route.query, ...values } })
async function search() {
  if (loading.value || planBusy.value) return
  if (dateInputs.value.some(input => !input.validate())) { more.value = true; return }
  const previous = JSON.stringify(query.value)
  await patch({ ...Object.fromEntries(flowDateFields.flatMap(field => [[`${field.key}From`, dateDraft.value[field.key].from], [`${field.key}To`, dateDraft.value[field.key].to]])), code: draft.value.code.trim() || undefined, status: draft.value.status || undefined, page: '1',
    planGroups: plans.value.groupIds.join(',') || undefined, planIds: plans.value.planIds.join(',') || undefined, planExclude: plans.value.excludedPlanIds.join(',') || undefined })
  if (previous === JSON.stringify(query.value)) void load()
}
function applyPlans(value: PlanSelectionState) { plans.value = value.selection; planState.value = value }
function toggleColumn(key: string, checked: boolean) {
  const next = new Set<Extract<keyof FlowRow, string>>(columnKeys.value)
  if (checked) next.add(key as keyof FlowRow); else next.delete(key as keyof FlowRow)
  void patch({ columns: [...next].join(',') })
}
async function exportRows(onlySelected: boolean) {
  if (loading.value || error.value || exporting.value || onlySelected && !selected.value.length) return
  const token = ++exportSequence
  exporting.value = true; exportError.value = ''
  try {
    const blob = await registrationDemo.exportFlowSamples({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) })
    if (token === exportSequence) downloadBlob(blob, `${title}.csv`)
  } catch (issue) { if (token === exportSequence) exportError.value = normalizeError(issue) }
  finally { if (token === exportSequence) exporting.value = false }
}
watch(() => JSON.stringify(query.value), () => {
  draft.value = { code: query.value.code || '', status: query.value.status || '' }
  dateDraft.value = routeDates()
  plans.value = query.value.plans!; planState.value = undefined; exportSequence++; exporting.value = false; exportError.value = ''
  void load()
}, { immediate: true })
watch(() => currentActor.value.id, async () => {
  sequence++; controller?.abort(); exportSequence++; exporting.value = false; drawer.value = false; selected.value = []; rows.value = emptyPage()
  planBusy.value = false; planError.value = ''; planState.value = undefined; plans.value = emptyPlanSelection(); error.value = ''; exportError.value = ''; more.value = false
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
      <TableToolbar :label="title" :columns="flowColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows">
        <button type="button" class="btn btn-light text-body text-nowrap" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-haspopup="dialog" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}<span v-if="planBusy" class="spinner-border spinner-border-sm ms-1" aria-label="正在更新方案选择"></span></button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}条件`" @submit.prevent="search">
      <QueryFormLayout>
        <div class="row g-3 align-items-end">
          <div class="col-12 col-md-6"><label for="flow-code" class="form-label">样品编号</label><input id="flow-code" v-model="draft.code" class="form-control" maxlength="200" /></div>
          <div class="col-12 col-md-6"><label for="flow-status" class="form-label">流转状态</label><select id="flow-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in flowStates" :key="status">{{ status }}</option></select></div>
        </div>
      <div v-show="more" id="flow-more-filters" class="row g-3 align-items-start mt-0">
          <div v-for="field in flowDateFields" :key="field.key" class="col-12 col-md-6 col-xxl-3"><label :for="`flow-${field.key}-dates`" class="form-label">{{ field.label }}</label><TemplateDateRange :id="`flow-${field.key}-dates`" ref="dateInputs" :from="dateDraft[field.key].from" :to="dateDraft[field.key].to" :disabled="!flowDateEnabled(field.key, draft.status)" @change="dateDraft[field.key] = $event" /></div>
      </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="flow-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
      <div v-if="planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" type="button" class="btn btn-link btn-sm p-0" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" sort-key="code" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @sort="patch({ direction: query.direction === 'asc' ? 'desc' : 'asc', page: '1' })" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load">
      <template #cell-retentionTime="{ row }">{{ row.retentionTime ? new Date(row.retentionTime).toLocaleString('zh-CN', { hour12: false }) : '—' }}</template>
    </DataTable>
  </section>
  <TestPlanFilterDrawer ref="planFilter" sample-scope="flow" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
</template>
