<template>
  <div v-if="completionFeedback && !entryPresentation.list.completingFromList" class="alert alert-warning" role="status">
    {{ completionFeedback }}
    <button v-if="unconfirmedCompletion.has(selectedNo)" type="button" class="btn btn-sm btn-light ms-2"
      :disabled="saving" @click="checkCompletion(selectedNo)">核对提交结果</button>
  </div>
  <EntryListPresentation v-if="!formOpen || entryPresentation.list.completingFromList" :context="entryPresentation.list" />
  <template v-else>
    <div v-if="detail?.testDataReviewRequired" class="alert alert-warning" role="alert">{{ detail.testDataReviewRequired.message }}</div>
    <EntryRecordPresentation :context="entryPresentation.record" />
  </template>
  <EsignWorkflowSelector v-if="signingChoiceReport === selectedNo && signingChoiceReport && !entryPresentation.list.completingFromList" :busy="saving" :message="completionFeedback"
    @close="signingChoiceReport = ''" @confirm="mode => finishDataEntry(signingChoiceReport, mode)" />
  <TemplateToast :message="entryPresentation.list.completingFromList || (saving && !formOpen && !signingChoiceReport) ? (completionFeedback || '录入提交中，请稍候…') : ''"
    :autohide="false" auto-show />

  <BootstrapModal :open="elnDraftOpen" title="导入电子原始记录审核结果" size="lg" scrollable @close="elnDraftOpen = false">
    <FeedbackNotice message="勾选后只写入当前检测数据表单；不会自动保存、完成检测或推进流程。" />
    <SchemaForm :model="t" :schema="elnImportSchema" :readonly="formReadOnly" />
    <template #footer><button class="btn btn-light" @click="elnDraftOpen = false">取消</button><button class="btn btn-primary" :disabled="formReadOnly || !elnSelectedPatches.length" @click="applyElnDraft">确认写入当前表单</button></template>
  </BootstrapModal>
  <BootstrapModal :open="coverPreviewOpen" :title="'完整报告预览' + (selected ? ' · ' + selected.reportNo : '')" size="xl" :loading="coverLoading" @close="coverPreviewOpen = false; clearCover()">
    <FeedbackNotice v-if="coverPreviewError" :message="coverPreviewError" tone="danger" />
    <DataEntryPreview :url="coverPdfUrl || ''" :name="(selected?.reportNo || 'report') + '.pdf'" type="application/pdf" title="完整报告 PDF" persistent hide-download />
    <template #footer><button class="btn btn-light" :disabled="coverLoading || !coverPdfUrl" @click="downloadCompleteReport">下载完整报告 PDF</button><button class="btn btn-light" @click="coverPreviewOpen = false; clearCover()">关闭</button></template>
  </BootstrapModal>
  <ConfirmationModal v-if="noSupplementConfirmOpen" title="确认无补充正文" :busy="compositionSaving || saving" @close="noSupplementConfirmOpen = false">
    <p>确认本报告无需补充正文？系统将直接生成正式报告预览，已勾选的其他附件仍会加入，原始记录不会加入。</p>
    <p>此操作不会跳过检测必填校验、审核或批准。</p>
    <template #footer><button class="btn btn-light" :disabled="compositionSaving || saving" @click="noSupplementConfirmOpen = false">取消</button><button class="btn btn-primary" :disabled="formReadOnly || compositionSaving || saving" @click="applyNoSupplement(true)">确认并生成 PDF</button></template>
  </ConfirmationModal>
  <BootstrapModal :open="pagesOpen" title="编辑报告内容（报告附加页）" size="lg" scrollable :busy="savingPages" @close="pagesOpen = false">
    <SchemaForm :model="editPages" :schema="reportAddendumSchema" :readonly="formReadOnly || savingPages">
      <template v-for="(_,i) in editPages" :key="i" #['remove-page-'+i]><button class="btn btn-light" :disabled="formReadOnly || savingPages" @click="editPages.splice(i,1)">删除本页</button></template>
    </SchemaForm>
    <template #footer><button class="btn btn-light" :disabled="formReadOnly || savingPages" @click="editPages.push({title:'',content:''})">新增一页</button><button class="btn btn-primary" :disabled="formReadOnly || savingPages" @click="savePages">保存</button><button class="btn btn-light" :disabled="savingPages" @click="pagesOpen = false">取消</button></template>
  </BootstrapModal>

</template>

<script setup lang="ts">
// BEGIN TEMPLATE REPORT IMPORTS
import {createListRequestState} from '../../platformUi/testing/listRequestState'
const entryListRequest=createListRequestState(),entryListState=entryListRequest.state
onBeforeUnmount(entryListRequest.dispose)
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import ConfirmationModal from '../../components/common/ConfirmationModal.vue'
import {elnDraftSchema,reportPagesSchema} from '../../platformUi/testing/entryAuxiliaryForms'
import EntryListPresentation from '../../platformUi/testing/EntryListPresentation.vue'
import EntryRecordPresentation from '../../platformUi/testing/EntryRecordPresentation.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import {createServerPage,fetchListPage,fetchListExport} from '../../platformUi/lists/serverPage'
import {createEntryPresentation} from '../../platformUi/testing/entryPresentation'
import {fetchEntryReferences} from '@/services/pipeline'
import {useEntryEditMode} from '../../platformUi/testing/entryEditMode'
import {createDataEntryReturn} from '../../platformUi/testing/dataEntryReturn'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import {createReportEntrySchema} from '../../platformUi/reportEntryForm'
import FormTabs from '../../components/forms/FormTabs.vue'
import FilePondUpload from '../../components/common/FilePondUpload.vue'
import AttachmentFileList from '../../components/common/AttachmentFileList.vue'
import {templateAttachments,runReportUpload,type ReportUploadRequest} from '../../platformUi/reportAttachments'
import type {FormSchema} from '../../types/forms'
import {nextTick} from 'vue'
// END TEMPLATE REPORT IMPORTS

import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import type { TechnicalSubproject } from '@/services/technicalSubprojects'
import { useRoute } from 'vue-router'
import { templateCapacityMessage } from '../../platformUi/testing/templateCapacityWarnings'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modules } from '@/data/modules'
import { reportWorkRows } from '@/data/mock'
import { demoWorkflowRows } from '@/data/moduleDemo'
import { reportDataStatus, reportDataStatusChoices } from '../../platformUi/reportDataStatus'
import { fetchReportRows, reportAction, type ReportRow } from '@/services/auth'
import { fetchReportDetail, type ReportDetailView } from '@/services/reports'
import { prepareReportQuery } from '@/services/reportAssurance'
import { PIPELINE_AVAILABLE, updateTestInfo, completeTestInfo, saveReportPages, changeTestComplete, fetchAuthorizedReportPeople, fetchReportDocumentContent, fetchReportDocumentPreflight, saveReportDocumentContent, downloadReportAuthoringTemplate, type AuthorizedReportPeople, type AuthorizedReportPerson, type ReportPageItem, type ReportDocumentContent, type ReportDocumentPreflight } from '@/services/pipeline'
import { fetchReportEquipment, searchStdLib, type EquipItem, type StdLibHit } from '@/services/quality'
import { completePreviewState, completeReportObjectUrl, deleteAttachment, listUploadedAttachments, uploadAttachment, type Attachment, type AttachmentCategory } from '@/services/attachments'
import { createElnLaunch, fetchElnDraft, fetchElnStatus, type ElnDraftPatch, type ElnReportStatus } from '@/services/eln'
import { useSessionStore } from '@/stores/session'
import EsignWorkflowSelector from '../components/EsignWorkflowSelector.vue'
import type { EsignWorkflow } from '@/services/pipeline'
import { readTestCompletion, TestCompletionUncertain } from '@/services/pipeline'
import { useCompletePreview } from '@/composables/useCompletePreview'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import ModuleCommandBar from '@/components/ModuleCommandBar.vue'
import ModuleContentCard from '@/components/ModuleContentCard.vue'
import FlatDatePicker from '@/components/FlatDatePicker.vue'
import AiVoiceDraft from '@/components/AiVoiceDraft.vue'
import type { AiFormPatch } from '@/services/ai'
import { isWorkflowDateBefore, isWorkflowDateValid } from '@/composables/workflowDate'
import { reportDataEntryScopeKey } from '@/composables/reportDataEntryRefresh'
import { equipmentCoversTestIntervals, equipmentValidityText, isLongTermEquipment } from '@/composables/equipmentValidity'

const route = useRoute()
const session = useSessionStore()
const available = PIPELINE_AVAILABLE
const pageName = computed(() => String(route.meta.pageName ?? '检测数据录入'))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pageKey = computed(() => String(route.meta.pageKey ?? 'data_entry'))
const pages = computed(() => modules.find((m) => m.key === 'testing')?.pages ?? [])
const initKeyword = computed(() => (typeof route.query.keyword === 'string' ? route.query.keyword : ''))

