import { watch } from 'vue'
import { currentActor } from '../../stores/session'
import type { RegistrationCommissionRow, RegistrationPage, RegistrationSampleRow } from '../../types/commissions/registration'

const root = '/commissions/registration'
export interface RegistrationListState {
  url: string
  commissions: RegistrationPage<RegistrationCommissionRow>
  samples: RegistrationPage<RegistrationSampleRow>
  current?: RegistrationCommissionRow
  selectedSamples: string[]
  scroll: { left: number; top: number }
}
let cached: (RegistrationListState & { actor: string }) | undefined
let returnScroll: { url: string; position: RegistrationListState['scroll'] } | undefined
const identity = () => JSON.stringify(currentActor.value)
function key(url: string) {
  const [path, search = ''] = url.split('?')
  const params = new URLSearchParams(search)
  params.delete('savedSample'); params.sort()
  return `${path}?${params}`
}
export function clearRegistrationListState() { cached = undefined; returnScroll = undefined }
watch(currentActor, clearRegistrationListState, { flush: 'sync' })

export function saveRegistrationListState(state: RegistrationListState) {
  // Retain the previous display while fresh backend queries run on every return.
  // This never determines data freshness; no attachment content or form drafts.
  cached = { ...JSON.parse(JSON.stringify(state)), actor: identity() }
}
export function restoreRegistrationListState(url: string) {
  const state = cached; cached = undefined
  if (!state || state.actor !== identity() || key(state.url) !== key(url)) return undefined
  returnScroll = { url: key(url), position: state.scroll }
  return state
}
export function takeRegistrationReturnScroll(url: string) {
  const pending = returnScroll; returnScroll = undefined
  return pending?.url === key(url) ? pending.position : undefined
}
export const isRegistrationChild = (path: string) => path.startsWith(`${root}/`)

