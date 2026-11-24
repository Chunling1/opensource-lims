<template>
  <PipelineWizard
    v-model="wizardOpen"
    mode="samples"
    page-view
    sample-list-view="register"
    detail-view="sample_register"
    :department="session.dataScope.department"
    :preset-entrust-no="presetEntrust || presetFromRow"
    :change-report-no="editReportNo"
    :in-place="true"
    :read-only="wizardReadonly"
    @created="onReportCreated"
    @updated="onEdited"
  />

  <div v-show="!wizardOpen"><RegistrationPresentation :model="sampleListPresentation" /></div>

  <AttachmentManagerDialog v-model="attachmentOpen" :report-no="selectedSample?.reportNo || ''" view="sample_register" :title="`附件管理 · ${selectedSample?.sampleNo || ''}`" />

  <el-dialog v-model="printOpen" :title="`委托单预览${selectedSample ? ` · ${selectedSample.sampleNo}` : ''}`" width="1200px" top="5vh"  @closed="clearPrintPreview">
    <div >
      <div >
        <div >
          <span>委托单模板</span>
          <el-segmented v-model="printTemplateKind" :options="BUSINESS_FORM_TEMPLATE_OPTIONS" size="small" :disabled="printLoading || printDownloadLoading" @change="onPrintTemplateChange" />
        </div>
        <div >
          <span>导出页码</span>
          <el-checkbox-group v-model="printSelectedPages" size="small" :disabled="printLoading || printDownloadLoading">
            <el-checkbox-button v-for="page in printPageOptions" :key="page" :value="page">第 {{ page }} 页</el-checkbox-button>
          </el-checkbox-group>
        </div>
      </div>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <el-tag v-if="printEngine" size="small" type="success">WPS PDF</el-tag>
        <el-button size="small" :loading="printLoading" :disabled="printDownloadLoading" @click="reloadSamplePrint">刷新预览</el-button>
        <el-button size="small" type="primary" :loading="printDownloadLoading" :disabled="!printUrl || !printSelectedPages.length" @click="downloadSamplePdf">下载委托单 PDF</el-button>
        <el-button size="small" :disabled="!selectedSample || printDownloadLoading" @click="downloadSampleDoc">导出 Word</el-button>
      </div>
    </div>
    <DataEntryPreview v-if="printUrl" :url="printUrl" title="委托单预览" name="" type="application/pdf" embedded compact persistent hide-download />
    <el-empty v-else :description="printLoading ? '生成中…' : '暂无预览'" />
  </el-dialog>

</template>

<script setup lang="ts">
// BEGIN TEMPLATE FORM_VISIBILITY IMPORTS
import RegistrationPresentation from "../../platformUi/commissions/RegistrationPresentation.vue"
import {createServerPage,fetchListPage,fetchListExport} from '../../platformUi/lists/serverPage'
import {useRegistrationPresentation} from "../../platformUi/commissions/registrationPresentation"
import {reactive} from "vue"
// END TEMPLATE FORM_VISIBILITY IMPORTS

