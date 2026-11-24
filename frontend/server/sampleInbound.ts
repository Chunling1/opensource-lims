import { inboundStatus, outboundStatus } from '../src/types/commissions/workflow'
import { AppError, problem } from '../src/services/common/errors'
import { parsePlanSelection } from './testPlanSelection'
import { summarySample } from './registrationSummary'
import { inboundStates, inboundLocations, inboundConditions, type InboundReceipt, type InboundQuery, type InboundRow } from '../src/types/samples/inbound'
import { parseStockReceipt, stockField } from './stockReceipt'
import { outboundStates } from '../src/types/samples/outbound'
import type { RegistrationSample } from '../src/types/commissions/registration'
export function parseInboundReceipt(input: unknown): InboundReceipt {
  const receipt = parseStockReceipt(input, '入库')
  const data = input as Record<string, unknown>
  if (!inboundLocations.includes(data.location as InboundReceipt['location'])) throw problem('VALIDATION', '请选择有效的样品存放地点。', 'location')
  if (!inboundConditions.includes(data.condition as InboundReceipt['condition'])) throw problem('VALIDATION', '请选择正常或异常的样品状态。', 'condition')
  return { ...receipt, location: data.location as InboundReceipt['location'], condition: data.condition as InboundReceipt['condition'], notes: stockField(data, 'notes', '备注（最多 2000 字）', 2000, false) }
}
export function parseInboundQuery(input: Record<string, unknown>): InboundQuery {
  return parseStorageQuery(input, inboundStates)
}
export function parseOutboundQuery(input: Record<string, unknown>): InboundQuery {
  return parseStorageQuery(input, outboundStates)
}
export function parseStorageQuery(input: Record<string, unknown>, states: readonly string[], dateLabel = '委托日期'): InboundQuery {
  const query: InboundQuery = { plans: parsePlanSelection(input.plans) }
  for (const key of ['code', 'status', 'from', 'to', 'site'] as const) {
    if (input[key] === undefined || input[key] === '') continue
    if (typeof input[key] !== 'string' || input[key].length > 200) throw new AppError('BAD_REQUEST', '查询条件格式有误。')
    query[key] = input[key].trim()
  }
  for (const value of [query.from, query.to]) if (value && (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value)) throw new AppError('VALIDATION', `请检查${dateLabel}范围。`)
  if (query.from && query.to && query.from > query.to) throw new AppError('VALIDATION', `请检查${dateLabel}范围。`)
  if (query.status && !states.includes(query.status)) throw new AppError('BAD_REQUEST', '不支持的数据状态。')
  for (const key of ['page', 'pageSize'] as const) {
    if (input[key] === undefined) continue
    if (!Number.isSafeInteger(input[key]) || Number(input[key]) < 1 || key === 'pageSize' && ![10, 20, 50].includes(Number(input[key]))) throw new AppError('BAD_REQUEST', '分页参数有误。')
    query[key] = Number(input[key])
  }
  if (input.sort !== undefined) {
    if (!['code', 'commissionDate'].includes(String(input.sort))) throw new AppError('BAD_REQUEST', '排序字段有误。')
    query.sort = input.sort as InboundQuery['sort']
  }
  if (input.direction !== undefined) {
    if (!['asc', 'desc'].includes(String(input.direction))) throw new AppError('BAD_REQUEST', '排序方向有误。')
    query.direction = input.direction as InboundQuery['direction']
  }
  if (input.ids !== undefined) {
    if (!Array.isArray(input.ids) || input.ids.length > 50 || input.ids.some(id => typeof id !== 'string' || !id || id.length > 100)) throw new AppError('BAD_REQUEST', '记录编号格式有误。')
    query.ids = [...new Set(input.ids)]
  }
  return query
}
export function isInboundSample(row: Pick<RegistrationSample, 'dataStatus' | 'status'>) {
  return (inboundStates as readonly string[]).includes(inboundStatus(row.dataStatus)) && !['voided', 'void_pending'].includes(row.status)
}
export function isOutboundSample(row: Pick<RegistrationSample, 'dataStatus' | 'status'>) {
  return (outboundStates as readonly string[]).includes(outboundStatus(row.dataStatus)) && !['voided', 'void_pending'].includes(row.status)
}
export function inboundRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: InboundQuery, planIds: Set<string>, restricted: boolean): InboundRow[] {
  return storageRows(samples.filter(isInboundSample).map(row => ({ ...row, dataStatus: inboundStatus(row.dataStatus) })), query, planIds, restricted)
}
export function outboundRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: InboundQuery, planIds: Set<string>, restricted: boolean): InboundRow[] {
  return storageRows(samples.filter(isOutboundSample).map(row => ({ ...row, dataStatus: outboundStatus(row.dataStatus) })), query, planIds, restricted)
}
export function storageRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: InboundQuery, planIds: Set<string>, restricted: boolean): InboundRow[] {
  const rows = samples
    .filter(row => (!restricted || planIds.has(row.details?.testPlanId || '')) && (!query.status || row.dataStatus === query.status)
      && (!query.site || row.inboundInfo?.site === query.site) && (!query.code || row.code.toLowerCase().includes(query.code.toLowerCase()))
      && (!query.ids || query.ids.includes(row.id))
      && (!query.from || !!row.commissionInfo.commissionDate && row.commissionInfo.commissionDate >= query.from)
      && (!query.to || !!row.commissionInfo.commissionDate && row.commissionInfo.commissionDate <= query.to))
    .map(row => ({ ...summarySample(row), commissionDate: row.commissionInfo.commissionDate || '', site: row.inboundInfo?.site || '', groupNumber: row.inboundInfo?.groupNumber || '', contractCode: row.commissionInfo.contract || '',
      customerAddress: row.commissionInfo.customerAddress || '', contact: row.commissionInfo.contact || '', phone: row.commissionInfo.phone || '',
      testPlanName: row.details?.testPlan || '', manufacturer: row.details?.manufacturer || '', notes: row.notes || '', mailingAddress: row.details?.mailingAddress || '' }))
  const key = query.sort || 'code', direction = query.direction === 'desc' ? -1 : 1
  return rows.sort((a, b) => {
    if (!a[key] !== !b[key]) return a[key] ? -1 : 1
    return (a[key].localeCompare(b[key], 'zh-CN', { numeric: true }) || a.code.localeCompare(b.code, 'zh-CN', { numeric: true })) * direction
  })
}