type WorkflowReportRow = ReportRow & {
  samplePickup?: { pickupTime?: string } | null
  workflowDates?: { samplePickupAt?: string }
}
const allRows = ref<WorkflowReportRow[]>([])
const entryPaging=createServerPage({presentation:'entry',sort:'code',direction:'asc',searchField:'reportCode',contains:initKeyword.value})
const entryPage=entryPaging.state
function entryPageQuery(){return {...entryPage.query,view:session.canCorrectBusinessData?'query':isChangePage.value?'data_change':'data_entry',...(session.canCorrectBusinessData&&entryPage.query.rowProjection==='active'?{handlingView:isChangePage.value?'data_change':'data_entry'}:{})}}
function setEntryQuery(q:Record<string,any>){entryPaging.setQuery({...q,presentation:'entry'})}
async function exportEntryRows(){return fetchListExport('/api/reports/query',entryPageQuery())}
const selectedNo = ref('')
const entryTableRef = ref<{ toggleRowSelection: (row: WorkflowReportRow) => void } | null>(null)
const selectedListRows = ref<WorkflowReportRow[]>([])
// 检测数据更改页（data_change）：退回待重传(校核/审核/批准退回) + 检测更改中(批准后更正)，附退回信息
// 检测数据录入页（data_entry）：样品已领取且处于明确的“检测录入中”。
const isChangePage = computed(() => pageKey.value === 'data_change')
const reportDetailView = computed<ReportDetailView>(() => (
  isChangePage.value ? 'data_change' : 'data_entry'
))
const entryRows = computed(() =>
  available ? allRows.value : allRows.value.filter((r) =>
    session.canCorrectBusinessData || (isChangePage.value
      ? r.status === '退回待重传' || r.status === '检测更改中'
      : (
        (r.status === '检测录入中' && r.sampleStatus === '已领取')
        || (
          r.status === '待审核'
          && (r.dataEntryCompletionAccount === session.account || session.account === 'admin' || (session.fullPlatformAuthority || session.roleKey === 'admin'))
        )
      )),
  ),
)
// 按关键词筛选（从任务查询跳转可带 keyword）
const keyword = ref(initKeyword.value)
const statusFilter = ref('')
const statusOptions = computed(() => reportDataStatusChoices(entryRows.value))
const filteredRows = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return entryRows.value.filter((r) => (
    (!kw || [r.reportNo, r.sampleNo, r.client, r.project].some((v) => String(v || '').toLowerCase().includes(kw)))
    && (!statusFilter.value || reportDataStatus(r) === statusFilter.value)
  ))
})
const selected = computed(() => entryRows.value.find((r) => r.reportNo === selectedNo.value))
const testPreviousDate = computed(() => selected.value?.samplePickup?.pickupTime || selected.value?.workflowDates?.samplePickupAt || '')
const isChangeRound = computed(() => selected.value?.status === '检测更改中')
const selectedListRow = computed(() => selectedListRows.value.length === 1 ? selectedListRows.value[0] : null)
const canUndoSelected = computed(() => Boolean(
  !isChangePage.value
  && selectedListRow.value?.status === '待审核'
  && selectedListRow.value.allowedActions?.includes('report.report_check.undo'),
))

async function load() {
  await entryListRequest.run(async () => {
    if (!available) return {rows:demoWorkflowRows as WorkflowReportRow[],total:demoWorkflowRows.length}
    const result=await fetchListPage<WorkflowReportRow>('/api/reports/query',entryPageQuery())
    return result
  }, result => { allRows.value = result.rows;entryPage.total=result.total })
}
// 权限资料刷新会用等值的新对象替换 dataScope。只监听语义范围签名，避免
// 一次 403 权限复核把正在编辑的整张表单反复重建。
const listScopeKey = computed(() => reportDataEntryScopeKey(
  session.dataScope,
  session.userName,
  isChangePage.value,
))


// 列表分页
const pageSize = 12
const tablePage = ref(1)
const tableHeight = ref(typeof window !== 'undefined' ? Math.max(360, window.innerHeight - 230) : 560)
const pagedRows = computed(() => filteredRows.value.slice((tablePage.value - 1) * pageSize, tablePage.value * pageSize))
watch([filteredRows, statusFilter], () => { if ((tablePage.value - 1) * pageSize >= filteredRows.value.length) tablePage.value = 1 })

