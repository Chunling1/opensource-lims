<script setup lang="ts">
import ConfirmationModal from '../common/ConfirmationModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import FeedbackNotice from '../common/FeedbackNotice.vue'
import { computed, ref, watch } from 'vue'
import type { UploadProgress } from '../common/fileUploadProgress'
import DataEntryFiles from './DataEntryFiles.vue'
import DataEntryPreview from './DataEntryPreview.vue'
import TemplateCompletionIcon from '../common/TemplateCompletionIcon.vue'
import type { ErrorValue } from '../../services/common/errors'
import type { EntryDetail, EntryFileKind, EntryFileSummary } from '../../types/testing/dataEntryDetail'
const props = defineProps<{ detail: EntryDetail; layoutId: string; activeTab: string; busy: boolean; readonly: boolean; dirty: boolean; canConfirm: boolean; confirmed: boolean; previewUrl: string; previewName: string; previewBlob?: Blob; layoutError?: string; templateDownloading?: boolean; completeReportDownloading?: boolean; completionError?: ErrorValue; removalError?: ErrorValue; progressError?: string; upload: (kind: EntryFileKind, file: File, progress: UploadProgress) => Promise<void> }>()
const emit = defineEmits<{ 'update:layoutId': [string]; selectTab: [string]; begin: ['files' | 'preview']; downloadTemplate: []; downloadCompleteReport: []; finalPreview: []; remove: [EntryFileSummary]; download: [EntryFileSummary]; sort: [string[]]; changeLayout: [string]; confirm: []; back: []; refreshProgress: [] }>()
const tabs = [
  { key: 'template', label: '报告模板', icon: 'ti ti-file-word', tabId: 'report-tab-template', panelId: 'report-panel-template' },
  { key: 'files', label: '上传文件', icon: 'ti ti-upload', tabId: 'report-tab-files', panelId: 'report-panel-files' },
  { key: 'preview', label: '报告预览', icon: 'ti ti-file-search', tabId: 'report-tab-preview', panelId: 'report-panel-preview' },
  { key: 'complete', label: '报告确认', icon: 'ti ti-circle-check', tabId: 'report-tab-complete', panelId: 'report-panel-complete' },
]
const showConfirmationHint = computed(() => !props.confirmed && (props.dirty || props.detail.reportStatus !== 'ready' || !props.previewUrl))
const currentStep = computed(() => tabs.findIndex(step => step.key === props.activeTab))
const changing = ref(false), targetLayout = ref('')
watch(() => props.detail.layoutId, () => { changing.value = false })
function chooseLayout(event: Event) {
  const select = event.target as HTMLSelectElement, value = select.value
  if (value === props.layoutId) { changing.value = false; return }
  if (props.detail.templateJob || props.detail.completeReportJob || props.detail.job || props.detail.files.some(file => file.kind === 'report' || file.kind === 'appendix')) {
    select.value = props.layoutId
    targetLayout.value = value; changing.value = true
  } else emit('update:layoutId', value)
}
const targetLabel = computed(() => props.detail.layouts.find(layout => layout.id === targetLayout.value)?.label || '')
const currentLabel = computed(() => props.detail.layouts.find(layout => layout.id === props.layoutId)?.label || '')
const templateFields = computed(() => [...props.detail.template.labels.filter(label => !label.startsWith('首页版式')), `模板版本：${props.detail.template.version}`].map(label => {
  const separator = label.indexOf('：')
  return { label: separator < 0 ? label : label.slice(0, separator), value: separator < 0 ? '—' : label.slice(separator + 1).trim() }
}))
const completeReport = computed(() => props.detail.files.some(file => file.kind === 'report'))
const appendixCount = computed(() => props.detail.files.filter(file => file.kind === 'appendix').length)
const previewDisabled = computed(() => props.busy || changing.value || !!props.detail.template.error || props.readonly && (props.dirty || props.detail.reportStatus !== 'ready'))
const layoutWarning = computed(() => completeReport.value
  ? `首页版式将切换为“${targetLabel.value}”，已上传的完整报告将被清空，附加文件保留。请按新首页版式重新上传完整报告，或直接使用系统生成的报告。`
  : appendixCount.value
    ? `首页版式将切换为“${targetLabel.value}”，已上传的附加文件及顺序将保留，请核对其是否适用。旧模板及报告预览将失效。`
    : `首页版式将切换为“${targetLabel.value}”，旧模板及报告预览将失效。`)
