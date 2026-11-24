<script setup lang="ts">
import FeedbackNotice from '../common/FeedbackNotice.vue'
import { computed, nextTick, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import SingleChoice from '../common/SingleChoice.vue'
import TemplateDate from '../common/TemplateDate.vue'
import { clientToday } from '../../services/common/date'
import type { ErrorValue } from '../../services/common/errors'
import { outboundReturnTypes, type OutboundReturnType, type OutboundReturn } from '../../types/samples/outbound'
import type { TaskQueryRow } from '../../types/testing/taskQuery'

const props = defineProps<{ row?: Pick<TaskQueryRow, 'code' | 'name'>; busy: boolean; error: ErrorValue }>()
const emit = defineEmits<{ close: []; submit: [OutboundReturn]; refresh: [] }>()
const returned = ref({ type: '' as OutboundReturnType | '', reason: '', details: '', date: '' })
const fieldErrors = ref<Record<string, string>>({}), validation = ref('')
const errorKeys = ['date', 'type', 'reason', 'details'] as const
const systemError = computed(() => props.error && props.error.code !== 'VALIDATION' ? props.error : '')
const stale = computed(() => !!props.error && ['BUSINESS_RULE', 'NOT_FOUND', 'FORBIDDEN', 'NETWORK'].includes(props.error.code))
function feedback(key: string) { return { class: { 'is-invalid': !!fieldErrors.value[key] }, 'aria-invalid': !!fieldErrors.value[key], 'aria-describedby': fieldErrors.value[key] ? `task-return-${key}-error` : undefined } }
watch(() => props.row, row => {
  if (!row) return
  returned.value = { type: 'commission', reason: '', details: '', date: clientToday() }
  fieldErrors.value = {}; validation.value = ''
})
watch(() => props.error, async error => {
  if (!error || error.code !== 'VALIDATION') return
  fieldErrors.value = Object.fromEntries(errorKeys.filter(key => error.fieldErrors?.[key]).map(key => [key, error.fieldErrors![key]!]))
  validation.value = Object.keys(fieldErrors.value).length ? '' : error.message
  await nextTick()
  document.querySelector<HTMLElement>('#task-return-operation .is-invalid')?.focus()
})
for (const key of ['type', 'reason', 'details', 'date'] as const) watch(() => returned.value[key], () => { delete fieldErrors.value[key]; validation.value = '' })
async function submit() {
  if (!props.row || props.busy || stale.value) return
  fieldErrors.value = {}; validation.value = ''
  if (!returned.value.type) { fieldErrors.value.type = '请选择退回类型。'; await nextTick(); document.getElementById('task-return-type-commission')?.focus() }
  else emit('submit', { ...returned.value, type: returned.value.type })
}
</script>
<template>
  <BootstrapModal :open="!!row" title="退回委托" :busy="busy" scrollable @close="!busy && emit('close')">
    <ErrorNotice :error="systemError" />
    <FeedbackNotice v-if="validation" :message="validation">{{ validation }}</FeedbackNotice>
    <button v-if="stale" type="button" class="btn btn-outline-primary btn-sm mb-3" :disabled="busy" @click="emit('refresh')">刷新列表</button>
    <form v-if="row" id="task-return-operation" @submit.prevent="submit">
      <p class="text-break text-muted"><strong>{{ row.code }}</strong> · {{ row.name }}</p>
      <fieldset :disabled="busy" class="row g-3">
        <div class="col-12"><div class="d-flex flex-wrap gap-3" role="group" aria-label="退回类型" :aria-invalid="!!fieldErrors.type" :aria-describedby="fieldErrors.type ? 'task-return-type-error' : undefined"><label v-for="option in outboundReturnTypes" :key="option.value" class="d-flex align-items-center gap-2"><SingleChoice :id="`task-return-type-${option.value}`" name="task-return-return-type" :value="option.value" :label="option.label" :checked="returned.type === option.value" :disabled="busy" @change="returned.type = option.value" />{{ option.label }}</label></div><div v-if="fieldErrors.type" id="task-return-type-error" class="invalid-feedback d-block" role="alert">{{ fieldErrors.type }}</div></div>
        <div class="col-12"><label for="task-return-reason" class="form-label">退回原因 <span class="text-danger">*</span></label><input id="task-return-reason" v-model="returned.reason" v-bind="feedback('reason')" class="form-control" required maxlength="500" /><div v-if="fieldErrors.reason" id="task-return-reason-error" class="invalid-feedback" role="alert">{{ fieldErrors.reason }}</div></div>
        <div class="col-12"><label for="task-return-details" class="form-label">补充说明</label><textarea id="task-return-details" v-model="returned.details" v-bind="feedback('details')" class="form-control" rows="4" maxlength="2000"></textarea><div v-if="fieldErrors.details" id="task-return-details-error" class="invalid-feedback" role="alert">{{ fieldErrors.details }}</div></div>
        <div class="col-12"><label for="task-return-return-date" class="form-label">退回时间 <span class="text-danger">*</span></label><TemplateDate id="task-return-return-date" v-model="returned.date" v-bind="feedback('date')" required :disabled="busy" /><div v-if="fieldErrors.date" id="task-return-date-error" class="invalid-feedback" role="alert">{{ fieldErrors.date }}</div></div>
      </fieldset>
    </form>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button><button type="submit" form="task-return-operation" class="btn btn-primary" :disabled="busy || stale || !row"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在提交…' : '确认' }}</button></template>
  </BootstrapModal>
</template>