// 点「数据录入/数据更改」开表单对话框（selectedNo 变化触发下方 watch 填表）
const formOpen = ref(false)
const requestedReadOnly = ref(false)
const { formReadOnly, adminEditing, canAdminEdit, toggleAdminEditing } = useEntryEditMode(() => ({
  open: formOpen.value, reportNo: selectedNo.value, account: session.account, route: route.path,
  canCorrect: session.canCorrectBusinessData, requestedReadOnly: requestedReadOnly.value,
  status: selected.value?.status || '', sampleStatus: selected.value?.sampleStatus || '',
}))
function openForm(row: ReportRow, readOnly = false) {
  if (!row) return
  requestedReadOnly.value = readOnly
  selectedNo.value = row.reportNo
  formOpen.value = true
}
function onListSelection(rows: WorkflowReportRow[]) {
  selectedListRows.value = rows
}
function toggleListRow(row: WorkflowReportRow) {
  entryTableRef.value?.toggleRowSelection(row)
}
function openSelectedForm(readOnly: boolean) {
  const row = selectedListRow.value
  if (!row) return
  openForm(row, readOnly)
}
function undoSelectedCompletion() {
  const row = selectedListRow.value
  if (row) void undoDataEntryCompletion(row)
}
const returnBusy = ref(false)
function canReturnReport(row: ReportRow | null | undefined): boolean {
  return Boolean(available && !isChangePage.value && row?.status === '检测录入中'
    && row.sampleStatus === '已领取' && row.allowedActions?.includes('testing.data_entry.return'))
}
const submitEntryReturn = createDataEntryReturn({
  busy: returnBusy,
  saving: () => saving.value,
  context: () => ({ account: session.account, scope: listScopeKey.value, path: route.path,
    formOpen: formOpen.value, formReportNo: selectedNo.value, formReadOnly: formReadOnly.value }),
  allowed: reportNo => canReturnReport(allRows.value.find(r => r.reportNo === reportNo)),
  prompt: async reportNo => {
    try {
      const result = await ElMessageBox.prompt(
        '请填写委托或样品信息需要修改的位置和原因。已保存的检测数据和附件保留；委托更改和合同评审完成后回到检测数据录入，无需重新入库、领取。当前未保存的输入不会随退回保存，如需保留请先取消并保存检测数据。',
        `退回委托/样品更改 · ${reportNo}`,
        { inputType: 'textarea', inputPlaceholder: '请输入退回原因', confirmButtonText: '确认退回',
          cancelButtonText: '取消', closeOnClickModal: false,
          inputValidator: value => Boolean(String(value || '').trim()) || '退回必须填写原因' },
      )
      return result.value
    } catch (error) {
      if (error === 'cancel' || error === 'close') return null
      throw error
    }
  },
  submit: (reportNo, note) => reportAction(reportNo, 'testing.data_entry.return', { note }),
  completed: async (reportNo, fromForm) => {
    if (fromForm) formOpen.value = false
    selectedNo.value = ''
    selectedListRows.value = []
    ElMessage.success(`${reportNo} 已退回委托/样品更改；合同评审通过后回到检测数据录入`)
    try {
      await load()
      if (entryListState.error) ElMessage.warning('退回已成功，但列表刷新失败，请重新查询；无需重复退回')
    } catch {
      ElMessage.warning('退回已成功，但列表刷新失败，请重新查询；无需重复退回')
    }
  },
  warning: message => ElMessage.warning(message),
  error: message => ElMessage.error(message),
})
async function returnToEntrust(row: ReportRow | null | undefined) {
  if (row) await submitEntryReturn(row.reportNo)
}
async function undoDataEntryCompletion(row: ReportRow) {
  try {
    await ElMessageBox.confirm(
      `确认撤销报告 ${row.reportNo} 的检测数据录入完成？撤销后可继续修改。`,
      '撤销完成',
      { type: 'warning' },
    )
  } catch { return }
  try {
    await reportAction(row.reportNo, 'report.report_check.undo')
    ElMessage.success('已撤销检测数据录入完成，可继续修改')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '撤销完成失败')
  }
}
// 退回信息文本（后端在退回时记录到 detail.returnInfo，随 to_row 带回行）
function returnText(row?: ReportRow | null): string {
  const ri = (row as unknown as { returnInfo?: { source?: string; by?: string; date?: string; note?: string } })?.returnInfo
  if (!ri) return ''
  return [ri.source, ri.by, ri.date, ri.note].filter(Boolean).join(' · ')
}
interface TestInterval { start: string; end: string }
interface DetectionCheckInput {
  judgmentDisplay?: {standardShowName?: boolean; standardTitleStyles?: Record<string, 'CN' | 'EN' | 'none'>; standardSeparatorText?: string}
  standard?: string
  standards?: string[]
  instrument?: string
  testStartDate?: string
  testDate?: string
  testIntervals?: TestInterval[]
  equipmentIds?: number[]
  equipmentDisplay?: Partial<{
    archiveNo: boolean
    spec: boolean
    maker: boolean
    factoryNo: boolean
  }>
  standardTitleStyles?: Record<string, 'CN' | 'EN' | 'none'>
  standardNames?: Record<string, string>
  standardRecords?: {id?: number; key: string; code: string; name: string}[]
  standardSeparatorText?: string
  equipmentSeparatorText?: string
  standardShowName?: boolean
  standardSeparator?: 'newline' | 'semicolon' | 'space'
  calibrationTime?: string
  calibrationPlace?: string
  temperature?: string
  humidity?: string
  pressure?: string
  resultStatus?: string
  unqualifiedParams?: string
  conclusion?: string
  remark?: string
  recordNo?: string
  result?: string
  people?: Record<string, { code?: string; name?: string }>
}
const t = reactive({
  judgmentDisplay: {standardShowName: true, standardTitleStyles: {} as Record<string, 'CN' | 'EN' | 'none'>, standardSeparatorText: '；'},
  standard: '',
  standards: [] as string[],
  standardTitleStyles: {} as Record<string, 'CN' | 'EN' | 'none'>,
  standardNames: {} as Record<string, string>,
  standardRecords: [] as {id?: number; key: string; code: string; name: string}[],
  standardSeparatorText: '；',
  equipmentSeparatorText: '；',
  standardShowName: false,
  standardSeparator: 'semicolon' as 'newline' | 'semicolon' | 'space',
  testIntervals: [{ start: '', end: '' }] as TestInterval[],
  equipmentIds: [] as number[],
  equipmentDisplay: { archiveNo: true, spec: true, maker: false, factoryNo: false },
  calibrationTime: '',
  calibrationPlace: '',
  temperature: '',
  humidity: '',
  pressure: '',
  primaryTester1Code: '',
  primaryTester2Code: '',
  reviewerCode: '',
  approverCode: '',
  conclusion: '',
  resultStatus: '',
  unqualifiedParams: '',
  recordNo: '',
  result: '',
  remark: '',
})
function applyVoiceDraft(patches: AiFormPatch[]) {
  for (const patch of patches) {
    if (Object.prototype.hasOwnProperty.call(t, patch.path)) {
      ;(t as unknown as Record<string, unknown>)[patch.path] = patch.value
    }
  }
}
const detail = ref<Awaited<ReturnType<typeof fetchReportDetail>>>(null)
const testEditVersion = ref<string>()
const technicalSelection = computed(() => {
  const value = detail.value?.rawSample?.detectionSubprojects
  return Array.isArray(value) ? value.filter((row): row is TechnicalSubproject => !!row && typeof row === 'object' && typeof row.name === 'string' && typeof row.id === 'number') : []
})
const equipment = ref<EquipItem[]>([])
const authorizedPeople = ref<AuthorizedReportPeople>({
  project: { id: 0, code: '', name: '' },
  testers: [],
  originalRecordReviewers: [],
  reviewers: [],
  approvers: [],
})
const standardOptions = ref<StdLibHit[]>([])
const standardLoading = ref(false)
const entryStaffDisplay = computed(() => {
  const saved = detail.value?.checkInput?.entryStaff
  if (saved && typeof saved === 'object') {
    const person = saved as { account?: string; name?: string }
    return [person.account, person.name].filter(Boolean).join(' / ') || '未记录'
  }
  return adminEditing.value ? '未记录' : `${session.account} / ${session.userName || session.account}`
})
const currentDepartment = computed(() => selected.value?.department || String(detail.value?.rawSample?.testDept || ''))
const isCalibrationReport = computed(() => {
  const raw = detail.value?.rawSample ?? {}
  return ['reportFormat', 'reportType', 'reportCategory'].some((key) => String(raw[key] || '').includes('校准'))
})
const hasCompleteIntervals = computed(() => t.testIntervals.length > 0 && t.testIntervals.every((item) => item.start && item.end))
const testerOptions = computed(() => authorizedPeople.value.testers)
const reviewerOptions = computed(() => authorizedPeople.value.reviewers)
const approverOptions = computed(() => authorizedPeople.value.approvers)
function personLabel(person: AuthorizedReportPerson) {
  return [person.name, person.code, person.title || person.position].filter(Boolean).join(' · ')
}
function standardLabel(item: StdLibHit) {
  return `${item.code}${item.name ? ` · ${item.name}` : ''}${item.status === '现行' ? '' : `（${item.status}）`}`
}
function splitStandardValues(value: unknown): string[] {
  const source = Array.isArray(value) ? value : String(value || '').split(/[、；;\n]+/)
  return [...new Set(source.map((item) => String(item || '').trim()).filter(Boolean))]
}
function sampleStandardValues(): string[] {
  const raw = detail.value?.rawSample ?? {}
  const fromArray = splitStandardValues(raw.testBases)
  const fromSample = fromArray.length ? fromArray : splitStandardValues(raw.testBasis)
  if (fromSample.length) return fromSample
  return splitStandardValues(summaryValue('实验信息', '检测依据', '执行标准', '判定标准'))
}
function setInheritedStandards(fallback: unknown = '') {
  t.standards = sampleStandardValues()
  if (!t.standards.length) t.standards = splitStandardValues(fallback)
  t.standard = t.standards.join('；')
}
async function loadStandardOptions(keyword = '') {
  if (formReadOnly.value || !['检测录入中', '退回待重传', '检测更改中'].includes(selected.value?.status || '')) {
    standardOptions.value = t.standardRecords.map(row => ({...row, authKind:'',singleList:false,status:'已保存',cma:false,cnas:false,useDepts:[],controlledNo:''}))
    return
  }
  const reportNo = selectedNo.value, epoch = preparationEpoch
  standardLoading.value = true
  try {
    const codes = t.standards.length ? t.standards : splitStandardValues(keyword)
    const ids = (detail.value?.rawSample?.standardItemIds || []) as number[]
    const rows: StdLibHit[] = []
    if (ids.length) {
      for (let start = 0; start < ids.length; start += 200) rows.push(...await searchStdLib('', currentDepartment.value, {ids:ids.slice(start,start+200),size:200}))
    } else {
      rows.push(...(await Promise.all(codes.map(code => searchStdLib(code, currentDepartment.value)))).flat())
    }
    if (ids.length && ids.some(id => !rows.some(row => row.id === id))) throw new Error('所选标准已删除或不在当前授权范围，请办理委托更改后重新选择')
    if (ids.length && rows.some(row => !codes.includes(row.code))) throw new Error('标准库编号或版本已变更，请办理委托更改确认检测依据；不能继续沿用旧编号')
    if (!formOpen.value || formReadOnly.value || selectedNo.value !== reportNo || preparationEpoch !== epoch) return
    t.standardNames = {}
    const merged = new Map<string, StdLibHit>()
    for (const code of codes) {
      const candidates = rows.filter(row => row.code === code)
      const selected = ids.length ? ids.map(id => candidates.find(row => row.id === id)).filter((row): row is StdLibHit => !!row)
        : (new Set(candidates.map(row => row.id)).size === 1 ? candidates.slice(0, 1) : [])
      for (const chosen of selected) { merged.set(`id:${chosen.id}`, chosen); t.standardNames[`id:${chosen.id}`] = chosen.name }
      if (selected.length === 1) t.standardNames[code] = selected[0].name
    }
    for (const code of codes) {
      if (![...merged.values()].some(row => row.code === code)) merged.set(code, { code, name: '', authKind: '', singleList: false, status: '无法确认，请重新选择', cma: false, cnas: false, useDepts: [], controlledNo: '' })
    }
    standardOptions.value = [...merged.values()]
    t.standardRecords = standardOptions.value.map(row => ({id: row.id, key: row.id ? `id:${row.id}` : row.code, code: row.code, name: row.name || ''}))
    if (ids.length) t.standardRecords.sort((a,b) => ids.indexOf(a.id || 0) - ids.indexOf(b.id || 0))
  } finally {
    standardLoading.value = false
  }
}
function equipmentCoversIntervals(item: EquipItem) {
  return equipmentCoversTestIntervals(item, t.testIntervals)
}
const equipmentDialogOpen = ref(false)
const equipmentKeyword = ref('')
const equipmentScopeFilter = ref<'selectable' | 'selected' | 'all'>('selectable')
const equipmentDraftIds = ref<number[]>([])
const selectedEquipmentItems = computed(() => equipment.value.filter((item) => t.equipmentIds.includes(item.id)))
const equipmentSelectionSummary = computed(() => {
  if (!hasCompleteIntervals.value) return '可先选择台账完整的仪器，填写区间后判断'
  if (!t.equipmentIds.length) return `请选择仪器设备（当前 ${selectableEquipmentCount.value} 台可选）`
  return `已选 ${t.equipmentIds.length} 台：${selectedEquipmentItems.value.map((item) => item.name).join('、') || '请重新核对设备'}`
})
const sortedEquipment = computed(() => [...equipment.value].sort((left, right) => {
  const activeIds = equipmentDialogOpen.value ? equipmentDraftIds.value : t.equipmentIds
  const leftSelected = activeIds.includes(left.id) ? 1 : 0
  const rightSelected = activeIds.includes(right.id) ? 1 : 0
  if (leftSelected !== rightSelected) return rightSelected - leftSelected
  const leftValid = equipmentCoversIntervals(left) ? 1 : 0
  const rightValid = equipmentCoversIntervals(right) ? 1 : 0
  return rightValid - leftValid || String(left.name || '').localeCompare(String(right.name || ''), 'zh-CN')
}))
const selectableEquipmentCount = computed(() => equipment.value.filter(equipmentCoversIntervals).length)
const longTermEquipmentCount = computed(() => equipment.value.filter((item) => (
  isLongTermEquipment(item) && equipmentCoversIntervals(item)
)).length)
const equipmentIntervalSummary = computed(() => {
  if (!hasCompleteIntervals.value) return '请先补全试验区间'
  const starts = t.testIntervals.map((item) => item.start).sort()
  const ends = t.testIntervals.map((item) => item.end).sort()
  return `${starts[0]} 至 ${ends[ends.length - 1]}`
})
const equipmentDialogRows = computed(() => {
  const keywordValue = equipmentKeyword.value.trim().toLowerCase()
  return sortedEquipment.value.filter((item) => {
    const selectedItem = equipmentDraftIds.value.includes(item.id)
    if (equipmentScopeFilter.value === 'selected' && !selectedItem) return false
    if (equipmentScopeFilter.value === 'selectable' && !selectedItem && !equipmentCoversIntervals(item)) return false
    if (!keywordValue) return true
    return [item.name, item.archiveNo, item.spec, item.factoryNo, item.maker, item.place, item.keeper]
      .some((value) => String(value || '').toLowerCase().includes(keywordValue))
  })
})
function equipmentValidityReason(item: EquipItem) {
  return equipmentValidityText(item, t.testIntervals)
}
function equipmentLabel(item: EquipItem) {
  const parts = [item.name]
  if (t.equipmentDisplay.archiveNo && item.archiveNo) parts.push(`档案号：${item.archiveNo}`)
  if (t.equipmentDisplay.spec && item.spec) parts.push(`型号：${item.spec}`)
  if (t.equipmentDisplay.maker && item.maker) parts.push(`厂商：${item.maker}`)
  if (t.equipmentDisplay.factoryNo && item.factoryNo) parts.push(`出厂编号：${item.factoryNo}`)
  return parts.join('；')
}
function equipmentStatusText(item: EquipItem) {
  if (!equipmentCoversIntervals(item)) return '不可选'
  return isLongTermEquipment(item) ? '长期有效' : '试验期有效'
}
function equipmentStatusType(item: EquipItem): 'success' | 'danger' {
  return equipmentCoversIntervals(item) ? 'success' : 'danger'
}
function openEquipmentSelector() {
  equipmentDraftIds.value = [...t.equipmentIds]
  equipmentKeyword.value = ''
  equipmentScopeFilter.value = 'selectable'
  equipmentDialogOpen.value = true
}
function toggleEquipmentDraft(item: EquipItem, checked: boolean) {
  if (checked && !equipmentCoversIntervals(item)) {
    ElMessage.warning(equipmentValidityReason(item))
    return
  }
  const next = new Set(equipmentDraftIds.value)
  if (checked) next.add(item.id)
  else next.delete(item.id)
  equipmentDraftIds.value = [...next]
}
function confirmEquipmentSelection() {
  t.equipmentIds = [...equipmentDraftIds.value]
  equipmentDialogOpen.value = false
}
function removeEquipment(id: number) {
  if (formReadOnly.value) return
  t.equipmentIds = t.equipmentIds.filter((itemId) => itemId !== id)
}
function addInterval() { t.testIntervals.push({ start: '', end: '' }) }
function removeInterval(index: number) { t.testIntervals.splice(index, 1) }
const uploaded = ref<Attachment[]>([])
const completedReportAttachments = computed(() => uploaded.value.filter((item) => (
  item.category === 'completed_report' || item.source === '完整报告正文'
)).filter((item) => item.active !== false && !item.superseded))
const supersededReportAttachments = computed(() => uploaded.value.filter((item) => item.superseded))
const reportPageAttachments = computed(() => uploaded.value.filter((item) => item.category === 'report_page' || item.source === '报告后续页'))
const rawRecordAttachments = computed(() => uploaded.value.filter((item) => item.source === '原始记录' || /原始记录|raw/i.test(`${item.source} ${item.name}`)))
const otherAttachments = computed(() => uploaded.value.filter((item) => (
  item.category === 'other'
  || (!completedReportAttachments.value.includes(item) && !supersededReportAttachments.value.includes(item) && !reportPageAttachments.value.includes(item) && !rawRecordAttachments.value.includes(item))
)))
const documentContent = ref<ReportDocumentContent | null>(null)
const documentPreflight = ref<ReportDocumentPreflight | null>(null)
const preparationError = ref('')
let preparationEpoch = 0
const { state: previewState, ready: previewReady, refresh: refreshPreview } = useCompletePreview(
  computed(() => selected.value?.reportNo || ''), reportDetailView,
  computed(() => formOpen.value && !formReadOnly.value && Boolean(documentPreflight.value?.hasCompletedReport || documentPreflight.value?.noSupplementBody)),
  computed(() => documentPreflight.value?.noSupplementSupported
    ? '请先上传完整报告正文，或在试验信息中确认“无需补充正文，使用平台模板生成报告”。'
    : '请先在“上传文件”中上传完整报告正文，再生成预览。'),
)
watch(() => previewState.value.sourceHash, () => {
  clearCover()
  coverPreviewRequestId += 1
})
const templateDownloading = ref(false)
const templateDownloaded = ref(false)
const compositionSaving = ref(false)
const attachmentDeleting = ref(false)
const attachmentDeleteBlocked = computed(() => attachmentDeleting.value || saving.value || uploading.value
  || compositionSaving.value || returnBusy.value || coverLoading.value || templateDownloading.value || savingPages.value)
