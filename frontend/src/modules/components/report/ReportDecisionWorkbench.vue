<template>
  <SchemaForm :model="props" :schema="decisionTemplateSchema">
    <template #evidence>
      <FormTabs :model-value="activeTab" :tabs="evidenceTabs" label="审核证据分类" @update:model-value="activeTab = $event as EvidenceTab" />
      <div id="decision-report-panel" role="tabpanel" aria-labelledby="decision-report-tab" v-show="activeTab === 'report'">
        <LoadState :loading="documentLoading" :error="props.documentIssue || decisionFallbackIssue" :has-data="Boolean(documentPdfUrl || htmlPreviewUrl)" @retry="$emit('refresh-report')" />
        <DataEntryPreview :url="documentPdfUrl || htmlPreviewUrl" :name="report.reportNo + (documentPdfUrl ? '.pdf' : '.html')" :type="documentPdfUrl ? 'application/pdf' : 'text/html'" title="正式报告" :subtitle="documentPreviewLabel || documentState.hint" persistent hide-download hide-print>
          <template #before><p role="status" data-testid="document-state-tag">{{ documentState.label }} · {{ documentState.hint }}</p></template>
          <template #actions><button class="btn btn-light" type="button" @click="$emit('refresh-report')">刷新版本</button><button class="btn btn-primary" type="button" @click="$emit('open-report')">大窗口预览</button></template>
        </DataEntryPreview>
      </div>
      <div id="decision-data-panel" role="tabpanel" aria-labelledby="decision-data-tab" v-show="activeTab === 'data'"><SchemaForm :model="props" :schema="decisionSummarySchema" readonly /></div>
      <div id="decision-files-panel" role="tabpanel" aria-labelledby="decision-files-tab" v-show="activeTab === 'files'">
        <AttachmentFileList :files="decisionFiles" :can-attach="false" :busy="false" title="原始记录与附件" empty-label="当前报告没有可查看的附件" @download="file => $emit('open-attachment',file.source)">
          <template #metadata="{file}">{{ file.source.status || '已归档' }} · {{ file.source.source || file.source.type || '业务附件' }}</template>
          <template #download="{file}"><button class="btn btn-sm btn-primary-lt" type="button" @click="$emit('open-attachment',file.source)">查看附件</button></template>
        </AttachmentFileList>
      </div>
      <div id="decision-checks-panel" role="tabpanel" aria-labelledby="decision-checks-tab" v-show="activeTab === 'checks'"><SchemaForm :model="props" :schema="decisionChecksSchema" readonly /></div>
    </template>
    <template #precheck><p role="status" :data-state="precheckSummary.state" data-testid="overall-precheck-summary">{{ precheckSummary.title }} · {{ precheckSummary.hint }}</p></template>
    <template #presets><button class="btn btn-light" v-for="preset in opinionPresets" :key="preset" type="button" :disabled="readOnly || !canAct" @click="$emit('update:opinion', preset)">{{ preset }}</button></template>
    <template #actions><footer class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <el-button v-if="!readOnly" type="primary" size="large" :disabled="!canPass || completedChecklist < checklist.length" @click="$emit('pass')">
            {{ nodeKey === 'review' ? '审核通过，提交批准' : '批准通过，提交打印' }}
          </el-button>
          <el-button v-if="!readOnly" size="large" :disabled="!canAct" @click="$emit('return')">退回修改</el-button>
          <div>
            <el-button v-if="!readOnly" text :disabled="!canAct" @click="$emit('save-opinion')">保存意见</el-button>
            <el-button v-if="!readOnly && canUndo" text type="warning" @click="$emit('undo')">{{ undoLabel }}</el-button>
          </div>
          <el-button v-if="readOnly" type="primary" plain size="large" @click="$emit('close')">关闭查看</el-button>
        </footer></template>
  </SchemaForm>
</template>

<script setup lang="ts">
// BEGIN TEMPLATE DECISION IMPORTS
import { reportPreviewError } from '../../../platformUi/apiErrors'
import type { AppError } from '../../../services/common/errors'
import SchemaForm from '../../../components/forms/SchemaForm.vue'
import FormTabs from '../../../components/forms/FormTabs.vue'
import DataEntryPreview from '../../../components/testing/DataEntryPreview.vue'
import AttachmentFileList from '../../../components/common/AttachmentFileList.vue'
import LoadState from '../../../components/common/LoadState.vue'
import type {FormSchema,FormField} from '../../../types/forms'
import {onBeforeUnmount} from 'vue'
// END TEMPLATE DECISION IMPORTS

