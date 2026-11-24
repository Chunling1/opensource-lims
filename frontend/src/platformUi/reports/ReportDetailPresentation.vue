<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import FormTabs from '../../components/forms/FormTabs.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import AttachmentFileList from '../../components/common/AttachmentFileList.vue'
import DataTable from '../../platformUi/TemplateDataTable'
import WorkflowDatePicker from '@/components/WorkflowDatePicker.vue'
import {reportSummarySchema,reportChecksSchema,reportTestSchema,reportOpinionSchema,reportVersionSchema,reportTimelineSchema,reportDocumentSchema,reportVersionRows,reportVersionColumns,reportFiles} from './reportDetailPresentation'
const props=defineProps<{context:Record<string,any>}>(),c=computed(()=>props.context),tab=ref('summary')
const tabs=Object.entries({summary:'报告信息',document:'完整报告与版本',files:'附件',checks:'校验结果',decision:'意见与操作'}).map(([key,label])=>({key,label,tabId:'report-detail-tab-'+key,panelId:'report-detail-panel-'+key}))
const htmlUrl=ref('')
watch(()=>c.value.coverHtml,html=>{if(htmlUrl.value)URL.revokeObjectURL(htmlUrl.value);htmlUrl.value=html?URL.createObjectURL(new Blob([html],{type:'text/html'})):''},{immediate:true})
watch(()=>c.value.formSessionId,()=>tab.value='summary')
onBeforeUnmount(()=>{if(htmlUrl.value)URL.revokeObjectURL(htmlUrl.value)})
const previewUrl=computed(()=>c.value.documentPdfUrl||c.value.coverPdfUrl||htmlUrl.value)
</script>
<template>
  <FormTabs v-model="tab" :tabs="tabs" label="报告详情" />
  <div v-show="tab==='summary'" id="report-detail-panel-summary" role="tabpanel" aria-labelledby="report-detail-tab-summary">
    <SchemaForm :model="c" :schema="reportSummarySchema(c)" readonly />
    <SchemaForm v-if="c.showTestInfoForm" :model="c.testInfo" :schema="reportTestSchema(c)" :readonly="c.formReadOnly">
      <template #start><WorkflowDatePicker v-model="c.testInfo.testStartDate" :disabled="c.formReadOnly" strict-order :previous-date="c.testPreviousDate" :next-date="c.testInfo.testEndDate" require-previous missing-previous-reason="缺少样品领取日期，请先完成出库领取。" /></template>
      <template #end><WorkflowDatePicker v-model="c.testInfo.testEndDate" :disabled="c.formReadOnly" strict-order :previous-date="c.testInfo.testStartDate" require-previous missing-previous-reason="请先填写试验开始日期。" /></template>
    </SchemaForm>
    <button v-if="c.showTestInfoForm" class="btn btn-primary" :disabled="c.formReadOnly||c.savingTestInfo" @click="c.saveTestInfo()">保存检测数据</button>
    <SchemaForm :model="c" :schema="reportTimelineSchema(c)" readonly />
  </div>
  <div v-show="tab==='document'" id="report-detail-panel-document" role="tabpanel" aria-labelledby="report-detail-tab-document">
    <SchemaForm :model="c" :schema="reportVersionSchema(c)" readonly>
      <template #actions>
        <button v-if="c.pipelineAvailable&&c.canEditReport&&c.session.canAction('report.pdf.merge')" class="btn btn-primary" :disabled="c.formReadOnly||c.documentGenerating||!c.documentPreflight?.ready" @click="c.generateDocument('official')">生成正式报告</button>
        <button v-if="c.pipelineAvailable&&c.canEditReport&&c.session.canAction('report.pdf.merge')" class="btn btn-light" :disabled="c.formReadOnly||c.documentGenerating||!c.documentPreflight?.ready" @click="c.generateDocument('audit')">生成内部审核包</button>
        <button class="btn btn-light" :disabled="c.documentLoading" @click="c.loadDocumentState()">刷新版本</button>
        <button v-if="c.pipelineAvailable&&c.canEditReport&&c.session.canAction('report.attachment.upload')" class="btn btn-primary" :disabled="c.formReadOnly" @click="c.openDocumentEditor()">编辑报告正文</button>
      </template>
    </SchemaForm>
    <FeedbackNotice v-if="c.documentJob&&['queued','running'].includes(c.documentJob.status)" :message="`${c.documentJob.message||'生成中'} · ${c.documentJob.progress}%`" />
    <FeedbackNotice v-if="c.documentPreflight?.missing.length" tone="danger" :message="'生成前请补齐：'+c.documentMissingLabels" />
    <FeedbackNotice v-else-if="c.documentPreflight?.warnings.length" :message="c.documentPreflight.warnings.join('；')" />
    <FeedbackNotice v-for="notice in c.documentNotices || []" :key="notice" :message="notice" tone="warning" />
    <DataEntryPreview :url="previewUrl" :name="c.selectedReport.reportNo" :type="c.documentPdfUrl||c.coverPdfUrl?'application/pdf':'text/html'" title="完整报告" persistent hide-download hide-print>
      <template #actions>
        <button v-if="!c.documentPdfUrl" class="btn btn-light" :disabled="c.coverLoading" @click="c.previewCover()">预览报告原件</button>
        <button v-if="!c.documentPdfUrl" class="btn btn-light" :disabled="c.coverLoading" @click="c.downloadCover()">下载 Word 源稿（非签署原件）</button>
      </template>
    </DataEntryPreview>
    <DataTable v-if="c.pipelineAvailable" label="报告版本" :rows="reportVersionRows(c)" :columns="reportVersionColumns" :row-key="row=>String(row.id)" :row-label="row=>row.versionLabel">
      <template #actions="{row}">
        <button class="dropdown-item" role="menuitem" @click="c.previewDocumentVersion(row.source)">预览</button>
        <button class="dropdown-item" role="menuitem" @click="c.downloadDocumentVersion(row.source,'pdf')">下载 PDF</button>
        <button v-if="row.hasDocx" class="dropdown-item" role="menuitem" @click="c.downloadDocumentVersion(row.source,'docx')">下载 Word</button>
      </template>
    </DataTable>
    <button v-if="!c.pipelineAvailable&&c.session.canAction('report.pdf.preview')" class="btn btn-primary" @click="c.previewMerged()">预览 PDF</button>
    <button v-if="!c.pipelineAvailable&&c.session.canAction('report.pdf.download')" class="btn btn-light" @click="c.downloadMerged()">下载</button>
  </div>
  <div v-show="tab==='files'" id="report-detail-panel-files" role="tabpanel" aria-labelledby="report-detail-tab-files">
    <AttachmentFileList :files="reportFiles(c)" :can-attach="false" :busy="false" title="报告与原始记录">
      <template #metadata="{file}">{{file.source.type}} · {{file.source.source}} · {{file.source.status}}</template>
      <template #name="{file}">{{file.name}}</template>
      <template #download="{file}"><button v-if="c.session.canAction('report.pdf.download')" class="btn btn-sm btn-primary-lt" @click="c.downloadFile(file.source)">下载</button></template>
      <template #actions="{file}"><button v-if="c.session.canAction('report.pdf.preview')" class="btn btn-sm btn-primary-lt" @click="c.previewFile(file.source)">预览</button></template>
    </AttachmentFileList>
  </div>
  <div v-show="tab==='checks'" id="report-detail-panel-checks" role="tabpanel" aria-labelledby="report-detail-tab-checks">
    <FeedbackNotice v-if="c.selectedReport.outOfScope" tone="danger" :message="'超范围报告：'+(c.selectedReport.outOfScopeNote||'校验未通过仍被提交')" />
    <FeedbackNotice v-if="c.cmaScopeWarn" message="盖章含 CMA，但检测依据不在一单一库范围内，请核实授权范围。" />
    <SchemaForm :model="c" :schema="reportChecksSchema(c)" readonly />
  </div>
  <div v-show="tab==='decision'" id="report-detail-panel-decision" role="tabpanel" aria-labelledby="report-detail-tab-decision">
    <FeedbackNotice v-if="c.nextActionName&&!c.canActOnSelected" :message="`报告当前处于${c.selectedReport.status}，不在${c.pageName}节点处理范围，仅可查看。`" />
    <FeedbackNotice v-else-if="c.needsReupload" message="请上传报告正文与原始记录后再提交审核。" />
    <FeedbackNotice v-else-if="c.documentVersionBlocker" :message="c.documentVersionBlocker" />
    <SchemaForm :model="c" :schema="reportOpinionSchema(c)" :readonly="c.formReadOnly">
      <template #actions>
        <button v-if="c.nextActionName&&c.session.canAction(c.passAction)" class="btn btn-primary" :disabled="c.formReadOnly||!c.canPass" @click="c.handlePass()">{{c.nextActionName}}</button>
        <button v-if="c.nextActionName&&c.session.canAction(c.returnAction)" class="btn btn-light" :disabled="c.formReadOnly||!c.canActOnSelected" @click="c.handleReturn()">退回</button>
        <button v-if="c.undoAction&&c.session.canAction(c.undoAction)" class="btn btn-light" :disabled="c.formReadOnly||!c.canUndoSelected" @click="c.handleUndo()">{{c.undoLabel}}</button>
        <button class="btn btn-light" :disabled="c.formReadOnly||!c.canActOnSelected" @click="c.saveOpinion()">保存意见</button>
        <button v-if="c.canEditReport&&c.session.canAction('report.attachment.upload')" class="btn btn-light" :disabled="c.formReadOnly" @click="c.openUpload()">上传附件</button>
        <button v-if="c.canRequestChange&&c.session.canAction('report.change.request')" class="btn btn-light" :disabled="c.formReadOnly" @click="c.doRequestChange()">申请更改（批准后回委托重走）</button>
      </template>
    </SchemaForm>
  </div>
  <BootstrapModal :open="c.documentEditorOpen" title="编辑标准报告正文" size="xl" scrollable :busy="c.savingDocument" @close="c.documentEditorOpen=false">
    <SchemaForm :model="c.editDocument" :schema="reportDocumentSchema(c)" :readonly="c.formReadOnly">
      <template v-for="(group,i) in c.editDocument.resultGroups" :key="'group-'+i" #[`group-${i}`]>
        <button class="btn btn-light" :disabled="c.formReadOnly" @click="c.addResultItem(i)">新增工况/结果</button>
        <button class="btn btn-light" :disabled="c.formReadOnly" @click="c.editDocument.resultGroups.splice(i,1)">删除项目</button>
        <button v-for="(_,j) in group.items" :key="j" class="btn btn-light" :disabled="c.formReadOnly" @click="group.items.splice(j,1)">删除结果 {{Number(j)+1}}</button>
      </template>
      <template v-for="(_,i) in c.editDocument.photos" :key="'photo-'+i" #[`photo-${i}`]><button class="btn btn-light" :disabled="c.formReadOnly" @click="c.editDocument.photos.splice(i,1)">删除照片</button></template>
    </SchemaForm>
    <template #footer>
      <button class="btn btn-light" :disabled="c.formReadOnly" @click="c.addResultGroup()">新增项目</button>
      <button class="btn btn-light" :disabled="c.formReadOnly||c.editDocument.photos.length>=6" @click="c.addPhotoSlot()">新增照片位</button>
      <button class="btn btn-primary" :disabled="c.formReadOnly||c.savingDocument" @click="c.saveDocumentEditor()">保存正文</button>
      <button class="btn btn-light" @click="c.documentEditorOpen=false">取消</button>
    </template>
  </BootstrapModal>
</template>
