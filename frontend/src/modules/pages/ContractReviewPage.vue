<template>
  <RegistrationPresentation :model="reviewListPresentation">
    <template #sample-finance><ManualFinanceAction :report-no="reviewListPresentation.selectedSamples.length === 1 ? reviewListPresentation.selectedSamples[0] : ''" mode="send" /></template>
  </RegistrationPresentation>

  <PipelineWizard v-model="parentViewOpen" mode="entrust" :edit-entrust="parentView" read-only />
  <PipelineWizard v-model="editOpen" :mode="editMode" :department="session.dataScope.department"
    :change-report-no="editReportNo" :edit-entrust="editParent" in-place detail-view="contract_review"
    @updated="loadReviewLists" @entrust-updated="loadReviewLists" />
  <BootstrapModal :open="formOpen" :title="(formReadOnly ? '查看合同评审' : '合同评审') + ' · ' + (selectedReport?.reportNo || '')" size="xl" scrollable :busy="reviewBusy" @close="formOpen = false">
    <LoadState :loading="reviewDetailLoading" :error="reviewDetailError" has-data />
    <FeedbackNotice v-if="formReadOnly" message="只读查看" />
    <FeedbackNotice v-if="cmaScopeWarn" message="盖章含 CMA，但检测依据超出一单一库范围，请核实授权范围。" />
    <SchemaForm v-if="selectedReport" :model="form" :schema="contractReviewSchema" :readonly="formReadOnly || reviewBusy" />
    <template #footer>
      <button class="btn btn-light" :disabled="reviewBusy" @click="viewReportDetail(selectedReport!.reportNo, 'contract_review', selectedReport!.reportNo + ' · 完整委托/样品信息')">查看完整信息</button>
      <button class="btn btn-light" :disabled="reviewBusy || formReadOnly" @click="openAttachmentManager">附件管理</button>
      <button v-if="!formReadOnly && session.canAction('report.contract_review.return')" class="btn btn-light" :disabled="reviewBusy" @click="submit('return')">退回（不通过）</button>
      <button v-if="!formReadOnly && session.canAction('report.contract_review.pass')" class="btn btn-primary" :disabled="!canPass || reviewBusy" :title="!canPass ? '还需确认：' + [...missingNames, ...sealMissingNames].join('、') : undefined" @click="submit('pass')">评审通过</button>
      <button class="btn btn-light" :disabled="reviewBusy" @click="formOpen = false">关闭</button>
    </template>
  </BootstrapModal>

  <DetailViewDialog v-model="detailOpen" :title="detailTitle" :sections="detailSections" :loading="detailLoading" :error="detailError" @retry="retryDetail" />
  <AttachmentManagerDialog v-model="attachmentOpen" :report-no="selectedReport?.reportNo || ''" view="contract_review" :title="`附件管理 · ${selectedReport?.reportNo || ''}`" />
  <el-dialog v-model="printOpen" :title="`打印合同评审单 · ${selectedReport?.reportNo || ''}`" width="1200px" top="5vh" @closed="clearPrintPreview">
    <div >
      <el-segmented v-model="printTemplateKind" :options="BUSINESS_FORM_TEMPLATE_OPTIONS" size="small" :disabled="printLoading" @change="reloadPrintPreview" />
      <div>
        <el-tag v-if="printUrl" size="small" type="success">WPS PDF</el-tag>
        <el-button size="small" :loading="printLoading" @click="reloadPrintPreview">刷新预览</el-button>
      </div>
    </div>
    <CommissionPdfPages :url="printUrl" :filename="`${reviewPrintParent?.no || selectedReport?.reportNo || '委托单'}-合同评审单.pdf`" :disabled="printLoading || !printOpen" />
    <DataEntryPreview v-if="printUrl" :url="printUrl" title="合同评审单预览" name="" type="application/pdf" embedded compact persistent hide-download />
    <el-empty v-else :description="printLoading ? '生成中…' : '暂无预览'" />
  </el-dialog>
  <ComplianceConfirmDialog
    v-model="complianceOpen"
    :preflight="compliancePreflight"
    :loading="complianceSubmitting"
    @confirm="confirmCompliancePass"
  />
</template>