let attachmentContextEpoch = 0
watch([formOpen, selectedNo, () => session.account, () => route.path, listScopeKey], () => {
  attachmentContextEpoch += 1
}, { flush: 'sync' })
onBeforeUnmount(() => { attachmentContextEpoch += 1 })
const includedOtherAttachmentIds = computed(() => documentContent.value?.compositionOptions?.includedOtherAttachmentIds ?? [])
const orderedOtherAttachments = computed(() => {
  const byId = new Map(otherAttachments.value.filter(item => item.id != null).map(item => [Number(item.id), item]))
  const selectedItems = includedOtherAttachmentIds.value.map(id => byId.get(id)).filter((item): item is Attachment => Boolean(item))
  const selectedSet = new Set(includedOtherAttachmentIds.value)
  return [...selectedItems, ...otherAttachments.value.filter(item => item.id == null || !selectedSet.has(Number(item.id)))]
})
const reportWorkflowStep = computed(() => {
  if (documentPreflight.value?.hasCompletedReport || documentPreflight.value?.noSupplementBody || completedReportAttachments.value.length) return 3
  if (templateDownloaded.value) return 2
  if (documentContent.value) return 1
  return 0
})
const uploading = ref(false)
const saving = ref(false)
const checksText = ref('')
const checksDanger = ref(false)
const emptyElnStatus = (): ElnReportStatus => ({ enabled: false, projectId: null, required: false, blocker: '', canLaunch: false, records: [] })
const elnStatus = ref<ElnReportStatus>(emptyElnStatus())
const elnLoading = ref(false)
const elnLaunching = ref(false)
const elnImporting = ref(false)
const elnDraftOpen = ref(false)
const elnDraftPatches = ref<ElnDraftPatch[]>([])
const elnSelectedPatches = ref<ElnDraftPatch['path'][]>([])
const elnFinalizedCount = computed(() => elnStatus.value.records.filter(item => item.status === 'FINALIZED').length)
const ELN_PATCH_LABELS: Record<ElnDraftPatch['path'], string> = {
  recordNo: '记录编号', result: '实测值', conclusion: '结论', resultStatus: '结论状态',
  unqualifiedParams: '不合格参数', remark: '备注',
}
function elnStatusText(value: ElnReportStatus['records'][number]['status']) {
  return ({ DRAFT: '草稿', PENDING_REVIEW: '待审核', REVIEWING: '审核中', REVIEW_REJECTED: '已退回', FINALIZED: '已定稿', CANCELED: '已撤销' } as Record<string, string>)[value] || value
}
function elnStatusTag(value: ElnReportStatus['records'][number]['status']): 'success' | 'warning' | 'danger' | 'info' {
  if (value === 'FINALIZED') return 'success'
  if (value === 'REVIEW_REJECTED') return 'danger'
  if (value === 'PENDING_REVIEW' || value === 'REVIEWING') return 'warning'
  return 'info'
}
function elnPatchLabel(path: ElnDraftPatch['path']) { return ELN_PATCH_LABELS[path] }
function displayDraftValue(value: unknown) { return value === null || value === undefined || value === '' ? '（空）' : String(value) }
// 真实模板封面+首页预览状态（声明在 immediate watch 之前，避免 TDZ）
const coverPdfUrl = ref('')
const coverLoading = ref(false)
const coverPreviewOpen = ref(false)
const coverPreviewError = ref('')
let coverPreviewRequestId = 0

function revokePreviewUrl(url: string) {
  if (url.startsWith('blob:')) URL.revokeObjectURL(url)
}
function clearCover() {
  coverPreviewRequestId += 1
  if (coverPdfUrl.value) { revokePreviewUrl(coverPdfUrl.value); coverPdfUrl.value = '' }
  coverPreviewError.value = ''
}

function summaryValue(title: string, ...labels: string[]) {
  const section = detail.value?.summary?.find((item) => item.title === title)
  for (const label of labels) {
    const value = section?.fields.find(([key]) => key === label)?.[1]
    if (value && value !== '—' && !value.includes('待检测人员录入')) return value
  }
  return ''
}

function resetForm() {
  Object.assign(t, {
    judgmentDisplay: {standardShowName: true, standardTitleStyles: {} as Record<string, 'CN' | 'EN' | 'none'>, standardSeparatorText: '；'},
    standard: '',
    standards: [],
    standardTitleStyles: {} as Record<string, 'CN' | 'EN' | 'none'>,
    standardNames: {} as Record<string, string>,
  standardRecords: [] as {id?: number; key: string; code: string; name: string}[],
    standardSeparatorText: '；',
    equipmentSeparatorText: '；',
    standardShowName: false,
    standardSeparator: 'semicolon',
    equipmentIds: [],
    equipmentDisplay: { archiveNo: true, spec: true, maker: false, factoryNo: false },
    calibrationTime: '',
    calibrationPlace: '',
    temperature: '',
    humidity: '',
    pressure: '',
    primaryTester1Code: '',
    primaryTester2Code: '',
    reviewerCode: '',
    approverCode: '',
    conclusion: '',
    resultStatus: '',
    unqualifiedParams: '',
    recordNo: '',
    result: '',
    remark: '',
  })
  t.testIntervals.splice(0, t.testIntervals.length, { start: '', end: '' })
}

function sourceRemark() {
  const raw = detail.value?.rawSample ?? {}
  return String(raw.homepageRemark || summaryValue('项目信息', '报告首页备注') || '')
}

