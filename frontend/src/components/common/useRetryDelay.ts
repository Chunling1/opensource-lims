import { onBeforeUnmount, ref, watch, type Ref } from 'vue'
import type { AppError } from '../../services/common/errors'
export function useRetryDelay(error: Readonly<Ref<AppError | undefined | ''>>) {
  const seconds = ref(0)
  let timer: ReturnType<typeof setInterval> | undefined
  watch(error, () => {
    clearInterval(timer)
    const tick = () => { seconds.value = Math.max(0, Math.ceil((((error.value && error.value.retryAt) || 0) - Date.now()) / 1000)); if (!seconds.value) clearInterval(timer) }
    tick(); if (seconds.value) timer = setInterval(tick, 250)
  }, { immediate: true })
  onBeforeUnmount(() => clearInterval(timer))
  return seconds
}
