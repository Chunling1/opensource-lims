import { AppError } from '../src/services/common/errors'
import type { RegistrationSample } from '../src/types/commissions/registration'
import { completionStates, completionDisposalEnabled, completionDateEnabled, type SampleCompletionQuery } from '../src/types/testing/sampleCompletion'
import { disposalStates } from '../src/types/samples/disposal'
import { parseStorageQuery } from './sampleInbound'
import { isDisposalSample } from './sampleDisposal'
import { flowRows } from './sampleFlow'
import { stockField } from './stockReceipt'

export function parseSampleCompletionResult(result: unknown) {
  return stockField({ result }, 'result', '处置结果（最多 500 字）', 500)
}

export function parseSampleCompletionQuery(input: Record<string, unknown>): SampleCompletionQuery {
  for (const [key, states] of [['processingStatus', completionStates], ['disposalStatus', disposalStates]] as const) {
    if (input[key] !== undefined && input[key] !== '' && !states.includes(input[key] as never)) throw new AppError('BAD_REQUEST', '不支持的样品处理或处置状态。')
  }
  const processingStatus = input.processingStatus as string | undefined
  const disposalStatus = completionDisposalEnabled(processingStatus) ? input.disposalStatus as string | undefined : undefined
  const dates = completionDateEnabled(processingStatus)
  const query = parseStorageQuery({ ...input, status: undefined, site: undefined, from: dates ? input.from : undefined, to: dates ? input.to : undefined }, [], '处理时间')
  return { ...query, processingStatus, disposalStatus }
}

export function sampleCompletionRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: SampleCompletionQuery, planIds: Set<string>, restricted: boolean, canManage: boolean) {
  const eligible = samples.filter(isDisposalSample), source = new Map(eligible.map(sample => [sample.id, sample]))
  // The testing handling status is independent from the later physical disposal status.
  return flowRows(eligible, { ...query, from: undefined, to: undefined }, planIds, restricted).map(row => {
    const info = source.get(row.id)!.sampleCompletionInfo, processingStatus = info?.status || '样品待处理'
    const processingTime = processingStatus === '样品已处理' ? info?.processedAt || '' : ''
    return { ...row, processingStatus, processingTime,
      disposalResult: info?.receipt?.result || row.disposalResult,
      canProcess: canManage && processingStatus === '样品待处理', canUndoProcess: canManage && processingStatus === '样品已处理' }
  }).filter(row => (!query.processingStatus || row.processingStatus === query.processingStatus)
    && (!query.disposalStatus || row.disposalStatus === query.disposalStatus)
    && (!query.from || !!row.processingTime && row.processingTime.slice(0, 10) >= query.from)
    && (!query.to || !!row.processingTime && row.processingTime.slice(0, 10) <= query.to))
}
