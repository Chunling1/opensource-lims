<script setup lang="ts">
import {toRefs} from 'vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import ContractRejectionAction from './ContractRejectionAction.vue'
import {reviewRequirements,reviewAuthorizations} from '../../types/commissions/contractReview'
import {createContractReviewPresentation} from './contractReviewPresentation'
const props=defineProps<{context:any}>()
const state=createContractReviewPresentation(props.context)
const {standardResolution,resolveStandards,form,record,busy,refreshing,checking,readConfirmed,checkError,error,hasResults,canApprove,results,requiresOpinion,complianceSchema,opinion,check,cancel,submit,reject,rejectionOpen,refreshSample,separateResultsScroll,isBatch,batchRecords,stale,sampleCaption,canReturn}=toRefs(state)
</script>
<template>
  <BootstrapModal :open="!!record || isBatch" title="合同评审" size="lg" scrollable :body-class="separateResultsScroll ? 'd-flex flex-column overflow-hidden' : undefined" :busy="busy" @close="cancel">
    <div v-if="error" class="flex-shrink-0"><ErrorNotice :error="error" /></div>
    <p v-if="isBatch" class="text-muted flex-shrink-0">已选择 {{ batchRecords.length }} 个样品，以下评审选项及评审决定将应用于全部所选样品。</p>
    <form id="contract-review-form" :class="separateResultsScroll ? 'd-flex flex-column overflow-hidden' : undefined" @submit.prevent="submit">
      <fieldset :disabled="busy || refreshing" class="card border shadow-none mb-3 flex-shrink-0" aria-labelledby="review-requirements-title">
        <div class="card-header bg-light py-2 px-3"><h6 id="review-requirements-title" class="card-title mb-0 fs-5">是否满足要求</h6></div>
        <div class="card-body p-3">
        <div class="row gx-3 gy-2"><div v-for="field in reviewRequirements" :key="field.key" class="col-6 col-md-auto"><div class="form-check"><input :id="`review-${field.key}`" v-model="form[field.key]" :disabled="false" class="form-check-input" type="checkbox" /><label class="form-check-label" :for="`review-${field.key}`">{{ field.label }}</label></div></div></div>
        </div>
      </fieldset>
      <fieldset :disabled="busy || refreshing" class="card border shadow-none mb-3 flex-shrink-0" aria-labelledby="review-remarks-title">
        <div class="card-header bg-light py-2 px-3"><h6 id="review-remarks-title" class="card-title mb-0 fs-5">备注</h6></div>
        <div class="card-body p-3">
        <div class="row gx-3 gy-2 align-items-center"><div v-for="field in reviewAuthorizations" :key="field.key" class="col-6 col-md-auto"><div class="form-check"><input :id="`review-${field.key}`" v-model="form[field.key]" :disabled="field.key === 'other'" class="form-check-input" type="checkbox" /><label class="form-check-label" :for="`review-${field.key}`">{{ field.label }}</label></div></div><div class="col-12 col-md"><label for="review-other-text" class="visually-hidden">其他说明</label><input id="review-other-text" v-model="form.otherText" class="form-control form-control-sm" placeholder="其他说明" maxlength="500" :disabled="true" /></div></div>
        </div>
      </fieldset>
      <section class="card border shadow-none mb-0" :class="{ 'overflow-hidden': separateResultsScroll }" aria-labelledby="review-check-title" :aria-busy="checking || refreshing">
        <div class="card-header bg-light py-2 px-3 flex-shrink-0 d-flex align-items-center justify-content-between flex-wrap gap-2">
          <h6 id="review-check-title" class="card-title mb-0 fs-5">合规校核</h6>
          <button type="button" class="btn btn-sm btn-outline-primary d-inline-flex align-items-center gap-1 my-n2" :disabled="busy || checking || refreshing || stale" @click="check"><span v-if="checking" class="spinner-border spinner-border-sm flex-shrink-0" aria-hidden="true"></span><i v-else class="ti ti-shield-check lh-1" aria-hidden="true"></i><span>{{ checking ? '校验中…' : '校验' }}</span></button>
        </div>
        <div id="review-check-results" class="card-body p-3" :class="{ 'overflow-auto': separateResultsScroll }" role="region" aria-label="合规校核结果" :tabindex="separateResultsScroll ? 0 : undefined">
          <ErrorNotice :error="checkError" :retry="!stale" :busy="checking || busy || refreshing" @retry="check" />
          <FeedbackNotice v-if="stale" message="样品信息已发生变化，请刷新样品后重新校核、确认。"><p class="mb-2">样品信息已发生变化，请刷新样品后重新校核、确认。当前评审选项已保留。</p><button class="btn btn-sm btn-outline-primary" type="button" :disabled="busy || refreshing" @click="refreshSample">{{ refreshing ? '正在刷新…' : '刷新样品' }}</button></FeedbackNotice>
          <div v-else-if="checking" class="alert alert-info alert-border-left mb-2" role="status">正在获取最新校核结果，请稍候…</div>
          <template v-else-if="hasResults">
          <section v-for="(checkResult, index) in results" :key="checkResult.sampleId" :class="{ 'mt-3 pt-3 border-top': index > 0 }" :aria-label="isBatch ? sampleCaption(checkResult.sampleId) : undefined">
            <h6 v-if="isBatch" class="fs-5 text-break">{{ sampleCaption(checkResult.sampleId) }}</h6>
            <div class="alert alert-border-left mb-2" :class="checkResult.messages.some(item => item.tone === 'warning') ? 'alert-warning' : 'alert-info'" role="status">
              <ul class="list-unstyled mb-0"><li v-for="(message, index) in checkResult.messages" :key="index" class="d-flex gap-2" :class="{ 'mt-2': index > 0 }"><i class="flex-shrink-0" :class="message.tone === 'warning' ? 'ti ti-alert-triangle' : 'ti ti-info-circle'" aria-hidden="true"></i><span class="text-break">{{ message.text }}</span></li></ul>
            </div>
            <p class="text-muted small mb-0">校核时间：{{ new Date(checkResult.checkedAt).toLocaleString('zh-CN') }}</p>
          </section>
          </template>
          <template v-else-if="!checkError"><p class="text-muted mb-0">请先进行合规校核，阅读结果后再确认通过。</p><ul v-if="isBatch" class="list-unstyled mt-3 mb-0"><li v-for="sample in batchRecords" :key="sample.id" class="text-break py-1">{{ sample.code }} · {{ sample.name }}</li></ul></template>

        </div>
      </section>
      <SchemaForm v-if="standardResolution.needed" :schema="standardResolution.schema" :model="standardResolution.selected" :readonly="standardResolution.busy" /><button v-if="standardResolution.needed" type="button" class="btn btn-outline-primary" :disabled="standardResolution.busy" @click="resolveStandards">确认标准关联并重新校核</button>
      <SchemaForm v-if="requiresOpinion" :schema="complianceSchema" :model="opinion" :readonly="busy || refreshing" />
    </form>
    <template #pagination>
      <div class="px-3 py-2 border-top">
          <div class="form-check"><input id="review-read-confirmed" v-model="readConfirmed" class="form-check-input" type="checkbox" :disabled="!hasResults || checking || busy || refreshing || stale" /><label for="review-read-confirmed" class="form-check-label">{{ isBatch ? '我已阅读并确认全部样品的校核结果' : '我已阅读并确认上述校核结果' }}</label></div>
      </div>
    </template>
    <template #footer>
      <button class="btn btn-light" type="button" :disabled="busy" @click="cancel">取消</button>
      <button class="btn btn-outline-danger" type="submit" form="contract-review-form" value="rejected" :disabled="busy || checking || refreshing || stale || !canReturn">不通过</button>
      <button class="btn btn-primary" type="submit" form="contract-review-form" value="approved" :disabled="busy || checking || refreshing || !canApprove" :title="!canApprove ? '请勾选所有要求，并完成合规校核及阅读确认' : undefined">通过</button>
    </template>
  </BootstrapModal>
  <ContractRejectionAction v-if="rejectionOpen" :record="record" :submit-reason="reject" @close="rejectionOpen = false" />
</template>
