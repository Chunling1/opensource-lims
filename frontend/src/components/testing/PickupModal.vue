<script setup lang="ts">
import FeedbackNotice from '../common/FeedbackNotice.vue'
import { computed, nextTick, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TemplateDate from '../common/TemplateDate.vue'
import { clientToday } from '../../services/common/date'
import { currentActor } from '../../stores/session'
import type { ErrorValue } from '../../services/common/errors'
import type { PickupReceipt, PickupRow } from '../../types/testing/pickup'

const props = defineProps<{ row?: PickupRow; busy: boolean; error: ErrorValue }>()
const emit = defineEmits<{ close: []; submit: [PickupReceipt]; refresh: [] }>()
const draft = ref<PickupReceipt>({ account: '', name: '', date: '' })
const keys = ['account', 'name', 'date'] as const
const fieldErrors = ref<Record<string, string>>({}), validation = ref('')
const systemError = computed(() => props.error && props.error.code !== 'VALIDATION' ? props.error : '')
const stale = computed(() => !!props.error && ['BUSINESS_RULE', 'NOT_FOUND', 'FORBIDDEN', 'NETWORK'].includes(props.error.code))
function feedback(key: string) {
  return { class: { 'is-invalid': !!fieldErrors.value[key] }, 'aria-invalid': !!fieldErrors.value[key], 'aria-describedby': fieldErrors.value[key] ? `pickup-${key}-error` : undefined }
}
watch(() => props.row, row => {
  if (!row) return
  draft.value = { account: currentActor.value.id, name: currentActor.value.name, date: clientToday() }
  fieldErrors.value = {}; validation.value = ''
})
watch(() => props.error, async error => {
  if (!error || error.code !== 'VALIDATION') return
  fieldErrors.value = Object.fromEntries(keys.filter(key => error.fieldErrors?.[key]).map(key => [key, error.fieldErrors![key]!]))
  validation.value = Object.keys(fieldErrors.value).length ? '' : error.message
  await nextTick()
  document.querySelector<HTMLElement>('#pickup-operation .is-invalid')?.focus()
})
for (const key of keys) watch(() => draft.value[key], () => {
  delete fieldErrors.value[key]; validation.value = ''
  if (key === 'account' || key === 'name') { delete fieldErrors.value.account; delete fieldErrors.value.name }
})
function submit() {
  if (!props.row || props.busy || stale.value) return
  fieldErrors.value = {}; validation.value = ''
  emit('submit', { ...draft.value })
}
</script>
<template>
  <BootstrapModal :open="!!row" title="领取样品" :busy="busy" scrollable @close="!busy && emit('close')">
    <ErrorNotice :error="systemError" />
    <FeedbackNotice v-if="validation" :message="validation">{{ validation }}</FeedbackNotice>
    <button v-if="stale" type="button" class="btn btn-outline-primary btn-sm mb-3" :disabled="busy" @click="emit('refresh')">刷新列表</button>
    <form v-if="row" id="pickup-operation" @submit.prevent="submit">
      <p class="text-break text-muted"><strong>{{ row.code }}</strong> · {{ row.name }}</p>
      <fieldset :disabled="busy" class="row g-3">
        <div class="col-12 col-sm-6"><label for="pickup-account" class="form-label">领样员工号 <span class="text-danger">*</span></label><input id="pickup-account" v-model="draft.account" v-bind="feedback('account')" class="form-control" required maxlength="100" autocomplete="off" /><div v-if="fieldErrors.account" id="pickup-account-error" class="invalid-feedback" role="alert">{{ fieldErrors.account }}</div></div>
        <div class="col-12 col-sm-6"><label for="pickup-name" class="form-label">领样员姓名 <span class="text-danger">*</span></label><input id="pickup-name" v-model="draft.name" v-bind="feedback('name')" class="form-control" required maxlength="100" autocomplete="off" /><div v-if="fieldErrors.name" id="pickup-name-error" class="invalid-feedback" role="alert">{{ fieldErrors.name }}</div></div>
        <div class="col-12"><label for="pickup-date" class="form-label">领样时间 <span class="text-danger">*</span></label><TemplateDate id="pickup-date" v-model="draft.date" v-bind="feedback('date')" required :disabled="busy" /><div v-if="fieldErrors.date" id="pickup-date-error" class="invalid-feedback" role="alert">{{ fieldErrors.date }}</div></div>
      </fieldset>
    </form>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button><button type="submit" form="pickup-operation" class="btn btn-primary" :disabled="busy || stale || !row"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在提交…' : '确认' }}</button></template>
  </BootstrapModal>
</template>
