<script setup lang="ts">
import { normalizeConclusion } from '../../types/testing/dataEntryDetail'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import AssignmentModal from '../../components/testing/AssignmentModal.vue'
import type { AssignmentSubmission } from '../../types/testing/assignment'
import TemplateToast from '../../components/common/TemplateToast.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import { emptyPlanSelection, type PlanSelectionState } from '../../types/samples/inbound'
import { assignmentColumns, assignmentStates, assignmentConclusions, assignmentSearchFields, assignmentDateFields, assignmentActions, type AssignmentQuery, type AssignmentPage, type AssignmentRow } from '../../types/testing/assignment'
import { sampleTypes } from '../../types/commissions/registration'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { clientYearRange } from '../../services/common/date'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { parseTableColumns } from '../../services/common/table'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import RegistrationAttachmentManager from '../../components/commissions/RegistrationAttachmentManager.vue'
import TaskProcessingModal from '../../components/testing/TaskProcessingModal.vue'

const title = '检测任务分配', root = '/testing/assignment', route = useRoute(), router = useRouter(), dates = clientYearRange()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const ids = (key: string) => text(key).split(',').filter(Boolean)
const plans = ref(emptyPlanSelection()), planState = ref<PlanSelectionState>()
const drawer = ref(false), planFilter = ref<InstanceType<typeof TestPlanFilterDrawer>>(), planBusy = ref(false), planError = ref<ErrorValue>('')
function applyPlans(value: PlanSelectionState) { plans.value = value.selection; planState.value = value }
const query = computed<AssignmentQuery>(() => ({
  searchField: text('searchField', 'code') as AssignmentQuery['searchField'], contains: text('contains'),
  status: text('status', '任务分配中'), sampleType: text('sampleType'), conclusion: normalizeConclusion(text('conclusion')),
  dateField: text('dateField', 'commissionDate') as AssignmentQuery['dateField'], from: text('from', dates.from), to: text('to', dates.to),
  plans: { groupIds: ids('planGroups'), planIds: ids('planIds'), excludedPlanIds: ids('planExclude') },
  sort: text('sort', 'code') as AssignmentQuery['sort'], direction: text('direction') === 'desc' ? 'desc' : 'asc',
  page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10,
}))
const draft = ref({ searchField: 'code', contains: '', status: '任务分配中', sampleType: '', conclusion: '', dateField: 'commissionDate', ...dates })
const more = ref(false)
const activeFilters = computed(() => Number(!!draft.value.conclusion) + Number(!!(draft.value.from || draft.value.to)))
const dateInput = ref<InstanceType<typeof TemplateDateRange>>()
const emptyPage = (): AssignmentPage => ({ items: [], total: 0, page: 1, pageSize: 10, planSelection: { selection: emptyPlanSelection(), count: 0, total: 0, previews: [], groups: {} } })
const rows = ref<AssignmentPage>(emptyPage()), selected = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>('')
const exporting = ref(false), exportError = ref<ErrorValue>('')
const assignmentTarget = ref<AssignmentRow>(), assignmentBusy = ref(false), assignmentError = ref<ErrorValue>('')
const attachmentId = ref<string>(), processingTarget = ref<AssignmentRow>()
function syncAttachment(updated: { id: string; version: number; attachmentCount: number }) {
  const row = rows.value.items.find(item => item.id === updated.id)
  if (row) { row.version = Math.max(row.version, updated.version); row.attachmentCount = updated.attachmentCount }
}
watch(() => [route.fullPath, currentActor.value.id], () => { attachmentId.value = undefined; processingTarget.value = undefined })
const assignmentUndo = ref(false)
const autoTarget = ref<AssignmentRow>(), autoBusy = ref(false), autoError = ref<ErrorValue>('')
const autoConfirmation = ref<AssignmentRow>()
const autoSuccess = ref(''), successToast = ref<InstanceType<typeof TemplateToast>>()
const taskBusy = computed(() => assignmentBusy.value || autoBusy.value)
const autoNeedsRefresh = computed(() => !!autoError.value && autoError.value.code !== 'VALIDATION')
let actionSequence = 0
function resetAssignment() { actionSequence++; assignmentTarget.value = undefined; assignmentBusy.value = false; assignmentError.value = ''; autoTarget.value = undefined; autoConfirmation.value = undefined; autoBusy.value = false; autoError.value = '' }
function confirmAutomatic() {
  const row = autoConfirmation.value
  if (!row || !row.canAssign || taskBusy.value || loading.value || autoNeedsRefresh.value) return
  autoConfirmation.value = undefined
  void runAutomatic(row)
}
async function runAutomatic(row: AssignmentRow) {
  if (!row.canAssign || taskBusy.value || loading.value) return
  const token = ++actionSequence
  successToast.value?.hide(); autoTarget.value = row; autoError.value = ''; autoBusy.value = true
  try {
    await registrationDemo.autoAssignment(row.id, row.version)
    if (token !== actionSequence) return
    autoSuccess.value = `样品 ${row.code} 自动分配成功`
    await nextTick()
    if (token !== actionSequence) return
    successToast.value?.show()
    await load(true)
  } catch (issue) { if (token === actionSequence) autoError.value = normalizeError(issue) }
  finally { if (token === actionSequence) autoBusy.value = false }
}
function switchToManual() {
  if (!autoTarget.value || taskBusy.value || loading.value || autoNeedsRefresh.value) return
  openAction(autoTarget.value, '分配')
}
function openAction(row: AssignmentRow, label: string) {
  if (loading.value || taskBusy.value || autoNeedsRefresh.value) return
  if (label === '附件管理') { attachmentId.value = row.id; return }
  if (label === '任务处理记录') { processingTarget.value = row; return }
  if (label === '自动分配') { if (row.canAssign) autoConfirmation.value = row; return }
  if (label === '打印任务单') { if (row.canPrintTask) void router.push({ path: `${root}/${encodeURIComponent(row.id)}/print`, query: { returnTo: route.fullPath } }); return }
  if (!['分配', '撤销分配'].includes(label)) return
  if (label === '撤销分配' ? !row.canUndoAssign : !row.canAssign) return
  assignmentUndo.value = label === '撤销分配'
  successToast.value?.hide(); autoTarget.value = undefined; autoError.value = ''
  assignmentError.value = ''; assignmentTarget.value = row
}
async function submitAssignment(submission?: AssignmentSubmission) {
  const target = assignmentTarget.value
  if (!target || taskBusy.value || loading.value) return
  if (assignmentUndo.value ? !target.canUndoAssign : !target.canAssign || !submission) return
  const token = ++actionSequence
  assignmentBusy.value = true; assignmentError.value = ''
  try {
    if (assignmentUndo.value) await registrationDemo.undoAssignment(target.id, target.version)
    else await registrationDemo.assignmentAction(target.id, target.version, submission!)
    if (token !== actionSequence) return
    assignmentTarget.value = undefined
    await load()
  } catch (issue) { if (token === actionSequence) assignmentError.value = normalizeError(issue) }
  finally { if (token === actionSequence) assignmentBusy.value = false }
}
const columnKeys = computed(() => parseTableColumns(assignmentColumns, route.query.columns))
const columns = computed(() => assignmentColumns.filter(column => columnKeys.value.includes(column.key)))
let sequence = 0, exportSequence = 0, controller: AbortController | undefined
async function load(keepSuccess = false) {
  if (!keepSuccess) successToast.value?.hide()
  resetAssignment()
  const token = ++sequence, appliedPlans = JSON.stringify(query.value.plans)
  controller?.abort(); const active = controller = new AbortController()
  loading.value = true; error.value = ''; selected.value = []
  try {
    const result = await registrationDemo.assignmentSamples(query.value, active.signal)
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
  const next = new Set<keyof AssignmentRow>(columnKeys.value)
  if (checked) next.add(key as keyof AssignmentRow); else next.delete(key as keyof AssignmentRow)
  void patch({ columns: [...next].join(',') })
}
async function exportRows(onlySelected: boolean) {
  if (loading.value || error.value || exporting.value || onlySelected && !selected.value.length) return
  const token = ++exportSequence
  exporting.value = true; exportError.value = ''
  try {
    const blob = await registrationDemo.exportAssignmentSamples({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) })
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
  resetAssignment()
  sequence++; controller?.abort(); exportSequence++; exporting.value = false; selected.value = []; rows.value = emptyPage()
  drawer.value = false; planBusy.value = false; planError.value = ''; planState.value = undefined; plans.value = emptyPlanSelection()
  error.value = ''; exportError.value = ''; more.value = false
  const previous = route.fullPath
  await router.replace({ path: root })
  if (previous === route.fullPath) void load()
})
onBeforeUnmount(() => { sequence++; exportSequence++; controller?.abort(); resetAssignment(); successToast.value?.hide() })
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :columns="assignmentColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows">
        <button type="button" class="btn btn-light text-body text-nowrap" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-haspopup="dialog" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}<span v-if="planBusy" class="spinner-border spinner-border-sm ms-1" aria-label="正在更新方案选择"></span></button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}条件`" @submit.prevent="search">
      <QueryFormLayout>
        <div class="row g-3 align-items-end">
          <div class="col-12 col-xl-6">
            <div class="row g-2">
              <div class="col-12 col-sm-5"><label for="assignment-field" class="form-label">查询内容</label><select id="assignment-field" v-model="draft.searchField" class="form-select"><option v-for="field in assignmentSearchFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div>
              <div class="col-12 col-sm-7"><label for="assignment-contains" class="form-label">包含</label><input id="assignment-contains" v-model="draft.contains" class="form-control" maxlength="200" /></div>
            </div>
          </div>
          <div class="col-6 col-xl-3"><label for="assignment-status" class="form-label">数据状态</label><select id="assignment-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in assignmentStates" :key="status">{{ status }}</option></select></div>
          <div class="col-6 col-xl-3"><label for="assignment-type" class="form-label">样品类型</label><select id="assignment-type" v-model="draft.sampleType" class="form-select"><option value="">全部</option><option v-for="type in sampleTypes" :key="type">{{ type }}</option></select></div>
        </div>
      <div v-show="more" id="assignment-more-filters" class="row g-3 align-items-start mt-0">
          <div class="col-12 col-md-4 col-xl-3"><label for="assignment-conclusion" class="form-label">结论状态</label><select id="assignment-conclusion" v-model="draft.conclusion" class="form-select"><option value="">全部</option><option v-for="conclusion in assignmentConclusions" :key="conclusion">{{ conclusion }}</option></select></div>
          <div class="col-12 col-md-8 col-xl-9">
            <label for="assignment-dates" class="form-label">日期</label>
            <div class="row g-2"><div class="col-12 col-sm-4"><select v-model="draft.dateField" class="form-select" aria-label="日期字段"><option v-for="field in assignmentDateFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div><div class="col-12 col-sm-8"><TemplateDateRange id="assignment-dates" ref="dateInput" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div></div>
          </div>
      </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="assignment-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
      <div v-if="planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" type="button" class="btn btn-link btn-sm p-0" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <div v-if="autoBusy" class="px-3 pt-3 d-flex align-items-center gap-2" role="status"><span class="spinner-border spinner-border-sm" aria-hidden="true"></span>样品 {{ autoTarget?.code }} 正在分配…</div>
    <div v-if="autoError" class="px-3 pt-3"><div class="alert alert-warning" role="alert"><p class="mb-2">样品 {{ autoTarget?.code }}：{{ autoError.message }}</p><p v-if="['NETWORK', 'UNAVAILABLE', 'INTERNAL'].includes(autoError.code)" class="mb-2">尚无法确认分配结果，请刷新列表核对最新状态后再操作。</p><button v-if="autoError.code === 'VALIDATION'" type="button" class="btn btn-outline-primary btn-sm" :disabled="taskBusy || loading" @click="switchToManual">手动分配</button><button v-else type="button" class="btn btn-outline-primary btn-sm" :disabled="taskBusy || loading" @click="load()">刷新列表</button></div></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" :actions-disabled="taskBusy || autoNeedsRefresh" preserve-rows-on-loading @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load()">
      <template #cell-attachmentCount="{ row }">{{ row.attachmentCount > 0 ? '有' : '' }}</template>
      <template #actions="{ row }"><button v-for="action in assignmentActions" :key="action.label" type="button" role="menuitem" class="dropdown-item" :disabled="taskBusy || autoNeedsRefresh || ['分配', '自动分配'].includes(action.label) && !row.canAssign || action.label === '撤销分配' && !row.canUndoAssign || action.label === '打印任务单' && !row.canPrintTask" @click="openAction(row, action.label)"><i :class="action.icon" class="me-2 text-muted" aria-hidden="true"></i>{{ action.label }}</button></template>
    </DataTable>
  </section>
  <TestPlanFilterDrawer ref="planFilter" sample-scope="assignment" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
  <TemplateToast ref="successToast" :message="autoSuccess" tone="success" />
  <RegistrationAttachmentManager v-if="attachmentId" :id="attachmentId" kind="samples" @close="attachmentId = undefined" @changed="syncAttachment" />
  <TaskProcessingModal v-if="processingTarget" :row="processingTarget" @close="processingTarget = undefined" />
  <AssignmentModal :row="assignmentTarget" :undo="assignmentUndo" :busy="assignmentBusy" :error="assignmentError" @close="!assignmentBusy && resetAssignment()" @submit="submitAssignment" @undo="submitAssignment()" @refresh="load()" />
  <BootstrapModal :open="!!autoConfirmation" title="自动分配" scrollable @close="autoConfirmation = undefined">
    <template v-if="autoConfirmation">
      <p class="text-break text-muted"><strong>{{ autoConfirmation.code }}</strong> · {{ autoConfirmation.name }}</p>
      <p class="text-break">检测方案：{{ autoConfirmation.projectName || '—' }}</p>
      <p class="mb-0">确认按照检测方案预设人员对该样品执行自动分配？</p>
    </template>
    <template #footer><button type="button" class="btn btn-light" @click="autoConfirmation = undefined">取消</button><button type="button" class="btn btn-primary" :disabled="!autoConfirmation || taskBusy || loading || autoNeedsRefresh" @click="confirmAutomatic">确认</button></template>
  </BootstrapModal>
</template>
