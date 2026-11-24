<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import CancellationApprovalModal from '../../components/commissions/CancellationApprovalModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { clientYearRange } from '../../services/common/date'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import type { RegistrationPage, RegistrationSample } from '../../types/commissions/registration'
import { cancellationRoot, cancellationColumns, cancellationStates, cancellationDate, canApproveCancellation, type CancellationColumnKey, type CancellationQuery, type CancellationRow } from '../../types/commissions/cancellationApproval'

const route = useRoute(), router = useRouter(), dates = clientYearRange()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const query = computed<CancellationQuery>(() => ({
  from: text('from', dates.from), to: text('to', dates.to), result: (text('result', '申请中') === '' || (cancellationStates as readonly string[]).includes(text('result', '申请中')) ? text('result', '申请中') : '申请中') as CancellationQuery['result'],
  sort: (['code', 'appliedAt', 'approvedAt'].includes(text('sort')) ? text('sort') : 'appliedAt') as CancellationQuery['sort'],
  direction: text('direction') === 'asc' ? 'asc' : 'desc',
  page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10,
}))
const draft = reactive({ from: dates.from, to: dates.to, result: '申请中' })
watch(query, value => Object.assign(draft, { from: value.from, to: value.to, result: value.result || '' }), { immediate: true })
const rows = ref<RegistrationPage<CancellationRow>>({ items: [], total: 0, page: 1, pageSize: 10 })
const selected = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>('')
const columnKeys = computed(() => parseTableColumns(cancellationColumns, route.query.columns))
const columns = computed(() => cancellationColumns.filter(column => columnKeys.value.includes(column.key)))
const approving = ref<RegistrationSample & { commissionCode: string }>(), actionLoading = ref(false), actionError = ref<ErrorValue>('')
const exporting = ref(false)
let request = 0, actionRequest = 0, exportRequest = 0, controller: AbortController | undefined
async function load() {
  const token = ++request
  controller?.abort(); controller = new AbortController()
  loading.value = true; error.value = ''; selected.value = []
  try {
    const result = await registrationDemo.cancellationApprovals(query.value, controller.signal)
    if (token === request) rows.value = result
  } catch (issue) {
    if (token === request && !controller.signal.aborted) { error.value = normalizeError(issue); rows.value.items = [] }
  } finally { if (token === request) loading.value = false }
}
function patch(values: Record<string, string | undefined>) { return router.push({ path: cancellationRoot, query: { ...route.query, ...values } }) }
async function search() {
  const previous = route.fullPath
  await patch({ from: draft.from, to: draft.to, result: draft.result, page: '1' })
  if (previous === route.fullPath) void load()
}
function sort(key: string) { void patch({ sort: key, direction: query.value.sort === key && query.value.direction === 'asc' ? 'desc' : 'asc', page: '1' }) }
function toggleColumn(key: string, checked: boolean) {
  const next = new Set(columnKeys.value)
  if (checked) next.add(key as CancellationColumnKey); else next.delete(key as CancellationColumnKey)
  void patch({ columns: [...next].join(',') })
}
async function openApproval(row: CancellationRow) {
  if (loading.value || actionLoading.value || row.approvalResult === '申请中' && !canApproveCancellation(currentActor.value)) return
  const token = ++actionRequest
  actionLoading.value = true; actionError.value = ''
  try { const record = await registrationDemo.sample(row.id); if (token === actionRequest) approving.value = record }
  catch (issue) { if (token === actionRequest) actionError.value = normalizeError(issue) }
  finally { if (token === actionRequest) actionLoading.value = false }
}
async function exportRows(onlySelected: boolean) {
  if (exporting.value || loading.value || error.value || onlySelected && !selected.value.length) return
  const token = ++exportRequest
  exporting.value = true; actionError.value = ''
  try {
    const csv = await registrationDemo.exportCancellationApprovals({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) })
    if (token === exportRequest) downloadBlob(csv, '作废审批.csv')
  } catch (issue) { if (token === exportRequest) actionError.value = normalizeError(issue) }
  finally { if (token === exportRequest) exporting.value = false }
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id], (value, old) => {
  actionRequest++; actionLoading.value = false; approving.value = undefined; actionError.value = ''
  exportRequest++; exporting.value = false
  if (old && value[1] !== old[1]) rows.value.items = []
  void load()
}, { immediate: true })
onBeforeUnmount(() => { request++; actionRequest++; exportRequest++; controller?.abort() })
</script>

<template>
  <PageHeading title="作废审批" />
  <section class="card" aria-label="作废审批列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">作废审批</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar label="作废审批" :columns="cancellationColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows" />
    </div>
    <form class="card-body border-bottom" aria-label="作废审批查询" @submit.prevent="search">
      <QueryFormLayout>
      <div class="row g-3 align-items-start">
        <div class="col-12 col-md-6"><label class="form-label" for="cancellation-dates">申请日期</label><TemplateDateRange id="cancellation-dates" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div>
        <div class="col-12 col-md-6"><label class="form-label" for="cancellation-result">数据状态</label><select id="cancellation-result" v-model="draft.result" class="form-select"><option value="">全部</option><option v-for="result in cancellationStates" :key="result">{{ result }}</option></select></div>
      </div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
      </QueryFormLayout>
    </form>
    <div v-if="actionError" class="px-3 pt-3"><ErrorNotice :error="actionError" /></div>
    <DataTable label="作废审批" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected"
      :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading :actions-disabled="actionLoading"
      @sort="sort" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load">
      <template #cell-approvalResult="{ row }"><span class="badge" :class="row.approvalResult === '申请中' ? 'bg-warning-subtle text-warning' : row.approvalResult === '申请通过' ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger'">{{ row.approvalResult }}</span></template>
      <template #cell-appliedAt="{ row }"><span :title="row.appliedAt">{{ cancellationDate(row.appliedAt) }}</span></template>
      <template #cell-approvedAt="{ row }"><span :title="row.approvedAt">{{ cancellationDate(row.approvedAt) }}</span></template>
      <template #actions="{ row }">
        <button class="dropdown-item" type="button" role="menuitem" :disabled="row.approvalResult === '申请中' && !canApproveCancellation(currentActor)" @click="openApproval(row)"><i :class="row.approvalResult === '申请中' ? 'ti ti-circle-check' : 'ti ti-eye'" class="align-bottom me-2 text-muted" aria-hidden="true"></i>{{ row.approvalResult === '申请中' ? '审批' : '查看审批结果' }}</button>
      </template>
    </DataTable>
  </section>
  <CancellationApprovalModal :record="approving" @close="approving = undefined" @saved="load" />
</template>
