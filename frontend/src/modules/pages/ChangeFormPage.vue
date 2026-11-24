<template>
  <ChangeList  :context="changeList" />
  <PipelineWizard
    v-model="wizardOpen"
    mode="samples"
    :change-report-no="selectedNo"
    :read-only="wizardReadonly"
    :detail-view="moduleKey === 'entrust' ? 'entrust_change' : 'sample_change'"
    @created="onChanged"
    @updated="onSaved"
  />

<AttachmentManagerDialog v-model="changeAttachmentsOpen" :report-no="changeList.attachmentId || ''" :view="moduleKey === 'entrust' ? 'entrust_change' : 'sample_change'" />
</template>

<script setup lang="ts">
// BEGIN TEMPLATE CHANGE IMPORTS
import {reactive} from 'vue'
import ChangeList from '../../platformUi/lists/ChangeList.vue'
import {createServerPage,fetchListPage,fetchListExport} from '../../platformUi/lists/serverPage'
import {useListPresentation} from '../../platformUi/lists/listPresentation'
import AttachmentManagerDialog from '@/components/AttachmentManagerDialog.vue'
// END TEMPLATE CHANGE IMPORTS
import { shallowRef, computed, ref, watch, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { modules } from '@/data/modules'
import { reportWorkRows } from '@/data/mock'
import { demoWorkflowRows } from '@/data/moduleDemo'
import { fetchReportRows, type ReportRow } from '@/services/auth'
import { PIPELINE_AVAILABLE } from '@/services/pipeline'
import { useSessionStore } from '@/stores/session'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import PipelineWizard from '@/components/PipelineWizard.vue'

const route = useRoute()
const session = useSessionStore()
const available = PIPELINE_AVAILABLE
const pageName = computed(() => String(route.meta.pageName ?? '更改'))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const moduleKey = computed(() => String(route.meta.moduleKey ?? 'entrust'))
const pageKey = computed(() => String(route.meta.pageKey ?? 'change'))
const pages = computed(() => modules.find((m) => m.key === (route.meta.moduleKey as string))?.pages ?? [])

const allRows = shallowRef<ReportRow[]>([])
const changeLoading=ref(false),changeError=ref('')
const selectedNo = ref('')
const keyword = ref('')
const pageSize = 12
const tablePage = ref(1)
const wizardOpen = ref(false)
const wizardReadonly = ref(false)
const selectedRow = ref<ReportRow | null>(null)
type TableRef = { toggleRowSelection: (row: ReportRow, selected?: boolean) => void }
const tableRef = ref<TableRef | null>(null)

const changeRows = computed(() => allRows.value.filter((r) => r.status === '委托更改中'))
const filteredRows = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return changeRows.value
  return changeRows.value.filter((r) =>
    [r.reportNo, r.client, r.project].some((v) => String(v ?? '').toLowerCase().includes(k)),
  )
})
const pagedRows = computed(() => filteredRows.value.slice((tablePage.value - 1) * pageSize, tablePage.value * pageSize))
watch([filteredRows, keyword], () => { tablePage.value = 1 })

function returnReason(row: ReportRow): string {
  const ri = row.returnInfo
  if (!ri) return '—'
  return [ri.source, ri.note].filter(Boolean).join('：') || '—'
}

const changePaging=createServerPage({presentation:'change'})
const listPage=changePaging.state
function setListQuery(q:Record<string,any>){changePaging.setQuery({...q,presentation:'change'})}
async function exportListRows(){return fetchListExport('/api/reports/query',{...listPage.query,view:'query'})}
let listGeneration=0
async function load() {
  if (!available) {
    allRows.value = demoWorkflowRows as ReportRow[]
    return
  }
  changeLoading.value=true;changeError.value=''
  const generation=++listGeneration
  try{const result=await fetchListPage<ReportRow>('/api/reports/query',{...listPage.query,view:'query'});if(generation===listGeneration){allRows.value=result.rows;listPage.total=result.total}}catch(e){if(generation===listGeneration)changeError.value=e instanceof Error?e.message:String(e)}finally{if(generation===listGeneration)changeLoading.value=false}
}
// One list watch is registered after the presentation initializes its query.

function openWizard(row: ReportRow, readOnly = false) {
  wizardReadonly.value = readOnly
  selectedNo.value = row.reportNo
  wizardOpen.value = true
}
function onSelection(rows: ReportRow[]) { selectedRow.value = rows[rows.length - 1] ?? null }
function toggleRow(row: ReportRow) { tableRef.value?.toggleRowSelection(row) }
function exportRows() {
  const header = '报告编号,委托单位,检测项目,状态,退回原因\n'
  const lines = filteredRows.value.map((row) => [row.reportNo, row.client, row.project, row.status, returnReason(row)]
    .map((value) => `"${String(value ?? '').replace(/"/g, '""')}"`).join(','))
  const blob = new Blob([`\uFEFF${header}${lines.join('\n')}`], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `${pageName.value}-演示清单.csv`
  link.click()
  URL.revokeObjectURL(link.href)
}
async function onChanged() {
  wizardOpen.value = false
  selectedNo.value = ''
  await load()
}
async function onSaved(reportNo: string) {
  selectedNo.value = reportNo
  await load()
}
// BEGIN TEMPLATE CHANGE ADAPTER
const changeList=useListPresentation(reactive({serverPaging:available,listPage,setListQuery,exportListRows,identity:computed(()=>route.path+session.account),title:pageName,session,rows:changeRows,loading:changeLoading,error:changeError,load,view:(r:any)=>openWizard(r,true),edit:openWizard,permission:computed(()=>moduleKey.value==='entrust'?'entrust.change.view':'sample.change.view')}),'change')
const changeAttachmentsOpen=computed({get:()=>!!changeList.attachmentId,set:(v:boolean)=>{if(!v)changeList.attachmentId=undefined}})
// END TEMPLATE CHANGE ADAPTER
watch(()=>JSON.stringify([listPage.query,session.account,route.path]),()=>void load(),{immediate:true})
</script>
