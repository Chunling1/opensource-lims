<script setup lang="ts">
import FeedbackNotice from '../common/FeedbackNotice.vue'
import { computed, nextTick, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TemplateDate from '../common/TemplateDate.vue'
import { clientToday } from '../../services/common/date'
import { currentActor } from '../../stores/session'
import type { ErrorValue } from '../../services/common/errors'
import type { AssignmentRow, AssignmentSubmission } from '../../types/testing/assignment'

const props = defineProps<{ row?: AssignmentRow; undo?: boolean; busy: boolean; error: ErrorValue }>()
const emit = defineEmits<{ close: []; submit: [AssignmentSubmission]; undo: []; refresh: [] }>()
const draft = ref<AssignmentSubmission>({ account: '', name: '', dataEntryPerson: '', tester1: '', tester2: '', date: '' })
const peopleFields = [{ key: 'dataEntryPerson', label: '数据录入人', required: true }, { key: 'tester1', label: '检测人1', required: true }, { key: 'tester2', label: '检测人2', required: false }] as const
const keys = ['account', 'name', 'dataEntryPerson', 'tester1', 'tester2', 'date'] as const
const fieldErrors = ref<Record<string, string>>({}), validation = ref('')
const systemError = computed(() => props.error && props.error.code !== 'VALIDATION' ? props.error : '')
const stale = computed(() => !!props.error && ['BUSINESS_RULE', 'NOT_FOUND', 'FORBIDDEN'].includes(props.error.code))
function feedback(key: string) {
  return { class: { 'is-invalid': !!fieldErrors.value[key] }, 'aria-invalid': !!fieldErrors.value[key], 'aria-describedby': fieldErrors.value[key] ? `assignment-${key}-error` : undefined }
}
watch(() => props.row, row => {
  if (!row) return
  draft.value = { account: currentActor.value.id, name: currentActor.value.name, dataEntryPerson: '', tester1: '', tester2: '', date: clientToday() }
  fieldErrors.value = {}; validation.value = ''
})
watch(() => props.error, async error => {
  if (!error || error.code !== 'VALIDATION') return
  fieldErrors.value = Object.fromEntries(keys.filter(key => error.fieldErrors?.[key]).map(key => [key, error.fieldErrors![key]!]))
  validation.value = Object.keys(fieldErrors.value).length ? '' : error.message
  await nextTick()
  document.querySelector<HTMLElement>('#assignment-operation .is-invalid')?.focus()
})
for (const key of keys) watch(() => draft.value[key], () => {
  delete fieldErrors.value[key]; validation.value = ''
  if (key === 'tester1') delete fieldErrors.value.tester2
  if (key === 'account' || key === 'name') { delete fieldErrors.value.account; delete fieldErrors.value.name }
})
function submit() {
  if (!props.row || props.busy || stale.value) return
  fieldErrors.value = {}; validation.value = ''
  if (props.undo) emit('undo')
  else emit('submit', { ...draft.value })
}
</script>
<template>
  <BootstrapModal :open="!!row" :title="undo ? '撤销分配' : '分配'" :busy="busy" scrollable @close="!busy && emit('close')">
    <ErrorNotice :error="systemError" />
    <FeedbackNotice v-if="validation" :message="validation">{{ validation }}</FeedbackNotice>
    <button v-if="stale" type="button" class="btn btn-outline-primary btn-sm mb-3" :disabled="busy" @click="emit('refresh')">刷新列表</button>
    <form v-if="row" id="assignment-operation" @submit.prevent="submit">
      <p class="text-break text-muted"><strong>{{ row.code }}</strong> · {{ row.name }}</p>
      <p v-if="undo">确认对这条样品执行“撤销分配”？撤销后将恢复为“任务分配中”。</p>
      <fieldset v-else :disabled="busy" class="row g-3">
        <div class="col-12 col-sm-6"><label for="assignment-operator-account" class="form-label">分配人工号 <span class="text-danger">*</span></label><input id="assignment-operator-account" v-model="draft.account" v-bind="feedback('account')" class="form-control" required maxlength="100" autocomplete="off" /><div v-if="fieldErrors.account" id="assignment-account-error" class="invalid-feedback" role="alert">{{ fieldErrors.account }}</div></div>
        <div class="col-12 col-sm-6"><label for="assignment-operator-name" class="form-label">分配人姓名 <span class="text-danger">*</span></label><input id="assignment-operator-name" v-model="draft.name" v-bind="feedback('name')" class="form-control" required maxlength="100" autocomplete="off" /><div v-if="fieldErrors.name" id="assignment-name-error" class="invalid-feedback" role="alert">{{ fieldErrors.name }}</div></div>
        <div v-for="field in peopleFields" :key="field.key" :class="field.key === 'dataEntryPerson' ? 'col-12' : 'col-12 col-sm-6'">
          <label :for="`assignment-${field.key}`" class="form-label">{{ field.label }} <span v-if="field.required" class="text-danger">*</span></label>
          <input :id="`assignment-${field.key}`" v-model="draft[field.key]" v-bind="feedback(field.key)" class="form-control" :required="field.required" maxlength="100" autocomplete="off" placeholder="请输入姓名或账号" />
          <div v-if="fieldErrors[field.key]" :id="`assignment-${field.key}-error`" class="invalid-feedback" role="alert">{{ fieldErrors[field.key] }}</div>
        </div>
        <div class="col-12"><label for="assignment-date" class="form-label">分配日期 <span class="text-danger">*</span></label><TemplateDate id="assignment-date" v-model="draft.date" v-bind="feedback('date')" required :disabled="busy" /><div v-if="fieldErrors.date" id="assignment-date-error" class="invalid-feedback" role="alert">{{ fieldErrors.date }}</div></div>
      </fieldset>
    </form>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button><button type="submit" form="assignment-operation" class="btn btn-primary" :disabled="busy || stale || !row"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在提交…' : '确认' }}</button></template>
  </BootstrapModal>
</template>
