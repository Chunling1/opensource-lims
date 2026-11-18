declare module '@tabler/core/dist/js/tabler.esm.min.js' {
  interface Instance {
    show(): void
    hide(): void
    dispose(): void
  }
  interface Ctor {
    new (el: Element, options?: Record<string, unknown>): Instance
    getOrCreateInstance(el: Element, options?: Record<string, unknown>): Instance
  }
  export const Modal: Ctor
  export const Dropdown: Ctor
  export const Toast: Ctor
  export const Collapse: Ctor
}
declare module '@tabler/core/dist/libs/litepicker/dist/litepicker.umd.js' {
  interface Picked {
    format(f: string): string
  }
  export default class Litepicker {
    constructor(options: Record<string, unknown>)
    on(event: 'selected', cb: (d: Picked) => void): void
    setOptions(options: Record<string, unknown>): void
    setDate(d: string | null): void
    clearSelection(): void
    destroy(): void
  }
}