function applyExistingInput() {
  const ci = (detail.value?.checkInput || {}) as DetectionCheckInput
  const raw = detail.value?.rawSample ?? {}
  const judgment = ci.judgmentDisplay ?? raw.judgmentDisplay as DetectionCheckInput['judgmentDisplay']
  t.judgmentDisplay = {standardShowName: judgment?.standardShowName ?? true, standardTitleStyles: {...judgment?.standardTitleStyles}, standardSeparatorText: judgment?.standardSeparatorText ?? '；'}
  setInheritedStandards(ci.standards || ci.standard)
  t.standardTitleStyles = { ...ci.standardTitleStyles }
  const historical = formReadOnly.value || !['检测录入中', '退回待重传', '检测更改中'].includes(selected.value?.status || '')
  t.standardNames = historical ? { ...(raw.standardNames as Record<string, string> || {}), ...ci.standardNames } : { ...ci.standardNames, ...(raw.standardNames as Record<string, string> || {}) }
  t.standardRecords = ((historical ? ci.standardRecords || raw.standardRecords : raw.standardRecords || ci.standardRecords) || []) as typeof t.standardRecords
  t.standardSeparatorText = ci.standardSeparatorText ?? ({ newline: '\n', space: ' ', semicolon: '；' }[ci.standardSeparator || 'semicolon'])
  t.equipmentSeparatorText = ci.equipmentSeparatorText ?? '；'
  t.standardShowName = Boolean(ci.standardShowName)
  t.standardSeparator = ci.standardSeparator === 'newline' || ci.standardSeparator === 'space'
    ? ci.standardSeparator : 'semicolon'
  const intervals = Array.isArray(ci.testIntervals) && ci.testIntervals.length
    ? ci.testIntervals
    : [{ start: ci.testStartDate || '', end: ci.testDate || '' }]
  t.testIntervals.splice(0, t.testIntervals.length, ...intervals.map((item) => ({ start: item.start || '', end: item.end || '' })))
  const sampleEquipmentIds = [raw.equipmentIds, raw.instrumentIds, raw.testEquipmentIds]
    .find((value) => Array.isArray(value)) as unknown[] | undefined
  t.equipmentIds = Array.isArray(ci.equipmentIds)
    ? ci.equipmentIds.map(Number)
    : (sampleEquipmentIds || []).map(Number).filter(Number.isFinite)
  Object.assign(t.equipmentDisplay, { archiveNo: true, spec: true, maker: false, factoryNo: false }, ci.equipmentDisplay || {})
  t.calibrationTime = ci.calibrationTime || ''
  t.calibrationPlace = ci.calibrationPlace || String(raw.testLocation || '') || summaryValue('实验信息', '校准地点', '检测地点') || summaryValue('样品信息', '检测地点')
  t.temperature = ci.temperature ?? summaryValue('实验信息', '温度')
  t.humidity = ci.humidity ?? summaryValue('实验信息', '湿度')
  t.pressure = ci.pressure ?? summaryValue('实验信息', '大气压力')
  t.primaryTester1Code = ci.people?.primaryTester1?.code || String(raw.primaryTester1Code || raw.testerCode || '')
  t.primaryTester2Code = ci.people?.primaryTester2?.code || String(raw.primaryTester2Code || '')
  t.reviewerCode = ci.people?.reviewer?.code || String(raw.reviewerCode || '')
  t.approverCode = ci.people?.approver?.code || String(raw.approverCode || '')
  t.conclusion = ci.conclusion || ''
  t.resultStatus = ({ 合格: '判定合格', 不合格: '判定不合格' } as Record<string, string>)[ci.resultStatus || ''] || ci.resultStatus || ''
  t.unqualifiedParams = ci.unqualifiedParams || ''
  t.recordNo = ci.recordNo || ''
  t.result = ci.result || ''
  t.remark = ci.remark ?? sourceRemark()
}

async function loadReferenceData() {
  if (!selected.value) return
  if (formReadOnly.value || !['检测录入中', '退回待重传', '检测更改中'].includes(selected.value?.status || '')) {
    const ci = (detail.value?.checkInput || {}) as DetectionCheckInput & {equipmentSnapshots?: EquipItem[]}
    equipment.value = (ci.equipmentSnapshots || []).map(item => ({...item, planCalDate:item.validUntil || item.planCalDate || ''}))
    const saved = ci.people || {}
    authorizedPeople.value = {project:{id:0,code:'',name:''}, testers:[saved.primaryTester1,saved.primaryTester2].filter(Boolean) as AuthorizedReportPerson[], reviewers:[saved.reviewer].filter(Boolean) as AuthorizedReportPerson[], approvers:[saved.approver].filter(Boolean) as AuthorizedReportPerson[], originalRecordReviewers:[]}
    return
  }
  const number = selected.value.reportNo, epoch = preparationEpoch, dates = JSON.stringify(t.testIntervals)
  const [peopleResult, equipmentResult, references] = await Promise.all([
    fetchAuthorizedReportPeople(selected.value.reportNo),
    // 独立仪器授权：本人部门、获授权部门及本报告已保存的设备。
    fetchReportEquipment(selected.value.reportNo, t.testIntervals),
    fetchEntryReferences(selected.value.reportNo),
  ])
  if (!formOpen.value || formReadOnly.value || selected.value?.reportNo !== number || epoch !== preparationEpoch || JSON.stringify(t.testIntervals) !== dates) throw new Error('报告或试验日期已变化，请重新刷新')
  authorizedPeople.value = peopleResult
  equipment.value = equipmentResult.rows
  if (detail.value) detail.value = {...detail.value, rawSample:{...detail.value.rawSample,...references}}
}

// 列表后台刷新会创建新的行对象；只在报告编号真的变化时初始化表单。
// 否则日期、标准等尚未保存的输入会被相同报告的新对象覆盖。
const preparationLoading = ref(false)
watch([formOpen, () => selected.value?.reportNo || '', () => session.account, () => route.path, formReadOnly], async ([open, selectedReportNo, account, path, readonly], previous) => {
  if (previous && open && previous[0] && selectedReportNo === previous[1] && account === previous[2] && path === previous[3] && readonly && !previous[4]) return
  const reportNo = open ? selectedReportNo : ''
  preparationLoading.value = true
  const epoch = ++preparationEpoch
  preparationError.value = ''
  documentPreflight.value = null
  checksText.value = ''
  clearCover()
  templateDownloaded.value = false
  coverPreviewOpen.value = false
  resetForm()
  elnStatus.value = emptyElnStatus()
  elnDraftOpen.value = false
  if (!reportNo) {
    detail.value = null
    uploaded.value = []
    documentContent.value = null
    documentPreflight.value = null
    preparationLoading.value = false
    return
  }
  try {
    const loaded = await fetchReportDetail(reportNo, reportDetailView.value)
    if (epoch !== preparationEpoch) return
    detail.value = loaded
    testEditVersion.value = loaded?.testEditVersion
    applyExistingInput()
    if (!formReadOnly.value) await prepareReportQuery(reportNo)
    if (epoch !== preparationEpoch) return
    const results = await Promise.allSettled([
      loadReferenceData(), loadStandardOptions(),
      listUploadedAttachments(reportNo, reportDetailView.value).then(rows => { if (epoch === preparationEpoch) uploaded.value = rows }),
      fetchReportDocumentContent(reportNo, reportDetailView.value).then(value => { if (epoch === preparationEpoch) documentContent.value = value }),
      fetchReportDocumentPreflight(reportNo, reportDetailView.value).then(value => { if (epoch === preparationEpoch) documentPreflight.value = value }),
      loadElnStatus(),
    ])
    const failed = results.find(result => result.status === 'rejected')
    if (failed?.status === 'rejected') throw failed.reason
  } catch (error) {
    if (epoch === preparationEpoch) preparationError.value = error instanceof Error ? error.message : '报告准备失败，请重试'
  } finally { if (epoch === preparationEpoch) preparationLoading.value = false }
}, { immediate: true })

const reportPages = computed<ReportPageItem[]>(() => detail.value?.reportPages ?? [])
const rawRecordsSection = ref<HTMLElement | null>(null)

function scrollToRawRecords() {
  rawRecordsSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function loadElnStatus() {
  if (!selected.value) return
  const reportNo = selected.value.reportNo
  elnLoading.value = true
  try {
    const result = await fetchElnStatus(reportNo)
    if (selected.value?.reportNo === reportNo) elnStatus.value = result
  } catch (error) {
    elnStatus.value = emptyElnStatus()
    ElMessage.error(error instanceof Error ? error.message : '电子原始记录状态加载失败')
  } finally {
    elnLoading.value = false
  }
}

async function launchEln() {
  if (!selected.value) return
  const target = window.open('', '_blank')
  elnLaunching.value = true
  try {
    const result = await createElnLaunch(selected.value.reportNo)
    if (target) target.location.replace(result.url)
    else ElMessage.warning('浏览器阻止了新窗口，请允许本站弹出窗口后重试')
  } catch (error) {
    target?.close()
    ElMessage.error(error instanceof Error ? error.message : '电子原始记录入口创建失败')
  } finally {
    elnLaunching.value = false
  }
}

async function prepareElnDraft() {
  if (!selected.value) return
  elnImporting.value = true
  try {
    const result = await fetchElnDraft(selected.value.reportNo)
    elnDraftPatches.value = result.patches
    elnSelectedPatches.value = result.patches.map(item => item.path)
    if (!result.patches.length) {
      ElMessage.info('当前没有可导入的已审核结构化结果')
      return
    }
    elnDraftOpen.value = true
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '读取电子原始记录结果失败')
  } finally {
    elnImporting.value = false
  }
}

function applyElnDraft() {
  const selectedPaths = new Set(elnSelectedPatches.value)
  for (const patch of elnDraftPatches.value) {
    if (selectedPaths.has(patch.path) && Object.prototype.hasOwnProperty.call(t, patch.path)) {
      ;(t as unknown as Record<string, unknown>)[patch.path] = patch.value
    }
  }
  elnDraftOpen.value = false
  ElMessage.success('已写入当前表单，请核对后自行保存')
}

async function refreshLinkedData() {
  if (!selected.value) return
  try {
    const number = selected.value.reportNo, epoch = preparationEpoch
    const loaded = await fetchReportDetail(number, reportDetailView.value)
    if (!formOpen.value || formReadOnly.value || selected.value?.reportNo !== number || preparationEpoch !== epoch) return
    detail.value = loaded
    setInheritedStandards(t.standards)
    await Promise.all([loadReferenceData(), loadStandardOptions()])
    ElMessage.success('已刷新委托、样品、标准、人员和设备关联数据，当前录入内容已保留')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '刷新失败')
  }
}

async function regenerateForm() {
  if (!selected.value) return
  try {
    await ElMessageBox.confirm(
      '重新生成会清空本窗口尚未保存的检测录入内容，并按最新委托、样品和基础库数据重新带入。是否继续？',
      '重新生成检测录入内容',
      { type: 'warning', confirmButtonText: '重新生成', cancelButtonText: '取消' },
    )
    detail.value = await fetchReportDetail(selected.value.reportNo, reportDetailView.value)
    resetForm()
    setInheritedStandards()
    t.remark = sourceRemark()
    await Promise.all([loadReferenceData(), loadStandardOptions()])
    ElMessage.success('已按最新关联数据重新生成')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error instanceof Error ? error.message : '重新生成失败')
  }
}