import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import { shallowRef, computed, onUnmounted, ref, watch, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { modules } from '@/data/modules'
import { ElMessage, ElMessageBox } from 'element-plus'
import { BUSINESS_FORM_TEMPLATE_OPTIONS, PIPELINE_AVAILABLE, fetchEntrustList, fetchSamplePrint, fetchSamples, sampleRegAction, voidSample, type BusinessFormTemplateKind, type EntrustOrder, type SampleRow } from '@/services/pipeline'
import { useSessionStore } from '@/stores/session'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import PipelineWizard from '@/components/PipelineWizard.vue'
import AttachmentManagerDialog from '@/components/AttachmentManagerDialog.vue'
import FlatDatePicker from '@/components/FlatDatePicker.vue'
import { exportRowsXlsx, type XlsxColumn } from '@/services/xlsxExport'
import { sampleRegisterDemoRows } from '@/data/workflowDemo'

const route = useRoute()
const session = useSessionStore()
const available = PIPELINE_AVAILABLE
const wizardOpen = ref(false)
const editReportNo = ref('')
const wizardReadonly = ref(false)
const keyword = ref('')
const statusFilter = ref('')
const dateRange = ref<[string, string] | null>(null)
const pageSize = ref(10)
const tablePage = ref(1)
const pageName = computed(() => String(route.meta.pageName ?? '样品登记'))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pageKey = computed(() => String(route.meta.pageKey ?? 'sample_register'))
const pages = computed(() => modules.find((m) => m.key === 'entrust')?.pages ?? [])

// 从「委托登记」跳转而来：自动打开新增样品并预选该委托单
const presetEntrust = computed(() => (typeof route.query.entrust === 'string' ? route.query.entrust : ''))
watchEffect(() => {
  if (route.query.addSample === '1') { wizardReadonly.value = false; editReportNo.value = ''; wizardOpen.value = true }
})

const entrusts = shallowRef<EntrustOrder[]>([])
const samples = shallowRef<SampleRow[]>([])
const sampleListLoading = ref(false), sampleListError = ref('')
const samplePaging=createServerPage({presentation:'registration-sample'})
const registrationSamplePage=samplePaging.state,commissionPage=reactive({total:0})
function setRegistrationQuery(kind:string,q:Record<string,any>){if(kind==='s')samplePaging.setQuery({...q,presentation:'registration-sample'})}
async function exportRegistrationRows(){return fetchListExport('/api/samples/query',{...registrationSamplePage.query,view:'register'})}
let loadEpoch = 0
onUnmounted(() => { loadEpoch++ })
async function load() {
  if (!available) {
    samples.value = sampleRegisterDemoRows
    return
  }
  sampleListLoading.value = true
  sampleListError.value = ''
  const epoch = ++loadEpoch
  try {
    const result=await fetchListPage<SampleRow>('/api/samples/query',{...registrationSamplePage.query,view:'register'})
    if (epoch === loadEpoch){samples.value=result.rows;registrationSamplePage.total=result.total}
  } catch (error) { if (epoch === loadEpoch) sampleListError.value = error instanceof Error ? error.message : String(error) }
  finally { if (epoch === loadEpoch) sampleListLoading.value = false }
}


interface ListColumn { key: string; label: string; width?: number; minWidth?: number }
const sampleColumns: ListColumn[] = [
  { key: 'entrustNo', label: '委托编号', minWidth: 140 },
  { key: 'sampleNo', label: '样品编号', minWidth: 140 },
  { key: 'reportNo', label: '报告编号', minWidth: 160 },
  { key: 'erpProjectNo', label: '外部ERP项目编号', minWidth: 150 },
  { key: 'erpProjectType', label: '外部ERP项目类型', minWidth: 130 },
  { key: 'erpContractNo', label: '外部ERP合同编号', minWidth: 150 },
  { key: 'handler', label: '委托经办人', width: 110 },
  { key: 'registrarDepartment', label: '样品登记部门', minWidth: 140 },
  { key: 'registrar', label: '样品登记人', width: 110 },
  { key: 'sampleOrProjectName', label: '样品/工程名称', minWidth: 180 },
  { key: 'testItems', label: '检测项目', minWidth: 170 },
  { key: 'testDepartment', label: '检测部门', minWidth: 150 },
  { key: 'dataStatus', label: '数据状态', width: 120 },
  { key: 'schemeDisplay', label: '检测方案（编号 · 名称）', minWidth: 220 },
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
const filteredSamples = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  const [start, end] = dateRange.value ?? ['', '']
  return samples.value.filter((row) => {
    const textMatched = !k || JSON.stringify(row).toLowerCase().includes(k)
    const dates = [row.sampleRegisteredAt, row.sendDate, row.samplingTime].filter(Boolean) as string[]
    const dateMatched = (!start && !end) || dates.some((value) => (!start || value >= start) && (!end || value <= end))
    const statusMatched = !statusFilter.value || String(row.dataStatus || row.status || '') === statusFilter.value
    return textMatched && dateMatched && statusMatched
  })
})
const statusOptions = computed(() => Array.from(new Set(
  samples.value.map((row) => String(row.dataStatus || row.status || '')).filter(Boolean),
)))
const pagedSamples = computed(() => filteredSamples.value.slice((tablePage.value - 1) * pageSize.value, tablePage.value * pageSize.value))
watch([filteredSamples, keyword, statusFilter, dateRange, pageSize], () => { tablePage.value = 1 })

const selectedSamples = ref<SampleRow[]>([])
const selectedSample = computed(() => selectedSamples.value[selectedSamples.value.length - 1] ?? null)
const canEditSelected = computed(() => (
  selectedSamples.value.length === 1
  && (session.canCorrectBusinessData || selectedSample.value?.sampleRegState === '登记中')
))
const canCompleteSelected = computed(() => available && (
  session.can('entrust.sample_register.view')
  || session.canAction('sample.register.complete')
) && selectedSamples.value.length > 0 && selectedSamples.value.every((row) => row.sampleRegState === '登记中'))
const canUncompleteSelected = computed(() => available && (
  session.can('entrust.sample_register.view')
  && selectedSamples.value.length > 0
  && selectedSamples.value.every((row) => (
    typeof row.canRecallSampleRegistration === 'boolean'
      ? row.canRecallSampleRegistration
      : (
        row.status === '待合同评审'
        && row.sampleRegState === '登记完成'
      )
  ))
))
function onSampleSelectionChange(rows: SampleRow[]) {
  selectedSamples.value = rows
}
type TableRef = { toggleRowSelection: (row: SampleRow, selected?: boolean) => void }
const tableRef = ref<TableRef | null>(null)
function toggleSampleRow(row: SampleRow) { tableRef.value?.toggleRowSelection(row) }

