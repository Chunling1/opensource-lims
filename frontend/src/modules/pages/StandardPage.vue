<template>
  <StandardWorkspace :title="pageName" :area-name="areaName" :module-name="moduleName" :path="route.path" :pages="pages" :active-key="pageKey" :show-command="false" :show-content="false">

  <PipelineWizard
    v-model="wizardOpen"
    :mode="wizardMode"
    :page-view="wizardMode === 'entrust'"
    :department="session.dataScope.department"
    :change-report-no="editReportNo"
    :in-place="true"
    :edit-entrust="editEntrustData"
    :read-only="wizardReadonly"
    :detail-view="wizardDetailView"
    @created="onReportCreated"
    @entrust-created="onEntrustCreated"
    @updated="onEdited"
    @entrust-updated="onEntrustEdited"
  />

  <div v-show="!(wizardOpen && wizardMode === 'entrust')" v-if="moduleKey === 'entrust' && ['registration','query'].includes(pageKey)"><RegistrationPresentation :model="registrationPresentation" /></div>
  <component :is="specialListComponent" v-else-if="specialListComponent" :context="specialListContext" />
  <template v-else>
  <BusinessFilters
    :state="filter.state"
    :status-options="displayStatusOptions"
    :total="filter.result.value.length"
    :keyword-placeholder="active.keyword"
    :show-date="Boolean(active.config.dateField)"
    @reset="filter.reset"
  >
    <template #actions>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <el-tag v-if="selectedRows.length" size="small" type="success">已选 {{ selectedRows.length }} 条</el-tag>
        <el-button size="small" :disabled="!selectedRow" @click="viewSelected">查看</el-button>
        <el-button
          v-if="moduleKey === 'system' && pageKey === 'runtime_parameters'"
          size="small"
          type="primary"
          :disabled="!selectedRow"
          @click="openRuntimeEdit"
        >修改配置</el-button>
        <template v-if="moduleKey === 'entrust' && !isEntrustQuery">
          <el-button size="small" type="success" @click="openWizard('entrust')">新增委托</el-button>
          <el-button size="small" type="primary" :disabled="!canModifySelectedEntrust" @click="editSelectedEntrust">修改</el-button>
          <el-button size="small" type="success" plain :disabled="!canAddSampleForSelectedEntrust" @click="addSampleForSelected">新增样品</el-button>
          <el-button size="small" :disabled="!canCompleteSelectedEntrust" type="success" @click="completeSelectedEntrust">完成登记</el-button>
          <el-button size="small" :disabled="!canUncompleteSelectedEntrust" type="warning" plain @click="uncompleteSelectedEntrust">撤销完成</el-button>
        </template>
        <template v-if="isEntrustQuery">
          <el-button size="small" :disabled="!selectedRow" @click="exportSelectedEntrustPdf">PDF导出</el-button>
          <el-button size="small" :disabled="!selectedRow" @click="openSelectedEntrustPrint">打印</el-button>
          <el-button size="small" :disabled="!selectedRow?.reportNo" @click="openQueryAttachments">附件管理</el-button>
        </template>
        <template v-if="moduleKey === 'testing'">
          <el-button size="small" type="primary" :disabled="!selectedRow" @click="jumpSelectedTesting">{{ selectedTestingJumpLabel }}</el-button>
          <el-button size="small" :disabled="!selectedRow || selectedRow.sampleStatus !== '已领取'" @click="returnStockSelected">撤销领取</el-button>
          <el-button size="small" type="danger" plain :disabled="!selectedRow || !['已领取','已出库'].includes(String(selectedRow.sampleStatus))" @click="disposeSelected">样品处置</el-button>
        </template>
        <el-button size="small" @click="exportCurrentList">导出</el-button>
      </div>
    </template>
  </BusinessFilters>

  <ModuleContentCard :title="profile.title"  data-ui="workbench-single">
    <el-alert v-if="moduleKey === 'sample' && pageKey === 'flow_query'" :title="sampleLoadError || (sampleListLoading ? '正在加载样品流转记录…' : '包含当前数据权限范围内所有已保存样品（含登记中、归档和作废记录）；未记录的流转信息留空。')" :type="sampleLoadError ? 'error' : 'info'" :closable="false" />
    <template #meta>
      <el-tag size="small" type="info">共 {{ filter.result.value.length }} 条</el-tag>
    </template>

    <el-table v-if="isEntrustQuery" ref="workbenchTableRef" :data="pagedRows" border :height="tableHeight" row-key="reportNo"  highlight-current-row @selection-change="onWorkbenchSelectionChange" @row-click="toggleWorkbenchRow">
      <el-table-column type="selection" width="42" fixed="left" />
      <el-table-column v-for="column in entrustQueryColumns" :key="column.key" :prop="column.key" :label="column.label" :width="column.width" :min-width="column.minWidth" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag v-if="column.key === 'dataStatus'" size="small" type="info">{{ row.dataStatus || row.status }}</el-tag>
          <span v-else>{{ row[column.key] || '—' }}</span>
        </template>
      </el-table-column>
    </el-table>

    <el-table v-else-if="moduleKey === 'entrust'" ref="workbenchTableRef" :data="pagedRows" border :height="tableHeight" row-key="no"  highlight-current-row @selection-change="onWorkbenchSelectionChange" @row-click="toggleWorkbenchRow">
      <el-table-column type="expand" width="42">
        <template #default="{ row }">
          <div class="mb-3">
            <div class="h6 mb-3">已挂样品单（{{ linkedSamples(row).length }} 条）</div>
            <el-table :data="linkedSamples(row)" border size="small" >
              <el-table-column v-for="column in linkedSampleColumns" :key="column.key" :prop="column.key" :label="column.label" :width="column.width" :min-width="column.minWidth" show-overflow-tooltip>
                <template #default="{ row: sample }">
                  <el-tag v-if="column.key === 'dataStatus'" size="small" type="info">{{ sample.dataStatus || sample.status }}</el-tag>
                  <span v-else>{{ sample[column.key] || '—' }}</span>
                </template>
              </el-table-column>
              <template #empty><el-empty description="该委托单下暂无样品" :image-size="42" /></template>
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column type="selection" width="42" />
      <el-table-column prop="erpProjectNo" label="外部ERP项目编号" min-width="150" />
      <el-table-column prop="no" label="委托编号" min-width="145" />
      <el-table-column prop="contractPartyA" label="合同甲方" min-width="150" show-overflow-tooltip />
      <el-table-column prop="otherPartyA" label="其他甲方（付款方）" min-width="170" show-overflow-tooltip />
      <el-table-column prop="entrustDate" label="委托时间" width="120" />
      <el-table-column prop="erpProjectType" label="外部ERP项目类型" width="130" />
      <el-table-column prop="handler" label="委托经办人" width="120" />
      <el-table-column prop="handlerDepartment" label="委托经办部门" min-width="140" show-overflow-tooltip />
      <el-table-column prop="amount" label="委托金额" width="110" />
      <el-table-column label="数据状态" width="120">
        <template #default="{ row }"><el-tag size="small" type="info">{{ row.dataStatus || row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="consignor" label="委托人" width="110" />
      <el-table-column prop="client" label="委托单位" min-width="150" show-overflow-tooltip />
      <el-table-column prop="clientAddress" label="委托单位地址" min-width="180" show-overflow-tooltip />
    </el-table>

    <el-table v-else-if="moduleKey === 'testing'" ref="workbenchTableRef" :data="pagedRows" border :height="tableHeight"  highlight-current-row @selection-change="onWorkbenchSelectionChange" @row-click="toggleWorkbenchRow">
      <el-table-column type="selection" width="42" />
      <el-table-column prop="sampleNo" label="样品编号" min-width="130" />
      <el-table-column prop="reportNo" label="报告编号" min-width="160" />
      <el-table-column prop="project" label="样品/工程名称" min-width="160" show-overflow-tooltip />
      <el-table-column prop="client" label="委托单位" min-width="150" show-overflow-tooltip />
      <el-table-column label="数据状态" width="120">
        <template #default="{ row }"><el-tag size="small" :type="testStatusType(String(row.status))">{{ testingStatusDisplay(String(row.status)) }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="sampleStatus" label="样品状态" width="100" />
      <el-table-column prop="owner" label="主检/责任人" width="110" />
      <el-table-column prop="department" label="报告中心/部门" min-width="140" show-overflow-tooltip />
    </el-table>

    <el-table v-else-if="moduleKey === 'finance'" ref="workbenchTableRef" :data="pagedRows" border :height="tableHeight"  highlight-current-row @selection-change="onWorkbenchSelectionChange" @row-click="toggleWorkbenchRow">
      <el-table-column type="selection" width="42" />
      <el-table-column prop="billNo" label="费用单号" min-width="150" />
      <el-table-column prop="entrustNo" label="委托编号" min-width="150" />
      <el-table-column prop="client" label="委托单位" min-width="150" />
      <el-table-column prop="amount" label="应收金额" width="120" />
      <el-table-column prop="paid" label="实收金额" width="120" />
      <el-table-column prop="invoice" label="发票状态" width="110" />
      <el-table-column prop="erp" label="外部ERP同步" width="110" />
      <el-table-column prop="status" label="当前状态" width="110" />
    </el-table>

    <el-table v-else-if="moduleKey === 'quality'" ref="workbenchTableRef" :data="pagedRows" border :height="tableHeight"  highlight-current-row @selection-change="onWorkbenchSelectionChange" @row-click="toggleWorkbenchRow">
      <el-table-column type="selection" width="42" />
      <el-table-column prop="code" label="编号" min-width="140" />
      <el-table-column prop="name" label="名称" min-width="190" />
      <el-table-column prop="category" label="类别" width="130" />
      <el-table-column prop="department" label="所属科室" width="130" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="plan" label="计划/事项" width="130" />
      <el-table-column prop="dueDate" label="到期日期" width="120" />
    </el-table>

    <el-table v-else-if="moduleKey === 'system'" ref="workbenchTableRef" :data="pagedRows" border :height="tableHeight"  highlight-current-row @selection-change="onWorkbenchSelectionChange" @row-click="toggleWorkbenchRow">
      <el-table-column type="selection" width="42" />
      <el-table-column prop="key" label="配置项" min-width="160" />
      <el-table-column prop="scope" label="作用范围" min-width="220" />
      <el-table-column prop="value" label="当前配置" min-width="180" />
      <el-table-column prop="owner" label="维护角色" width="130" />
      <el-table-column prop="updatedAt" label="更新时间" width="120" />
    </el-table>

    <SampleTable v-else :rows="pagedRows" :show-flow-info="moduleKey === 'sample' && pageKey === 'flow_query'" @select="selectRow" @selection="onWorkbenchSelectionChange" @view="viewSample" @edit="editSample" />

    <template #footer>
    <el-pagination
      v-model:current-page="tablePage"
      background
      layout="total, prev, pager, next"
      :total="filter.result.value.length"
      :page-size="tablePageSize"
    />
    </template>
  </ModuleContentCard>

  <!-- 行详情：按状态展示相应信息 -->
  <el-drawer v-model="detailOpen" :title="detailTitle" size="460px">
    <el-alert v-if="selectedRow" :type="statusType" :closable="false" show-icon :title="statusNote" class="text-muted small" />
    <div v-if="selectedRow" class="row g-3">
      <div v-for="[label, prop] in detailFields" :key="prop" class="col-12 col-md-6">
        <span class="form-label d-block">{{ label }}</span>{{ display(prop) }}
      </div>
    </div>
  </el-drawer>

  </template>
  <el-dialog v-model="runtimeEditOpen" title="修改系统运行参数" width="560px" append-to-body>
    <el-alert type="warning" :closable="false" show-icon title="修改会记录更新时间和原因。" class="text-muted small" />
    <el-form label-position="top">
      <el-form-item label="配置项"><el-input :model-value="String(selectedRow?.key ?? '')" disabled /></el-form-item>
      <el-form-item label="当前配置"><el-input v-model="runtimeForm.value" placeholder="请输入新的配置值" /></el-form-item>
      <el-form-item label="修改原因"><el-input v-model="runtimeForm.reason" type="textarea" :rows="3" placeholder="请说明修改原因，便于审计追踪" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="runtimeEditOpen = false">取消</el-button>
      <el-button type="primary" @click="saveRuntimeEdit">保存配置</el-button>
    </template>
  </el-dialog>

  <SampleDrawer v-model="drawerOpen" />

  <AttachmentManagerDialog v-model="queryAttachmentOpen" :report-no="String(selectedRow?.reportNo || '')" view="sample_flow_query" :title="`附件管理 · ${String(selectedRow?.reportNo || '')}`" />

  <!-- 打印委托合同单：PDF 预览 + 下载 Word（与模板完全一致） -->
  <el-dialog v-model="printOpen" title="打印委托单" width="1200px" top="5vh" @closed="clearPrintPreview">
    <div >
      <div >
        <span>打印模板</span>
        <el-segmented v-model="printTemplateKind" :options="BUSINESS_FORM_TEMPLATE_OPTIONS" size="small" :disabled="printLoading" @change="onPrintTemplateChange" />
      </div>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <el-tag v-if="printEngine" size="small" type="success">WPS PDF</el-tag>
        <el-button size="small" :loading="printLoading" @click="reloadPrint">刷新预览</el-button>
        <el-button size="small" @click="downloadEntrustDoc">导出 Word</el-button>
      </div>
    </div>
    <CommissionPdfPages :url="printUrl" :filename="`${listPrintSample || selectedRow?.no || '委托单'}-${printTemplateKind}-委托单.pdf`" :disabled="printLoading || !printOpen" />
    <DataEntryPreview v-if="printUrl" :url="printUrl" title="委托单预览" name="" type="application/pdf" embedded compact persistent hide-download />
    <el-empty v-else :description="printLoading ? '生成中…' : '点「预览」生成委托单'" />
  </el-dialog>

  </StandardWorkspace>
