import type { RegistrationSample, RegistrationState } from '../src/types/commissions/registration'
import { dataQueryStates, type DataQueryQuery, type DataQueryRow } from '../src/types/testing/dataQuery'
import { normalizeConclusion, entryConclusions } from '../src/types/testing/dataEntryDetail'
import { sampleCopyDataStatus } from './testingSampleCopy'
import { dataEntryRows, parseDataEntryQuery } from './testingDataEntry'
import { assignmentPrintable } from './testingAssignment'

export const parseDataQueryQuery = (input: Record<string, unknown>) => parseDataEntryQuery(input, dataQueryStates)
export function dataQueryRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: DataQueryQuery, state: RegistrationState): DataQueryRow[] {
  const sources = new Map(samples.map(sample => [sample.id, sample]))
  const normalized = samples.map(sample => {
    const entry = state.dataEntries?.[sample.id]
    return { ...sample, dataStatus: sampleCopyDataStatus(sample),
      assignmentInfo: { ...sample.assignmentInfo, ...(entry ? { conclusion: entryConclusions.find(value => value === normalizeConclusion(entry.form.conclusionStatus)) } : {}) } }
  })
  const workflow = dataQueryStates.slice(0, dataQueryStates.indexOf('报告打印完成') + 1)
  return dataEntryRows(normalized, query, dataQueryStates, true).map(row => {
    const sample = sources.get(row.id)!, entry = state.dataEntries?.[row.id], step = workflow.findIndex(status => status === row.dataStatus)
    return { ...row, canPrintTask: assignmentPrintable(sample), pendingStatus: step >= 0 ? workflow[step + 1] || '' : '',
      checkDate: sample.workflow?.checkDate || '', checker: sample.dataCheckInfo?.actorName || '',
      conclusion: entry?.form.conclusion || '', failedParameters: entry?.form.failedParameters || '' }
  })
}
