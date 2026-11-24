import type { Directive } from 'vue'
import Tooltip from 'bootstrap/js/dist/tooltip'
import Popover from 'bootstrap/js/dist/popover'

export const vTooltip: Directive<HTMLElement, string> = {
  mounted(element, binding) { new Tooltip(element, { title: binding.value, container: 'body', trigger: 'hover focus' }) },
  updated(element, binding) { if (binding.value !== binding.oldValue) Tooltip.getInstance(element)?.setContent({ '.tooltip-inner': binding.value }) },
  beforeUnmount(element) { Tooltip.getInstance(element)?.dispose() }
}
export const vPopover: Directive<HTMLElement, string> = {
  mounted(element, binding) { new Popover(element, { content: binding.value, container: 'body', trigger: 'focus', placement: 'top', title: '操作说明' }) },
  updated(element, binding) { if (binding.value !== binding.oldValue) Popover.getInstance(element)?.setContent({ '.popover-body': binding.value }) },
  beforeUnmount(element) { Popover.getInstance(element)?.dispose() }
}
