<template>
  <ReportWorkspace :title="pageName" :area-name="areaName" :module-name="moduleName" :path="route.path" :pages="pages" :active-key="pageKey" :show-command="false" :show-content="false">

  <div v-if="isReportModule" >
    <ReportReviewPresentation v-if="formOpen && selectedReport && fullReviewPage" :key="`${selectedReport.reportNo}:${formSessionId}`" :controller="reviewContext"><template #scope-review><ReportScopePanel v-if="isDecisionNode && USE_BACKEND" :report-no="selectedReport.reportNo" :view="currentReportDetailView()" :read-only="formReadOnly" @changed="onScopeReviewed" /></template></ReportReviewPresentation>
    <template v-else>
    <ReportStagePresentation v-if="['review','approval'].includes(pageKey)" :context="reportStagePresentation" />
    <ReportCorrections v-else-if="pageKey === 'change_request'" :rows="workRows" :total="USE_BACKEND ? reportPageState.total : undefined" :loading="reportPresentationLoading" :error="reportPresentationError" :can-request="session.canAction('report.change.request')" @query="setReportQuery" @view="openForm($event, true)" @refresh="refreshReportList" />
    <template v-else-if="['print','release','archive','query'].includes(pageKey)">
      <ReportQueryListPresentation v-if="pageKey === 'query'" :context="reportOutputPresentation" />
      <ReportOutputListPresentation v-else :context="reportOutputPresentation"><template #finance><ManualFinanceAction v-if="pageKey === 'print'" :report-no="reportOutputPresentation.selected.length === 1 ? reportOutputPresentation.selected[0] : ''" mode="reverse" /></template></ReportOutputListPresentation>
    </template>
    <template v-else>
    <ModuleCommandBar
      v-model:status-model-value="statusFilter"
      :status-options="statusOptions"
      :count-label="`显示 ${filteredRows.length} 条结果`"
      show-search
      @search="tablePage = 1"
    >
      <template #filters>
            <el-input v-model="keyword" clearable placeholder="报告编号 / 样品编号 / 委托单位"  />
      </template>
      <template #summary>
            <el-tag v-if="selectedListRows.length" size="small" type="success">已选 {{ selectedListRows.length }} 条</el-tag>
      </template>
      <template #actions>
          <ManualFinanceAction v-if="actionPageKey === 'print'" :report-no="selectedReport?.reportNo || ''" mode="reverse" />
            <el-button size="small" :disabled="selectedListRows.length !== 1" @click="viewSelectedReport">查看</el-button>
            <el-button v-if="pageKey !== 'query'" size="small" type="primary" :disabled="selectedListRows.length !== 1" @click="processSelectedReport">处理</el-button>
      </template>
    </ModuleCommandBar>
    <ModuleContentCard title="报告清单">
      <el-table ref="reportTableRef" :data="pagedRows" row-key="reportNo" border height="100%"  @selection-change="onReportSelectionChange" @row-click="toggleReportRow">
        <el-table-column type="selection" width="42" />
        <el-table-column label="报告编号" min-width="170">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openForm(row, true)">{{ row.reportNo }}</el-button>
            <el-tag v-if="row.outOfScope" type="danger" size="small" effect="dark">超范围</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="client" label="委托单位" min-width="140" show-overflow-tooltip />
        <el-table-column prop="project" label="检测项目" min-width="120" />
        <el-table-column label="状态" width="120"><template #default="{ row }">{{ displayStatus(row.status) }}</template></el-table-column>
        <el-table-column label="数据状态" width="120">
          <template #default="{ row }"><el-tag size="small" type="info">{{ row.dataStatus || row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="sampleStatus" label="样品状态" width="100" />
        <el-table-column prop="version" label="报告版本" width="90" />
        <el-table-column label="时限" width="110">
          <template #default="{ row }"><el-tag :type="deadlineTagType(row.deadline)" size="small">{{ row.deadline }}</el-tag></template>
        </el-table-column>
        <template #empty><el-empty description="当前账号的数据范围内暂无待处理报告" :image-size="70" /></template>
      </el-table>
      <template #footer>
        <el-pagination layout="prev, pager, next" :total="filteredRows.length" :page-size="pageSize" v-model:current-page="tablePage" />
      </template>
    </ModuleContentCard>

    </template>
    </template>
    <ReleasedDepartmentReports v-if="pageKey === 'release' && USE_BACKEND" />
    <BootstrapModal v-if="!fullReviewPage" :open="formOpen" :title="(formReadOnly ? '只读查看' : pageName) + ' · ' + (selectedReport?.reportNo || '')" size="xl" scrollable fullscreen-mobile @close="formOpen=false">
      <ReportScopePanel v-if="selectedReport && USE_BACKEND && !['print','query','release'].includes(actionPageKey)" :key="selectedReport.reportNo + currentReportDetailView()" :report-no="selectedReport.reportNo" :view="currentReportDetailView()" :read-only="formReadOnly" @changed="onScopeReviewed" />
      <ReportArtifactPanel v-if="selectedReport && USE_BACKEND" :key="selectedReport.reportNo + ':' + currentReportDetailView()" :report-no="selectedReport.reportNo" :view="currentReportDetailView()" />
      <EsignFlowPanel
        v-if="actionPageKey === 'print' && selectedReport"
        :report-no="selectedReport.reportNo"
      />
      <FeedbackNotice v-if="actionPageKey === 'print' && documentVersionBlocker" :message="documentVersionBlocker" />
      <FeedbackNotice v-if="formReadOnly" message="只读查看" />
      <div v-for="notice in documentNotices" :key="notice" class="alert alert-warning" role="status">{{ notice }}</div>
      <ReportDecisionWorkbench
        v-if="isDecisionNode && selectedReport"
        :key="`${selectedReport.reportNo}:${formSessionId}`"
        v-model:opinion="opinion"
        :node-key="actionPageKey === 'approval' ? 'approval' : 'review'"
        :report="selectedReport"
        :project-name="detail.projectName"
        :summary="visibleSummarySections"
        :checks="detail.checks ?? []"
        :attachments="currentAttachments"
        :signatures="signatures"
        :document-pdf-url="documentPdfUrl || coverPdfUrl"
        :document-html="documentPdfUrl || coverPdfUrl ? '' : coverHtml"
        :document-loading="decisionPreviewLoading"
        :document-error="decisionPreviewIssue?.code === 'BUSINESS_RULE' ? '' : decisionPreviewError"
        :document-issue="decisionPreviewIssue"
        :document-preview-label="decisionPreviewLabel"
        :document-ready="(decisionPreviewSigned || Boolean(documentVersionsState.currentVersionId) && Boolean(documentPreflight?.ready) && !documentPreflight?.currentVersionStale) && Boolean(documentPdfUrl)"
        :current-user="session.userName"
        :can-act="canActOnSelected"
        :can-pass="canPass"
        :can-undo="canUndoSelected"
        :undo-label="undoLabel"
        :read-only="formReadOnly"
        @open-report="openDecisionReportPreview"
        @refresh-report="loadDecisionReportPreview(true)"
        @open-attachment="previewFile"
        @pass="handlePass"
        @return="handleReturn"
        @undo="handleUndo"
        @save-opinion="saveOpinion"
        @close="formOpen = false"
      />
      <ReportDetailPresentation v-else-if="selectedReport && actionPageKey !== 'print'" :context="reportDetailContext" />
      <template #footer>
        <button v-if="actionPageKey === 'print' && !formReadOnly && session.canAction(passAction)" class="btn btn-primary" :disabled="!canPass" @click="handlePass">{{ nextActionName }}</button>
        <button v-if="actionPageKey === 'print' && !formReadOnly && undoAction && session.canAction(undoAction)" class="btn btn-light" :disabled="!canUndoSelected" @click="handleUndo">{{ undoLabel }}</button>
        <el-button @click="formOpen = false">关闭</el-button>
      </template>
    </BootstrapModal>    <el-dialog v-model="uploadDialogOpen" title="重新上传报告与原始记录" width="540px">
      <p >报告「{{ selectedReport?.reportNo }}」被退回，请重新上传报告正文（Word/PDF）与原始记录（PDF）。</p>
      <el-upload
        drag
        multiple
        :auto-upload="false"
        :file-list="dialogFileList"
        :on-change="onUploadChange"
        :on-remove="onUploadChange"
        accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.webp"
      >
        <el-icon ><UploadFilled /></el-icon>
        <div >将文件拖到此处，或<em>点击选择本地文件</em></div>
        <template #tip>
          <div class="text-muted small">支持 Word、PDF 与 JPG/PNG 图片；图片可用于标准报告照片页</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!dialogFileList.length" @click="confirmUpload">
          确认上传（{{ dialogFileList.length }}）
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="previewDialogOpen" :title="previewTitle" width="1200px"  top="5vh">
      <DataEntryPreview v-if="previewSrc && !previewUnsupported" :url="previewSrc" title="附件预览" name="" type="" embedded compact persistent hide-download hide-print />
      <el-empty
        v-else-if="previewUnsupported"
        description="该文件类型（如 Word）无法在线预览，请下载后查看"
      >
        <el-button type="primary" @click="downloadFromPreview">下载文件</el-button>
      </el-empty>
    </el-dialog>

  </div>

  <div v-else class="row g-3">
    <div class="col-12 col-md-6">
      <el-card shadow="never" >
        <template #header>
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
            <strong>{{ pageName }}结果</strong>
            <el-tag size="small">报表模板</el-tag>
          </div>
        </template>
        <el-table :data="reportRows" border>
          <el-table-column prop="name" label="报表" min-width="180" />
          <el-table-column prop="period" label="周期" width="140" />
          <el-table-column prop="department" label="科室" width="140" />
          <el-table-column prop="scope" label="口径" width="120" />
          <el-table-column prop="value" label="结果" width="120" />
          <el-table-column prop="trend" label="变化" width="120" />
        </el-table>
      </el-card>
    </div>

    <el-card class="col-12 col-md-6" shadow="never">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
          <strong>统计图示</strong>
          <el-tag size="small" type="info">弹窗/侧栏</el-tag>
        </div>
      </template>
      <div >
        <span v-for="height in [44, 82, 64, 118, 96, 130]" :key="height"  />
      </div>
    </el-card>
  </div>
  <ComplianceConfirmDialog
    :key="formSessionId"
    v-model="complianceOpen"
    :preflight="compliancePreflight"
    :loading="complianceSubmitting"
    @confirm="confirmCompliancePass"
  />
  <el-dialog
    v-model="returnDialogOpen"
    title="选择退回路径"
    width="620px"
    append-to-body
    destroy-on-close
  >
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      :title="`退回原因：${opinion.trim()}`"
      
    />
    <el-radio-group v-model="returnMode" class="list-group">
      <el-radio value="entrust_only" border>
        <strong>退回委托更改</strong>
        <span>委托更改 → 合同评审 → 跳过样品出入库 → 报告审核</span>
      </el-radio>
      <el-radio value="data_only" border>
        <strong>退回检测数据录入更改</strong>
        <span>检测数据更改 → 报告审核</span>
      </el-radio>
      <el-radio value="entrust_and_data" border>
        <strong>委托和检测数据都退回</strong>
        <span>委托更改 → 合同评审 → 跳过样品出入库 → 检测数据更改 → 报告审核</span>
      </el-radio>
    </el-radio-group>
    <template #footer>
      <el-button @click="returnDialogOpen = false">取消</el-button>
      <el-button type="primary" :loading="returnSubmitting" @click="confirmReturn">确认退回</el-button>
    </template>
  </el-dialog>
  </ReportWorkspace>