import { Loading } from '@element-plus/icons-vue'
import { computed, reactive, ref, watch } from 'vue'

type SummarySection = { title: string; fields: [string, string][] }
type CheckItem = { group: string; status: string; type: 'success' | 'warning' | 'danger'; items: [string, string][] }
type DecisionAttachment = { id?: number; name: string; type: string; source: string; status: string; contentType?: string; url?: string }
type DecisionReport = {
  reportNo: string
  client?: string
  project?: string
  status: string
  dataStatus?: string
  deadline?: string
  outOfScope?: boolean
}

const props = defineProps<{
  nodeKey: 'review' | 'approval'
  report: DecisionReport
  projectName?: string
  summary: SummarySection[]
  checks: CheckItem[]
  attachments: DecisionAttachment[]
  signatures: { 主检: string; 审核: string; 批准: string }
  documentPdfUrl?: string
  documentHtml?: string
  documentLoading?: boolean
  documentError?: string
  documentIssue?: AppError
  documentPreviewLabel?: string
  documentReady?: boolean
  opinion: string
  currentUser: string
  canAct: boolean
  canPass: boolean
  canUndo?: boolean
  undoLabel?: string
  readOnly?: boolean
}>()

const emit = defineEmits<{
  'update:opinion': [value: string]
  'open-report': []
  'refresh-report': []
  'open-attachment': [file: DecisionAttachment]
  pass: []
  return: []
  undo: []
  'save-opinion': []
  close: []
}>()

type EvidenceTab = 'report' | 'data' | 'files' | 'checks'
const activeTab = ref<EvidenceTab>('report')
const confirmations = reactive<Record<string, boolean>>({})

watch(() => props.report.reportNo, () => {
  activeTab.value = 'report'
  Object.keys(confirmations).forEach((key) => delete confirmations[key])
})

const nodeTitle = computed(() => props.nodeKey === 'review' ? '报告审核' : '报告批准')
const blockingCount = computed(() => props.checks.filter((item) => item.type === 'danger').length)
const warningCount = computed(() => props.checks.filter((item) => item.type === 'warning').length)
const documentErrorText = computed(() => props.documentError?.trim() ?? '')
const documentState = computed(() => {
  if (props.documentLoading) return {
    state: 'loading', label: '预览加载中', type: 'info' as const,
    hint: '正式报告正在加载，预检尚未完成。',
  }
  if (documentErrorText.value) return {
    state: 'error', label: '预览异常', type: 'danger' as const,
    hint: `正式报告预览异常：${documentErrorText.value}`,
  }
  if (!props.documentReady) return {
    state: 'not_ready', label: '版本未就绪', type: 'warning' as const,
    hint: '正式报告版本尚未就绪，请检查正文是否补齐，并生成或刷新正式版本。',
  }
  if (!props.documentPdfUrl && !props.documentHtml) return {
    state: 'preview_missing', label: '预览待确认', type: 'warning' as const,
    hint: '正式版本已就绪，但尚未取得对应预览，请刷新后核对。',
  }
  return {
    state: 'ready', label: '版本就绪', type: 'success' as const,
    hint: '当前正式版本及预览已就绪，仍须人工核对正文。',
  }
})
const attentionCount = computed(() => blockingCount.value + warningCount.value
  + (props.report.outOfScope ? 1 : 0)
  + (documentState.value.state !== 'ready' ? 1 : 0)
  + (props.checks.length === 0 ? 1 : 0))