</template>

<script setup lang="ts">
import CommissionPdfPages from '../components/CommissionPdfPages.vue'
// BEGIN TEMPLATE REGISTRATION IMPORTS
import {fetchSamplePrint} from '@/services/pipeline'
import FlowList from "../../platformUi/lists/FlowList.vue"
import StorageList from "../../platformUi/lists/StorageList.vue"
import TaskList from "../../platformUi/lists/TaskList.vue"
import CancellationList from "../../platformUi/lists/CancellationList.vue"
import {createServerPage,fetchListPage,fetchListExport} from '../../platformUi/lists/serverPage'
import {useListPresentation} from "../../platformUi/lists/listPresentation"
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import {reactive,defineComponent,h} from 'vue'
import RegistrationPresentation from '../../platformUi/commissions/RegistrationPresentation.vue'
import {useRegistrationPresentation} from '../../platformUi/commissions/registrationPresentation'
import {AppError} from '../../services/common/errors'
const entrustPresentationLoading=ref(false),entrustPresentationError=ref<AppError|''>('')
// END TEMPLATE REGISTRATION IMPORTS
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { modules } from '@/data/modules'
import { entrustRows, financeRows, pageProfiles, qualityRows, reportWorkRows, sampleRows, systemRows, testingRows } from '@/data/mock'
import { sampleFlowRow } from '@/data/sampleFlow'
import { fetchReportRows } from '@/services/auth'
import type { ReportDetailView } from '@/services/reports'
import { useTableFilter, type FilterConfig } from '@/composables/tableFilter'
import { ElMessage, ElMessageBox } from 'element-plus'
import { BUSINESS_FORM_TEMPLATE_OPTIONS, PIPELINE_AVAILABLE, fetchDepartments, fetchSamples, fetchEntrustList, fetchEntrustDetail, fetchEntrustPrint, completeEntrust, uncompleteEntrust, submitSampleReturnStock, submitSampleDispose, type BusinessFormTemplateKind, type EntrustOrder, type SampleRow } from '@/services/pipeline'
import { useSessionStore } from '@/stores/session'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import BusinessFilters from '@/components/BusinessFilters.vue'
import ModuleContentCard from '@/components/ModuleContentCard.vue'
import SampleTable from '@/components/SampleTable.vue'
import SampleDrawer from '@/components/SampleDrawer.vue'
import PipelineWizard from '@/components/PipelineWizard.vue'
import AttachmentManagerDialog from '@/components/AttachmentManagerDialog.vue'
import { exportRowsXlsx, type XlsxColumn } from '@/services/xlsxExport'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const drawerOpen = ref(false)
const wizardOpen = ref(false)
const wizardMode = ref<'entrust' | 'samples'>('entrust')
const editReportNo = ref('')  // 样品就地修改：传给向导的报告号（inPlace）
const editEntrustData = ref<EntrustOrder | null>(null)  // 委托就地修改
const wizardReadonly = ref(false)
const pipelineAvailable = PIPELINE_AVAILABLE

