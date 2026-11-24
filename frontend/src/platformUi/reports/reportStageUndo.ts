import type {ReportRow, ReportActionResult} from '@/services/auth'
import {AppError} from '../../services/common/errors'

export type ReportReviewStage = 'review' | 'approval'

export function createReportStageUndo(context: {
  page: () => string
  rows: () => ReportRow[]
  canAction: (action: string) => boolean
  perform: (reportNo: string, action: string) => Promise<ReportActionResult | null>
  invalidate: (reportNo: string) => void
  refresh: () => Promise<void>
}) {
  return async (reportNo: string, stage: ReportReviewStage): Promise<void> => {
    const action = `report.${stage}.undo`
    const row = context.rows().find(item => item.reportNo === reportNo)
    const expected = stage === 'review' ? '待批准' : '待打印'
    if (!['review', 'approval'].includes(stage) || context.page() !== stage || !row
      || row.status !== expected || !row.allowedActions?.includes(action) || !context.canAction(action)) {
      throw new AppError('BUSINESS_RULE', '当前报告状态或撤销权限已变化，请刷新列表后核对。')
    }
    // Use the same production workflow endpoint as the report detail page.
    const result = await context.perform(reportNo, action)
    if (!result) throw new AppError('BUSINESS_RULE', '撤销未完成，请核对当前流程状态。')
    context.invalidate(reportNo)
    if (context.page() === stage) await context.refresh()
  }
}
