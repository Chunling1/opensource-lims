import { computed, onBeforeUnmount, ref } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useUnsavedChanges } from './useUnsavedChanges'
export interface FileUploadState { name: string; index: number; total: number; phase: 'reading' | 'uploading' | 'saving' }
const pendingNotices = new Set<() => void>()
export function notifyUploadLeaveBlocked() { pendingNotices.forEach(notify => notify()) }
export function useFileUpload() {
  const state = ref<FileUploadState>(), leaveAttempted = ref(false), active = computed(() => !!state.value)
  useUnsavedChanges(active)
  const notify = () => { if (active.value) leaveAttempted.value = true }
  pendingNotices.add(notify)
  onBeforeUnmount(() => pendingNotices.delete(notify))
  function guard() { if (active.value) { leaveAttempted.value = true; return false } }
  onBeforeRouteLeave(guard); onBeforeRouteUpdate(guard)
  function start(name: string, index = 1, total = 1) { state.value = { name, index, total, phase: 'reading' }; leaveAttempted.value = false }
  function processing(phase: 'uploading' | 'saving' = 'uploading') { if (state.value) state.value.phase = phase }
  function finish() { state.value = undefined; leaveAttempted.value = false }
  return { state, active, leaveAttempted, start, processing, finish }
}
