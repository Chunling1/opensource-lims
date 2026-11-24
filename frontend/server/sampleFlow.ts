import type { RegistrationSample } from '../src/types/commissions/registration'
import { flowStates, flowDateFields, flowDateEnabled, type FlowQuery, type FlowRow } from '../src/types/samples/flow'
import { AppError } from '../src/services/common/errors'
import { parseStorageQuery, storageRows } from './sampleInbound'
import { disposalRequirement } from './sampleDisposal'

export function flowStatus(row: RegistrationSample) {
  if (['voided', 'void_pending'].includes(row.status)) return ''
  const aliases: Record<string, string> = { '样品入库完成': '样品已入库', '样品出库中': '样品已入库', '样品待领取': '样品已出库' }
  const status = aliases[row.dataStatus] || row.dataStatus
  return (flowStates as readonly string[]).includes(status) ? status : ''
}
export function isFlowSample(row: RegistrationSample) { return !!flowStatus(row) }
export function parseFlowQuery(input: Record<string, unknown>): FlowQuery {
  const query: FlowQuery = parseStorageQuery({ ...input, from: undefined, to: undefined, site: undefined }, flowStates)
  const fields = flowDateFields.filter(field => flowDateEnabled(field.key, query.status))
  if (input.dates === undefined || !fields.length) return query
  if (!input.dates || typeof input.dates !== 'object' || Array.isArray(input.dates)) throw new AppError('BAD_REQUEST', '时间范围格式有误。')
  const ranges = input.dates as Record<string, unknown>
  query.dates = {}
  for (const field of fields) {
    const range = ranges[field.key]
    if (range === undefined) continue
    if (!range || typeof range !== 'object' || Array.isArray(range)) throw new AppError('VALIDATION', `请检查${field.label}范围。`)
    const inputRange = range as Record<string, unknown>
    const dates = parseStorageQuery({ from: inputRange.from, to: inputRange.to }, [], field.label)
    if (!dates.from || !dates.to) throw new AppError('VALIDATION', `请填写完整的${field.label}范围。`)
    query.dates[field.key] = { from: dates.from, to: dates.to }
  }
  return query
}
export function flowRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: FlowQuery, planIds: Set<string>, restricted: boolean): FlowRow[] {
  const eligible = samples.filter(row => isFlowSample(row) && (!query.status || flowStatus(row) === query.status))
  const source = new Map(eligible.map(row => [row.id, row]))
  return storageRows(eligible, { ...query, status: undefined, from: undefined, to: undefined }, planIds, restricted).map(row => {
    const sample = source.get(row.id)!, status = flowStatus(sample), inbound = sample.inboundInfo?.receipt
    const outbound = status === '样品已入库' ? undefined : sample.outboundInfo?.receipt
    const disposal = sample.dataStatus === '样品已处置' ? sample.disposalInfo?.receipt : undefined
    return { ...row, flowStatus: status,
      inboundPerson: inbound?.name || '', inboundDate: inbound?.date || '', outboundPerson: outbound?.name || '', outboundDate: outbound?.date || '',
      restockPerson: sample.flowInfo?.restock?.name || '', restockDate: sample.flowInfo?.restock?.date || '',
      collectionPerson: sample.flowInfo?.collection?.name || '', collectionDate: sample.flowInfo?.collection?.date || '',
      retentionTime: sample.disposalInfo?.retentionTime || '', customerRequirement: disposalRequirement(sample.details?.disposalMethod),
      disposalResult: disposal?.result || '', disposalDate: disposal?.date || '', disposalPerson: disposal?.name || '',
      customerSignature: sample.flowInfo?.customerSignature || '', disposalStatus: ['样品待处置', '样品已处置'].includes(sample.dataStatus) ? sample.dataStatus : '' }
  }).filter(row => flowDateFields.every(field => {
    const range = flowDateEnabled(field.key, query.status) ? query.dates?.[field.key] : undefined
    const date = row[field.column]
    return !range || !!date && date >= range.from && date <= range.to
  }))
}
