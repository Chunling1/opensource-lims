import type { Plugin } from 'vue'

type DialogKind = 'dialog' | 'message-box'
type InteractionMode = 'drag' | 'resize'
type ResizeDirection = 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w' | 'nw'

interface StyleValue {
  value: string
  priority: string
}

interface Interaction {
  mode: InteractionMode
  direction?: ResizeDirection
  pointerId: number
  pointerTarget: Element
  startX: number
  startY: number
  startRect: DOMRect
  minWidth: number
  minHeight: number
}

interface DialogController {
  root: HTMLElement
  header: HTMLElement | null
  footer: HTMLElement | null
  kind: DialogKind
  baseline: Map<string, StyleValue>
  defaultRect: DOMRect | null
  wasVisible: boolean
  positioned: boolean
  resized: boolean
  active: Interaction | null
  dispose: () => void
}

const ROOT_SELECTOR = '.el-dialog, .el-message-box'
const VIEWPORT_MARGIN = 16
const RESIZE_HIT_AREA = 8
const MANAGED_STYLE_PROPERTIES = [
  'position',
  'left',
  'top',
  'right',
  'bottom',
  'margin',
  'width',
  'height',
]
const NON_DRAG_SELECTOR = [
  'button',
  'a',
  'input',
  'textarea',
  'select',
  'label',
  '[contenteditable="true"]',
  '[role="button"]',
  '[role="link"]',
  '[role="heading"]',
  '[tabindex]:not([tabindex="-1"])',
  '.el-button',
  '.el-dialog__title',
  '.el-message-box__title > span',
  '.el-message-box__title > .el-icon',
  '.el-input',
  '.el-select',
  '.el-switch',
  '.el-dropdown',
  '.el-tabs__item',
].join(',')

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), Math.max(minimum, maximum))
}

function captureManagedStyles(element: HTMLElement): Map<string, StyleValue> {
  return new Map(MANAGED_STYLE_PROPERTIES.map((property) => [property, {
    value: element.style.getPropertyValue(property),
    priority: element.style.getPropertyPriority(property),
  }]))
}

function restoreManagedStyles(element: HTMLElement, snapshot: Map<string, StyleValue>): void {
  for (const property of MANAGED_STYLE_PROPERTIES) {
    const saved = snapshot.get(property)
    if (saved?.value) element.style.setProperty(property, saved.value, saved.priority)
    else element.style.removeProperty(property)
  }
}

function isVisible(element: HTMLElement): boolean {
  if (!element.isConnected) return false
  let current: HTMLElement | null = element
  while (current) {
    const style = window.getComputedStyle(current)
    if (style.display === 'none' || style.visibility === 'hidden') return false
    current = current.parentElement
  }
  const rect = element.getBoundingClientRect()
  return rect.width > 0 && rect.height > 0
}

function pointerCanStart(event: PointerEvent): boolean {
  return event.isPrimary && event.button === 0
}

function resizeDirectionAt(element: HTMLElement, event: PointerEvent): ResizeDirection | null {
  const rect = element.getBoundingClientRect()
  const atLeft = event.clientX - rect.left <= RESIZE_HIT_AREA
  const atRight = rect.right - event.clientX <= RESIZE_HIT_AREA
  const atTop = event.clientY - rect.top <= RESIZE_HIT_AREA
  const atBottom = rect.bottom - event.clientY <= RESIZE_HIT_AREA

  if (atTop && atLeft) return 'nw'
  if (atTop && atRight) return 'ne'
  if (atBottom && atLeft) return 'sw'
  if (atBottom && atRight) return 'se'
  if (atTop) return 'n'
  if (atRight) return 'e'
  if (atBottom) return 's'
  if (atLeft) return 'w'
  return null
}

function sumVisibleChildWidths(element: HTMLElement | null): number {
  if (!element) return 0
  return Array.from(element.children).reduce((total, child) => {
    const rect = child.getBoundingClientRect()
    return total + (rect.width > 0 ? rect.width : 0)
  }, 0)
}

