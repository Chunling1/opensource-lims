import type { TableColumn } from '../common/table'
import type { RegistrationPage } from '../commissions/registration'
import type { ReviewConfirmation } from '../commissions/contractReview'
import type { PlanSelectionState } from '../samples/inbound'
import type { DataEntryQuery, DataEntryRow } from '../testing/dataEntry'
import { dataEntrySearchFields } from '../testing/dataEntry'
import { dataCheckColumns } from '../testing/dataCheck'

export type ReportStage = 'check' | 'review' | 'approval'
export const reportStages = {
  check: { label: '校核', title: '报告校核', root: '/reports/check', pending: '报告校核中', completed: '报告校核完成', previous: '检测数据校核完成', infoKey: 'reportCheckInfo', role: 'reviewer' },
  review: { label: '审核', title: '报告审核', root: '/reports/review', pending: '报告审核中', completed: '报告审核完成', previous: '报告校核完成', infoKey: 'reportReviewInfo', role: 'reviewer' },
  approval: { label: '批准', title: '报告批准', root: '/reports/approval', pending: '报告批准中', completed: '报告批准完成', previous: '报告审核完成', infoKey: 'reportApprovalInfo', role: 'approver' },
} as const
export type ReportStageStatus = '未校核' | '已校核' | '未审核' | '已审核' | '未批准' | '已批准'

export const reportCheckStates = ['报告校核中', '报告校核完成'] as const
export const reportCheckStatuses = ['未校核', '已校核'] as const
export const reportCheckSearchFields = dataEntrySearchFields.filter(field => field.value !== 'dataEntryPerson')
export const reportCheckDateFields = [
  { value: 'checkDate', label: '校核日期' },
  { value: 'testStartDate', label: '试验开始日期' },
  { value: 'testEndDate', label: '试验结束日期' },
  { value: 'commissionDate', label: '委托日期' },
] as const
export type ReportCheckNextAction = 'next' | 'transfer'
export interface ReportCheckInfo { actorId: string; actorName: string; at: string; date?: string; reviewConfirmation?: ReviewConfirmation; nextAction?: ReportCheckNextAction; recipient?: { id: string; name: string } }
export interface ReportCheckConfirmation { reviewCheckId: string; readConfirmed: boolean; nextAction: ReportCheckNextAction; recipientId?: string }
export interface ReportBatchSubmission {
  targets: import('../commissions/contractReview').BatchReviewTarget[]
  stage: ReportStage
  action: 'check' | 'reject'
  confirmation?: Omit<ReportCheckConfirmation, 'reviewCheckId'>
  checks: { sampleId: string; checkId: string }[]
  rejection?: ReportCheckRejection
}
export const reportIssueTypes = ['委托信息问题', '检测数据问题', '委托、检测数据问题', '其他问题'] as const
export interface ReportCheckRejection {
  reason: string; problemType: '' | typeof reportIssueTypes[number]
  destination: 'commission' | 'testing'; handler: string; opinion: string
}
export interface ReportCheckIssue extends ReportCheckRejection {
  stage?: ReportStage
  id: string; submittedAt: string; submittedBy: { id: string; name: string }
  completedAt?: string; completedBy?: { id: string; name: string }
}
export function emptyReportCheckRejection(): ReportCheckRejection { return { reason: '', problemType: '', destination: 'commission', handler: '', opinion: '' } }
export interface ReportCheckQuery extends Omit<DataEntryQuery, 'dateField' | 'searchField'> {
  checkStatus?: ReportStageStatus | ''
  searchField?: typeof reportCheckSearchFields[number]['value']
  dateField?: typeof reportCheckDateFields[number]['value'] | 'reportReviewDate'
}
export interface ReportCheckRow extends DataEntryRow {
  checker: string; checkDate: string; checkStatus: ReportStageStatus
  reportChecker: string; reportCheckDate: string; reportReviewer: string; reportReviewDate: string
  changeCount: number | null; canCheck: boolean; canUndoCheck: boolean; canVoid: boolean
}
export interface ReportCheckPage extends RegistrationPage<ReportCheckRow> { planSelection: PlanSelectionState }
export const reportCheckActions = [
  { label: '校核', icon: 'ti ti-circle-check' },
  { label: '撤销校核', icon: 'ti ti-arrow-back-up' },
  { label: '查看任务处理记录', icon: 'ti ti-file-description' },
  { label: '查看附件', icon: 'ti ti-paperclip' },
] as const
export const reportCheckColumns: readonly TableColumn<keyof ReportCheckRow>[] = dataCheckColumns.flatMap(column => {
  if (column.key === 'commissionCode') return [column, { key: 'changeCount', label: '更改次数', default: false } as TableColumn<keyof ReportCheckRow>]
  const labels: Record<string, string> = { name: '样品/工程名称', projectName: '检测方案', conclusion: '结论', engineeringName: '项目名称' }
  return [{ ...column, label: labels[column.key] || column.label }]
})
export function reportStageColumns(stage: ReportStage): readonly TableColumn<keyof ReportCheckRow>[] {
  return reportCheckColumns.flatMap(column => {
    const current = { ...column, label: column.label.replaceAll('校核', reportStages[stage].label) }
    if (column.key !== 'engineeringName' || stage === 'check') return [current]
    const previous: TableColumn<keyof ReportCheckRow>[] = stage === 'approval' ? [
      { key: 'reportReviewer', label: '审核人', default: false },
      { key: 'reportReviewDate', label: '审核日期', default: false },
    ] : []
    return [current, ...previous,
      { key: 'reportChecker', label: '校核人', default: false },
      { key: 'reportCheckDate', label: '校核日期', default: false },
    ]
  })
}
export function reportStageActions(stage: ReportStage) {
  const actions: { label: string; icon: string }[] = reportCheckActions.filter(action => stage !== 'approval' || action.label !== '撤销校核').map(action => ({ ...action, label: action.label.replaceAll('校核', reportStages[stage].label) }))
  if (stage !== 'check') actions.splice(stage === 'approval' ? 1 : 2, 0, { label: '作废', icon: 'ti ti-trash' })
  return actions
}
export function reportStageDates(stage: ReportStage): { value: NonNullable<ReportCheckQuery['dateField']>; label: string }[] {
  return [{ value: 'commissionDate', label: '委托日期' }]
}
