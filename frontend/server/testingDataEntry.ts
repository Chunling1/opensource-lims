import { dataEntryStatus } from '../src/types/commissions/workflow'
import { normalizeConclusion } from '../src/types/testing/dataEntryDetail'
import { AppError } from '../src/services/common/errors'
import { sampleTypes, type RegistrationSample } from '../src/types/commissions/registration'
import { assignmentConclusions } from '../src/types/testing/assignment'
import { dataEntryStates, dataEntrySearchFields, dataEntryDateFields, type DataEntryQuery, type DataEntryRow } from '../src/types/testing/dataEntry'
import { parseStorageQuery } from './sampleInbound'
import { assignmentRows } from './testingAssignment'

export function isDataEntrySample(sample: Pick<RegistrationSample, 'status' | 'dataStatus'>) {
  return !['voided', 'void_pending'].includes(sample.status) && (dataEntryStates as readonly string[]).includes(dataEntryStatus(sample.dataStatus))
}
export function parseDataEntryQuery(input: Record<string, unknown>, states: readonly string[] = dataEntryStates): DataEntryQuery {
  const base = parseStorageQuery(input, states, '查询日期')
  const query: DataEntryQuery = { plans: base.plans, status: base.status, from: base.from, to: base.to, page: base.page, pageSize: base.pageSize, sort: base.sort, direction: base.direction, ids: base.ids }
  const choices = { searchField: dataEntrySearchFields.map(field => field.value), dateField: dataEntryDateFields.map(field => field.value), sampleType: sampleTypes, conclusion: assignmentConclusions }
  for (const key of ['searchField', 'dateField', 'sampleType', 'conclusion', 'contains'] as const) {
    const value = key === 'conclusion' && typeof input[key] === 'string' ? normalizeConclusion(input[key]) : input[key]
    if (value === undefined || value === '') continue
    if (typeof value !== 'string' || value.length > 200 || key !== 'contains' && !(choices[key] as readonly string[]).includes(value)) throw new AppError('BAD_REQUEST', '检测数据录入查询条件格式有误。')
    Object.assign(query, { [key]: value.trim() })
  }
  return query
}
export function dataEntryRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: DataEntryQuery, states: readonly string[] = dataEntryStates, includeInactive = false): DataEntryRow[] {
  if (states === dataEntryStates) samples = samples.map(sample => ({ ...sample, dataStatus: dataEntryStatus(sample.dataStatus) }))
  const sources = new Map(samples.map(sample => [sample.id, sample]))
  const rows = assignmentRows(samples, {}, states, includeInactive).map(({ canAssign, canUndoAssign, canPrintTask, ...row }): DataEntryRow => {
    const sample = sources.get(row.id)!
    return { ...row, inspector: sample.details?.inspector || '', assignedDate: sample.assignmentInfo?.assignedDate || '',
      testStartDate: sample.workflow?.testStartDate || '', testEndDate: sample.workflow?.testEndDate || '',
      tester1: sample.dataEntryInfo?.tester1 || '', tester2: sample.dataEntryInfo?.tester2 || '',
      canReturn: false }
  }).filter(row => {
    const dateField = query.dateField || 'commissionDate'
    const date = row[dateField]
    const periods = sources.get(row.id)?.dataEntryInfo?.testDates
    const dates = periods && ['testStartDate', 'testEndDate'].includes(dateField) ? periods.map(period => dateField === 'testStartDate' ? period.from : period.kind === 'single' ? period.from : period.to) : [date]
    const matchesDate = !query.from && !query.to || dates.some(value => !!value && (!query.from || value >= query.from) && (!query.to || value <= query.to))
    return (!query.status || row.dataStatus === query.status) && (!query.sampleType || row.sampleType === query.sampleType)
      && (!query.conclusion || row.conclusion === query.conclusion) && (!query.ids || query.ids.includes(row.id))
      && (!query.contains || row[query.searchField || 'code'].toLocaleLowerCase().includes(query.contains.toLocaleLowerCase()))
      && matchesDate
  })
  const key = query.sort || 'code', direction = query.direction === 'desc' ? -1 : 1
  return rows.sort((a, b) => (a[key].localeCompare(b[key], 'zh-CN', { numeric: true }) || a.code.localeCompare(b.code, 'zh-CN', { numeric: true })) * direction)
}
