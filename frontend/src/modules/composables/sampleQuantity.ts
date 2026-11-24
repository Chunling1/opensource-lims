/** Legacy records keep unit separately; edited records store the complete text. */
export function sampleQuantityText(amount: unknown, unit: unknown = ''): string {
  const value = amount == null ? '' : String(amount).trim()
  const suffix = unit == null ? '' : String(unit).trim()
  if (!value || value === '—' || value === '-') return ''
  if (!suffix || suffix === '—' || suffix === '-' || value.endsWith(suffix)) return value
  return `${value} ${suffix}`
}
export function setSampleQuantity(sample: { sampleAmount: string; unit: string }, value: string) {
  sample.sampleAmount = value
  sample.unit = ''
}
