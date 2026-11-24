import type { EquipItem } from '@/services/quality'

export interface EquipmentTestInterval {
  start: string
  end: string
}

// '限制使用' is derived from today's expiry and may also be a legacy cached value.
// Test eligibility must use the selected test dates below, not that status label.
const unavailableTokens = ['停用', '报废', '失效', '维修']
const longTermTokens = ['长期', '永久', '不定期']

export function isLongTermEquipment(item: Pick<EquipItem, 'period'>): boolean {
  const period = String(item.period || '').trim()
  return longTermTokens.some((token) => period.includes(token))
}

export function equipmentManualUnavailable(item: Pick<EquipItem, 'status' | 'manualStatus'>): boolean {
  const status = `${item.status || ''} ${item.manualStatus || ''}`
  return unavailableTokens.some((token) => status.includes(token))
}

export function equipmentCoversTestIntervals(
  item: EquipItem,
  intervals: EquipmentTestInterval[],
): boolean {
  // Eligibility is supplied by the report-scoped backend evaluator.
  return item.eligibility?.selectable === true
}

export function equipmentValidityText(item: EquipItem, intervals: EquipmentTestInterval[]): string {
  return item.eligibility?.message || '正在核对仪器有效期'
}
