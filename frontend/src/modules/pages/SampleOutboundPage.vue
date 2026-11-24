<template>
  <PipelineWizard
    v-model="editOpen"
    mode="samples"
    sample-list-view="outbound"
    detail-view="sample_outbound"
    :department="session.dataScope.department"
    :change-report-no="editReportNo"
    :read-only="wizardReadonly"
  />

  <StorageList :context="stockList" />

  <OutboundPickupDialog
    :open="formOpen" :row="selected" :form="form" :previous-date="selectedInboundDate" :can-sign="canSign"
    :allow-sign="session.canAction('sample.out_warehouse.sign')" :allow-return="session.canAction('sample.out_warehouse.return')"
    @close="formOpen = false" @submit="submit"
  />

</template>

<script setup lang="ts">
// BEGIN TEMPLATE STOCK IMPORTS
import StorageList from '../../platformUi/lists/StorageList.vue'
import {createServerPage,fetchListPage,fetchListExport} from '../../platformUi/lists/serverPage'
import {useListPresentation} from '../../platformUi/lists/listPresentation'
// END TEMPLATE STOCK IMPORTS

import { computed, reactive, ref, watch, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modules } from '@/data/modules'
import { PIPELINE_AVAILABLE, fetchSamples, submitSamplePickup, submitSampleReturnStock, type SampleRow } from '@/services/pipeline'
import { useSessionStore } from '@/stores/session'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import PipelineWizard from '@/components/PipelineWizard.vue'
import OutboundPickupDialog from '../../platformUi/samples/OutboundPickupDialog.vue'
import { businessToday, isWorkflowDateBefore, isWorkflowDateValid } from '@/composables/workflowDate'
import { sampleOutboundDemoRows } from '@/data/workflowDemo'

const route = useRoute()
const session = useSessionStore()
const available = PIPELINE_AVAILABLE
const pageName = computed(() => String(route.meta.pageName ?? '样品出库'))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pageKey = computed(() => String(route.meta.pageKey ?? 'outbound'))
const pages = computed(() => modules.find((m) => m.key === 'sample')?.pages ?? [])

type WorkflowSampleRow = SampleRow & {
  workflowDates?: { sampleAvailableAt?: string; sampleInboundAt?: string; sampleReturnedAt?: string }
}
const rows = ref<WorkflowSampleRow[]>([])
type TableSelectionRef<T> = { toggleRowSelection: (row: T, selected?: boolean) => void }
const tableRef = ref<TableSelectionRef<SampleRow> | null>(null)
const selectedNo = ref('')
const selectedRows = ref<SampleRow[]>([])
const keyword = ref('')
const statusFilter = ref('')
const pageSize = 12
const tablePage = ref(1)
const formOpen = ref(false)
const editOpen = ref(false)
const editReportNo = ref('')
const wizardReadonly = ref(false)
function viewSample(row: SampleRow) {
  wizardReadonly.value = true
  editReportNo.value = row.reportNo
  editOpen.value = true
}
const form = reactive({ managerId: '', managerName: '', outTime: '', receiverName: '', pickupTime: '', returnNote: '' })
watch(() => form.outTime, (value) => { form.pickupTime = value })

const outboundRows = computed(() => rows.value.filter((r) => (
  r.sampleStatus === '已入库'
  || (
    r.sampleStatus === '已领取'
    && r.status === '检测录入中'
    && !r.dataEntryStarted
  )
)))
const statusOptions = computed(() => Array.from(new Set(
  outboundRows.value.map((row) => String(row.dataStatus || row.status || '')).filter(Boolean),
)))
const filteredRows = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  return outboundRows.value.filter((r) =>
    (!k || [r.sampleNo, r.reportNo, r.client, r.project].some((v) => String(v ?? '').toLowerCase().includes(k)))
    && (!statusFilter.value || String(r.dataStatus || r.status || '') === statusFilter.value),
  )
})
const pagedRows = computed(() => filteredRows.value.slice((tablePage.value - 1) * pageSize, tablePage.value * pageSize))
watch([filteredRows, keyword, statusFilter], () => { tablePage.value = 1 })
const selected = computed(() => outboundRows.value.find((r) => r.reportNo === selectedNo.value))
const canPickupSelected = computed(() => selected.value?.sampleStatus === '已入库')
const canReturnSelected = computed(() => selected.value?.canRecallSampleOutbound === true)
const selectedInboundDate = computed(() => selected.value?.workflowDates?.sampleInboundAt || '')
const canSign = computed(() =>
  Boolean(
    form.managerName
    && (session.canOverrideWorkflowDate || isWorkflowDateValid(selectedInboundDate.value))
    && form.outTime
    && form.receiverName.trim()
    && form.pickupTime
    && isWorkflowDateValid(form.outTime)
    && isWorkflowDateValid(form.pickupTime)
    && !isWorkflowDateBefore(form.outTime, selectedInboundDate.value),
  ),
)

