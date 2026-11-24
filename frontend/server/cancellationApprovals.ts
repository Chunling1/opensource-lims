import { AppError } from '../src/services/common/errors'
import { summarySample } from './registrationSummary'
import { cancellationDate, cancellationStates, type CancellationQuery, type CancellationRow, type CancellationSubmission } from '../src/types/commissions/cancellationApproval'
import type { RegistrationSample } from '../src/types/commissions/registration'

export function parseCancellationQuery(input: Record<string, unknown>): CancellationQuery {
  const query: CancellationQuery = {}
  for (const key of ['from', 'to'] as const) {
    if (input[key] === undefined || input[key] === '') continue
    const value = input[key]
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value) throw new AppError('VALIDATION', '请检查申请日期范围。')
    query[key] = value
  }
  if (query.from && query.to && query.from > query.to) throw new AppError('VALIDATION', '请检查申请日期范围。')
  if (input.result !== undefined && input.result !== '') {
    if (!(cancellationStates as readonly unknown[]).includes(input.result)) throw new AppError('BAD_REQUEST', '不支持的审批状态。')
    query.result = input.result as CancellationQuery['result']
  }
  for (const key of ['page', 'pageSize'] as const) {
    if (input[key] === undefined) continue
    if (!Number.isSafeInteger(input[key]) || Number(input[key]) < 1 || key === 'pageSize' && ![10, 20, 50].includes(Number(input[key]))) throw new AppError('BAD_REQUEST', '分页参数有误。')
    query[key] = Number(input[key])
  }
  if (input.sort !== undefined) {
    if (!['code', 'appliedAt', 'approvedAt'].includes(String(input.sort))) throw new AppError('BAD_REQUEST', '排序字段有误。')
    query.sort = input.sort as CancellationQuery['sort']
  }
  if (input.direction !== undefined) {
    if (!['asc', 'desc'].includes(String(input.direction))) throw new AppError('BAD_REQUEST', '排序方向有误。')
    query.direction = input.direction as CancellationQuery['direction']
  }
  if (input.ids !== undefined) {
    if (!Array.isArray(input.ids) || input.ids.length > 50 || input.ids.some(id => typeof id !== 'string' || !id || id.length > 100)) throw new AppError('BAD_REQUEST', '记录编号格式有误。')
    query.ids = [...new Set(input.ids)]
  }
  return query
}
export function parseCancellationSubmission(input: Record<string, unknown>): CancellationSubmission {
  if (!Number.isSafeInteger(input.version) || Number(input.version) < 1 || !['approved', 'rejected'].includes(String(input.decision)) || typeof input.reason !== 'string' || input.reason.length > 500) throw new AppError('BAD_REQUEST', '审批数据格式有误。')
  if (input.decision === 'rejected' && !input.reason.trim()) throw new AppError('VALIDATION', '请填写审批不通过原因。')
  return { version: Number(input.version), decision: input.decision as CancellationSubmission['decision'], reason: input.reason.trim() }
}
export function cancellationRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: CancellationQuery): CancellationRow[] {
  const rows = samples.filter(sample => !!sample.voidApplication).map(sample => {
    const application = sample.voidApplication!
    return { ...summarySample(sample), approvalResult: application.decision === 'approved' ? '申请通过' as const : application.decision === 'rejected' ? '申请不通过' as const : '申请中' as const,
      applicant: application.appliedBy.name, applicationReason: application.reason, appliedAt: application.appliedAt,
      approver: application.approvedBy?.name || '', approvedAt: application.approvedAt || '', rejectionReason: application.rejectionReason || '' }
  }).filter(row => (!query.result || row.approvalResult === query.result)
    && (!query.from || cancellationDate(row.appliedAt) >= query.from) && (!query.to || cancellationDate(row.appliedAt) <= query.to)
    && (!query.ids || query.ids.includes(row.id)))
  const key = query.sort || 'appliedAt', direction = query.direction === 'asc' ? 1 : -1
  return rows.sort((a, b) => {
    if (!a[key] !== !b[key]) return a[key] ? -1 : 1
    return (a[key].localeCompare(b[key], 'zh-CN', { numeric: true }) || a.code.localeCompare(b.code, 'zh-CN', { numeric: true })) * direction
  })
}
