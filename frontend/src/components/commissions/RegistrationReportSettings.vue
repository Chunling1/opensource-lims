<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TemplateToast from '../common/TemplateToast.vue'
import type { ErrorValue } from '../../services/common/errors'
import { allowedReportOptions, changeReportSetting, reportSettingsIssues } from '../../services/commissions/reportSettings'
import { reportSettingFields, type ReportSettings, type ReportSettingsConfig, type ReportSettingKey } from '../../types/commissions/reportSettings'

const props = defineProps<{ modelValue: ReportSettings; config?: ReportSettingsConfig; loading: boolean; error: ErrorValue; readonly?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [ReportSettings]; retry: [] }>()
const toast = ref<InstanceType<typeof TemplateToast>>(), message = ref('')
const visibleFields = reportSettingFields.filter(field => field.key !== 'layoutId')
const issues = computed(() => props.config ? reportSettingsIssues(props.config, props.modelValue) : {})
const allowed = (key: ReportSettingKey) => props.config ? allowedReportOptions(props.config, props.modelValue, key) : []
function locked(key: ReportSettingKey) { const values = allowed(key); return props.readonly || props.loading || !props.config || values.length === 1 && values[0] === props.modelValue[key] }
async function change(key: ReportSettingKey, event: Event) {
  if (!props.config || props.readonly) return
  const result = changeReportSetting(props.config, props.modelValue, key, (event.target as HTMLSelectElement).value)
  emit('update:modelValue', result.value)
  if (result.changes.length) { message.value = `已调整报告设置：${result.changes.join('；')}。`; await nextTick(); toast.value?.show() }
}
</script>
<template>
  <div aria-label="报告设置选项">
    <ErrorNotice :error="error" retry :busy="loading" @retry="emit('retry')" />
    <p v-if="loading" class="text-muted" role="status">正在加载报告设置…</p>
    <div class="row g-3">
      <div v-for="field in visibleFields" :key="field.key" class="col-md-6 col-xl-4">
        <label class="form-label" :for="`report-setting-${field.key}`">{{ field.label }}</label>
        <select :id="`report-setting-${field.key}`" class="form-select" :class="{ 'is-invalid': issues[field.key] }" :value="modelValue[field.key]" :disabled="locked(field.key)" :aria-invalid="!!issues[field.key]" :aria-describedby="issues[field.key] ? `report-setting-error-${field.key}` : undefined" @change="change(field.key, $event)">
          <option value="">请选择</option>
          <option v-if="modelValue[field.key] && !config?.options[field.key].some(option => option.id === modelValue[field.key])" :value="modelValue[field.key]" disabled>已失效选项（{{ modelValue[field.key] }}）</option>
          <option v-for="option in config?.options[field.key] || []" :key="option.id" :value="option.id" :disabled="!allowed(field.key).includes(option.id)">{{ option.label }}</option>
        </select>
        <div v-if="issues[field.key]" :id="`report-setting-error-${field.key}`" class="invalid-feedback">{{ issues[field.key] }}</div>
      </div>
    </div>
    <TemplateToast ref="toast" :message="message" />
  </div>
</template>
