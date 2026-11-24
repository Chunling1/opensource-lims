import { AppError } from '../src/services/common/errors'
import { summarySample } from './registrationSummary'
import { changeProblemSources, changeProcessingResults, type CommissionChangeQuery, type CommissionChangeRow } from '../src/types/commissions/commissionChanges'
import { sampleTypes, type RegistrationSample } from '../src/types/commissions/registration'

export function parseCommissionChangeQuery(input: unknown): CommissionChangeQuery {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new AppError('BAD_REQUEST', '查询条件格式有误。')
  const value = input as Record<string, unknown>, query: CommissionChangeQuery = {}
  for (const key of ['from', 'to', 'source', 'result', 'sampleType'] as const) {
    if (value[key] === undefined || value[key] === '') continue
    if (typeof value[key] !== 'string' || value[key].length > 200) throw new AppError('BAD_REQUEST', '查询条件格式有误。')
    query[key] = value[key].trim()
  }
  const validDate = (date: string) => /^\d{4}-\d{2}-\d{2}$/.test(date) && !Number.isNaN(Date.parse(date)) && new Date(date).toISOString().slice(0, 10) === date
  if (query.from && !validDate(query.from) || query.to && !validDate(query.to) || query.from && query.to && query.from > query.to) throw new AppError('VALIDATION', '请检查问题提交日期范围。')
  for (const [key, options] of [['source', changeProblemSources], ['result', changeProcessingResults], ['sampleType', sampleTypes]] as const) {
    if (query[key] && !(options as readonly string[]).includes(query[key]!)) throw new AppError('BAD_REQUEST', '不支持的查询选项。')
  }
  for (const key of ['page', 'pageSize'] as const) {
    if (value[key] === undefined) continue
    if (!Number.isSafeInteger(value[key]) || Number(value[key]) < 1 || key === 'pageSize' && ![10, 20, 50].includes(Number(value[key]))) throw new AppError('BAD_REQUEST', '分页参数有误。')
    query[key] = Number(value[key])
  }
  if (value.sort !== undefined) {
    if (!['commissionCode', 'code', 'problemSubmittedAt'].includes(String(value.sort))) throw new AppError('BAD_REQUEST', '不支持的排序字段。')
    query.sort = value.sort as CommissionChangeQuery['sort']
  }
  if (value.direction !== undefined) {
    if (!['asc', 'desc'].includes(String(value.direction))) throw new AppError('BAD_REQUEST', '不支持的排序方向。')
    query.direction = value.direction as CommissionChangeQuery['direction']
  }
  if (value.ids !== undefined) {
    if (!Array.isArray(value.ids) || value.ids.length > 50 || value.ids.some(id => typeof id !== 'string' || !id || id.length > 100)) throw new AppError('BAD_REQUEST', '记录编号格式有误。')
    query.ids = [...new Set(value.ids)]
  }
  return query
}
export function changeRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: CommissionChangeQuery): CommissionChangeRow[] {
  const rows = samples.map(sample => {
    const problem = sample.commissionChange
    return { ...summarySample(sample), problemSource: problem?.source || '', problemSubmitter: problem?.submittedBy || '',
      problemSubmittedAt: problem?.submittedAt || '', problemType: problem?.type || '', problemDescription: problem?.description || '', processingResult: problem?.result || '' }
  }).filter(row => (!query.from || !!row.problemSubmittedAt && row.problemSubmittedAt.slice(0, 10) >= query.from)
    && (!query.to || !!row.problemSubmittedAt && row.problemSubmittedAt.slice(0, 10) <= query.to)
    && (!query.source || row.problemSource === query.source) && (!query.result || row.processingResult === query.result)
    && (!query.sampleType || row.sampleType === query.sampleType) && (!query.ids || query.ids.includes(row.id)))
  const key = query.sort || 'commissionCode', direction = query.direction === 'desc' ? -1 : 1
  return rows.sort((a, b) => {
    if (!a[key] !== !b[key]) return a[key] ? -1 : 1
    return (a[key].localeCompare(b[key], 'zh-CN', { numeric: true }) || a.code.localeCompare(b.code, 'zh-CN', { numeric: true })) * direction
  })
}
