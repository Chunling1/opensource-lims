<script setup lang="ts">
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import ReportFormDisplay from '../../components/reports/ReportFormDisplay.vue'
import LoadState from '../../components/common/LoadState.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import ConfirmationModal from '../../components/common/ConfirmationModal.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import FormTabs from '../../components/forms/FormTabs.vue'
import RegistrationCommissionFields from '../../components/commissions/RegistrationCommissionFields.vue'
import RegistrationSampleFields from '../../components/commissions/RegistrationSampleFields.vue'
import RegistrationTestBasisField from '../../components/commissions/RegistrationTestBasisField.vue'
import RegistrationReportSettings from '../../components/commissions/RegistrationReportSettings.vue'
import DataEntryTrialForm from './EntryTrialForm.vue'
import OriginalRecordsWorkspace from './EntryOriginalRecords.vue'
import DataEntryReportFiles from './EntryReportFiles.vue'
import DataCheckReportPreview from '../../components/testing/DataCheckReportPreview.vue'
import RegistrationAttachmentManager from './EntryAttachments.vue'
import DataEntryRecordsModal from './EntryRecords.vue'
import DataEntryPersonPicker from '../../components/testing/DataEntryPersonPicker.vue'
import ReportCheckRejectionForm from '../../components/testing/ReportCheckRejectionForm.vue'
import { toRefs } from "vue"
const props=defineProps<{context: Record<string, any> & { reviewCheckResult?: import("../../types/commissions/contractReview").ReviewCheckResult }}>()
const {reportStage,stageConfig,stageText,route,router,detail,form,saved,layoutId,entryViewMode,previewLayout,initialTab,tab,error,busy,loading,stale,reportTab,completionError,progressError,pollFailures,pollInFlight,success,toast,discard,tabs,reportConfig,reportConfigLoading,reportConfigError,readonlyMode,editable,dirty,listRoot,returnTo,fieldErrors,sampleForm,peopleScopes,sampleOptions,pendingTemplateDownload,downloadKind,pdfUrl,previewName,previewBlob,previewKind,epoch,pollTimer,allowLeave,previewSequence,reportRequest,pendingPreview,draftKey,resultKey,uploadStatus,working,reportConfirmed,canConfirmReport,originalBusy,checkOpen,checkError,checkStep,nextAction,recipient,recipientPicking,rejection,rejectionReady,recipientScope,reviewReadConfirmed,reviewCheckResult,reviewChecking,reviewCheckError,reviewRequest,reviewController,clearReviewCheck,canCheck,canApproveCheck,openCheck,rejectCheck,approveCheck,selectRecipient,runReviewCheck,confirmCheck,attachmentOpen,recordsMode,syncAttachments,leaveDirty,selectTab,selectReportTab,beginReport,loadReportConfig,clearPreview,apply,schedulePoll,pollProgress,resumeProgress,load,notify,action,save,templateDownload,finishTemplateDownload,openPendingPreview,finalPreview,confirmReport,download,preview,uploadReportFile,changeReportLayout,remove,requestLeave,back,openReport,guard,abandon,reportOnly,checkMode,reportCheckMode,queryMode,reportQueryMode,changeMode}=toRefs(props.context)
</script>
<template>
  <PageHeading :title="reportCheckMode ? stageConfig.title : checkMode ? '数据校核' : reportOnly ? '报告填写' : readonlyMode ? '查看检测数据' : changeMode ? '检测数据更改' : '检测数据录入'" :parent-to="returnTo" />
  <LoadState :loading="loading" :error="!detail ? error : ''" :back-to="returnTo" @retry="load()" />
  <template v-if="detail && sampleForm">
    <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-3">
      <button class="btn btn-light" type="button" :disabled="props.context.navigationBusy || originalBusy" @click="back"><i class="ti ti-arrow-left me-1" aria-hidden="true"></i>{{ reportQueryMode ? '返回报告查询' : reportCheckMode ? '返回' + stageConfig.title : changeMode ? '返回检测数据更改' : queryMode ? '返回检测数据查询' : checkMode ? '返回检测数据校核' : '返回检测数据录入' }}</button>
      <ReportFormDisplay v-if="reportCheckMode" :sample="detail.sample" />
      <button v-if="props.context.canAdminEdit" type="button" class="btn btn-outline-primary ms-auto" :aria-pressed="!!props.context.adminEditing" :disabled="working || loading || originalBusy" @click="props.context.toggleAdminEditing()"><i class="ti ti-edit me-1" aria-hidden="true"></i>{{ props.context.adminEditing ? '退出管理员编辑' : '管理员编辑' }}</button>
      <button v-if="!reportOnly && !previewLayout && !queryMode" class="btn btn-light ms-auto" type="button" :disabled="working || loading || originalBusy || !detail.capabilities.canView" @click="openReport">报告填写<i class="ti ti-arrow-right ms-1" aria-hidden="true"></i></button>
    </div>
    <div v-if="props.context.adminEditing" class="alert alert-warning" role="status">管理员编辑已开启，保存检测数据时需填写修订说明并记录修改前后内容。</div>
    <div v-if="error" class="mb-3"><ErrorNotice :error="error" /><button v-if="stale || ['NETWORK', 'UNAVAILABLE'].includes(error.code)" type="button" class="btn btn-light" :disabled="working || loading" @click="load(true)">刷新核对</button></div>

    <div v-for="notice in props.context.previewState?.notices || []" :key="notice" class="alert alert-warning" role="status">{{ notice }}</div>
    <form :aria-label="reportOnly ? '报告填写表单' : '检测数据录入表单'" novalidate @submit.prevent="save()">
    <fieldset :disabled="!reportOnly && (working || loading)" :aria-busy="working || loading">
    <template v-if="!reportOnly">
    <section class="card" aria-label="检测设置">
      <div class="card-body"><div class="row g-3">
        <div class="col-md-6">
          <label for="sample-testPlan" class="form-label">检测方案</label>
          <div class="input-group"><input id="sample-testPlan" :value="sampleForm.details.testPlanCode ? `${sampleForm.details.testPlan}（${sampleForm.details.testPlanCode}）` : sampleForm.details.testPlan" class="form-control bg-body-tertiary" readonly placeholder="请选择检测方案" /></div>
        </div>
        <div class="col-md-6">
          <RegistrationTestBasisField readonly :text-value="sampleForm.details.testBasis" :plan-id="sampleForm.details.testPlanId" :ids="sampleForm.details.testBasisIds" :separators="sampleForm.details.testBasisSeparators" :english-book-marks="sampleForm.details.englishBookMarks" />
        </div>
      </div></div>
    </section>
    <FormTabs :model-value="tab" @update:model-value="selectTab" :tabs="tabs" label="检测数据录入页签" />
    <div v-for="item in tabs" v-show="tab === item.key" :id="item.panelId" :key="item.key" role="tabpanel" :aria-labelledby="item.tabId">
      <RegistrationCommissionFields v-if="item.key === 'order' && tab === 'order'" :form="detail.sample.commissionInfo" :code="detail.sample.commissionInfo.code" :owner="detail.sample.commissionInfo.owner" sample readonly />
      <RegistrationSampleFields v-if="item.key === 'sample' && tab === 'sample'" :form="sampleForm" :options="sampleOptions" :code="detail.sample.code" :report-code="detail.sample.reportCode" :commission-code="detail.sample.commissionInfo.code" :projects="detail.sample.projects" readonly><template #report-settings><RegistrationReportSettings readonly :model-value="sampleForm.details.reportSettings" :config="reportConfig" :loading="reportConfigLoading" :error="reportConfigError" @retry="loadReportConfig" /></template></RegistrationSampleFields>
      <fieldset v-if="item.key === 'trial' && tab === 'trial'" :disabled="working || loading"><DataEntryTrialForm :form="form" :detail="detail" :readonly="!editable" :errors="fieldErrors" :people-scopes="peopleScopes" @equipment-config="apply($event)" @people-scope="peopleScopes[$event.role] = $event.scope" /></fieldset>
      <OriginalRecordsWorkspace v-if="item.key === 'original'" :sample-id="detail.sample.id" :active="tab === 'original'" :readonly="readonlyMode || stale" :preview-only="previewLayout || queryMode" @busy="originalBusy = $event" />
      <DataCheckReportPreview v-if="previewLayout && item.key === 'report-preview'" :detail="detail" :active="tab === 'report-preview'" @refresh="load()" />
    </div>
    </template>
      <DataEntryReportFiles :navigation-busy="!!props.context.navigationBusy || originalBusy" :confirming="!!props.context.confirming" :can-preserve-uploaded-report="props.context.canPreserveUploadedReport" :preserve-uploaded-report="props.context.preserveUploadedReport" :preserve-option-unavailable="props.context.preserveOptionUnavailable" @toggle-preserve-uploaded-report="props.context.togglePreserveUploadedReport()" :removal-error="error" v-else v-model:layout-id="layoutId" :detail="detail" :active-tab="reportTab" :can-confirm="canConfirmReport" :confirmed="reportConfirmed" :completion-error="completionError" :progress-error="progressError" @refresh-progress="pollProgress" @confirm="confirmReport" @back="back" @begin="beginReport" @select-tab="selectReportTab" :busy="working || loading" :readonly="!editable" :dirty="dirty" :preview-url="pdfUrl" :preview-name="previewName" :preview-blob="previewBlob" :layout-error="fieldErrors.layoutId" @change-layout="changeReportLayout" :upload="uploadReportFile" @remove="remove" @sort="action('sort', { ids: $event })" @download="download(`files/${encodeURIComponent($event.id)}`, $event.name)" @download-template="templateDownload()" @download-complete-report="templateDownload('complete-report')" :template-downloading="!!pendingTemplateDownload && downloadKind === 'template'" :complete-report-downloading="!!pendingTemplateDownload && downloadKind === 'complete-report'" @final-preview="finalPreview">
        <template #upload-status><FeedbackNotice v-if="uploadStatus.leaveAttempted.value" message="文件正在上传，请等待完成后再离开。" /></template>
      </DataEntryReportFiles>

    </fieldset>
    <div class="d-flex align-items-center justify-content-end flex-wrap gap-2 mb-4 pe-5">
      <div class="d-flex flex-wrap gap-2 me-auto">
        <button class="btn btn-light" type="button" :disabled="working || loading || originalBusy" @click="attachmentOpen = true"><i class="ti ti-paperclip me-1" aria-hidden="true"></i>{{ previewLayout || queryMode ? '查看附件' : '附件管理' }}</button>
        <button class="btn btn-light" type="button" :disabled="true" :title="'现平台通过委托更改、报告查询查看流程记录'" @click="recordsMode = 'changes'"><i class="ti ti-history me-1" aria-hidden="true"></i>查看修改记录</button>
        <button class="btn btn-light" type="button" :disabled="true" :title="'现平台通过委托更改、报告查询查看问题记录'" @click="recordsMode = 'issues'"><i class="ti ti-help me-1" aria-hidden="true"></i>查看问题记录</button>
      </div>
      <span class="spinner-border spinner-border-sm text-primary" :class="{ invisible: !working }" role="status" aria-label="正在处理" :aria-hidden="!working"></span>
      <button class="btn btn-light" type="button" :disabled="props.context.navigationBusy || originalBusy" @click="back">返回</button>
      <button v-if="!reportOnly && !readonlyMode && detail.capabilities.canEdit" type="submit" class="btn btn-primary" :disabled="working || loading || stale || originalBusy">保存</button>
      <button v-if="props.context.canCompleteChange" type="button" class="btn btn-primary" :disabled="working || loading || stale || originalBusy" @click="props.context.completeChange()">完成更改并提交审核</button>
      <button v-if="checkMode && !reportOnly" type="button" class="btn btn-primary" :disabled="!canCheck" @click="openCheck">{{ reportCheckMode ? stageConfig.label : '校核' }}</button>
    </div>
    </form>
    <BootstrapModal v-if="checkOpen && !recipientPicking" open :title="checkStep === 'reject' ? '问题处理' : checkStep === 'next' ? '确认下一步' : reportCheckMode ? stageConfig.title : '数据校核'" :size="reportCheckMode && checkStep !== 'next' ? 'lg' : undefined" scrollable :busy="working" @close="!working && (checkOpen = false)">
      <p class="text-break"><strong>{{ detail.sample.code }}</strong> · {{ detail.sample.name }}</p>
      <template v-if="checkStep === 'next'">
        <fieldset :disabled="working" class="mb-3">
          <legend class="visually-hidden">下一步</legend>
          <div class="d-flex flex-wrap gap-4">
            <div class="form-check"><input id="report-next-transfer" v-model="nextAction" class="form-check-input" type="radio" name="report-next-action" value="transfer" /><label class="form-check-label" for="report-next-transfer">转交{{ stageConfig.label }}</label></div>
            <div class="form-check"><input id="report-next-submit" v-model="nextAction" class="form-check-input" type="radio" name="report-next-action" value="next" /><label class="form-check-label" for="report-next-submit">下一步</label></div>
          </div>
        </fieldset>
        <label for="report-next-recipient" class="form-label">接收人<span v-if="nextAction === 'transfer'" class="text-danger ms-1">*</span></label>
        <div class="input-group">
          <input id="report-next-recipient" class="form-control" readonly :disabled="working || nextAction !== 'transfer'" :value="nextAction === 'transfer' && recipient ? `${recipient.name}（${recipient.id}）` : ''" placeholder="请选择接收人" />
          <button type="button" class="btn btn-light" aria-label="选择接收人" :disabled="working || nextAction !== 'transfer'" @click="recipientPicking = true"><i class="ti ti-search" aria-hidden="true"></i></button>
          <button type="button" class="btn btn-light" aria-label="清除接收人" :disabled="working || nextAction !== 'transfer' || !recipient" @click="recipient = undefined"><i class="ti ti-x" aria-hidden="true"></i></button>
        </div>
      </template>
      <ReportCheckRejectionForm v-else-if="checkStep === 'reject'" :form="rejection" :busy="working" :errors="checkError ? checkError.fieldErrors || {} : {}" />
      <template v-else>
      <p>{{ reportCheckMode ? stageText('请选择校核结果。不通过时需填写问题处理信息。') : '请选择校核结果。不通过将退回检测数据录入。' }}</p>
      <section v-if="reportCheckMode" class="card border shadow-none mb-0" aria-labelledby="report-review-check-title" :aria-busy="reviewChecking">
        <div class="card-header bg-light py-2 px-3 d-flex align-items-center justify-content-between flex-wrap gap-2">
          <h6 id="report-review-check-title" class="card-title mb-0 fs-5">{{ stageText('合规校核') }}</h6>
          <button type="button" class="btn btn-sm btn-outline-primary d-inline-flex align-items-center gap-1 my-n2" :disabled="!canCheck" @click="runReviewCheck"><span v-if="reviewChecking" class="spinner-border spinner-border-sm flex-shrink-0" aria-hidden="true"></span><i v-else class="ti ti-shield-check lh-1" aria-hidden="true"></i><span>{{ reviewChecking ? '校验中…' : '校验' }}</span></button>
        </div>
        <div class="card-body p-3" role="region" :aria-label="stageText('合规校核结果')">
          <ErrorNotice :error="reviewCheckError" :retry="!stale" :busy="reviewChecking || working" @retry="runReviewCheck" />
          <FeedbackNotice v-if="stale" message="样品信息或可用状态已发生变化，请刷新样品后重新校验、确认。"><p class="mb-2">样品信息或可用状态已发生变化，请刷新样品后重新校验、确认。</p><button type="button" class="btn btn-sm btn-outline-primary" :disabled="working || loading" @click="load()">刷新样品</button></FeedbackNotice>
          <div v-else-if="reviewChecking" class="alert alert-info alert-border-left mb-2" role="status">{{ stageText('正在获取最新校核结果，请稍候…') }}</div>
          <template v-else-if="reviewCheckResult">
            <div class="alert alert-border-left mb-2" :class="reviewCheckResult.messages.some(message => message.tone === 'warning') ? 'alert-warning' : 'alert-info'">
              <ul class="list-unstyled mb-0"><li v-for="(message, index) in reviewCheckResult.messages" :key="index" class="d-flex gap-2" :class="{ 'mt-2': index > 0 }"><i class="flex-shrink-0" :class="message.tone === 'warning' ? 'ti ti-alert-triangle' : 'ti ti-info-circle'" aria-hidden="true"></i><span class="text-break">{{ message.text }}</span></li></ul>
            </div>
            <p class="text-muted small mb-0">{{ stageConfig.label }}时间：{{ new Date(reviewCheckResult.checkedAt).toLocaleString('zh-CN') }}</p>
          </template>
          <p v-else-if="!reviewCheckError" class="text-muted mb-0">{{ stageText('请先进行合规校核，阅读结果后再确认通过。') }}</p>
        </div>
      </section>
      </template>
      <ErrorNotice :error="checkError" />
      <template v-if="reportCheckMode && checkStep === 'check'" #pagination>
        <div class="px-3 py-2 border-top"><div class="form-check"><input id="report-review-confirmed" v-model="reviewReadConfirmed" type="checkbox" class="form-check-input" :disabled="!reviewCheckResult || !canCheck" /><label for="report-review-confirmed" class="form-check-label">{{ stageText('我已阅读并确认上述校核结果') }}</label></div></div>
      </template>
      <template #footer>
        <template v-if="checkStep === 'reject'">
          <button type="button" class="btn btn-light" :disabled="working" @click="checkStep = 'check'; checkError = ''">取消</button>
          <button type="button" class="btn btn-primary" :disabled="!canCheck || !rejectionReady" @click="confirmCheck('reject')">确定</button>
        </template>
        <template v-else-if="checkStep === 'next'">
          <button type="button" class="btn btn-light" :disabled="working" @click="checkStep = 'check'">返回</button>
          <button type="button" class="btn btn-primary" :disabled="!canApproveCheck || nextAction === 'transfer' && !recipient" @click="confirmCheck('check')">确定</button>
        </template>
        <template v-else>
        <button type="button" class="btn btn-light" :disabled="working" @click="checkOpen = false">取消</button>
        <button type="button" class="btn btn-outline-danger" :disabled="!canCheck" @click="rejectCheck">不通过</button>
        <button type="button" class="btn btn-primary" :disabled="!canApproveCheck" @click="approveCheck">通过</button>
        </template>
      </template>
    </BootstrapModal>
    <DataEntryPersonPicker v-if="recipientPicking && checkOpen" :sample-id="detail.sample.id" :role="stageConfig.role" :report-stage="reportStage" purpose="report-check" title="选择接收人" :value="recipient" :initial-scope="recipientScope" @scope="recipientScope = $event" @select="selectRecipient" @close="recipientPicking = false" />
    <RegistrationAttachmentManager :id="attachmentOpen ? detail.sample.id : undefined" kind="samples" :title="previewLayout || queryMode ? '查看附件' : '附件管理'" :readonly="readonlyMode || stale" @close="attachmentOpen = false" @changed="syncAttachments" />
    <DataEntryRecordsModal :sample-id="detail.sample.id" :mode="recordsMode" @close="recordsMode = undefined" />
  </template>
  <TemplateToast ref="toast" :message="success" tone="success" />
  <ConfirmationModal v-if="discard" title="放弃填写" :busy="props.context.navigationBusy || originalBusy" @close="discard = ''">
    <p class="mb-0">尚有未保存的修改，是否放弃填写？</p>
    <template #footer><button type="button" class="btn btn-light" :disabled="props.context.navigationBusy || originalBusy" @click="discard = ''">继续填写</button><button type="button" class="btn btn-danger" :disabled="props.context.navigationBusy || originalBusy" @click="abandon">放弃填写</button></template>
  </ConfirmationModal>
</template>
