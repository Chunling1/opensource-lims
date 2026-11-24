import { onScopeDispose, watch, type WatchSource } from 'vue'

/** Debounce remote reads, never business actions. Clear/reset remains immediate. */
export function useLiveSearch(source: WatchSource, search: () => unknown, enabled: () => boolean = () => true) {
  let timer: ReturnType<typeof setTimeout> | undefined
  function cancel() { clearTimeout(timer); timer = undefined }
  function run() { cancel(); if (enabled()) void search() }
  watch(source, value => {
    cancel()
    if (!enabled()) return
    if (value === '') run()
    else timer = setTimeout(run, 250)
  }, { flush: 'sync' })
  onScopeDispose(cancel)
  return { run, cancel }
}

/** A response is valid only for the latest request AND unchanged query context. */
export function useSearchRequest(context: () => unknown) {
  let sequence = 0
  let alive = true
  onScopeDispose(() => { alive = false; sequence++ })
  return () => {
    const id = ++sequence
    const key = JSON.stringify(context())
    return () => alive && id === sequence && key === JSON.stringify(context())
  }
}
