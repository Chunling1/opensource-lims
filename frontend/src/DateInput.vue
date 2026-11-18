<script setup lang="ts">
// Tabler 自带的 Litepicker 日期选择；v-model 仍以输入框文本为准（键盘录入与选择器结果一致）。
import Litepicker from '@tabler/core/dist/libs/litepicker/dist/litepicker.umd.js'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
const props = defineProps<{ modelValue: string; min?: string; max?: string; required?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const el = ref<HTMLInputElement>()
let picker: Litepicker | undefined
const limits = () => ({ minDate: props.min || null, maxDate: props.max || null })
onMounted(() => {
  picker = new Litepicker({
    element: el.value,
    format: 'YYYY-MM-DD',
    lang: 'zh-CN',
    autoApply: true,
    dropdowns: { minYear: 2000, maxYear: null, months: true, years: true },
    buttonText: {
      previousMonth: '<span aria-hidden="true">‹</span>',
      nextMonth: '<span aria-hidden="true">›</span>',
    },
    ...limits(),
  })
  picker.on('selected', (d) => emit('update:modelValue', d.format('YYYY-MM-DD')))
})
watch(() => [props.min, props.max], () => picker?.setOptions(limits()))
onBeforeUnmount(() => picker?.destroy())
</script>
<template>
  <input
    ref="el"
    class="form-control"
    inputmode="numeric"
    autocomplete="off"
    placeholder="YYYY-MM-DD"
    pattern="\d{4}-\d{2}-\d{2}"
    :required="required"
    :value="modelValue"
    @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>
