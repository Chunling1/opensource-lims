import type { RegistrationSample } from '../src/types/commissions/registration'
import { pickupStates, type PickupQuery, type PickupRow } from '../src/types/testing/pickup'
import { assignmentRows, parseAssignmentQuery } from './testingAssignment'
import { AppError } from '../src/services/common/errors'
import { demoActors } from '../src/services/storage/demoActors'
import { stockDate, stockField } from './stockReceipt'

export function pickupAllowed(sample: Pick<RegistrationSample, 'dataStatus' | 'status'>) {
  return sample.dataStatus === '样品待领取' && !['voided', 'void_pending'].includes(sample.status)
}
export function parsePickupReceipt(input: unknown) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new AppError('VALIDATION', '请填写领样信息。')
  const data = input as Record<string, unknown>
  const account = stockField(data, 'account', '领样员工号'), name = stockField(data, 'name', '领样员姓名')
  const person = demoActors.find(user => user.id === account)
  if (!person || person.name !== name) throw new AppError('VALIDATION', '领样员工号与姓名不匹配，请核对后重新提交。', { fieldErrors: { account: '请核对领样员工号。', name: '工号与姓名不匹配，请核对后重新提交。' } })
  return { account: person.id, name: person.name, date: stockDate(data, '领样时间') }
}

export const parsePickupQuery = (input: Record<string, unknown>): PickupQuery => parseAssignmentQuery(input, pickupStates)
export function pickupRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: PickupQuery): PickupRow[] {
  const sources = new Map(samples.map(sample => [sample.id, sample]))
  return assignmentRows(samples, query, pickupStates).map(({ canAssign, canUndoAssign, canPrintTask, ...row }) => {
    const sample = sources.get(row.id)!
    return { ...row, inspector: sample.details?.inspector || '', canPickup: false }
  })
}