async function loadCompleteTemplatePdf(reportNo: string, download = false) {
  if (!previewReady.value) throw new Error('当前版本预览尚未就绪，请等待转换完成')
  return completeReportObjectUrl(reportNo, reportDetailView.value, download)
}

// 检测录入预览只接受后端按当前项目模板生成的完整 PDF。
async function previewCover() {
  if (!selected.value) return
  const reportNo = selected.value.reportNo
  coverPreviewOpen.value = true
  coverLoading.value = true
  clearCover()
  const requestId = ++coverPreviewRequestId
  try {
    const res = await loadCompleteTemplatePdf(reportNo)
    if (requestId !== coverPreviewRequestId || selected.value?.reportNo !== reportNo) {
      revokePreviewUrl(res.url)
      return
    }
    coverPdfUrl.value = res.url
  } catch (error) {
    if (requestId !== coverPreviewRequestId || selected.value?.reportNo !== reportNo) return
    const reason = error instanceof Error ? error.message : '真实模板 PDF 生成失败'
    coverPreviewError.value = `${reason}。系统不会使用文字摘要替代正式报告，请稍后重试。`
    ElMessage.error(coverPreviewError.value)
  } finally {
    if (requestId === coverPreviewRequestId) coverLoading.value = false
  }
}
async function downloadCompleteReport() {
  if (!selected.value) return
  coverLoading.value = true
  try {
    const result = await loadCompleteTemplatePdf(selected.value.reportNo, true)
    const a = document.createElement('a')
    a.href = result.url
    a.download = result.name
    document.body.appendChild(a); a.click(); a.remove()
    window.setTimeout(() => URL.revokeObjectURL(result.url), 1000)
    templateDownloaded.value = true
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '下载完整报告失败')
  } finally {
    coverLoading.value = false
  }
}

async function retryPreparation() {
  const no = selected.value?.reportNo
  if (!no) return
  const epoch = preparationEpoch
  try {
    if (!formReadOnly.value) await prepareReportQuery(no)
    if (epoch !== preparationEpoch) return
    await refreshDocumentWorkflow(() => epoch === preparationEpoch)
    if (epoch === preparationEpoch) { preparationError.value = ''; await refreshPreview(true) }
  } catch (e) { if (epoch === preparationEpoch) preparationError.value = e instanceof Error ? e.message : '报告准备失败' }
}

async function refreshDocumentWorkflow(isCurrent: () => boolean = () => true) {
  if (!selected.value) return
  const reportNo = selected.value.reportNo
  const [attachments, content, preflight] = await Promise.all([
    listUploadedAttachments(reportNo, reportDetailView.value),
    fetchReportDocumentContent(reportNo, reportDetailView.value),
    fetchReportDocumentPreflight(reportNo, reportDetailView.value),
  ])
  if (selected.value?.reportNo !== reportNo || !isCurrent()) return
  uploaded.value = attachments
  documentContent.value = content
  documentPreflight.value = preflight
}

function canRemoveAttachment(attachment: Attachment) {
  return !formReadOnly.value && session.canAction('report.attachment.upload')
    && Number.isSafeInteger(attachment.id) && Number(attachment.id) > 0
}

async function removeUploadedAttachment(attachment: Attachment) {
  if (!formOpen.value || !selected.value || !canRemoveAttachment(attachment) || attachmentDeleteBlocked.value) return
  const reportNo = selected.value.reportNo
  const id = attachment.id!
  const context = attachmentContextEpoch
  const current = () => context === attachmentContextEpoch && formOpen.value && selected.value?.reportNo === reportNo
  attachmentDeleting.value = true
  try {
    try {
      await ElMessageBox.confirm(`删除附件“${attachment.name}”？文件将移入回收区，不再并入正式报告，已有预览会重新核对。`, '删除附件', {
        type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
      })
    } catch { return }
    if (!current() || !canRemoveAttachment(attachment)
      || !uploaded.value.some(item => item.id === id)) return
    await deleteAttachment(id)
    if (!current()) return
    uploaded.value = uploaded.value.filter(item => item.id !== id)
    if (documentContent.value) {
      documentContent.value = { ...documentContent.value, compositionOptions: {
        ...documentContent.value.compositionOptions,
        includedOtherAttachmentIds: includedOtherAttachmentIds.value.filter(value => value !== id),
      } }
    }
    clearCover()
    void refreshPreview()
    ElMessage.success('附件已移入回收区')
    try { await refreshDocumentWorkflow(current) } catch {
      if (current()) ElMessage.warning('附件已删除，但列表状态刷新失败，请重新打开报告核对')
    }
  } catch (error) {
    if (current()) ElMessage.error(error instanceof Error ? error.message : '附件删除失败')
  } finally {
    attachmentDeleting.value = false
  }
}

async function downloadAuthoringTemplate() {
  if (!selected.value) return
  if (!formReadOnly.value && !(await saveDraft())) return
  templateDownloading.value = true
  try {
    const result = await downloadReportAuthoringTemplate(selected.value.reportNo)
    const anchor = document.createElement('a')
    anchor.href = result.url
    anchor.download = result.name
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(result.url), 1000)
    if (result.capacityWarnings.length) {
      ElMessage.warning(templateCapacityMessage(result.capacityWarnings))
    } else {
      ElMessage.success('完整报告 Word 模板已生成，请填写正文后原文件上传')
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '完整报告 Word 模板下载失败')
  } finally {
    templateDownloading.value = false
  }
}

async function persistIncludedOtherAttachments(ids: number[]) {
  if (!selected.value || !documentContent.value) return
  compositionSaving.value = true
  try {
    const updated: ReportDocumentContent = {
      ...documentContent.value,
      compositionOptions: { ...documentContent.value.compositionOptions, includedOtherAttachmentIds: [...ids] },
    }
    const preflight = await saveReportDocumentContent(selected.value.reportNo, updated)
    documentPreflight.value = preflight
    documentContent.value = preflight.content
    uploaded.value = await listUploadedAttachments(selected.value.reportNo, reportDetailView.value)
    void refreshPreview()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '附件组合顺序保存失败')
  } finally {
    compositionSaving.value = false
  }
}

function isOtherIncluded(attachment: Attachment) {
  return attachment.id != null && includedOtherAttachmentIds.value.includes(Number(attachment.id))
}

const noSupplementConfirmOpen = ref(false)
const noSupplementRequestNo = ref('')

function confirmNoSupplement(value: boolean) {
  if (!selected.value || formReadOnly.value || compositionSaving.value) return
  noSupplementRequestNo.value = selected.value.reportNo
  if (value) noSupplementConfirmOpen.value = true
  else void applyNoSupplement(false)
}

const supportsExtendedTemplate = computed(() => {
  const kind = documentPreflight.value?.templateSelection?.kind
  if (kind) return ['product', 'sampling'].includes(kind)
  return ['产品报告', '抽样报告'].includes(String(detail.value?.rawSample?.reportType || '产品报告'))
})

async function saveDocumentOption(key: 'reportLanguage' | 'reportTemplateVariant' | 'preserveUploadedReport', value: unknown) {
  const reportNo = selected.value?.reportNo
  if (!reportNo || !documentContent.value || formReadOnly.value || compositionSaving.value || uploading.value) return
  if (key === 'preserveUploadedReport' && session.roleKey !== 'admin' && session.account !== 'admin') return
  if (key === 'preserveUploadedReport' ? typeof value !== 'boolean' : typeof value !== 'string') return
  compositionSaving.value = true
  try {
    const options = { ...documentContent.value.compositionOptions, [key]: value }
    if (key === 'preserveUploadedReport' && value === true) options.noSupplementBody = false
    const preflight = await saveReportDocumentContent(reportNo, { ...documentContent.value, compositionOptions: options })
    if (selected.value?.reportNo !== reportNo) return
    documentPreflight.value = preflight
    documentContent.value = preflight.content
    clearCover()
    void refreshPreview()
    ElMessage.success('报告模板选项已保存，系统将生成新版本预览')
  } catch (error) {
    if (selected.value?.reportNo === reportNo) ElMessage.error(error instanceof Error ? error.message : '模板选项保存失败')
  } finally {
    compositionSaving.value = false
  }
}

async function applyNoSupplement(value: boolean) {
  const reportNo = selected.value?.reportNo
  noSupplementConfirmOpen.value = false
  if (!reportNo || reportNo !== noSupplementRequestNo.value || !documentContent.value || compositionSaving.value || formReadOnly.value) return
  if (value) {
    if (selected.value?.reportNo !== reportNo || !(await persistTestInfo(false))) return
  }
  if (selected.value?.reportNo !== reportNo || !documentContent.value) return
  compositionSaving.value = true
  try {
    const preflight = await saveReportDocumentContent(reportNo, {
      ...documentContent.value,
      compositionOptions: { ...documentContent.value.compositionOptions, noSupplementBody: value },
    })
    if (selected.value?.reportNo !== reportNo) return
    documentPreflight.value = preflight
    documentContent.value = preflight.content
    ElMessage.success(value ? '已确认无补充正文' : '已取消无补充确认，请上传完整报告')
    void refreshPreview()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '补充正文确认保存失败')
  } finally {
    compositionSaving.value = false
  }
}

function toggleOtherAttachment(attachment: Attachment, checked: boolean) {
  if (attachment.id == null || !attachment.mergeEligible) return
  const id = Number(attachment.id)
  const next = includedOtherAttachmentIds.value.filter(value => value !== id)
  if (checked) next.push(id)
  void persistIncludedOtherAttachments(next)
}

