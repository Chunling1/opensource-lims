import type { Ref } from 'vue'

export interface ReturnContext {
  account: string
  scope: string
  path: string
  formOpen: boolean
  formReportNo: string
  formReadOnly: boolean
}

interface ReturnDependencies {
  busy: Ref<boolean>
  saving: () => boolean
  context: () => ReturnContext
  allowed: (reportNo: string) => boolean
  prompt: (reportNo: string) => Promise<string | null>
  submit: (reportNo: string, note: string) => Promise<unknown>
  completed: (reportNo: string, fromForm: boolean) => Promise<void>
  warning: (message: string) => void
  error: (message: string) => void
}

// The clicked report is the operation target; table checkbox selection is unrelated.
export function createDataEntryReturn(d: ReturnDependencies) {
  return async (reportNo: string) => {
    if (!reportNo || d.busy.value) return
    if (d.saving()) {
      d.warning('正在保存检测数据，请保存完成后再退回')
      return
    }
    if (!d.allowed(reportNo)) {
      d.warning('当前报告状态或权限不允许退回，请刷新后重试')
      return
    }
    const origin = { ...d.context() }
    const sameContext = () => {
      const current = d.context()
      return current.account === origin.account && current.scope === origin.scope
        && current.path === origin.path && current.formOpen === origin.formOpen
        && (!origin.formOpen || (!current.formReadOnly && current.formReportNo === reportNo))
    }
    d.busy.value = true
    try {
      const answer = await d.prompt(reportNo)
      if (answer === null) return
      const note = answer.trim()
      if (!note) { d.warning('退回必须填写原因'); return }
      if (!sameContext() || !d.allowed(reportNo) || d.saving()) {
        d.warning('页面、报告状态或权限已变化，本次退回未提交，请刷新后重试')
        return
      }
      await d.submit(reportNo, note)
      // A completed request must not clear a different form or another account's state.
      if (sameContext()) await d.completed(reportNo, origin.formOpen)
    } catch (error) {
      if (sameContext()) d.error(error instanceof Error ? error.message : '退回失败，请刷新状态后重试')
    } finally {
      d.busy.value = false
    }
  }
}
