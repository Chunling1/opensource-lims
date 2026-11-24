import { isDataEntrySample } from './testingDataEntry'
import type { RegistrationSample } from '../src/types/commissions/registration'
import { taskQueryStates, type TaskQuery, type TaskQueryRow } from '../src/types/testing/taskQuery'
import { assignmentRows, parseAssignmentQuery } from './testingAssignment'

export const taskReturnAllowed = (sample: RegistrationSample) => isTaskQuerySample(sample) || isDataEntrySample(sample)

export function taskQueryStatus(sample: Pick<RegistrationSample, 'dataStatus'>) {
  const aliases: Record<string, string> = { '完成登记': '委托登记完成', '合同评审中': '委托复核中', '评审完成': '委托复核完成' }
  return aliases[sample.dataStatus] || sample.dataStatus
}
export function isTaskQuerySample(sample: RegistrationSample) {
  return !['voided', 'void_pending'].includes(sample.status) && (taskQueryStates as readonly string[]).includes(taskQueryStatus(sample))
}
export const parseTaskQuery = (input: Record<string, unknown>): TaskQuery => parseAssignmentQuery(input, taskQueryStates)
export function taskQueryRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: TaskQuery): TaskQueryRow[] {
  const sources = new Map(samples.map(sample => [sample.id, sample]))
  return assignmentRows(samples.map(sample => ({ ...sample, dataStatus: taskQueryStatus(sample) })), query, taskQueryStates).map(({ canAssign, canUndoAssign, ...row }) => ({
    ...row, inspector: sources.get(row.id)?.details?.inspector || '', canReturn: false,
  }))
}
