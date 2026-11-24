import { onBeforeUnmount, provide, watch, type InjectionKey, type Ref } from 'vue'
import { isValidatableControl } from './formValidation'

type Control = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
export const dialogValidationKey: InjectionKey<{ show: (fields: Record<string, string>) => string[] }> = Symbol('dialog-validation')

// One adapter for native constraints and explicit API field keys in existing dialogs.
// It owns only the feedback nodes it creates; existing Vue field feedback stays intact.
export function useDialogValidation(root: Ref<HTMLElement | undefined>) {
  const hints = new Map<Control, { node: HTMLElement; describedBy: string | null; invalid: string | null; marked: boolean }>()
  let focusFrame = 0, first: Control | undefined
  function clear(control: Control) {
    const hint = hints.get(control)
    if (!hint) return
    hint.node.remove()
    if (!hint.marked) control.classList.remove('is-invalid')
    if (hint.invalid === null) control.removeAttribute('aria-invalid'); else control.setAttribute('aria-invalid', hint.invalid)
    if (hint.describedBy === null) control.removeAttribute('aria-describedby'); else control.setAttribute('aria-describedby', hint.describedBy)
    hints.delete(control)
  }
  function clearAll() {
    cancelAnimationFrame(focusFrame); first = undefined
    for (const control of hints.keys()) clear(control)
  }
  function focus(control: Control) {
    if (first) return
    first = control
    focusFrame = requestAnimationFrame(() => {
      const target = first; first = undefined
      if (target?.isConnected) { target.scrollIntoView({ block: 'center' }); target.focus({ preventScroll: true }) }
    })
  }
  function show(control: Control, message: string) {
    clear(control)
    const node = document.createElement('div')
    node.id = `${control.id || 'field'}-validation-${crypto.randomUUID().slice(0, 8)}`
    node.className = 'invalid-feedback d-block'; node.setAttribute('role', 'alert'); node.dataset.fieldFeedback = ''
    node.textContent = message
    const hint = { node, describedBy: control.getAttribute('aria-describedby'), invalid: control.getAttribute('aria-invalid'), marked: control.classList.contains('is-invalid') }
    hints.set(control, hint)
    control.classList.add('is-invalid'); control.setAttribute('aria-invalid', 'true')
    control.setAttribute('aria-describedby', [hint.describedBy, node.id].filter(Boolean).join(' '))
    const anchor = control.closest('[data-field-control], .input-group') || control
    anchor.after(node)
    focus(control)
  }
  function own(control: Control) { return control.closest('.modal, .offcanvas') === root.value }
  function invalid(event: Event) {
    if (!isValidatableControl(event.target) || !own(event.target)) return
    event.preventDefault()
    const control = event.target
    const label = control.getAttribute('aria-label') || control.labels?.[0]?.textContent?.replace(/\s*\*\s*$/, '').trim() || '此项'
    const message = control.validity.valueMissing ? `${control instanceof HTMLSelectElement ? '请选择' : '请填写'}${label}。` : control.validationMessage
    show(control, message)
  }
  function edited(event: Event) {
    if (!isValidatableControl(event.target) || !own(event.target)) return
    const group = event.target.closest('[data-field-control]')
    // Multi-checkbox fields share one feedback message; editing any option clears it.
    if (group) for (const control of hints.keys()) if (group.contains(control)) clear(control)
    clear(event.target)
  }
  const api = { show(fields: Record<string, string>) {
    for (const control of hints.keys()) if (!control.isConnected) clear(control)
    const controls = [...root.value?.querySelectorAll<Control>('input, select, textarea') || []].filter(control => own(control) && !control.matches(':disabled') && control.getClientRects().length)
    const applied: string[] = []
    // DOM order puts focus on the first field, rather than the order of API keys.
    for (const control of controls) {
      const key = control.dataset.validationKey || control.closest<HTMLElement>('[data-validation-key]')?.dataset.validationKey || control.name || control.id
      if (!key || !fields[key] || applied.includes(key)) continue
      show(control, fields[key]); applied.push(key)
    }
    return applied
  } }
  provide(dialogValidationKey, api)
  watch(root, (element, _old, cleanup) => {
    if (!element) return
    element.addEventListener('invalid', invalid, true)
    element.addEventListener('input', edited, true); element.addEventListener('change', edited, true)
    element.addEventListener('hidden.bs.modal', clearAll); element.addEventListener('hidden.bs.offcanvas', clearAll)
    cleanup(() => {
      element.removeEventListener('invalid', invalid, true)
      element.removeEventListener('input', edited, true); element.removeEventListener('change', edited, true)
      element.removeEventListener('hidden.bs.modal', clearAll); element.removeEventListener('hidden.bs.offcanvas', clearAll)
    })
  }, { flush: 'post' })
  onBeforeUnmount(clearAll)
}