function minimumSize(controller: DialogController, currentRect: DOMRect): { width: number; height: number } {
  const reference = controller.defaultRect ?? currentRect
  const titleSelector = controller.kind === 'dialog' ? '.el-dialog__title' : '.el-message-box__title > span'
  const title = controller.header?.querySelector<HTMLElement>(titleSelector)
  const close = controller.header?.querySelector<HTMLElement>('.el-dialog__headerbtn, .el-message-box__headerbtn')
  const headerWidth = (title?.scrollWidth ?? 0) + (close?.offsetWidth ?? 0) + 64
  const footerWidth = sumVisibleChildWidths(controller.footer) + 48
  const proportionalWidth = reference.width * (controller.kind === 'message-box' ? 0.68 : 0.42)
  const width = Math.min(reference.width, Math.max(
    220,
    proportionalWidth,
    headerWidth,
    Math.min(footerWidth, reference.width * 0.78),
  ))

  const headerHeight = controller.header?.getBoundingClientRect().height ?? 0
  const footerHeight = controller.footer?.getBoundingClientRect().height ?? 0
  const bodyFloor = clamp(reference.height * 0.2, 88, 160)
  const structuralHeight = headerHeight + footerHeight + bodyFloor
  const height = Math.min(reference.height, Math.max(reference.height * 0.4, structuralHeight))
  return { width, height }
}

function fitRectToViewport(rect: DOMRect): { left: number; top: number; width: number; height: number } {
  const availableWidth = Math.max(1, window.innerWidth - VIEWPORT_MARGIN * 2)
  const availableHeight = Math.max(1, window.innerHeight - VIEWPORT_MARGIN * 2)
  const width = Math.min(rect.width, availableWidth)
  const height = Math.min(rect.height, availableHeight)
  return {
    left: clamp(rect.left, VIEWPORT_MARGIN, window.innerWidth - VIEWPORT_MARGIN - width),
    top: clamp(rect.top, VIEWPORT_MARGIN, window.innerHeight - VIEWPORT_MARGIN - height),
    width,
    height,
  }
}

function setSafeMaximumHeight(controller: DialogController, positioned = controller.positioned): void {
  const maximum = Math.max(1, window.innerHeight - VIEWPORT_MARGIN * 2)
  let value: string
  if (positioned) {
    value = `${maximum}px`
  } else {
    const top = Math.max(VIEWPORT_MARGIN, controller.root.getBoundingClientRect().top)
    value = `${Math.max(1, window.innerHeight - VIEWPORT_MARGIN - top)}px`
  }
  if (controller.root.style.getPropertyValue('--hn-dialog-safe-max-height') !== value) {
    controller.root.style.setProperty('--hn-dialog-safe-max-height', value)
  }
}

function setFixedRect(
  controller: DialogController,
  rect: { left: number; top: number; width: number; height: number },
  includeHeight: boolean,
): void {
  const { root } = controller
  root.style.position = 'fixed'
  root.style.left = `${Math.round(rect.left)}px`
  root.style.top = `${Math.round(rect.top)}px`
  root.style.right = 'auto'
  root.style.bottom = 'auto'
  root.style.margin = '0'
  root.style.width = `${Math.round(rect.width)}px`
  if (includeHeight) root.style.height = `${Math.round(rect.height)}px`
  root.classList.add('hn-dialog--positioned')
  root.classList.toggle('hn-dialog--resized', controller.resized || includeHeight)
  controller.positioned = true
  if (includeHeight) controller.resized = true
  setSafeMaximumHeight(controller, true)
}

function resetController(controller: DialogController): void {
  restoreManagedStyles(controller.root, controller.baseline)
  controller.root.style.removeProperty('--hn-dialog-safe-max-height')
  controller.root.classList.remove('hn-dialog--positioned', 'hn-dialog--resized', 'hn-dialog--active')
  controller.root.removeAttribute('data-hn-resize-cursor')
  controller.positioned = false
  controller.resized = false
  controller.active = null
}