<script setup lang="ts">
import CommissionPdfPages from '../components/CommissionPdfPages.vue'
// BEGIN TEMPLATE REVIEW IMPORTS
import { useId } from 'vue'
import RegistrationPresentation from '../../platformUi/commissions/RegistrationPresentation.vue'
import {createServerPage,fetchListPage,fetchListExport} from '../../platformUi/lists/serverPage'
import {useRegistrationPresentation} from '../../platformUi/commissions/registrationPresentation'
import {fetchEntrustPrint,fetchEntrustList,fetchEntrustDetail} from '@/services/pipeline'
import PipelineWizard from '@/components/PipelineWizard.vue'
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import BootstrapModal from "../../components/common/BootstrapModal.vue"
import SchemaForm from "../../components/forms/SchemaForm.vue"
import LoadState from "../../components/common/LoadState.vue"
import FeedbackNotice from "../../components/common/FeedbackNotice.vue"
import {reviewFormSchema} from "../../platformUi/commissions/reviewForm"
// END TEMPLATE REVIEW IMPORTS

import ManualFinanceAction from '../../platformUi/finance/ManualFinanceAction.vue'
import { shallowRef, computed, onUnmounted, reactive, ref, watch, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSearchRequest } from '@/composables/liveSearch'
import { modules } from '@/data/modules'
import { reportWorkRows } from '@/data/mock'
import { fetchReportRows, reportAction, type ReportRow } from '@/services/auth'
import { fetchReportDetail } from '@/services/reports'
import { BUSINESS_FORM_TEMPLATE_OPTIONS, PIPELINE_AVAILABLE, fetchCompliancePreflight, fetchSamplePrint, submitContractReview, type BusinessFormPrint, type BusinessFormTemplateKind, type ComplianceConfirmation, type CompliancePreflight } from '@/services/pipeline'
import { useSessionStore } from '@/stores/session'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import DetailViewDialog from '@/components/DetailViewDialog.vue'
import AttachmentManagerDialog from '@/components/AttachmentManagerDialog.vue'
import ComplianceConfirmDialog from '@/components/ComplianceConfirmDialog.vue'
import FlatDatePicker from '@/components/FlatDatePicker.vue'
import { useDetailView } from '@/composables/useDetailView'
import { exportRowsXlsx, type XlsxColumn } from '@/services/xlsxExport'

const {
  detailOpen, detailTitle, detailSections, detailLoading, detailError,
  viewReportDetail, retryDetail,
} = useDetailView()
const complianceOpen = ref(false)
const compliancePreflight = ref<CompliancePreflight | null>(null)
const complianceSubmitting = ref(false)

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const available = PIPELINE_AVAILABLE
const pageName = computed(() => String(route.meta.pageName ?? '合同评审'))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pageKey = computed(() => String(route.meta.pageKey ?? 'contract_review'))
// 合同评审挂在委托管理菜单下；按当前路由所属模块取页签
const pages = computed(() => modules.find((m) => m.key === (route.meta.moduleKey as string))?.pages ?? [])

const crItems = [
  { key: 'tech', name: '技术能力' },
  { key: 'instrument', name: '仪器设备' },
  { key: 'env', name: '环境' },
  { key: 'method', name: '方法' },
  { key: 'personnel', name: '人员' },
  { key: 'sample', name: '样品' },
  { key: 'basisAuth', name: '检验依据授权' },
]

const allRows = shallowRef<ReportRow[]>([])
type TableSelectionRef<T> = { toggleRowSelection: (row: T, selected?: boolean) => void }
const tableRef = ref<TableSelectionRef<ReportRow> | null>(null)
const selectedNo = ref('')
const selectedRows = ref<ReportRow[]>([])
const keyword = ref('')
const statusFilter = ref('')
const dateRange = ref<[string, string] | null>(null)
const pageSize = ref(10)
const tablePage = ref(1)
const formOpen = ref(false)
const formReadOnly = ref(false)
const form = reactive<{ items: Record<string, boolean>; cma: boolean; cnas: boolean; opinion: string }>({
  items: {}, cma: false, cnas: false, opinion: '',
})

