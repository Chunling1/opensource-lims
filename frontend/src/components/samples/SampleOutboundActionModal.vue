<script setup lang="ts">
import FeedbackNotice from '../common/FeedbackNotice.vue'
import { computed, nextTick, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import SingleChoice from '../common/SingleChoice.vue'
import TemplateDate from '../common/TemplateDate.vue'
import { clientToday } from '../../services/common/date'
import type { ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { outboundReturnTypes, type OutboundAction, type OutboundReceipt, type OutboundReturnType, type OutboundSubmission } from '../../types/samples/outbound'
import type { InboundRow } from '../../types/samples/inbound'

const props = defineProps<{ operation?: { row: InboundRow; action: OutboundAction }; busy: boolean; error: ErrorValue }>()
const emit = defineEmits<{ close: []; submit: [OutboundSubmission]; refresh: [] }>()
const title = computed(() => props.operation?.action === 'return' ? '退回委托' : props.operation?.action === 'undo' ? '撤销出库' : '样品出库')
const receipt = ref<OutboundReceipt>({ account: '', name: '', date: '' })
const returned = ref({ type: '' as OutboundReturnType | '', reason: '', details: '', date: '' })
const fieldErrors = ref<Record<string, string>>({}), validation = ref('')
const errorKeys = ['account', 'name', 'date', 'type', 'reason', 'details'] as const
const systemError = computed(() => props.error && props.error.code !== 'VALIDATION' ? props.error : '')
const stale = computed(() => !!props.error && ['BUSINESS_RULE'].includes(props.error.code))
function feedback(key: string) { return { class: { 'is-invalid': !!fieldErrors.value[key] }, 'aria-invalid': !!fieldErrors.value[key], 'aria-describedby': fieldErrors.value[key] ? `outbound-${key}-error` : undefined } }
watch(() => props.operation, operation => {
  if (!operation) return
  receipt.value = { account: currentActor.value.id, name: currentActor.value.name, date: clientToday() }
  returned.value = { type: 'commission', reason: '', details: '', date: clientToday() }
  fieldErrors.value = {}; validation.value = ''
})
watch(() => props.error, async error => {
  if (!error || error.code !== 'VALIDATION') return
  fieldErrors.value = Object.fromEntries(errorKeys.filter(key => error.fieldErrors?.[key]).map(key => [key, error.fieldErrors![key]!]))
  validation.value = Object.keys(fieldErrors.value).length ? '' : error.message
  await nextTick()
  document.querySelector<HTMLElement>('#sample-outbound-operation .is-invalid')?.focus()
})
for (const key of ['account', 'name', 'date'] as const) watch(() => receipt.value[key], () => {
  delete fieldErrors.value[key]; validation.value = ''
  if (key === 'account' || key === 'name') { delete fieldErrors.value.account; delete fieldErrors.value.name }
})
for (const key of ['type', 'reason', 'details', 'date'] as const) watch(() => returned.value[key], () => { delete fieldErrors.value[key]; validation.value = '' })
async function submit() {
  if (!props.operation || props.busy || stale.value) return
  fieldErrors.value = {}; validation.value = ''
  const action = props.operation.action
  if (action === 'dispatch') emit('submit', { action, receipt: { ...receipt.value } })
  else if (action === 'undo') emit('submit', { action })
  else if (!returned.value.type) { fieldErrors.value.type = '请选择退回类型。'; await nextTick(); document.getElementById('outbound-type-commission')?.focus() }
  else emit('submit', { action, returned: { ...returned.value, type: returned.value.type } })
}
</script>
<template>
  <BootstrapModal :open="!!operation" :title="title" :busy="busy" scrollable @close="!busy && emit('close')">
    <ErrorNotice :error="systemError" />
    <FeedbackNotice v-if="validation" :message="validation">{{ validation }}</FeedbackNotice>
    <button v-if="stale" type="button" class="btn btn-outline-primary btn-sm mb-3" :disabled="busy" @click="emit('refresh')">刷新列表</button>
    <form v-if="operation" id="sample-outbound-operation" @submit.prevent="submit">
      <p class="text-break text-muted"><strong>{{ operation.row.code }}</strong> · {{ operation.row.name }}</p>
      <fieldset v-if="operation.action === 'dispatch'" :disabled="busy" class="row g-3">
        <div class="col-12 col-sm-6"><label for="outbound-account" class="form-label">样品管理员工号 <span class="text-danger">*</span></label><input id="outbound-account" v-model="receipt.account" v-bind="feedback('account')" class="form-control" required maxlength="100" autocomplete="off" /><div v-if="fieldErrors.account" id="outbound-account-error" class="invalid-feedback" role="alert">{{ fieldErrors.account }}</div></div>
        <div class="col-12 col-sm-6"><label for="outbound-name" class="form-label">样品管理员姓名 <span class="text-danger">*</span></label><input id="outbound-name" v-model="receipt.name" v-bind="feedback('name')" class="form-control" required maxlength="100" autocomplete="off" /><div v-if="fieldErrors.name" id="outbound-name-error" class="invalid-feedback" role="alert">{{ fieldErrors.name }}</div></div>
        <div class="col-12"><label for="outbound-date" class="form-label">出库时间 <span class="text-danger">*</span></label><TemplateDate id="outbound-date" v-model="receipt.date" v-bind="feedback('date')" required :disabled="busy" /><div v-if="fieldErrors.date" id="outbound-date-error" class="invalid-feedback" role="alert">{{ fieldErrors.date }}</div></div>
      </fieldset>
      <fieldset v-else-if="operation.action === 'return'" :disabled="busy" class="row g-3">
        <div class="col-12"><div class="d-flex flex-wrap gap-3" role="group" aria-label="退回类型" :aria-invalid="!!fieldErrors.type" :aria-describedby="fieldErrors.type ? 'outbound-type-error' : undefined"><label v-for="option in outboundReturnTypes" :key="option.value" class="d-flex align-items-center gap-2"><SingleChoice :id="`outbound-type-${option.value}`" name="outbound-return-type" :value="option.value" :label="option.label" :checked="returned.type === option.value" :disabled="busy" @change="returned.type = option.value" />{{ option.label }}</label></div><div v-if="fieldErrors.type" id="outbound-type-error" class="invalid-feedback d-block" role="alert">{{ fieldErrors.type }}</div></div>
        <div class="col-12"><label for="outbound-reason" class="form-label">退回原因 <span class="text-danger">*</span></label><input id="outbound-reason" v-model="returned.reason" v-bind="feedback('reason')" class="form-control" required maxlength="500" /><div v-if="fieldErrors.reason" id="outbound-reason-error" class="invalid-feedback" role="alert">{{ fieldErrors.reason }}</div></div>
        <div class="col-12"><label for="outbound-details" class="form-label">补充说明</label><textarea id="outbound-details" v-model="returned.details" v-bind="feedback('details')" class="form-control" rows="4" maxlength="2000"></textarea><div v-if="fieldErrors.details" id="outbound-details-error" class="invalid-feedback" role="alert">{{ fieldErrors.details }}</div></div>
        <div class="col-12"><label for="outbound-return-date" class="form-label">退回时间 <span class="text-danger">*</span></label><TemplateDate id="outbound-return-date" v-model="returned.date" v-bind="feedback('date')" required :disabled="busy" /><div v-if="fieldErrors.date" id="outbound-date-error" class="invalid-feedback" role="alert">{{ fieldErrors.date }}</div></div>
      </fieldset>
      <p v-else>确认对这条样品执行“撤销出库”？</p>
    </form>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button><button type="submit" form="sample-outbound-operation" class="btn btn-primary" :disabled="busy || stale || !operation"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在提交…' : '确认' }}</button></template>
  </BootstrapModal>
</template>
