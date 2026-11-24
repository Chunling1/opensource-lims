<template>
  <div class="d-flex flex-column gap-1">
    <select v-model="precision" class="form-select form-select-sm" aria-label="生产日期精度" :disabled="disabled" @change="changePrecision">
      <option value="day">精确到日</option><option value="month">精确到月</option><option value="custom">不填日期</option>
    </select>
    <input v-if="precision === 'month'" class="form-control" type="month" aria-label="生产月份" :value="modelValue" :max="nextDate?.slice(0, 7)" :disabled="disabled" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)" />
    <input v-else-if="precision === 'custom'" class="form-control" type="text" aria-label="生产日期替代字符" :value="modelValue" :disabled="disabled" placeholder="输入替代字符，如 /、—，也可留空" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)" />
    <WorkflowDatePicker v-else :model-value="modelValue" :disabled="disabled" strict-order :next-date="nextDate" placeholder="选择生产日期" @update:model-value="emit('update:modelValue', $event)" />
    <small class="text-muted">{{ precision === 'custom' ? '填写的字符将原样显示在委托单和报告中。' : '可只填年月；不晚于抽样、送样及委托日期。' }}</small>
  </div>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import WorkflowDatePicker from './WorkflowDatePicker.vue'
import { isProductionDateMarker } from '@/composables/sampleDateRules'
const props = defineProps<{ modelValue?: string; nextDate?: string; disabled?: boolean; datePrecision?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; 'update:datePrecision': [value: string] }>()
function mode(value = '') {
  return isProductionDateMarker(value) ? 'custom' : /^\d{4}-\d{2}$/.test(value) ? 'month' : 'day'
}
const precision = ref(props.datePrecision || mode(props.modelValue))
watch(() => [props.modelValue, props.datePrecision], ([value, chosen]) => { if (chosen || value) precision.value = chosen || mode(value) })
function changePrecision() {
  emit('update:datePrecision', precision.value)
  // Changing to day precision needs a real user-selected day, not an invented 1st.
  emit('update:modelValue', precision.value === 'month' && !isProductionDateMarker(props.modelValue)
    ? (props.modelValue || '').slice(0, 7) : '')
}
</script>