</template>

<script setup lang="ts">
import ReleasedDepartmentReports from '../components/ReleasedDepartmentReports.vue'
// BEGIN TEMPLATE STAGE IMPORTS
import type {ReportDetailData} from "../services/auth"
import ReportCorrections from "../../platformUi/reports/ReportCorrections.vue"
import ReportReviewPresentation from "../../platformUi/reports/ReportReviewPresentation.vue"
import { platformError, reportPreviewError } from '../../platformUi/apiErrors'
const decisionPreviewIssue=ref<AppError|undefined>()
const decisionPreviewSigned=ref(false)
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import ReportDetailPresentation from '../../platformUi/reports/ReportDetailPresentation.vue'
import ReportOutputListPresentation from '../../platformUi/reports/ReportOutputListPresentation.vue'
import ReportQueryListPresentation from '../../platformUi/reports/ReportQueryListPresentation.vue'
import {createReportOutputPresentation} from '../../platformUi/reports/reportOutputPresentation'
import {defineComponent,h} from 'vue'
import ReportStagePresentation from '../../platformUi/reports/ReportStagePresentation.vue'
import {createServerPage,fetchListPage,fetchListExport} from '../../platformUi/lists/serverPage'
import {createReportStagePresentation} from '../../platformUi/reports/reportStagePresentation'
import {createReportStageUndo} from '../../platformUi/reports/reportStageUndo'
import {AppError} from '../../services/common/errors'
const reportPresentationLoading=ref(false),reportPresentationError=ref<AppError|''>('')
// END TEMPLATE STAGE IMPORTS
import ManualFinanceAction from '../../platformUi/finance/ManualFinanceAction.vue'
import { shallowRef, computed, reactive, ref, watch, watchEffect, onBeforeUnmount } from 'vue'
import ReportArtifactPanel from '@/components/ReportArtifactPanel.vue'
import ReportScopePanel from '@/components/ReportScopePanel.vue'
import { artifactObjectUrl, fetchReportArtifact } from '@/services/reportAssurance'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type UploadUserFile } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { modules } from '@/data/modules'
import {
  PIPELINE_AVAILABLE,
  createReportRenderJob,
  fetchReportDocumentPreflight,
  fetchReportDocumentVersions,
  fetchReportRenderJob,
  reportVersionObjectUrl,
  requestReportChange,
  saveReportDocumentContent,
  updateTestInfo,
  fetchReportCover,
  fetchCompliancePreflight,
  type ComplianceConfirmation,
  type CompliancePreflight,
  type ReportDocumentContent,
  type ReportDocumentPreflight,
  type ReportDocumentVersion,
  type ReportRenderJob,
} from '@/services/pipeline'
import { fetchReportRows, reportAction, USE_BACKEND, type ReportRow } from '@/services/auth'
import { fetchReportDetail, type ReportDetailView } from '@/services/reports'
import {
  attachmentObjectUrl,
  isPreviewable,
  listUploadedAttachments,
  uploadAttachment,
  type Attachment,
} from '@/services/attachments'
import { useSessionStore } from '@/stores/session'
import { isLegacySystemCover } from '../../platformUi/reportAttachments'
import {
  reportNodeActions,
  reportRows,
  reportTimeline,
  reportWorkDetails,
  reportWorkRows,
} from '@/data/mock'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import ModuleCommandBar from '@/components/ModuleCommandBar.vue'
import ModuleContentCard from '@/components/ModuleContentCard.vue'
import ReportDecisionWorkbench from '@/components/report/ReportDecisionWorkbench.vue'
import WorkflowDatePicker from '@/components/WorkflowDatePicker.vue'
import ComplianceConfirmDialog from '@/components/ComplianceConfirmDialog.vue'
import EsignFlowPanel from '@/components/EsignFlowPanel.vue'
import { isWorkflowDateBefore, isWorkflowDateValid } from '@/composables/workflowDate'

const route = useRoute()
const session = useSessionStore()
const moduleKey = computed(() => route.meta.moduleKey ?? '')
const pageKey = computed(() => String(route.meta.pageKey ?? ''))
const pageName = computed(() => String(route.meta.pageName ?? ''))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pages = computed(() => modules.find((module) => module.key === moduleKey.value)?.pages ?? [])
const isReportModule = computed(() => moduleKey.value === 'report')
const reportDetailView = computed<ReportDetailView | null>(() => {
  const allowed: ReportDetailView[] = [
    'query', 'review', 'interim_report', 'approval', 'print', 'release',
    'archive', 'change_request', 'contract_review',
  ]
  return allowed.includes(pageKey.value as ReportDetailView)
    ? pageKey.value as ReportDetailView
    : null
})
function currentReportDetailView(): ReportDetailView {
  const view = reportDetailView.value
  if (!view) throw new Error('当前页面没有有效的报告详情入口')
  return view
}
const pipelineAvailable = PIPELINE_AVAILABLE
function displayStatus(status: string) { return status === '待打印' ? '待签发' : status }

