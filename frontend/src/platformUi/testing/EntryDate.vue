<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createPopper, type Instance } from '@popperjs/core'
const props = defineProps<{ modelValue: string; id: string; required?: boolean; disabled?: boolean; withinModal?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const input = ref<HTMLInputElement>(); let instance: { setDate: (value: string, trigger?: boolean) => void; destroy: () => void } | undefined
let popper: Instance | undefined
function positionInModal(picker: { calendarContainer: HTMLElement }) {
  if (!input.value) return
  popper?.destroy()
  popper = createPopper(input.value, picker.calendarContainer, {
    placement: 'bottom-start', strategy: 'fixed', modifiers: [
      { name: 'offset', options: { offset: [0, 4] } },
      { name: 'preventOverflow', options: { boundary: 'viewport', padding: 4 } },
      { name: 'flip', options: { padding: 4 } },
    ],
  })
  popper.forceUpdate()
}
onMounted(() => {
  const flatpickr = (window as unknown as { flatpickr: (element: HTMLElement, options: object) => typeof instance }).flatpickr
  instance = flatpickr(input.value!, {
    appendTo: props.withinModal ? input.value!.closest<HTMLElement>('.modal') ?? undefined : undefined,
    // Flatpickr's transform animation overrides Popper's coordinates while opening.
    ...(props.withinModal ? { position: positionInModal, disableMobile: true, animate: false } : {}),
    locale: 'zh', enableTime: props.id === 'trial-calibrationDate', enableSeconds: props.id === 'trial-calibrationDate', time_24hr: true, dateFormat: props.id === 'trial-calibrationDate' ? 'Y-m-d H:i:S' : 'Y-m-d', allowInput: true, defaultDate: props.modelValue || undefined,
    onChange: (_dates: Date[], value: string) => emit('update:modelValue', value),
    onClose: () => { popper?.destroy(); popper = undefined },
  })
})
watch(() => props.modelValue, value => instance?.setDate(value, false))
onBeforeUnmount(() => { popper?.destroy(); instance?.destroy() })
</script>
<template><input :id="id" ref="input" class="form-control" type="text" :value="modelValue" :required="required" :disabled="disabled" placeholder="YYYY-MM-DD" @change="emit('update:modelValue', ($event.target as HTMLInputElement).value)" /></template>
