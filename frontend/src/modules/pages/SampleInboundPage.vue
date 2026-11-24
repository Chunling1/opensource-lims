<template>
  <PipelineWizard
    v-model="wizardOpen"
    mode="samples"
    sample-list-view="inbound"
    detail-view="sample_inbound"
    :department="session.dataScope.department"
    :change-report-no="editReportNo"
    :read-only="true"
  />

  <StorageList :context="stockList" />
  <InboundDateDialog :row="inboundRow" @close="inboundRow = undefined" @completed="inboundCompleted" />

</template>

<script setup lang="ts">
// BEGIN TEMPLATE STOCK IMPORTS
import StorageList from '../../platformUi/lists/StorageList.vue'
import InboundDateDialog from '../../platformUi/samples/InboundDateDialog.vue'
import {createServerPage,fetchListPage,fetchListExport} from '../../platformUi/lists/serverPage'
import {useListPresentation} from '../../platformUi/lists/listPresentation'
import {reactive} from 'vue'
// END TEMPLATE STOCK IMPORTS

import { computed, ref, watch, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modules } from '@/data/modules'
import { PIPELINE_AVAILABLE, fetchSamples, undoSampleInbound, type SampleRow } from '@/services/pipeline'
import { useSessionStore } from '@/stores/session'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import PipelineWizard from '@/components/PipelineWizard.vue'
import { sampleInboundDemoRows } from '@/data/workflowDemo'
const route = useRoute()
const session = useSessionStore()
const available = PIPELINE_AVAILABLE
const wizardOpen = ref(false)
const editReportNo = ref('')
const pageName = computed(() => String(route.meta.pageName ?? '样品入库'))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pageKey = computed(() => String(route.meta.pageKey ?? 'inbound'))
const pages = computed(() => modules.find((m) => m.key === 'sample')?.pages ?? [])

function viewSample(row: SampleRow) {
  editReportNo.value = row.reportNo
  wizardOpen.value = true
}

const all = ref<SampleRow[]>([])
type TableSelectionRef<T> = { toggleRowSelection: (row: T, selected?: boolean) => void }
const tableRef = ref<TableSelectionRef<SampleRow> | null>(null)
const selectedRow = ref<SampleRow | null>(null)
const selectedRows = ref<SampleRow[]>([])
const keyword = ref('')
const statusFilter = ref('')
const statusOptions = ['待入库', '已入库']
const hasActiveFilters = computed(() => Boolean(keyword.value.trim() || statusFilter.value))
const filteredRows = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  return all.value.filter((row) => {
    if (statusFilter.value && row.sampleStatus !== statusFilter.value) return false
    if (!normalizedKeyword) return true
    return [row.sampleNo, row.reportNo, row.client, row.project]
      .some((value) => String(value || '').toLowerCase().includes(normalizedKeyword))
  })
})
const canInboundSelected = computed(() => selectedRow.value?.sampleStatus === '待入库')
const stockPaging=createServerPage({presentation:'inbound'})
const stockPage=stockPaging.state
function setListQuery(q:Record<string,any>){stockPaging.setQuery({...q,presentation:'inbound'})}
async function exportListRows(){return fetchListExport('/api/samples/query',{...stockPage.query,view:'inbound'})}
let stockGeneration=0
async function load() {
  if (!available) {
    all.value = sampleInboundDemoRows
    return
  }
  const generation=++stockGeneration
  try { const result=await fetchListPage<SampleRow>('/api/samples/query',{...stockPage.query,view:'inbound'})
  if(generation===stockGeneration){all.value=result.rows;stockPage.total=result.total}
  } catch { /* request() publishes the list failure; preserve the previous page. */ }
}


const inboundRow = ref<SampleRow>()
function doInbound(row: SampleRow) {
  if (available && row.sampleStatus === '待入库' && session.canAction('sample.inbound.confirm')) inboundRow.value = row
}
async function inboundCompleted() {
  inboundRow.value = undefined
  ElMessage.success('样品已入库')
  await load()
}
function canUndoInbound(row: SampleRow) {
  return available && row.canUndoSampleInbound === true && session.canAction('sample.inbound.confirm')
}
async function doUndoInbound(row: SampleRow) {
  if (!canUndoInbound(row)) return
  try {
    await ElMessageBox.confirm(`确认撤销样品 ${row.sampleNo} 的入库？撤销后恢复待入库，需重新办理入库。`, '撤销入库', {type:'warning'})
  } catch { return }
  await undoSampleInbound(row.reportNo)
  ElMessage.success('已撤销入库，样品恢复待入库')
}
function onSelectionChange(selection: SampleRow[]) {
  selectedRows.value = selection
  selectedRow.value = selection[selection.length - 1] ?? null
}
function toggleRow(row: SampleRow) { tableRef.value?.toggleRowSelection(row) }
function viewSelected() {
  if (!selectedRow.value) return
  viewSample(selectedRow.value)
}
function inboundSelected() {
  if (canInboundSelected.value && selectedRow.value) doInbound(selectedRow.value)
}
function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
}

// BEGIN TEMPLATE STOCK ADAPTER
const stockList=useListPresentation(reactive({serverPaging:available,listPage:stockPage,setListQuery,exportListRows,title:pageName,session,available,rows:all,view:viewSample,load,
 canReceive:(r:SampleRow)=>available && r.sampleStatus==='待入库' && session.canAction('sample.inbound.confirm'),receive:doInbound,canUndoInbound,undoInbound:doUndoInbound,
}),'inbound')
// END TEMPLATE STOCK ADAPTER
watch(()=>JSON.stringify([stockPage.query,session.dataScope]),()=>void load(),{immediate:true})
</script>
