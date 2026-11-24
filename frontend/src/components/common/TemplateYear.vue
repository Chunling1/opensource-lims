<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useAttrs, watch } from 'vue'
import { createPopper, type Instance } from '@popperjs/core'
import { clientToday } from '../../services/common/date'

defineOptions({ inheritAttrs: false })
const props = withDefaults(defineProps<{ id: string; modelValue: number | ''; required?: boolean; disabled?: boolean; min?: number; max?: number }>(), { min: 1000, max: 9999 })
const emit = defineEmits<{ 'update:modelValue': [number] }>()
const attrs = useAttrs(), input = ref<HTMLInputElement>(), panel = ref<HTMLElement>()
const target = ref<HTMLElement | string>('body'), open = ref(false), start = ref(2000)
const currentYear = Number(clientToday().slice(0, 4))
const years = computed(() => Array.from({ length: Math.min(12, props.max - start.value + 1) }, (_, index) => start.value + index))
let popper: Instance | undefined
const clamp = (year: number) => Math.max(props.min, Math.min(props.max, year))
function showPage(year: number) { start.value = props.min + Math.floor((clamp(year) - props.min) / 12) * 12 }
function close(restoreFocus = false) {
  open.value = false; popper?.destroy(); popper = undefined
  if (restoreFocus) input.value?.focus()
}
async function focusYear(year: number) {
  await nextTick()
  panel.value?.querySelector<HTMLButtonElement>(`[data-year="${year}"]`)?.focus()
}
async function show() {
  if (props.disabled || open.value) return
  const year = clamp(props.modelValue || currentYear)
  showPage(year); open.value = true
  await nextTick()
  if (!open.value || !input.value || !panel.value) return
  // Use the same viewport-aware positioning as the date picker, inside modal focus traps.
  popper = createPopper(input.value, panel.value, {
    placement: 'bottom-start', strategy: 'fixed', modifiers: [
      { name: 'offset', options: { offset: [0, 4] } },
      { name: 'preventOverflow', options: { boundary: 'viewport', padding: 8 } },
      { name: 'flip', options: { padding: 8 } },
    ],
  })
  popper.forceUpdate(); await focusYear(year)
}
async function select(year: number) {
  if (props.disabled) return
  emit('update:modelValue', year)
  await nextTick()
  input.value?.dispatchEvent(new Event('change', { bubbles: true }))
  close(true)
}
function movePage(offset: number) { showPage(start.value + offset); void nextTick(() => popper?.update()) }
function navigate(event: KeyboardEvent, year: number) {
  const offset = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -3, ArrowDown: 3, PageUp: -12, PageDown: 12 }[event.key]
  if (offset === undefined) return
  event.preventDefault(); event.stopPropagation()
  const next = clamp(year + offset)
  showPage(next); void focusYear(next)
}
function outside(event: Event) {
  if (open.value && event.target instanceof Node && event.target !== input.value && !panel.value?.contains(event.target)) close()
}
onMounted(() => {
  target.value = input.value?.closest<HTMLElement>('.modal, .offcanvas') || 'body'
  document.addEventListener('pointerdown', outside, true)
  document.addEventListener('focusin', outside)
})
watch(() => props.disabled, disabled => { if (disabled) close() })
watch(() => props.modelValue, year => { if (open.value) showPage(year || currentYear) })
onBeforeUnmount(() => {
  popper?.destroy()
  document.removeEventListener('pointerdown', outside, true)
  document.removeEventListener('focusin', outside)
})
</script>
<template>
  <input v-bind="attrs" :id="id" ref="input" type="text" class="form-control" readonly :value="modelValue" :required="required" :disabled="disabled" placeholder="YYYY" aria-haspopup="dialog" :aria-expanded="open" :aria-controls="`${id}-picker`" @click="show" @keydown.enter.prevent="show" @keydown.space.prevent="show" @keydown.down.prevent="show" />
  <Teleport :to="target">
    <!-- Reuse the template calendar surface; this is a year-only selector, not a Flatpickr plugin. -->
    <div v-if="open" :id="`${id}-picker`" ref="panel" class="flatpickr-calendar open p-2" role="dialog" aria-label="选择年度" @keydown.esc.stop.prevent="close(true)">
      <div class="d-flex align-items-center justify-content-between mb-2">
        <button type="button" class="btn btn-sm btn-light" aria-label="上一组年份" :disabled="start <= min" @click="movePage(-12)"><i class="ti ti-chevron-left" aria-hidden="true"></i></button>
        <span class="fw-semibold" aria-live="polite">{{ start }} – {{ years[years.length - 1] }}</span>
        <button type="button" class="btn btn-sm btn-light" aria-label="下一组年份" :disabled="start + 12 > max" @click="movePage(12)"><i class="ti ti-chevron-right" aria-hidden="true"></i></button>
      </div>
      <div class="row g-1">
        <div v-for="year in years" :key="year" class="col-4"><button type="button" class="btn btn-sm w-100 py-2" :class="year === modelValue ? 'btn-primary' : 'btn-light'" :data-year="year" :aria-pressed="year === modelValue" @click="select(year)" @keydown="navigate($event, year)">{{ year }}</button></div>
      </div>
      <div class="border-top mt-2 pt-2 text-center"><button type="button" class="btn btn-sm btn-link" :disabled="currentYear < min || currentYear > max" @click="select(currentYear)">今年</button></div>
    </div>
  </Teleport>
</template>