// 报告清单由后端按当前账号的数据范围下发（mock 或真实 Flask 后端），前端不做权限决策
type WorkflowReportRow = ReportRow & {
  samplePickup?: { pickupTime?: string } | null
  workflowDates?: { samplePickupAt?: string }
}
const workRows = shallowRef<WorkflowReportRow[]>([])
const selectedReportNo = ref('')
const keyword = ref('')
const pageSize = 12
const tablePage = ref(1)
const formOpen = ref(false)
const formReadOnly = ref(false)
// Every opening is a new session, even when the same report is reopened.
// Async work may update only the report and session that initiated it.
const formSessionId = ref(0)
const mutationPending = ref(false)
type ReportFormContext = { reportNo: string; page: string; sessionId: number; view: ReportDetailView }
function captureFormContext(): ReportFormContext | null {
  const reportNo = selectedReport.value?.reportNo
  const view = reportDetailView.value
  if (!formOpen.value || !reportNo || !view) return null
  return { reportNo, view, page: pageKey.value, sessionId: formSessionId.value }
}
function isCurrentForm(context: ReportFormContext | null): context is ReportFormContext {
  return !!context && formOpen.value && selectedReportNo.value === context.reportNo
    && selectedReport.value?.reportNo === context.reportNo
    && pageKey.value === context.page && formSessionId.value === context.sessionId
}
function beginMutation(): ReportFormContext | null {
  const context = captureFormContext()
  if (!context || formReadOnly.value || mutationPending.value) return null
  mutationPending.value = true
  return context
}
function endMutation(context: ReportFormContext) {
  if (isCurrentForm(context)) mutationPending.value = false
}
type ReviewWorkspaceTab = 'basic' | 'report' | 'checks'
const reviewWorkspaceTab = ref<ReviewWorkspaceTab>('basic')
const reviewWorkspaceTabs = computed(() => [
  {
    key: 'basic' as const,
    label: '基本信息',
    description: '委托、样品与检测数据',
    tag: `${visibleSummarySections.value.length} 组`,
    tagType: 'info' as const,
  },
  {
    key: 'report' as const,
    label: '报告和原始记录',
    description: '报告版本、附件及原始记录',
    tag: `${currentAttachments.value.length} 个附件`,
    tagType: 'primary' as const,
  },
  {
    key: 'checks' as const,
    label: '三库核查结果',
    description: '标准、设备与能力范围',
    tag: `${detail.value.checks?.length ?? 0} 项`,
    tagType: selectedReport.value?.outOfScope ? 'danger' as const : 'success' as const,
  },
])
const reportTableRef = ref()
const selectedListRows = ref<ReportRow[]>([])
const statusFilter = ref('')
const statusOptions = computed(() => Array.from(new Set(
  workRows.value.map((row) => String(row.dataStatus || row.status || '')).filter(Boolean),
)))
const filteredRows = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  return workRows.value.filter((r) => (
    (!k || [r.reportNo, r.sampleNo, r.client, r.project].some((v) => String(v ?? '').toLowerCase().includes(k)))
    && (!statusFilter.value || String(r.dataStatus || r.status || '') === statusFilter.value)
  ))
})
const pagedRows = computed(() => filteredRows.value.slice((tablePage.value - 1) * pageSize, tablePage.value * pageSize))
watch([filteredRows, keyword, statusFilter], () => {
  tablePage.value = 1
  selectedListRows.value = []
  reportTableRef.value?.clearSelection()
})
let lastAutoKw = ''
function openForm(row: ReportRow, readOnly = false) {
  // A stale list selection must never reopen an unrelated / removed record.
  if (!workRows.value.some(item => item.reportNo === row.reportNo)) return
  resetFormSession()
  formReadOnly.value = readOnly || pageKey.value === 'change_request'
  selectedReportNo.value = row.reportNo
  reviewWorkspaceTab.value = 'basic'
  formOpen.value = true
}
function onReportSelectionChange(rows: ReportRow[]) {
  selectedListRows.value = rows
}
function toggleReportRow(row: ReportRow) {
  reportTableRef.value?.toggleRowSelection(row)
}
function viewSelectedReport() {
  const row = selectedListRows.value[0]
  if (row) openForm(row, true)
}
function processSelectedReport() {
  const row = selectedListRows.value[0]
  if (row) openForm(row, false)
}
// 切换报告子页（校核/审核/批准…）时关闭处理对话框，避免残留
watch(() => pageKey.value, () => {
  formOpen.value = false
  formReadOnly.value = false
  reviewWorkspaceTab.value = 'basic'
  lastAutoKw = ''
})

const initKeyword = computed(() => (typeof route.query.keyword === 'string' ? route.query.keyword : ''))
const reportPaging=createServerPage({presentation:'report'})
const reportPageState=reportPaging.state
function setReportQuery(q:Record<string,any>){reportPaging.setQuery({...q,presentation:'report'})}
async function exportReportRows(){return fetchListExport('/api/reports/query',{...reportPageState.query,view:pageKey.value})}
async function requestReportPage(){
 if(!USE_BACKEND){const rows=await fetchReportRows(reportWorkRows,session.dataScope,session.userName,pageKey.value as import('@/services/auth').ReportListView);return {rows,total:rows.length}}
 return fetchListPage<ReportRow>('/api/reports/query',{...reportPageState.query,view:pageKey.value})
}
let listRequestId = 0

// Workflow responses do not include every list projection (e.g. archiveState).
// Refresh after success without automatically opening a record or reusing a draft.
function replaceReportRow(reportNo: string, patch: Partial<WorkflowReportRow>) {
  workRows.value = workRows.value.map(row => row.reportNo === reportNo ? {...row, ...patch} : row)
}
async function onScopeReviewed(value: {outOfScope: boolean; note: string; state: string}) {
  const row = selectedReport.value
  if (row) {
    replaceReportRow(row.reportNo, {outOfScope: value.outOfScope, outOfScopeNote: value.outOfScope ? value.note : ''})
    const next = {...detailCache.value}; delete next[row.reportNo]; detailCache.value = next
  }
  await refreshReportList()
}
async function refreshReportList() {
  const requestId = ++listRequestId
  const page = pageKey.value
  reportPresentationLoading.value=true;reportPresentationError.value=''
  try {
    const result = await requestReportPage();const rows=result.rows
    if (requestId !== listRequestId || page !== pageKey.value) return
    workRows.value = rows.map(row => ({ ...row }));reportPageState.total=result.total
  } catch (error) {
    if (requestId === listRequestId && page === pageKey.value) {
      reportPresentationError.value=platformError(error /* report list refresh */)
      ElMessage.warning(`操作已完成，但清单刷新失败，请重新进入本页核对：${error instanceof Error ? error.message : '网络错误'}`)
    }
  } finally { if(requestId===listRequestId&&page===pageKey.value)reportPresentationLoading.value=false }
}


const selectedReport = computed(
  () => workRows.value.find((row) => row.reportNo === selectedReportNo.value),
)
const testPreviousDate = computed(() => selectedReport.value?.samplePickup?.pickupTime || selectedReport.value?.workflowDates?.samplePickupAt || '')
// 报告明细：后端模式从接口取（覆盖新建报告），mock 模式用本地数据
const detailCache = ref<Record<string, typeof reportWorkDetails[string]>>({})
watch(() => pageKey.value, () => { detailCache.value = {} })
watchEffect(async (onCleanup) => {
  let active = true
  onCleanup(() => { active = false })
  const context = captureFormContext()
  const no = selectedReport.value?.reportNo
  const view = reportDetailView.value
  if (!no || !view || detailCache.value[no]) return
  const d = await fetchReportDetail(no, view)
  if (active && isCurrentForm(context) && d) detailCache.value = { ...detailCache.value, [no]: d as typeof reportWorkDetails[string] }
})
// 真实模板封面+首页：预览(PDF)/下载(docx)
const coverPdfUrl = ref('')
const coverHtml = ref('')
const coverLoading = ref(false)
const decisionPreviewLoading = ref(false)
const decisionPreviewError = ref('')
const decisionPreviewLabel = ref('')
let decisionPreviewRequestId = 0
function clearCover() {
  if (coverPdfUrl.value) { URL.revokeObjectURL(coverPdfUrl.value); coverPdfUrl.value = '' }
  coverHtml.value = ''
}
watch(() => selectedReportNo.value, () => clearCover())
async function previewCover() {
  const context = captureFormContext()
  if (!context) return
  coverLoading.value = true
  clearCover()
  try {
    if (USE_BACKEND) {
      const url = await artifactObjectUrl(context.reportNo, context.view)
      if (!isCurrentForm(context)) { URL.revokeObjectURL(url); return }
      coverPdfUrl.value = url
      return
    }
    const res = await fetchReportCover(context.reportNo, context.view, 'pdf')
    if (!isCurrentForm(context)) {
      if (res.type === 'pdf') URL.revokeObjectURL(res.url)
      return
    }
    if (res.type === 'pdf') coverPdfUrl.value = res.url
    else if (res.type === 'html') coverHtml.value = res.html
  } catch (e) {
    if (isCurrentForm(context)) ElMessage.error(e instanceof Error ? e.message : '生成封面失败')
  } finally {
    if (isCurrentForm(context)) coverLoading.value = false
  }
}
async function downloadCover() {
  const context = captureFormContext()
  if (!context) return
  coverLoading.value = true
  try {
    const res = await fetchReportCover(context.reportNo, context.view, 'docx')
    if (!isCurrentForm(context)) {
      if (res.type === 'docx' || res.type === 'pdf') URL.revokeObjectURL(res.url)
      return
    }
    if (res.type === 'docx') {
      const a = document.createElement('a')
      a.href = res.url; a.download = res.name
      document.body.appendChild(a); a.click(); a.remove()
      ElMessage.success('封面+首页 已下载')
    } else {
      ElMessage.warning('未匹配到模板')
    }
  } catch (e) {
    if (isCurrentForm(context)) ElMessage.error(e instanceof Error ? e.message : '下载失败')
  } finally {
    if (isCurrentForm(context)) coverLoading.value = false
  }
}

