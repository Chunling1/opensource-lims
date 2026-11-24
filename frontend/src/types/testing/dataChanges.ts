import type { CommissionChangeQuery, CommissionChangeRow } from '../commissions/commissionChanges'
import type { RegistrationPage, RegistrationSample } from '../commissions/registration'
import type { PlanSelection, PlanSelectionState } from '../samples/inbound'
import type { Actor } from '../lims'
export interface DataChangeQuery extends CommissionChangeQuery { plans?: PlanSelection }
export interface DataChangePage extends RegistrationPage<CommissionChangeRow> { planSelection: PlanSelectionState }
export function isDataChangeSample(sample: Pick<RegistrationSample, 'status' | 'dataStatus'>) {
  return sample.dataStatus === '检测更改中' && !['voided', 'void_pending'].includes(sample.status)
}
export function canChangeData(actor: Actor, sample: Pick<RegistrationSample, 'status' | 'dataStatus'>) {
  return isDataChangeSample(sample) && actor.roles.some(role => role === 'admin' || role === 'testing')
}
