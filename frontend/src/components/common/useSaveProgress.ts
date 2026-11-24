import { ref } from 'vue'
import type { TransferProgress } from '../../services/common/uploadRequest'

export function useSaveProgress() {
  const percent = ref<number>()
  const active = ref(false)
  const update: TransferProgress = (loaded, total) => {
    if (!active.value || total <= 0) return
    // Do not show 100% before the complete request body has been transmitted.
    percent.value = Math.max(0, Math.min(100, Math.floor(loaded / total * 100)))
  }
  function start() { percent.value = undefined; active.value = true; return update }
  function finish() { active.value = false; percent.value = undefined }
  return { percent, active, start, finish }
}