const detail = computed(() => {
  const no = selectedReport.value?.reportNo ?? ''
  return (
    detailCache.value[no] ??
    (!USE_BACKEND ? reportWorkDetails[no] : undefined) ??
    { projectName: '', summary: [], checks: [], attachments: [] }
  )
})

const visibleSummarySections = computed(() =>
  (detail.value.summary ?? [])
    .map((section) => ({
      ...section,
      fields: section.fields.filter(([, value]) => {
        const normalized = String(value ?? '').trim()
        return normalized !== '' && normalized !== '—' && normalized !== '-'
      }),
    }))
    .filter((section) => section.fields.length > 0),
)

const documentPreflight = ref<ReportDocumentPreflight | null>(null)
const documentVersions = ref<ReportDocumentVersion[]>([])
const documentVersionsState = ref<{ currentVersionId?: number; approvedVersionId?: number }>({})
const documentJob = ref<ReportRenderJob | null>(null)
const documentLoading = ref(false)
let documentStateRequestId = 0
const documentGenerating = ref(false)
const documentPdfUrl = ref('')
const documentNotices = ref<string[]>([])
const documentEditorOpen = ref(false)
const savingDocument = ref(false)

function blankDocumentContent(): ReportDocumentContent {
  return {
    profileCode: '', resultGroups: [], remarks: '', photos: [], extraPages: [],
    compositionOptions: { includedOtherAttachmentIds: [] },
  }
}
const editDocument = ref<ReportDocumentContent>(blankDocumentContent())
const missingFieldNames: Record<string, string> = {
  sampleNo: '样品编号', productName: '产品名称', client: '委托单位',
  testBasis: '检测依据', testItems: '检测项目', resultGroups: '检验结果',
}
const documentMissingLabels = computed(() =>
  (documentPreflight.value?.missing ?? []).map((key) => missingFieldNames[key] ?? key).join('、'),
)
const requiresDocumentVersion = computed(() =>
  Boolean(documentPreflight.value?.profile.requiresVersion) || /^LAB-\d{4}JF-/.test(selectedReport.value?.reportNo ?? ''),
)
const documentVersionBlocker = computed(() => {
  if (!requiresDocumentVersion.value) return ''
  if (!documentPreflight.value) return '正在检查标准报告内容，请稍候'
  if (!documentPreflight.value.ready) return `请先补齐标准报告内容：${documentMissingLabels.value}`
  if (!documentVersionsState.value.currentVersionId) return '请先生成正式报告版本，再提交审核'
  if (documentPreflight.value.currentVersionStale) return '报告数据已变化，请重新生成正式报告版本'
  return ''
})

function clearDocumentPreview() {
  if (documentPdfUrl.value) URL.revokeObjectURL(documentPdfUrl.value)
  documentPdfUrl.value = ''
  documentNotices.value = []
}

async function loadDocumentState(showError = true) {
  const context = captureFormContext()
  if (!pipelineAvailable || !context) return
  const requestId = ++documentStateRequestId
  const ownsResponse = () => isCurrentForm(context) && requestId === documentStateRequestId
  documentLoading.value = true
  try {
    const [preflight, versions] = await Promise.all([
      fetchReportDocumentPreflight(context.reportNo, context.view).catch(() => null),
      fetchReportDocumentVersions(context.reportNo, context.view),
    ])
    if (!ownsResponse()) return
    documentPreflight.value = preflight
    documentVersions.value = versions.rows
    documentVersionsState.value = {
      currentVersionId: versions.currentVersionId,
      approvedVersionId: versions.approvedVersionId,
    }
  } catch (error) {
    if (!ownsResponse()) return
    documentPreflight.value = null
    documentVersions.value = []
    documentVersionsState.value = {}
    if (showError) ElMessage.error(error instanceof Error ? error.message : '报告版本信息加载失败')
  } finally {
    if (ownsResponse()) documentLoading.value = false
  }
}

watch([() => selectedReportNo.value, formOpen], ([, opened]) => {
  decisionPreviewRequestId += 1
  clearDocumentPreview()
  clearCover()
  decisionPreviewError.value = ''; decisionPreviewIssue.value = undefined; decisionPreviewSigned.value = false
  decisionPreviewLabel.value = ''
  documentJob.value = null
  if (opened) void loadDocumentState()
  if (opened && fullReviewPage.value) void loadDecisionReportPreview()
})

function openDocumentEditor() {
  const source = documentPreflight.value?.content ?? blankDocumentContent()
  editDocument.value = JSON.parse(JSON.stringify(source)) as ReportDocumentContent
  if (!editDocument.value.resultGroups.length) addResultGroup()
  if (!editDocument.value.photos.length) {
    editDocument.value.photos = [
      { attachmentId: null, caption: '机组照片' },
      { attachmentId: null, caption: '铭牌照片' },
      { attachmentId: null, caption: '过滤器照片' },
    ]
  }
  documentEditorOpen.value = true
}

function addResultGroup() {
  editDocument.value.resultGroups.push({
    name: '',
    items: [{ name: '', condition: '', unit: '', value: '' }],
  })
}
function addResultItem(groupIndex: number) {
  editDocument.value.resultGroups[groupIndex]?.items.push({ name: '', condition: '', unit: '', value: '' })
}
function addPhotoSlot() {
  if (editDocument.value.photos.length < 6) editDocument.value.photos.push({ attachmentId: null, caption: '' })
}

async function saveDocumentEditor() {
  const context = beginMutation()
  if (!context) return
  const content = JSON.parse(JSON.stringify(editDocument.value)) as ReportDocumentContent
  savingDocument.value = true
  try {
    const preflight = await saveReportDocumentContent(context.reportNo, content)
    if (!isCurrentForm(context)) return
    documentPreflight.value = preflight
    documentEditorOpen.value = false
    await loadDocumentState()
    if (!isCurrentForm(context)) return
    ElMessage.success('标准报告正文已保存，旧版本继续保留')
  } catch (error) {
    if (isCurrentForm(context)) ElMessage.error(error instanceof Error ? error.message : '报告正文保存失败')
  } finally {
    if (isCurrentForm(context)) savingDocument.value = false
    endMutation(context)
  }
}

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

