<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import TableDropdown from './TableDropdown.vue'

export interface ToolbarAction { label: string; icon: string; hint?: string; disabled?: boolean; ariaLabel?: string; expanded?: boolean; controls?: string; busy?: boolean; haspopup?: 'dialog' }
const props = withDefaults(defineProps<{ label: string; actions: readonly ToolbarAction[]; count?: number; exportDisabled?: boolean; tableControls?: boolean }>(), { count: 0, exportDisabled: false, tableControls: true })
const emit = defineEmits<{ action: [index: number]; export: [selected: boolean]; columns: [] }>()
const root = ref<HTMLElement>(), primary = ref<HTMLElement>(), measure = ref<HTMLElement>()
const visible = ref(0), total = computed(() => props.actions.length + (props.tableControls ? 2 : 0))
let observer: ResizeObserver | undefined, frame = 0, disposed = false
function fit() {
  const element = root.value, parent = element?.parentElement, rail = measure.value
  if (!element || !parent || !rail) return
  const parentStyle = getComputedStyle(parent), gap = parseFloat(getComputedStyle(element).columnGap) || 0
  const parentGap = parseFloat(parentStyle.columnGap) || 0
  const siblings = [...parent.children].filter((node): node is HTMLElement => node instanceof HTMLElement && node !== element && !!node.getClientRects().length)
  const fullWidth = parent.clientWidth - parseFloat(parentStyle.paddingLeft) - parseFloat(parentStyle.paddingRight)
  const widths = [...rail.children].map(node => node.getBoundingClientRect().width)
  const moreWidth = widths.pop() || 0, primaryWidth = primary.value?.getBoundingClientRect().width || 0
  let available = fullWidth - siblings.reduce((sum, node) => sum + node.getBoundingClientRect().width + parentGap, 0)
  // If even the primary action and overflow cannot share the heading row, use
  // a full row below the heading. Buttons themselves always stay on one line.
  if (available < primaryWidth + gap + moreWidth) available = fullWidth
  let used = primaryWidth, count = 0
  for (let i = 0; i < widths.length; i++) {
    const next = used + (i || primary.value ? gap : 0) + widths[i]!
    const overflow = i < widths.length - 1 ? gap + moreWidth : 0
    if (next + overflow > available - 1) break
    used = next; count++
  }
  visible.value = count
}
function schedule() { if (!disposed) { cancelAnimationFrame(frame); frame = requestAnimationFrame(fit) } }
function observeLayout() {
  // Action labels and permissions can replace measured nodes. Release old
  // observations before tracking the current heading, primary and actions.
  observer?.disconnect()
  const parent = root.value?.parentElement
  if (parent) { observer?.observe(parent); for (const child of parent.children) if (child !== root.value) observer?.observe(child) }
  if (primary.value) observer?.observe(primary.value)
  if (measure.value) for (const child of measure.value.children) observer?.observe(child)
}
onMounted(() => {
  observer = new ResizeObserver(schedule)
  observeLayout()
  void document.fonts.ready.then(schedule)
  schedule()
})
watch(() => [props.actions, props.tableControls], async () => {
  await nextTick()
  if (disposed) return
  observeLayout()
  schedule()
}, { deep: true })
const attributes = (action: ToolbarAction) => ({ disabled: action.disabled, title: action.hint, 'aria-label': action.ariaLabel, 'aria-expanded': action.expanded, 'aria-controls': action.controls, 'aria-busy': action.busy, 'aria-haspopup': action.haspopup })
onBeforeUnmount(() => { disposed = true; observer?.disconnect(); cancelAnimationFrame(frame) })
</script>
<template>
  <div ref="root" class="d-flex align-items-center gap-2 flex-nowrap position-relative flex-shrink-0" :aria-label="`${label}工具栏`" role="group">
    <div v-if="$slots.default" ref="primary" class="d-flex align-items-center gap-2 flex-shrink-0"><slot /></div>
    <button v-for="(action, index) in actions.slice(0, visible)" :key="index" type="button" class="btn btn-light text-nowrap" v-bind="attributes(action)" @click="emit('action', index)"><i :class="action.icon" class="me-1" aria-hidden="true"></i>{{ action.label }}<span v-if="action.busy" class="spinner-border spinner-border-sm ms-1" aria-hidden="true"></span></button>
    <TableDropdown v-if="tableControls && visible > actions.length" :key="`export-${visible}`" label="导出" :disabled="exportDisabled"><button class="dropdown-item" @click="emit('export', false)">导出查询结果</button><button class="dropdown-item" :disabled="!count" @click="emit('export', true)">导出已选记录（{{ count }}）</button></TableDropdown>
    <button v-if="tableControls && visible === total" type="button" class="btn btn-light text-nowrap" aria-haspopup="dialog" @click="emit('columns')"><i class="ti ti-layout-columns me-1" aria-hidden="true"></i>显示</button>
    <TableDropdown v-if="visible < total" :key="`more-${visible}`" :label="`${label}更多操作`" icon-only>
      <button v-for="(action, index) in actions.slice(visible)" :key="index" type="button" class="dropdown-item" v-bind="attributes(action)" @click="emit('action', visible + index)"><i :class="action.icon" class="me-2" aria-hidden="true"></i>{{ action.label }}<span v-if="action.busy" class="spinner-border spinner-border-sm ms-1" aria-hidden="true"></span></button>
      <div v-if="tableControls && visible < actions.length" class="dropdown-divider"></div>
      <template v-if="tableControls && visible <= actions.length">
        <button class="dropdown-item" :disabled="exportDisabled" @click="emit('export', false)"><i class="ti ti-download me-2" aria-hidden="true"></i>导出查询结果</button>
        <button class="dropdown-item" :disabled="exportDisabled || !count" @click="emit('export', true)"><i class="ti ti-download me-2" aria-hidden="true"></i>导出已选记录（{{ count }}）</button>
        <div class="dropdown-divider"></div>
      </template>
      <button v-if="tableControls" class="dropdown-item" @click="emit('columns')"><i class="ti ti-layout-columns me-2" aria-hidden="true"></i>显示</button>
    </TableDropdown>
    <!-- Inert, clipped measuring copies retain natural widths even when the
         corresponding real actions have moved into the overflow menu. -->
    <div class="position-absolute top-0 start-0 w-100 overflow-hidden invisible pe-none" aria-hidden="true" inert>
      <div ref="measure" class="d-flex flex-nowrap">
        <span v-for="(action, index) in actions" :key="index" class="btn btn-light text-nowrap flex-shrink-0"><i :class="action.icon" class="me-1"></i>{{ action.label }}<span v-if="action.busy" class="spinner-border spinner-border-sm ms-1"></span></span>
        <span v-if="tableControls" class="btn btn-light dropdown-toggle text-nowrap flex-shrink-0">导出</span>
        <span v-if="tableControls" class="btn btn-light text-nowrap flex-shrink-0"><i class="ti ti-layout-columns me-1"></i>显示</span>
        <span class="btn btn-light btn-icon flex-shrink-0"><i class="ti ti-dots"></i></span>
      </div>
    </div>
  </div>
</template>
