<script setup lang="ts">
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { outboundStates, type OutboundAction, type OutboundSubmission } from '../../types/samples/outbound'
import { disposalColumns, disposalStates, disposalRequirements, disposalSearchFields, type DisposalQuery, type DisposalAction, type DisposalSubmission } from '../../types/samples/disposal'
import type { TableColumn } from '../../types/common/table'
import SampleDisposalActionModal from '../../components/samples/SampleDisposalActionModal.vue'
import SampleOutboundActionModal from '../../components/samples/SampleOutboundActionModal.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import TemplateDate from '../../components/common/TemplateDate.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { registrationCanWrite } from '../../services/commissions/registrationService'
import { parseTableColumns } from '../../services/common/table'
import { clientToday, clientYearRange } from '../../services/common/date'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { emptyPlanSelection, inboundColumns, inboundStates, inboundLocations, inboundConditions, type InboundReceipt, type InboundAction, type InboundPage, type InboundRow, type PlanSelectionState } from '../../types/samples/inbound'
const props = defineProps<{ mode: 'inbound' | 'outbound' | 'disposal' }>()
const outbound = props.mode === 'outbound', disposal = props.mode === 'disposal'
const title = disposal ? '样品处置' : outbound ? '样品出库' : '样品入库'
const allColumns: readonly TableColumn<Extract<keyof InboundRow, string>>[] = disposal ? disposalColumns : inboundColumns
const states = outbound ? outboundStates.filter(state => state !== '样品已领取') : inboundStates
const root = `/samples/${props.mode}`, route = useRoute(), router = useRouter(), dates = clientYearRange()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const ids = (key: string) => text(key).split(',').filter(Boolean)
const query = computed<DisposalQuery>(() => ({
  ...(disposal ? {
    searchField: text('searchField', 'code') as DisposalQuery['searchField'], keyword: text('keyword'), requirement: text('requirement'), status: text('status'),
    from: text('status') === '样品已处置' ? text('disposalFrom', dates.from) : undefined,
    to: text('status') === '样品已处置' ? text('disposalTo', dates.to) : undefined,
  } : { code: text('code'), status: text('status', states[0]), from: text('from', dates.from), to: text('to', dates.to) }),
  plans: { groupIds: ids('planGroups'), planIds: ids('planIds'), excludedPlanIds: ids('planExclude') },
  sort: text('sort') === 'commissionDate' ? 'commissionDate' : 'code', direction: text('direction') === 'desc' ? 'desc' : 'asc',
  page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10,
}))
const draft = reactive({ code: '', status: disposal ? '' : states[0], from: dates.from, to: dates.to, searchField: 'code' as NonNullable<DisposalQuery['searchField']>, keyword: '', requirement: '' })
const disposalDateRange = ref<InstanceType<typeof TemplateDateRange>>()
const plans = ref(emptyPlanSelection()), planState = ref<PlanSelectionState>(), drawer = ref(false)
const planFilter = ref<InstanceType<typeof TestPlanFilterDrawer>>(), planBusy = ref(false), planError = ref<ErrorValue>('')
const emptyPage = (): InboundPage => ({ items: [], total: 0, page: 1, pageSize: 10, sites: [], planSelection: { selection: emptyPlanSelection(), count: 0, total: 0, previews: [], groups: {} } })
const rows = ref<InboundPage>(emptyPage()), selected = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>(''), actionError = ref<ErrorValue>(''), exporting = ref(false)
const operation = ref<{ row: InboundRow; action: InboundAction }>(), operationBusy = ref(false), operationError = ref<ErrorValue>('')
const disposalOperation = ref<{ row: InboundRow; action: DisposalAction }>()
function canDispose(row: InboundRow, action: DisposalAction) { return disposal && !loading.value && !operationBusy.value && !!row.disposalActions?.includes(action) }
function openDisposal(row: InboundRow, action: DisposalAction) {
  if (!canDispose(row, action)) return
  operationError.value = ''; disposalOperation.value = { row, action }
}
async function submitDisposal(submission: DisposalSubmission) {
  const target = disposalOperation.value
  if (!target || target.action !== submission.action || !canDispose(target.row, target.action)) return
  const token = ++operationSequence
  operationBusy.value = true; operationError.value = ''
  try {
    await registrationDemo.disposalAction(target.row.id, target.row.version, submission)
    if (token !== operationSequence) return
    operationBusy.value = false; disposalOperation.value = undefined
    await load()
  } catch (issue) { if (token === operationSequence) operationError.value = normalizeError(issue) }
  finally { if (token === operationSequence) operationBusy.value = false }
}
const outboundOperation = ref<{ row: InboundRow; action: OutboundAction }>()
const operationLabel = computed(() => operation.value?.action === 'undo' ? '撤销入库' : '入库')
const receipt = ref<InboundReceipt>({ account: '', name: '', date: '', location: '检测室', condition: '正常', notes: '' })
const receiptErrors = ref<Partial<Record<keyof InboundReceipt, string>>>({}), receiptValidation = ref('')
const receiptKeys = ['account', 'name', 'date', 'location', 'condition', 'notes'] as const
function receiptFeedback(key: keyof InboundReceipt) {
  return { class: { 'is-invalid': !!receiptErrors.value[key] }, 'aria-invalid': !!receiptErrors.value[key], 'aria-describedby': receiptErrors.value[key] ? `receipt-${key}-error` : undefined }
}
for (const key of receiptKeys) watch(() => receipt.value[key], () => {
  delete receiptErrors.value[key]
  if (key === 'account' || key === 'name') { delete receiptErrors.value.account; delete receiptErrors.value.name }
  receiptValidation.value = ''
})
let operationSequence = 0
function canOutbound(row: InboundRow, action: OutboundAction) {
  return outbound && !loading.value && !operationBusy.value && !!row.outboundActions?.includes(action)
}
function openOutbound(row: InboundRow, action: OutboundAction) {
  if (!canOutbound(row, action)) return
  operationError.value = ''; outboundOperation.value = { row, action }
}
async function submitOutbound(submission: OutboundSubmission) {
  const target = outboundOperation.value
  if (!target || target.action !== submission.action || !canOutbound(target.row, target.action)) return
  const token = ++operationSequence
  operationBusy.value = true; operationError.value = ''
  try {
    await registrationDemo.outboundAction(target.row.id, target.row.version, submission)
    if (token !== operationSequence) return
    operationBusy.value = false; outboundOperation.value = undefined
    await load()
  } catch (issue) { if (token === operationSequence) operationError.value = normalizeError(issue) }
  finally { if (token === operationSequence) operationBusy.value = false }
}
function canOperate(row: InboundRow, action: InboundAction) {
  return !outbound && !loading.value && !operationBusy.value && registrationCanWrite(currentActor.value, 'samples') && !['void_pending', 'voided'].includes(row.status)
    && row.dataStatus === (action === 'receive' ? '样品入库中' : '样品入库完成')
}
function openOperation(row: InboundRow, action: InboundAction) {
  if (!canOperate(row, action)) return
  receipt.value = { account: currentActor.value.id, name: currentActor.value.name, date: clientToday(), location: '检测室', condition: '正常', notes: '' }
  operationError.value = ''; receiptErrors.value = {}; receiptValidation.value = ''; operation.value = { row, action }
}
async function submitOperation() {
  const target = operation.value
  if (!target || !canOperate(target.row, target.action)) return
  const token = ++operationSequence
  operationBusy.value = true; operationError.value = ''; receiptErrors.value = {}; receiptValidation.value = ''
  try {
    await registrationDemo.inboundAction(target.row.id, target.action, target.row.version, target.action === 'receive' ? { ...receipt.value } : undefined)
    if (token !== operationSequence) return
    operationBusy.value = false; operation.value = undefined
    await load()
  } catch (issue) {
    if (token === operationSequence) {
      const failure = normalizeError(issue)
      if (failure.code === 'VALIDATION') {
        for (const key of receiptKeys) if (failure.fieldErrors?.[key]) receiptErrors.value[key] = failure.fieldErrors[key]
        if (!Object.keys(receiptErrors.value).length) receiptValidation.value = failure.message
        void nextTick(() => { if (token === operationSequence) document.querySelector<HTMLElement>('#sample-inbound-operation .is-invalid')?.focus() })
      } else operationError.value = failure
    }
  }
  finally { if (token === operationSequence) operationBusy.value = false }
}
function refreshOperation() { if (!operationBusy.value) { operation.value = undefined; outboundOperation.value = undefined; disposalOperation.value = undefined; void load() } }
const columnKeys = computed(() => parseTableColumns(allColumns, route.query.columns))
const columns = computed(() => allColumns.filter(column => columnKeys.value.includes(column.key)))
let sequence = 0, exportSequence = 0, controller: AbortController | undefined
async function load() {
  const token = ++sequence, appliedPlans = JSON.stringify(query.value.plans)
  controller?.abort(); const active = controller = new AbortController()
  loading.value = true; error.value = ''; selected.value = []
  try {
    const result = await (disposal ? registrationDemo.disposalSamples : outbound ? registrationDemo.outboundSamples : registrationDemo.inboundSamples)(query.value, active.signal)
    if (token === sequence) {
      rows.value = result
      if (JSON.stringify(plans.value) === appliedPlans) { planState.value = result.planSelection; plans.value = result.planSelection.selection }
    }
  } catch (issue) { if (token === sequence && !active.signal.aborted) { error.value = normalizeError(issue); rows.value.items = [] } }
  finally { if (token === sequence) loading.value = false }
}
const patch = (values: Record<string, string | undefined>) => router.push({ path: root, query: { ...route.query, ...values, site: undefined } })
async function search() {
  if (loading.value || planBusy.value || disposal && !disposalDateRange.value?.validate()) return
  const previous = JSON.stringify(query.value)
  await patch({ ...(disposal ? { code: undefined, from: undefined, to: undefined, searchField: draft.searchField, keyword: draft.keyword.trim() || undefined, requirement: draft.requirement || undefined, status: draft.status, disposalFrom: draft.from, disposalTo: draft.to } : { code: draft.code.trim() || undefined, status: draft.status, from: draft.from, to: draft.to }),
    planGroups: plans.value.groupIds.join(',') || undefined, planIds: plans.value.planIds.join(',') || undefined, planExclude: plans.value.excludedPlanIds.join(',') || undefined, page: '1' })
  if (previous === JSON.stringify(query.value)) void load()
}
function applyPlans(value: PlanSelectionState) { plans.value = value.selection; planState.value = value }
function sort(key: string) { void patch({ sort: key, direction: query.value.sort === key && query.value.direction === 'asc' ? 'desc' : 'asc', page: '1' }) }
function toggleColumn(key: string, checked: boolean) {
  const next = new Set(columnKeys.value)
  if (checked) next.add(key as Extract<keyof InboundRow, string>); else next.delete(key as Extract<keyof InboundRow, string>)
  void patch({ columns: [...next].join(',') })
}
function view(row: InboundRow) { if (!loading.value) void router.push({ path: `${root}/samples/${row.id}`, query: { returnTo: route.fullPath } }) }
async function exportRows(onlySelected: boolean) {
  if (loading.value || error.value || exporting.value || onlySelected && !selected.value.length) return
  const token = ++exportSequence
  exporting.value = true; actionError.value = ''
  try { const blob = await (disposal ? registrationDemo.exportDisposalSamples : outbound ? registrationDemo.exportOutboundSamples : registrationDemo.exportInboundSamples)({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) }); if (token === exportSequence) downloadBlob(blob, `${title}.csv`) }
  catch (issue) { if (token === exportSequence) actionError.value = normalizeError(issue) }
  finally { if (token === exportSequence) exporting.value = false }
}
watch(() => JSON.stringify(query.value), () => {
  Object.assign(draft, { code: query.value.code || '', status: query.value.status || '', from: disposal ? text('disposalFrom', dates.from) : query.value.from, to: disposal ? text('disposalTo', dates.to) : query.value.to, searchField: query.value.searchField || 'code', keyword: query.value.keyword || '', requirement: query.value.requirement || '' })
  plans.value = query.value.plans!; planState.value = undefined; exportSequence++; exporting.value = false; actionError.value = ''
  void load()
}, { immediate: true })
watch(() => currentActor.value.id, async () => {
  operationSequence++; operationBusy.value = false; operation.value = undefined; outboundOperation.value = undefined; disposalOperation.value = undefined; operationError.value = ''
  planBusy.value = false; planError.value = ''
  sequence++; controller?.abort(); exportSequence++; exporting.value = false; drawer.value = false; selected.value = []; rows.value = emptyPage(); planState.value = undefined; plans.value = emptyPlanSelection(); error.value = ''; actionError.value = ''
  const previous = route.fullPath
  await router.replace({ path: root })
  if (previous === route.fullPath) void load()
})
onBeforeUnmount(() => { sequence++; exportSequence++; operationSequence++; controller?.abort() })
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3"><div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div><TableToolbar :label="title" :columns="allColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows"><button id="inbound-plans" type="button" class="btn btn-light text-body text-nowrap" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-haspopup="dialog" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}<span v-if="planBusy" class="spinner-border spinner-border-sm ms-1" aria-label="正在更新方案选择"></span></button></TableToolbar></div>
    <form class="card-body border-bottom" :aria-label="`${title}查询`" @submit.prevent="search">
      <QueryFormLayout>
      <div v-if="disposal" class="row g-3 align-items-start">
        <div class="col-12 col-xl"><div class="row g-2"><div class="col-12 col-sm-5"><label for="disposal-field" class="form-label">查询内容</label><select id="disposal-field" v-model="draft.searchField" class="form-select"><option v-for="field in disposalSearchFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div><div class="col-12 col-sm-7"><label for="disposal-keyword" class="form-label">包含</label><input id="disposal-keyword" v-model="draft.keyword" class="form-control" maxlength="200" placeholder="请输入查询内容" /></div></div></div>
        <div class="col-6 col-xl-auto"><label for="disposal-requirement-filter" class="form-label">处置要求</label><select id="disposal-requirement-filter" v-model="draft.requirement" class="form-select"><option value="">全部</option><option v-for="requirement in disposalRequirements" :key="requirement">{{ requirement }}</option></select></div>
        <div class="col-6 col-xl-auto"><label for="disposal-status-filter" class="form-label">处置状态</label><select id="disposal-status-filter" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in disposalStates" :key="status">{{ status }}</option></select></div>
        <div class="col-12 col-xl-3"><label for="disposal-dates" class="form-label">处置时间</label><TemplateDateRange id="disposal-dates" ref="disposalDateRange" :from="draft.from" :to="draft.to" :disabled="draft.status !== '样品已处置'" @change="Object.assign(draft, $event)" /></div>
      </div>
      <div v-else class="row g-3 align-items-start">
        <div class="col-12 col-md-4"><label for="inbound-code" class="form-label">样品编号</label><input id="inbound-code" v-model="draft.code" class="form-control" maxlength="200" /></div>
        <div class="col-12 col-md-4"><label for="inbound-status" class="form-label">数据状态</label><select id="inbound-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in states" :key="status">{{ status }}</option></select></div>
        <div class="col-12 col-md-4"><label for="inbound-dates" class="form-label">委托日期</label><TemplateDateRange id="inbound-dates" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div>
      </div>
      <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
      </QueryFormLayout>
      <div v-if="planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" type="button" class="btn btn-link btn-sm p-0" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="actionError" class="px-3 pt-3"><ErrorNotice :error="actionError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @sort="sort" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load">
      <template #cell-code="{ row }"><button type="button" class="btn btn-link p-0 text-nowrap" :disabled="loading" @click="view(row)">{{ row.code }}</button></template>
      <template #cell-retentionTime="{ row }">{{ row.retentionTime ? new Date(row.retentionTime).toLocaleString('zh-CN', { hour12: false }) : '—' }}</template>
      <template #cell-dataStatus="{ row }"><span class="badge" :class="['样品入库完成', '样品已领取'].includes(row.dataStatus) ? 'bg-success-subtle text-success' : 'bg-info-subtle text-info'">{{ row.dataStatus }}</span></template>
      <template #actions="{ row }"><template v-if="disposal"><button type="button" role="menuitem" class="dropdown-item" :disabled="!canDispose(row, 'dispose')" @click="openDisposal(row, 'dispose')"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>样品处置</button><button type="button" role="menuitem" class="dropdown-item" :disabled="!canDispose(row, 'undo')" @click="openDisposal(row, 'undo')"><i class="ti ti-arrow-back-up me-2 text-muted" aria-hidden="true"></i>撤销处置</button></template><template v-else-if="outbound"><button type="button" role="menuitem" class="dropdown-item" :disabled="!canOutbound(row, 'dispatch')" @click="openOutbound(row, 'dispatch')"><i class="ti ti-package-export me-2 text-muted" aria-hidden="true"></i>出库</button><button type="button" role="menuitem" class="dropdown-item" :disabled="!canOutbound(row, 'undo')" @click="openOutbound(row, 'undo')"><i class="ti ti-arrow-back-up me-2 text-muted" aria-hidden="true"></i>撤销出库</button><button type="button" role="menuitem" class="dropdown-item" :disabled="!canOutbound(row, 'return')" @click="openOutbound(row, 'return')"><i class="ti ti-arrow-back me-2 text-muted" aria-hidden="true"></i>退回委托</button></template><template v-else><button type="button" role="menuitem" class="dropdown-item" :disabled="!canOperate(row, 'receive')" @click="openOperation(row, 'receive')"><i class="ti ti-inbox me-2 text-muted" aria-hidden="true"></i>入库</button><button type="button" role="menuitem" class="dropdown-item" :disabled="!canOperate(row, 'undo')" @click="openOperation(row, 'undo')"><i class="ti ti-arrow-back-up me-2 text-muted" aria-hidden="true"></i>撤销入库</button></template></template>
    </DataTable>
  </section>
  <TestPlanFilterDrawer ref="planFilter" :sample-scope="mode" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
  <SampleDisposalActionModal v-if="disposal" :operation="disposalOperation" :busy="operationBusy" :error="operationError" @submit="submitDisposal" @refresh="refreshOperation" @close="!operationBusy && (disposalOperation = undefined)" />
  <SampleOutboundActionModal v-if="outbound" :operation="outboundOperation" :busy="operationBusy" :error="operationError" @close="!operationBusy && (outboundOperation = undefined)" @submit="submitOutbound" @refresh="refreshOperation" />
  <BootstrapModal v-if="mode === 'inbound'" :open="!!operation" :title="operation?.action === 'receive' ? '样品入库' : operationLabel" :busy="operationBusy" scrollable @close="!operationBusy && (operation = undefined)">
    <ErrorNotice :error="operationError" />
    <FeedbackNotice v-if="receiptValidation" :message="receiptValidation" />
    <button v-if="operationError && ['BUSINESS_RULE'].includes(operationError.code)" type="button" class="btn btn-outline-primary btn-sm" :disabled="operationBusy" @click="refreshOperation">刷新列表</button>
    <form v-if="operation" id="sample-inbound-operation" @submit.prevent="submitOperation">
      <p class="text-break text-muted"><strong>{{ operation.row.code }}</strong> · {{ operation.row.name }}</p>
      <fieldset v-if="operation.action === 'receive'" :disabled="operationBusy" class="row g-3">
        <div class="col-12 col-sm-6"><label for="receipt-account" class="form-label">样品管理员工号 <span class="text-danger">*</span></label><input id="receipt-account" v-bind="receiptFeedback('account')" v-model="receipt.account" class="form-control" required maxlength="100" autocomplete="off" /><div v-if="receiptErrors.account" id="receipt-account-error" class="invalid-feedback" role="alert">{{ receiptErrors.account }}</div></div>
        <div class="col-12 col-sm-6"><label for="receipt-name" class="form-label">样品管理员姓名 <span class="text-danger">*</span></label><input id="receipt-name" v-bind="receiptFeedback('name')" v-model="receipt.name" class="form-control" required maxlength="100" autocomplete="off" /><div v-if="receiptErrors.name" id="receipt-name-error" class="invalid-feedback" role="alert">{{ receiptErrors.name }}</div></div>
        <div class="col-12"><label for="receipt-date" class="form-label">入库日期 <span class="text-danger">*</span></label><TemplateDate id="receipt-date" v-bind="receiptFeedback('date')" v-model="receipt.date" required :disabled="operationBusy" /><div v-if="receiptErrors.date" id="receipt-date-error" class="invalid-feedback" role="alert">{{ receiptErrors.date }}</div></div>
        <div class="col-12 col-sm-6"><label for="receipt-location" class="form-label">样品存放地点 <span class="text-danger">*</span></label><select id="receipt-location" v-bind="receiptFeedback('location')" v-model="receipt.location" class="form-select" required><option v-for="location in inboundLocations" :key="location">{{ location }}</option></select><div v-if="receiptErrors.location" id="receipt-location-error" class="invalid-feedback" role="alert">{{ receiptErrors.location }}</div></div>
        <div class="col-12 col-sm-6"><label for="receipt-condition" class="form-label">样品状态 <span class="text-danger">*</span></label><select id="receipt-condition" v-bind="receiptFeedback('condition')" v-model="receipt.condition" class="form-select" required><option v-for="condition in inboundConditions" :key="condition">{{ condition }}</option></select><div v-if="receiptErrors.condition" id="receipt-condition-error" class="invalid-feedback" role="alert">{{ receiptErrors.condition }}</div></div>
        <div class="col-12"><label for="receipt-notes" class="form-label">备注</label><textarea id="receipt-notes" v-bind="receiptFeedback('notes')" v-model="receipt.notes" class="form-control" rows="3" maxlength="2000"></textarea><div v-if="receiptErrors.notes" id="receipt-notes-error" class="invalid-feedback" role="alert">{{ receiptErrors.notes }}</div></div>
      </fieldset>
      <p v-else>确认对这条样品执行“{{ operationLabel }}”？</p>
    </form>
    <template #footer><button type="button" class="btn btn-light" :disabled="operationBusy" @click="operation = undefined">取消</button><button type="submit" form="sample-inbound-operation" class="btn btn-primary" :disabled="operationBusy || !operation || !!operationError && ['BUSINESS_RULE'].includes(operationError.code)"><span v-if="operationBusy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ operationBusy ? '正在提交…' : '确认' }}</button></template>
  </BootstrapModal>
</template>