async function generateDocument(outputKind: 'official' | 'audit') {
  if (!documentPreflight.value?.ready) return
  const context = beginMutation()
  if (!context) return
  const label = outputKind === 'official' ? '正式报告' : '内部审核包'
  try {
    await ElMessageBox.confirm(
      `将按当前业务数据和结构化正文生成新的${label}版本，历史版本不会被覆盖。`,
      `生成${label}`,
      { confirmButtonText: '开始生成', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    endMutation(context)
    return
  }
  if (!isCurrentForm(context)) return
  documentGenerating.value = true
  try {
    let job = await createReportRenderJob(context.reportNo, outputKind)
    if (!isCurrentForm(context)) return
    documentJob.value = job
    for (let count = 0; count < 180; count += 1) {
      await wait(1000)
      if (!isCurrentForm(context)) return
      job = await fetchReportRenderJob(context.reportNo, job.id, context.view)
      if (!isCurrentForm(context)) return
      documentJob.value = job
      if (job.status === 'completed') break
      if (job.status === 'failed') throw new Error(job.message || '报告生成失败')
    }
    if (job.status !== 'completed') throw new Error('报告生成超时，请稍后刷新查看任务状态')
    await loadDocumentState()
    if (!isCurrentForm(context)) return
    const version = documentVersions.value.find((item) => item.id === job.versionId)
    if (version) await previewDocumentVersion(version)
    if (!isCurrentForm(context)) return
    ElMessage.success(`${label}生成完成`)
  } catch (error) {
    if (isCurrentForm(context)) ElMessage.error(error instanceof Error ? error.message : '报告生成失败')
  } finally {
    if (isCurrentForm(context)) documentGenerating.value = false
    endMutation(context)
  }
}

async function previewDocumentVersion(version: ReportDocumentVersion) {
  const context = captureFormContext()
  if (!context) return
  try {
    clearDocumentPreview()
    const result = await reportVersionObjectUrl(context.reportNo, version.id, context.view, 'pdf', false)
    if (!isCurrentForm(context)) { URL.revokeObjectURL(result.url); return }
    documentPdfUrl.value = result.url
    documentNotices.value = version.warnings.filter(w => w === '检测地点超出模板容量，已截断，请核对')
  } catch (error) {
    if (isCurrentForm(context)) ElMessage.error(error instanceof Error ? error.message : '报告预览失败')
  }
}

function escapeTemplateText(value: unknown): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function decisionTemplateField(pattern: RegExp, fallback = '—'): string {
  for (const section of visibleSummarySections.value) {
    const matched = section.fields.find(([label]) => pattern.test(label))
    if (matched?.[1]) return String(matched[1])
  }
  return fallback
}


async function loadDecisionReportPreview(_retry = false) {
  const no = selectedReport.value?.reportNo
  if (!no || !fullReviewPage.value || !formOpen.value) return
  const requestId = ++decisionPreviewRequestId
  decisionPreviewLoading.value = true
  decisionPreviewError.value = ''; decisionPreviewIssue.value = undefined; decisionPreviewSigned.value = false
  decisionPreviewLabel.value = '正在加载真实模板并替换封面、首页字段'
  clearDocumentPreview()
  clearCover()

  try {
    if (!USE_BACKEND) {
      throw new Error('报告预览需要连接现平台后端')
    }

    // Never render a substitute for a signed report, or generate in a read path.
    const artifact = await fetchReportArtifact(no, currentReportDetailView(), pageKey.value === 'print')
    if (requestId !== decisionPreviewRequestId || no !== selectedReport.value?.reportNo) return
    const originalUrl = await artifactObjectUrl(no, currentReportDetailView(), false, pageKey.value === 'print')
    if (requestId !== decisionPreviewRequestId || no !== selectedReport.value?.reportNo) { URL.revokeObjectURL(originalUrl); return }
    documentPdfUrl.value = originalUrl
    const latest = await fetchReportArtifact(no, currentReportDetailView(), pageKey.value === 'print')
    if (requestId !== decisionPreviewRequestId || no !== selectedReport.value?.reportNo) return
    documentNotices.value = latest.preview?.notices || []
    decisionPreviewSigned.value = artifact.kind === 'signed'
    decisionPreviewLabel.value = artifact.label
  } catch (error) {
    if (requestId !== decisionPreviewRequestId) return
    decisionPreviewIssue.value = reportPreviewError(error)
    decisionPreviewError.value = decisionPreviewIssue.value.message
    decisionPreviewLabel.value = '报告模板暂不可用'
  } finally {
    if (requestId === decisionPreviewRequestId) decisionPreviewLoading.value = false
  }
}

async function openDecisionReportPreview() {
  const context = captureFormContext()
  if (!context) return
  const hasAllowedPreview = documentPdfUrl.value || coverPdfUrl.value || (!USE_BACKEND && coverHtml.value)
  if (!hasAllowedPreview) await loadDecisionReportPreview()
  if (!isCurrentForm(context)) return
  const url = documentPdfUrl.value || coverPdfUrl.value
  if (!url && (USE_BACKEND || !coverHtml.value)) {
    ElMessage.warning(decisionPreviewError.value || '当前没有可打开的报告模板预览')
    return
  }
  previewFileRef.value = null
  previewUnsupported.value = false
  previewSrc.value = url || URL.createObjectURL(new Blob([coverHtml.value], { type: 'text/html' }))
  previewTitle.value = `${selectedReport.value?.reportNo ?? ''} 模板报告预览`
  previewDialogOpen.value = true
}

async function downloadDocumentVersion(version: ReportDocumentVersion, format: 'pdf' | 'docx') {
  const context = captureFormContext()
  if (!context) return
  const no = context.reportNo
  try {
    const result = await reportVersionObjectUrl(no, version.id, context.view, format, true)
    if (!isCurrentForm(context)) { URL.revokeObjectURL(result.url); return }
    documentNotices.value = version.warnings.filter(w => w === '检测地点超出模板容量，已截断，请核对')
    const anchor = document.createElement('a')
    const label = version.outputKind === 'official' ? '正式报告' : '内部审核包'
    anchor.href = result.url
    anchor.download = `${no}-${label}-${version.versionLabel}.${format}`
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(result.url), 1000)
  } catch (error) {
    if (isCurrentForm(context)) ElMessage.error(error instanceof Error ? error.message : '报告下载失败')
  }
}
// CMA 盖章但检测依据超出一单一库范围 → 各报告节点持续提示
const cmaScopeWarn = computed(() => {
  const f = detail.value.summary?.find((s) => s.title === '实验信息')?.fields.find(([k]) => k === '检测依据范围')
  return String(f?.[1] ?? '').includes('超出一单一库')
})
// 签名状态由报告流程状态推导（与后端一致），随流转实时更新
const SIG_ORDER = ['待审核', '待批准', '待打印', '待发放', '已发放']
const signatures = computed<{ 主检: string; 审核: string; 批准: string }>(() => {
  // 优先用后端记录的各步骤电子签名（含已签/待签兜底）
  const fromBackend = (detail.value as unknown as { signatures?: Record<string, string> })?.signatures
  if (fromBackend && (fromBackend.主检 || fromBackend.审核 || fromBackend.批准)) {
    return { 主检: fromBackend.主检 || '待签', 审核: fromBackend.审核 || '待签', 批准: fromBackend.批准 || '待签' }
  }
  const idx = SIG_ORDER.indexOf(selectedReport.value?.status ?? '')
  return { 主检: '已签', 审核: idx >= 2 ? '已签' : '待签', 批准: idx >= 3 ? '已签' : '待签' }
})
const stampLabel = computed(() => {
  const seal = detail.value.summary?.find((s) => s.title === '委托信息')?.fields.find(([k]) => k === '盖章要求')?.[1]
  return (seal as string) || 'CMA'
})
const opinion = ref('')
const complianceOpen = ref(false)
const compliancePreflight = ref<CompliancePreflight | null>(null)
const complianceSubmitting = ref(false)
const returnDialogOpen = ref(false)
const returnSubmitting = ref(false)
const returnMode = ref<'entrust_only' | 'data_only' | 'entrust_and_data'>('data_only')
let complianceContext: ReportFormContext | null = null
let returnContext: ReportFormContext | null = null

// 中间报告复用审核节点的动作与权限
const actionPageKey = computed(() => (pageKey.value === 'interim_report' ? 'review' : pageKey.value))
const isDecisionNode = computed(() => ['review', 'approval'].includes(actionPageKey.value))
const canEditReport = computed(() => (
  !!selectedReport.value
  && ['检测录入中', '退回待重传', '检测更改中'].includes(selectedReport.value.status)
))
const passAction = computed(() => actionPageKey.value === 'release' ? 'report.distribution.complete' : `report.${actionPageKey.value}.pass`)
const returnAction = computed(() => `report.${actionPageKey.value}.return`)
// 撤回归属完成该操作的当前模块，不再放到下一个流程页面。
const undoByPage: Record<string, { action: string; label: string }> = {
  review: { action: 'report.review.undo', label: '撤回审核完成' },
  approval: { action: 'report.approval.undo', label: '撤回批准完成' },
  print: { action: 'report.print.undo', label: '撤回签发完成' },
  archive: { action: 'report.archive.undo', label: '撤销归档' },
}
const undoAction = computed(() => undoByPage[actionPageKey.value]?.action ?? '')
const undoLabel = computed(() => undoByPage[actionPageKey.value]?.label ?? '撤销')
const nodeActions = computed(() => reportNodeActions[actionPageKey.value] ?? reportNodeActions.default)

const actionNames: Record<string, string> = {
  report_check: '校核通过',
  review: '审核通过',
  approval: '批准通过',
  print: '确认签发',
  archive: '归档',
  release: '发放',
}
const passedStatus: Record<string, string> = {
  report_check: '待审核',
  review: '待批准',
  approval: '待打印',
  print: '待发放',
  release: '已发放',
}
const RETURNED_STATUS = '退回待重传'
// 各节点页面期望处理的报告状态：报告校核节点同时受理新报告与被退回需重传的报告
const nodeExpectedStatus: Record<string, string[]> = {
  report_check: ['待校核', RETURNED_STATUS],
  review: ['待审核'],
  approval: ['待批准'],
  print: ['待打印'],
  archive: ['待打印', '待发放', '已发放'],
  release: ['待发放', '已发放'],
}
const nextActionName = computed(() => actionNames[actionPageKey.value] ?? '')
const expectedStatuses = computed(() => nodeExpectedStatus[actionPageKey.value] ?? [])
// 选中报告是否在当前节点的处理范围内（不在则禁用通过/退回）
const canActOnSelected = computed(
  () =>
    !mutationPending.value && !!selectedReport.value &&
    (expectedStatuses.value.length === 0 || expectedStatuses.value.includes(selectedReport.value.status)) &&
    (!['archive','release'].includes(actionPageKey.value) || selectedReport.value.allowedActions?.includes(passAction.value) === true),
)
const undoExpectedStatus: Record<string, string> = {
  'report.review.undo': '待批准',
  'report.approval.undo': '待打印',
  'report.print.undo': '已发放',
}
const canUndoSelected = computed(() => {
  const row = selectedReport.value
  const action = undoAction.value
  if (!row || !action || mutationPending.value) return false
  if (action === 'report.archive.undo') return row.allowedActions?.includes(action) === true
  if (action === 'report.print.undo' && row.archiveState === '归档完成') return false
  return (row.status === undoExpectedStatus[action] || (action === 'report.print.undo' && row.status === '待发放')) && row.allowedActions?.includes(action) === true
})

// 报告校核节点：新生成（待校核）或被退回（退回待重传）的报告，都必须先上传报告正文与原始记录
const isReturnedReport = computed(() => selectedReport.value?.status === RETURNED_STATUS)
const requiresUpload = computed(
  () => selectedReport.value?.status === '待校核' || selectedReport.value?.status === RETURNED_STATUS,
)
// 是否已上传过报告正文/原始记录（排除系统生成的封面），决定退回/新报告能否提交校核
const reportHasUploads = computed(() =>
  (uploadedAtts.value[selectedReport.value?.reportNo ?? ''] ?? []).some((a) => a.source !== '模板生成'),
)
const needsReupload = computed(
  () => actionPageKey.value === 'report_check' && requiresUpload.value && !reportHasUploads.value,
)
// 检测信息录入：报告校核节点由检测人员录入标准/仪器/检测日期，未录入不能提交校核
const hasTestInfo = computed(() =>
  Boolean((detail.value as unknown as Record<string, unknown>).checkInput
    ? ((detail.value as unknown as { checkInput?: { standard?: string } }).checkInput?.standard)
    : false),
)
const showTestInfoForm = computed(
  () => actionPageKey.value === 'report_check' && session.canAction('report.attachment.upload') && !!selectedReport.value,
)
const needsTestInfo = computed(() => actionPageKey.value === 'report_check' && !hasTestInfo.value)
const canPass = computed(
  () => canActOnSelected.value && (['review', 'approval', 'print'].includes(actionPageKey.value) || (!needsReupload.value && !needsTestInfo.value && !documentVersionBlocker.value)),
)

const testInfo = reactive({
  standard: '', instrument: '', testStartDate: '', testEndDate: '', owner: '',
  conclusion: '', resultStatus: '合格', unqualifiedParams: '',
  recordNo: '', result: '', assignedReviewer: '', assignedApprover: '', remark: '',
})
const savingTestInfo = ref(false)

// 选中报告变化时，用已录入的 checkInput 预填表单
watchEffect(() => {
  const ci = (detail.value as unknown as { checkInput?: Record<string, string> }).checkInput
  if (ci) {
    testInfo.standard = ci.standard ?? ''
    testInfo.instrument = ci.instrument ?? ''
    testInfo.testStartDate = ci.testStartDate ?? ''
    testInfo.testEndDate = ci.testDate ?? ''
  }
})
async function saveTestInfo() {
  const row = selectedReport.value
  if (!row) return
  if (!testInfo.standard || !testInfo.instrument || !testInfo.testStartDate || !testInfo.testEndDate) {
    ElMessage.warning('检测标准、试验设备、试验开始日期、试验结束日期为必填')
    return
  }
  savingTestInfo.value = true
  const context = beginMutation()
  if (!context) { savingTestInfo.value = false; return }
  try {
    await updateTestInfo(row.reportNo, { ...testInfo, testEditVersion: (detail.value as any)?.testEditVersion })
    if (!isCurrentForm(context)) return
    // 刷新明细（三库校验结果 + 实验信息回填）
    const next = { ...detailCache.value }
    delete next[row.reportNo]
    detailCache.value = next
    await loadDocumentState()
    if (!isCurrentForm(context)) return
    ElMessage.success('检测信息已录入，已自动校验三库')
  } catch (e) {
    if (isCurrentForm(context)) ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    if (isCurrentForm(context)) savingTestInfo.value = false
    endMutation(context)
  }
}

// 已上传附件（后端模式来自 SQLite，mock 模式来自 localStorage），按报告缓存
const uploadedAtts = ref<Record<string, Attachment[]>>({})
async function loadUploaded(reportNo: string) {
  const context = captureFormContext()
  if (!context || context.reportNo !== reportNo) return
  try {
    const rows = await listUploadedAttachments(reportNo, context.view)
    if (!isCurrentForm(context)) return
    uploadedAtts.value = { ...uploadedAtts.value, [reportNo]: rows }
  } catch {
    if (isCurrentForm(context)) uploadedAtts.value = { ...uploadedAtts.value, [reportNo]: [] }
  }
}
watchEffect(() => {
  const no = selectedReport.value?.reportNo
  if (no && uploadedAtts.value[no] === undefined) loadUploaded(no)
})

const currentAttachments = computed<Attachment[]>(() => {
  const base = (detail.value.attachments ?? []) as Attachment[]
  const extra = uploadedAtts.value[selectedReport.value?.reportNo ?? ''] ?? []
  return [...base, ...extra].filter(file => !isLegacySystemCover(file))
})
const imageAttachments = computed(() =>
  currentAttachments.value.filter((file) =>
    file.id != null && ((file.contentType ?? '').startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(file.name)),
  ),
)

// 预览：应用内对话框 + iframe，避免新窗口被拦截；不可在线预览的类型给出下载提示
const previewDialogOpen = ref(false)
const previewSrc = ref('')
const previewTitle = ref('')
const previewUnsupported = ref(false)
const previewFileRef = ref<Attachment | null>(null)

async function previewFile(file: Attachment) {
  const context = captureFormContext()
  if (!context) return
  previewTitle.value = file.name
  previewFileRef.value = file
  // 系统种子附件（无 id 无 url）→ 生成占位封面预览
  if (file.id == null && !file.url) {
    const html = `<!doctype html><meta charset="utf-8"><body style="font-family:sans-serif;padding:40px;line-height:1.8">
      <h2>${file.name}</h2><p>${file.type} · ${file.source} · ${file.status}</p>
      <p>报告 ${selectedReport.value?.reportNo} · ${detail.value.projectName}</p>
      <p style="color:#888">（演示占位：系统生成内容，真实环境为服务端转换的 PDF）</p></body>`
    previewSrc.value = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
    previewUnsupported.value = false
    previewDialogOpen.value = true
    return
  }
  const { url, contentType } = await attachmentObjectUrl(file, context.view, false)
  if (!isCurrentForm(context)) { URL.revokeObjectURL(url); return }
  previewUnsupported.value = !isPreviewable(contentType, file.name)
  previewSrc.value = previewUnsupported.value ? '' : url
  previewDialogOpen.value = true
}
async function downloadFile(file: Attachment) {
  const context = captureFormContext()
  if (!context) return
  if (file.id == null && !file.url) {
    // 种子附件无真实内容，下载占位说明
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([`${file.name} (系统生成占位)`], { type: 'text/plain' }))
    a.download = file.name
    a.click()
    return
  }
  const { url } = await attachmentObjectUrl(file, context.view, true)
  if (!isCurrentForm(context)) { URL.revokeObjectURL(url); return }
  const a = document.createElement('a')
  a.href = url
  a.download = file.name
  a.click()
}
function downloadFromPreview() {
  if (previewFileRef.value) downloadFile(previewFileRef.value)
}

