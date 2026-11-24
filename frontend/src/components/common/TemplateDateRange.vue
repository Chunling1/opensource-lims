<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createPopper, type Instance } from '@popperjs/core'
const props = defineProps<{ id: string; from: string; to: string; withinModal?: boolean; disabled?: boolean; allowPartial?: boolean; placeholder?: string }>()
const emit = defineEmits<{ change: [{ from: string; to: string }] }>()
interface Picker { setDate: (dates: string[], trigger?: boolean) => void; destroy: () => void; open: () => void; close: () => void; formatDate: (date: Date, format: string) => string }
const input = ref<HTMLInputElement>(), error = ref('')
let instance: Picker | undefined, pending = false, pendingDate = ''
let popper: Instance | undefined
function positionInModal(picker: { calendarContainer: HTMLElement }) {
  if (!input.value) return
  popper?.destroy()
  // Flatpickr's page offsets do not account for a scrolling fixed modal.
  // Keep its calendar inside the focus trap and use Bootstrap's positioning library.
  popper = createPopper(input.value, picker.calendarContainer, {
    placement: 'bottom-start', strategy: 'fixed',
    modifiers: [
      { name: 'offset', options: { offset: [0, 4] } },
      { name: 'preventOverflow', options: { boundary: 'viewport', padding: 4 } },
      { name: 'flip', options: { padding: 4 } },
    ],
  })
  popper.forceUpdate()
}
function sync() {
  pending = !!(props.allowPartial && props.from && !props.to); pendingDate = pending ? props.from : ''; error.value = ''
  const day = (value: string) => value.match(/^\d{4}-\d{2}-\d{2}/)?.[0] || value
  const from = day(props.from), to = day(props.to)
  instance?.setDate([from, to].filter(Boolean), false)
  if (input.value) input.value.value = from || to ? `${from} 至 ${to}` : ''
}
function validate() {
  if (props.disabled) return true
  if (!pending) return true
  error.value = '请选择结束日期。'
  if (input.value?.getClientRects().length) { input.value.focus(); instance?.open() }
  return false
}
onMounted(() => {
  const flatpickr = (window as unknown as { flatpickr: (element: HTMLElement, options: object) => Picker }).flatpickr
  instance = flatpickr(input.value!, {
    appendTo: props.withinModal ? input.value!.closest<HTMLElement>('.modal') ?? undefined : undefined,
    // Flatpickr's transform animation overrides Popper's coordinates while opening.
    ...(props.withinModal ? { position: positionInModal, animate: false } : {}),
    locale: 'zh', mode: 'range', dateFormat: 'Y-m-d', ariaDateFormat: 'Y-m-d', disableMobile: true,
    onChange: (dates: Date[]) => {
      if (props.disabled) { sync(); return }
      error.value = ''; pending = dates.length === 1
      pendingDate = pending ? instance!.formatDate(dates[0]!, 'Y-m-d') : ''
      if (dates.length === 2) emit('change', { from: instance!.formatDate(dates[0]!, 'Y-m-d'), to: instance!.formatDate(dates[1]!, 'Y-m-d') })
      else if (pending && props.allowPartial) emit('change', { from: pendingDate, to: '' })
      else if (!dates.length) sync()
    },
    onClose: () => {
      popper?.destroy(); popper = undefined
      if (pending && !props.allowPartial) error.value = '请选择结束日期。'
      // Flatpickr clears an unfinished range after an outside click. Preserve it
      // so reopening the picker can finish the range instead of losing the start.
      queueMicrotask(() => { if (pending && pendingDate) instance?.setDate([pendingDate], false) })
    },
  })
  sync()
})
watch(() => [props.from, props.to], () => {
  if (props.allowPartial && pending && props.from === pendingDate && !props.to) return
  sync()
})
watch(() => props.disabled, disabled => { if (disabled) { sync(); instance?.close() } })
onBeforeUnmount(() => { popper?.destroy(); popper = undefined; instance?.destroy(); instance = undefined })
function clear() {
  if (props.disabled) return
  pending = false; pendingDate = ''; error.value = ''
  instance?.setDate([], false); instance?.close()
  if (input.value) input.value.value = ''
  emit('change', { from: '', to: '' })
}
defineExpose({ validate, clear })
</script>
<template>
  <input :id="id" ref="input" class="form-control" :class="{ 'is-invalid': error, 'bg-body-tertiary text-muted': disabled }" type="text" readonly :disabled="disabled" :placeholder="placeholder || '请选择开始和结束日期'" size="25" :aria-invalid="!!error" :aria-describedby="error ? `${id}-error` : undefined" @keydown.enter.prevent @keydown.delete.capture.stop.prevent @keydown.backspace.capture.stop.prevent />
  <div v-if="error" :id="`${id}-error`" class="invalid-feedback d-block" role="alert">{{ error }}</div>
</template>