// Display evidence only: canPass remains owned by the existing parent/backend policy.
const precheckSummary = computed(() => {
  const concerns: string[] = []
  if (props.report.outOfScope) concerns.push('报告存在超范围标记，须核实授权依据')
  if (blockingCount.value) concerns.push(`三库检查存在 ${blockingCount.value} 项阻断/异常`)
  if (documentState.value.state !== 'ready') concerns.push(documentState.value.hint)
  if (props.checks.length === 0) concerns.push('尚未取得三库预检结果，不能确认整体预检通过')
  if (warningCount.value) concerns.push(`另有 ${warningCount.value} 项提醒需要人工核对`)
  const hint = concerns.join('；')
  if (props.report.outOfScope || blockingCount.value || documentState.value.state === 'error') {
    return { state: 'error', tone: 'danger', title: '预检存在异常，待处理', hint }
  }
  if (documentState.value.state === 'loading') return {
    state: 'loading', tone: 'pending', title: '预检进行中', hint,
  }
  if (documentState.value.state !== 'ready') return {
    state: 'pending', tone: 'pending',
    title: documentState.value.state === 'not_ready' ? '正式报告未就绪' : '报告预览待确认', hint,
  }
  if (props.checks.length === 0) return { state: 'pending', tone: 'pending', title: '三库预检待确认', hint }
  if (warningCount.value) return { state: 'warning', tone: 'warning', title: '预检有提醒，待核对', hint }
  return {
    state: 'ready', tone: 'ready', title: '系统预检通过',
    hint: '正式报告及预览已就绪，三库检查未发现异常；仍须完成人工核对。',
  }
})
const checkRank: Record<CheckItem['type'], number> = { danger: 0, warning: 1, success: 2 }
const sortedChecks = computed(() => [...props.checks].sort((a, b) => checkRank[a.type] - checkRank[b.type]))
const tabs = computed(() => [
  { key: 'report' as const, label: '正式报告', count: documentState.value.label },
  { key: 'data' as const, label: '业务与检测数据', count: props.summary.length },
  { key: 'files' as const, label: '原始记录与附件', count: props.attachments.length },
  { key: 'checks' as const, label: '异常与合规', count: attentionCount.value },
])

const checklist = computed(() => props.nodeKey === 'review'
  ? [
      { key: 'data', label: '检测数据与报告一致', description: '核对结果、单位、结论及报告正文', badge: '技术', tone: 'blue' },
      { key: 'records', label: '原始记录与附件齐全', description: '确认记录可追溯、版本正确', badge: `${props.attachments.length} 份`, tone: 'green' },
      { key: 'compliance', label: '标准、设备和能力适用', description: '优先处理系统标记的异常', badge: blockingCount.value ? `${blockingCount.value} 异常` : props.checks.length === 0 ? '待确认' : warningCount.value ? `${warningCount.value} 提醒` : '正常', tone: blockingCount.value ? 'red' : props.checks.length === 0 || warningCount.value ? 'amber' : 'green' },
      { key: 'conclusion', label: '结论表达准确', description: '结论与检测结果、判定依据一致', badge: '人工', tone: 'gray' },
    ]
  : [
      { key: 'reviewed', label: '审核环节已完成', description: '审核签名、意见及退回记录完整', badge: props.signatures.审核, tone: 'green' },
      { key: 'authorization', label: '授权范围和报告用途合规', description: '核对项目范围、标识和客户用途', badge: props.report.outOfScope ? '异常' : '正常', tone: props.report.outOfScope ? 'red' : 'green' },
      { key: 'version', label: '最终报告版本正确', description: '批准后绑定此版本，不再修改正文', badge: documentState.value.label, tone: documentState.value.state === 'ready' ? 'green' : documentState.value.state === 'error' ? 'red' : 'amber' },
      { key: 'delivery', label: '签章与交付条件明确', description: '确认签章、打印与发放要求', badge: '人工', tone: 'gray' },
    ])
const completedChecklist = computed(() => checklist.value.filter((item) => confirmations[item.key]).length)
const opinionPlaceholder = computed(() => props.nodeKey === 'review'
  ? '记录技术审核意见；退回时请明确指出数据、原始记录或报告正文需要修改的位置'
  : '记录批准意见；退回时请明确授权、版本、签章或交付方面的问题')
const opinionPresets = computed(() => props.nodeKey === 'review'
  ? ['内容完整，结果与原始记录一致', '请补充原始记录后重新提交', '检测依据与结论需要复核']
  : ['同意批准并提交打印', '请复核授权范围后重新提交', '请修正报告版本或签章要求'])

const workflowSteps = computed(() => {
  const labels = ['数据录入', '报告审核', '报告批准', '打印', '发放']
  const current = props.nodeKey === 'review' ? 1 : 2
  return labels.map((label, index) => ({ index: index + 1, label, state: index < current ? 'done' : index === current ? 'current' : 'todo' }))
})

