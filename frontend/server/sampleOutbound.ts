import { outboundStatus } from '../src/types/commissions/workflow'
import { AppError, problem } from '../src/services/common/errors'
import { outboundReturnTypes, type OutboundAction, type OutboundReturn } from '../src/types/samples/outbound'
import type { RegistrationSample } from '../src/types/commissions/registration'
import { stockDate, stockField } from './stockReceipt'

export function allowedOutboundActions(sample: Pick<RegistrationSample, 'status' | 'dataStatus'>): OutboundAction[] {
  if (sample.status === 'void_pending' || sample.status === 'voided') return []
  if (outboundStatus(sample.dataStatus) === '样品出库中') return ['dispatch', 'return']
  if (sample.dataStatus === '样品待领取') return ['undo', 'return']
  return []
}
export function parseOutboundReturn(input: unknown): OutboundReturn {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new AppError('VALIDATION', '请填写退回信息。')
  const data = input as Record<string, unknown>
  if (!outboundReturnTypes.some(type => type.value === data.type)) throw problem('VALIDATION', '请选择退回类型。', 'type')
  return { type: data.type as OutboundReturn['type'], reason: stockField(data, 'reason', '退回原因（最多 500 字）', 500), details: stockField(data, 'details', '补充说明（最多 2000 字）', 2000, false), date: stockDate(data, '退回时间') }
}
