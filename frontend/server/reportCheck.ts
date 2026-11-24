import type { RegistrationSample } from '../src/types/commissions/registration'
import type { Actor } from '../src/types/lims'
import { AppError } from '../src/services/common/errors'
import { reportStages, reportStageDates, type ReportStage, reportCheckSearchFields, type ReportCheckQuery, type ReportCheckRow } from '../src/types/reports/reportCheck'
import { dataEntryRows, parseDataEntryQuery } from './testingDataEntry'
import { reportIssueTypes, type ReportCheckRejection } from '../src/types/reports/reportCheck'

export function parseReportCheckRejection(value: unknown): ReportCheckRejection {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new AppError('VALIDATION', '请填写问题处理信息。')
  const input = value as Record<string, unknown>, errors: Record<string, string> = {}
  if (!(reportIssueTypes as readonly unknown[]).includes(input.problemType)) errors.problemType = '请选择问题类型。'
  if (input.destination !== 'commission' && input.destination !== 'testing') errors.destination = '请选择退回方向。'
  for (const [key, label, limit, required] of [['reason', '退回原因', 2000, false], ['handler', '退回处理人', 100, false], ['opinion', '处理意见', 2000, false]] as const) {
    if (typeof input[key] !== 'string' || input[key].length > limit || required && !input[key].trim()) errors[key] = `请填写${required ? '有效的' : ''}${label}，不超过${limit}字。`
  }
  if (Object.keys(errors).length) throw new AppError('VALIDATION', '请检查问题处理信息。', { fieldErrors: errors })
  return { problemType: input.problemType as ReportCheckRejection['problemType'], destination: input.destination as ReportCheckRejection['destination'], reason: (input.reason as string).trim(), handler: (input.handler as string).trim(), opinion: (input.opinion as string).trim() }
}
export function completeReportIssue(sample: RegistrationSample, issueId: string | undefined, actor: Actor) {
  const issue = issueId ? sample.reportCheckIssues?.find(row => row.id === issueId) : undefined
  if (issue) { issue.completedAt = new Date().toISOString(); issue.completedBy = { id: actor.id, name: actor.name } }
}
export function parseReportStage(value: unknown): ReportStage {
  if (value === undefined) return 'check'
  if (value !== 'check' && value !== 'review' && value !== 'approval') throw new AppError('BAD_REQUEST', '报告处理环节有误。')
  return value
}

export function isReportCheckSample(sample: Pick<RegistrationSample, 'status' | 'dataStatus'>, stage: ReportStage = 'check') {
  const config = reportStages[stage]
  return !['voided', 'void_pending'].includes(sample.status) && ([config.pending, config.completed, ...(config.previous ? [config.previous] : [])] as readonly string[]).includes(sample.dataStatus)
}
export function reportCheckCapabilities(actor: Actor, sample: RegistrationSample, stage: ReportStage = 'check') {
  const config = reportStages[stage]
  const roles = stage === 'approval' ? ['admin', 'approver'] : ['admin', 'reports', 'reviewer']
  const laterDone = stage === 'check' ? !!(sample.workflow?.auditDate || sample.workflow?.approvalDate || sample.reportReviewInfo || sample.reportApprovalInfo)
    : stage === 'review' ? !!(sample.workflow?.approvalDate || sample.reportApprovalInfo) : !!(sample.workflow?.issueDate || sample.workflow?.archiveDate)
  const allowed = actor.roles.some(role => roles.includes(role)) && (actor.scope === 'all' || actor.departmentId === sample.departmentId)
    && isReportCheckSample(sample, stage) && !laterDone
  return { canCheck: allowed && sample.dataStatus !== config.completed, canUndoCheck: allowed && stage !== 'approval' && sample.dataStatus === config.completed, canVoid: allowed && stage !== 'check' && sample.status === 'completed' }
}
export function parseReportCheckQuery(input: Record<string, unknown>, stage: ReportStage = 'check'): ReportCheckQuery {
  const config = reportStages[stage], states = [config.pending, config.completed]
  if (input.searchField !== undefined && input.searchField !== '' && !reportCheckSearchFields.some(field => field.value === input.searchField)) throw new AppError('BAD_REQUEST', `不支持的${config.title}查询内容。`)
  const allowedDates = new Set<string>([
    ...reportStageDates(stage).map(field => field.value),
    'checkDate',
    'testStartDate',
    'testEndDate',
    ...(stage === 'approval' ? ['reportReviewDate'] : []),
  ])
  if (input.dateField !== undefined && input.dateField !== '' && !allowedDates.has(String(input.dateField))) throw new AppError('BAD_REQUEST', `不支持的${config.title}日期字段。`)
  const reportDateField = input.dateField === 'checkDate' || input.dateField === 'reportReviewDate' ? input.dateField : undefined
  const { dateField, searchField, ...query } = parseDataEntryQuery({ ...input, dateField: reportDateField ? undefined : input.dateField }, states)
  if (input.checkStatus !== undefined && input.checkStatus !== '' && ![`未${config.label}`, `已${config.label}`].includes(String(input.checkStatus))) throw new AppError('BAD_REQUEST', `不支持的${config.title}状态。`)
  return { ...query, searchField: searchField as ReportCheckQuery['searchField'], dateField: reportDateField ?? dateField as ReportCheckQuery['dateField'], checkStatus: input.checkStatus as ReportCheckQuery['checkStatus'] }
}
export function reportCheckRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: ReportCheckQuery, actor?: Actor, stage: ReportStage = 'check'): ReportCheckRow[] {
  const config = reportStages[stage], sources = new Map(samples.map(sample => [sample.id, sample]))
  const { dateField, ...filters } = query
  const reportDateField = dateField === 'checkDate' || dateField === 'reportReviewDate' ? dateField : undefined
  const entryQuery = dateField === 'checkDate' || dateField === 'reportReviewDate' ? { ...filters, from: undefined, to: undefined } : { ...filters, dateField }
  const eligible = samples.filter(sample => isReportCheckSample(sample, stage)).map(sample => sample.dataStatus === config.previous ? { ...sample, dataStatus: config.pending } : sample)
  return dataEntryRows(eligible, entryQuery, [config.pending, config.completed]).map((row): ReportCheckRow => {
    const sample = sources.get(row.id)!, info = sample[config.infoKey], checked = sample.dataStatus === config.completed
    return { ...row, checker: checked ? info?.actorName || '' : '', checkDate: checked ? info?.date || info?.at.slice(0, 10) || '' : '',
      reportChecker: sample.reportCheckInfo?.actorName || '',
      reportCheckDate: sample.reportCheckInfo?.date || sample.reportCheckInfo?.at.slice(0, 10) || '',
      reportReviewer: sample.reportReviewInfo?.actorName || '',
      reportReviewDate: sample.reportReviewInfo?.date || sample.reportReviewInfo?.at.slice(0, 10) || '',
      changeCount: sample.reportChangeCount ?? null, checkStatus: `${checked ? '已' : '未'}${config.label}`,
      ...(actor ? reportCheckCapabilities(actor, sample, stage) : { canCheck: false, canUndoCheck: false, canVoid: false }) }
  }).filter(row => (!query.checkStatus || row.checkStatus === query.checkStatus)
    && (!reportDateField || (!query.from || !!row[reportDateField] && row[reportDateField] >= query.from) && (!query.to || !!row[reportDateField] && row[reportDateField] <= query.to)))
}
