import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { completePreviewState, type CompletePreviewState } from '@/services/attachments'
import type { ReportDetailView } from '@/services/reports'

// A form session owns polling, not the background job. Closing the form cancels
// only polling. Out-of-order replies may never enable another report's button.
export function useCompletePreview(reportNo: Ref<string>, view: Ref<ReportDetailView>, enabled: Ref<boolean>, unavailableReason?: Ref<string>) {
  const state = ref<CompletePreviewState>({ status: 'missing', message: '尚未生成预览' })
  let epoch = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  const ready = computed(() => enabled.value && state.value.status === 'ready')
  function stop() { epoch += 1; clearTimeout(timer); timer = undefined }
  async function refresh(retry = false) {
    stop()
    const token = epoch
    const number = reportNo.value
    const currentView = view.value
    if (!enabled.value || !number) {
      state.value = { status: 'missing', message: unavailableReason?.value || '尚未生成预览' }
      return
    }
    state.value = { status: 'missing', message: '正在核对预览版本' }
    const valid = () => token === epoch && enabled.value && number === reportNo.value && currentView === view.value
    async function poll(first: boolean) {
      try {
        let result = await completePreviewState(number, currentView)
        if (!valid()) return
        if (['missing', 'stale'].includes(result.status) || (first && retry)) {
          result = await completePreviewState(number, currentView, true, first && retry)
          if (!valid()) return
        }
        state.value = result
        // Continue checking a ready preview: another user may change its inputs.
        if (result.status !== 'failed') timer = setTimeout(() => void poll(false), result.status === 'ready' ? 10000 : 3000)
      } catch (error) {
        if (valid()) state.value = { status: 'failed', message: error instanceof Error ? error.message : '预览状态读取失败' }
      }
    }
    await poll(true)
  }
  watch([reportNo, view, enabled], () => void refresh(), { immediate: true })
  onBeforeUnmount(stop)
  return { state, ready, refresh, stop }
}
