<script setup lang="ts" generic="Key extends string">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{
  tabs: readonly { key: Key; label: string; tabId?: string; panelId?: string; disabled?: boolean }[]
  modelValue: Key; label: string; idPrefix?: string; disabled?: boolean; variant?: 'tabs' | 'pills' | 'underline'
}>()
const emit = defineEmits<{ 'update:modelValue': [Key] }>()
const root = ref<HTMLElement>(), viewport = ref<HTMLElement>(), list = ref<HTMLElement>()
const overflow = ref(false), atStart = ref(true), atEnd = ref(true)
let observer: ResizeObserver | undefined, frame = 0, alive = true
const buttons = () => Array.from(list.value?.querySelectorAll<HTMLButtonElement>('[role="tab"]') || [])
function updateEdges() {
  const el = viewport.value
  if (!el) return
  atStart.value = el.scrollLeft <= 1
  atEnd.value = el.scrollLeft + el.clientWidth >= el.scrollWidth - 1
}
function revealActive() {
  const el = viewport.value, active = buttons().find(button => button.getAttribute('aria-selected') === 'true')
  if (!el || !active || !el.clientWidth) return
  const bounds = el.getBoundingClientRect(), target = active.getBoundingClientRect()
  if (target.left < bounds.left) el.scrollLeft += target.left - bounds.left
  else if (target.right > bounds.right) el.scrollLeft += target.right - bounds.right
  updateEdges()
}
function schedule() {
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(async () => {
    if (!root.value?.clientWidth) return
    // Compare against the full row, so showing arrows cannot cause oscillation.
    const width = buttons().reduce((total, button) => total + button.getBoundingClientRect().width, 0)
    overflow.value = width > root.value.clientWidth + 1
    await nextTick()
    if (alive) revealActive()
  })
}
function scroll(direction: number) {
  const el = viewport.value
  if (el) el.scrollLeft += direction * el.clientWidth * 0.75
  updateEdges()
}
function navigate(event: KeyboardEvent, key: Key) {
  if (props.disabled || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  const available = props.tabs.filter(tab => !tab.disabled)
  if (!available.length) return
  event.preventDefault()
  const index = available.findIndex(tab => tab.key === key)
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? available.length - 1 : (index + (event.key === 'ArrowLeft' ? -1 : 1) + available.length) % available.length
  emit('update:modelValue', available[next]!.key)
  void nextTick(() => buttons().find(button => button.getAttribute('aria-selected') === 'true')?.focus({ preventScroll: true }))
}
function observe() {
  observer?.disconnect()
  for (const element of [root.value, list.value, ...buttons()]) if (element) observer?.observe(element)
  schedule()
}
watch(() => props.modelValue, () => void nextTick(revealActive))
watch(() => props.tabs, () => void nextTick(observe), { deep: true })
onMounted(() => {
  observer = new ResizeObserver(schedule)
  observe()
  void document.fonts.ready.then(() => { if (alive) schedule() })
})
onBeforeUnmount(() => { alive = false; observer?.disconnect(); cancelAnimationFrame(frame) })
</script>
<template>
  <div ref="root" class="d-flex align-items-center gap-1" :class="variant === 'underline' ? 'mb-0' : 'mb-3'">
    <button v-if="overflow" class="btn btn-light btn-sm flex-shrink-0" type="button" :aria-label="`${label}：向左滚动标签`" :disabled="atStart" @click="scroll(-1)"><i class="ti ti-chevron-left fs-3" aria-hidden="true"></i></button>
    <!-- Keep focus outlines and the pills' 12px arrow inside the horizontal viewport. -->
    <div ref="viewport" class="col overflow-x-auto overflow-y-hidden pt-1" :class="variant === 'pills' ? 'pb-3' : 'pb-1'" @scroll.passive="updateEdges">
      <ul ref="list" class="nav flex-nowrap mb-0" :class="variant === 'pills' ? 'nav-pills arrow-navtabs nav-primary bg-light' : variant === 'underline' ? 'nav-tabs nav-tabs-custom nav-primary' : 'nav-tabs'" role="tablist" :aria-label="label">
        <li v-for="tab in tabs" :key="tab.key" class="nav-item flex-shrink-0" role="presentation"><button :id="tab.tabId || `${idPrefix}-tab-${tab.key}`" class="nav-link text-nowrap" :class="{ active: modelValue === tab.key, 'text-body': variant === 'underline' && modelValue !== tab.key }" type="button" role="tab" :tabindex="modelValue === tab.key ? 0 : -1" :disabled="disabled || tab.disabled" :aria-controls="tab.panelId || `${idPrefix}-panel-${tab.key}`" :aria-selected="modelValue === tab.key" @keydown="navigate($event, tab.key)" @click="emit('update:modelValue', tab.key)">{{ tab.label }}</button></li>
      </ul>
    </div>
    <button v-if="overflow" class="btn btn-light btn-sm flex-shrink-0" type="button" :aria-label="`${label}：向右滚动标签`" :disabled="atEnd" @click="scroll(1)"><i class="ti ti-chevron-right fs-3" aria-hidden="true"></i></button>
  </div>
</template>