function installDialogInteractions(): () => void {
  if (typeof window === 'undefined' || typeof document === 'undefined') return () => {}

  const controllers = new Map<HTMLElement, DialogController>()
  let activeController: DialogController | null = null
  let syncFrame = 0
  let resizeFrame = 0

  const clearGlobalPointerState = () => {
    document.documentElement.classList.remove('hn-dialog-interacting')
    document.documentElement.removeAttribute('data-hn-dialog-cursor')
  }

  const finishInteraction = (controller: DialogController) => {
    const interaction = controller.active
    if (!interaction) return
    window.removeEventListener('pointermove', onWindowPointerMove)
    window.removeEventListener('pointerup', onWindowPointerEnd)
    window.removeEventListener('pointercancel', onWindowPointerEnd)
    if (interaction.pointerTarget.isConnected && interaction.pointerTarget.hasPointerCapture?.(interaction.pointerId)) {
      interaction.pointerTarget.releasePointerCapture(interaction.pointerId)
    }
    controller.active = null
    controller.root.classList.remove('hn-dialog--active')
    activeController = null
    clearGlobalPointerState()
  }

  const beginInteraction = (
    controller: DialogController,
    event: PointerEvent,
    mode: InteractionMode,
    direction?: ResizeDirection,
  ) => {
    if (!pointerCanStart(event) || activeController) return
    const current = controller.root.getBoundingClientRect()
    const fitted = fitRectToViewport(current)
    const minimum = minimumSize(controller, current)
    controller.resized = controller.resized || mode === 'resize'
    setFixedRect(controller, fitted, mode === 'resize' || fitted.height < current.height)
    const startRect = controller.root.getBoundingClientRect()
    const interaction: Interaction = {
      mode,
      direction,
      pointerId: event.pointerId,
      pointerTarget: event.currentTarget instanceof Element ? event.currentTarget : controller.root,
      startX: event.clientX,
      startY: event.clientY,
      startRect,
      minWidth: Math.min(minimum.width, window.innerWidth - VIEWPORT_MARGIN * 2),
      minHeight: Math.min(minimum.height, window.innerHeight - VIEWPORT_MARGIN * 2),
    }
    controller.active = interaction
    activeController = controller
    controller.root.classList.add('hn-dialog--active')
    document.documentElement.classList.add('hn-dialog-interacting')
    document.documentElement.dataset.hnDialogCursor = mode === 'drag' ? 'move' : direction ?? 'se'
    interaction.pointerTarget.setPointerCapture?.(event.pointerId)
    window.addEventListener('pointermove', onWindowPointerMove, { passive: false })
    window.addEventListener('pointerup', onWindowPointerEnd)
    window.addEventListener('pointercancel', onWindowPointerEnd)
    event.preventDefault()
    event.stopPropagation()
  }

  function onWindowPointerMove(event: PointerEvent): void {
    const controller = activeController
    const interaction = controller?.active
    if (!controller || !interaction || event.pointerId !== interaction.pointerId) return
    const dx = event.clientX - interaction.startX
    const dy = event.clientY - interaction.startY
    const availableWidth = Math.max(1, window.innerWidth - VIEWPORT_MARGIN * 2)
    const availableHeight = Math.max(1, window.innerHeight - VIEWPORT_MARGIN * 2)
    const start = interaction.startRect

    if (interaction.mode === 'drag') {
      setFixedRect(controller, {
        left: clamp(start.left + dx, VIEWPORT_MARGIN, window.innerWidth - VIEWPORT_MARGIN - start.width),
        top: clamp(start.top + dy, VIEWPORT_MARGIN, window.innerHeight - VIEWPORT_MARGIN - start.height),
        width: Math.min(start.width, availableWidth),
        height: Math.min(start.height, availableHeight),
      }, controller.resized)
      event.preventDefault()
      return
    }

    const direction = interaction.direction ?? 'se'
    let left = start.left
    let top = start.top
    let right = start.right
    let bottom = start.bottom

    if (direction.includes('e')) {
      right = clamp(start.right + dx, start.left + interaction.minWidth, window.innerWidth - VIEWPORT_MARGIN)
    }
    if (direction.includes('w')) {
      left = clamp(start.left + dx, VIEWPORT_MARGIN, start.right - interaction.minWidth)
    }
    if (direction.includes('s')) {
      bottom = clamp(start.bottom + dy, start.top + interaction.minHeight, window.innerHeight - VIEWPORT_MARGIN)
    }
    if (direction.includes('n')) {
      top = clamp(start.top + dy, VIEWPORT_MARGIN, start.bottom - interaction.minHeight)
    }

    setFixedRect(controller, {
      left,
      top,
      width: Math.min(right - left, availableWidth),
      height: Math.min(bottom - top, availableHeight),
    }, true)
    event.preventDefault()
  }

  function onWindowPointerEnd(event: PointerEvent): void {
    const controller = activeController
    if (!controller?.active || event.pointerId !== controller.active.pointerId) return
    finishInteraction(controller)
  }

  const reclampPositionedController = (controller: DialogController) => {
    if (!controller.root.isConnected || !controller.wasVisible || !controller.positioned || controller.active) return
    const current = controller.root.getBoundingClientRect()
    const fitted = fitRectToViewport(current)
    const changed = Math.abs(fitted.left - current.left) > 0.5
      || Math.abs(fitted.top - current.top) > 0.5
      || Math.abs(fitted.width - current.width) > 0.5
      || Math.abs(fitted.height - current.height) > 0.5
    if (!changed) return
    setFixedRect(controller, fitted, controller.resized || fitted.height < current.height)
  }

  const attach = (root: HTMLElement) => {
    if (controllers.has(root) || root.classList.contains('is-fullscreen')) return
    const kind: DialogKind = root.classList.contains('el-message-box') ? 'message-box' : 'dialog'
    const header = root.querySelector<HTMLElement>(kind === 'dialog' ? '.el-dialog__header' : '.el-message-box__header')
    const footer = root.querySelector<HTMLElement>(kind === 'dialog' ? '.el-dialog__footer' : '.el-message-box__btns')

    const controller: DialogController = {
      root,
      header,
      footer,
      kind,
      baseline: captureManagedStyles(root),
      defaultRect: null,
      wasVisible: isVisible(root),
      positioned: false,
      resized: false,
      active: null,
      dispose: () => {},
    }

    const onRootPointerMove = (event: PointerEvent) => {
      if (controller.active) return
      const direction = resizeDirectionAt(root, event)
      if (direction) root.dataset.hnResizeCursor = direction
      else root.removeAttribute('data-hn-resize-cursor')
    }
    const onRootPointerLeave = () => {
      if (!controller.active) root.removeAttribute('data-hn-resize-cursor')
    }
    const onRootPointerDown = (event: PointerEvent) => {
      const direction = resizeDirectionAt(root, event)
      if (direction) beginInteraction(controller, event, 'resize', direction)
    }
    const onHeaderPointerDown = (event: PointerEvent) => {
      if (!pointerCanStart(event) || resizeDirectionAt(root, event)) return
      const target = event.target
      if (!(target instanceof Element) || target.closest(NON_DRAG_SELECTOR)) return
      if (target.closest(ROOT_SELECTOR) !== root) return
      beginInteraction(controller, event, 'drag')
    }

    root.classList.add('hn-dialog-interaction')
    root.dataset.hnDialogInteraction = kind
    root.addEventListener('pointermove', onRootPointerMove)
    root.addEventListener('pointerleave', onRootPointerLeave)
    root.addEventListener('pointerdown', onRootPointerDown, true)
    header?.addEventListener('pointerdown', onHeaderPointerDown)

    const rootResizeObserver = new ResizeObserver(() => reclampPositionedController(controller))
    rootResizeObserver.observe(root)

    controller.dispose = () => {
      if (controller.active) finishInteraction(controller)
      rootResizeObserver.disconnect()
      root.removeEventListener('pointermove', onRootPointerMove)
      root.removeEventListener('pointerleave', onRootPointerLeave)
      root.removeEventListener('pointerdown', onRootPointerDown, true)
      header?.removeEventListener('pointerdown', onHeaderPointerDown)
      resetController(controller)
      root.classList.remove('hn-dialog-interaction')
      root.removeAttribute('data-hn-dialog-interaction')
      controllers.delete(root)
    }

    controllers.set(root, controller)
    if (controller.wasVisible) {
      controller.defaultRect = root.getBoundingClientRect()
      setSafeMaximumHeight(controller, false)
    }
  }

  const scan = (node: Node) => {
    if (!(node instanceof Element)) return
    if (node.matches(ROOT_SELECTOR)) attach(node as HTMLElement)
    node.querySelectorAll<HTMLElement>(ROOT_SELECTOR).forEach(attach)
  }

  const syncControllers = () => {
    syncFrame = 0
    document.querySelectorAll<HTMLElement>(ROOT_SELECTOR).forEach(attach)
    for (const controller of controllers.values()) {
      if (!controller.root.isConnected) {
        controller.dispose()
        continue
      }
      const visible = isVisible(controller.root)
      if (controller.wasVisible && !visible) {
        if (controller.active) finishInteraction(controller)
        resetController(controller)
        controller.defaultRect = null
      } else if (!controller.wasVisible && visible) {
        controller.baseline = captureManagedStyles(controller.root)
        controller.defaultRect = controller.root.getBoundingClientRect()
        setSafeMaximumHeight(controller, false)
      } else if (visible && !controller.positioned) {
        setSafeMaximumHeight(controller, false)
      }
      controller.wasVisible = visible
    }
  }

  const scheduleSync = () => {
    if (!syncFrame) syncFrame = window.requestAnimationFrame(syncControllers)
  }

  const observer = new MutationObserver((mutations) => {
    let shouldSync = false
    for (const mutation of mutations) {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach(scan)
        shouldSync = true
      } else if (mutation.target instanceof Element
        && mutation.target.matches('.el-overlay, .el-overlay-dialog, .el-overlay-message-box')) {
        shouldSync = true
      }
    }
    if (shouldSync) scheduleSync()
  })
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['class', 'style'],
  })
  scan(document.body)

  const onWindowResize = () => {
    if (resizeFrame) return
    resizeFrame = window.requestAnimationFrame(() => {
      resizeFrame = 0
      for (const controller of controllers.values()) {
        if (!controller.wasVisible) continue
        controller.root.removeAttribute('data-hn-resize-cursor')
        if (!controller.positioned) {
          setSafeMaximumHeight(controller, false)
          continue
        }
        reclampPositionedController(controller)
      }
    })
  }
  window.addEventListener('resize', onWindowResize)

  return () => {
    observer.disconnect()
    if (syncFrame) window.cancelAnimationFrame(syncFrame)
    if (resizeFrame) window.cancelAnimationFrame(resizeFrame)
    window.removeEventListener('resize', onWindowResize)
    for (const controller of controllers.values()) controller.dispose()
    clearGlobalPointerState()
  }
}

let stopCurrentInstallation: (() => void) | null = null

const DialogInteractionPlugin: Plugin = {
  install() {
    stopCurrentInstallation?.()
    stopCurrentInstallation = installDialogInteractions()
  },
}

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    stopCurrentInstallation?.()
    stopCurrentInstallation = null
  })
}

export { installDialogInteractions }
export default DialogInteractionPlugin
