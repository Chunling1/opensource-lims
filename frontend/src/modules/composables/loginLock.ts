import { computed, onBeforeUnmount, ref, type Ref } from 'vue'
const prefix = 'hn_login_lock_v1:'
const memory = new Map<string, number>()
export function useLoginLock(account: Ref<string>) {
  const clock = ref(Date.now())
  const tick = setInterval(() => { clock.value = Date.now() }, 1000)
  onBeforeUnmount(() => clearInterval(tick))
  const key = computed(() => prefix + account.value.trim().toLowerCase())
  const revision = ref(0)
  const seconds = computed(() => {
    void revision.value
    let until = memory.get(key.value) || 0
    try { until = Math.max(until, Number(sessionStorage.getItem(key.value) || 0)) } catch { /* memory fallback */ }
    return Number.isFinite(until) ? Math.max(0, Math.ceil((until-clock.value)/1000)) : 0
  })
  function lock(retrySeconds: number) {
    const wait = Number.isFinite(retrySeconds) && retrySeconds > 0 ? retrySeconds : 1800
    const until = Date.now()+wait*1000
    memory.set(key.value, until)
    try { sessionStorage.setItem(key.value, String(until)) } catch { /* memory fallback */ }
    clock.value=Date.now(); revision.value++
  }
  function clear() { memory.delete(key.value); try { sessionStorage.removeItem(key.value) } catch { /* optional UI hint */ }; revision.value++ }
  return { seconds, lock, clear }
}
