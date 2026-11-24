<script setup lang="ts">
import { ref } from 'vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { canRetry, type ErrorValue } from '../../services/common/errors'
import BootstrapModal from '../common/BootstrapModal.vue'
import TemplateDateRange from '../common/TemplateDateRange.vue'
import FormControl from '../forms/FormControl.vue'
import { sampleWorkflowDateFields, sampleConclusions, type SampleWorkflowDateKey } from '../../types/commissions/sampleWorkflow'
import { sampleTypes } from '../../types/commissions/registration'
import { inquirySampleDataStatusOptions } from '../../views/commissions/sampleQueryOptions'
import { sampleAdvancedFields, type SampleAdvancedDraft, type SampleAdvancedFields } from '../../types/commissions/sampleAdvancedQuery'
import type { FormField } from '../../types/forms'
const props = defineProps<{ initial: SampleAdvancedDraft; busy?: boolean; error?: ErrorValue }>()
const emit = defineEmits<{ close: []; search: [SampleAdvancedDraft] }>()
const draft = ref<SampleAdvancedDraft>({ ...props.initial, fields: { ...props.initial.fields }, workflowDates: Object.fromEntries(sampleWorkflowDateFields.map(({ key }) => [key, { ...props.initial.workflowDates[key] }])) as SampleAdvancedDraft['workflowDates'] })
const dateRange = ref<InstanceType<typeof TemplateDateRange>>()
const workflowDateRefs = new Map<SampleWorkflowDateKey, InstanceType<typeof TemplateDateRange>>()
function setDateRef(key: SampleWorkflowDateKey, control: unknown) {
  if (control) workflowDateRefs.set(key, control as InstanceType<typeof TemplateDateRange>)
  else workflowDateRefs.delete(key)
}
const fields: FormField<SampleAdvancedFields>[] = sampleAdvancedFields.map(({ key, label }) => ({
  id: `sample-advanced-${key}`, label, control: 'text', maxlength: 200,
  binding: { get: model => model[key] || '', set: (model, value) => { model[key] = value } },
}))
function submit() {
  if (props.busy) return
  if (draft.value.useDate && !dateRange.value?.validate()) return
  for (const { key } of sampleWorkflowDateFields) if (draft.value.workflowDates[key].enabled && !workflowDateRefs.get(key)?.validate()) return
  emit('search', { ...draft.value, fields: Object.fromEntries(Object.entries(draft.value.fields).map(([key, value]) => [key, value?.trim() || ''])) })
}
</script>
<template>
  <BootstrapModal open :busy="busy" title="样品高级查询" size="lg" scrollable fullscreen-mobile @close="emit('close')">
    <form :aria-busy="busy" id="sample-advanced-form" aria-label="样品高级查询条件" @submit.prevent="submit">
      <fieldset :disabled="busy">
      <div class="row g-3">
        <div v-for="field in fields" :key="field.id" class="col-12 col-md-6 col-lg-4">
          <label :for="field.id" class="form-label">{{ field.label }}</label>
          <FormControl :field="field" :model="draft.fields" />
        </div>
        <div class="col-12 col-md-6 col-lg-4">
          <label for="sample-advanced-status" class="form-label">数据状态</label>
          <select id="sample-advanced-status" v-model="draft.dataStatus" class="form-select"><option v-for="option in inquirySampleDataStatusOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select>
        </div>
        <div class="col-12 col-md-6 col-lg-4">
          <label for="sample-advanced-type" class="form-label">样品类型</label>
          <select id="sample-advanced-type" v-model="draft.sampleType" class="form-select"><option value="">全部</option><option v-for="type in sampleTypes" :key="type" :value="type">{{ type }}</option></select>
        </div>
        <div class="col-12 col-md-6 col-lg-4">
          <label for="sample-advanced-conclusion" class="form-label">结论</label>
          <select id="sample-advanced-conclusion" v-model="draft.conclusion" class="form-select"><option value="">全部</option><option v-for="option in sampleConclusions" :key="option.value" :value="option.value">{{ option.label }}</option></select>
        </div>
      </div>
      <fieldset class="mt-4">
        <legend class="fs-5 fw-semibold mb-3">日期条件</legend>
        <div class="row g-3">
        <div class="col-12 col-md-6">
          <div class="form-check mb-2"><input id="sample-advanced-use-date" v-model="draft.useDate" class="form-check-input" type="checkbox" /><label class="form-check-label" for="sample-advanced-use-date">按委托日期查询</label></div>
          <label for="sample-advanced-date" class="visually-hidden">委托日期</label>
          <TemplateDateRange v-if="draft.useDate" id="sample-advanced-date" ref="dateRange" within-modal :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" />
          <input v-else id="sample-advanced-date" class="form-control" disabled :value="`${draft.from} 至 ${draft.to}`" />
        </div>
        <div v-for="field in sampleWorkflowDateFields" :key="field.key" class="col-12 col-md-6">
          <div class="form-check mb-2"><input :id="`sample-advanced-use-${field.key}`" v-model="draft.workflowDates[field.key].enabled" class="form-check-input" type="checkbox" /><label class="form-check-label" :for="`sample-advanced-use-${field.key}`">按{{ field.label }}查询</label></div>
          <label :for="`sample-advanced-${field.key}`" class="visually-hidden">{{ field.label }}</label>
          <TemplateDateRange v-if="draft.workflowDates[field.key].enabled" :id="`sample-advanced-${field.key}`" :ref="control => setDateRef(field.key, control)" within-modal :from="draft.workflowDates[field.key].from" :to="draft.workflowDates[field.key].to" @change="Object.assign(draft.workflowDates[field.key], $event)" />
          <input v-else :id="`sample-advanced-${field.key}`" class="form-control" disabled :value="`${draft.workflowDates[field.key].from} 至 ${draft.workflowDates[field.key].to}`" />
        </div>
        </div>
      </fieldset>
      </fieldset>
    </form>
    <template #footer>
      <div v-if="error" class="w-100"><ErrorNotice :error="error" :retry="!!error && canRetry(error)" :busy="busy" @retry="submit" /></div>
      <button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button>
      <button type="submit" form="sample-advanced-form" class="btn btn-primary" :disabled="busy"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span><i v-else class="ti ti-search me-1" aria-hidden="true"></i>{{ busy ? '查询中…' : '查询' }}</button>
    </template>
  </BootstrapModal>
</template>