// 报告整体预览/下载：用结构化数据生成封面 + 信息 + 附件清单
function buildReportHtml(): string {
  const r = selectedReport.value
  const d = detail.value
  const sections = (d.summary ?? [])
    .map((s) => `<h3>${s.title}</h3>` + s.fields.map(([k, v]) => `<div><b>${k}</b>：${v}</div>`).join(''))
    .join('')
  const atts = currentAttachments.value.map((f) => `<li>${f.name} — ${f.status}</li>`).join('')
  return `<!doctype html><meta charset="utf-8"><body style="font-family:sans-serif;max-width:820px;margin:auto;padding:40px;line-height:1.8">
    <h1 style="text-align:center;letter-spacing:8px">检 测 报 告</h1>
    <div><b>报告编号</b>：${r?.reportNo ?? ''}</div>
    <div><b>工程名称</b>：${d.projectName}</div>
    <div><b>检测项目</b>：${r?.project ?? ''}</div>
    <hr>${sections}<h3>附件清单</h3><ul>${atts}</ul>
    <p style="margin-top:40px">主检：已签　审核：${r?.status === '待审核' ? '待签' : '已签'}　批准：待签</p></body>`
}
function previewMerged() {
  previewFileRef.value = null
  previewUnsupported.value = false
  previewSrc.value = URL.createObjectURL(new Blob([buildReportHtml()], { type: 'text/html' }))
  previewTitle.value = `${selectedReport.value?.reportNo ?? ''} 报告合并预览`
  previewDialogOpen.value = true
}
function downloadMerged() {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([buildReportHtml()], { type: 'text/html' }))
  a.download = `${selectedReport.value?.reportNo ?? 'report'}.html`
  a.click()
}