const viewMode = ref<'pending' | 'reviewed'>('pending')
interface ListColumn { key: string; label: string; width?: number; minWidth?: number }
const reviewColumns: ListColumn[] = [
  { key: 'entrustNo', label: '委托编号', minWidth: 140 },
  { key: 'sampleNo', label: '样品编号', minWidth: 140 },
  { key: 'reportNo', label: '报告编号', minWidth: 160 },
  { key: 'erpProjectNo', label: '外部ERP项目编号', minWidth: 150 },
  { key: 'erpProjectType', label: '外部ERP项目类型', minWidth: 130 },
  { key: 'erpContractNo', label: '外部ERP合同编号', minWidth: 150 },
  { key: 'handler', label: '委托经办人', width: 110 },
  { key: 'registrar', label: '样品登记人', width: 110 },
  { key: 'sampleOrProjectName', label: '样品/工程名称', minWidth: 180 },
  { key: 'testItems', label: '检测项目', minWidth: 170 },
  { key: 'dataStatus', label: '数据状态', width: 120 },
  { key: 'schemeName', label: '检测方案名称', minWidth: 170 },
  { key: 'client', label: '委托单位', minWidth: 180 },
  { key: 'amount', label: '金额', width: 110 },
  { key: 'reportCategory', label: '报告类别', width: 110 },
  { key: 'reportFormat', label: '报告格式', width: 120 },
  { key: 'testCategory', label: '检测类别', width: 110 },
  { key: 'sampleRegisteredAt', label: '样品登记时间', width: 130 },
  { key: 'sendDate', label: '送样日期', width: 120 },
  { key: 'reportTitle', label: '报告标题', minWidth: 180 },
  { key: 'sealRequirement', label: '盖章要求', width: 120 },
  { key: 'samplingUnit', label: '抽样单位', minWidth: 160 },
  { key: 'sampler', label: '抽样人', width: 100 },
  { key: 'samplingTime', label: '抽样时间', width: 130 },
  { key: 'reviewer', label: '合同评审人', width: 110 },
  { key: 'reviewedAt', label: '合同评审时间', width: 140 },
]
// 待评审与评审通过后待入库使用两个明确状态，不再借用“待校核”。
const reviewRows = computed(() => {
  if (viewMode.value === 'reviewed') {
    return allRows.value.filter((r) => r.status === '待样品入库' && (r.sampleStatus || '待入库') === '待入库')
  }
  return allRows.value.filter((r) => r.status === '待合同评审' && (r.sampleRegState || '登记完成') === '登记完成')
})
const statusOptions = computed(() => Array.from(new Set(
  reviewRows.value.map((row) => String(row.dataStatus || row.status || '')).filter(Boolean),
)))
async function undoReviewSelected() {
  const row = selectedReport.value
  if (!row) return
  try {
    await ElMessageBox.confirm(`确认撤销 ${row.reportNo} 的合同评审？报告将回到「待合同评审」。`, '撤销合同评审', { type: 'warning' })
  } catch { return }
  try {
    const res = await reportAction(row.reportNo, 'report.contract_review.undo')
    if (res) {
      ElMessage.success(`${row.reportNo} 已撤销评审，回到待合同评审`)
      await loadReviewLists(true)
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '撤销合同评审失败')
  }
}
function goInbound() {
  const row = selectedReport.value
  if (!row) return
  router.push({ path: '/inspection/sample/inbound', query: { keyword: row.reportNo } })
}
const filteredRows = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  const [start, end] = dateRange.value ?? ['', '']
  return reviewRows.value.filter((row) => {
    const textMatched = !k || JSON.stringify(row).toLowerCase().includes(k)
    const dates = [row.sampleRegisteredAt, row.sendDate, row.samplingTime, row.reviewedAt].filter(Boolean) as string[]
    const dateMatched = (!start && !end) || dates.some((value) => (!start || value >= start) && (!end || value <= end))
    const statusMatched = !statusFilter.value || String(row.dataStatus || row.status || '') === statusFilter.value
    return textMatched && dateMatched && statusMatched
  })
})
const pagedRows = computed(() => filteredRows.value.slice((tablePage.value - 1) * pageSize.value, tablePage.value * pageSize.value))
watch([filteredRows, keyword, statusFilter, dateRange, pageSize], () => { tablePage.value = 1 })
const selectedReport = computed(() => allRows.value.find((r) => r.reportNo === selectedNo.value))
const reviewBusy = ref(false)
let reviewEpoch = 0
let complianceEpoch: number | null = null
function invalidateReview() {
  reviewEpoch += 1
  reviewBusy.value = false
  complianceEpoch = null
  complianceOpen.value = false
  compliancePreflight.value = null
  complianceSubmitting.value = false
}
watch([formOpen, selectedNo, () => route.path, () => session.userName], invalidateReview, { flush: 'sync' })
onUnmounted(invalidateReview)
function isCurrentReview(epoch: number) {
  return epoch === reviewEpoch && formOpen.value && !formReadOnly.value
}
const canUndoReviewSelected = computed(() => (
  !!selectedReport.value
  && selectedReport.value.allowedActions?.includes('report.contract_review.undo') === true
))

