<script setup lang="ts">
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter, type RouteLocationNormalized } from 'vue-router'
import type { UploadProgress } from '../../components/common/fileUploadProgress'
import type { TransferProgress } from '../../services/common/uploadRequest'
import { useFileUpload, notifyUploadLeaveBlocked } from '../../components/common/useFileUpload'
import PageHeading from '../../components/common/PageHeading.vue'
import ReportFormDisplay from '../../components/reports/ReportFormDisplay.vue'
import LoadState from '../../components/common/LoadState.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import ConfirmationModal from '../../components/common/ConfirmationModal.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import FormTabs from '../../components/forms/FormTabs.vue'
import RegistrationCommissionFields from '../../components/commissions/RegistrationCommissionFields.vue'
import RegistrationSampleFields from '../../components/commissions/RegistrationSampleFields.vue'
import RegistrationTestBasisField from '../../components/commissions/RegistrationTestBasisField.vue'
import RegistrationReportSettings from '../../components/commissions/RegistrationReportSettings.vue'
import { sampleFormTabs } from '../commissions/forms/sampleSchema'
import type { ReportSettingsConfig } from '../../types/commissions/reportSettings'
import DataEntryTrialForm from '../../components/testing/DataEntryTrialForm.vue'
import OriginalRecordsWorkspace from '../../components/testing/OriginalRecordsWorkspace.vue'
import DataEntryReportFiles from '../../components/testing/DataEntryReportFiles.vue'
import DataCheckReportPreview from '../../components/testing/DataCheckReportPreview.vue'
import RegistrationAttachmentManager from '../../components/commissions/RegistrationAttachmentManager.vue'
import DataEntryRecordsModal from '../../components/testing/DataEntryRecordsModal.vue'
import DataEntryPersonPicker from '../../components/testing/DataEntryPersonPicker.vue'
import ReportCheckRejectionForm from '../../components/testing/ReportCheckRejectionForm.vue'
import type { EntryPerson } from '../../types/testing/dataEntryDetail'
import { emptyReportCheckRejection, reportStages, type ReportStage, type ReportCheckNextAction } from '../../types/reports/reportCheck'
import { useUnsavedChanges } from '../../components/common/useUnsavedChanges'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { emptyTrialForm, type EntryDetail, type EntryFileKind, type EntryFileSummary, type EntryPersonRole, type EntryPeopleScope } from '../../types/testing/dataEntryDetail'
import { emptySampleDetails } from '../../types/commissions/sampleForm'
import { AppError, normalizeError, safeReturn, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor, sessionLocked } from '../../stores/session'
import type { ReviewCheckResult } from '../../types/commissions/contractReview'

