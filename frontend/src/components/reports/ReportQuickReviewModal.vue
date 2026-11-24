<script setup lang="ts">
import FeedbackNotice from '../common/FeedbackNotice.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ConfirmationModal from '../common/ConfirmationModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import DataEntryPersonPicker from '../testing/DataEntryPersonPicker.vue'
import ReportCheckRejectionForm from '../testing/ReportCheckRejectionForm.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { reportStages, emptyReportCheckRejection, type ReportStage, type ReportCheckNextAction } from '../../types/reports/reportCheck'
import type { RegistrationSample } from '../../types/commissions/registration'
import type { ReviewCheckResult } from '../../types/commissions/contractReview'
import type { EntryPerson, EntryPeopleScope } from '../../types/testing/dataEntryDetail'
import { currentActor } from '../../stores/session'

const props = defineProps<{ ids: string[]; stage: ReportStage }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const config = computed(() => reportStages[props.stage])
const samples = ref<RegistrationSample[]>([]), results = ref<ReviewCheckResult[]>([])
const loading = ref(false), checking = ref(false), busy = ref(false), stale = ref(false)
const error = ref<ErrorValue>(''), readConfirmed = ref(false)
const step = ref<'check' | 'next' | 'reject'>('check'), nextAction = ref<ReportCheckNextAction>('next')
const recipient = ref<EntryPerson>(), picking = ref(false), recipientScope = ref<EntryPeopleScope>('all')
const rejection = ref(emptyReportCheckRejection())
const working = computed(() => busy.value || loading.value || checking.value)
const ready = computed(() => samples.value.length === props.ids.length && samples.value.length > 0 && !working.value && !stale.value)
const verified = computed(() => results.value.length === samples.value.length && results.value.length > 0)
const canPass = computed(() => ready.value && verified.value && readConfirmed.value)
const targets = () => samples.value.map(({ id, version }) => ({ id, version }))
const caption = (id: string) => { const sample = samples.value.find(sample => sample.id === id); return sample ? `${sample.code} · ${sample.name}` : id }
let sequence = 0, controller: AbortController | undefined
function clearProof() { results.value = []; readConfirmed.value = false; step.value = 'check'; picking.value = false }
function invalidate() { sequence++; controller?.abort(); checking.value = false; loading.value = false; clearProof() }
function closeDecision() { if (!working.value) { step.value = 'check'; error.value = '' } }
function close() { if (busy.value) return; if (step.value !== 'check') { closeDecision(); return }; invalidate(); emit('close') }
function failure(issue: unknown) {
  error.value = normalizeError(issue)
  if (['BUSINESS_RULE', 'FORBIDDEN', 'NOT_FOUND'].includes(error.value.code)) { stale.value = true; clearProof() }
  return error.value
}
async function load() {
  if (busy.value) return
  invalidate(); const token = sequence, abort = controller = new AbortController()
  loading.value = true; error.value = ''
  try {
    const records = await registrationDemo.reportBatchContext([...props.ids], props.stage, abort.signal)
    if (token !== sequence) return
    if (!Array.isArray(records) || records.length !== props.ids.length || new Set(records.map(sample => sample.id)).size !== props.ids.length || records.some(sample => !props.ids.includes(sample.id))) throw new AppError('UNAVAILABLE', '样品列表不完整，请重试。')
    samples.value = records; stale.value = false
  } catch (issue) { if (token === sequence && !abort.signal.aborted) failure(issue) }
  finally { if (token === sequence) loading.value = false }
}
async function check() {
  if (!ready.value) return
  invalidate(); const token = sequence, abort = controller = new AbortController(), expected = targets()
  checking.value = true; error.value = ''
  try {
    const response = await registrationDemo.reportBatchCheck(expected, props.stage, abort.signal)
    if (token !== sequence) return
    const received = response.items
    if (!Array.isArray(received) || received.length !== expected.length || new Set(received.map(item => item?.sampleId)).size !== expected.length || received.some(item => !item?.id || !expected.some(sample => sample.id === item.sampleId) || !Number.isFinite(Date.parse(item.checkedAt)) || !Array.isArray(item.messages) || !item.messages.length || item.messages.some(message => !message || !['info', 'warning'].includes(message.tone) || typeof message.text !== 'string'))) throw new AppError('UNAVAILABLE', '核验结果不完整或格式有误，请重新校验。')
    results.value = received
  } catch (issue) { if (token === sequence && !abort.signal.aborted) failure(issue) }
  finally { if (token === sequence) checking.value = false }
}
async function submit(action: 'check' | 'reject') {
  if (!ready.value || action === 'check' && (!canPass.value || step.value !== 'next' || nextAction.value === 'transfer' && !recipient.value) || action === 'reject' && (step.value !== 'reject' || !rejection.value.problemType)) return
  const token = sequence; busy.value = true; error.value = ''
  try {
    await registrationDemo.reportBatchSubmit({ targets: targets(), stage: props.stage, action,
      checks: results.value.map(result => ({ sampleId: result.sampleId, checkId: result.id })),
      ...(action === 'check' ? { confirmation: { readConfirmed: readConfirmed.value, nextAction: nextAction.value, ...(nextAction.value === 'transfer' ? { recipientId: recipient.value!.id } : {}) } } : { rejection: { ...rejection.value } }) })
    if (token === sequence) { emit('saved'); emit('close') }
  } catch (issue) {
    if (token !== sequence) return
    const failed = failure(issue)
    if (['NETWORK', 'UNAVAILABLE'].includes(failed.code)) { stale.value = true; clearProof() }
    if (failed.code === 'VALIDATION' && action === 'check') clearProof()
  } finally { if (token === sequence) busy.value = false }
}
watch(() => [props.stage, JSON.stringify(props.ids)], () => { nextAction.value = 'next'; recipient.value = undefined; rejection.value = emptyReportCheckRejection(); samples.value = []; void load() }, { immediate: true })
watch(currentActor, () => { invalidate(); emit('close') })
onBeforeUnmount(invalidate)
</script>
<template>
  <BootstrapModal :loading="loading" open :title="`快速${config.label}`" size="lg" scrollable :busy="busy" guard-close @close="close">
    <p class="text-muted">已选择 {{ ids.length }} 个样品，本次操作将应用于全部所选样品。</p>
    <ErrorNotice v-if="step === 'check'" :error="error" />
    <FeedbackNotice v-if="stale" message="样品信息或可用状态已变化，请刷新样品后重新校验、确认。"><p class="mb-2">样品信息或可用状态已变化，请刷新样品后重新校验、确认。</p><button type="button" class="btn btn-sm btn-outline-primary" :disabled="working" @click="load">刷新样品</button></FeedbackNotice>
    <p v-if="loading" class="text-muted" role="status">正在加载所选样品…</p>
    <button v-else-if="error && !samples.length && !stale" class="btn btn-outline-primary" type="button" @click="load">重试</button>
    <section v-if="samples.length" class="card border shadow-none mb-0" aria-labelledby="quick-report-check-title" :aria-busy="checking">
      <div class="card-header bg-light py-2 px-3 d-flex align-items-center justify-content-between flex-wrap gap-2">
        <h6 id="quick-report-check-title" class="card-title mb-0 fs-5">合规{{ config.label }}</h6>
        <button type="button" class="btn btn-sm btn-outline-primary" :disabled="!ready" @click="check"><span v-if="checking" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ checking ? '校验中…' : '校验' }}</button>
      </div>
      <div class="card-body p-3" role="region" aria-label="批量核验结果">
        <p v-if="checking" class="text-muted mb-0" role="status">正在获取全部样品的核验结果，请稍候…</p>
        <template v-else-if="verified">
          <section v-for="(result, index) in results" :key="result.sampleId" :class="{ 'mt-3 pt-3 border-top': index > 0 }" :aria-label="caption(result.sampleId)">
            <h6 class="fs-5 text-break">{{ caption(result.sampleId) }}</h6>
            <div class="alert alert-border-left mb-2" :class="result.messages.some(message => message.tone === 'warning') ? 'alert-warning' : 'alert-info'">
              <ul class="list-unstyled mb-0"><li v-for="(message, i) in result.messages" :key="i" class="d-flex gap-2" :class="{ 'mt-2': i > 0 }"><i :class="message.tone === 'warning' ? 'ti ti-alert-triangle' : 'ti ti-info-circle'" class="flex-shrink-0" aria-hidden="true"></i><span class="text-break">{{ message.text }}</span></li></ul>
            </div>
            <p class="text-muted small mb-0">核验时间：{{ new Date(result.checkedAt).toLocaleString('zh-CN') }}</p>
          </section>
        </template>
        <template v-else><p class="text-muted">请先进行合规校验，阅读全部结果后再确认通过。</p><ul class="list-unstyled mb-0"><li v-for="sample in samples" :key="sample.id" class="text-break py-1">{{ sample.code }} · {{ sample.name }}</li></ul></template>
      </div>
    </section>
    <template #pagination>
      <div class="px-3 py-2 border-top"><div class="form-check"><input id="quick-report-confirmed" v-model="readConfirmed" type="checkbox" class="form-check-input" :disabled="!verified || !ready" /><label for="quick-report-confirmed" class="form-check-label">我已阅读并确认全部样品的{{ config.label }}结果</label></div></div>
    </template>
    <template #footer>

        <button type="button" class="btn btn-light" :disabled="busy" @click="close">取消</button>
        <button type="button" class="btn btn-outline-danger" :disabled="!ready" @click="step = 'reject'; error = ''">不通过</button>
        <button type="button" class="btn btn-primary" :disabled="!canPass" @click="step = 'next'; error = ''">通过</button>
    </template>
  </BootstrapModal>
  <ConfirmationModal v-if="step !== 'check'" :title="step === 'next' ? '确认下一步' : '问题处理'" :size="step === 'reject' ? 'lg' : undefined" :busy="working" @close="closeDecision">
    <p class="text-muted">已选择 {{ ids.length }} 个样品，本次操作将应用于全部所选样品。</p>
    <ErrorNotice :error="error" />
    <template v-if="step === 'next'">
      <fieldset :disabled="working" class="mb-3">
        <legend class="visually-hidden">下一步</legend>
        <div class="d-flex flex-wrap gap-4">
          <div class="form-check"><input id="quick-report-transfer" v-model="nextAction" type="radio" class="form-check-input" value="transfer" name="quick-report-next" /><label for="quick-report-transfer" class="form-check-label">转交{{ config.label }}</label></div>
          <div class="form-check"><input id="quick-report-next" v-model="nextAction" type="radio" class="form-check-input" value="next" name="quick-report-next" /><label for="quick-report-next" class="form-check-label">下一步</label></div>
        </div>
      </fieldset>
      <label for="quick-report-recipient" class="form-label">接收人<span v-if="nextAction === 'transfer'" class="text-danger ms-1">*</span></label>
      <div class="input-group">
        <input id="quick-report-recipient" class="form-control" readonly :disabled="working || nextAction !== 'transfer'" :value="nextAction === 'transfer' && recipient ? `${recipient.name}（${recipient.id}）` : ''" placeholder="请选择接收人" />
        <button type="button" class="btn btn-light" aria-label="选择接收人" :disabled="working || nextAction !== 'transfer'" @click="picking = true"><i class="ti ti-search" aria-hidden="true"></i></button>
        <button type="button" class="btn btn-light" aria-label="清除接收人" :disabled="working || nextAction !== 'transfer' || !recipient" @click="recipient = undefined"><i class="ti ti-x" aria-hidden="true"></i></button>
      </div>
    </template>
    <ReportCheckRejectionForm v-else-if="step === 'reject'" :form="rejection" :busy="working" :errors="error ? error.fieldErrors || {} : {}" />

    <template #footer>
      <button type="button" class="btn btn-light" :disabled="working" @click="closeDecision">取消</button>
      <button type="button" class="btn btn-primary" :disabled="step === 'next' ? !canPass || nextAction === 'transfer' && !recipient : !ready || !rejection.problemType" @click="submit(step === 'next' ? 'check' : 'reject')">{{ busy ? '正在提交…' : '确定' }}</button>
    </template>
  </ConfirmationModal>
  <ConfirmationModal v-if="picking && samples[0]" title="选择接收人" size="lg" fill-height @close="picking = false">
    <DataEntryPersonPicker embedded :sample-id="samples[0].id" :role="config.role" :report-stage="stage" purpose="report-check" title="选择接收人" :value="recipient" :initial-scope="recipientScope" @scope="recipientScope = $event" @select="recipient = $event; picking = false" @close="picking = false" />
  </ConfirmationModal>
</template>