// List loading is owned by the complete-template list adapter.
// 带 keyword 进入（从我的待办 / 样品出库领取后跳转）：自动打开该报告的评审对话框
watchEffect(() => {
  if (!reviewRows.value.length) return
  const kw = typeof route.query.keyword === 'string' ? route.query.keyword : ''
  if (!kw) return
  const matched = reviewRows.value.find((r) => r.reportNo === kw)
  if (matched && !formOpen.value && selectedNo.value !== matched.reportNo) {
    selectedNo.value = matched.reportNo
    formReadOnly.value = false
    resetForm()
    formOpen.value = true
  }
})

type ContractReviewSnapshot = {
  items?: Record<string, boolean>
  cma?: boolean
  cnas?: boolean
  opinion?: string
}
const detail = ref<{ requestedSeal?: string; summary?: { title: string; fields: [string, string][] }[]; contractReview?: ContractReviewSnapshot } | null>(null)
const reviewDetailLoading = ref(false)
const reviewDetailError = ref('')
watch([() => selectedReport.value?.reportNo, formOpen, () => session.userName], async ([no, open], _old, onCleanup) => {
  let current = true
  onCleanup(() => { current = false })
  detail.value = null
  reviewDetailError.value = ''
  reviewDetailLoading.value = false
  if (!no || !open) return
  reviewDetailLoading.value = true
  try {
    const result = await fetchReportDetail(no, 'contract_review')
    if (!current) return
    detail.value = result
    if (!result) reviewDetailError.value = '本报告详情未读取成功，请关闭后重新打开'
    if (formOpen.value && formReadOnly.value) applyReviewSnapshot()
  } catch {
    if (!current) return
    detail.value = null
    reviewDetailError.value = '本报告详情读取失败，请关闭后重新打开；未加载时不能确认授权'
  } finally {
    if (current) reviewDetailLoading.value = false
  }
}, { flush: 'sync' })
const summarySections = computed(() => detail.value?.summary ?? [])
const sealRequirement = computed(() => {
  if (detail.value?.requestedSeal !== undefined) return detail.value.requestedSeal
  const f = detail.value?.summary?.find((s) => s.title === '委托信息')?.fields.find(([k]) => k === '盖章要求')
  return (f?.[1] as string) || ''
})
const requiredCma = computed(() => sealRequirement.value.toUpperCase().includes('CMA'))
const requiredCnas = computed(() => sealRequirement.value.toUpperCase().includes('CNAS'))
// CMA 盖章但检测依据超出一单一库范围 → 评审提示
const cmaScopeWarn = computed(() => {
  const f = detail.value?.summary?.find((s) => s.title === '实验信息')?.fields.find(([k]) => k === '检测依据范围')
  return String(f?.[1] ?? '').includes('超出一单一库')
})

const checkedCount = computed(() => crItems.filter((it) => form.items[it.key]).length)
const allChecked = computed(() => checkedCount.value === crItems.length)
const missingNames = computed(() => crItems.filter((it) => !form.items[it.key]).map((it) => it.name))
const sealMissingNames = computed(() => [
  requiredCma.value && !form.cma ? 'CMA' : '',
  requiredCnas.value && !form.cnas ? 'CNAS' : '',
].filter(Boolean))
const canPass = computed(() => !reviewDetailLoading.value && !!detail.value && allChecked.value && !sealMissingNames.value.length)

function resetForm() {
  crItems.forEach((it) => (form.items[it.key] = false))
  form.cma = false
  form.cnas = false
  form.opinion = ''
}

