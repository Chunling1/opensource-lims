import { storageRows, parseStorageQuery } from './sampleInbound'
import { disposalStates, disposalRequirements, disposalSearchFields, type DisposalAction, type DisposalReceipt, type DisposalQuery } from '../src/types/samples/disposal'
import { AppError, problem } from '../src/services/common/errors'
import { stockDate, stockField } from './stockReceipt'
import { demoActors } from '../src/services/storage/demoActors'
import type { RegistrationSample } from '../src/types/commissions/registration'
import type { InboundRow } from '../src/types/samples/inbound'

export function parseDisposalQuery(input: Record<string, unknown>): DisposalQuery {
  const completed = input.status === '样品已处置'
  const query: DisposalQuery = parseStorageQuery({ ...input, code: undefined, site: undefined, from: completed ? input.from : undefined, to: completed ? input.to : undefined }, disposalStates, '处置时间')
  if (input.searchField !== undefined && !disposalSearchFields.some(field => field.value === input.searchField)) throw new AppError('BAD_REQUEST', '不支持的内容查询字段。')
  query.searchField = input.searchField as DisposalQuery['searchField'] || 'code'
  for (const key of ['keyword', 'requirement'] as const) {
    if (input[key] === undefined || input[key] === '') continue
    if (typeof input[key] !== 'string' || input[key].length > 200) throw new AppError('BAD_REQUEST', '查询条件格式有误。')
    query[key] = input[key].trim()
  }
  if (query.requirement && !disposalRequirements.includes(query.requirement as typeof disposalRequirements[number])) throw new AppError('BAD_REQUEST', '不支持的处置要求。')
  return query
}

export function isDisposalSample(row: RegistrationSample) {
  return (disposalStates as readonly string[]).includes(row.dataStatus) && !['voided', 'void_pending'].includes(row.status)
}
export function allowedDisposalActions(row: RegistrationSample): DisposalAction[] {
  return isDisposalSample(row) ? [row.dataStatus === '样品待处置' ? 'dispose' : 'undo'] : []
}
export function disposalRequirement(value?: string) { return value === '委托中心托运' ? '中心处置' : value || '' }
export function parseDisposalReceipt(input: unknown): DisposalReceipt {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new AppError('VALIDATION', '请填写样品处置信息。')
  const data = input as Record<string, unknown>
  const result = stockField(data, 'result', '处置结果（最多 500 字）', 500), name = stockField(data, 'name', '处置人')
  if (!demoActors.some(user => user.name === name)) throw problem('VALIDATION', '未找到该处置人，请核对姓名后重新提交。', 'name')
  return { result, name, date: stockDate(data, '处置时间') }
}
export function disposalRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: DisposalQuery, planIds: Set<string>, restricted: boolean): InboundRow[] {
  const eligible = samples.filter(isDisposalSample), source = new Map(eligible.map(row => [row.id, row]))
  const keyword = query.keyword?.trim().toLocaleLowerCase()
  return storageRows(eligible, { ...query, code: undefined, status: undefined, from: undefined, to: undefined }, planIds, restricted).map(row => {
    const sample = source.get(row.id)!, info = sample.disposalInfo, receipt = info?.receipt
    return { ...row, testPlanName: sample.details?.testPlan || '', retentionTime: info?.retentionTime || '',
      customerRequirement: disposalRequirement(sample.details?.disposalMethod), disposalResult: receipt?.result || '',
      disposalDate: receipt?.date || '', disposalPerson: receipt?.name || '', disposalStatus: sample.dataStatus }
  }).filter(row => (!keyword || String(row[query.searchField || 'code']).toLocaleLowerCase().includes(keyword))
    && (!query.requirement || row.customerRequirement === query.requirement)
    && (!query.status || row.disposalStatus === query.status)
    && (query.status !== '样品已处置' || ((!query.from || !!row.disposalDate && row.disposalDate >= query.from) && (!query.to || !!row.disposalDate && row.disposalDate <= query.to))))
}
