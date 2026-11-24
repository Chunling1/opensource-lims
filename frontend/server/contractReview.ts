import { AppError } from '../src/services/common/errors'
import { emptyContractReview, reviewRequirements, reviewAuthorizations, reviewCheckOptions, type ReviewCheckOptions, type ContractReview } from '../src/types/commissions/contractReview'
export function parseReviewCheckOptions(value: unknown): ReviewCheckOptions {
  const fail = (): never => { throw new AppError('VALIDATION', '请提交有效的合同评审内容。') }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return fail()
  const input = value as Record<string, unknown>, result = emptyContractReview()
  for (const { key } of [...reviewRequirements, ...reviewAuthorizations]) {
    if (typeof input[key] !== 'boolean') return fail()
    result[key] = input[key]
  }
  if (typeof input.otherText !== 'string' || input.otherText.length > 500) return fail()
  result.otherText = input.otherText
  return reviewCheckOptions(result)
}
export function parseContractReview(value: unknown): ContractReview {
  const result: ContractReview = { ...emptyContractReview(), ...parseReviewCheckOptions(value) }
  const input = value as Record<string, unknown>
  const fail = (): never => { throw new AppError('VALIDATION', '请提交有效的合同评审内容。') }
  if (input.notes !== undefined) {
    if (typeof input.notes !== 'string' || input.notes.length > 2000) return fail()
    result.notes = input.notes
  }
  if (input.decision !== 'approved' && input.decision !== 'rejected') return fail()
  if (input.decision === 'approved' && !reviewRequirements.every(({ key }) => result[key])) {
    throw new AppError('VALIDATION', '是否满足要求的所有选项均须勾选，才能通过评审。')
  }
  result.decision = input.decision
  if (!result.other) result.otherText = ''
  return result
}