const task = computed(() => props.detail.templateJob)
const changed = computed(() => props.dirty || props.detail.templateStale || props.layoutId !== task.value?.layoutId)
const running = computed(() => !!task.value && !changed.value && task.value.stage === 'word')
const completeTask = computed(() => props.detail.completeReportJob)
const completeSupported = computed(() => props.detail.completeReportGeneration?.layoutIds.includes(props.layoutId) ?? false)
const completeChanged = computed(() => props.dirty || props.detail.completeReportStale || props.layoutId !== completeTask.value?.layoutId)
const downloadBusy = computed(() => props.busy || changing.value || props.templateDownloading || props.completeReportDownloading)
const generating = computed(() => props.detail.reportStatus === 'running' || props.busy && (props.dirty || props.detail.reportStatus !== 'ready'))
const waitingForReport = computed(() => props.detail.reportStatus === 'running' && !props.dirty)
const elapsedSeconds = computed(() => Math.floor((props.detail.job?.elapsedMs ?? 0) / 1000))
const generationDisabled = computed(() => props.readonly || props.busy || !!props.detail.template.error || props.detail.reportStatus === 'running' || !props.dirty && props.detail.reportStatus === 'ready')
const emptyPreview = computed(() => !props.detail.job ? '报告未生成' : props.dirty || props.detail.reportStatus === 'stale' ? '请更新报告预览。' : {
  pending: '报告未生成', running: '报告正在生成，请稍候。', ready: props.busy ? '正在加载报告预览…' : '报告已生成，暂未加载预览。', failed: '报告生成失败，请重试。',
}[props.detail.reportStatus])
</script>
<template>
  <section class="card" aria-label="报告填写流程">
  <div class="card-body checkout-tab">
    <div class="step-arrow-nav mt-n3 mx-n3 mb-3">
      <ul class="nav nav-pills nav-justified custom-nav" role="tablist" aria-label="报告填写步骤">
        <li v-for="(step, index) in tabs" :key="step.key" class="nav-item" role="presentation">
          <button :id="step.tabId" class="nav-link text-body-emphasis fs-5 p-2 p-md-3 h-100 w-100" :class="{ active: activeTab === step.key, done: confirmed || index < currentStep }" type="button" role="tab" :disabled="busy || changing || step.key === 'complete' && !confirmed && !canConfirm" :aria-label="step.label" :aria-describedby="step.key === 'complete' && showConfirmationHint ? 'report-confirmation-hint' : undefined" :aria-controls="step.panelId" :aria-selected="activeTab === step.key" :aria-current="activeTab === step.key ? 'step' : undefined" @click="emit('selectTab', step.key)"><span class="d-block d-md-inline mb-2 mb-md-0"><i :class="step.icon" class="fs-4 p-2 bg-primary-subtle text-body-emphasis rounded-circle align-middle me-md-2" aria-hidden="true"></i></span>{{ step.label }}<small v-if="step.key === 'complete' && showConfirmationHint" id="report-confirmation-hint" class="d-block text-muted fw-normal small mt-1">报告预览就绪后可确认</small></button>
        </li>
      </ul>
    </div>
  <FeedbackNotice v-if="completionError" :message="completionError.message" title="报告确认提示">{{ completionError.message }}</FeedbackNotice>
  <FeedbackNotice v-if="progressError" :message="progressError">{{ progressError }} <button type="button" class="btn btn-link p-0" :disabled="busy" @click="emit('refreshProgress')">刷新状态</button></FeedbackNotice>
  <div v-show="activeTab === 'template'" id="report-panel-template" class="p-2 p-lg-4" role="tabpanel" aria-labelledby="report-tab-template">
  <section aria-label="报告模板">
      <div class="mb-4"><h4 class="mb-2">准备报告文件</h4><p class="text-muted mb-0">选择首页版式后，可下载模板填写，或下载完整报告进行校核并按需修改。</p></div>
      <div class="row g-4 align-items-stretch">
        <div class="col-lg-6">
          <div class="border rounded p-3 p-lg-4 h-100">
            <div class="d-flex align-items-center gap-3 mb-4"><div class="avatar-sm flex-shrink-0"><span class="avatar bg-primary-subtle text-body-emphasis rounded"><i class="ti ti-file-text fs-1" aria-hidden="true"></i></span></div><div><h5 class="mb-1">报告配置</h5><span class="text-muted text-break">{{ detail.sample.code }}</span></div></div>
            <dl class="row g-3 mb-0"><div v-for="field in templateFields" :key="field.label" class="col-6"><dt class="text-muted fw-normal mb-1">{{ field.label }}</dt><dd class="fw-medium text-break mb-0">{{ field.value }}</dd></div></dl>
          </div>
        </div>
        <div class="col-lg-6">
          <div class="bg-light rounded p-3 p-lg-4 h-100">
            <label for="entry-report-layout" class="form-label fw-semibold">首页版式</label><select id="entry-report-layout" class="form-select" :class="{ 'is-invalid': layoutError }" :value="layoutId" :disabled="readonly || busy" @change="chooseLayout"><option v-for="layout in detail.layouts" :key="layout.id" :value="layout.id">{{ layout.label }}</option></select><div v-if="layoutError" class="invalid-feedback">{{ layoutError }}</div>
            <p class="text-muted small mt-2 mb-3">完整报告的首页版式需与此处选择一致。</p>
            <div class="border-top pt-3">
              <div class="row g-3">
                <div class="col-12 col-sm-6">
                  <button type="button" class="btn btn-ghost-dark border material-shadow-none w-100" aria-describedby="template-download-hint" :disabled="downloadBusy || !!detail.template.error || readonly && (changed || !task?.wordAvailable)" @click="emit('downloadTemplate')"><span v-if="templateDownloading" class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span><i v-else class="ti ti-download me-2" aria-hidden="true"></i>下载模板</button>
                  <p id="template-download-hint" class="text-muted small mt-2 mb-0">下载模板，按需填写报告内容。</p>
                  <p v-if="!detail.template.error && changed && task" class="text-muted small mt-2 mb-0" role="status">{{ layoutId !== task.layoutId ? '首页版式已更改，请下载对应模板。' : '试验资料已修改，请下载最新模板。' }}</p>
                  <div v-else-if="!detail.template.error && task" class="text-muted small mt-2" role="status"><span v-if="running" class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>{{ running ? '正在生成模板…' : task.wordAvailable ? '模板已就绪' : '模板生成失败，请重试下载。' }} · 已用 {{ Math.floor(task.elapsedMs / 1000) }} 秒<p v-if="task.error && !task.wordAvailable" class="text-danger mt-2 mb-0">{{ task.error }}</p></div>
                </div>
                <div class="col-12 col-sm-6" aria-label="自动生成完整报告">
                  <button type="button" class="btn btn-ghost-dark border material-shadow-none w-100" aria-describedby="complete-report-download-hint" :disabled="!completeSupported || downloadBusy || !!detail.template.error || readonly && (completeChanged || !completeTask?.wordAvailable)" @click="emit('downloadCompleteReport')"><span v-if="completeReportDownloading" class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span><i v-else class="ti ti-download me-2" aria-hidden="true"></i>下载完整报告</button>
                  <p id="complete-report-download-hint" class="text-muted small mt-2 mb-0"><template v-if="completeSupported">根据已保存的检测数据自动生成。