const presetFromRow = computed(() => {
  return selectedSample.value?.entrustNo || ''
})
function openAdd() { wizardReadonly.value = false; editReportNo.value = ''; wizardOpen.value = true }
function viewSample(s: SampleRow) { editSample(s, true) }
function editSample(s: SampleRow, readOnly = false) {
  wizardReadonly.value = readOnly
  editReportNo.value = s.reportNo
  wizardOpen.value = true
}
function viewSelectedSample() { if (selectedSample.value) viewSample(selectedSample.value) }
function editSelectedSample() { if (selectedSample.value) editSample(selectedSample.value) }
async function completeSelected() {
  try {
    await Promise.all(selectedSamples.value.map((row) => sampleRegAction(row.reportNo, 'complete')))
    ElMessage.success(`已完成 ${selectedSamples.value.length} 条样品登记`)
    await load()
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '操作失败') }
}
async function uncompleteSelected() {
  try {
    await Promise.all(selectedSamples.value.map((row) => sampleRegAction(row.reportNo, 'uncomplete')))
    ElMessage.success(`已撤销 ${selectedSamples.value.length} 条样品登记完成`)
    await load()
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '操作失败') }
}
const attachmentOpen = ref(false)
function openAttachmentManager() { attachmentOpen.value = true }
const printOpen = ref(false)
const printLoading = ref(false)
const printDownloadLoading = ref(false)
const printUrl = ref('')
const printTemplateKind = ref<BusinessFormTemplateKind>('product')
const printSourceHash = ref('')
const printEngine = ref('')
const printExpectedPages = ref(0)
const printSelectedPages = ref<number[]>([])
const printPageOptions = computed(() => Array.from({ length: printExpectedPages.value }, (_, index) => index + 1))
function clearPrintPreview() {
  if (printUrl.value) URL.revokeObjectURL(printUrl.value)
  printUrl.value = ''
  printSourceHash.value = ''
  printEngine.value = ''
  printExpectedPages.value = 0
  printSelectedPages.value = []
}
async function openSamplePrint() {
  if (!selectedSample.value) return ElMessage.warning('请先选择样品单')
  const entrust = entrusts.value.find((item) => item.entrustNo === selectedSample.value?.entrustNo)
  const projectType = `${entrust?.projectType ?? ''} ${entrust?.erpProjectType ?? ''}`
  printTemplateKind.value = projectType.includes('工程') ? 'engineering' : 'product'
  clearPrintPreview()
  printOpen.value = true
  await reloadSamplePrint()
}
async function onPrintTemplateChange() {
  clearPrintPreview()
  await reloadSamplePrint()
}
async function reloadSamplePrint() {
  if (!selectedSample.value) return
  printLoading.value = true
  try {
    const result = await fetchSamplePrint(selectedSample.value.reportNo, 'pdf', printTemplateKind.value)
    if (result.type === 'pdf') {
      clearPrintPreview()
      printUrl.value = result.url
      printSourceHash.value = result.sourceHash
      printEngine.value = result.engine
      printExpectedPages.value = result.expectedPages
      printSelectedPages.value = printPageOptions.value.slice()
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '样品单生成失败')
  } finally {
    printLoading.value = false
  }
}
async function downloadSamplePdf() {
  const row = selectedSample.value
  if (!row || !printUrl.value || !printSelectedPages.value.length) return
  const pages = printSelectedPages.value.slice().sort((left, right) => left - right)
  printDownloadLoading.value = true
  try {
    const sampleNo = row.sampleNo || row.reportNo
    const isFullDocument = pages.length === printExpectedPages.value
      && pages.every((page, index) => page === index + 1)
    // 完整委托单已经由当前预览生成并校验过，直接下载该 Blob。
    // 避免点击下载时再次请求 WPS 转换，导致工程类模板长时间无响应。
    if (isFullDocument) {
      const link = document.createElement('a')
      link.href = printUrl.value
      link.download = `${sampleNo}-WT.pdf`
      link.click()
      return
    }
    const result = await fetchSamplePrint(row.reportNo, 'pdf', printTemplateKind.value, pages)
    if (result.type !== 'pdf') return
    if (printSourceHash.value && result.sourceHash && result.sourceHash !== printSourceHash.value) {
      URL.revokeObjectURL(result.url)
      ElMessage.warning('业务数据已变化，已重新生成预览，请确认后再导出')
      await reloadSamplePrint()
      return
    }
    const pageSuffix = pages.length === printExpectedPages.value ? '' : `-第${pages.join('-')}页`
    const link = document.createElement('a')
    link.href = result.url
    link.download = `${sampleNo}-WT${pageSuffix}.pdf`
    link.click()
    setTimeout(() => URL.revokeObjectURL(result.url), 1000)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '委托单 PDF 导出失败')
  } finally {
    printDownloadLoading.value = false
  }
}
async function downloadSampleDoc() {
  if (!selectedSample.value) return
  try {
    const sampleNo = selectedSample.value.sampleNo || selectedSample.value.reportNo
    const result = await fetchSamplePrint(selectedSample.value.reportNo, 'docx', printTemplateKind.value)
    if (result.type === 'docx') {
      if (printSourceHash.value && result.sourceHash && result.sourceHash !== printSourceHash.value) {
        URL.revokeObjectURL(result.url)
        ElMessage.warning('业务数据已变化，已重新生成预览，请确认后再导出')
        await reloadSamplePrint()
        return
      }
      const link = document.createElement('a')
      link.href = result.url
      link.download = `${sampleNo}-WT.docx`
      link.click()
      setTimeout(() => URL.revokeObjectURL(result.url), 1000)
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '样品单下载失败')
  }
}
onUnmounted(() => {
  clearPrintPreview()
})
function onEdited() { load() }
async function voidSelectedSample() {
  if (!selectedSamples.value.length) return
  try {
    const labels = selectedSamples.value.map((row) => row.sampleNo || row.reportNo).join('、')
    await ElMessageBox.confirm(`确认作废已选 ${selectedSamples.value.length} 条样品单？\n${labels}`, '作废确认', { type: 'warning' })
    await ElMessageBox.prompt('作废后不进入后续流程。请输入“作废”确认。', '再次确认', {
      inputPattern: /^作废$/,
      inputErrorMessage: '请输入“作废”',
      confirmButtonText: '作废',
    })
    await Promise.all(selectedSamples.value.map((row) => voidSample(row.reportNo)))
    ElMessage.success(`已作废 ${selectedSamples.value.length} 条样品单`)
    await load()
  } catch (error) {
    if (error instanceof Error) ElMessage.error(error.message)
  }
}
async function exportSampleList() {
  const columns: XlsxColumn[] = sampleColumns.map((column) => ({
    label: column.label,
    key: column.key,
    width: column.minWidth ? Math.round(column.minWidth / 9) : Math.round((column.width || 120) / 9),
  }))
  try {
    await exportRowsXlsx(`样品登记列表-${new Date().toISOString().slice(0, 10)}`, columns, filteredSamples.value as unknown as Record<string, unknown>[])
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '导出失败') }
}
function onReportCreated() { void load() }

