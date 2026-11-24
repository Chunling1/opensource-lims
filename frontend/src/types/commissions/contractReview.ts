export const reviewRequirements = [
  { key: 'technicalCapability', label: '技术能力' }, { key: 'equipment', label: '仪器设备' },
  { key: 'environment', label: '环境设施条件' }, { key: 'methods', label: '方法' },
  { key: 'personnel', label: '人员' }, { key: 'sample', label: '样品' },
] as const
export const reviewAuthorizations = [
  { key: 'basisAuthorization', label: '检验依据授权' }, { key: 'cma', label: '加盖CMA章' },
  { key: 'cnas', label: '加盖CNAS章' }, { key: 'other', label: '其他' },
] as const
export type ReviewDecision = 'approved' | 'rejected'
export type ContractReview = Record<(typeof reviewRequirements)[number]['key'] | (typeof reviewAuthorizations)[number]['key'], boolean> & { otherText: string; notes: string; decision?: ReviewDecision; compliance?: ReviewConfirmation }
export function emptyContractReview(): ContractReview {
  return { technicalCapability: true, equipment: true, environment: true, methods: true, personnel: true, sample: true, basisAuthorization: false, cma: false, cnas: false, other: false, otherText: '', notes: '' }
}

export type ReviewCheckOptions = Pick<ContractReview, (typeof reviewRequirements)[number]['key'] | (typeof reviewAuthorizations)[number]['key'] | 'otherText'>
// A stable snapshot of editable review fields, excluding historical notes and proof.
export function reviewCheckOptions(review: ReviewCheckOptions): ReviewCheckOptions {
  return {
    technicalCapability: review.technicalCapability, equipment: review.equipment,
    environment: review.environment, methods: review.methods, personnel: review.personnel, sample: review.sample,
    basisAuthorization: review.basisAuthorization, cma: review.cma, cnas: review.cnas, other: review.other,
    otherText: review.other ? review.otherText : '',
  }
}

export interface ReviewCheckResult {
  id: string
  sampleId: string
  sampleVersion: number
  checkedAt: string
  reviewOptions?: ReviewCheckOptions // Absent only on historical results.
  messages: { tone: 'info' | 'warning'; text: string }[]
}
export interface ReviewConfirmation {
  result: ReviewCheckResult
  readConfirmed?: boolean
  confirmedBy?: { id: string; name: string }
  confirmedAt?: string
}
export type ContractReviewSubmission = ContractReview & { checkId?: string; readConfirmed?: boolean }
export interface BatchReviewTarget { id: string; version: number }
export interface BatchReviewCheckResult extends ReviewCheckResult { sampleCode: string; sampleName: string }
export interface BatchReviewCheckResponse { items: BatchReviewCheckResult[] }
export interface BatchReviewSubmission {
  targets: BatchReviewTarget[]
  review: ContractReviewSubmission
  checks: { sampleId: string; checkId: string }[]
}
