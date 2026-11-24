<script setup lang="ts">
import FeedbackNotice from '../common/FeedbackNotice.vue'
import { computed, nextTick, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TemplateDate from '../common/TemplateDate.vue'
import type { ErrorValue } from '../../services/common/errors'
import { clientToday } from '../../services/common/date'
import { currentActor } from '../../stores/session'
import type { InboundRow } from '../../types/samples/inbound'
import type { DisposalAction, DisposalReceipt, DisposalSubmission } from '../../types/samples/disposal'
const props = defineProps<{ operation?: { row: InboundRow; action: DisposalAction }; busy: boolean; error: ErrorValue }>()
const emit = defineEmits<{ close: []; submit: [DisposalSubmission]; refresh: [] }>()
const receipt = ref<DisposalReceipt>({ result: '', name: '', date: '' })
const fieldErrors = ref<Record<string, string>>({}), validation = ref('')
const keys = ['result', 'name', 'date'] as const
const systemError = computed(() => props.error && props.error.code !== 'VALIDATION' ? props.error : '')
const stale = computed(() => !!props.error && ['BUSINESS_RULE'].includes(props.error.code))
function feedback(key: string) { return { class: { 'is-invalid': !!fieldErrors.value[key] }, 'aria-invalid': !!fieldErrors.value[key], 'aria-describedby': fieldErrors.value[key] ? `disposal-${key}-error` : undefined } }
watch(() => props.operation, operation => {
  if (!operation) return
  receipt.value = { result: '', name: currentActor.value.name, date: clientToday() }
  fieldErrors.value = {}; validation.value = ''
})
watch(() => props.error, async error => {
  if (!error || error.code !== 'VALIDATION') return
  fieldErrors.value = Object.fromEntries(keys.filter(key => error.fieldErrors?.[key]).map(key => [key, error.fieldErrors![key]!]))
  validation.value = Object.keys(fieldErrors.value).length ? '' : error.message
  await nextTick()
  document.querySelector<HTMLElement>('#sample-disposal-operation .is-invalid')?.focus()
})
for (const key of keys) watch(() => receipt.value[key], () => { delete fieldErrors.value[key]; validation.value = '' })
function submit() {
  if (!props.operation || props.busy || stale.value) return
  fieldErrors.value = {}; validation.value = ''
  emit('submit', props.operation.action === 'dispose' ? { action: 'dispose', receipt: { ...receipt.value } } : { action: 'undo' })
}
</script>
<template>
  <BootstrapModal :open="!!operation" :title="operation?.action === 'undo' ? '撤销处置' : '样品处置'" :busy="busy" scrollable @close="!busy && emit('close')">
    <ErrorNotice :error="systemError" />
    <FeedbackNotice v-if="validation" :message="validation">{{ validation }}</FeedbackNotice>
    <button v-if="stale" type="button" class="btn btn-outline-primary btn-sm mb-3" :disabled="busy" @click="emit('refresh')">刷新列表</button>
    <form v-if="operation" id="sample-disposal-operation" @submit.prevent="submit">
      <p class="text-break text-muted"><strong>{{ operation.row.code }}</strong> · {{ operation.row.name }}</p>
      <fieldset v-if="operation.action === 'dispose'" :disabled="busy" class="row g-3">
        <div class="col-12"><label for="disposal-requirement" class="form-label">本样品客户处置要求</label><input id="disposal-requirement" :value="operation.row.customerRequirement || '未填写'" class="form-control bg-light" readonly /></div>
        <div class="col-12"><label for="disposal-result" class="form-label">处置结果 <span class="text-danger">*</span></label><input id="disposal-result" v-model="receipt.result" v-bind="feedback('result')" class="form-control" required maxlength="500" /><div v-if="fieldErrors.result" id="disposal-result-error" class="invalid-feedback" role="alert">{{ fieldErrors.result }}</div></div>
        <div class="col-12 col-sm-6"><label for="disposal-name" class="form-label">处置人 <span class="text-danger">*</span></label><input id="disposal-name" v-model="receipt.name" v-bind="feedback('name')" class="form-control" required maxlength="100" /><div v-if="fieldErrors.name" id="disposal-name-error" class="invalid-feedback" role="alert">{{ fieldErrors.name }}</div></div>
        <div class="col-12 col-sm-6"><label for="disposal-date" class="form-label">处置时间 <span class="text-danger">*</span></label><TemplateDate id="disposal-date" v-model="receipt.date" v-bind="feedback('date')" required :disabled="busy" /><div v-if="fieldErrors.date" id="disposal-date-error" class="invalid-feedback" role="alert">{{ fieldErrors.date }}</div></div>
      </fieldset>
      <p v-else>确认对这条样品执行“撤销处置”？</p>
    </form>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button><button type="submit" form="sample-disposal-operation" class="btn btn-primary" :disabled="busy || stale || !operation"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在提交…' : '确认' }}</button></template>
  </BootstrapModal>
</template>
