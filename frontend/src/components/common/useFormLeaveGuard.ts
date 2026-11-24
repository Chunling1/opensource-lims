import { onBeforeUnmount, ref } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useFormChanges } from './useFormChanges'
import { useUnsavedChanges } from './useUnsavedChanges'

export function useFormLeaveGuard(value: () => unknown, ready: () => boolean, busy: () => boolean, navigation = true) {
  const changes = useFormChanges(value, ready), requested = ref(false)
  let pending: Promise<boolean> | undefined, resolve: ((leave: boolean) => void) | undefined
  function finish(leave: boolean) {
    if (leave && busy()) return
    requested.value = false
    resolve?.(leave); resolve = undefined; pending = undefined
  }
  async function allowLeave() {
    if (busy()) return false
    if (!changes.dirty.value) return true
    if (!pending) { pending = new Promise<boolean>(done => { resolve = done }); requested.value = true }
    return pending
  }
  useUnsavedChanges(changes.dirty)
  if (navigation) { onBeforeRouteLeave(allowLeave); onBeforeRouteUpdate(allowLeave) }
  onBeforeUnmount(() => finish(false))
  return { requested, finish, allowLeave, dirty: changes.dirty, commit: changes.reset }
}
