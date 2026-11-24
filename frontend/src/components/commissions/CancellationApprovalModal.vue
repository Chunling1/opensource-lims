<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { currentActor } from '../../stores/session'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { canApproveCancellation, type CancellationDecision } from '../../types/commissions/cancellationApproval'
import type { RegistrationSample } from '../../types/commissions/registration'
const props = defineProps<{ record?: RegistrationSample & { commissionCode: string } }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const reason = ref(''), reasonError = ref(''), error = ref<ErrorValue>(''), busy = ref(false)
const application = computed(() => props.record?.voidApplication)
const pending = computed(() => props.record?.status === 'void_pending' && !!application.value && !application.value.decision)
const permitted = computed(() => pending.value && canApproveCancellation(currentActor.value))
const date = (value?: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
let request = 0
watch(() => props.record, () => { request++; reason.value = ''; reasonError.value = ''; error.value = ''; busy.value = false })
onBeforeUnmount(() => request++)
async function submit(decision: CancellationDecision) {
  if (!props.record || !permitted.value || busy.value) return
  reasonError.value = ''
  if (decision === 'rejected' && !reason.value.trim()) { reasonError.value = '请填写审批不通过原因。'; return }
  const token = ++request
  busy.value = true; error.value = ''
  try {
    await registrationDemo.approveCancellation(props.record.id, { version: props.record.version, decision, reason: reason.value })
    if (token === request) { emit('saved'); emit('close') }
  } catch (issue) { if (token === request) error.value = normalizeError(issue) }
  finally { if (token === request) busy.value = false }
}
</script>
<template>
  <BootstrapModal :open="!!record" :title="pending ? '作废审批' : '审批结果'" :busy="busy" size="lg" scrollable fullscreen-mobile @close="!busy && emit('close')">
    <template v-if="record && application">
      <ErrorNotice :error="error" />
      <div class="card border shadow-none mb-3">
        <div class="card-header bg-light"><h6 class="card-title mb-0">申请信息</h6></div>
        <div class="card-body"><dl class="row g-3 mb-0">
          <div class="col-12 col-sm-6"><dt class="text-muted fw-normal">样品编号</dt><dd class="mb-0 text-break">{{ record.code }}</dd></div>
          <div class="col-12 col-sm-6"><dt class="text-muted fw-normal">委托编号</dt><dd class="mb-0 text-break">{{ record.commissionCode }}</dd></div>
          <div class="col-12 col-sm-6"><dt class="text-muted fw-normal">报告编号</dt><dd class="mb-0 text-break">{{ record.reportCode || '—' }}</dd></div>
          <div class="col-12 col-sm-6"><dt class="text-muted fw-normal">样品/工程名称</dt><dd class="mb-0 text-break">{{ record.name }}</dd></div>
          <div class="col-12 col-sm-6"><dt class="text-muted fw-normal">申请人</dt><dd class="mb-0 text-break">{{ application.appliedBy.name }}</dd></div>
          <div class="col-12 col-sm-6"><dt class="text-muted fw-normal">申请日期</dt><dd class="mb-0">{{ date(application.appliedAt) }}</dd></div>
          <div class="col-12"><dt class="text-muted fw-normal">申请原因</dt><dd class="mb-0 text-break">{{ application.reason }}</dd></div>
        </dl></div>
      </div>
      <div v-if="permitted"><label for="cancellation-reason" class="form-label">审批不通过原因</label><textarea id="cancellation-reason" v-model="reason" class="form-control" :class="{ 'is-invalid': reasonError }" rows="3" maxlength="500" :disabled="busy" :aria-invalid="!!reasonError" aria-describedby="cancellation-reason-error" @input="reasonError = ''"></textarea><div id="cancellation-reason-error" class="invalid-feedback">{{ reasonError }}</div></div>
      <div v-else-if="application.decision" class="card border shadow-none mb-0">
        <div class="card-header bg-light"><h6 class="card-title mb-0">审批结果</h6></div>
        <div class="card-body"><dl class="row g-3 mb-0">
          <div class="col-12 col-sm-4"><dt class="text-muted fw-normal">审批结果</dt><dd class="mb-0"><span class="badge" :class="application.decision === 'approved' ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger'">{{ application.decision === 'approved' ? '申请通过' : '申请不通过' }}</span></dd></div>
          <div class="col-12 col-sm-4"><dt class="text-muted fw-normal">审批人</dt><dd class="mb-0 text-break">{{ application.approvedBy?.name || '—' }}</dd></div>
          <div class="col-12 col-sm-4"><dt class="text-muted fw-normal">审批日期</dt><dd class="mb-0">{{ date(application.approvedAt) }}</dd></div>
          <div v-if="application.decision === 'rejected'" class="col-12"><dt class="text-muted fw-normal">审批不通过原因</dt><dd class="mb-0 text-break">{{ application.rejectionReason }}</dd></div>
        </dl></div>
      </div>
      <p v-else class="text-muted mb-0">当前身份无权审批此申请。</p>
    </template>
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">{{ pending ? '取消' : '关闭' }}</button>
      <template v-if="permitted"><button type="button" class="btn btn-outline-danger" :disabled="busy" @click="submit('rejected')">不通过</button><button type="button" class="btn btn-primary" :disabled="busy" @click="submit('approved')"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在提交…' : '通过' }}</button></template>
    </template>
  </BootstrapModal>
</template>