// 上传对话框
const uploadDialogOpen = ref(false)
const uploading = ref(false)
const dialogFileList = ref<UploadUserFile[]>([])
function openUpload() {
  dialogFileList.value = []
  uploadDialogOpen.value = true
}
function onUploadChange(_file: unknown, fileList: UploadUserFile[]) {
  dialogFileList.value = fileList
}
async function confirmUpload() {
  const row = selectedReport.value
  if (!row || !dialogFileList.value.length) return
  const context = beginMutation()
  if (!context) return
  const files = [...dialogFileList.value]
  uploading.value = true
  try {
    for (const f of files) {
      if (!isCurrentForm(context)) return
      if (f.raw) await uploadAttachment(row.reportNo, f.raw)
    }
    if (!isCurrentForm(context)) return
    await loadUploaded(row.reportNo)
    if (!isCurrentForm(context)) return
    await loadDocumentState()
    if (!isCurrentForm(context)) return
    uploadDialogOpen.value = false
    ElMessage.success(`已上传 ${files.length} 个文件并入库，可直接提交校核`)
  } catch (e) {
    if (isCurrentForm(context)) ElMessage.error(e instanceof Error ? e.message : '上传失败')
  } finally {
    if (isCurrentForm(context)) uploading.value = false
    endMutation(context)
  }
}

function deadlineTagType(deadline: string) {
  if (deadline.includes('超期')) return 'danger'
  if (deadline.includes('加急')) return 'warning'
  return 'info'
}

// 批准后申请更改：仅 报告更改申请 页、且报告处于 待打印/待发放/已发放 时可申请
const canRequestChange = computed(
  () =>
    pageKey.value === 'change_request' && !formReadOnly.value &&
    !!selectedReport.value &&
    ['待打印', '待发放', '已发放'].includes(selectedReport.value.status),
)
async function doRequestChange() {
  let row = selectedReport.value
  const context = beginMutation()
  if (!row || !context) return
  try {
    const { value } = await ElMessageBox.prompt('填写更改原因（报告将退回到「委托更改」重新走更改流程，原信息保留）', '申请报告更改', {
      confirmButtonText: '确认申请', cancelButtonText: '取消', inputType: 'textarea',
    })
    if (!isCurrentForm(context)) return
    const res = await requestReportChange(row.reportNo, (value || '').trim())
    if (!isCurrentForm(context)) return
    row = {...row}
    row.status = res?.status ?? '委托更改中'
    replaceReportRow(row.reportNo, row)
    const next = { ...detailCache.value }; delete next[row.reportNo]; detailCache.value = next
    ElMessage.success(`${row.reportNo} 已转入委托更改，请到「委托管理 → 委托更改」继续`)
    formOpen.value = false
    await refreshReportList()
  } catch (e) {
    if (isCurrentForm(context) && e !== 'cancel') ElMessage.error(e instanceof Error ? e.message : '申请失败')
  } finally {
    endMutation(context)
  }
}
async function handlePass() {
  const row = selectedReport.value
  if (!row || !canPass.value) return
  const context = beginMutation()
  if (!context) return
  try {
    if (actionPageKey.value === 'review' || actionPageKey.value === 'approval') {
      const stage = actionPageKey.value === 'review' ? 'report_review' : 'report_approval'
      const preflight = await fetchCompliancePreflight(row.reportNo, stage)
      if (!isCurrentForm(context)) return
      if (preflight.required) {
        compliancePreflight.value = preflight
        complianceContext = context
        complianceOpen.value = true
        return
      }
    }
    await performReportPass({}, context)
  } catch (e) {
    if (isCurrentForm(context)) ElMessage.error(e instanceof Error ? e.message : '合规预检失败')
  } finally {
    endMutation(context)
  }
}

async function performReportPass(compliance: ComplianceConfirmation, context: ReportFormContext) {
  let row = selectedReport.value
  if (!row || !isCurrentForm(context)) return false
  const action = passAction.value
  const status = passedStatus[actionPageKey.value]
  const actionName = nextActionName.value
  try {
    // 后端模式：调接口持久化，刷新后状态保留；mock 模式：本地更新
    const res = await reportAction(context.reportNo, action, compliance)
    if (!isCurrentForm(context)) return false
    row = {...row}
    row.status = res?.status ?? status ?? row.status
    if (res?.sampleStatus) row.sampleStatus = res.sampleStatus
    if (typeof res?.stamped === 'boolean') row.stamped = res.stamped
    if (typeof res?.outOfScope === 'boolean') {
      row.outOfScope = res.outOfScope
      row.outOfScopeNote = res.outOfScopeNote
    }
    replaceReportRow(row.reportNo, row)
    // 流转后让明细重新拉取（样品状态/签名等回填）
    if (selectedReport.value) {
      const next = { ...detailCache.value }
      delete next[row.reportNo]
      detailCache.value = next
    }
    const oos = res?.outOfScope ? '（超范围，已通知批准人）' : ''
    ElMessage.success(res?.esignPending ? (res.message || '本节点已确认，请完成本人电子签署') : `${row.reportNo} ${actionName}，已流转至「${row.status}」${oos}`)
    if (res?.esignPending) window.dispatchEvent(new Event('esign-stage-confirmed'))
    formOpen.value = false
    await refreshReportList()
    return true
  } catch (e) {
    if (isCurrentForm(context)) ElMessage.error(e instanceof Error ? e.message : '操作失败')
    return false
  }
}

async function confirmCompliancePass(payload: ComplianceConfirmation) {
  if (!complianceOpen.value || !isCurrentForm(complianceContext) || !canPass.value) return
  const context = beginMutation()
  if (!context) return
  complianceSubmitting.value = true
  try {
    await performReportPass(payload, context)
  } finally {
    if (isCurrentForm(context)) complianceSubmitting.value = false
    endMutation(context)
  }
}

async function handleReturn() {
  const row = selectedReport.value
  const context = captureFormContext()
  if (!row || !context || formReadOnly.value || !canActOnSelected.value) return
  if (!opinion.value.trim()) {
    ElMessage.warning('退回前必须填写退回原因')
    return
  }
  if (isDecisionNode.value) {
    returnContext = context
    returnMode.value = 'data_only'
    returnDialogOpen.value = true
    return
  }
  await performReturn('data_only')
}

async function performReturn(mode: 'entrust_only' | 'data_only' | 'entrust_and_data') {
  let row = selectedReport.value
  const context = beginMutation()
  if (!row || !context) return false
  const note = opinion.value.trim()
  const action = returnAction.value
  try {
    const res = await reportAction(context.reportNo, action, {
      note,
      returnMode: mode,
    })
    if (!isCurrentForm(context)) return false
    row = {...row}
    row.status = res?.status ?? (mode === 'data_only' ? '检测更改中' : '委托更改中')
    if (res?.dataStatus) row.dataStatus = res.dataStatus
    replaceReportRow(row.reportNo, row)
    const next = { ...detailCache.value }
    delete next[row.reportNo]
    detailCache.value = next
    const fallbackTarget = mode === 'entrust_only'
      ? '委托更改 → 合同评审 → 报告审核'
      : mode === 'entrust_and_data'
        ? '委托更改 → 合同评审 → 检测数据更改 → 报告审核'
        : '检测数据更改 → 报告审核'
    const target = res?.returnPlan?.targetLabel ?? fallbackTarget
    ElMessage.warning(`${row.reportNo} 已退回，后续路径：${target}`)
    formOpen.value = false
    await refreshReportList()
    return true
  } catch (e) {
    if (isCurrentForm(context)) ElMessage.error(e instanceof Error ? e.message : '操作失败')
    return false
  } finally {
    endMutation(context)
  }
}

