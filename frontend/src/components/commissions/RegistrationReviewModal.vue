<script setup lang="ts">
import FeedbackNotice from '../common/FeedbackNotice.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { emptyContractReview, reviewCheckOptions, reviewRequirements, reviewAuthorizations } from '../../types/commissions/contractReview'
import type { ReviewCheckResult } from '../../types/commissions/contractReview'
import type { RegistrationSample } from '../../types/commissions/registration'
import { currentActor } from '../../stores/session'
const props = defineProps<{ record?: RegistrationSample; records?: RegistrationSample[] }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const form = reactive(emptyContractReview()), busy = ref(false), error = ref<ErrorValue>('')
const checking = ref(false), refreshing = ref(false), checkError = ref<ErrorValue>(''), checkResult = ref<ReviewCheckResult>(), readConfirmed = ref(false), stale = ref(false), version = ref(0)
const batchRecords = ref<RegistrationSample[]>([]), batchResults = ref<ReviewCheckResult[]>([])
const isBatch = computed(() => !!props.records?.length)
const results = computed(() => isBatch.value ? batchResults.value : checkResult.value ? [checkResult.value] : [])
const hasResults = computed(() => isBatch.value ? batchRecords.value.length > 0 && results.value.length === batchRecords.value.length : !!checkResult.value)
const canApprove = computed(() => reviewRequirements.every(({ key }) => form[key]) && hasResults.value && readConfirmed.value && !stale.value)
const targets = () => batchRecords.value.map(({ id, version }) => ({ id, version }))
const sampleCaption = (id: string) => { const record = batchRecords.value.find(sample => sample.id === id); return record ? `${record.code} · ${record.name}` : id }
// Compact or short viewports use one body scrollbar instead of nested scrolling.
const separateResultsScroll = ref(false)
let resultsMedia: MediaQueryList | undefined
function updateResultsLayout() { separateResultsScroll.value = resultsMedia?.matches ?? false }
onMounted(() => {
  resultsMedia = window.matchMedia('(min-width: 992px) and (min-height: 700px)')
  updateResultsLayout()
  resultsMedia.addEventListener('change', updateResultsLayout)
})
onBeforeUnmount(() => resultsMedia?.removeEventListener('change', updateResultsLayout))
const currentOptions = computed(() => JSON.stringify(reviewCheckOptions(form)))
// Also invalidate proof on programmatic changes, not only changes through the controls.
watch(currentOptions, () => { if (checking.value || hasResults.value) clearCheck() }, { flush: 'sync' })
let epoch = 0, checkRequest = 0, controller: AbortController | undefined
function clearCheck() { checkRequest++; controller?.abort(); checking.value = false; checkResult.value = undefined; batchResults.value = []; readConfirmed.value = false }
watch(() => [props.record, props.records] as const, ([record, records]) => {
  epoch++; clearCheck(); busy.value = false; refreshing.value = false; error.value = ''; checkError.value = ''; stale.value = false; version.value = record?.version ?? 0
  Object.assign(form, emptyContractReview(), record?.contractReview)
  batchRecords.value = records ? records.map(sample => ({ ...sample })) : []
}, { immediate: true })
function cancel() { if (busy.value) return; epoch++; clearCheck(); emit('close') }
watch(currentActor, () => { epoch++; clearCheck(); emit('close') })
onBeforeUnmount(() => { epoch++; clearCheck() })
function captureFailure(e: unknown) {
  const issue = normalizeError(e)
  return issue
}
async function check() {
  if ((!props.record && !isBatch.value) || busy.value || checking.value || refreshing.value || stale.value) return
  clearCheck(); checkError.value = ''; error.value = ''; checking.value = true
  const token = epoch, request = checkRequest, abort = controller = new AbortController()
  try {
    const batch = isBatch.value
    const response = batch ? await registrationDemo.batchReviewCheck(targets(), reviewCheckOptions(form), abort.signal) : undefined
    const received = batch ? response?.items : [await registrationDemo.reviewCheck(props.record!.id, version.value, reviewCheckOptions(form), abort.signal)]
    if (token !== epoch || request !== checkRequest) return
    const expected = batch ? targets() : [{ id: props.record!.id, version: version.value }]
    if (!Array.isArray(received) || received.length !== expected.length || new Set(received.map(result => result?.sampleId)).size !== expected.length || received.some(result => !result?.id || !expected.some(sample => sample.id === result.sampleId) || !Number.isFinite(Date.parse(result.checkedAt)) || !Array.isArray(result.messages) || !result.messages.length || result.messages.some(item => !item || !['info', 'warning'].includes(item.tone) || typeof item.text !== 'string'))) throw new AppError('UNAVAILABLE', '校核结果格式有误，请重试。')
    if (batch) batchResults.value = received
    else checkResult.value = received[0]
  } catch (e) { if (token === epoch && request === checkRequest && !abort.signal.aborted) checkError.value = captureFailure(e) }
  finally { if (token === epoch && request === checkRequest) checking.value = false }
}
async function refreshSample() {
  if ((!props.record && !isBatch.value) || busy.value || refreshing.value) return
  const token = epoch; clearCheck(); refreshing.value = true
  try {
    if (isBatch.value) {
      const latest = await registrationDemo.batchReviewContext(batchRecords.value.map(sample => sample.id))
      if (token !== epoch) return
      batchRecords.value = latest; stale.value = false; error.value = ''; checkError.value = ''
      return
    }
    const latest = await registrationDemo.sample(props.record!.id)
    if (token !== epoch) return
    if (latest.status !== 'completed' || latest.reviewStatus !== 'reviewed') throw new AppError('BUSINESS_RULE', '样品已不在评审中，请关闭对话框并刷新列表。')
    version.value = latest.version; stale.value = false; error.value = ''; checkError.value = ''
  } catch (e) { if (token === epoch) checkError.value = normalizeError(e) }
  finally { if (token === epoch) refreshing.value = false }
}
async function submit(event: Event) {
  const decision = ((event as SubmitEvent).submitter as HTMLButtonElement | null)?.value
  if ((!props.record && !isBatch.value) || busy.value || checking.value || refreshing.value || stale.value || (decision !== 'approved' && decision !== 'rejected') || (decision === 'approved' && !canApprove.value)) return
  const token = epoch; busy.value = true; error.value = ''
  try {
    if (isBatch.value) await registrationDemo.submitBatchReview({ targets: targets(), review: { ...form, decision, otherText: form.other ? form.otherText : '', readConfirmed: readConfirmed.value }, checks: batchResults.value.map(result => ({ sampleId: result.sampleId, checkId: result.id })) })
    else await registrationDemo.act('samples', props.record!.id, 'review', version.value, '', { ...form, decision, otherText: form.other ? form.otherText : '', ...(checkResult.value ? { checkId: checkResult.value.id, readConfirmed: readConfirmed.value } : {}) })
    if (token === epoch) { emit('saved'); emit('close') }
  } catch (e) {
    if (token === epoch) {
      error.value = captureFailure(e)
      if (error.value.code === 'VALIDATION' && decision === 'approved') clearCheck()
    }
  }
  finally { if (token === epoch) busy.value = false }
}
</script>
<template>
  <BootstrapModal :open="!!record || isBatch" title="合同评审" size="lg" scrollable :body-class="separateResultsScroll ? 'd-flex flex-column overflow-hidden' : undefined" :busy="busy" @close="cancel">
    <div v-if="error" class="flex-shrink-0"><ErrorNotice :error="error" /></div>
    <p v-if="isBatch" class="text-muted flex-shrink-0">已选择 {{ batchRecords.length }} 个样品，以下评审选项及评审决定将应用于全部所选样品。</p>
    <form id="contract-review-form" :class="separateResultsScroll ? 'd-flex flex-column overflow-hidden' : undefined" @submit.prevent="submit">
      <fieldset :disabled="busy || refreshing" class="card border shadow-none mb-3 flex-shrink-0" aria-labelledby="review-requirements-title">
        <div class="card-header bg-light py-2 px-3"><h6 id="review-requirements-title" class="card-title mb-0 fs-5">是否满足要求</h6></div>
        <div class="card-body p-3">
        <div class="row gx-3 gy-2"><div v-for="field in reviewRequirements" :key="field.key" class="col-6 col-md-auto"><div class="form-check"><input :id="`review-${field.key}`" v-model="form[field.key]" class="form-check-input" type="checkbox" /><label class="form-check-label" :for="`review-${field.key}`">{{ field.label }}</label></div></div></div>
        </div>
      </fieldset>
      <fieldset :disabled="busy || refreshing" class="card border shadow-none mb-3 flex-shrink-0" aria-labelledby="review-remarks-title">
        <div class="card-header bg-light py-2 px-3"><h6 id="review-remarks-title" class="card-title mb-0 fs-5">备注</h6></div>
        <div class="card-body p-3">
        <div class="row gx-3 gy-2 align-items-center"><div v-for="field in reviewAuthorizations" :key="field.key" class="col-6 col-md-auto"><div class="form-check"><input :id="`review-${field.key}`" v-model="form[field.key]" class="form-check-input" type="checkbox" /><label class="form-check-label" :for="`review-${field.key}`">{{ field.label }}</label></div></div><div class="col-12 col-md"><label for="review-other-text" class="visually-hidden">其他说明</label><input id="review-other-text" v-model="form.otherText" class="form-control form-control-sm" placeholder="其他说明" maxlength="500" :disabled="!form.other" /></div></div>
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
    </form>
    <template #pagination>
      <div class="px-3 py-2 border-top">
          <div class="form-check"><input id="review-read-confirmed" v-model="readConfirmed" class="form-check-input" type="checkbox" :disabled="!hasResults || checking || busy || refreshing || stale" /><label for="review-read-confirmed" class="form-check-label">{{ isBatch ? '我已阅读并确认全部样品的校核结果' : '我已阅读并确认上述校核结果' }}</label></div>
      </div>
    </template>
    <template #footer>
      <button class="btn btn-light" type="button" :disabled="busy" @click="cancel">取消</button>
      <button class="btn btn-outline-danger" type="submit" form="contract-review-form" value="rejected" :disabled="busy || checking || refreshing || stale">不通过</button>
      <button class="btn btn-primary" type="submit" form="contract-review-form" value="approved" :disabled="busy || checking || refreshing || !canApprove" :title="!canApprove ? '请勾选所有要求，并完成合规校核及阅读确认' : undefined">通过</button>
    </template>
  </BootstrapModal>
</template>