// 工作台表格随视口高度铺满（el-table 的 height 仅认像素数值，calc 字符串无效）
const tableHeight = ref(560)
function calcTableHeight() {
  // 工作台表格上方固定区域约 410px（头部+标题+页签+筛选+卡片头），下留 ~20px 边距
  const el = document.querySelector('[data-ui~=workbench-single] table') as HTMLElement | null
  const top = el ? el.getBoundingClientRect().top : 410
  tableHeight.value = Math.max(300, window.innerHeight - top - 20)
}
onMounted(() => { calcTableHeight(); window.addEventListener('resize', calcTableHeight) })
onUnmounted(() => {
  window.removeEventListener('resize', calcTableHeight)
  clearPrintPreview()
})

function openWizard(mode: 'entrust' | 'samples') {
  ++entrustDetailSequence
  wizardReadonly.value = false
  editReportNo.value = ''
  editEntrustData.value = null
  wizardMode.value = mode
  wizardOpen.value = true
}
// 委托就地修改：用已登记信息预填委托表单
let entrustDetailSequence = 0
async function editEntrust(row: Row, readOnly = false) {
  const sequence = ++entrustDetailSequence
  try {
    const detail = await fetchEntrustDetail(Number(row.id))
    if (sequence !== entrustDetailSequence) return
    wizardReadonly.value = readOnly
    editReportNo.value = ''
    editEntrustData.value = detail
    wizardMode.value = 'entrust'
    wizardOpen.value = true
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '委托详情加载失败') }
}
// 样品就地修改：预填该报告样品信息（晚期阶段后端会拒绝并提示）
function editSample(row: Row, readOnly = false) {
  ++entrustDetailSequence
  wizardReadonly.value = readOnly
  editEntrustData.value = null
  editReportNo.value = String(row.reportNo ?? '')
  wizardMode.value = 'samples'
  wizardOpen.value = true
}
function onEdited() { loadSamples() }
function onEntrustEdited() { loadEntrust() }

