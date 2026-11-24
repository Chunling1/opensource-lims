import { isWorkflowDateBefore, normalizeWorkflowDate } from './workflowDate'
import { productionDatesIssues, type ProductionDateRow } from './productionDates'

export function isProductionDateMarker(value: unknown): boolean {
  const text = String(value || '').trim()
  return Boolean(text) && !/^\d{4}(?:[-/.年]|$)/.test(text)
}

export function isProductionDateValid(value: unknown): boolean {
  return !String(value || '').trim() || isProductionDateMarker(value) || Boolean(productionDateBoundary(value))
}

export function productionDateBoundary(value: unknown): string {
  const text = String(value || '').trim()
  return normalizeWorkflowDate(/^\d{4}-\d{2}$/.test(text) ? text + '-01' : text)
}

export function dateBoundary(values: unknown[], edge: 'min' | 'max'): string {
  const dates = values.map(productionDateBoundary).filter(Boolean).sort()
  return (edge === 'min' ? dates[0] : dates[dates.length - 1]) || ''
}

export function savedSampleDates(detail: { rawSample?: Record<string, unknown>; summary?: { fields: [string, string][] }[] } | null) {
  function read(key: string, ...labels: string[]) {
    const raw = detail?.rawSample?.[key]
    if (detail?.rawSample && Object.prototype.hasOwnProperty.call(detail.rawSample, key)) return String(raw ?? '')
    const candidates = [raw, ...(detail?.summary || []).flatMap(section => section.fields.filter(([label]) => labels.includes(label)).map(([, value]) => value))]
    return String(candidates.find(value => value != null && !['', '—', '待填写', '待录入'].includes(String(value).trim())) || '')
  }
  return { produceDate: read('produceDate', '生产日期'), productionDates: (detail?.rawSample?.productionDates || []) as ProductionDateRow[], sampleTime: read('sampleTime', '抽样时间', '抽样日期'), sendDate: read('sendDate', '送样日期') }
}

/** Inclusive dates; sampling and entrust intentionally have no ordering. */
export function sampleDateOrderErrors(dates: {
  produceDate?: string; productionDates?: ProductionDateRow[]; sampleTime?: string; sendDate?: string; entrustDate?: string
}): string[] {
  if (dates.productionDates?.length) {
    const limits = {sampleTime: dates.sampleTime, sendDate: dates.sendDate, entrustDate: dates.entrustDate}
    return [...productionDatesIssues(dates.productionDates, limits).errors, ...sampleDateOrderErrors(limits)]
  }
  const production = productionDateBoundary(dates.produceDate)
  const checks = [
    [dates.sampleTime, production, '抽样日期', '生产日期'],
    [dates.sendDate, production, '送样日期', '生产日期'],
    [dates.entrustDate, production, '委托日期', '生产日期'],
    [dates.sendDate, dates.sampleTime, '送样日期', '抽样日期'],
  ] as const
  return checks.filter(([value, previous]) => isWorkflowDateBefore(value, previous))
    .map(([, , current, previous]) => `${current}不得早于${previous}`)
}