const stockPaging=createServerPage({presentation:'outbound'})
const stockPage=stockPaging.state
function setListQuery(q:Record<string,any>){stockPaging.setQuery({...q,presentation:'outbound'})}
async function exportListRows(){return fetchListExport('/api/samples/query',{...stockPage.query,view:'outbound'})}
let stockGeneration=0
async function load() {
  if (!available) {
    rows.value = sampleOutboundDemoRows
    return
  }
  const generation=++stockGeneration
  try { const result=await fetchListPage<SampleRow>('/api/samples/query',{...stockPage.query,view:'outbound'})
  if(generation===stockGeneration){rows.value=result.rows;stockPage.total=result.total}
  } catch { /* request() publishes the list failure; preserve the previous page. */ }
}


// 管理员=当前登录操作者（真实工号/姓名，不编造）；出库/领取时间默认今天（操作时间戳，可改）
const today = businessToday()
function resetForm() {
  form.managerId = session.account
  form.managerName = session.userName
  form.outTime = today
  form.receiverName = ''
  form.pickupTime = today
  form.returnNote = ''
}

function openForm(row: SampleRow) {
  selectedNo.value = row.reportNo
  resetForm()
  formOpen.value = true
}
function onSelectionChange(selection: SampleRow[]) {
  selectedRows.value = selection
  selectedNo.value = selection[selection.length - 1]?.reportNo ?? ''
}
function toggleRow(row: SampleRow) {
  tableRef.value?.toggleRowSelection(row)
}
function viewSelected() {
  const row = selected.value
  if (!row) return
  viewSample(row)
}
function openSelectedForm() {
  const row = selected.value
  if (row?.sampleStatus === '已入库') openForm(row)
}
async function returnStockSelected() {
  const row = selected.value
  if (!row?.canRecallSampleOutbound) return
  try {
    await ElMessageBox.confirm(
      `确认将已领取样品 ${row.sampleNo} 撤回并恢复为“已入库”？`,
      '撤回入库',
      { type: 'warning' },
    )
    await submitSampleReturnStock(row.reportNo)
    ElMessage.success(`${row.sampleNo} 已撤回入库，可重新办理出库领取`)
    selectedNo.value = ''
    await load()
  } catch (error) {
    if (error instanceof Error && error.message !== 'cancel') ElMessage.error(error.message || '撤回入库失败')
  }
}

async function submit(action: 'sign' | 'return') {
  const row = selected.value
  if (!row) return
  if (action === 'sign' && !canSign.value) {
    ElMessage.warning('请完整填写出库领取单（领样人、出库/领取时间）')
    return
  }
  if (action === 'return' && !form.returnNote.trim()) {
    ElMessage.warning('退回需填写原因')
    return
  }
  try {
    await submitSamplePickup(row.reportNo, {
      action,
      managerId: form.managerId,
      managerName: form.managerName,
      outTime: form.outTime,
      receiverName: form.receiverName,
      pickupTime: form.pickupTime,
      returnNote: form.returnNote,
    })
    ElMessage.success(action === 'sign' ? `${row.sampleNo} 已签字领取` : `${row.sampleNo} 已退回`)
    formOpen.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '提交失败')
  }
}

// BEGIN TEMPLATE STOCK ADAPTER
const stockList=useListPresentation(reactive({serverPaging:available,listPage:stockPage,setListQuery,exportListRows,title:pageName,session,available,rows:outboundRows,view:viewSample,load,
 canDispatch:(r:SampleRow)=>available && r.sampleStatus==='已入库',canRecall:(r:SampleRow)=>available && r.canRecallSampleOutbound===true && session.canAction('sample.return_stock'),dispatch:openForm,recall:(r:SampleRow)=>{selectedNo.value=r.reportNo;return returnStockSelected()},canReturn:(r:SampleRow)=>available && r.sampleStatus==='已入库' && session.canAction('sample.out_warehouse.return'),
}),'outbound')
// END TEMPLATE STOCK ADAPTER
watch(()=>JSON.stringify([stockPage.query,session.dataScope]),()=>void load(),{immediate:true})
</script>