function applyReviewSnapshot() {
  const snapshot = detail.value?.contractReview
  if (!snapshot) return
  crItems.forEach((it) => (form.items[it.key] = Boolean(snapshot.items?.[it.key])))
  form.cma = Boolean(snapshot.cma)
  form.cnas = Boolean(snapshot.cnas)
  form.opinion = snapshot.opinion || ''
}

function openForm(row: ReportRow, readOnly = false) {
  formReadOnly.value = readOnly
  selectedNo.value = row.reportNo
  resetForm()
  if (readOnly) applyReviewSnapshot()
  formOpen.value = true
}
function onSelectionChange(selection: ReportRow[]) {
  selectedRows.value = selection
  selectedNo.value = selection[selection.length - 1]?.reportNo ?? ''
}
function toggleRow(row: ReportRow) {
  tableRef.value?.toggleRowSelection(row)
}
function viewSelected() {
  const row = selectedReport.value
  if (!row) return
  openForm(row, true)
}
const attachmentOpen = ref(false)
function openAttachmentManager() {
  if (selectedReport.value) attachmentOpen.value = true
}
const printOpen = ref(false)
const printLoading = ref(false)
const printUrl = ref('')
const printTemplateKind = ref<BusinessFormTemplateKind>('product')
// Only this open dialog retains Blob URLs; every selection still checks the server.
const printFiles = new Map<string, BusinessFormPrint>()
let printEpoch = 0
function clearPrintPreview() {
  printEpoch += 1
  for (const file of printFiles.values()) URL.revokeObjectURL(file.url)
  printFiles.clear()
  printUrl.value = ''
  printLoading.value = false
}
watch(printOpen, open => { if (!open) clearPrintPreview() })
async function openPrintDialog() {
  reviewPrintParent.value=undefined
  const row = selectedReport.value
  if (!row) return
  printTemplateKind.value = String(row.erpProjectType || row.testCategory || '').includes('工程') ? 'engineering' : 'product'
  clearPrintPreview()
  printOpen.value = true
  await reloadPrintPreview()
}
async function reloadPrintPreview() {
  const row = reviewPrintParent.value || selectedReport.value
  if (!row) return
  const parent = !!reviewPrintParent.value
  const kind = printTemplateKind.value
  const key = `${parent ? 'entrust:' + row.id : 'sample:' + row.reportNo}:${kind}`
  const reusable = printFiles.get(key)
  const epoch = ++printEpoch
  printUrl.value = ''
  printLoading.value = true
  try {
    const result = await (parent ? fetchEntrustPrint(row.id, 'pdf', kind, reusable)
      : fetchSamplePrint(row.reportNo, 'pdf', kind, [], reusable))
    if (epoch !== printEpoch || !printOpen.value) {
      if (result !== reusable) URL.revokeObjectURL(result.url)
      return
    }
    if (result.type === 'pdf') {
      if (reusable && reusable !== result) URL.revokeObjectURL(reusable.url)
      printFiles.set(key, result)
      printUrl.value = result.url
    }
  } catch (error) {
    if (epoch === printEpoch) ElMessage.error(error instanceof Error ? error.message : '评审单生成失败')
  } finally {
    if (epoch === printEpoch) printLoading.value = false
  }
}
async function downloadReviewPdf() {
  const row = selectedReport.value
  if (!row) return
  const kind: BusinessFormTemplateKind = String(row.erpProjectType || row.testCategory || '').includes('工程') ? 'engineering' : 'product'
  try {
    const result = await fetchSamplePrint(row.reportNo, 'pdf', kind)
    if (result.type !== 'pdf') return
    const link = document.createElement('a')
    link.href = result.url
    link.download = `${row.reportNo}-合同评审单.pdf`
    link.click()
    setTimeout(() => URL.revokeObjectURL(result.url), 1000)
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : 'PDF 导出失败') }
}
onUnmounted(clearPrintPreview)
async function exportReviewList() {
  const columns: XlsxColumn[] = reviewColumns.map((column) => ({
    label: column.label,
    key: column.key,
    width: column.minWidth ? Math.round(column.minWidth / 9) : Math.round((column.width || 120) / 9),
  }))
  try {
    await exportRowsXlsx(`合同评审列表-${new Date().toISOString().slice(0, 10)}`, columns, filteredRows.value as unknown as Record<string, unknown>[])
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '导出失败') }
}
function openSelectedForm() {
  const row = selectedReport.value
  if (row) openForm(row, false)
}

