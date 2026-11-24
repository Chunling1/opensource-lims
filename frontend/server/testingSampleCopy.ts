import type { RegistrationSample, RegistrationState } from '../src/types/commissions/registration'
import { sampleCopyTypes, sampleCopyNextState, sampleCopyReportSuffix, sampleCopyStates, sampleCopySearchFields, sampleCopyDateFields, type SampleCopyInput, type SampleCopyQuery, type SampleCopyRow } from '../src/types/testing/sampleCopy'
import { dataEntryRows, parseDataEntryQuery } from './testingDataEntry'
import { AppError } from '../src/services/common/errors'
import { summarySample } from './registrationSummary'

export function parseSampleCopyInput(input: Record<string, unknown>): SampleCopyInput {
  if (typeof input.requestId !== 'string' || !/^[a-zA-Z0-9-]{16,80}$/.test(input.requestId) || !Number.isInteger(input.version) || Number(input.version) < 1) throw new AppError('VALIDATION', '复制请求格式有误，请重新打开复制对话框。')
  const sampleType = sampleCopyTypes.find(type => type === input.sampleType)
  if (!sampleType || typeof input.dataStatus !== 'string' || !sampleCopyNextState(input.dataStatus)) throw new AppError('VALIDATION', '请选择有效的样品类型及数据状态。')
  const editable = sampleType === sampleCopyTypes[0]
  if (editable && (typeof input.reportSuffix !== 'string' || !input.reportSuffix.trim() || input.reportSuffix.trim().length > 40 || /[\x00-\x1f\x7f]/.test(input.reportSuffix))) throw new AppError('VALIDATION', '请填写不超过 40 字的报告编号后缀。')
  if (editable && (typeof input.testingDepartment !== 'string' || input.testingDepartment.length > 200)) throw new AppError('VALIDATION', '请选择有效检测部门。')
  return { requestId: input.requestId, version: input.version as number, sampleType, dataStatus: input.dataStatus,
    reportSuffix: sampleCopyReportSuffix(sampleType, editable ? input.reportSuffix as string : ''), testingDepartment: editable ? (input.testingDepartment as string).trim() : '' }
}