</template><template v-else><span>暂不支持</span>。{{ detail.completeReportGeneration?.unavailableReason || '当前检测方案或报告版式暂不支持自动生成完整报告。' }}</template></p>
                  <p v-if="completeSupported && completeTask" class="text-muted small mt-2 mb-0" role="status">{{ completeChanged ? '资料或版式已更改，请下载最新完整报告。' : completeTask.stage === 'word' ? '正在生成完整报告…' : completeTask.wordAvailable ? '完整报告已就绪' : '完整报告生成失败，请重试下载。' }}<span v-if="!completeChanged"> · 已用 {{ Math.floor(completeTask.elapsedMs / 1000) }} 秒</span></p>
                  <p v-if="completeSupported && !completeChanged && completeTask?.error && !completeTask.wordAvailable" class="text-danger small mt-2 mb-0" role="alert">{{ completeTask.error }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <p v-if="detail.template.error" class="text-danger mt-2 mb-0" role="alert">{{ detail.template.error }}</p>
      <div class="d-flex flex-wrap align-items-center gap-3 border-top pt-4 mt-4"><button type="button" class="btn btn-primary btn-label right ms-auto" :disabled="readonly || busy || changing || !!detail.template.error" @click="emit('begin', 'files')"><i class="ti ti-upload label-icon align-middle fs-4 ms-2" aria-hidden="true"></i>上传文件</button></div>
  </section>
  </div>
  <div v-show="activeTab === 'files'" id="report-panel-files" class="p-2 p-lg-4" role="tabpanel" aria-labelledby="report-tab-files">
  <div class="d-flex flex-wrap align-items-start justify-content-between gap-3 mb-4"><div><h4 class="mb-2">上传报告文件</h4><p class="text-muted mb-0">按需上传完整报告或附加文件；不上传时，系统使用模板文件作为报告。</p></div><span class="badge bg-light text-body-emphasis small fw-normal p-2">当前首页版式：{{ currentLabel }}</span></div>
  <DataEntryFiles :removal-error="removalError" :upload="upload" :detail="detail" :layout-id="layoutId" :busy="busy" :readonly="readonly" :dirty="dirty" @remove="emit('remove', $event)" @download="emit('download', $event)" @sort="emit('sort', $event)"><template #upload-status><slot name="upload-status" /></template></DataEntryFiles>
  <div class="d-flex flex-wrap align-items-start gap-3 border-top pt-4 mt-4"><button type="button" class="btn btn-light btn-label" :disabled="busy" @click="emit('selectTab', 'template')"><i class="ti ti-arrow-left label-icon align-middle fs-4 me-2" aria-hidden="true"></i>返回报告模板</button><button type="button" class="btn btn-primary btn-label right ms-auto" :disabled="previewDisabled" @click="emit('begin', 'preview')"><i class="ti ti-file-search label-icon align-middle fs-4 ms-2" aria-hidden="true"></i>预览报告</button></div>
  </div>
  <div v-show="activeTab === 'preview'" id="report-panel-preview" class="p-2 p-lg-4" role="tabpanel" aria-labelledby="report-tab-preview">
  <DataEntryPreview embedded collapsible :url="previewUrl" :name="previewName" :blob="previewBlob" type="application/pdf" title="完整报告预览" :subtitle="readonly ? undefined : '请仔细检查报告内容，点击报告确认完成报告填写。'" persistent>
    <template #actions><button class="btn btn-primary" type="button" :disabled="generationDisabled" :aria-busy="generating" @click="emit('finalPreview')"><span v-if="generating" class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>生成预览</button></template>
    <template #empty>
      <div class="border rounded text-center p-4 p-lg-5">
        <div v-if="waitingForReport" role="status" aria-label="报告生成进度">
          <div class="spinner-border text-primary mb-3" aria-hidden="true"></div>
          <h5>{{ detail.job?.phase === 'queued' ? '已加入报告生成队列' : '正在生成完整报告' }}</h5>
          <p class="mb-2">生成时间需要 30 秒左右，请耐心等待。 {{ detail.job?.stage || '等待后台处理' }}<span v-if="detail.job?.elapsedMs !== undefined"> · 已用 {{ elapsedSeconds }} 秒</span></p>
          <p class="text-muted mb-4">{{ elapsedSeconds >= 30 ? '处理时间较长，您可以先办理其他业务。' : '可以离开本页，后台任务会继续。' }}稍后从该样品的“报告填写”查看结果。</p>
          <button type="button" class="btn btn-light" :disabled="busy" @click="emit('back')">返回列表</button>
        </div>
        <div v-else-if="busy && (generating || detail.reportStatus === 'ready')" role="status"><div class="spinner-border text-primary mb-3" aria-hidden="true"></div><h5 class="mb-0">{{ detail.reportStatus === 'ready' ? '正在加载报告预览…' : '正在提交生成任务…生成时间需要 30 秒左右，请耐心等待。' }}</h5></div>
        <template v-else>
          <div class="avatar-md mx-auto mb-3"><span class="avatar bg-light text-muted rounded-circle"><i :class="detail.reportStatus === 'failed' ? 'ti ti-alert-circle' : 'ti ti-file-search'" class="fs-32" aria-hidden="true"></i></span></div>
          <p class="text-muted mb-0">{{ emptyPreview }}</p><p v-if="detail.reportStatus === 'failed' && detail.job?.error" class="text-danger mt-2 mb-0" role="alert">{{ detail.job.error }}</p><button v-if="detail.reportStatus === 'ready' && !dirty && !busy" type="button" class="btn btn-light mt-3" @click="emit('finalPreview')">重新加载预览</button>
        </template>
      </div>
    </template>
  </DataEntryPreview>

  <div class="d-flex flex-wrap align-items-start gap-3 border-top pt-4 mt-4">
    <button type="button" class="btn btn-light btn-label" :disabled="busy" @click="emit('selectTab', 'files')"><i class="ti ti-arrow-left label-icon align-middle fs-4 me-2" aria-hidden="true"></i>返回上传文件</button>
    <button v-if="!readonly && detail.capabilities.canManageReport" class="btn btn-primary btn-label right ms-auto" type="button" :disabled="!canConfirm" @click="emit('confirm')"><i class="ti ti-circle-check label-icon align-middle fs-4 ms-2" aria-hidden="true"></i>{{ busy ? '正在确认…' : '报告确认' }}</button>
    <button v-else-if="confirmed" class="btn btn-primary btn-label right ms-auto" type="button" :disabled="busy" @click="emit('selectTab', 'complete')"><i class="ti ti-circle-check label-icon align-middle fs-4 ms-2" aria-hidden="true"></i>查看报告确认</button>
  </div>
  </div>
  <div v-show="activeTab === 'complete'" id="report-panel-complete" role="tabpanel" aria-labelledby="report-tab-complete">
    <div v-if="confirmed" class="text-center py-5" aria-label="报告确认总结">
      <div class="mb-4">
        <TemplateCompletionIcon :active="activeTab === 'complete'">
        <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <g class="text-success" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 105L36 46L82 87L18 105Z"/><path d="M37 47C38 60 65 87 81 87M29 32L25 28M83 17L87 21M97 55L99 62M67 103L69 107M101 90L97 94M60 17L63 12"/></g>
          <g class="text-primary" stroke="currentColor" stroke-width="3.5" stroke-linecap="round"><path d="M29 19C54 12 67 45 52 66M76 14C61 28 85 26 74 38C67 43 73 48 76 49M88 42C104 45 91 52 104 52M54 85C53 64 92 57 102 80M24 62L20 67M79 101L81 106"/></g>
        </svg>
        </TemplateCompletionIcon>
      </div>
      <h4 id="report-complete-title" class="mb-2" tabindex="-1">报告填写已完成</h4>
      <p class="text-muted">本次报告已确认，返回列表并点击“录入完成”可以完成检测数据录入。</p>
      <div class="d-flex flex-wrap justify-content-center gap-3 mt-4"><button type="button" class="btn btn-light btn-label" :disabled="busy" @click="emit('selectTab', 'preview')"><i class="ti ti-arrow-left label-icon align-middle fs-4 me-2" aria-hidden="true"></i>查看报告</button><button type="button" class="btn btn-primary btn-label right" :disabled="busy" @click="emit('back')"><i class="ti ti-list-check label-icon align-middle fs-4 ms-2" aria-hidden="true"></i>返回列表</button></div>
    </div>
  </div>
  </div>
  </section>
  <ConfirmationModal v-if="changing && !readonly" title="切换首页版式" :busy="busy" @close="changing = false">
    <p class="mb-0">{{ layoutWarning }}</p><ErrorNotice :error="removalError" />
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="changing = false">取消</button><button type="button" class="btn btn-primary" :disabled="busy || !targetLayout" @click="emit('changeLayout', targetLayout)">确认切换</button></template>
  </ConfirmationModal>
</template>