async function submit(action: 'pass' | 'return') {
  const row = selectedReport.value
  if (!row || reviewBusy.value || complianceOpen.value || !formOpen.value || formReadOnly.value) return
  if (action === 'pass' && !allChecked.value) {
    ElMessage.warning(`还有未确认项：${missingNames.value.join('、')}`)
    return
  }
  if (action === 'pass' && sealMissingNames.value.length) {
    ElMessage.warning(`请确认委托盖章要求：${sealMissingNames.value.join('、')}`)
    return
  }
  if (action === 'return' && !form.opinion.trim()) {
    ElMessage.warning('退回需填写不通过原因')
    return
  }
  const epoch = reviewEpoch
  reviewBusy.value = true
  try {
    if (action === 'pass') {
      const preflight = await fetchCompliancePreflight(row.reportNo, 'contract_review')
      if (!isCurrentReview(epoch)) return
      if (preflight.required) {
        compliancePreflight.value = preflight
        complianceEpoch = epoch
        complianceOpen.value = true
        return
      }
    }
    await performSubmit(action, {}, epoch)
  } catch (e) {
    if (isCurrentReview(epoch)) ElMessage.error(e instanceof Error ? e.message : '合规预检失败')
  } finally {
    if (epoch === reviewEpoch) reviewBusy.value = false
  }
}

async function performSubmit(action: 'pass' | 'return', compliance: ComplianceConfirmation = {}, epoch = reviewEpoch) {
  const row = selectedReport.value
  if (!row || !isCurrentReview(epoch)) return false
  try {
    const result = await submitContractReview(row.reportNo, {
      action, items: { ...form.items }, cma: form.cma, cnas: form.cnas, opinion: form.opinion,
      ...compliance,
    })
    if (!isCurrentReview(epoch)) return false
    const destination = result?.dataStatus?.trim() || result?.status?.trim()
    ElMessage.success(action === 'pass'
      ? `${row.reportNo} 合同评审通过${destination ? `，已进入「${destination}」` : ''}`
      : `${row.reportNo} 已退回`)
    formOpen.value = false
    // 刷新列表（评审后离开待评审队列）
    await loadReviewLists(true)
    return true
  } catch (e) {
    if (isCurrentReview(epoch)) ElMessage.error(e instanceof Error ? e.message : '提交失败')
    return false
  }
}

async function confirmCompliancePass(payload: ComplianceConfirmation) {
  const epoch = complianceEpoch
  if (epoch === null || !isCurrentReview(epoch) || !complianceOpen.value || complianceSubmitting.value) return
  complianceSubmitting.value = true
  reviewBusy.value = true
  try {
    if (await performSubmit('pass', payload, epoch)) complianceOpen.value = false
  } finally {
    if (epoch === reviewEpoch) {
      complianceSubmitting.value = false
      reviewBusy.value = false
    }
  }
}

