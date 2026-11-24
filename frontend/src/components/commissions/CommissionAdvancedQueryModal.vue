<script setup lang="ts">
import { ref } from 'vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { canRetry, type ErrorValue } from '../../services/common/errors'
import BootstrapModal from '../common/BootstrapModal.vue'
import TemplateDateRange from '../common/TemplateDateRange.vue'
import { commissionStates } from '../../services/commissions/registrationService'
import FormControl from '../forms/FormControl.vue'
import { commissionAdvancedFields, type CommissionAdvancedDraft, type CommissionAdvancedFields } from '../../types/commissions/commissionAdvancedQuery'
import type { FormField } from '../../types/forms'
const props = defineProps<{ initial: CommissionAdvancedDraft; busy?: boolean; error?: ErrorValue }>()
const emit = defineEmits<{ close: []; search: [CommissionAdvancedDraft] }>()
const draft = ref<CommissionAdvancedDraft>({ ...props.initial, fields: { ...props.initial.fields } })
const dateRange = ref<InstanceType<typeof TemplateDateRange>>()
const fields: FormField<CommissionAdvancedFields>[] = commissionAdvancedFields.map(({ key, label }) => ({
  id: `commission-advanced-${key}`, label, control: 'text', maxlength: 200,
  binding: { get: model => model[key] || '', set: (model, value) => { model[key] = value } },
}))
function submit() {
  if (props.busy) return
  if (draft.value.useDate && !dateRange.value?.validate()) return
  emit('search', { ...draft.value, fields: Object.fromEntries(Object.entries(draft.value.fields).map(([key, value]) => [key, value?.trim() || ''])) })
}
</script>
<template>
  <BootstrapModal open :busy="busy" title="委托高级查询" size="lg" scrollable fullscreen-mobile @close="emit('close')">
    <form :aria-busy="busy" id="commission-advanced-form" aria-label="委托高级查询条件" @submit.prevent="submit">
      <fieldset :disabled="busy">
      <div class="row g-3">
        <div v-for="field in fields" :key="field.id" class="col-12 col-md-6 col-lg-4">
          <label :for="field.id" class="form-label">{{ field.label }}</label>
          <FormControl :field="field" :model="draft.fields" />
        </div>
        <div class="col-12 col-md-6 col-lg-4">
          <label for="commission-advanced-status" class="form-label">委托状态</label>
          <select id="commission-advanced-status" v-model="draft.status" class="form-select"><option value="">全部状态</option><option v-for="status in commissionStates" :key="status" :value="status">{{ status }}</option></select>
        </div>
        <div class="col-12 col-md-8">
          <div class="form-check mb-2"><input id="commission-advanced-use-date" v-model="draft.useDate" class="form-check-input" type="checkbox" /><label class="form-check-label" for="commission-advanced-use-date">按委托日期查询</label></div>
          <label for="commission-advanced-date" class="visually-hidden">委托日期</label>
          <TemplateDateRange v-if="draft.useDate" id="commission-advanced-date" ref="dateRange" within-modal :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" />
          <input v-else id="commission-advanced-date" class="form-control" disabled :value="`${draft.from} 至 ${draft.to}`" />
        </div>
      </div>
      </fieldset>
    </form>
    <template #footer>
      <div v-if="error" class="w-100"><ErrorNotice :error="error" :retry="!!error && canRetry(error)" :busy="busy" @retry="submit" /></div>
      <button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button>
      <button type="submit" form="commission-advanced-form" class="btn btn-primary" :disabled="busy"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span><i v-else class="ti ti-search me-1" aria-hidden="true"></i>{{ busy ? '查询中…' : '查询' }}</button>
    </template>
  </BootstrapModal>
</template>
