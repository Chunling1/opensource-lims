import { computed, shallowRef } from 'vue'

// One state per navigation. In-flight responses from a previous page cannot
// change the next page's feedback. No response data or credentials are retained.
type ReadState = { page: string; pending: number; latest: Map<string, number>; failed: Set<string> }
const fresh = (page: string): ReadState => ({ page, pending: 0, latest: new Map<string, number>(), failed: new Set<string>() })
let active = fresh('')
const current = shallowRef({ loading: false, failed: false })
let sequence = 0
export const listReadLoading = computed(() => current.value.loading)
export const listReadFailed = computed(() => current.value.failed)
// Request bookkeeping must remain non-reactive: callers often run in
// watchEffect. Reading a reactive pending counter there creates a reload loop.
function publish() { current.value = { loading: active.pending > 0, failed: active.failed.size > 0 } }
export function enterListPage(page: string) { active = fresh(page); publish() }

export function isListRead(path: string, method = 'GET'): boolean {
  const url = path.split('?')[0]
  const verb = method.toUpperCase()
  if (verb === 'POST') return /\/(query|search|list|logs|workspace-page|plan-counts)$/.test(url) || /^\/api\/reports\/(derivable|lib\/(standards|schemes|items|capability-items))$/.test(url)
  if (verb !== 'GET') return false
  // Read-only collection URLs, including paged customers, capability libraries,
  // organization and workflow workbenches. Detail polling and auth are excluded.
  return /\/(query|search|list|options|claimable|claimed|contract-library|contracts|customers|departments|personnel|users|roles|permissions|entries|standards|schemes|items|capability-items|batches|tree|inbox|tasks|notifications|templates|devices|equipment|records|pending|derivable|std-library|instruments|project-masters|external-entrustments|permission-templates|bindings|attachments|catalog|standard-catalog)$/.test(url)
}

export function beginListRead(path: string, method?: string): (error?: unknown) => void {
  if (!isListRead(path, method)) return () => undefined
  const state = active
  const key = path.split('?')[0]
  const id = ++sequence
  state.pending++
  state.latest.set(key, id)
  state.failed.delete(key)
  publish()
  let settled = false
  return (error?: unknown) => {
    if (settled) return
    settled = true
    state.pending--
    if (state.latest.get(key) === id) {
      if (error && !(error instanceof Error && error.name === 'AbortError')) state.failed.add(key)
      else state.failed.delete(key)
    }
    if (state === active) publish()
  }
}

