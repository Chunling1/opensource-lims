import type { RegistrationSample, RegistrationState } from '../src/types/commissions/registration'
import type { Actor } from '../src/types/lims'
import { reportQueryDateFields, reportQuerySearchFields, reportQueryStates, type ReportQueryQuery, type ReportQueryRow } from '../src/types/reports/reportQuery'
import { registrationCanWrite, sampleReadOnlyReason } from '../src/services/commissions/registrationService'
import { dataEntryRows, parseDataEntryQuery } from './testingDataEntry'
import { sampleCopyDataStatus } from './testingSampleCopy'
import { sampleCopyStates } from '../src/types/testing/sampleCopy'
import { summarySample } from './registrationSummary'
import { normalizeConclusion, entryConclusions } from '../src/types/testing/dataEntryDetail'
import { AppError } from '../src/services/common/errors'

const reportDates = ['checkDate', 'auditDate', 'approvalDate', 'archiveDate', 'printDate'] as const
export function parseReportQuery(input: Record<string, unknown>): ReportQueryQuery {
  for (const [key, choices] of [['dateField', reportQueryDateFields], ['searchField', reportQuerySearchFields]] as const) {
    if (input[key] !== undefined && input[key] !== '' && !choices.some(choice => choice.value === input[key])) throw new AppError('BAD_REQUEST', '报告查询条件有误。')
  }
  const savedDate = reportDates.some(key => key === input.dateField)
  const query = parseDataEntryQuery({ ...input, dateField: savedDate ? undefined : input.dateField }, reportQueryStates)
  return { ...query, dateField: (savedDate ? input.dateField : query.dateField) as ReportQueryQuery['dateField'] }
}
export function reportQueryStatus(sample: RegistrationSample) {
  const status = sampleCopyDataStatus(sample), release = sample.reportRelease
  if (!release || release.supersededAt || ['void_pending', 'voided'].includes(sample.status) || /更改|取消|终止/.test(status)) return status
  if (release.archiveStatus === '已归档') return '报告归档完成'
  if (release.distributionStatus === '已发放') return '报告发放完成'
  return release.form === '电子' ? release.signing?.status === '签章完成' ? '报告签章完成' : '报告签章中' : release.printStatus === '打印完成' ? '报告打印完成' : '报告打印中'
}
export const canQueryVoid = (actor: Actor, sample: RegistrationSample) => actor.roles.some(role => ['admin', 'reports', 'reviewer', 'approver'].includes(role)) && ['pending', 'completed'].includes(sample.status) && !/更改|取消|终止/.test(sample.dataStatus) && !sample.reportRelease?.supersededAt
const date = (at?: string) => at && Number.isFinite(Date.parse(at)) ? new Date(at).toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' }) : ''
export function reportQueryRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: ReportQueryQuery, state: RegistrationState, actor: Actor): ReportQueryRow[] {
  const sources = new Map(samples.map(sample => [sample.id, sample]))
  const normalized = samples.map(sample => {
    const entry = state.dataEntries?.[sample.id]
    return { ...sample, dataStatus: reportQueryStatus(sample), assignmentInfo: { ...sample.assignmentInfo, ...(entry ? { conclusion: entryConclusions.find(item => item === normalizeConclusion(entry.form.conclusionStatus)) } : {}) } }
  })
  const { dateField, searchField, ...filters } = query
  const savedDate = reportDates.find(key => key === dateField)
  const rows = dataEntryRows(normalized, { ...filters, searchField: searchField as 'code', ...(savedDate ? { from: undefined, to: undefined } : { dateField: dateField as 'commissionDate' }) }, [...reportQueryStates, ...normalized.map(row => row.dataStatus)], true)
  return rows.map((row): ReportQueryRow => {
    const sample = sources.get(row.id)!, release = sample.reportRelease, entry = state.dataEntries?.[sample.id], prices = summarySample(sample)
    const receipt = release?.distributionStatus === '已发放' ? release.receipt : undefined
    const archive = release?.archiveStatus === '已归档' ? release.archive : undefined
    const printed = release?.printStatus === '打印完成' ? [...release.history].reverse().find(event => event.action === '打印完成') : undefined
    const completion = [...sample.events.filter(event => ['录入完成', '检测数据录入完成'].includes(event.action)), ...(entry?.events || []).filter(event => ['complete', 'undo'].includes(event.action))].sort((a, b) => b.at.localeCompare(a.at))[0]
    const workflow = sampleCopyStates.slice(0, sampleCopyStates.indexOf('报告打印完成') + 1), step = workflow.findIndex(status => status === row.dataStatus)
    const inactive = ['voided', 'void_pending'].includes(sample.status) || /更改|取消|终止/.test(row.dataStatus) || !!release?.supersededAt
    const pendingStatus = inactive ? '' : release ? archive ? '' : receipt ? '报告归档中' : release.form === '电子' && release.signing?.status !== '签章完成' ? '报告签章中' : release.form === '纸质' && release.printStatus !== '打印完成' ? '报告打印中' : '报告发放中' : step >= 0 ? workflow[step + 1] || '' : ''
    return { ...row, canView: true, canVoid: canQueryVoid(actor, sample),
      releaseId: release?.id || '', form: release?.form || '', signingStatus: release?.signing?.status || '',
      erpProjectNumber: sample.commissionInfo.erpContract || '', erpContractNumber: sample.erpContractNumber || '', contractType: sample.contractType || '', changeCount: sample.reportChangeCount ?? null,
      reportDeliveryStatus: release ? receipt ? '报告已发放' : '报告发放中' : '', reportArchiveStatus: release ? archive ? '报告已归档' : '报告归档中' : '',
      paymentStatus: sample.details?.paymentStatus || '', priceAdjustmentStatus: sample.reportPricing ? '已调整' : '', recipient: receipt?.recipient || '', collectionDate: receipt?.date || '', pendingStatus,
      inboundDate: sample.inboundInfo?.receipt?.date || '', inboundPerson: sample.inboundInfo?.receipt?.name || '', outboundDate: sample.outboundInfo?.receipt?.date || '', outboundPerson: sample.outboundInfo?.receipt?.name || '',
      checkDate: sample.reportCheckInfo?.date || date(sample.reportCheckInfo?.at), checker: sample.reportCheckInfo?.actorName || '', dataCompletedDate: completion?.action === 'undo' ? '' : date(completion?.at),
      auditDate: sample.reportReviewInfo?.date || sample.workflow?.auditDate || date(sample.reportReviewInfo?.at), auditor: sample.reportReviewInfo?.actorName || '',
      approvalDate: date(release?.approvedAt) || sample.reportApprovalInfo?.date || sample.workflow?.approvalDate || '', approver: release?.approvedBy.name || sample.reportApprovalInfo?.actorName || '',
      printDate: date(printed?.at), printPerson: printed?.actorName || '', printCount: sample.reportPrintCount ?? null,
      distributionDate: receipt?.date || '', distributionPerson: receipt?.actorName || '', archiveDate: archive?.date || '', archiver: archive?.actorName || '',
      conclusion: entry?.form.conclusion || row.conclusion, failedParameters: entry?.form.failedParameters || '', standardPrice: prices.standardPrice, discountPrice: prices.discountPrice, actualPrice: prices.actualPrice }
  }).filter(row => !savedDate || (!query.from || !!row[savedDate] && row[savedDate] >= query.from) && (!query.to || !!row[savedDate] && row[savedDate] <= query.to))
}