function moveOtherAttachment(attachment: Attachment, offset: number) {
  if (attachment.id == null) return
  const ids = [...includedOtherAttachmentIds.value]
  const index = ids.indexOf(Number(attachment.id))
  const target = index + offset
  if (index < 0 || target < 0 || target >= ids.length) return
  ;[ids[index], ids[target]] = [ids[target], ids[index]]
  void persistIncludedOtherAttachments(ids)
}

async function doUpload(opt: ReportUploadRequest, category: AttachmentCategory) {
  if (!selected.value) return
  const reportNo = selected.value.reportNo
  uploading.value = true
  try {
    await uploadAttachment(reportNo, opt.file, category)
    if (selected.value?.reportNo !== reportNo) return
    await refreshDocumentWorkflow()
    void refreshPreview()
    ElMessage.success('已上传')
    opt.onSuccess?.()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '上传失败')
    opt.onError?.(e)
  } finally {
    uploading.value = false
  }
}
async function uploadCompletedReport(opt: ReportUploadRequest) {
  if (completedReportAttachments.value.length) {
    try {
      await ElMessageBox.confirm('重新上传会将当前完整报告标记为“已替代”，历史文件仍保留。是否继续？', '替换完整报告', { type: 'warning' })
    } catch { return }
  }
  return doUpload(opt, 'completed_report')
}
function uploadRawRecord(opt: ReportUploadRequest) { return doUpload(opt, 'raw_record') }
function uploadOtherAttachment(opt: ReportUploadRequest) { return doUpload(opt, 'other') }

async function persistTestInfo(validateForCompletion: boolean, completing = false): Promise<boolean> {
  const row = selected.value
  if (!row || !formOpen.value || formReadOnly.value || saving.value) return false
  const administratorEditing = adminEditing.value
  if (validateForCompletion && (!t.standards.length || !hasCompleteIntervals.value || !t.equipmentIds.length)) {
    const message = '检测标准、完整试验时间区间和仪器设备为必填'
    if (completing) completionFeedback.value = message
    ElMessage.warning(message)
    return false
  }
  if (validateForCompletion && t.resultStatus === '判定不合格' && !t.unqualifiedParams.trim()) {
    const message = '判定不合格时必须填写不合格参数'
    if (completing) completionFeedback.value = message
    ElMessage.warning(message)
    return false
  }
  if (validateForCompletion && isCalibrationReport.value && !t.calibrationTime) {
    const message = '校准报告必须填写校准时间'
    if (completing) completionFeedback.value = message
    ElMessage.warning(message)
    return false
  }
  const starts = t.testIntervals.map((part) => part.start).filter(Boolean).sort()
  const ends = t.testIntervals.map((part) => part.end).filter(Boolean).sort()
  const testStartDate = starts[0] || ''
  const testEndDate = ends[ends.length - 1] || ''
  const intervalVersion = JSON.stringify(t.testIntervals)
  saving.value = true
  try {
    await Promise.all([loadReferenceData(), loadStandardOptions()])
    if (selected.value?.reportNo !== row.reportNo || !formOpen.value || formReadOnly.value) return false
    if (JSON.stringify(t.testIntervals) !== intervalVersion) throw new Error('试验日期已变化，请重新保存')
    const selectedEquipment = equipment.value.filter((item) => t.equipmentIds.includes(item.id))
    const invalidEquipment = selectedEquipment.filter((item) => !equipmentCoversIntervals(item))
    if (validateForCompletion && (selectedEquipment.length !== t.equipmentIds.length || invalidEquipment.length)) {
      const message = '所选仪器设备已失效或校准有效期不能覆盖全部试验区间，请重新选择'
      if (completing) completionFeedback.value = message
      ElMessage.warning(message)
      return false
    }
    await prepareReportQuery(row.reportNo)
    const savedInfo = await updateTestInfo(row.reportNo, {
      testEditVersion: testEditVersion.value,
      judgmentDisplay: {...t.judgmentDisplay, standardTitleStyles: {...t.judgmentDisplay.standardTitleStyles}},
      validateForCompletion,
      standard: t.standard,
      standards: [...t.standards],
      instrument: selectedEquipment.map(equipmentLabel).join('、'),
      testStartDate,
      testEndDate,
      testIntervals: t.testIntervals.map((part) => ({ ...part })),
      equipmentIds: [...t.equipmentIds],
      equipmentDisplay: { ...t.equipmentDisplay },
      standardTitleStyles: { ...t.standardTitleStyles },
      standardSeparatorText: t.standardSeparatorText,
      equipmentSeparatorText: t.equipmentSeparatorText,
      standardShowName: t.standardShowName,
      standardSeparator: t.standardSeparator,
      calibrationTime: t.calibrationTime,
      calibrationPlace: t.calibrationPlace,
      temperature: t.temperature,
      humidity: t.humidity,
      pressure: t.pressure,
      primaryTester1Code: t.primaryTester1Code,
      primaryTester2Code: t.primaryTester2Code,
      reviewerCode: t.reviewerCode,
      approverCode: t.approverCode,
      conclusion: t.conclusion,
      resultStatus: t.resultStatus,
      unqualifiedParams: t.unqualifiedParams,
      recordNo: t.recordNo,
      result: t.result,
      remark: t.remark,
    }, administratorEditing)
    if (selected.value?.reportNo !== row.reportNo || !formOpen.value) return false
    testEditVersion.value = savedInfo.testEditVersion
    if (validateForCompletion) {
      const all = JSON.stringify(savedInfo.checks ?? [])
      checksDanger.value = all.includes('danger') || all.includes('不在库内')
      checksText.value = checksDanger.value ? '三库校验：存在不通过项（标准不在库/仪器失效），完成后将标记超范围' : '三库校验：通过'
      if (!completing) ElMessage.success('检测数据已保存，三库校验已完成')
    } else {
      checksDanger.value = false
      checksText.value = '检测数据草稿已保存；保存并完成检测时再执行完整校验。'
      ElMessage.success(savedInfo.notice ? `检测数据草稿已保存；${savedInfo.notice}` : '检测数据草稿已保存')
    }
    if (!completing) {
      const current = () => formOpen.value && selected.value?.reportNo === row.reportNo
      try {
        const updated = await fetchReportDetail(row.reportNo, reportDetailView.value)
        if (current()) {
          detail.value = updated
          await Promise.all([loadElnStatus(), refreshDocumentWorkflow(current)])
        }
        if (current()) { preparationError.value = ''; void refreshPreview(true) }
      } catch (error) {
        if (current()) preparationError.value = `检测数据已保存，关联资料刷新失败。${error instanceof Error ? error.message : ''}`
      }
    }
    return true
  } catch (e) {
    const message = e instanceof Error ? e.message : '保存失败'
    if (completing) completionFeedback.value = message
    ElMessage.error(message)
    return false
  } finally {
    saving.value = false
  }
}
async function saveDraft() {
  return persistTestInfo(false)
}
const signingChoiceReport = ref('')
const completionFeedback = ref('')
const unconfirmedCompletion = reactive(new Map<string, 'data_entry' | 'data_change'>())
watch([selectedNo, () => route.path], () => {
  completionFeedback.value = unconfirmedCompletion.has(selectedNo.value) ? '上次完成请求未收到回执，请先核对提交结果。' : ''
  signingChoiceReport.value = ''
}, { flush: 'sync' })

watch(() => session.account, () => {
  unconfirmedCompletion.clear()
  signingChoiceReport.value = ''
  completionFeedback.value = ''
}, { flush: 'sync' })

async function checkCompletion(reportNo: string) {
  const view = unconfirmedCompletion.get(reportNo)
  if (!view || saving.value || selectedNo.value !== reportNo) return
  saving.value = true
  completionFeedback.value = '检测数据已保存。完成请求未收到回执，正在核对服务器状态。'
  try {
    const state = await readTestCompletion(reportNo, view)
    if (selectedNo.value !== reportNo) return
    if (state.stillEditable) {
      unconfirmedCompletion.delete(reportNo)
      completionFeedback.value = `服务器目前仍显示「${state.status}」。如需再次提交，请确认后重新点击完成。`
      return
    }
    unconfirmedCompletion.delete(reportNo)
    await closeCompletedEntry(state.esignPending
      ? '服务器已记录完成确认，请由主检本人完成电子签署。'
      : `已核对服务器，报告当前为「${state.status}」。`, state.esignPending)
  } catch (error) {
    if (selectedNo.value === reportNo) completionFeedback.value = `提交结果仍待核对。${error instanceof Error ? error.message : '请稍后重试。'}`
  } finally { saving.value = false }
}

async function closeCompletedEntry(message: string, esignPending?: boolean, esignPrepareError?: string) {
  signingChoiceReport.value = ''
  formOpen.value = false
  selectedNo.value = ''
  if (esignPrepareError) ElMessage.warning(`${message}。签署准备未完成：${esignPrepareError}`)
  else ElMessage.success(message)
  if (esignPending) {
    await nextTick()
    window.dispatchEvent(new Event('esign-stage-confirmed'))
  }
  await load()
  if (entryListState.error) ElMessage.warning('已收到服务器结果，列表刷新失败，请重新查询。')
}

