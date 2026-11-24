import { computed, onMounted, ref, watch } from 'vue'

// Capture server/default values only when the form becomes ready, never while saving.
export function useFormChanges(value: () => unknown, ready: () => boolean) {
  const baseline = ref(''), captured = ref(false)
  const snapshot = () => JSON.stringify(value(), (_key, item) => item == null ? '' : item)
  function reset() { baseline.value = snapshot(); captured.value = true }
  watch(ready, active => { if (active) reset(); else captured.value = false }, { immediate: true, flush: 'sync' })
  onMounted(() => { if (ready()) reset() })
  const dirty = computed(() => ready() && captured.value && snapshot() !== baseline.value)
  return { dirty, reset }
}