// BEGIN TEMPLATE FORM_VISIBILITY ADAPTER
const sampleListParents=computed(()=>{
  const groups = new Map<string, SampleRow[]>()
  for (const sample of samples.value) {
    const key = sample.entrustNo || ''
    const group = groups.get(key) || []
    group.push(sample); groups.set(key, group)
  }
  const parents = entrusts.value.map(p=>({...p,no:p.entrustNo,linkedSamples:groups.get(p.entrustNo)||[]}))
  const known = new Set(entrusts.value.map(p=>p.entrustNo))
  // The sample API already supplies its commission date and business fields.
  // Keep those rows visible while parent choices arrive, or when a parent is
  // outside the account's independently scoped commission list.
  const pending = [...groups].filter(([key])=>!known.has(key)).map(([key,linkedSamples])=>({
    id:`sample-parent:${key}`,no:key,entrustNo:key,linkedSamples,
    entrustDate:linkedSamples[0]?.entrustDate||'',
  }))
  return [...parents,...pending]
})
const sampleListPresentation=useRegistrationPresentation(reactive({serverPaging:available,commissionPage,registrationSamplePage,registrationPageSamples:samples,setRegistrationQuery,exportRegistrationRows,samplesOnly:true,pageName,route,session,
 backendEntrust:sampleListParents,entrustPresentationLoading:sampleListLoading,entrustPresentationError:sampleListError,
 loadEntrust:load,onWorkbenchSelectionChange:()=>{},openAdd,editSample,viewSample,openQueryAttachments:openAttachmentManager,
 get selectedRow(){return selectedSample.value},set selectedRow(r:any){selectedSamples.value=r?[r]:[]},
 printSample:(r:SampleRow)=>{selectedSamples.value=[r];openSamplePrint()},
}))
// END TEMPLATE FORM_VISIBILITY ADAPTER
watch(()=>JSON.stringify([registrationSamplePage.query,session.dataScope]),()=>void load(),{immediate:true})
</script>


