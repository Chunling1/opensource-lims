import { parseCommissionChangeQuery, changeRows } from './commissionChanges'
import { parsePlanSelection } from './testPlanSelection'
import type { DataChangeQuery } from '../src/types/testing/dataChanges'
import type { RegistrationSample } from '../src/types/commissions/registration'
export function parseDataChangeQuery(input: Record<string, unknown>): DataChangeQuery {
  return { ...parseCommissionChangeQuery(input), plans: parsePlanSelection(input.plans) }
}
export function dataChangeRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: DataChangeQuery) {
  return changeRows(samples.map(sample => ({ ...sample, commissionChange: sample.dataChange })), query)
}
