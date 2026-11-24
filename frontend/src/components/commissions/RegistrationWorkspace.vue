<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import RegistrationFilters from '../../components/commissions/RegistrationFilters.vue'
import CommissionAdvancedQueryModal from './CommissionAdvancedQueryModal.vue'
import { commissionAdvancedFields, type CommissionAdvancedDraft } from '../../types/commissions/commissionAdvancedQuery'
import { sampleWorkflowDateFields, sampleConclusions, workflowDateDraft } from '../../types/commissions/sampleWorkflow'
import SampleAdvancedQueryModal from './SampleAdvancedQueryModal.vue'
import { sampleAdvancedFields, type SampleAdvancedDraft } from '../../types/commissions/sampleAdvancedQuery'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import RegistrationReviewModal from '../../components/commissions/RegistrationReviewModal.vue'
import RegistrationAttachmentManager from './RegistrationAttachmentManager.vue'
import RegistrationActionModal from '../../components/commissions/RegistrationActionModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { clearRegistrationListState, isRegistrationChild, restoreRegistrationListState, saveRegistrationListState } from '../../services/commissions/registrationListState'
import { commissionColumns, parseCommissionColumns, sampleColumns, type CommissionColumnKey, type SampleColumnKey } from '../../services/commissions/registrationColumns'
import { inquirySampleColumns, type InquirySampleColumnKey } from '../../services/commissions/inquirySampleColumns'
import { parseTableColumns } from '../../services/common/table'
import { sampleReadOnlyReason, registrationContext, registrationCanWrite, registrationCanLink, registrationCanAddSample, registrationCanReadSamples, workspaceActions, workspaceCanEdit } from '../../services/commissions/registrationService'
import type { TableColumn } from '../../types/common/table'
import { clientYearRange } from '../../services/common/date'
import { currentActor } from '../../stores/session'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import type { RegistrationQuery, RegistrationKind, RegistrationCommission, RegistrationSample, RegistrationSampleRow, RegistrationCommissionRow } from '../../types/commissions/registration'
import { inquirySampleDataStatusOptions } from '../../views/commissions/sampleQueryOptions'
import { commissionSearchFields, sampleSearchFields, inquirySampleSearchFields } from '../../types/commissions/registration'

const props = withDefaults(defineProps<{ review?: boolean; inquiry?: boolean }>(), { review: false, inquiry: false })
const advancedSearchKind = ref<RegistrationKind>()
const advancedBusy = ref(false), advancedError = ref<ErrorValue>('')
let advancedRequest = 0, advancedController: AbortController | undefined, advancedCommitPath = '', advancedActor = ''
let prefetchedCommissions: { query: string; result: Awaited<ReturnType<typeof registrationDemo.commissions>> } | undefined
let prefetchedSamples: { query: string; result: Awaited<ReturnType<typeof registrationDemo.samples>> } | undefined
function closeAdvanced() {
  advancedRequest++; advancedController?.abort(); advancedController = undefined
  advancedBusy.value = false; advancedError.value = ''; advancedSearchKind.value = undefined
  advancedCommitPath = ''; prefetchedCommissions = undefined; prefetchedSamples = undefined
}
const context = registrationContext(props.inquiry ? '/commissions/query' : props.review ? '/commissions/review' : '/commissions/registration')
const registrationDataStatusOptions = [{ value: '', label: '全部状态' }, { value: '委托登记中', label: '委托登记中' }, { value: '完成登记', label: '完成登记' }]
const reviewDataStatusOptions = [{ value: '', label: '全部' }, { value: '合同评审中', label: '合同评审中' }, { value: '评审完成', label: '合同评审完成' }]
const registrationRoot = context.root
const route = useRoute(), router = useRouter()
const attachmentId = ref<string>(), attachmentKind = ref<RegistrationKind>('commissions')
function openAttachments(kind: RegistrationKind, id: string) { attachmentKind.value = kind; attachmentId.value = id }
watch(() => [route.fullPath, currentActor.value], () => { attachmentId.value = undefined })
const defaultDates = clientYearRange()
const value = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
function query(prefix: string): RegistrationQuery {
  const common = { sort: value(`${prefix}Sort`, 'createdAt'), direction: value(`${prefix}Direction`, 'desc'), page: Number(value(`${prefix}Page`, '1')), pageSize: Number(value(`${prefix}Size`, prefix === 'c' ? '5' : '10')) }
  if (prefix === 's') {
    const searchField = (props.inquiry ? inquirySampleSearchFields : sampleSearchFields).find(field => field.value === value('sSearchField'))?.value
    if (props.inquiry) {
      const from = value('sCommissionFrom'), to = value('sCommissionTo')
      const legacyOwner = !value('sSearchField') ? value('sOwner') : ''
      return { ...common, keyword: value('sKeyword'), searchField: searchField || (legacyOwner ? 'owner' : inquirySampleSearchFields[0].value),
        contains: searchField ? value('sContains') : legacyOwner, dataStatus: value('sDataStatus'), sampleType: value('sSampleType'),
        commissionFrom: from && to ? from : defaultDates.from, commissionTo: from && to ? to : defaultDates.to }
    }
    const legacy = { sampleCode: value('sCode', value('sKeyword')), reportCode: value('sReportCode'), owner: value('sOwner') }
    const first = !searchField ? (['sampleCode', 'reportCode', 'owner'] as const).find(key => legacy[key]) : undefined
    const contains = first ? legacy[first] : value('sContains')
    if (first) legacy[first] = ''
    const from = value('sCommissionFrom'), to = value('sCommissionTo')
    const dataStatus = value('sDataStatus')
    return { ...common, ...legacy, searchField: searchField || (first === 'sampleCode' ? 'code' : first) || 'all', contains,
      dataStatus: props.review || props.inquiry || registrationDataStatusOptions.some(option => option.value === dataStatus) ? dataStatus : '', sampleType: value('sSampleType'),
      commissionFrom: from && to ? from : defaultDates.from, commissionTo: from && to ? to : defaultDates.to }
  }
  const searchField = commissionSearchFields.find(field => field.value === value('cSearchField'))?.value || 'all'
  const contains = value('cSearchField') === 'contract' ? '' : value('cContains')
  const legacyCode = value('cCode', value('cKeyword'))
  const from = value('cFrom'), to = value('cTo')
  const dates = from && to ? { from, to } : defaultDates
  // Old combined links retain their extra number condition visibly; number-only links use the new selector.
  return { ...common, commissionCode: contains && legacyCode ? legacyCode : undefined, contains: contains || legacyCode, searchField: !contains && legacyCode ? 'code' : searchField, status: value('cStatus'), ...dates, category: value('cCategory') }
}

