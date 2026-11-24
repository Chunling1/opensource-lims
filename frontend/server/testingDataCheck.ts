import type { RegistrationSample } from '../src/types/commissions/registration'
import type { Actor } from '../src/types/lims'
import { dataCheckStates, type DataCheckQuery, type DataCheckRow } from '../src/types/testing/dataCheck'
import { dataEntryRows, parseDataEntryQuery } from './testingDataEntry'

export function isDataCheckSample(sample: Pick<RegistrationSample, 'status' | 'dataStatus'>) {
  return !['voided', 'void_pending'].includes(sample.status) && ['检测数据录入完成', ...dataCheckStates].includes(sample.dataStatus)
}
export function parseDataCheckQuery(input: Record<string, unknown>): DataCheckQuery {
  const query = parseDataEntryQuery({ ...input, dateField: input.dateField === 'checkDate' ? undefined : input.dateField }, dataCheckStates)
  return input.dateField === 'checkDate' ? { ...query, dateField: 'checkDate' } : query
}
export function dataCheckCapabilities(actor: Actor, sample: RegistrationSample) {
  const allowed = actor.roles.some(role => ['admin', 'testing', 'reviewer'].includes(role))
    && (actor.scope === 'all' || actor.departmentId === sample.departmentId) && isDataCheckSample(sample)
    && !sample.workflow?.auditDate && !sample.workflow?.approvalDate
  return { canCheck: allowed && sample.dataStatus !== '检测数据校核完成', canUndoCheck: allowed && sample.dataStatus === '检测数据校核完成' }
}
export function dataCheckRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: DataCheckQuery): DataCheckRow[] {
  const sources = new Map(samples.map(sample => [sample.id, sample]))
  // Completed entry records join the pending check queue without changing them on a read.
  const pending = samples.filter(isDataCheckSample).map(sample => ({ ...sample, dataStatus: sample.dataStatus === '检测数据录入完成' ? '检测数据校核中' : sample.dataStatus }))
  const { dateField, ...filters } = query
  const entryQuery = dateField === 'checkDate' ? { ...filters, from: undefined, to: undefined } : { ...filters, dateField }
  return dataEntryRows(pending, entryQuery, dataCheckStates).map(row => {
    const sample = sources.get(row.id)!
    return { ...row, checker: sample.dataCheckInfo?.actorName || '', checkDate: sample.workflow?.checkDate || '', canCheck: false, canUndoCheck: false }
  }).filter(row => dateField !== 'checkDate' || (!query.from || !!row.checkDate && row.checkDate >= query.from) && (!query.to || !!row.checkDate && row.checkDate <= query.to))
}
