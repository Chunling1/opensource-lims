<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
const props = defineProps<{ modelValue: string; id: string; required?: boolean; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
interface Picker {
  calendarContainer: HTMLElement; currentYear: number; currentYearElement: HTMLInputElement
  selectedDates: Date[]
  setDate: (value: string, trigger?: boolean) => void
  changeYear: (year: number) => void
  close: () => void; destroy: () => void
}
const input = ref<HTMLInputElement>()
let picker: Picker | undefined
let unbindYear: (() => void) | undefined
const valid = (value: string) => /^[1-9]\d{3}-(0[1-9]|1[0-2])$/.test(value)
// Keep the vendor month grid, using the same template theme utilities as other controls.
function decorateMonth(instance: Picker, month: HTMLElement & { dateObj: Date }) {
  const selected = instance.selectedDates.some(date => date.getFullYear() === instance.currentYear && date.getMonth() === month.dateObj.getMonth())
  month.setAttribute('role', 'button')
  month.setAttribute('aria-label', `${month.dateObj.getMonth() + 1}月`)
  month.setAttribute('aria-pressed', String(selected))
  month.classList.toggle('selected', selected)
  for (const name of ['bg-primary', 'border-primary', 'text-white']) month.classList.toggle(name, selected)
  month.classList.toggle('text-body', !selected)
}
function syncMonths(_dates: Date[], _value: string, instance: Picker) {
  instance.calendarContainer.querySelectorAll<HTMLElement & { dateObj: Date }>('.flatpickr-monthSelect-month').forEach(month => decorateMonth(instance, month))
}
onMounted(() => {
  const { flatpickr, monthSelectPlugin } = window as unknown as {
    flatpickr: (element: HTMLElement, options: object) => Picker
    monthSelectPlugin: (options: object) => unknown
  }
  picker = flatpickr(input.value!, {
    locale: 'zh', disableMobile: true, allowInput: false,
    minDate: '1000-01', maxDate: '9999-12', defaultDate: valid(props.modelValue) ? props.modelValue : undefined,
    plugins: [monthSelectPlugin({ dateFormat: 'Y-m', altFormat: 'Y-m' })],
    onReady: (dates: Date[], value: string, instance: Picker) => {
      instance.currentYearElement.setAttribute('aria-label', '年份')
      // The vendor plugin handles Enter as month selection even inside the year input.
      const confirmYear = (event: KeyboardEvent) => {
        if (event.key !== 'Enter') return
        event.preventDefault(); event.stopImmediatePropagation()
        const year = Number(instance.currentYearElement.value)
        if (Number.isInteger(year) && year >= 1000 && year <= 9999) instance.changeYear(year)
      }
      instance.currentYearElement.addEventListener('keydown', confirmYear, true)
      unbindYear = () => instance.currentYearElement.removeEventListener('keydown', confirmYear, true)
      instance.calendarContainer.querySelector('.flatpickr-prev-month')?.setAttribute('aria-label', '上一年')
      instance.calendarContainer.querySelector('.flatpickr-next-month')?.setAttribute('aria-label', '下一年')
      syncMonths(dates, value, instance)
    },
    onDayCreate: (_dates: Date[], _value: string, instance: Picker, day: HTMLElement & { dateObj: Date }) => {
      if (day.classList.contains('flatpickr-monthSelect-month')) decorateMonth(instance, day)
    },
    onYearChange: syncMonths,
    onValueUpdate: syncMonths,
    onChange: (_dates: Date[], value: string) => { if (!props.disabled && valid(value)) emit('update:modelValue', value) },
  })
})
watch(() => props.modelValue, value => picker?.setDate(valid(value) ? value : '', false))
watch(() => props.disabled, disabled => { if (disabled) picker?.close() })
onBeforeUnmount(() => { unbindYear?.(); picker?.destroy() })
</script>
<template>
  <input :id="id" ref="input" class="form-control" type="text" readonly :value="modelValue" :required="required" :disabled="disabled" placeholder="YYYY-MM" />
</template>