// 打印委托合同单
const printOpen = ref(false)
const printLoading = ref(false)
const printUrl = ref('')
const printId = ref<number | null>(null)
const printTemplateKind = ref<BusinessFormTemplateKind>('product')
const printSourceHash = ref('')
const printEngine = ref('')
function clearPrintPreview() {
  if (printUrl.value) URL.revokeObjectURL(printUrl.value)
  printUrl.value = ''
  printSourceHash.value = ''
  printEngine.value = ''
}
async function openSelectedEntrustPrint() {
  if (!selectedRow.value) return ElMessage.warning('请先选择委托单')
  listPrintSample.value=''
  printId.value = selectedRow.value.id as number
  const projectType = `${selectedRow.value.projectType ?? ''} ${selectedRow.value.erpProjectType ?? ''}`
  printTemplateKind.value = projectType.includes('工程') ? 'engineering' : 'product'
  clearPrintPreview()
  printOpen.value = true
  await reloadPrint()
}
async function onPrintTemplateChange() {
  clearPrintPreview()
  await reloadPrint()
}
async function onCompleteEntrust(row: Row) {
  try {
    await ElMessageBox.confirm(`确认完成委托单 ${row.no}？完成后状态转为「委托完成」。`, '完成委托', { type: 'warning' })
  } catch { return }
  try {
    await completeEntrust(row.id as number)
    ElMessage.success('已完成委托')
    await loadEntrust()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}
async function reloadPrint() {
  if (printId.value == null && !listPrintSample.value) return
  printLoading.value = true
  try {
    const res = await (listPrintSample.value?fetchSamplePrint(listPrintSample.value,'pdf',printTemplateKind.value):fetchEntrustPrint(printId.value!, 'pdf', printTemplateKind.value))
    if (res.type === 'pdf') {
      clearPrintPreview()
      printUrl.value = res.url
      printSourceHash.value = res.sourceHash
      printEngine.value = res.engine
    }
  } catch (e) {
    ElMessage.error((e as Error).message || '生成失败')
  } finally {
    printLoading.value = false
  }
}
async function downloadEntrustDoc() {
  if (printId.value == null && !listPrintSample.value) return
  try {
    const res = await (listPrintSample.value?fetchSamplePrint(listPrintSample.value,'docx',printTemplateKind.value):fetchEntrustPrint(printId.value!, 'docx', printTemplateKind.value))
    if (res.type === 'docx') {
      if (printSourceHash.value && res.sourceHash && res.sourceHash !== printSourceHash.value) {
        URL.revokeObjectURL(res.url)
        ElMessage.warning('业务数据已变化，已重新生成预览，请确认后再导出')
        await reloadPrint()
        return
      }
      const a = document.createElement('a')
      a.href = res.url
      a.download = res.name
      a.click()
      setTimeout(() => URL.revokeObjectURL(res.url), 1000)
    }
  } catch (e) {
    ElMessage.error((e as Error).message || '下载失败')
  }
}
function onReportCreated() {
  // 保存只刷新当前页面，后续流程由用户通过菜单或操作按钮进入
  void loadSamples()
}
function onEntrustCreated() {
  // 保存只刷新当前页面，不自动跳转到样品登记
  void loadEntrust()
}
function addSampleFor(row: Row) {
  // 委托登记列表直接「新增样品」：跳样品登记页并预选该委托单
  router.push({ path: '/inspection/entrust/sample_register', query: { entrust: String(row.no ?? ''), addSample: '1' } })
}

const moduleKey = computed(() => route.meta.moduleKey ?? '')
const pageKey = computed(() => String(route.meta.pageKey ?? ''))
const isEntrustQuery = computed(() => moduleKey.value === 'entrust' && pageKey.value === 'query')
const wizardDetailView = computed<ReportDetailView>(() => {
  if (isEntrustQuery.value) return 'entrust_query'
  if (moduleKey.value === 'testing') return 'testing_task_query'
  if (moduleKey.value === 'sample') {
    if (pageKey.value === 'change') return 'sample_change'
    if (pageKey.value === 'disposal') return 'sample_disposal'
    return 'sample_flow_query'
  }
  return 'sample_flow_query'
})

interface ListColumn { key: string; label: string; width?: number; minWidth?: number }
const linkedSampleColumns: ListColumn[] = [
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
]
const entrustQueryColumns: ListColumn[] = [
  { key: 'entrustNo', label: '委托编号', minWidth: 140 },
  ...linkedSampleColumns,
  { key: 'consignor', label: '委托人', width: 110 },
  { key: 'consignorPhone', label: '委托人电话', width: 140 },
  { key: 'clientAddress', label: '委托单位地址', minWidth: 200 },
]

// 各模块的数据源、筛选字段与关键词占位
interface ModuleData {
  rows: Record<string, unknown>[]
  config: FilterConfig
  keyword: string
}
const moduleDataMap: Record<string, ModuleData> = {
  entrust: { rows: entrustRows.filter((r) => r.status !== '委托完成'), config: { statusField: 'status', dateField: 'date' }, keyword: '委托编号 / 委托单位 / 工程名称' },
  sample: { rows: sampleRows, config: { statusField: 'status', dateField: 'date' }, keyword: '样品编号 / 报告编号 / 委托单位' },
  testing: { rows: testingRows, config: { statusField: 'collectStatus', dateField: 'date' }, keyword: '任务编号 / 样品编号 / 检测项目' },
  finance: { rows: financeRows, config: { statusField: 'status', dateField: 'date' }, keyword: '费用单号 / 委托编号 / 委托单位' },
  quality: { rows: qualityRows, config: { statusField: 'status', dateField: 'dueDate' }, keyword: '编号 / 名称 / 科室' },
  system: { rows: systemRows, config: { dateField: 'updatedAt' }, keyword: '配置项 / 作用范围' },
}
// 后端模式下样品流转查询用真实样品（含入库/出库状态）
const backendSamples = ref<Record<string, unknown>[]>([])
const sampleListLoading = ref(false)
const sampleLoadError = ref('')
let sampleLoadSequence = 0
// 后端模式下委托列表用真实委托单
const backendEntrust = ref<Record<string, unknown>[]>([])
const backendEntrustQuery = ref<Record<string, unknown>[]>([])
// 检测任务查询：样品出库领取后进入检测的真实报告（录入 + 更改记录）
const backendTesting = ref<Record<string, unknown>[]>([])
const taskListBusy=ref(false),taskListError=ref('')
const active = computed<ModuleData>(() => {
  const base = moduleDataMap[moduleKey.value as string] ?? moduleDataMap.sample
  if (moduleKey.value === 'testing' && pipelineAvailable) {
    return {
      rows: backendTesting.value,
      config: { statusField: 'queryStatus', keywordFields: ['sampleNo', 'reportNo', 'client', 'project'] },
      keyword: '报告编号 / 样品编号 / 委托单位 / 工程名称',
    }
  }
  if (moduleKey.value === 'sample' && pipelineAvailable) {
    return {
      rows: backendSamples.value,
      config: { statusField: 'status', dateField: 'date', keywordFields: ['sampleNo', 'reportNo', 'client', 'projectName', 'inboundPerson', 'pickupPerson'] },
      keyword: '样品编号 / 报告编号 / 委托单位',
    }
  }
  if (moduleKey.value === 'entrust' && pipelineAvailable) {
    if (isEntrustQuery.value) {
      return {
        rows: backendEntrustQuery.value,
        config: { statusField: 'status', dateField: 'sampleRegisteredAt' },
        keyword: '搜索全部委托与样品字段',
      }
    }
    return {
      rows: backendEntrust.value,
      config: { statusField: 'status', dateField: 'date', keywordFields: ['no', 'client', 'projectName', 'contractNo'] },
      keyword: '委托编号 / 委托单位 / 工程名称',
    }
  }
  return base
})
const filter = useTableFilter(
  () => active.value.rows,
  computed(() => active.value.config),
)
const testingStatusOptions = ['检测录入中', '待校核', '待审核', '检测更改中', '待批准', '待签发', '待发放', '已发放']
const displayStatusOptions = computed(() =>
  moduleKey.value === 'testing' && pipelineAvailable
    ? testingStatusOptions
    : filter.statusOptions.value,
)
// 业务清单默认 10 条/页；分页常驻在卡片底部，避免长表格把翻页操作挤出视口。
const tablePageSize = 10
const tablePage = ref(1)
const pagedRows = computed(() =>
  filter.result.value.slice((tablePage.value - 1) * tablePageSize, tablePage.value * tablePageSize),
)
watch(() => filter.result.value.length, () => {
  if ((tablePage.value - 1) * tablePageSize >= filter.result.value.length) tablePage.value = 1
})
watch(() => filter.state.keyword, () => { tablePage.value = 1 })
const sharedPaging=createServerPage()
const sharedListPage=sharedPaging.state
const commissionPaging=createServerPage({pageSize:5,presentation:'commission'})
const samplePaging=createServerPage({presentation:'registration-sample',commissionIds:[]})
const commissionPage=commissionPaging.state,registrationSamplePage=samplePaging.state
const registrationPageSamples=ref<SampleRow[]>([])
const activeListKind=computed(()=>moduleKey.value==='sample'?(pageKey.value==='flow_query'?'flow':'disposal'):moduleKey.value==='testing'?'task':'cancel')
function setListQuery(q:Record<string,any>){if(moduleKey.value!=='entrust'||pageKey.value==='void_approval')sharedPaging.setQuery(q)}
async function exportListRows(){return fetchListExport(moduleKey.value!=='testing'?'/api/samples/query':'/api/reports/query',{...sharedListPage.query,view:moduleKey.value!=='testing'?'flow_query':'query',includeVoided:['flow_query','void_approval'].includes(pageKey.value)})}
function setRegistrationQuery(kind:string,q:Record<string,any>){if(moduleKey.value!=='entrust'||pageKey.value==='void_approval')return;const paging=kind==='c'?commissionPaging:samplePaging;paging.setQuery({...q,presentation:kind==='c'?'commission':'registration-sample'})}
async function exportRegistrationRows(kind:string){return fetchListExport(kind==='c'?'/api/entrust/query':'/api/samples/query',{...(kind==='c'?commissionPage.query:registrationSamplePage.query),projection:'list',view:'flow_query'})}
async function loadSamples() {
  if (!pipelineAvailable) return
  const sequence = ++sampleLoadSequence
  sampleListLoading.value = true
  sampleLoadError.value = ''
  try {
    const result=await fetchListPage<SampleRow>('/api/samples/query',{...sharedListPage.query,view:'flow_query',includeVoided:['flow_query','void_approval'].includes(pageKey.value),presentation:activeListKind.value});const rows=result.rows
    if (sequence !== sampleLoadSequence) return
    sharedListPage.total=result.total
    backendSamples.value = rows.map(row=>({...sampleFlowRow(row),workflowStatus:row.status}))
  } catch (error) {
    if (sequence !== sampleLoadSequence) return
    sampleLoadError.value = error instanceof Error ? error.message : '样品流转记录加载失败，请刷新重试'
  } finally {
    if (sequence === sampleLoadSequence) sampleListLoading.value = false
  }
}
const entrustSamplesLoading = ref(false)
const entrustSamplesError = ref('')
let entrustListSequence = 0
async function loadEntrust() {
  if (!pipelineAvailable) return
  if(pageKey.value==='void_approval'){await loadSamples();return}
  const sequence = ++entrustListSequence
  entrustPresentationLoading.value=true;entrustPresentationError.value=''
  entrustSamplesLoading.value=true;entrustSamplesError.value=''
  const samplesTask = fetchListPage<SampleRow>('/api/samples/query',{...registrationSamplePage.query,view:'flow_query'}).catch((error) => {
    if (sequence === entrustListSequence) entrustSamplesError.value = error instanceof Error ? error.message : '样品列表加载失败'
    return {rows:[] as SampleRow[],total:0}
  })
  const departmentsTask = fetchDepartments().catch(() => [])
  try {
    const result=await fetchListPage<EntrustOrder>('/api/entrust/query',{...commissionPage.query,projection:'list'});const rows=result.rows
    if (sequence !== entrustListSequence) return
    commissionPage.total=result.total
    const departmentDisplayNames = new Map<string, string>()
    void departmentsTask.then(departments => {
      if (sequence !== entrustListSequence) return
      departments.forEach(department => {
        departmentDisplayNames.set(department.name, department.fullName)
        departmentDisplayNames.set(department.fullName, department.fullName)
      })
      for (const parent of backendEntrust.value) parent.handlerDepartment = fullDepartmentName(parent.handlerDepartment)
    })
    const fullDepartmentName = (value: unknown) => {
      const name = String(value || '').trim()
      return departmentDisplayNames.get(name) || name
    }
    backendEntrust.value = rows.map((e) => ({
      id: e.id, no: e.entrustNo, client: e.client, projectName: e.projectName, contractNo: e.contractNo, erpContractNo: String(e.info?.erpContractNo || ''),
      projectType: e.projectType, amount: e.amount, status: e.status, owner: e.owner, date: e.date,
      department: e.department, sampleCount: e.sampleCount, info: e.info, dataStatus: e.dataStatus,
      erpProjectNo: e.erpProjectNo || e.contractNo,
      erpProjectType: e.erpProjectType || e.projectType,
      contractPartyA: e.contractPartyA || e.client,
      otherPartyA: e.otherPartyA || '',
      entrustDate: e.entrustDate || e.date,
      handler: e.handler || e.owner,
      handlerDepartment: fullDepartmentName(e.handlerDepartment || e.info?.handleDept || e.department),
      consignor: e.consignor || '',
      clientAddress: e.clientAddress || '',
      completionAccount: e.completionAccount || '',
      completionUserName: e.completionUserName || '',
      linkedSamples: [] as SampleRow[],
    }))
    entrustPresentationLoading.value = false
    const sampleResult = await samplesTask;const sampleList=sampleResult.rows
    if (sequence !== entrustListSequence) return
    registrationSamplePage.total=sampleResult.total;registrationPageSamples.value=sampleList
    const samplesByEntrust = new Map<string, SampleRow[]>()
    for (const sample of sampleList) {
      const key = sample.entrustNo || ''
      const group = samplesByEntrust.get(key) || []
      group.push(sample); samplesByEntrust.set(key, group)
    }
    for (const parent of backendEntrust.value) {
      parent.linkedSamples = samplesByEntrust.get(String(parent.no)) || []
    }
    const entrustMap = new Map(rows.map((row) => [row.entrustNo, row]))
    const queryRow = (entrust: EntrustOrder | undefined, sample: SampleRow | undefined) => ({
      ...sample,
      id: entrust?.id,
      no: sample?.entrustNo || entrust?.entrustNo,
      entrustNo: sample?.entrustNo || entrust?.entrustNo,
      contractNo: entrust?.contractNo,
      projectType: entrust?.projectType,
      erpProjectNo: sample?.erpProjectNo || entrust?.erpProjectNo || entrust?.contractNo,
      erpProjectType: sample?.erpProjectType || entrust?.erpProjectType || entrust?.projectType,
      erpContractNo: sample?.erpContractNo || String(entrust?.info?.erpContractNo || ''),
      handler: sample?.handler || entrust?.handler || entrust?.owner,
      client: sample?.client || entrust?.client,
      amount: sample?.amount || entrust?.amount,
      dataStatus: sample?.dataStatus || entrust?.dataStatus,
      consignor: sample?.consignor || entrust?.consignor,
      consignorPhone: sample?.consignorPhone || entrust?.info?.consignorPhone || '',
      clientAddress: sample?.clientAddress || entrust?.clientAddress,
    })
    backendEntrustQuery.value = rows.flatMap((entrust) => {
      const samples = samplesByEntrust.get(entrust.entrustNo) || []
      return samples.length ? samples.map((sample) => queryRow(entrust, sample)) : [queryRow(entrust, undefined)]
    })
    for (const sample of sampleList) {
      if (sample.entrustNo && entrustMap.has(sample.entrustNo)) continue
      backendEntrustQuery.value.push(queryRow(undefined, sample))
    }
  } catch (error) { if (sequence === entrustListSequence) entrustPresentationError.value=new AppError('NETWORK',error instanceof Error?error.message:'委托加载失败') } finally { if (sequence === entrustListSequence) { entrustPresentationLoading.value=false;entrustSamplesLoading.value=false } }
}
let testingListSequence=0
async function loadTesting() {
  if (!pipelineAvailable) return
  const sequence=++testingListSequence
  taskListBusy.value=true;taskListError.value=''
  try {
    const result=await fetchListPage('/api/reports/query',{...sharedListPage.query,view:'query',presentation:activeListKind.value});const rows=result.rows;if(sequence!==testingListSequence)return;sharedListPage.total=result.total
    // 样品出库领取后(已领取/已出库)进入检测的报告：录入 + 更改记录
    backendTesting.value = rows
      .filter((r) => r.sampleStatus === '已领取' || r.sampleStatus === '已出库')
      .map((row) => ({ ...row, queryStatus: testingStatusDisplay(String(row.status)) })) as unknown as Record<string, unknown>[]
  } catch (e) { if(sequence===testingListSequence)taskListError.value=e instanceof Error?e.message:'检测任务查询失败' } finally { if(sequence===testingListSequence)taskListBusy.value=false }
}
// 检测任务查询：状态标签 / 跳转录入或更改 / 查看全部信息
function testStatusType(s: string): 'success' | 'warning' | 'info' | 'danger' {
  return s === '退回待重传' ? 'danger' : (s === '检测更改中' ? 'warning' : 'info')
}
function testingStatusDisplay(status: string) {
  return status === '待打印' ? '待签发' : status
}
function jumpLabel(s: string) {
  if (s === '待校核') return '前往报告审核'
  return (s === '退回待重传' || s === '检测更改中') ? '进检测更改' : '进检测录入'
}
function jumpTesting(row: Record<string, unknown>) {
  const s = String(row.status)
  if (s === '待校核') {
    router.push({ path: '/inspection/report/review', query: { keyword: String(row.reportNo) } })
    return
  }
  const isChange = s === '退回待重传' || s === '检测更改中'
  router.push({ path: `/inspection/testing/${isChange ? 'data_change' : 'data_entry'}`, query: { keyword: String(row.reportNo) } })
}
const pageName = computed(() => String(route.meta.pageName ?? ''))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pages = computed(() => modules.find((module) => module.key === moduleKey.value)?.pages ?? [])
const profile = computed(() => pageProfiles[moduleKey.value as keyof typeof pageProfiles] ?? pageProfiles.default)

// 行详情：点行查看（取代末尾「查看」按钮），按状态展示相应信息
type Row = Record<string, unknown>
type TableSelectionRef<T> = { toggleRowSelection: (row: T, selected?: boolean) => void; clearSelection: () => void }
const workbenchTableRef = ref<TableSelectionRef<Row> | null>(null)
const detailOpen = ref(false)
const selectedRow = ref<Row | null>(null)
const selectedRows = ref<Row[]>([])

const SYSTEM_OVERRIDES_KEY = 'hn_system_runtime_overrides'
const runtimeEditOpen = ref(false)
const runtimeForm = ref({ value: '', reason: '' })

function today() {
  return new Date().toLocaleDateString('sv-SE')
}

function persistOverride(key: string, id: string, value: Row) {
  let map: Record<string, Row> = {}
  try { map = JSON.parse(localStorage.getItem(key) || '{}') as Record<string, Row> } catch { /* ignore corrupt local state */ }
  map[id] = value
  localStorage.setItem(key, JSON.stringify(map))
}

function restorePersistentWorkbenchState() {
  try {
    const systemOverrides = JSON.parse(localStorage.getItem(SYSTEM_OVERRIDES_KEY) || '{}') as Record<string, Row>
    systemRows.forEach((row) => Object.assign(row, systemOverrides[String(row.key)] ?? {}))
  } catch { /* ignore corrupt local state */ }
}
restorePersistentWorkbenchState()

function openRuntimeEdit() {
  if (!selectedRow.value) return ElMessage.warning('请先选择一条配置')
  runtimeForm.value = { value: String(selectedRow.value.value ?? ''), reason: '' }
  runtimeEditOpen.value = true
}

function saveRuntimeEdit() {
  const row = selectedRow.value
  const value = runtimeForm.value.value.trim()
  const reason = runtimeForm.value.reason.trim()
  if (!row) return
  if (!value) return ElMessage.warning('配置值不能为空')
  if (!reason) return ElMessage.warning('请填写修改原因')
  if (value === String(row.value ?? '')) return ElMessage.warning('配置值没有变化')
  Object.assign(row, { value, changeReason: reason, owner: session.userName, updatedAt: today() })
  persistOverride(SYSTEM_OVERRIDES_KEY, String(row.key), row)
  runtimeEditOpen.value = false
  ElMessage.success(`配置“${String(row.key)}”已保存，刷新后仍会保留`)
}
// 切换模块/页面时清空筛选条件；进入样品/委托/检测模块时拉取真实数据
// 注意：必须放在 workbenchTableRef/selectedRow/selectedRows 声明之后（immediate 触发时引用它们，先声明后使用）
watch(() => [route.path, route.query.action], () => {
  filter.reset()
  tablePage.value = 1
  selectedRow.value = null
  selectedRows.value = []
  workbenchTableRef.value?.clearSelection()

  if (moduleKey.value === 'entrust' && pageKey.value === 'registration' && route.query.action === 'create') {
    openWizard('entrust')
    const query = { ...route.query }
    delete query.action
    void router.replace({ path: route.path, query })
  }
}, { immediate: true })
const canCompleteSelectedEntrust = computed(() =>
  moduleKey.value === 'entrust'
  && !!selectedRow.value
  && selectedRow.value.status === '委托中'
  && (
    session.can('entrust.registration.view')
    || session.canAction('entrust.register.complete')
  ),
)
const canModifySelectedEntrust = computed(() =>
  moduleKey.value === 'entrust'
  && !!selectedRow.value
  && selectedRow.value.status !== '委托完成',
)
const canUncompleteSelectedEntrust = computed(() =>
  moduleKey.value === 'entrust'
  && !!selectedRow.value
  && selectedRow.value.status === '委托完成'
  && (selectedRow.value.completionAccount === session.account || session.account === 'admin' || (session.fullPlatformAuthority || session.roleKey === 'admin'))
  && session.can('entrust.registration.view'),
)
const canAddSampleForSelectedEntrust = computed(() =>
  moduleKey.value === 'entrust' && !!selectedRow.value && selectedRow.value.status === '委托完成',
)
async function uncompleteSelectedEntrust() {
  const row = selectedRow.value
  if (!row) return
  try {
    await ElMessageBox.confirm(`确认撤销委托单 ${row.no} 的登记完成？下游已有样品单时将被拦截。`, '撤销完成', { type: 'warning' })
  } catch { return }
  try {
    await uncompleteEntrust(row.id as number)
    ElMessage.success('已撤销完成，委托单回到「委托登记中」')
    await loadEntrust()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}
async function returnStockSelected() {
  const row = selectedRow.value
  if (!row) return
  try {
    await ElMessageBox.confirm(`样品 ${row.sampleNo} 撤销领取并退回库内待重新领取（尚未录入检测数据）？`, '撤销领取', { type: 'warning' })
  } catch { return }
  try {
    await submitSampleReturnStock(String(row.reportNo))
    ElMessage.success('已撤销领取，样品回到库内待重新领取')
    await loadTesting()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}
async function disposeSelected() {
  const row = selectedRow.value
  if (!row) return
  try {
    await ElMessageBox.confirm(`处置样品 ${row.sampleNo}？处置为终态、不可恢复。`, '样品处置', { type: 'warning' })
  } catch { return }
  try {
    await submitSampleDispose(String(row.reportNo))
    ElMessage.success('样品已处置')
    await loadTesting()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}
const selectedTestingJumpLabel = computed(() => selectedRow.value ? jumpLabel(String(selectedRow.value.status ?? '')) : '进入录入')
const detailFieldMap: Record<string, [string, string][]> = {
  entrust: [['委托编号', 'no'], ['委托单位', 'client'], ['工程名称', 'projectName'], ['外部ERP合同编号', 'contractNo'], ['项目类型', 'projectType'], ['金额', 'amount'], ['经办部门', 'department'], ['样品数', 'sampleCount'], ['状态', 'status'], ['责任人', 'owner'], ['登记日期', 'date']],
  testing: [['任务编号', 'taskNo'], ['样品编号', 'sampleNo'], ['检测项目', 'project'], ['执行标准', 'standard'], ['仪器设备', 'instrument'], ['采集状态', 'collectStatus'], ['结果状态', 'result'], ['主检人', 'owner']],
  finance: [['费用单号', 'billNo'], ['委托编号', 'entrustNo'], ['委托单位', 'client'], ['应收金额', 'amount'], ['实收金额', 'paid'], ['发票状态', 'invoice'], ['外部ERP同步', 'erp'], ['当前状态', 'status']],
  quality: [['编号', 'code'], ['名称', 'name'], ['类别', 'category'], ['所属科室', 'department'], ['状态', 'status'], ['计划/事项', 'plan'], ['到期日期', 'dueDate']],
  system: [['配置项', 'key'], ['作用范围', 'scope'], ['当前配置', 'value'], ['维护角色', 'owner'], ['更新时间', 'updatedAt'], ['最近修改原因', 'changeReason']],
}
const detailFields = computed(() => detailFieldMap[moduleKey.value as string] ?? [])
const detailTitle = computed(() => `${profile.value.title} · 详情`)
function display(prop: string) {
  const v = selectedRow.value?.[prop]
  return v === undefined || v === null || v === '' ? '—' : String(v)
}
// 按状态给出相应信息（是否委托完成 / 检测数据录入等）
const STATUS_NOTE: Record<string, string> = {
  已登记: '委托单已登记完成。可在「样品入库」添加样品并入库，随后进入合同评审。',
  待合同评审: '待合同评审，评审通过后进入样品入库。',
  待样品入库: '合同评审已通过，下一步办理样品入库。',
  待样品领取: '样品已入库，下一步办理出库领取。',
  检测录入中: '样品已领取，正在录入检测数据。',
  待入库: '合同评审已通过，样品待入库。',
  已入库: '样品已入库，待出库领取后录入检测数据。',
  已领取: '样品已领取，可进行检测数据录入。',
  待校核: '历史数据：检测数据录入已完成，待报告审核。',
  待审核: '检测数据录入已完成，待报告审核。',
  待批准: '已审核，待批准。',
  待打印: '已批准，待电子签发。',
  待发放: '待发放。',
  已发放: '报告已发放。',
  委托更改中: '委托更改中，修改后提交：批准前重走合同评审，批准后进入检测更改。',
  检测更改中: '批准后更改：委托更改已完成，正在检测更改，完成后回到待审核。',
}
const statusVal = computed(() => String(selectedRow.value?.status ?? selectedRow.value?.collectStatus ?? ''))
const statusNote = computed(() => STATUS_NOTE[statusVal.value] || `当前状态：${statusVal.value || '—'}`)
const statusType = computed(() => (['委托更改中', '退回待重传'].includes(statusVal.value) ? 'warning' : 'info'))
function selectRow(row: Row) {
  selectedRow.value = row
}
function onWorkbenchSelectionChange(selection: Row[]) {
  selectedRows.value = selection
  selectedRow.value = selection[selection.length - 1] ?? null
}
function toggleWorkbenchRow(row: Row) {
  workbenchTableRef.value?.toggleRowSelection(row)
}
function linkedSamples(row: Row) {
  return Array.isArray(row.linkedSamples) ? row.linkedSamples as Row[] : []
}

// 点击「查看」→ 统一只读详情弹窗，展示该对象的全部信息
function viewEntrust(row: Row) {
  editEntrust(row, true)
}
function viewSample(row: Row) {
  editSample(row, true)
}
function viewSelected() {
  if (!selectedRow.value) return ElMessage.warning('请先在列表中选择一条记录')
  if (isEntrustQuery.value) {
    return selectedRow.value.reportNo ? viewSample(selectedRow.value) : viewEntrust(selectedRow.value)
  }
  if (moduleKey.value === 'entrust') return viewEntrust(selectedRow.value)
  if (moduleKey.value === 'testing') return viewSample(selectedRow.value)
  if (moduleKey.value === 'sample') return viewSample(selectedRow.value)
  detailOpen.value = true
}
const queryAttachmentOpen = ref(false)
function openQueryAttachments() {
  if (!selectedRow.value?.reportNo) return ElMessage.warning('请选择已关联样品的委托记录')
  queryAttachmentOpen.value = true
}
async function exportSelectedEntrustPdf() {
  const row = selectedRow.value
  if (!row?.id) return ElMessage.warning('当前记录未关联有效委托单')
  const kind: BusinessFormTemplateKind = String(row.erpProjectType || row.projectType || '').includes('工程') ? 'engineering' : 'product'
  try {
    const result = await fetchEntrustPrint(Number(row.id), 'pdf', kind)
    if (result.type !== 'pdf') return
    const link = document.createElement('a')
    link.href = result.url
    link.download = `${String(row.entrustNo || row.no || '委托单')}-${kind === 'engineering' ? '工程类' : '产品类'}委托单.pdf`
    link.click()
    setTimeout(() => URL.revokeObjectURL(result.url), 1000)
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : 'PDF 导出失败') }
}
function editSelectedEntrust() {
  if (!selectedRow.value) return ElMessage.warning('请先选择委托单')
  if (selectedRow.value.status === '委托完成') return ElMessage.warning('委托单已完成，请先撤销完成后再修改')
  editEntrust(selectedRow.value)
}
function addSampleForSelected() {
  if (!selectedRow.value) return ElMessage.warning('请先选择委托单')
  addSampleFor(selectedRow.value)
}
function completeSelectedEntrust() {
  if (!selectedRow.value) return ElMessage.warning('请先选择委托单')
  return onCompleteEntrust(selectedRow.value)
}
function jumpSelectedTesting() {
  if (!selectedRow.value) return ElMessage.warning('请先选择检测任务')
  jumpTesting(selectedRow.value)
}
const exportColumns: Record<string, [string, string][]> = {
  entrust: [['外部ERP项目编号', 'erpProjectNo'], ['委托编号', 'no'], ['合同甲方', 'contractPartyA'], ['其他甲方（付款方）', 'otherPartyA'], ['委托时间', 'entrustDate'], ['外部ERP项目类型', 'erpProjectType'], ['委托经办人', 'handler'], ['委托经办部门', 'handlerDepartment'], ['委托金额', 'amount'], ['委托状态', 'dataStatus'], ['委托人', 'consignor'], ['委托单位', 'client'], ['委托单位地址', 'clientAddress'], ['样品数', 'sampleCount']],
  sample: [['样品编号', 'sampleNo'], ['报告编号', 'reportNo'], ['检测项目', 'project'], ['委托单位', 'client'], ['工程名称', 'projectName'], ['当前状态', 'status'], ['标记', 'tag'], ['责任人', 'owner'], ['委托日期', 'date']],
  testing: [['样品编号', 'sampleNo'], ['报告编号', 'reportNo'], ['样品/工程名称', 'project'], ['委托单位', 'client'], ['当前数据状态', 'status'], ['样品状态', 'sampleStatus'], ['主检/责任人', 'owner'], ['报告中心/部门', 'department']],
  finance: [['费用单号', 'billNo'], ['委托编号', 'entrustNo'], ['委托单位', 'client'], ['应收金额', 'amount'], ['实收金额', 'paid'], ['发票状态', 'invoice'], ['外部ERP同步', 'erp'], ['当前状态', 'status']],
  quality: [['编号', 'code'], ['名称', 'name'], ['类别', 'category'], ['所属科室', 'department'], ['状态', 'status'], ['计划/事项', 'plan'], ['到期日期', 'dueDate']],
  system: [['配置项', 'key'], ['作用范围', 'scope'], ['当前配置', 'value'], ['维护角色', 'owner'], ['更新时间', 'updatedAt']],
}
async function exportCurrentList() {
  const rows = filter.result.value
  const columns: XlsxColumn[] = isEntrustQuery.value
    ? entrustQueryColumns.map((column) => ({
        label: column.label,
        key: column.key,
        width: column.minWidth ? Math.round(column.minWidth / 9) : Math.round((column.width || 120) / 9),
      }))
    : (exportColumns[moduleKey.value as string] ?? Object.keys(rows[0] ?? {}).map((key) => [key, key] as [string, string]))
        .map(([label, key]) => ({ label, key, width: 18 }))
  if (moduleKey.value === 'sample' && pageKey.value === 'flow_query') {
    columns.push(...[
      ['数据状态', 'dataStatus'], ['入库人', 'inboundPerson'], ['入库时间', 'inboundTime'],
      ['出库领取人', 'pickupPerson'], ['出库领取时间', 'pickupTime'], ['样品处置', 'sampleDisposition'],
    ].map(([label, key]) => ({ label, key, width: 20 })))
  }
  try {
    await exportRowsXlsx(`${pageName.value || '列表'}-${today()}`, columns, rows as Row[])
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '导出失败') }
}

// BEGIN TEMPLATE REGISTRATION ADAPTER
const listPrintSample=ref('')
async function printListSample(r:any){selectedRow.value=r;listPrintSample.value=r.reportNo;printId.value=null;printTemplateKind.value=String(r.erpProjectType||r.testCategory||'').includes('工程')?'engineering':'product';clearPrintPreview();printOpen.value=true;await reloadPrint()}
const StandardWorkspace=defineComponent({inheritAttrs:false,setup(_,{attrs,slots}){return()=>(moduleKey.value==='entrust'&&['registration','query','void_approval'].includes(pageKey.value)||moduleKey.value==='sample'&&['disposal','flow_query'].includes(pageKey.value)||moduleKey.value==='testing'&&pageKey.value==='task_query')?slots.default?.():h(ModuleWorkspace as any,attrs,slots)}})
const registrationPresentation=useRegistrationPresentation(reactive({serverPaging:pipelineAvailable,commissionPage,registrationSamplePage,registrationPageSamples,setRegistrationQuery,exportRegistrationRows,mode:computed(()=>pageKey.value==='query'?'query':'registration'),entrustPresentationLoading,entrustPresentationError,entrustSamplesLoading,entrustSamplesError,backendEntrust,selectedRow,selectedRows,session,pageName,route,openWizard,viewEntrust,editEntrust,viewSample,editSample,addSampleFor,completeSelectedEntrust,uncompleteSelectedEntrust,canCompleteSelectedEntrust,canUncompleteSelectedEntrust,loadEntrust,printSample:printListSample,openSelectedEntrustPrint,openQueryAttachments,exportCurrentList,onWorkbenchSelectionChange}))
const listController=reactive({serverPaging:pipelineAvailable,activeListKind,listPage:sharedListPage,setListQuery,exportListRows,identity:computed(()=>route.path+session.account),title:pageName,session,rows:computed(()=>moduleKey.value==='sample'?backendSamples.value:moduleKey.value==='testing'?backendTesting.value:backendSamples.value),loading:computed(()=>moduleKey.value!=='testing'?sampleListLoading.value:moduleKey.value==='testing'?taskListBusy.value:entrustPresentationLoading.value),error:computed(()=>moduleKey.value!=='testing'?sampleLoadError.value:moduleKey.value==='testing'?taskListError.value:entrustPresentationError.value),load:()=>moduleKey.value==='sample'?loadSamples():moduleKey.value==='testing'?loadTesting():loadEntrust(),view:viewSample,enter:jumpTesting,restock:async(r:any)=>{selectedRow.value=r;await returnStockSelected()},confirmVoid:async(r:any,run:any)=>{try{await ElMessageBox.confirm('确认作废样品 '+r.sampleNo+'？','作废样品',{type:'warning'});await run()}catch(e){if(e instanceof Error)ElMessage.error(e.message)}}})
const flowList=useListPresentation(listController,'flow'),disposalList=useListPresentation(listController,'disposal'),taskList=useListPresentation(listController,'task'),cancelList=useListPresentation(listController,'cancel')
const specialListComponent=computed(()=>moduleKey.value==='sample'?(pageKey.value==='flow_query'?FlowList:pageKey.value==='disposal'?StorageList:null):moduleKey.value==='testing'&&pageKey.value==='task_query'?TaskList:moduleKey.value==='entrust'&&pageKey.value==='void_approval'?CancellationList:null)
const specialListContext=computed(()=>moduleKey.value==='sample'?(pageKey.value==='flow_query'?flowList:disposalList):moduleKey.value==='testing'?taskList:cancelList)
// END TEMPLATE REGISTRATION ADAPTER
watch(()=>JSON.stringify([route.path,session.account,moduleKey.value==='entrust'&&pageKey.value!=='void_approval'?[commissionPage.query,registrationSamplePage.query]:sharedListPage.query]),()=>{if(moduleKey.value==='entrust')void loadEntrust();else if(moduleKey.value==='sample')void loadSamples();else if(moduleKey.value==='testing')void loadTesting()},{immediate:true})
</script>


