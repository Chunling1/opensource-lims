<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { createPopper, type Instance } from '@popperjs/core'

const props = defineProps<{ label: string; disabled?: boolean }>()
const id = useId(), button = ref<HTMLButtonElement>(), menu = ref<HTMLElement>(), open = ref(false)
const menuHost = ref<HTMLElement | string>('body')
let popper: Instance | undefined
let viewport: { width: number; height: number } | undefined
function close(restoreFocus = false) {
  open.value = false; popper?.destroy(); popper = undefined
  document.removeEventListener('click', outside)
  document.removeEventListener('scroll', scroll, true)
  window.removeEventListener('resize', resize)
  if (restoreFocus && button.value?.isConnected) button.value.focus()
}
function outside(event: MouseEvent) {
  const target = event.target as Node
  if (!button.value?.contains(target) && !menu.value?.contains(target)) close()
}
function scroll(event: Event) {
  if (event.target instanceof Node && menu.value?.contains(event.target)) return
  const rect = button.value?.getBoundingClientRect()
  const table = button.value?.closest('.table-responsive')?.getBoundingClientRect()
  // Popper follows visible anchors. Close only when the button leaves the viewport
  // or its scroll container, rather than treating queued layout scrolls as dismissal.
  if (rect && (rect.bottom <= 0 || rect.top >= innerHeight || rect.right <= Math.max(0, table?.left ?? 0) || rect.left >= Math.min(innerWidth, table?.right ?? innerWidth))) close()
}
function resize() { if (viewport && (innerWidth !== viewport.width || innerHeight !== viewport.height)) close() }
function items() { return [...(menu.value?.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)') ?? [])] }
function focusEdge(last: boolean) {
  const options = items(); (last ? options.at(-1) : options[0])?.focus({ preventScroll: true })
}
async function show(last = false, focusItem = true) {
  if (props.disabled) return
  if (open.value) { if (focusItem) focusEdge(last); return }
  // Keep modal menus inside its stacking and focus context, outside the table overflow.
  menuHost.value = button.value?.closest<HTMLElement>('.modal') || 'body'
  open.value = true
  await nextTick()
  if (!open.value || !button.value || !menu.value) return
  viewport = { width: innerWidth, height: innerHeight }
  // Use the template's dropdown classes and Bootstrap's existing positioning library.
  // Teleport prevents the table's overflow container from clipping the menu.
  const padding = { top: Math.max(0, document.getElementById('page-topbar')?.getBoundingClientRect().bottom ?? 0) + 8, right: 8, bottom: 8, left: 8 }
  popper = createPopper(button.value, menu.value, {
    placement: 'bottom-end', strategy: 'fixed',
    modifiers: [{ name: 'offset', options: { offset: [0, 4] } }, { name: 'preventOverflow', options: { boundary: 'viewport', padding, altAxis: true, tether: false } }, { name: 'flip', options: { padding } }],
  })
  await popper.update()
  if (!open.value) return
  // Pointer opening should not leave the first item permanently focus-highlighted.
  if (focusItem) focusEdge(last)
  document.addEventListener('click', outside)
  document.addEventListener('scroll', scroll, true)
  window.addEventListener('resize', resize)
}
function keydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true) }
  else if (event.key === 'Tab') close(true)
  else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
    event.preventDefault()
    const options = items(), index = options.indexOf(document.activeElement as HTMLElement)
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : index < 0 ? (event.key === 'ArrowUp' ? options.length - 1 : 0) : (index + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length
    options[next]?.focus({ preventScroll: true })
  }
}
watch(() => props.disabled, disabled => { if (disabled) close() })
onBeforeUnmount(() => close())
</script>

<template>
  <button :id="id" ref="button" type="button" class="btn btn-link p-0 text-decoration-none" :aria-label="label" title="更多操作" aria-haspopup="menu" :aria-controls="`${id}-menu`" :aria-expanded="open" :disabled="disabled" @click="open ? close(true) : show(false, $event.detail === 0)" @keydown.down.prevent="show()" @keydown.up.prevent="show(true)"><i class="ti ti-dots-vertical" aria-hidden="true"></i></button>
  <Teleport :to="menuHost"><div v-if="open" :id="`${id}-menu`" ref="menu" class="dropdown-menu dropdown-menu-end show" role="menu" :aria-labelledby="id" @keydown="keydown" @click.stop="close(true)"><slot /></div></Teleport>
</template>
