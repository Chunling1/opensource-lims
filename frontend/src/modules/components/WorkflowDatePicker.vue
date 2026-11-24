<template>
  <div >
    <FlatDatePicker
      v-bind="$attrs"
      :model-value="modelValue"
      :clearable="clearable"
      :disabled="disabled || previousMissing"
      :disabled-date="disabledDate"
      :placeholder="previousMissing ? '前序流程日期缺失，暂不能选择' : placeholder"
      
      @update:model-value="updateValue"
    />
    <small v-if="previousMissing" class="text-muted small">
      {{ missingPreviousReason }}
    </small>
    <small v-else-if="orderError" class="text-muted small" role="alert">{{ orderError }}</small>
  </div>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue'
import FlatDatePicker from '@/components/FlatDatePicker.vue'
import { isWorkflowDateBefore, isWorkflowDateValid, useWorkflowDatePolicy } from '@/composables/workflowDate'

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  modelValue?: string | null
  previousDate?: string | null
  nextDate?: string | null
  strictOrder?: boolean
  requirePrevious?: boolean
  disabled?: boolean
  clearable?: boolean
  placeholder?: string
  missingPreviousReason?: string
}>(), {
  modelValue: '',
  previousDate: '',
  nextDate: '',
  strictOrder: false,
  requirePrevious: false,
  disabled: false,
  clearable: true,
  placeholder: '选择日期',
  missingPreviousReason: '前序流程尚未形成有效日期，请先完成上一流程。',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const { disabledDate, previousMissing } = useWorkflowDatePolicy(
  toRef(props, 'previousDate'),
  toRef(props, 'requirePrevious'),
  toRef(props, 'nextDate'),
  toRef(props, 'strictOrder'),
)

const orderError = computed(() => {
  if (!props.strictOrder || !props.modelValue) return ''
  if (!isWorkflowDateValid(props.modelValue)) return '请填写有效日期'
  if (isWorkflowDateBefore(props.modelValue, props.previousDate)) return `日期不得早于 ${props.previousDate}`
  if (isWorkflowDateBefore(props.nextDate, props.modelValue)) return `日期不得晚于 ${props.nextDate}`
  return ''
})

function updateValue(value: string | string[] | null) {
  emit('update:modelValue', Array.isArray(value) ? (value[0] ?? '') : (value ?? ''))
}
</script>