export function sampleCopyDataStatus(sample: Pick<RegistrationSample, 'status' | 'dataStatus'>) {
  if (sample.status === 'voided') return '委托已作废'
  if (sample.status === 'void_pending') return '委托作废申请中'
  const aliases: Record<string, string> = { '完成登记': '委托登记完成', '合同评审中': '委托复核中', '评审完成': '委托复核完成', '合同评审完成': '委托复核完成', '作废申请中': '委托作废申请中', '已作废': '委托已作废' }
  return aliases[sample.dataStatus] || sample.dataStatus
}
export function isSampleCopySample(sample: Pick<RegistrationSample, 'status' | 'dataStatus'>) { return (sampleCopyStates as readonly string[]).includes(sampleCopyDataStatus(sample)) }
export function resetCopiedWorkflow(sample: RegistrationSample) {
  const registration = ['委托登记中', '委托登记完成'].includes(sample.dataStatus)
  const reviewed = ['报告审核完成', '报告批准完成'].includes(sample.dataStatus)
  if (registration) { sample.reviewStatus = 'unreviewed'; delete sample.contractReview }
  if (!reviewed) {
    delete sample.dataCheckInfo; delete sample.reportCheckInfo; delete sample.reportReviewInfo
    if (sample.workflow) { delete sample.workflow.checkDate; delete sample.workflow.auditDate }
  }
  if (sample.dataStatus !== '报告批准完成') {
    delete sample.reportApprovalInfo
    if (sample.workflow) delete sample.workflow.approvalDate
  }
  if (sample.workflow) { delete sample.workflow.issueDate; delete sample.workflow.archiveDate }
  delete sample.voidApplication; delete sample.commissionChange; delete sample.dataChange
  delete sample.reportCheckIssues
  delete sample.reportRelease; delete sample.reportReleaseHistory; delete sample.reportPricing
}
export function parseSampleCopyQuery(input: Record<string, unknown>): SampleCopyQuery {
  const dateField = sampleCopyDateFields.find(field => field.value === input.dateField)?.value
  if (input.dateField !== undefined && input.dateField !== '' && !dateField) throw new AppError('BAD_REQUEST', '复制样品数据日期字段有误。')
  const parsed = parseDataEntryQuery({ ...input, dateField: undefined }, sampleCopyStates)
  const searchField = sampleCopySearchFields.find(field => field.value === parsed.searchField)?.value
  if (parsed.searchField && !searchField) throw new AppError('BAD_REQUEST', '复制样品数据查询内容有误。')
  return { ...parsed, searchField, dateField }
}
export function sampleCopyRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: SampleCopyQuery, state: RegistrationState): SampleCopyRow[] {
  const sources = new Map(samples.map(sample => [sample.id, sample]))
  const normalized = samples.map(sample => ({ ...sample, dataStatus: sampleCopyDataStatus(sample) }))
  const { dateField, ...filters } = query
  const workflowDate = dateField && dateField !== 'commissionDate' && dateField !== 'testStartDate' && dateField !== 'testEndDate' ? dateField : undefined
  const entryQuery = dateField === undefined || dateField === 'commissionDate' || dateField === 'testStartDate' || dateField === 'testEndDate' ? { ...filters, dateField } : { ...filters, from: undefined, to: undefined }
  return dataEntryRows(normalized, entryQuery, sampleCopyStates, true).map(row => {
    const sample = sources.get(row.id)!, entry = state.dataEntries?.[row.id], prices = summarySample(sample)
    const release = sample.reportRelease
    const printed = release?.form === '纸质' && release.printStatus === '打印完成'
      ? [...release.history].reverse().find(event => event.action === '打印完成') : undefined
    const printedAt = printed ? new Date(printed.at) : undefined
    const receipt = release?.distributionStatus === '已发放' ? release.receipt : undefined
    return { ...row, canCopy: false, testingDepartment: sample.details?.testingDepartment || '',
      // Leave unsupported facts empty rather than infer them from assigned people or delivery methods.
      changeCount: null, reportDeliveryStatus: '', reportArchiveStatus: '', priceAdjustmentStatus: '', paymentStatus: sample.details?.paymentStatus || '',
      collectionPerson: sample.flowInfo?.collection?.name || '', collectionDate: sample.flowInfo?.collection?.date || '',
      inboundDate: sample.inboundInfo?.receipt?.date || '', inboundPerson: sample.inboundInfo?.receipt?.name || '',
      outboundDate: sample.outboundInfo?.receipt?.date || '', outboundPerson: sample.outboundInfo?.receipt?.name || '',
      checkDate: sample.workflow?.checkDate || '', checker: sample.dataCheckInfo?.actorName || '',
      auditDate: sample.workflow?.auditDate || '', auditor: '', approvalDate: sample.workflow?.approvalDate || '', approver: '',
      issueDate: sample.workflow?.issueDate || '',
      printDate: printedAt && Number.isFinite(printedAt.getTime()) ? printedAt.toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' }) : '',
      printPerson: printed?.actorName || '', distributionDate: receipt?.date || '', distributionPerson: receipt?.actorName || '',
      archiveDate: sample.workflow?.archiveDate || '', archiver: '',
      conclusion: entry?.form.conclusion || '', failedParameters: entry?.form.failedParameters || '',
      standardPrice: prices.standardPrice, discountPrice: prices.discountPrice, actualPrice: prices.actualPrice }
  }).filter(row => !workflowDate || (!query.from || !!row[workflowDate] && row[workflowDate] >= query.from) && (!query.to || !!row[workflowDate] && row[workflowDate] <= query.to))
}