function fileTypeMark(name: string) {
  const ext = name.split('.').pop()?.toUpperCase()
  return ext && ext.length <= 4 ? ext : 'FILE'
}

// BEGIN TEMPLATE DECISION ADAPTER
const decisionFallbackIssue=computed(()=>documentErrorText.value ? reportPreviewError(new Error(documentErrorText.value)) : undefined)
const evidenceTabs=computed(()=>tabs.value.map(tab=>({...tab,label:tab.label+'（'+tab.count+'）',tabId:'decision-'+tab.key+'-tab',panelId:'decision-'+tab.key+'-panel'})))
const decisionFiles=computed(()=>props.attachments.map((source,index)=>({id:String(source.id??'legacy-'+index),name:source.name,type:source.contentType||source.type||'',size:0,source})))
const htmlPreviewUrl=ref('')
watch(()=>props.documentHtml,html=>{if(htmlPreviewUrl.value)URL.revokeObjectURL(htmlPreviewUrl.value);htmlPreviewUrl.value=html?URL.createObjectURL(new Blob([html],{type:'text/html'})):''},{immediate:true})
onBeforeUnmount(()=>{if(htmlPreviewUrl.value)URL.revokeObjectURL(htmlPreviewUrl.value)})
function displayField(id:string,label:string,value:()=>string):FormField<typeof props>{return {id,label,control:'text',readonly:true,binding:{get:value}}}
const decisionSummarySchema=computed<FormSchema<typeof props>>(()=>({sections:props.summary.map((section,index)=>({id:'decision-summary-'+index,title:section.title,fields:section.fields.map(([label,value],fieldIndex)=>displayField('decision-summary-'+index+'-'+fieldIndex,label,()=>value))}))}))
const decisionChecksSchema=computed<FormSchema<typeof props>>(()=>({sections:sortedChecks.value.map((check,index)=>({id:'decision-check-'+index,title:check.group+' · '+check.status,fields:check.items.map(([label,value],fieldIndex)=>displayField('decision-check-'+index+'-'+fieldIndex,label,()=>value))}))}))
const decisionTemplateSchema=computed<FormSchema<typeof props>>(()=>({sections:[
 {id:'decision-context',title:nodeTitle.value+' · '+props.report.reportNo,fields:[displayField('decision-client','委托单位',()=>props.report.client||'—'),displayField('decision-project','检测项目',()=>props.report.project||'—'),displayField('decision-status','当前状态',()=>props.report.dataStatus||props.report.status),displayField('decision-flow','报告流程',()=>workflowSteps.value.map(step=>step.label).join(' → ')),displayField('decision-deadline','时限',()=>props.report.deadline||'正常时限'),displayField('decision-scope','能力范围',()=>props.report.outOfScope?'超范围':'按系统预检核对')]},
 {id:'decision-evidence',title:'报告与核对资料',fields:[],slot:'evidence'},
 {id:'decision-precheck',title:'系统预检',fields:[],slot:'precheck'},
 {id:'decision-checklist',title:nodeTitle.value+'核对清单（'+completedChecklist.value+'/'+checklist.value.length+'）',fields:checklist.value.map(item=>({id:'decision-confirm-'+item.key,label:item.label,control:'checkbox' as const,hint:item.description+' · '+item.badge,disabled:props.readOnly||!props.canAct,binding:{get:()=>Boolean(confirmations[item.key]),set:(_model:typeof props,value:boolean)=>{confirmations[item.key]=value}}}))},
 {id:'decision-opinion-section',title:nodeTitle.value+'意见',fields:[{id:'decision-opinion',label:nodeTitle.value+'意见',control:'textarea',width:'col-12',rows:3,placeholder:opinionPlaceholder.value,disabled:props.readOnly||!props.canAct,binding:{get:()=>props.opinion,set:(_model,value)=>emit('update:opinion',value)}},displayField('decision-user','当前处理人',()=>props.currentUser),displayField('decision-permission','处理权限',()=>props.canAct?'可处理':'仅查看')]},
 {id:'decision-presets',title:'常用意见',fields:[],slot:'presets'},
 {id:'decision-actions',title:'处理操作',fields:[],slot:'actions'},
]}))
// END TEMPLATE DECISION ADAPTER
</script>