// BEGIN TEMPLATE REVIEW ADAPTER
// Hidden quick-review forms remain mounted; each label must target this dialog's own control.
const reviewFormId = `contract-review-${useId()}`
const contractReviewSchema = computed(() => reviewFormSchema({idPrefix:reviewFormId,crItems,checkedCount:checkedCount.value,requiredCma:requiredCma.value,requiredCnas:requiredCnas.value,reviewDetailLoading:reviewDetailLoading.value}))
const reviewListSelected=ref<any>(),reviewPrintParent=ref<any>()
const parentViewOpen=ref(false),parentView=ref<any>(),reviewParents=shallowRef<any[]>([]),reviewListBusy=ref(false),reviewListError=ref<any>('')
const editOpen=ref(false),editMode=ref<'entrust'|'samples'>('samples'),editReportNo=ref(''),editParent=ref<any>(null)
async function editReviewRecord(row:any,kind:'entrust'|'samples') {
  if (!session.canCorrectBusinessData || session.businessReadOnly) return
  try {
    const parent=kind==='entrust'?await fetchEntrustDetail(Number(row.id)):null
    editParent.value=parent
    editReportNo.value=kind==='samples'?String(row.reportNo):''
    editMode.value=kind
    editOpen.value=true
  } catch(e) { ElMessage.error(e instanceof Error?e.message:'编辑信息加载失败') }
}
const commissionPaging=createServerPage({pageSize:5,presentation:'commission'}),reviewPaging=createServerPage({presentation:'registration-sample',commissionIds:[]})
const commissionPage=commissionPaging.state,registrationSamplePage=reviewPaging.state
function setRegistrationQuery(kind:string,q:Record<string,any>){(kind==='c'?commissionPaging:reviewPaging).setQuery({...q,presentation:kind==='c'?'commission':'registration-sample'})}
async function exportRegistrationRows(kind:string){return fetchListExport(kind==='c'?'/api/entrust/query':'/api/reports/query',{...(kind==='c'?commissionPage.query:registrationSamplePage.query),view:'contract_review',projection:'list'})}
const beginReviewLoad = useSearchRequest(() => [session.account,session.dataScope,session.userName,commissionPage.query,registrationSamplePage.query])
let reviewLoad: {key: string; promise: Promise<void>} | undefined
function loadReviewLists(force: boolean | string = false) {
  const key = JSON.stringify([session.account,session.dataScope,session.userName,commissionPage.query,registrationSamplePage.query])
  if (!force && reviewLoad?.key === key) return reviewLoad.promise
  const current = beginReviewLoad()
  reviewListBusy.value = true; reviewListError.value = ''
  const promise = Promise.all([fetchListPage('/api/entrust/query',{...commissionPage.query,projection:'list',view:'contract_review'}), fetchListPage<ReportRow>('/api/reports/query',{...registrationSamplePage.query,view:'contract_review'})])
    .then(([parents,reports]) => { if (current()) { reviewParents.value=parents.rows; commissionPage.total=parents.total; allRows.value=reports.rows; registrationSamplePage.total=reports.total } })
    .catch(e => { if (current()) reviewListError.value=e instanceof Error?e.message:String(e) })
    .finally(() => { if (current()) reviewListBusy.value=false; if (reviewLoad?.promise===promise) reviewLoad=undefined })
  reviewLoad={key,promise}
  return promise
}
const reviewLinkedParents=computed(()=>reviewParents.value.map(p=>({...p,no:p.entrustNo,linkedSamples:allRows.value.filter(r=>r.entrustNo===p.entrustNo)})))
function selectReviewRow(r:any){viewMode.value=r.status==='待样品入库'?'reviewed':'pending';selectedNo.value=r.reportNo;selectedRows.value=[r]}
const reviewListPresentation=useRegistrationPresentation(reactive({serverPaging:true,commissionPage,registrationSamplePage,registrationPageSamples:allRows,setRegistrationQuery,exportRegistrationRows,mode:'review',pageName,route,session,backendEntrust:reviewLinkedParents,reviewSamples:allRows,entrustPresentationLoading:reviewListBusy,entrustPresentationError:reviewListError,get selectedRow(){return reviewListSelected.value},set selectedRow(r:any){reviewListSelected.value=r;if(r?.reportNo)selectReviewRow(r)},openSelectedEntrustPrint:async()=>{reviewPrintParent.value=reviewListSelected.value;printOpen.value=true;clearPrintPreview();await reloadPrintPreview()},loadEntrust:loadReviewLists,onWorkbenchSelectionChange:()=>{},editSample:(r:any)=>editReviewRecord(r,'samples'),editEntrust:(r:any)=>editReviewRecord(r,'entrust'),viewEntrust:async(r:any)=>{try{const d=await fetchEntrustDetail(Number(r.id));parentView.value={...r,...d};parentViewOpen.value=true}catch(e){ElMessage.error(e instanceof Error?e.message:'委托详情加载失败')}},viewSample:(r:any)=>{selectReviewRow(r);openForm(r,true)},reviewSample:(r:any)=>{selectReviewRow(r);openForm(r)},undoReview:async(r:any)=>{selectReviewRow(r);await undoReviewSelected()},printSample:(r:any)=>{selectReviewRow(r);openPrintDialog()},openQueryAttachments:()=>openAttachmentManager()}))
watch(()=>reviewListPresentation.selectedRow,(r:any)=>{if(r?.reportNo)selectReviewRow(r)})
// END TEMPLATE REVIEW ADAPTER
watch(()=>JSON.stringify([session.account,commissionPage.query,registrationSamplePage.query]),()=>void loadReviewLists(),{immediate:true})
</script>