const basicCommissionQuery = computed(() => query('c'))
const usingAdvancedCommission = computed(() => props.inquiry && value('cQueryMode') === 'advanced')
const advancedCommissionDraft = computed<CommissionAdvancedDraft>(() => ({
  fields: Object.fromEntries(commissionAdvancedFields.map(({ key }) => [key, value(`ca${key[0]!.toUpperCase()}${key.slice(1)}`)])),
  status: value('caStatus'), useDate: value('caUseDate') === '1', from: value('caFrom') || defaultDates.from, to: value('caTo') || defaultDates.to,
}))
function commissionAdvancedConditions(draft: CommissionAdvancedDraft, page = basicCommissionQuery.value.page): RegistrationQuery {
  const { pageSize, sort, direction } = basicCommissionQuery.value
  return { page, pageSize, sort, direction, commissionAdvanced: { ...draft.fields }, ...(draft.status ? { status: draft.status } : {}), ...(draft.useDate ? { from: draft.from, to: draft.to } : {}) }
}
const commissionQuery = computed<RegistrationQuery>(() => usingAdvancedCommission.value ? commissionAdvancedConditions(advancedCommissionDraft.value) : basicCommissionQuery.value)
async function searchAdvancedCommission(draft: CommissionAdvancedDraft) {
  const next: Record<string, string | undefined> = { cQueryMode: 'advanced', cPage: '1', current: undefined, sPage: '1', caStatus: draft.status || undefined, caUseDate: draft.useDate ? '1' : undefined, caFrom: draft.from, caTo: draft.to }
  for (const { key } of commissionAdvancedFields) next[`ca${key[0]!.toUpperCase()}${key.slice(1)}`] = draft.fields[key] || undefined
  await submitAdvanced('commissions', commissionAdvancedConditions(draft, 1), next)
}
const selectedCommissions = computed(() => [...new Set(value('current').split(',').filter(Boolean))])
const currentId = computed(() => selectedCommissions.value.length === 1 ? selectedCommissions.value[0]! : '')
const scope = computed(() => value('scope') === 'all' ? 'all' : 'current')
const sampleCommissionId = computed(() => scope.value === 'current' ? currentId.value : '')
const sampleReady = computed(() => scope.value === 'all' || selectedCommissions.value.length > 0)
const currentCaption = computed(() => selectedCommissions.value.length > 1 ? `已选 ${selectedCommissions.value.length} 张委托` : current.value ? `${current.value.code} · ${current.value.name}` : '')
const basicSampleQuery = computed(() => query('s'))
const usingAdvancedSample = computed(() => props.inquiry && value('sQueryMode') === 'advanced')
const advancedSampleDraft = computed<SampleAdvancedDraft>(() => ({
  fields: Object.fromEntries(sampleAdvancedFields.map(({ key }) => [key, value(`sa${key[0]!.toUpperCase()}${key.slice(1)}`)])),
  dataStatus: value('saDataStatus'), sampleType: value('saSampleType'),
  conclusion: sampleConclusions.find(option => option.value === value('saConclusion'))?.value || '',
  workflowDates: Object.assign(workflowDateDraft(defaultDates), Object.fromEntries(sampleWorkflowDateFields.map(({ key }) => {
    const prefix = `sa${key[0]!.toUpperCase()}${key.slice(1)}`
    return [key, { enabled: value(`${prefix}Enabled`) === '1', from: value(`${prefix}From`) || defaultDates.from, to: value(`${prefix}To`) || defaultDates.to }]
  }))),
  useDate: value('saUseDate') === '1', from: value('saFrom') || defaultDates.from, to: value('saTo') || defaultDates.to,
}))
function sampleAdvancedConditions(draft: SampleAdvancedDraft, page = basicSampleQuery.value.page): RegistrationQuery {
  const { pageSize, sort, direction } = basicSampleQuery.value
  const workflowDates = Object.fromEntries(sampleWorkflowDateFields.filter(({ key }) => draft.workflowDates[key].enabled).map(({ key }) => [key, { from: draft.workflowDates[key].from, to: draft.workflowDates[key].to }]))
  const workflow = { ...(Object.keys(workflowDates).length ? { dates: workflowDates } : {}), ...(draft.conclusion ? { conclusion: draft.conclusion } : {}) }
  const conditions = {
    page, pageSize, sort, direction, sampleAdvanced: { ...draft.fields },
    ...(Object.keys(workflow).length ? { sampleWorkflow: workflow } : {}),
    ...(draft.dataStatus ? { dataStatus: draft.dataStatus } : {}), ...(draft.sampleType ? { sampleType: draft.sampleType } : {}),
    ...(draft.useDate ? { commissionFrom: draft.from, commissionTo: draft.to } : {}),
  }
  return { ...conditions, ...(scope.value === 'current' ? { commissionIds: selectedCommissions.value } : {}) }
}
const sampleQuery = computed<RegistrationQuery>(() => usingAdvancedSample.value ? sampleAdvancedConditions(advancedSampleDraft.value) : { ...basicSampleQuery.value, ...(scope.value === 'current' ? { commissionIds: selectedCommissions.value } : {}) })
async function searchAdvancedSample(draft: SampleAdvancedDraft) {
  const next: Record<string, string | undefined> = { sQueryMode: 'advanced', sPage: '1',
    saDataStatus: draft.dataStatus || undefined, saSampleType: draft.sampleType || undefined, saConclusion: draft.conclusion || undefined,
    saUseDate: draft.useDate ? '1' : undefined, saFrom: draft.from, saTo: draft.to }
  for (const { key } of sampleAdvancedFields) next[`sa${key[0]!.toUpperCase()}${key.slice(1)}`] = draft.fields[key] || undefined
  for (const { key } of sampleWorkflowDateFields) {
    const prefix = `sa${key[0]!.toUpperCase()}${key.slice(1)}`, range = draft.workflowDates[key]
    next[`${prefix}Enabled`] = range.enabled ? '1' : undefined
    next[`${prefix}From`] = range.from; next[`${prefix}To`] = range.to
  }
  await submitAdvanced('samples', sampleAdvancedConditions(draft, 1), next)
}
// Fetch before committing URL conditions. A failed attempt leaves the existing list and modal draft intact.
async function submitAdvanced(kind: RegistrationKind, query: RegistrationQuery, next: Record<string, string | undefined>) {
  if (advancedBusy.value || advancedSearchKind.value !== kind) return
  const token = ++advancedRequest, previous = route.fullPath
  const controller = advancedController = new AbortController()
  advancedActor = currentActor.value.id; advancedBusy.value = true; advancedError.value = ''
  const active = () => token === advancedRequest && !controller.signal.aborted && currentActor.value.id === advancedActor
  try {
    if (kind === 'commissions') {
      const result = await registrationDemo.commissions(query, controller.signal)
      if (!active() || route.fullPath !== previous) return
      prefetchedCommissions = { query: JSON.stringify(query), result }
    } else {
      const result = await registrationDemo.samples(query, controller.signal, context.workspace)
      if (!active() || route.fullPath !== previous) return
      prefetchedSamples = { query: JSON.stringify(query), result }
    }
    advancedCommitPath = router.resolve({ path: registrationRoot, query: { ...route.query, ...next, savedSample: undefined } }).fullPath
    await patch(next)
    if (!active()) return
    if (route.fullPath !== advancedCommitPath) throw new Error('查询结果未能应用，请重试。')
    // Unchanged effective conditions do not trigger a watcher; consume any remaining response explicitly.
    if (kind === 'commissions' && prefetchedCommissions) await loadCommissions()
    if (kind === 'samples' && prefetchedSamples) await loadSamples()
    closeAdvanced()
  } catch (error) {
    if (active()) advancedError.value = normalizeError(error)
  } finally {
    if (token === advancedRequest) {
      advancedBusy.value = false; advancedController = undefined; advancedCommitPath = ''
      prefetchedCommissions = undefined; prefetchedSamples = undefined
    }
  }
}
const collapsed = computed(() => value('collapsed') === '1')
const columnKeys = computed(() => parseCommissionColumns(route.query.cColumns, route.query.contractColumn))
const visibleColumns = computed(() => commissionColumns.filter(column => columnKeys.value.includes(column.key)))
function toggleColumn(key: CommissionColumnKey, checked: boolean) {
  if ((commissionColumns.find(column => column.key === key) as TableColumn | undefined)?.required) return
  const next = new Set(columnKeys.value)
  if (checked) next.add(key); else next.delete(key)
  void router.push({ path: registrationRoot, query: { ...route.query, cColumns: commissionColumns.filter(column => next.has(column.key)).map(column => column.key).join(','), contractColumn: undefined } })
}
function resetColumns() { void router.push({ path: registrationRoot, query: { ...route.query, cColumns: undefined, contractColumn: undefined } }) }
type WorkspaceSampleColumnKey = SampleColumnKey | InquirySampleColumnKey
const availableSampleColumns = computed<readonly TableColumn<WorkspaceSampleColumnKey>[]>(() => props.inquiry ? inquirySampleColumns : sampleColumns)
const sampleColumnKeys = computed(() => parseTableColumns(availableSampleColumns.value, route.query.sColumns))
const visibleSampleColumns = computed(() => availableSampleColumns.value.filter(column => sampleColumnKeys.value.includes(column.key)))
function toggleSampleColumn(key: WorkspaceSampleColumnKey, checked: boolean) {
  if (availableSampleColumns.value.find(column => column.key === key)?.required) return
  const next = new Set(sampleColumnKeys.value)
  if (checked) next.add(key); else next.delete(key)
  void router.push({ path: registrationRoot, query: { ...route.query, sColumns: availableSampleColumns.value.filter(column => next.has(column.key)).map(column => column.key).join(',') } })
}
function resetSampleColumns() { void router.push({ path: registrationRoot, query: { ...route.query, sColumns: undefined } }) }
const commissions = ref<Awaited<ReturnType<typeof registrationDemo.commissions>>>({ items: [], total: 0, page: 1, pageSize: 5 })
const samples = ref<Awaited<ReturnType<typeof registrationDemo.samples>>>({ items: [], total: 0, page: 1, pageSize: 10 })
const current = ref<RegistrationCommissionRow>(), currentError = ref<ErrorValue>('')
const cError = ref<ErrorValue>(''), sError = ref<ErrorValue>(''), operationError = ref<ErrorValue>(''), cLoading = ref(false), sLoading = ref(false), exporting = ref(false)
const selectedSamples = ref<string[]>([]), notice = ref('')
const actionKind = ref<RegistrationKind>('commissions'), actionRecord = ref<RegistrationCommission | RegistrationSample>(), actionSelection = ref('')
let cRequest = 0, sRequest = 0, currentRequest = 0, actionRequest = 0
let cController: AbortController | undefined, sController: AbortController | undefined, currentController: AbortController | undefined
const actionLoading = ref(false)
const restored = context.workspace === 'registration' ? restoreRegistrationListState(route.fullPath) : undefined
if (restored) {
  commissions.value = restored.commissions; samples.value = restored.samples; current.value = restored.current
  selectedSamples.value = restored.selectedSamples
}
onBeforeRouteLeave((to, from) => {
  if (context.workspace !== 'registration') return
  if (!isRegistrationChild(to.path)) { clearRegistrationListState(); return }
  saveRegistrationListState({ url: from.fullPath, commissions: commissions.value, samples: samples.value, current: current.value,
    selectedSamples: selectedSamples.value,
    scroll: { left: window.scrollX, top: window.scrollY } })
})
const quickReviewRecord = ref<RegistrationSample>(), quickReviewLoading = ref(false)
const quickReviewRecords = ref<RegistrationSample[]>()
let quickReviewRequest = 0
const canQuickReview = computed(() => props.review && registrationCanWrite(currentActor.value, 'samples') && sampleReady.value && !sLoading.value && !sError.value && !actionLoading.value && !quickReviewLoading.value && selectedSamples.value.length > 0 && selectedSamples.value.length <= 50 && selectedSamples.value.every(id => samples.value.items.some(row => row.id === id)))
async function openQuickReview() {
  if (!canQuickReview.value) return
  const selectedId = selectedSamples.value[0]!, token = ++quickReviewRequest
  quickReviewLoading.value = true; operationError.value = ''
  try {
    if (selectedSamples.value.length > 1) {
      const targets = selectedSamples.value.map(id => { const row = samples.value.items.find(row => row.id === id)!; return { id, version: row.version } })
      const records = await registrationDemo.startBatchReview(targets)
      if (token === quickReviewRequest) quickReviewRecords.value = records
      return
    }
    const detail = await registrationDemo.sample(selectedId)
    if (token !== quickReviewRequest) return
    const started = await registrationDemo.act('samples', detail.id, 'start-review', detail.version)
    if (token !== quickReviewRequest) return
    quickReviewRecord.value = Object.assign(detail, started)
  } catch (e) { if (token === quickReviewRequest) operationError.value = normalizeError(e) }
  finally { if (token === quickReviewRequest) quickReviewLoading.value = false }
}
function closeQuickReview() {
  if (!quickReviewRecord.value && !quickReviewRecords.value) return
  quickReviewRecord.value = undefined; quickReviewRecords.value = undefined
  refresh()
}
watch(() => JSON.stringify([selectedSamples.value, route.fullPath, currentActor.value.id]), () => {
  quickReviewRequest++; quickReviewLoading.value = false; quickReviewRecord.value = undefined; quickReviewRecords.value = undefined
})