async function confirmReturn() {
  const context = returnContext
  if (!returnDialogOpen.value || !isCurrentForm(context) || !canActOnSelected.value || !opinion.value.trim()) return
  returnSubmitting.value = true
  try {
    // performReturn closes only its own current form. A delayed list refresh
    // must not close a new report's return dialog opened in the meantime.
    await performReturn(returnMode.value)
  } finally {
    if (isCurrentForm(context)) returnSubmitting.value = false
  }
}

async function handleUndo() {
  let row = selectedReport.value
  if (!row || !undoAction.value || !canUndoSelected.value) return
  const context = beginMutation()
  if (!context) return
  const action = undoAction.value
  const label = undoLabel.value
  try {
    const res = await reportAction(context.reportNo, action)
    if (!isCurrentForm(context)) return
    row = {...row}
    row.status = res?.status ?? row.status
    if (typeof res?.stamped === 'boolean') row.stamped = res.stamped
    replaceReportRow(row.reportNo, row)
    const next = { ...detailCache.value }
    delete next[row.reportNo]
    detailCache.value = next
    ElMessage.success(`${row.reportNo} ${label}，已回退至「${row.status}」`)
    formOpen.value = false
    await refreshReportList()
  } catch (e) {
    if (isCurrentForm(context)) ElMessage.error(e instanceof Error ? e.message : '撤销失败')
  } finally {
    endMutation(context)
  }
}

function saveOpinion() {
  if (!captureFormContext() || formReadOnly.value || mutationPending.value) return
  ElMessage.success(opinion.value ? '审核意见已保存' : '请先填写审核意见')
}

function resetFormSession() {
  formSessionId.value += 1
  documentStateRequestId += 1
  mutationPending.value = false
  opinion.value = ''
  complianceOpen.value = false
  compliancePreflight.value = null
  complianceContext = null
  complianceSubmitting.value = false
  returnDialogOpen.value = false
  returnContext = null
  returnSubmitting.value = false
  returnMode.value = 'data_only'
  uploadDialogOpen.value = false
  uploading.value = false
  dialogFileList.value = []
  documentEditorOpen.value = false
  editDocument.value = blankDocumentContent()
  savingDocument.value = false
  savingTestInfo.value = false
  for (const key of Object.keys(testInfo) as (keyof typeof testInfo)[]) testInfo[key] = key === 'resultStatus' ? '合格' : ''
  documentPreflight.value = null
  documentVersions.value = []
  documentVersionsState.value = {}
  documentLoading.value = false
  documentGenerating.value = false
  documentJob.value = null
  previewDialogOpen.value = false
  previewFileRef.value = null
  previewSrc.value = ''
  previewTitle.value = ''
  previewUnsupported.value = false
  clearDocumentPreview()
  clearCover()
  coverLoading.value = false
  decisionPreviewRequestId += 1
  decisionPreviewError.value = ''; decisionPreviewIssue.value = undefined; decisionPreviewSigned.value = false
  decisionPreviewLabel.value = ''
  decisionPreviewLoading.value = false
}
watch(formOpen, opened => {
  if (!opened) {
    resetFormSession()
    selectedReportNo.value = ''
  }
}, { flush: 'sync' })
watch(selectedReport, row => {
  if (formOpen.value && !row) formOpen.value = false
}, { flush: 'sync' })
onBeforeUnmount(() => { listRequestId += 1; formOpen.value = false; resetFormSession() })

// BEGIN TEMPLATE STAGE ADAPTER
const fullReviewPage=computed(()=>['review','approval','print'].includes(pageKey.value))
const reviewContext=reactive({documentNotices,route,pageKey,pageName,session,selectedReport,formOpen,formReadOnly,mutationPending,canActOnSelected,canPass,passAction,returnAction,documentPdfUrl,documentPreflight,decisionPreviewLoading,decisionPreviewIssue,loadDocumentState,loadDecisionReportPreview,handlePass,handleUndo,canUndoSelected,undoAction,undoLabel,nextActionName,documentVersionBlocker,
  setDetail:(data:ReportDetailData)=>{if(selectedReport.value)detailCache.value={...detailCache.value,[selectedReport.value.reportNo]:data}},
  submitPass:async(payload:ComplianceConfirmation)=>{
    if(formReadOnly.value||!canPass.value||!canActOnSelected.value||!session.canAction(passAction.value))return false
    const context=beginMutation();if(!context)return false
    try{return await performReportPass(payload,context)}finally{endMutation(context)}
  },
  submitReturn:async(reason:string,mode:'entrust_only'|'data_only'|'entrust_and_data')=>{
    if(formReadOnly.value||!canActOnSelected.value||!session.canAction(returnAction.value)||!reason.trim())return false
    opinion.value=reason;return performReturn(mode)
  },
})
const ReportWorkspace=defineComponent({inheritAttrs:false,setup(_,{attrs,slots}){return()=>['review','approval','print'].includes(pageKey.value)?slots.default?.():h(ModuleWorkspace as any,attrs,slots)}})
const undoReport=createReportStageUndo({
  page:()=>pageKey.value,rows:()=>workRows.value,canAction:action=>session.canAction(action),
  perform:reportAction,refresh:refreshReportList,
  invalidate:reportNo=>{const next={...detailCache.value};delete next[reportNo];detailCache.value=next},
})
const reportStagePresentation=createReportStagePresentation(reactive({serverPaging:USE_BACKEND,pagingActive:computed(()=>['review','approval'].includes(pageKey.value)),reportPageState,setReportQuery,exportReportRows,reportPresentationLoading,reportPresentationError,pageKey,pageName,route,workRows,session,openForm,refreshReportList,formOpen,undoReport}))
const reportOutputPresentation=createReportOutputPresentation(reactive({serverPaging:USE_BACKEND,pagingActive:computed(()=>!['review','approval','change_request'].includes(pageKey.value)),reportPageState,setReportQuery,exportReportRows,reportPresentationLoading,reportPresentationError,pageKey,pageName,route,workRows,session,openForm,refreshReportList,formOpen,undoReport,
  completeOutput: async (reportNo: string, action: 'report.archive.pass' | 'report.distribution.complete') => {
    await reportAction(reportNo, action)
    const next = {...detailCache.value}
    delete next[reportNo]
    detailCache.value = next
  },
}))
const reportDetailContext=reactive({documentNotices,opinion,addPhotoSlot,addResultGroup,addResultItem,canActOnSelected,canEditReport,canPass,canRequestChange,canUndoSelected,cmaScopeWarn,coverHtml,coverLoading,coverPdfUrl,currentAttachments,detail,doRequestChange,documentEditorOpen,documentGenerating,documentJob,documentLoading,documentMissingLabels,documentPdfUrl,documentPreflight,documentVersionBlocker,documentVersions,documentVersionsState,downloadCover,downloadDocumentVersion,downloadFile,downloadMerged,editDocument,formReadOnly,formSessionId,generateDocument,handlePass,handleReturn,handleUndo,imageAttachments,loadDocumentState,needsReupload,nextActionName,nodeActions,openDocumentEditor,openUpload,pageName,passAction,pipelineAvailable,previewCover,previewDocumentVersion,previewFile,previewMerged,reportTimeline,returnAction,saveDocumentEditor,saveOpinion,saveTestInfo,savingDocument,savingTestInfo,selectedReport,session,showTestInfoForm,signatures,stampLabel,testInfo,testPreviousDate,undoAction,undoLabel,visibleSummarySections})
watch(() => JSON.stringify([pageKey.value, initKeyword.value, reportPageState.query, session.dataScope, session.userName]), async (_value, _old, onCleanup) => {
  if (!isReportModule.value) return
  let active = true
  onCleanup(() => { active = false })
  const requestId = ++listRequestId
  const page = pageKey.value
  const kw = initKeyword.value.trim()
  reportPresentationLoading.value=true;reportPresentationError.value=''
  try {
  const result = await requestReportPage();const rows=result.rows
  if (!active || requestId !== listRequestId || page !== pageKey.value) return
  workRows.value = rows.map((row) => ({ ...row }));reportPageState.total=result.total
  // 带 keyword 进入时同步到可见筛选框；普通报告查询始终以只读方式打开。
  keyword.value = kw
  if (kw && kw !== lastAutoKw) {
    const matched = workRows.value.find((r) => r.reportNo === kw)
    if (matched) {
      openForm(matched, pageKey.value === 'query' || route.query.mode === 'view')
      lastAutoKw = kw
    }
  }
  } catch(error) { if(active&&requestId===listRequestId)reportPresentationError.value=platformError(error /* report list load */) } finally { if(active&&requestId===listRequestId)reportPresentationLoading.value=false }
}, { immediate: true })
// END TEMPLATE STAGE ADAPTER
</script>