async function saveAndDone() {
  const row = selected.value
  if (!row || saving.value) return false
  if (unconfirmedCompletion.has(row.reportNo)) { await checkCompletion(row.reportNo); return }
  completionFeedback.value = `${row.reportNo} 正在保存检测数据并校验。`
  if (!(await persistTestInfo(true, true))) return false
  return finishDataEntry(row.reportNo)
}
async function finishDataEntry(reportNo: string, mode?: EsignWorkflow) {
  if (saving.value || selectedNo.value !== reportNo || (formOpen.value ? formReadOnly.value : !mode)) return false
  if (unconfirmedCompletion.has(reportNo)) { await checkCompletion(reportNo); return }
  const view = reportDetailView.value
  saving.value = true
  completionFeedback.value = '检测数据已保存，正在核对报告预览。'
  try {
    const preview = await completePreviewState(reportNo, view)
    if (selectedNo.value !== reportNo || (formOpen.value ? formReadOnly.value : !mode)) return false
    if (preview.status !== 'ready') throw new Error('请先打开最新完整报告预览并点击“报告确认”，再完成录入')
    completionFeedback.value = '检测数据已保存，正在提交录入完成。'
    const result = await completeTestInfo(reportNo, mode)
    if (result.esignWorkflowRequired) {
      completionFeedback.value = ''
      signingChoiceReport.value = reportNo
      return
    }
    await closeCompletedEntry(result.esignPending ? `${reportNo} 已提交录入，等待主检签署` : `检测数据录入完成，已进入「${result.status}」`, result.esignPending, result.esignPrepareError)
    return true
  } catch (e) {
    if (e instanceof TestCompletionUncertain) {
      unconfirmedCompletion.set(reportNo, 'data_entry')
      signingChoiceReport.value = ''
    } else {
      completionFeedback.value = `检测数据已保存，录入尚未完成。${e instanceof Error ? e.message : '请稍后重试。'}`
      return false
    }
  } finally {
    saving.value = false
  }
  await checkCompletion(reportNo)
}
// 检测更改完成（批准后更改）：先保存本次改动（有填则保存），再回到待审核
async function completeChange() {
  const row = selected.value
  if (!row || saving.value || !formOpen.value || formReadOnly.value) return false
  if (unconfirmedCompletion.has(row.reportNo)) { await checkCompletion(row.reportNo); return }
  completionFeedback.value = `${row.reportNo} 正在保存检测数据并校验。`
  if (!(await persistTestInfo(true, true))) return false
  if (!formOpen.value || formReadOnly.value || selected.value?.reportNo !== row.reportNo) {
    throw new Error('报告已切换，本次完成操作已取消')
  }
  saving.value = true
  completionFeedback.value = '检测数据已保存，正在核对最新报告预览并提交检测更改。'
  try {
    const preview = await completePreviewState(row.reportNo, reportDetailView.value)
    if (!formOpen.value || formReadOnly.value || selected.value?.reportNo !== row.reportNo) {
      throw new Error('报告已切换，本次完成操作已取消')
    }
    if (preview.status !== 'ready') {
      void refreshPreview(true)
      throw new Error('请先打开最新完整报告预览并点击“报告确认”，再完成检测更改')
    }
    const result = await changeTestComplete(row.reportNo)
    await closeCompletedEntry(result.esignPending ? result.message || '本节点已确认，等待主检签署。' : `检测更改完成，已进入「${result.status}」`, result.esignPending, result.esignPrepareError)
    return true
  } catch (e) {
    if (!(e instanceof TestCompletionUncertain)) {
      completionFeedback.value = `检测数据已保存，更改尚未提交。${e instanceof Error ? e.message : '请稍后重试。'}`
      return false
    }
    unconfirmedCompletion.set(row.reportNo, 'data_change')
  } finally {
    saving.value = false
  }
  await checkCompletion(row.reportNo)
}

// 报告附加页
const pagesOpen = ref(false)
const savingPages = ref(false)
const editPages = ref<ReportPageItem[]>([])
function openPages() {
  if (formReadOnly.value || !formOpen.value || attachmentDeleting.value) return
  editPages.value = reportPages.value.map((p) => ({ ...p }))
  if (!editPages.value.length) editPages.value = [{ title: '', content: '' }]
  pagesOpen.value = true
}
async function savePages() {
  if (formReadOnly.value || !formOpen.value || attachmentDeleting.value) return
  const row = selected.value
  if (!row) return
  savingPages.value = true
  try {
    await saveReportPages(row.reportNo, editPages.value.filter((p) => p.title.trim() || p.content.trim()))
    detail.value = await fetchReportDetail(row.reportNo, reportDetailView.value)
    ElMessage.success('报告内容已保存')
    pagesOpen.value = false
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    savingPages.value = false
  }
}

// BEGIN TEMPLATE REPORT ADAPTER
const reportEntrySchema = computed(() => createReportEntrySchema({isCalibrationReport:isCalibrationReport.value,entryStaffDisplay:entryStaffDisplay.value}))
const reportEntryTab=ref('information')
const reportEntryTabs=[{key:'information',label:'报告信息',tabId:'report-information-tab',panelId:'report-information-panel'},{key:'files',label:'完整报告与附件',tabId:'report-files-tab',panelId:'report-files-panel'}]
watch(formOpen,open=>{if(open)reportEntryTab.value='information'})
async function showReportFiles(){reportEntryTab.value='files';await nextTick();scrollToRawRecords()}
const reportPreparationSchema=computed<FormSchema<typeof t>>(()=>({sections:[{id:'report-preparation',title:'报告准备',fields:[
 {id:'report-preparation-actions',label:'准备操作',ownLabel:true,width:'col-12',control:'custom',slot:'preparation'},
 {id:'report-language',label:'报告语言',control:'select',visible:!!documentContent.value,disabled:formReadOnly.value||compositionSaving.value||uploading.value||isCalibrationReport.value,options:[{label:'中文',value:'CN'},{label:'英文',value:'EN'}],binding:{get:()=>documentContent.value?.compositionOptions.reportLanguage||documentPreflight.value?.templateSelection?.language||'CN',set:(_model,value)=>{void saveDocumentOption('reportLanguage',value)}}},
 {id:'report-template-variant',label:'封面首页版式',control:'select',visible:!!documentContent.value,disabled:formReadOnly.value||compositionSaving.value||uploading.value,options:[{label:'标准版',value:'Standard'},...(supportsExtendedTemplate.value?[{label:'扩展版（长首页／两页）',value:'Extended'}]:[])],binding:{get:()=>documentContent.value?.compositionOptions.reportTemplateVariant||documentPreflight.value?.templateSelection?.variant||'Standard',set:(_model,value)=>{void saveDocumentOption('reportTemplateVariant',value)}}},
 {id:'report-preserve-uploaded',label:'保留上传完整报告（管理员）',control:'checkbox',visible:!!documentContent.value&&(session.roleKey === 'admin' || session.account === 'admin'),disabled:formReadOnly.value||compositionSaving.value||uploading.value,binding:{get:()=>documentContent.value?.compositionOptions.preserveUploadedReport===true,set:(_model,value)=>{void saveDocumentOption('preserveUploadedReport',value)}}},
]}]}))
const reportFilesSchema:FormSchema<typeof t>={sections:[{id:'report-files-eln',title:"电子原始记录",fields:[],slot:'eln'},
{id:'report-upload-section',title:'完整报告与附件',fields:[{id:'report-upload-0',label:"完整报告",control:'custom',slot:'upload-0'},{id:'report-upload-1',label:"其他附件",control:'custom',slot:'upload-1'},{id:'report-upload-2',label:"原始记录",control:'custom',slot:'upload-2'}]},
{id:'report-files-composition',title:"报告合成说明",fields:[],slot:'composition'},
{id:'report-attachment-lists',title:'附件记录',fields:[{id:'report-list-0',label:'附件列表',ownLabel:true,width:'col-12',control:'custom',slot:'list-0',visible:()=>completedReportAttachments.value.length>0},{id:'report-list-1',label:'附件列表',ownLabel:true,width:'col-12',control:'custom',slot:'list-1',visible:()=>supersededReportAttachments.value.length>0},{id:'report-list-2',label:'附件列表',ownLabel:true,width:'col-12',control:'custom',slot:'list-2',visible:()=>reportPageAttachments.value.length>0},{id:'report-list-3',label:'附件列表',ownLabel:true,width:'col-12',control:'custom',slot:'list-3',visible:()=>rawRecordAttachments.value.length>0},{id:'report-list-4',label:'附件列表',ownLabel:true,width:'col-12',control:'custom',slot:'list-4',visible:()=>orderedOtherAttachments.value.length>0}],visible:()=>uploaded.value.length>0}]}
const entryPresentation = createEntryPresentation(reactive({serverPaging:available,entryPage,setEntryQuery,exportEntryRows,entryListState,t,selected,detail,formOpen,formReadOnly,adminEditing,canAdminEdit,toggleAdminEditing,preparationLoading,preparationError,completionFeedback,entryRows,statusOptions,pageName,route,session,isChangePage,isChangeRound,isCalibrationReport,entryStaffDisplay,currentDepartment,reportDetailView,equipment,authorizedPeople,standardOptions,standardLoading,testerOptions,reviewerOptions,approverOptions,documentContent,documentPreflight,supportsExtendedTemplate,uploaded,completedReportAttachments,orderedOtherAttachments,rawRecordAttachments,includedOtherAttachmentIds,reportPageAttachments,previewState,previewReady,elnStatus,elnFinalizedCount,saving,uploading,compositionSaving,attachmentDeleting,returnBusy,nextTick,load,onListSelection,openSelectedForm,canReturnReport,returnToEntrust,undoDataEntryCompletion,equipmentCoversIntervals,equipmentValidityReason,saveDocumentOption,saveDraft,saveAndDone,completeChange,persistTestInfo,refreshLinkedData,regenerateForm,downloadAuthoringTemplate,refreshPreview,persistIncludedOtherAttachments,uploadCompletedReport,uploadOtherAttachment,uploadRawRecord,removeUploadedAttachment,canRemoveAttachment,loadElnStatus,launchEln,prepareElnDraft,elnStatusText,openPages,confirmNoSupplement,toggleOtherAttachment,isOtherIncluded}))
const elnImportSchema=computed(()=>elnDraftSchema(reactive({elnDraftPatches,elnPatchLabel,displayDraftValue,t,elnSelectedPatches})))
const reportAddendumSchema=computed(()=>reportPagesSchema({editPages:editPages.value}))
// END TEMPLATE REPORT ADAPTER
watch(()=>JSON.stringify([listScopeKey.value,entryPage.query]),()=>void load(),{immediate:true})
</script>