watch(() => JSON.stringify([route.fullPath, currentActor.value.id]), () => {
  if (route.fullPath !== advancedCommitPath || currentActor.value.id !== advancedActor) closeAdvanced()
})
onBeforeUnmount(closeAdvanced)
const canReadSamples = computed(() => registrationCanReadSamples(currentActor.value))
const canAddSample = computed(() => registrationCanLink(currentActor.value) && (scope.value === 'all' || selectedCommissions.value.length === 1 && !!current.value && registrationCanAddSample(currentActor.value, current.value.status)))
const bulkSelectionError = computed(() => {
  const rows = samples.value.items.filter(row => selectedSamples.value.includes(row.id))
  if (!rows.length) return '请先勾选需要修改的样品'
  if (!rows[0]!.commissionId || rows.some(row => row.commissionId !== rows[0]!.commissionId)) return '只能批量修改同一委托单下的样品'
  if (rows.some(row => !workspaceCanEdit(currentActor.value, 'samples', row, context.workspace))) return context.review ? '请仅选择尚未评审且未作废的样品' : '请仅选择未完成的样品'
  return ''
})
function openBulk() { if (!bulkSelectionError.value) void router.push({ path: `${registrationRoot}/samples/bulk-edit`, query: { ids: selectedSamples.value.join(','), returnTo: route.fullPath } }) }
const sampleToolbarActions = computed(() => !props.inquiry && registrationCanWrite(currentActor.value, 'samples') ? [{
  label: selectedSamples.value.length ? `批量修改（${selectedSamples.value.length}）` : '批量修改', icon: 'ti ti-edit',
  disabled: !!bulkSelectionError.value || sLoading.value || !!sError.value,
  hint: bulkSelectionError.value || '批量修改所选样品的委托信息',
}] : [])
function patch(changes: Record<string, string | undefined>) {
  const changesCommissionQuery = Object.keys(changes).some(key => /^c(?:QueryMode|Code|Contains|SearchField|Keyword|Status|From|To|Customer|Owner|Contract|Category|Sort|Direction|Page|Size)$/.test(key) && (key === 'cFrom' ? (changes[key] ?? defaultDates.from) !== commissionQuery.value.from : key === 'cTo' ? (changes[key] ?? defaultDates.to) !== commissionQuery.value.to : changes[key] !== value(key)))
  return router.push({ path: registrationRoot, query: { ...route.query, ...changes, ...(changesCommissionQuery ? { current: undefined, sPage: '1' } : {}), savedSample: undefined } })
}
async function search(prefix: string, q: RegistrationQuery) {
  const previous = route.fullPath
  const next: Record<string, string | undefined> = { [`${prefix}Page`]: '1' }
  for (const key of ['contains', 'searchField', 'keyword', 'status', 'from', 'to', 'customer', 'contract', 'owner', 'category'] as const) next[`${prefix}${key[0]!.toUpperCase()}${key.slice(1)}`] = q[key] || undefined
  if (prefix === 'c') {
    next.cQueryMode = undefined
    next.cCode = q.commissionCode || undefined; next.cKeyword = undefined; next.cAdvanced = undefined
    // The range is mandatory for list searches; legacy empty boundaries use the last calendar year.
    next.cFrom = q.from && q.to ? q.from : defaultDates.from; next.cTo = q.from && q.to ? q.to : defaultDates.to
  } else {
    next.sQueryMode = undefined
    next.sCode = q.sampleCode || undefined; next.sKeyword = props.inquiry ? q.keyword || undefined : undefined; next.sAdvanced = undefined
    next.sReportCode = q.reportCode || undefined; next.sDataStatus = q.dataStatus || undefined; next.sSampleType = q.sampleType || undefined
    next.sCommissionFrom = q.commissionFrom && q.commissionTo ? q.commissionFrom : defaultDates.from; next.sCommissionTo = q.commissionFrom && q.commissionTo ? q.commissionTo : defaultDates.to
  }
  await patch(next)
  if (route.fullPath === previous) { if (prefix === 'c') void loadCommissions(); else void loadSamples() }
}
function sort(prefix: string, key: string) { const q = prefix === 'c' ? commissionQuery.value : sampleQuery.value; void patch({ [`${prefix}Sort`]: key, [`${prefix}Direction`]: q.sort === key && q.direction === 'asc' ? 'desc' : 'asc', [`${prefix}Page`]: '1' }) }
function selectCommissions(ids: string[]) { void patch({ current: ids.length ? [...new Set(ids)].join(',') : undefined, scope: undefined, sPage: '1' }) }
function showSamples(id: string) { selectCommissions(id ? [id] : []) }
function selectCommissionRow(id: string) {
  // Keep multi-selection, sample selection, scope and pagination on repeated row clicks.
  if (!selectedCommissions.value.includes(id)) showSamples(id)
}
function changeScope(next: 'current' | 'all') { void patch({ scope: next === 'all' ? 'all' : undefined, sPage: '1' }) }
function link(kind: RegistrationKind, id: string, edit = false) { return { path: `${registrationRoot}/${kind}/${id}${edit ? '/edit' : ''}`, query: { returnTo: route.fullPath, ...(id === 'new' && kind === 'samples' && scope.value === 'current' ? sampleCommissionId.value ? { commissionId: sampleCommissionId.value } : { commissionIds: selectedCommissions.value.join(',') } : {}) } } }
function addSampleLink(id: string) { return { path: `${registrationRoot}/samples/new`, query: { commissionId: id, returnTo: route.fullPath } } }
async function openActions(kind: RegistrationKind, row: { id: string }, actionId: string) {
  const token = ++actionRequest; actionLoading.value = true; operationError.value = ''
  try { const detail = kind === 'commissions' ? await registrationDemo.commission(row.id) : await registrationDemo.sample(row.id); if (token === actionRequest) { actionKind.value = kind; actionSelection.value = actionId; actionRecord.value = detail } }
  catch (e) { if (token === actionRequest) operationError.value = normalizeError(e) } finally { if (token === actionRequest) actionLoading.value = false }
}
async function loadCurrent() {
  currentController?.abort(); const controller = currentController = new AbortController()
  const token = ++currentRequest; currentError.value = ''
  if (current.value?.id !== currentId.value) current.value = undefined
  if (!currentId.value) return
  try { const result = await registrationDemo.commissionSummary(currentId.value, controller.signal); if (token === currentRequest) current.value = result }
  catch (e) { if (token === currentRequest && !controller.signal.aborted) currentError.value = normalizeError(e) }
}
async function loadCommissions() {
  const token = ++cRequest; cLoading.value = true; cError.value = ''
  cController?.abort(); const controller = cController = new AbortController()
  const cached = prefetchedCommissions; prefetchedCommissions = undefined
  try { const result = cached?.query === JSON.stringify(commissionQuery.value) ? cached.result : await registrationDemo.commissions(commissionQuery.value, controller.signal); if (token === cRequest) commissions.value = result }
  catch (e) { if (token === cRequest && !controller.signal.aborted) { cError.value = normalizeError(e); commissions.value.items = [] } }
  finally { if (token === cRequest) cLoading.value = false }
}
async function loadSamples() {
  const token = ++sRequest; sError.value = ''; notice.value = ''
  // Keep the previous rows' space while loading so the document does not shrink
  // and clamp the user's scroll position. Old rows are dimmed and cannot be operated.
  sController?.abort(); const controller = sController = new AbortController()
  if (!canReadSamples.value || !sampleReady.value) { samples.value = { items: [], total: 0, page: 1, pageSize: 10 }; sLoading.value = false; return }
  sLoading.value = true
  try {
    const cached = prefetchedSamples; prefetchedSamples = undefined
    const result = cached?.query === JSON.stringify(sampleQuery.value) ? cached.result : await registrationDemo.samples(sampleQuery.value, controller.signal, context.workspace)
    if (token !== sRequest) return
    samples.value = result; selectedSamples.value = selectedSamples.value.filter(id => result.items.some(r => r.id === id && !sampleReadOnlyReason(r.status)))
    if (value('savedSample')) { const matches = await registrationDemo.samples({ ...sampleQuery.value, ids: [value('savedSample')] }, controller.signal, context.workspace); if (token === sRequest) notice.value = matches.total ? '' : '样品已保存，但不符合当前筛选条件。筛选条件已保留。' }
  } catch (e) { if (token === sRequest && !controller.signal.aborted) { sError.value = normalizeError(e); samples.value.items = []; selectedSamples.value = [] } }
  finally { if (token === sRequest) sLoading.value = false }
}
function syncAttachmentVersion(updated: Pick<RegistrationCommission, 'id' | 'version'> & { kind: RegistrationKind; attachmentCount: number }) {
  // Attachment writes only change attachments, audit events and the record version.
  const row = (updated.kind === 'samples' ? samples.value.items : commissions.value.items).find(item => item.id === updated.id)
  if (row) row.version = Math.max(row.version, updated.version)
  if (updated.kind === 'samples' && row && 'attachmentCount' in row) row.attachmentCount = updated.attachmentCount
  if (updated.kind === 'commissions' && current.value?.id === updated.id) current.value.version = Math.max(current.value.version, updated.version)
}
function refresh() { void loadCommissions(); void loadSamples(); void loadCurrent() }
async function exportData(kind: RegistrationKind, selected: boolean) {
  if (exporting.value) return
  exporting.value = true; operationError.value = ''
  try { const q = kind === 'commissions' ? commissionQuery.value : sampleQuery.value; const ids = kind === 'commissions' ? selectedCommissions.value : selectedSamples.value; downloadBlob(await registrationDemo.export(kind, selected ? { ids: [...ids], ...(kind === 'samples' && scope.value === 'current' ? { commissionIds: selectedCommissions.value } : {}) } : q, context.workspace), `${kind === 'commissions' ? '委托' : '样品'}-${selected ? '已选记录' : '查询结果'}-演示.csv`) }
  catch (e) { operationError.value = normalizeError(e) } finally { exporting.value = false }
}
watch(() => JSON.stringify(commissionQuery.value), loadCommissions, { immediate: true })
watch(() => JSON.stringify([sampleQuery.value, scope.value, value('savedSample')]), (_, previous) => {
  if (previous !== undefined) selectedSamples.value = []
  void loadSamples()
}, { immediate: true })
watch(currentId, loadCurrent, { immediate: true })
watch(currentActor, async () => {
  cRequest++; sRequest++; currentRequest++; actionRequest++
  cController?.abort(); sController?.abort(); currentController?.abort()
  commissions.value.items = []; samples.value.items = []; current.value = undefined; selectedSamples.value = []; actionRecord.value = undefined; operationError.value = ''; notice.value = ''
  await router.replace({ path: registrationRoot }); refresh()
})
onBeforeUnmount(() => { quickReviewRequest++; cRequest++; sRequest++; currentRequest++; actionRequest++; cController?.abort(); sController?.abort(); currentController?.abort() })
</script>

