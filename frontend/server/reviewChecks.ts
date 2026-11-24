import { randomUUID } from 'node:crypto'
import { AppError } from '../src/services/common/errors'
import { reviewCheckOptions, type ReviewCheckOptions, type ReviewCheckResult } from '../src/types/commissions/contractReview'
import type { RegistrationSample } from '../src/types/commissions/registration'

export function reviewCheckMessages(sample: Pick<RegistrationSample, 'code'>): ReviewCheckResult['messages'] {
  return [
    { tone: 'info', text: `样品 ${sample.code} 的信息已完成模拟校核。` },
    { tone: 'warning', text: '模拟提醒：请核对所选检测依据与检测项目的适用性；本提示不代表正式合规结论，也不阻止通过评审。' },
    { tone: 'info', text: '当前为示例校核结果，正式校核项目及判断规则将在后续接入。' },
  ]
}

// One store per HTTP session. Starting another check invalidates the preceding result,
// including requests still running; checks never mutate the sample or its version.
export function createReviewChecks(delay = 1500) {
  const latest = new Map<string, { id: string; result?: ReviewCheckResult }>()
  const key = (actorId: string, sampleId: string, scope: string) => JSON.stringify([actorId, sampleId, scope])
  return {
    async run(actorId: string, sample: RegistrationSample, validateLatest: () => void, options: ReviewCheckOptions, scope = 'contract') {
      const snapshot = reviewCheckOptions(options)
      const entry = { id: randomUUID(), result: undefined as ReviewCheckResult | undefined }
      const owner = key(actorId, sample.id, scope)
      latest.set(owner, entry)
      await new Promise(resolve => setTimeout(resolve, delay))
      validateLatest()
      if (latest.get(owner) !== entry) throw new AppError('VALIDATION', '已有新的校核请求，请使用最新校核结果。')
      entry.result = {
        id: entry.id, sampleId: sample.id, sampleVersion: sample.version, checkedAt: new Date().toISOString(),
        reviewOptions: snapshot,
        messages: reviewCheckMessages(sample),
      }
      return structuredClone(entry.result)
    },
    matching(actorId: string, sample: RegistrationSample, id: unknown, options: ReviewCheckOptions, scope = 'contract') {
      const result = latest.get(key(actorId, sample.id, scope))?.result
      return typeof id === 'string' && result?.id === id && JSON.stringify(result.reviewOptions) === JSON.stringify(reviewCheckOptions(options)) ? structuredClone(result) : undefined
    },
    verify(actorId: string, sample: RegistrationSample, id: unknown, readConfirmed: unknown, options: ReviewCheckOptions, scope = 'contract') {
      const result = latest.get(key(actorId, sample.id, scope))?.result
      if (readConfirmed !== true || typeof id !== 'string' || !result || result.id !== id) {
        throw new AppError('VALIDATION', '请重新进行合规校核，并确认已阅读当前校核结果。')
      }
      
      if (JSON.stringify(result.reviewOptions) !== JSON.stringify(reviewCheckOptions(options))) throw new AppError('VALIDATION', '评审选项已变化，请重新校验并确认校验结果。')
      return structuredClone(result)
    },
  }
}