const props = defineProps<{ reportOnly?: boolean; checkMode?: boolean; reportCheckMode?: boolean; reportStage?: ReportStage; queryMode?: boolean; reportQueryMode?: boolean; changeMode?: boolean }>()
const reportStage = computed(() => props.reportStage || 'check')
const stageConfig = computed(() => reportStages[reportStage.value])
const stageText = (text: string) => text.replaceAll('校核', stageConfig.value.label)
const route = useRoute(), router = useRouter(), detail = ref<EntryDetail>(), form = ref(emptyTrialForm()), saved = ref(''), layoutId = ref('')
const entryViewMode = computed(() => !props.reportOnly && !props.queryMode && !props.changeMode && route.query.mode === 'view')
const previewLayout = computed(() => !!props.checkMode || entryViewMode.value)
const initialTab = () => props.reportOnly ? 'report' : props.checkMode ? 'report-preview' : entryViewMode.value ? 'trial' : route.query.tab === 'original' ? 'original' : 'trial'
const tab = ref(initialTab()), error = ref<ErrorValue>(''), busy = ref(false), loading = ref(false), stale = ref(false)
const reportTab = ref('template')
const completionError = ref<ErrorValue>('')
const progressError = ref('')
let pollFailures = 0, pollInFlight: number | undefined
const success = ref(''), toast = ref<InstanceType<typeof TemplateToast>>(), discard = ref('')
const tabs = computed(() => [...sampleFormTabs, ...['试验信息', '原始记录'].map((label, index) => ({ label, key: ['trial', 'original'][index]!, tabId: `entry-tab-${index}`, panelId: `entry-panel-${index}` })), ...(previewLayout.value ? [{ label: '报告预览', key: 'report-preview', tabId: 'check-report-tab', panelId: 'check-report-panel' }] : [])])
const reportConfig = ref<ReportSettingsConfig>(), reportConfigLoading = ref(false), reportConfigError = ref<ErrorValue>('')
const readonlyMode = computed(() => !!props.queryMode || !!props.checkMode || route.query.mode === 'view')
const editable = computed(() => !readonlyMode.value && !!detail.value?.capabilities.canEdit && !stale.value)
const dirty = computed(() => !!detail.value && draftKey() !== saved.value)
const listRoot = computed(() => props.reportQueryMode ? '/reports/query' : props.reportCheckMode ? stageConfig.value.root : props.changeMode ? '/testing/data-changes' : props.queryMode ? '/testing/data-query' : props.checkMode ? '/testing/data-check' : '/testing/data-entry')
const returnTo = computed(() => {
  const target = safeReturn(route.query.returnTo, listRoot.value), path = target.split('?')[0]
  return path === listRoot.value ? target : listRoot.value
})
const fieldErrors = computed(() => error.value ? error.value.fieldErrors || {} : {})
const sampleForm = computed(() => detail.value ? { ...detail.value.sample, details: { ...emptySampleDetails(), ...detail.value.sample.details } } : undefined)
const peopleScopes = ref<Partial<Record<EntryPersonRole, EntryPeopleScope>>>({})
const sampleOptions = { choices: {}, subprojectOptions: [] }
const pendingTemplateDownload = ref('')
const downloadKind = ref<'template' | 'complete-report'>('template')
const pdfUrl = ref(''), previewName = ref(''), previewBlob = ref<Blob>(), previewKind = ref('')
let epoch = 0, pollTimer: ReturnType<typeof setTimeout> | undefined, allowLeave = false, previewSequence = 0, reportRequest = 0
let pendingPreview: { kind: 'final'; id: string } | undefined
const draftKey = () => JSON.stringify({ form: form.value, layoutId: layoutId.value })
const resultKey = (result: EntryDetail) => JSON.stringify({ form: result.form, layoutId: result.layoutId })
const uploadStatus = useFileUpload()
const working = computed(() => busy.value || uploadStatus.active.value)
const reportConfirmed = computed(() => !!detail.value?.reportConfirmed && !dirty.value && !stale.value)
const canConfirmReport = computed(() => !!props.reportOnly && editable.value && !working.value && !loading.value && !dirty.value && !!pdfUrl.value && detail.value?.reportStatus === 'ready' && !!detail.value.capabilities.canManageReport)
const originalBusy = ref(false)
const checkOpen = ref(false), checkError = ref<ErrorValue>('')
const checkStep = ref<'check' | 'next' | 'reject'>('check'), nextAction = ref<ReportCheckNextAction>('next'), recipient = ref<EntryPerson>(), recipientPicking = ref(false)
const rejection = ref(emptyReportCheckRejection())
const rejectionReady = computed(() => !!rejection.value.problemType)
const recipientScope = ref<EntryPeopleScope>()
const reviewReadConfirmed = ref(false)
const reviewCheckResult = ref<ReviewCheckResult>(), reviewChecking = ref(false), reviewCheckError = ref<ErrorValue>('')
let reviewRequest = 0, reviewController: AbortController | undefined
function clearReviewCheck() { reviewRequest++; reviewController?.abort(); reviewChecking.value = false; reviewCheckResult.value = undefined; reviewReadConfirmed.value = false; checkStep.value = 'check'; recipientPicking.value = false }
const canCheck = computed(() => !!props.checkMode && !props.reportOnly && !!(props.reportCheckMode ? detail.value?.capabilities[reportStage.value === 'review' ? 'canReportReview' : reportStage.value === 'approval' ? 'canReportApprove' : 'canReportCheck'] : detail.value?.capabilities.canCheck) && !stale.value && !working.value && !loading.value && !originalBusy.value && !reviewChecking.value)
const canApproveCheck = computed(() => canCheck.value && (!props.reportCheckMode || !!reviewCheckResult.value && reviewReadConfirmed.value))
watch(() => [detail.value?.sample.id, detail.value?.sample.version, currentActor.value.id, checkOpen.value], clearReviewCheck, { flush: 'sync' })
onBeforeUnmount(clearReviewCheck)
function openCheck() { if (canCheck.value) { checkError.value = ''; reviewCheckError.value = ''; clearReviewCheck(); nextAction.value = 'next'; recipient.value = undefined; rejection.value = emptyReportCheckRejection(); checkOpen.value = true } }
function rejectCheck() {
  if (!canCheck.value) return
  if (props.reportCheckMode) { checkStep.value = 'reject'; checkError.value = '' }
  else void confirmCheck('reject')
}
function approveCheck() {
  if (!canApproveCheck.value) return
  if (props.reportCheckMode) { checkStep.value = 'next'; checkError.value = '' }
  else void confirmCheck('check')
}
function selectRecipient(person: EntryPerson) { recipient.value = person; recipientPicking.value = false }
async function runReviewCheck() {
  if (!props.reportCheckMode || !checkOpen.value || !canCheck.value || !detail.value) return
  clearReviewCheck(); reviewCheckError.value = ''; checkError.value = ''; reviewChecking.value = true
  const request = reviewRequest, sample = detail.value.sample, abort = reviewController = new AbortController()
  try {
    const result = await registrationDemo.reportComplianceCheck(sample.id, sample.version, abort.signal, reportStage.value)
    if (request !== reviewRequest) return
    if (!result.id || result.sampleId !== sample.id || !Number.isFinite(Date.parse(result.checkedAt)) || !Array.isArray(result.messages) || !result.messages.length || result.messages.some(item => !item || !['info', 'warning'].includes(item.tone) || typeof item.text !== 'string')) throw new AppError('UNAVAILABLE', '校核结果格式有误，请重试。')
    reviewCheckResult.value = result
  } catch (issue) {
    if (request !== reviewRequest || abort.signal.aborted) return
    reviewCheckError.value = normalizeError(issue)
    if (['FORBIDDEN', 'NOT_FOUND', 'BUSINESS_RULE'].includes(reviewCheckError.value.code)) stale.value = true
  } finally { if (request === reviewRequest) reviewChecking.value = false }
}
async function confirmCheck(decision: 'check' | 'reject') {
  if (!checkOpen.value || !canCheck.value || !detail.value) return
  if (decision === 'check' && !canApproveCheck.value) return
  if (decision === 'check' && props.reportCheckMode && (checkStep.value !== 'next' || nextAction.value === 'transfer' && !recipient.value)) return
  if (decision === 'reject' && props.reportCheckMode && (checkStep.value !== 'reject' || !rejectionReady.value)) return
  const token = epoch, sample = detail.value.sample
  busy.value = true; checkError.value = ''
  try {
    const result = await (props.reportCheckMode
      ? registrationDemo.reportCheckAction(sample.id, decision, sample.version, decision === 'check' ? { reviewCheckId: reviewCheckResult.value!.id, readConfirmed: reviewReadConfirmed.value, nextAction: nextAction.value, ...(nextAction.value === 'transfer' ? { recipientId: recipient.value!.id } : {}) } : undefined, decision === 'reject' ? { ...rejection.value } : undefined, reportStage.value)
      : registrationDemo.dataCheckAction(sample.id, decision, sample.version))
    if (token !== epoch) return
    detail.value.sample = result; detail.value.capabilities.canCheck = false
    if (props.reportCheckMode) detail.value.capabilities[reportStage.value === 'review' ? 'canReportReview' : reportStage.value === 'approval' ? 'canReportApprove' : 'canReportCheck'] = false
    checkOpen.value = false; busy.value = false
    await router.push(decision === 'reject' && !props.reportCheckMode ? '/testing/data-entry' : returnTo.value)
  } catch (issue) {
    if (token !== epoch) return
    const failure = normalizeError(issue)
    if (['NETWORK', 'UNAVAILABLE', 'FORBIDDEN', 'NOT_FOUND', 'BUSINESS_RULE'].includes(failure.code)) {
      checkOpen.value = false; stale.value = true; error.value = failure
    } else { checkError.value = failure; if (props.reportCheckMode && decision === 'check' && failure.code === 'VALIDATION') clearReviewCheck() }
  } finally { if (token === epoch) busy.value = false }
}
const attachmentOpen = ref(false), recordsMode = ref<'changes' | 'issues'>()
function syncAttachments(record: { id: string; version: number }) {
  if (detail.value?.sample.id === record.id) detail.value.sample.version = Math.max(detail.value.sample.version, record.version)
}
const leaveDirty = computed(() => dirty.value)
useUnsavedChanges(leaveDirty)
function selectTab(value: string) {
  if (originalBusy.value || working.value) return
  tab.value = value
}
async function selectReportTab(value: string) {
  if (working.value || loading.value || !['template', 'files', 'preview', 'complete'].includes(value)) return
  if (value === 'complete' && !reportConfirmed.value) {
    await confirmReport()
    return
  }
  if (value === 'preview' && editable.value) { await beginReport('preview'); return }
  if (value !== 'template' && !readonlyMode.value && detail.value?.capabilities.canEdit && (!detail.value.layoutAdopted || layoutId.value !== detail.value.layoutId)) {
    reportTab.value = 'template'
    if (!await save(true)) return
  }
  completionError.value = ''
  reportTab.value = value
  if (value !== 'preview' || dirty.value || stale.value) return
  if (detail.value?.reportStatus === 'ready' && !pdfUrl.value) await preview()
  else if (detail.value?.reportStatus === 'running' && detail.value.job) pendingPreview = { kind: 'final', id: detail.value.job.id }
}
async function beginReport(target: 'files' | 'preview') {
  if (working.value || loading.value || stale.value || !detail.value) return
  if (!editable.value) { await selectReportTab(target); return }
  if (!await save(true)) return
  completionError.value = ''
  reportTab.value = target
  if (target === 'preview') await finalPreview()
}
async function loadReportConfig() {
  const token = epoch, request = ++reportRequest
  reportConfigLoading.value = true; reportConfigError.value = ''; reportConfig.value = undefined
  try {
    const config = await registrationDemo.reportSettingsConfig()
    if (token === epoch && request === reportRequest) reportConfig.value = config
  } catch (issue) { if (token === epoch && request === reportRequest) reportConfigError.value = normalizeError(issue) }
  finally { if (token === epoch && request === reportRequest) reportConfigLoading.value = false }
}
function clearPreview() { previewSequence++; if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value); pdfUrl.value = ''; previewBlob.value = undefined; previewKind.value = '' }
function apply(result: EntryDetail, replaceForm = false) {
  if (detail.value && (result.version < detail.value.version || result.sample.version < detail.value.sample.version)) return
  if (previewKind.value === 'final' && (result.reportStatus !== 'ready' || detail.value?.job?.id !== result.job?.id) || detail.value?.reportRevision !== result.reportRevision || detail.value?.template.version !== result.template.version) clearPreview()
  if (detail.value?.reportRevision !== result.reportRevision || detail.value?.job?.id !== result.job?.id) completionError.value = ''
  detail.value = result
  if (replaceForm) { form.value = structuredClone(result.form); layoutId.value = result.layoutId; saved.value = resultKey(result) }
  schedulePoll()
}
function schedulePoll() {
  clearTimeout(pollTimer)
  if (document.hidden || sessionLocked.value || stale.value || loading.value) return
  if (detail.value?.reportStatus !== 'running' && detail.value?.templateJob?.stage !== 'word' && detail.value?.completeReportJob?.stage !== 'word') return
  const elapsed = detail.value.job?.elapsedMs ?? 0
  const delay = pollFailures ? Math.min(15000, 2000 * 2 ** (pollFailures - 1)) : elapsed >= 30000 ? 5000 : 800
  pollTimer = setTimeout(() => void pollProgress(), delay)
}
async function pollProgress() {
  clearTimeout(pollTimer)
  if (document.hidden || sessionLocked.value || stale.value || loading.value) return
  if (detail.value?.reportStatus !== 'running' && detail.value?.templateJob?.stage !== 'word' && detail.value?.completeReportJob?.stage !== 'word') return
  if (working.value || pollInFlight === epoch) { schedulePoll(); return }
  const token = epoch
  pollInFlight = token
  try {
    const result = await registrationDemo.entryDetail(String(route.params.id))
    if (token !== epoch) return
    progressError.value = ''; pollFailures = 0
    apply(result); await finishTemplateDownload(); await openPendingPreview()
  } catch (issue) {
    if (token !== epoch) return
    const failure = normalizeError(issue)
    if (['FORBIDDEN', 'UNAUTHORIZED', 'NOT_FOUND', 'LOCKED'].includes(failure.code)) {
      stale.value = true; pendingTemplateDownload.value = ''; error.value = failure
    } else {
      progressError.value = '暂时无法获取最新进度，后台任务可能仍在运行。正在自动重试。'
      pollFailures++
    }
  } finally {
    if (pollInFlight === token) pollInFlight = undefined
    if (token === epoch) schedulePoll()
  }
}
function resumeProgress() {
  if (document.hidden || sessionLocked.value) clearTimeout(pollTimer)
  else void pollProgress()
}
async function load(preserveDraft = false) {
  checkOpen.value = false; checkError.value = ''
  const keepDraft = preserveDraft && dirty.value
  pendingPreview = undefined; pendingTemplateDownload.value = ''; completionError.value = ''; progressError.value = ''; pollFailures = 0
  const token = ++epoch; uploadStatus.finish(); clearTimeout(pollTimer); clearPreview(); loading.value = true; error.value = ''; busy.value = false
  try {
    const result = await registrationDemo.entryDetail(String(route.params.id))
    if (token !== epoch) return
    if (!readonlyMode.value && result.capabilities.canEdit && (props.reportOnly || route.query.checkReport === '1')) {
      try {
        await registrationDemo.entryAction(result.sample.id, 'validate-report-entry', { version: result.version, sampleVersion: result.sample.version, requestId: crypto.randomUUID() })
      } catch (issue) {
        if (token !== epoch) return
        const failure = normalizeError(issue)
        if (props.reportOnly && failure.code === 'VALIDATION') {
          loading.value = false
          await router.replace({ path: `${listRoot.value}/${encodeURIComponent(result.sample.id)}`, query: { returnTo: returnTo.value, checkReport: '1' } })
          return
        }
        if (props.reportOnly || failure.code !== 'VALIDATION') throw issue
        error.value = failure; tab.value = 'trial'
      }
      if (token !== epoch) return
    }
    apply(result, !keepDraft); stale.value = false
    if (props.reportOnly && !preserveDraft) {
      reportTab.value = result.job ? 'preview' : result.files.some(file => file.kind === 'report' || file.kind === 'appendix') ? 'files' : 'template'
    }
    if (props.reportOnly && !keepDraft && result.reportConfirmed) reportTab.value = 'complete'
    else if (reportTab.value === 'complete') reportTab.value = 'preview'
    if (props.reportOnly && reportTab.value === 'preview' && result.reportStatus === 'running' && result.job) pendingPreview = { kind: 'final', id: result.job.id }
    if (!props.reportOnly) void loadReportConfig()
    if (keepDraft) {
      saved.value = resultKey(result); notify('已刷新服务器资料，当前填写内容已保留，请核对后操作。')
    }
  } catch (issue) { if (token === epoch) error.value = normalizeError(issue) }
  finally { if (token === epoch) { loading.value = false; schedulePoll() } }
  if (token === epoch && props.reportOnly && reportTab.value === 'preview' && detail.value?.reportStatus === 'ready' && !dirty.value) await preview()
}
function notify(message: string) { success.value = message; void nextTick(() => toast.value?.show()) }
async function action(name: string, values: Record<string, unknown> = {}, replaceForm = false, progress?: TransferProgress) {
  if (!detail.value || busy.value || stale.value) return false
  const token = epoch; busy.value = true; error.value = ''
  try {
    const result = await registrationDemo.entryAction(detail.value.sample.id, name, { ...values, version: detail.value.version, sampleVersion: detail.value.sample.version, requestId: crypto.randomUUID() }, progress)
    if (token !== epoch) return false
    apply(result, replaceForm); return true
  } catch (issue) {
    if (token !== epoch) return false
    const failure = normalizeError(issue); error.value = failure
    if (failure.fieldErrors && name !== 'confirm-report') {
      if (!props.reportOnly) tab.value = 'trial'
      else if (failure.fieldErrors.layoutId) reportTab.value = 'template'
      await nextTick(); document.querySelector<HTMLElement>('.invalid-feedback')?.scrollIntoView({ block: 'center' })
    }
    if (['NETWORK', 'UNAVAILABLE', 'FORBIDDEN', 'NOT_FOUND'].includes(failure.code)) { stale.value = true; clearPreview() }
    return false
  } finally { if (token === epoch) { busy.value = false; schedulePoll() } }
}
async function save(adoptLayout = false) {
  if (!editable.value || working.value || loading.value || originalBusy.value) return false
  if ((dirty.value || adoptLayout && !detail.value?.layoutAdopted) && !await action('save', { form: form.value, layoutId: layoutId.value, ...(adoptLayout ? { adoptLayout: true } : {}) }, true)) return false
  notify(props.reportOnly ? '报告设置已保存。' : '试验信息已保存。'); return true
}
async function templateDownload(kind: 'template' | 'complete-report' = 'template') {
  if (working.value || loading.value || stale.value || pendingTemplateDownload.value || !detail.value) return
  if (kind === 'complete-report' && !detail.value.completeReportGeneration.layoutIds.includes(layoutId.value)) return
  if (editable.value && !await save(true)) return
  downloadKind.value = kind
  const task = kind === 'complete-report' ? detail.value.completeReportJob : detail.value.templateJob
  if (!task || (kind === 'complete-report' ? detail.value.completeReportStale : detail.value.templateStale) || task.stage === 'word-failed') {
    if (!editable.value || !await action('template-tasks', { wordOnly: true, kind }) || stale.value) return
  }
  const next = kind === 'complete-report' ? detail.value.completeReportJob : detail.value.templateJob
  if (!next) return
  pendingTemplateDownload.value = next.id
  await finishTemplateDownload()
  schedulePoll()
}
async function finishTemplateDownload() {
  const id = pendingTemplateDownload.value, current = detail.value, complete = downloadKind.value === 'complete-report', task = complete ? current?.completeReportJob : current?.templateJob
  if (!id || !current || !task || busy.value) return
  if (stale.value || dirty.value || (complete ? current.completeReportStale : current.templateStale) || task.id !== id || !props.reportOnly) { pendingTemplateDownload.value = ''; return }
  if (task.stage === 'word-failed') { pendingTemplateDownload.value = ''; return }
  if (!task.wordAvailable) return
  pendingTemplateDownload.value = ''
  await download(`template-tasks/${encodeURIComponent(task.id)}/word`, `${current.sample.code}-${task.layoutId}-${complete ? '完整报告' : '演示模板'}.docx`)
}
async function openPendingPreview() {
  const pending = pendingPreview, current = detail.value
  if (!pending || !current || busy.value || stale.value || tab.value !== 'report' || reportTab.value !== 'preview' || dirty.value) return
  if (current.job?.id === pending.id && current.reportStatus === 'ready') { pendingPreview = undefined; await preview() }
}
async function finalPreview() {
  if (working.value || reportTab.value !== 'preview') return
  if (!dirty.value && detail.value?.reportStatus === 'running' && detail.value.job) {
    pendingPreview = { kind: 'final', id: detail.value.job.id }; schedulePoll(); return
  }
  if (!dirty.value && detail.value?.reportStatus === 'ready' && pdfUrl.value) return
  pendingPreview = undefined; clearPreview()
  if (dirty.value && !await save()) return
  if (detail.value?.reportStatus === 'ready') { await preview(); return }
  if (!editable.value || !await action('combine')) return
  if (tab.value === 'report' && detail.value?.job) pendingPreview = { kind: 'final', id: detail.value.job.id }
  await openPendingPreview()
}
async function confirmReport() {
  if (!canConfirmReport.value || !detail.value) return
  if (!detail.value.reportConfirmed && !await action('confirm-report', { taskId: detail.value.job!.id })) {
    if (error.value && ['VALIDATION', 'BUSINESS_RULE'].includes(error.value.code)) {
      completionError.value = error.value; error.value = ''
    }
    return
  }
  if (!detail.value.reportConfirmed) return
  completionError.value = ''; pendingPreview = undefined; pendingTemplateDownload.value = ''
  reportTab.value = 'complete'
  await nextTick(); document.getElementById('report-complete-title')?.focus()
}
async function download(target: string, filename: string) {
  if (busy.value) return
  const token = epoch; busy.value = true; error.value = ''
  try { const blob = await registrationDemo.entryDownload(String(route.params.id), target); if (token === epoch) downloadBlob(blob, filename) }
  catch (issue) { if (token === epoch) error.value = normalizeError(issue) }
  finally { if (token === epoch) busy.value = false }
}
async function preview() {
  if (busy.value || !detail.value || dirty.value || stale.value || reportTab.value !== 'preview' || detail.value.reportStatus !== 'ready') return
  const taskId = detail.value.job?.id
  if (!taskId) return
  pendingPreview = undefined; clearPreview(); const token = epoch, request = previewSequence, activeTab = tab.value; busy.value = true; error.value = ''
  try {
    const target = `report-tasks/${encodeURIComponent(taskId)}/pdf`
    const blob = await registrationDemo.entryDownload(detail.value.sample.id, target)
    if (token !== epoch || request !== previewSequence || tab.value !== activeTab) return
    previewBlob.value = blob; pdfUrl.value = URL.createObjectURL(blob); previewKind.value = 'final'
    previewName.value = `${detail.value.sample.code}-最终报告-模拟预览.pdf`
  } catch (issue) { if (token === epoch) error.value = normalizeError(issue) }
  finally { if (token === epoch) { busy.value = false; schedulePoll() } }
}
async function uploadReportFile(kind: EntryFileKind, file: File, progress: UploadProgress) {
  if (!detail.value || working.value || !editable.value) throw new Error('当前不可上传，请刷新后重试。')
  if (kind === 'report' && dirty.value && !await save()) throw new Error(error.value ? error.value.message : '报告设置保存失败。')
  if (file.size > detail.value.options.maxFileSize || !file.size) throw new Error('请选择不超过 20 MB 的非空文件。')
  const token = epoch
  uploadStatus.start(file.name); error.value = ''; busy.value = true
  try {
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(reader.error)
      reader.onabort = () => reject(new Error('文件读取已取消。'))
      reader.onprogress = event => progress('reading', event.loaded, event.lengthComputable ? event.total : undefined)
      reader.readAsDataURL(file)
    })
    if (token !== epoch) throw new Error('页面已切换，请重新上传。')
    uploadStatus.processing(); progress('uploading'); busy.value = false
    const ok = await action('upload', { kind, file: { name: file.name, size: file.size, type: file.type, dataUrl } }, false,
      (loaded, total) => progress(loaded === total ? 'saving' : 'uploading', loaded === total ? undefined : loaded, loaded === total ? undefined : total))
    if (!ok) { const failure = error.value as ErrorValue; throw new Error(failure ? failure.message : '上传失败，请重试。') }
    clearPreview()
  } finally { if (token === epoch) { busy.value = false; uploadStatus.finish() } }
}
async function changeReportLayout(target: string) {
  if (!editable.value || busy.value) return
  if (dirty.value && !await save()) return
  if (await action('change-report-layout', { layoutId: target, confirmed: true }, true)) {
    reportTab.value = 'template'
    notify('首页版式已切换。')
  }
}
async function remove(file: EntryFileSummary) { if (await action('delete', { fileId: file.id })) { clearPreview(); notify('文件已删除。') } }
function requestLeave(path: string) { discard.value = path }
function back() { if (working.value || originalBusy.value) return; if (leaveDirty.value) requestLeave(returnTo.value); else void router.push(returnTo.value) }
async function openReport() {
  if (props.reportOnly || working.value || loading.value || originalBusy.value || !detail.value?.capabilities.canView) return
  if (!readonlyMode.value && detail.value.capabilities.canEdit) {
    const ready = dirty.value
      ? await action('save', { form: form.value, layoutId: layoutId.value, prepareReport: true }, true)
      : await action('validate-report-entry')
    if (!ready) return
  }
  await router.push({ path: `${listRoot.value}/${encodeURIComponent(detail.value.sample.id)}/report`, query: { returnTo: returnTo.value, ...(readonlyMode.value ? { mode: 'view' } : {}) } })
}
function guard(to: RouteLocationNormalized) { if (working.value || originalBusy.value) { notifyUploadLeaveBlocked(); return false }; if (leaveDirty.value && !allowLeave) { requestLeave(to.fullPath); return false } }
onBeforeRouteLeave(guard)
onBeforeRouteUpdate(guard)
function abandon() { allowLeave = true; void router.push(discard.value) }
watch(tab, () => { pendingPreview = undefined; pendingTemplateDownload.value = ''; clearPreview() })
watch([form, layoutId], () => { if (dirty.value) { completionError.value = ''; pendingPreview = undefined; pendingTemplateDownload.value = ''; clearPreview() } }, { deep: true })
watch(() => [route.params.id, route.query.mode, currentActor.value.id, props.reportOnly, props.checkMode, props.reportCheckMode, props.reportStage, props.queryMode, props.changeMode], () => { tab.value = initialTab(); allowLeave = false; attachmentOpen.value = false; recordsMode.value = undefined; detail.value = undefined; saved.value = ''; discard.value = ''; peopleScopes.value = {}; void load() }, { immediate: true })
document.addEventListener('visibilitychange', resumeProgress)
watch(sessionLocked, resumeProgress)
onBeforeUnmount(() => { epoch++; clearTimeout(pollTimer); clearPreview(); document.removeEventListener('visibilitychange', resumeProgress) })
</script>
<template>
  <PageHeading :title="reportCheckMode ? stageConfig.title : checkMode ? '数据校核' : reportOnly ? '报告填写' : readonlyMode ? '查看检测数据' : changeMode ? '检测数据更改' : '检测数据录入'" :parent-to="returnTo" />
  <LoadState :loading="loading" :error="!detail ? error : ''" :back-to="returnTo" @retry="load()" />
  <template v-if="detail && sampleForm">
    <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-3">
      <button class="btn btn-light" type="button" :disabled="working || loading || originalBusy" @click="back"><i class="ti ti-arrow-left me-1" aria-hidden="true"></i>{{ reportQueryMode ? '返回报告查询' : reportCheckMode ? '返回' + stageConfig.title : changeMode ? '返回检测数据更改' : queryMode ? '返回检测数据查询' : checkMode ? '返回检测数据校核' : '返回检测数据录入' }}</button>
      <ReportFormDisplay v-if="reportCheckMode" :sample="detail.sample" />
      <button v-if="!reportOnly && !previewLayout && !queryMode" class="btn btn-light ms-auto" type="button" :disabled="working || loading || originalBusy || !detail.capabilities.canView" @click="openReport">报告填写<i class="ti ti-arrow-right ms-1" aria-hidden="true"></i></button>
    </div>
    <div v-if="error" class="mb-3"><ErrorNotice :error="error" /><button v-if="stale || ['NETWORK', 'UNAVAILABLE'].includes(error.code)" type="button" class="btn btn-light" :disabled="working || loading" @click="load(true)">刷新核对</button></div>

    <form :aria-label="reportOnly ? '报告填写表单' : '检测数据录入表单'" novalidate @submit.prevent="save()">
    <fieldset :disabled="working || loading" :aria-busy="working || loading">
    <template v-if="!reportOnly">
    <section class="card" aria-label="检测设置">
      <div class="card-body"><div class="row g-3">
        <div class="col-md-6">
          <label for="sample-testPlan" class="form-label">检测方案</label>
          <div class="input-group"><input id="sample-testPlan" :value="sampleForm.details.testPlanCode ? `${sampleForm.details.testPlan}（${sampleForm.details.testPlanCode}）` : sampleForm.details.testPlan" class="form-control bg-body-tertiary" readonly placeholder="请选择检测方案" /></div>
        </div>
        <div class="col-md-6">
          <RegistrationTestBasisField readonly :text-value="sampleForm.details.testBasis" :plan-id="sampleForm.details.testPlanId" :ids="sampleForm.details.testBasisIds" :separators="sampleForm.details.testBasisSeparators" :english-book-marks="sampleForm.details.englishBookMarks" />
        </div>
      </div></div>
    </section>
    <FormTabs :model-value="tab" @update:model-value="selectTab" :tabs="tabs" label="检测数据录入页签" />
    <div v-for="item in tabs" v-show="tab === item.key" :id="item.panelId" :key="item.key" role="tabpanel" :aria-labelledby="item.tabId">
      <RegistrationCommissionFields v-if="item.key === 'order' && tab === 'order'" :form="detail.sample.commissionInfo" :code="detail.sample.commissionInfo.code" :owner="detail.sample.commissionInfo.owner" sample readonly />
      <RegistrationSampleFields v-if="item.key === 'sample' && tab === 'sample'" :form="sampleForm" :options="sampleOptions" :code="detail.sample.code" :report-code="detail.sample.reportCode" :commission-code="detail.sample.commissionInfo.code" :projects="detail.sample.projects" readonly><template #report-settings><RegistrationReportSettings readonly :model-value="sampleForm.details.reportSettings" :config="reportConfig" :loading="reportConfigLoading" :error="reportConfigError" @retry="loadReportConfig" /></template></RegistrationSampleFields>
      <fieldset v-if="item.key === 'trial' && tab === 'trial'" :disabled="working || loading"><DataEntryTrialForm :form="form" :detail="detail" :readonly="!editable" :errors="fieldErrors" :people-scopes="peopleScopes" @equipment-config="apply($event)" @people-scope="peopleScopes[$event.role] = $event.scope" /></fieldset>
      <OriginalRecordsWorkspace v-if="item.key === 'original'" :sample-id="detail.sample.id" :active="tab === 'original'" :readonly="readonlyMode || stale" :preview-only="previewLayout || queryMode" @busy="originalBusy = $event" />
      <DataCheckReportPreview v-if="previewLayout && item.key === 'report-preview'" :detail="detail" :active="tab === 'report-preview'" @refresh="load()" />
    </div>
    </template>
      <DataEntryReportFiles :removal-error="error" v-else v-model:layout-id="layoutId" :detail="detail" :active-tab="reportTab" :can-confirm="canConfirmReport" :confirmed="reportConfirmed" :completion-error="completionError" :progress-error="progressError" @refresh-progress="pollProgress" @confirm="confirmReport" @back="back" @begin="beginReport" @select-tab="selectReportTab" :busy="working || loading" :readonly="!editable" :dirty="dirty" :preview-url="pdfUrl" :preview-name="previewName" :preview-blob="previewBlob" :layout-error="fieldErrors.layoutId" @change-layout="changeReportLayout" :upload="uploadReportFile" @remove="remove" @sort="action('sort', { ids: $event })" @download="download(`files/${encodeURIComponent($event.id)}`, $event.name)" @download-template="templateDownload()" @download-complete-report="templateDownload('complete-report')" :template-downloading="!!pendingTemplateDownload && downloadKind === 'template'" :complete-report-downloading="!!pendingTemplateDownload && downloadKind === 'complete-report'" @final-preview="finalPreview">
        <template #upload-status><FeedbackNotice v-if="uploadStatus.leaveAttempted.value" message="文件正在上传，请等待完成后再离开。" /></template>
      </DataEntryReportFiles>

    </fieldset>
    <div class="d-flex align-items-center justify-content-end flex-wrap gap-2 mb-4 pe-5">
      <div class="d-flex flex-wrap gap-2 me-auto">
        <button class="btn btn-light" type="button" :disabled="working || loading || originalBusy" @click="attachmentOpen = true"><i class="ti ti-paperclip me-1" aria-hidden="true"></i>{{ previewLayout || queryMode ? '查看附件' : '附件管理' }}</button>
        <button class="btn btn-light" type="button" :disabled="working || loading || originalBusy" @click="recordsMode = 'changes'"><i class="ti ti-history me-1" aria-hidden="true"></i>查看修改记录</button>
        <button class="btn btn-light" type="button" :disabled="working || loading || originalBusy" @click="recordsMode = 'issues'"><i class="ti ti-help me-1" aria-hidden="true"></i>查看问题记录</button>
      </div>
      <span class="spinner-border spinner-border-sm text-primary" :class="{ invisible: !working }" role="status" aria-label="正在处理" :aria-hidden="!working"></span>
      <button class="btn btn-light" type="button" :disabled="working || loading || originalBusy" @click="back">返回</button>
      <button v-if="!reportOnly && !readonlyMode && detail.capabilities.canEdit" type="submit" class="btn btn-primary" :disabled="working || loading || stale || originalBusy">保存</button>
      <button v-if="checkMode && !reportOnly" type="button" class="btn btn-primary" :disabled="!canCheck" @click="openCheck">{{ reportCheckMode ? stageConfig.label : '校核' }}</button>
    </div>
    </form>
    <BootstrapModal v-if="checkOpen && !recipientPicking" open :title="checkStep === 'reject' ? '问题处理' : checkStep === 'next' ? '确认下一步' : reportCheckMode ? stageConfig.title : '数据校核'" :size="reportCheckMode && checkStep !== 'next' ? 'lg' : undefined" scrollable :busy="working" @close="!working && (checkOpen = false)">
      <p class="text-break"><strong>{{ detail.sample.code }}</strong> · {{ detail.sample.name }}</p>
      <template v-if="checkStep === 'next'">
        <fieldset :disabled="working" class="mb-3">
          <legend class="visually-hidden">下一步</legend>
          <div class="d-flex flex-wrap gap-4">
            <div class="form-check"><input id="report-next-transfer" v-model="nextAction" class="form-check-input" type="radio" name="report-next-action" value="transfer" /><label class="form-check-label" for="report-next-transfer">转交{{ stageConfig.label }}</label></div>
            <div class="form-check"><input id="report-next-submit" v-model="nextAction" class="form-check-input" type="radio" name="report-next-action" value="next" /><label class="form-check-label" for="report-next-submit">下一步</label></div>
          </div>
        </fieldset>
        <label for="report-next-recipient" class="form-label">接收人<span v-if="nextAction === 'transfer'" class="text-danger ms-1">*</span></label>
        <div class="input-group">
          <input id="report-next-recipient" class="form-control" readonly :disabled="working || nextAction !== 'transfer'" :value="nextAction === 'transfer' && recipient ? `${recipient.name}（${recipient.id}）` : ''" placeholder="请选择接收人" />
          <button type="button" class="btn btn-light" aria-label="选择接收人" :disabled="working || nextAction !== 'transfer'" @click="recipientPicking = true"><i class="ti ti-search" aria-hidden="true"></i></button>
          <button type="button" class="btn btn-light" aria-label="清除接收人" :disabled="working || nextAction !== 'transfer' || !recipient" @click="recipient = undefined"><i class="ti ti-x" aria-hidden="true"></i></button>
        </div>
      </template>
      <ReportCheckRejectionForm v-else-if="checkStep === 'reject'" :form="rejection" :busy="working" :errors="checkError ? checkError.fieldErrors || {} : {}" />
      <template v-else>
      <p>{{ reportCheckMode ? stageText('请选择校核结果。不通过时需填写问题处理信息。') : '请选择校核结果。不通过将退回检测数据录入。' }}</p>
      <section v-if="reportCheckMode" class="card border shadow-none mb-0" aria-labelledby="report-review-check-title" :aria-busy="reviewChecking">
        <div class="card-header bg-light py-2 px-3 d-flex align-items-center justify-content-between flex-wrap gap-2">
          <h6 id="report-review-check-title" class="card-title mb-0 fs-5">{{ stageText('合规校核') }}</h6>
          <button type="button" class="btn btn-sm btn-outline-primary d-inline-flex align-items-center gap-1 my-n2" :disabled="!canCheck" @click="runReviewCheck"><span v-if="reviewChecking" class="spinner-border spinner-border-sm flex-shrink-0" aria-hidden="true"></span><i v-else class="ti ti-shield-check lh-1" aria-hidden="true"></i><span>{{ reviewChecking ? '校验中…' : '校验' }}</span></button>
        </div>
        <div class="card-body p-3" role="region" :aria-label="stageText('合规校核结果')">
          <ErrorNotice :error="reviewCheckError" :retry="!stale" :busy="reviewChecking || working" @retry="runReviewCheck" />
          <FeedbackNotice v-if="stale" message="样品信息或可用状态已发生变化，请刷新样品后重新校验、确认。"><p class="mb-2">样品信息或可用状态已发生变化，请刷新样品后重新校验、确认。</p><button type="button" class="btn btn-sm btn-outline-primary" :disabled="working || loading" @click="load()">刷新样品</button></FeedbackNotice>
          <div v-else-if="reviewChecking" class="alert alert-info alert-border-left mb-2" role="status">{{ stageText('正在获取最新校核结果，请稍候…') }}</div>
          <template v-else-if="reviewCheckResult">
            <div class="alert alert-border-left mb-2" :class="reviewCheckResult.messages.some(message => message.tone === 'warning') ? 'alert-warning' : 'alert-info'">
              <ul class="list-unstyled mb-0"><li v-for="(message, index) in reviewCheckResult.messages" :key="index" class="d-flex gap-2" :class="{ 'mt-2': index > 0 }"><i class="flex-shrink-0" :class="message.tone === 'warning' ? 'ti ti-alert-triangle' : 'ti ti-info-circle'" aria-hidden="true"></i><span class="text-break">{{ message.text }}</span></li></ul>
            </div>
            <p class="text-muted small mb-0">{{ stageConfig.label }}时间：{{ new Date(reviewCheckResult.checkedAt).toLocaleString('zh-CN') }}</p>
          </template>
          <p v-else-if="!reviewCheckError" class="text-muted mb-0">{{ stageText('请先进行合规校核，阅读结果后再确认通过。') }}</p>
        </div>
      </section>
      </template>
      <ErrorNotice :error="checkError" />
      <template v-if="reportCheckMode && checkStep === 'check'" #pagination>
        <div class="px-3 py-2 border-top"><div class="form-check"><input id="report-review-confirmed" v-model="reviewReadConfirmed" type="checkbox" class="form-check-input" :disabled="!reviewCheckResult || !canCheck" /><label for="report-review-confirmed" class="form-check-label">{{ stageText('我已阅读并确认上述校核结果') }}</label></div></div>
      </template>
      <template #footer>
        <template v-if="checkStep === 'reject'">
          <button type="button" class="btn btn-light" :disabled="working" @click="checkStep = 'check'; checkError = ''">取消</button>
          <button type="button" class="btn btn-primary" :disabled="!canCheck || !rejectionReady" @click="confirmCheck('reject')">确定</button>
        </template>
        <template v-else-if="checkStep === 'next'">
          <button type="button" class="btn btn-light" :disabled="working" @click="checkStep = 'check'">返回</button>
          <button type="button" class="btn btn-primary" :disabled="!canApproveCheck || nextAction === 'transfer' && !recipient" @click="confirmCheck('check')">确定</button>
        </template>
        <template v-else>
        <button type="button" class="btn btn-light" :disabled="working" @click="checkOpen = false">取消</button>
        <button type="button" class="btn btn-outline-danger" :disabled="!canCheck" @click="rejectCheck">不通过</button>
        <button type="button" class="btn btn-primary" :disabled="!canApproveCheck" @click="approveCheck">通过</button>
        </template>
      </template>
    </BootstrapModal>
    <DataEntryPersonPicker v-if="recipientPicking && checkOpen" :sample-id="detail.sample.id" :role="stageConfig.role" :report-stage="reportStage" purpose="report-check" title="选择接收人" :value="recipient" :initial-scope="recipientScope" @scope="recipientScope = $event" @select="selectRecipient" @close="recipientPicking = false" />
    <RegistrationAttachmentManager :id="attachmentOpen ? detail.sample.id : undefined" kind="samples" :title="previewLayout || queryMode ? '查看附件' : '附件管理'" :readonly="readonlyMode || stale" @close="attachmentOpen = false" @changed="syncAttachments" />
    <DataEntryRecordsModal :sample-id="detail.sample.id" :mode="recordsMode" @close="recordsMode = undefined" />
  </template>
  <TemplateToast ref="toast" :message="success" tone="success" />
  <ConfirmationModal v-if="discard" title="放弃填写" :busy="working || originalBusy" @close="discard = ''">
    <p class="mb-0">尚有未保存的修改，是否放弃填写？</p>
    <template #footer><button type="button" class="btn btn-light" :disabled="working || originalBusy" @click="discard = ''">继续填写</button><button type="button" class="btn btn-danger" :disabled="working || originalBusy" @click="abandon">放弃填写</button></template>
  </ConfirmationModal>
</template>