<template>
  <PageHeading :title="context.title" />
  <ErrorNotice :error="operationError" />
  <section class="card" aria-label="委托列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">委托</h5><span class="badge bg-primary-subtle text-body">{{ commissions.total }}</span><button class="btn btn-sm btn-light" :aria-expanded="!collapsed" aria-controls="commission-body" @click="patch({ collapsed: collapsed ? undefined : '1' })">{{ collapsed ? '展开委托' : '收起委托' }}</button></div>
      <TableToolbar label="委托" :columns="commissionColumns" :selected="columnKeys" :count="selectedCommissions.length" :export-disabled="exporting || cLoading || !!cError" @column="(key, checked) => toggleColumn(key as CommissionColumnKey, checked)" @reset="resetColumns" @export="exportData('commissions', $event)">
        <RouterLink v-if="!inquiry && !review && registrationCanWrite(currentActor, 'commissions')" class="btn btn-primary text-nowrap px-2" :to="link('commissions', 'new')"><i class="ti ti-plus me-1 d-none d-sm-inline-block" aria-hidden="true"></i>新增委托</RouterLink>
      </TableToolbar>
    </div>
    <div v-if="collapsed && currentCaption" class="card-body"><p class="mb-0 text-break">{{ currentCaption }}</p></div>
    <div id="commission-body" class="collapse" :class="{ show: !collapsed }">
      <RegistrationFilters kind="commissions" :show-advanced-search="inquiry" @advanced-search="advancedSearchKind = 'commissions'" :query="basicCommissionQuery" :advanced-active="usingAdvancedCommission" @search="search('c', $event)" />
      <DataTable label="委托" :rows="commissions.items" :columns="visibleColumns" :row-key="row => row.id" :row-label="row => row.code"
        :selected="selectedCommissions" highlight-selected :sort-key="commissionQuery.sort" :direction="commissionQuery.direction"
        :pagination="{ ...commissions, sizes: [5, 10, 20] }" :loading="cLoading" :error="cError" preserve-rows-on-loading :actions-disabled="actionLoading"
        @update:selected="selectCommissions" @row-click="row => selectCommissionRow(row.id)" @sort="sort('c', $event)" @retry="loadCommissions"
        @page="patch({ cPage: String($event) })" @size="patch({ cSize: String($event), cPage: '1' })">
        <template #cell-code="{ row }"><RouterLink class="fw-medium" :to="link('commissions', row.id)">{{ row.code }}</RouterLink></template>
        <template #cell-status="{ text }"><span class="badge bg-primary-subtle text-body">{{ text }}</span></template>
        <template #actions="{ row }">
            <RouterLink class="dropdown-item" role="menuitem" :to="link('commissions', row.id)"><i class="ti ti-eye align-bottom me-2 text-muted" aria-hidden="true"></i>查看</RouterLink>
            <template v-if="!review">
            <button v-if="!row.sampleCount" class="dropdown-item" role="menuitem" disabled title="该委托下暂无样品，无法打印"><i class="ti ti-printer align-bottom me-2 text-muted" aria-hidden="true"></i>打印</button>
            <RouterLink v-else class="dropdown-item" role="menuitem" :to="{ path: `${registrationRoot}/commissions/${row.id}/print`, query: { returnTo: route.fullPath } }"><i class="ti ti-printer align-bottom me-2 text-muted" aria-hidden="true"></i>打印</RouterLink>
            </template>
            <RouterLink v-if="workspaceCanEdit(currentActor, 'commissions', row, context.workspace)" class="dropdown-item" role="menuitem" :to="link('commissions', row.id, true)"><i class="ti ti-pencil align-bottom me-2 text-muted" aria-hidden="true"></i>{{ review ? '编辑' : '修改' }}</RouterLink>
            <button v-if="!inquiry && !workspaceCanEdit(currentActor, 'commissions', row, context.workspace)" class="dropdown-item" role="menuitem" disabled :title="!registrationCanWrite(currentActor, 'commissions') ? '当前身份无权操作' : '请先取消完成再编辑'"><i class="ti ti-pencil align-bottom me-2 text-muted" aria-hidden="true"></i>{{ review ? '编辑' : '修改' }}</button>
            <RouterLink v-if="!inquiry && !review && registrationCanAddSample(currentActor, row.status)" class="dropdown-item" role="menuitem" :to="addSampleLink(row.id)"><i class="ti ti-circle-plus align-bottom me-2 text-muted" aria-hidden="true"></i>新增样品</RouterLink>
            <button v-if="!inquiry && !review && !registrationCanAddSample(currentActor, row.status)" class="dropdown-item" role="menuitem" disabled :title="!registrationCanLink(currentActor) ? '当前身份无权新增样品' : '请先取消完成再新增样品'"><i class="ti ti-circle-plus align-bottom me-2 text-muted" aria-hidden="true"></i>新增样品</button>
            <template v-if="workspaceActions(currentActor, 'commissions', row, context.workspace).length"><div class="dropdown-divider" role="separator"></div><button v-for="item in workspaceActions(currentActor, 'commissions', row, context.workspace)" :key="item.id" class="dropdown-item" :class="{ 'text-danger': item.id === 'cancel' }" role="menuitem" :disabled="item.disabled" :title="item.disabledReason" @click="openActions('commissions', row, item.id)"><i class="align-bottom me-2 text-muted" :class="item.id === 'complete' ? 'ti ti-circle-check' : 'ti ti-arrow-back-up'" aria-hidden="true"></i>{{ item.label }}</button></template>
            <button class="dropdown-item" role="menuitem" @click="openAttachments('commissions', row.id)"><i class="ti ti-paperclip align-bottom me-2 text-muted" aria-hidden="true"></i>附件管理</button>
                  </template>
        <template #empty><p class="mt-2 mb-0">暂无符合条件的委托</p><button class="btn btn-link" @click="search('c', {})">清空筛选条件</button></template>
      </DataTable>
    </div>
  </section>
  <section class="card" aria-label="样品列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">样品</h5><span v-if="canReadSamples && sampleReady && !sLoading && !sError" class="badge bg-primary-subtle text-body">{{ samples.total }}</span><span v-if="canReadSamples" class="spinner-border spinner-border-sm text-primary" :class="{ invisible: !sLoading }" :aria-hidden="!sLoading" role="status" aria-label="正在加载样品"></span></div>
      <TableToolbar v-if="canReadSamples" label="样品" :adaptive-actions="sampleToolbarActions" @action="openBulk" :columns="availableSampleColumns" :selected="sampleColumnKeys" :count="selectedSamples.length" :export-disabled="exporting || sLoading || !!sError || !sampleReady || scope === 'current' && selectedCommissions.length === 1 && !current" @column="(key, checked) => toggleSampleColumn(key as WorkspaceSampleColumnKey, checked)" @reset="resetSampleColumns" @export="exportData('samples', $event)">
        <button v-if="review && registrationCanWrite(currentActor, 'samples')" class="btn btn-primary text-nowrap px-2" :disabled="!canQuickReview" :aria-busy="quickReviewLoading" :title="!selectedSamples.length ? '请勾选样品（最多 50 个）' : '快速评审所选样品'" @click="openQuickReview"><span v-if="quickReviewLoading" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span><i v-else class="ti ti-clipboard-list align-bottom me-1" aria-hidden="true"></i>快速评审</button>
        <button v-if="!inquiry && !review" type="button" class="btn btn-primary text-nowrap px-2" :disabled="!canAddSample" @click="canAddSample && router.push(link('samples', 'new'))"><i class="ti ti-plus me-1 d-none d-sm-inline-block" aria-hidden="true"></i>新增样品</button>
      </TableToolbar>
    </div>
    <div v-if="!canReadSamples" class="card-body text-muted">当前身份没有查看样品的权限。</div>
    <template v-else>
      <div class="d-flex flex-wrap align-items-center gap-3 px-3 border-bottom">
        <div class="nav nav-tabs nav-tabs-custom border-bottom-0" role="tablist" aria-label="样品范围">
          <button id="samples-current-tab" class="nav-link" :class="{ active: scope === 'current' }" role="tab" :aria-selected="scope === 'current'" aria-controls="samples-panel" @click="changeScope('current')">当前委托</button>
          <button id="samples-all-tab" class="nav-link" :class="{ active: scope === 'all' }" role="tab" :aria-selected="scope === 'all'" aria-controls="samples-panel" @click="changeScope('all')">全部样品</button>
        </div>
        <span v-if="scope === 'current' && currentCaption" class="text-muted small text-break py-2">{{ currentCaption }}</span>
      </div>
      <div id="samples-panel" role="tabpanel" :aria-labelledby="scope === 'all' ? 'samples-all-tab' : 'samples-current-tab'">
        <div v-if="!sampleReady" class="text-center py-5"><i class="ti ti-file-description display-5 text-muted" aria-hidden="true"></i><h5 class="mt-3">请选择委托</h5><p class="text-muted">勾选上方委托，查看关联样品。</p></div>
        <template v-else>
          <div v-if="scope === 'current' && currentError" class="px-3 pt-3"><ErrorNotice :error="currentError" retry @retry="loadCurrent" /></div>
        <RegistrationFilters kind="samples" :sample-search-fields="inquiry ? inquirySampleSearchFields : sampleSearchFields" :show-advanced-search="inquiry" @advanced-search="advancedSearchKind = 'samples'" :data-status-options="inquiry ? inquirySampleDataStatusOptions : review ? reviewDataStatusOptions : registrationDataStatusOptions" :query="basicSampleQuery" :advanced-active="usingAdvancedSample" @search="search('s', $event)" />
          <div v-if="notice" class="alert alert-info m-3" role="status">{{ notice }}</div>
          <DataTable label="样品" :rows="samples.items" :columns="visibleSampleColumns" :row-key="row => row.id" :row-label="row => row.code"
            v-model:selected="selectedSamples" :selectable="row => !sampleReadOnlyReason(row.status)" :selection-disabled-reason="row => sampleReadOnlyReason(row.status)"
            :sort-key="sampleQuery.sort" :direction="sampleQuery.direction" :pagination="{ ...samples, sizes: [10, 20, 50] }"
            :loading="sLoading" :error="sError" preserve-rows-on-loading :actions-disabled="actionLoading"
            @sort="sort('s', $event)" @retry="loadSamples" @page="patch({ sPage: String($event) })" @size="patch({ sSize: String($event), sPage: '1' })">
            <template #cell-code="{ row }"><RouterLink class="fw-medium" :to="link('samples', row.id)">{{ row.code }}</RouterLink></template>
            <template #cell-commissionCode="{ row }"><button v-if="row.commissionCode" class="btn btn-link p-0 text-nowrap" @click="showSamples(row.commissionId)">{{ row.commissionCode }}</button><span v-else>—</span></template>
            <template #cell-dataStatus="{ text }"><span class="badge bg-primary-subtle text-body">{{ text }}</span></template>
            <template #cell-attachmentCount="{ row }">{{ row.attachmentCount > 0 ? '有' : '' }}</template>
            <template #actions="{ row }">
                <RouterLink class="dropdown-item" role="menuitem" :to="link('samples', row.id)"><i class="ti ti-eye align-bottom me-2 text-muted" aria-hidden="true"></i>查看</RouterLink>
                <template v-if="!sampleReadOnlyReason(row.status)">
                <RouterLink v-if="workspaceCanEdit(currentActor, 'samples', row, context.workspace)" class="dropdown-item" role="menuitem" :to="link('samples', row.id, true)"><i class="ti ti-pencil align-bottom me-2 text-muted" aria-hidden="true"></i>编辑</RouterLink>
                <button v-else-if="!inquiry && registrationCanWrite(currentActor, 'samples')" class="dropdown-item" role="menuitem" disabled :title="review ? '请先撤销评审再编辑' : row.status === 'completed' ? '请先取消完成再编辑' : '已作废样品不可编辑'"><i class="ti ti-pencil align-bottom me-2 text-muted" aria-hidden="true"></i>编辑</button>
                <RouterLink class="dropdown-item" role="menuitem" :to="{ path: `${registrationRoot}/samples/${row.id}/print`, query: { returnTo: route.fullPath } }"><i class="ti ti-printer align-bottom me-2 text-muted" aria-hidden="true"></i>打印</RouterLink>
                <template v-if="workspaceActions(currentActor, 'samples', row, context.workspace).length"><div class="dropdown-divider" role="separator"></div><template v-for="item in workspaceActions(currentActor, 'samples', row, context.workspace)" :key="item.id"><RouterLink v-if="review && item.id === 'review' && !item.disabled" class="dropdown-item" role="menuitem" :to="{ path: `${registrationRoot}/samples/${row.id}/assess`, query: { returnTo: route.fullPath } }"><i class="ti ti-clipboard-list align-bottom me-2 text-muted" aria-hidden="true"></i>{{ item.label }}</RouterLink><button v-else class="dropdown-item" :class="{ 'text-danger': item.id === 'void' }" role="menuitem" :disabled="item.disabled" :title="item.disabledReason" @click="openActions('samples', row, item.id)"><i class="align-bottom me-2" :class="item.id === 'void' ? 'ti ti-ban' : ['complete', 'review'].includes(item.id) ? 'ti ti-circle-check text-muted' : 'ti ti-arrow-back-up text-muted'" aria-hidden="true"></i>{{ item.label }}</button></template>
                </template>
                </template>
                <button class="dropdown-item" role="menuitem" @click="openAttachments('samples', row.id)"><i class="ti ti-paperclip align-bottom me-2 text-muted" aria-hidden="true"></i>附件管理</button>
            </template>
            <template #empty><p class="mt-2 mb-0">暂无符合条件的样品</p><button class="btn btn-link" @click="search('s', {})">清空样品筛选</button></template>
          </DataTable>
        </template>
      </div>
    </template>
  </section>

  <CommissionAdvancedQueryModal v-if="inquiry && advancedSearchKind === 'commissions'" :initial="advancedCommissionDraft" :busy="advancedBusy" :error="advancedError" @close="closeAdvanced" @search="searchAdvancedCommission" />
  <SampleAdvancedQueryModal v-if="inquiry && advancedSearchKind === 'samples'" :initial="advancedSampleDraft" :busy="advancedBusy" :error="advancedError" @close="closeAdvanced" @search="searchAdvancedSample" />

  <RegistrationAttachmentManager :id="attachmentId" :kind="attachmentKind" @close="attachmentId = undefined" @changed="syncAttachmentVersion" />
  <RegistrationReviewModal :record="quickReviewRecord" :records="quickReviewRecords" @close="closeQuickReview" />
  <RegistrationActionModal :workspace="context.workspace" :kind="actionKind" :record="actionRecord" :initial-action="actionSelection" @close="actionRecord = undefined" @saved="refresh" />
</template>


