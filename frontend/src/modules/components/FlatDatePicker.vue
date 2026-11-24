<template>
    <input
      v-bind="$attrs"
      ref="input"
      class="form-control"
      type="text"
      :disabled="disabled"
      :placeholder="displayPlaceholder"
      autocomplete="off"
      @change="clearTypedValue"
    />
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import flatpickr from 'flatpickr'
import { Mandarin } from 'flatpickr/dist/l10n/zh.js'
import type { Instance } from 'flatpickr/dist/types/instance'
import type { Options } from 'flatpickr/dist/types/options'

defineOptions({ inheritAttrs: false })

type DateValue = string | string[]

const props = withDefaults(defineProps<{
  modelValue?: DateValue | null
  mode?: 'date' | 'datetime' | 'range'
  disabled?: boolean
  clearable?: boolean
  placeholder?: string
  startPlaceholder?: string
  endPlaceholder?: string
  disabledDate?: (date: Date) => boolean
}>(), {
  modelValue: '',
  mode: 'date',
  disabled: false,
  clearable: true,
  placeholder: '选择日期',
  startPlaceholder: '开始日期',
  endPlaceholder: '结束日期',
  disabledDate: undefined,
})

const emit = defineEmits<{
  'update:modelValue': [value: DateValue]
  change: [value: DateValue]
}>()

const input = ref<HTMLInputElement>()
let picker: Instance | null = null
let syncing = false

const displayPlaceholder = computed(() => (
  props.mode === 'range'
    ? `${props.startPlaceholder} 至 ${props.endPlaceholder}`
    : props.placeholder
))

function formatDate(date: Date, withTime = false) {
  const year = date.getFullYear().toString().padStart(4, '0')
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  if (!withTime) return `${year}-${month}-${day}`
  const hour = date.getHours().toString().padStart(2, '0')
  const minute = date.getMinutes().toString().padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

function pickerOptions(): Partial<Options> {
  const isDateTime = props.mode === 'datetime'
  return {
    locale: Mandarin,
    mode: props.mode === 'range' ? 'range' : 'single',
    enableTime: isDateTime,
    time_24hr: true,
    minuteIncrement: 1,
    dateFormat: isDateTime ? 'Y-m-d H:i' : 'Y-m-d',
    allowInput: true,
    clickOpens: !props.disabled,
    disable: props.disabledDate ? [(date: Date) => props.disabledDate?.(date) ?? false] : [],
    onChange: (selectedDates: Date[]) => {
      if (syncing) return
      if (props.mode === 'range') {
        if (selectedDates.length !== 2) return
        const value = selectedDates.map((date) => formatDate(date))
        emit('update:modelValue', value)
        emit('change', value)
        return
      }
      const value = selectedDates[0] ? formatDate(selectedDates[0], isDateTime) : ''
      emit('update:modelValue', value)
      emit('change', value)
    },
    onClose: (selectedDates: Date[]) => {
      if (props.mode === 'range' && selectedDates.length === 1) {
        picker?.clear(false)
        emit('update:modelValue', [])
        emit('change', [])
      }
    },
  }
}

function syncValue() {
  if (!picker) return
  syncing = true
  const value = props.modelValue
  if (Array.isArray(value)) picker.setDate(value, false)
  else if (value) picker.setDate(value, false)
  else picker.clear(false)
  // An upstream date change may make a saved value invalid. Keep it visible
  // for correction instead of showing blank while the model still holds it.
  if (typeof value === 'string' && value && input.value && !picker.selectedDates.length) input.value.value = value
  nextTick(() => { syncing = false })
}

function clearValue() {
  picker?.clear(false)
  const value: DateValue = props.mode === 'range' ? [] : ''
  emit('update:modelValue', value)
  emit('change', value)
}

// TemplateDate is a single editable input. Clearing its text preserves the
// platform's range/scalar value contract without adding a custom clear button.
function clearTypedValue(event: Event) {
  if (props.clearable && !props.disabled && !(event.target as HTMLInputElement).value.trim()) clearValue()
}

onMounted(() => {
  if (!input.value) return
  picker = flatpickr(input.value, pickerOptions())
  syncValue()
})

watch(() => props.modelValue, syncValue, { deep: true })
watch(
  () => [props.disabled, props.disabledDate] as const,
  () => {
    if (!picker) return
    picker.set('clickOpens', !props.disabled)
    picker.set(
      'disable',
      props.disabledDate ? [(date: Date) => props.disabledDate?.(date) ?? false] : [],
    )
    if (input.value) input.value.disabled = props.disabled
    syncValue()
  },
)

onBeforeUnmount(() => {
  picker?.destroy()
  picker = null
})
</script>




