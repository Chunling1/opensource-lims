import Offcanvas from 'bootstrap/js/dist/offcanvas'

let active: ManagedOffcanvas | undefined
let pending: ManagedOffcanvas | undefined

/** Serialize Bootstrap transitions so focus traps, backdrops and scroll locks never overlap. */
export class ManagedOffcanvas {
  private instance: Offcanvas
  private phase: 'hidden' | 'opening' | 'shown' | 'closing' = 'hidden'
  private closingRequested = false
  private disposed = false
  private opener: HTMLElement | null = null

  constructor(private element: HTMLElement, private onClose: () => void = () => {}) {
    this.instance = new Offcanvas(element)
    element.addEventListener('shown.bs.offcanvas', this.shown)
    element.addEventListener('hide.bs.offcanvas', this.hiding)
    element.addEventListener('hidden.bs.offcanvas', this.hidden)
  }

  show() {
    if (this.disposed || active === this && this.phase !== 'closing') return
    const focused = document.activeElement instanceof HTMLElement ? document.activeElement : null
    // A programmatic switch must not restore focus into the drawer being replaced.
    this.opener = active ? active.opener : focused
    if (pending && pending !== this) pending.hide()
    pending = this
    if (active) active.closeActive()
    else this.openPending()
  }

  hide() {
    if (pending === this) {
      pending = undefined
      if (active !== this && !this.disposed) this.onClose()
    }
    if (active === this) this.closeActive()
  }

  dispose() {
    if (this.disposed) return
    this.disposed = true
    if (pending === this) pending = undefined
    if (active === this) this.closeActive()
    else this.cleanup()
  }

  private openPending() {
    if (this.disposed || pending !== this) return
    pending = undefined
    active = this
    this.closingRequested = false
    this.phase = 'opening'
    this.instance.show()
  }

  private closeActive() {
    this.closingRequested = true
    // Bootstrap's show/hide callbacks cannot safely run concurrently.
    if (this.phase === 'shown') this.instance.hide()
  }

  private shown = () => {
    this.phase = 'shown'
    if (this.closingRequested || this.disposed) this.instance.hide()
  }

  private hiding = (event: Event) => {
    // Escape or a backdrop click can arrive during the opening transition.
    // Defer that hide until shown, just like a programmatic switch.
    if (this.phase === 'opening') {
      event.preventDefault()
      this.closingRequested = true
    } else this.phase = 'closing'
    if (!this.disposed) this.onClose()
  }

  private hidden = () => {
    this.phase = 'hidden'
    if (active === this) active = undefined
    if (this.disposed) this.cleanup()
    if (pending) pending.openPending()
    else if (this.opener?.isConnected && this.opener.getClientRects().length && !this.opener.closest('.offcanvas:not(.show)')) this.opener.focus()
  }

  private cleanup() {
    this.element.removeEventListener('shown.bs.offcanvas', this.shown)
    this.element.removeEventListener('hide.bs.offcanvas', this.hiding)
    this.element.removeEventListener('hidden.bs.offcanvas', this.hidden)
    this.instance.dispose()
  }
}
