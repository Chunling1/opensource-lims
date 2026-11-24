import { isProductionDateValid, sampleDateOrderErrors } from './sampleDateRules'

export interface ProductionDateRow { name: string; precision: 'day' | 'month' | 'custom'; value: string; note: string }
export type ProductionDateLimits = { sampleTime?: string; sendDate?: string; entrustDate?: string }
export function singleProductionDate(value = ''): ProductionDateRow {
  return { name: '', precision: /^\d{4}-\d{2}-\d{2}$/.test(value) ? 'day' : /^\d{4}-\d{2}$/.test(value) ? 'month' : 'custom', value, note: '' }
}
export function productionDatesText(rows: ProductionDateRow[], language = 'CN', formatted = false): string {
  return rows.map(row => {
    let name = row.name.trim(), value = row.value.trim()
    const precision = row.precision || singleProductionDate(value).precision
    if (language === 'EN') name = name.replace(/^(室内机|室外机|整机)(\d*)$/, (_, n, i) => ({室内机:'Indoor unit',室外机:'Outdoor unit',整机:'Unit'}[n as '室内机'] + (i ? ` ${i}` : '')))
    if (formatted && precision !== 'custom' && value && isProductionDateValid(value)) {
      const [y, m, d] = value.split('-')
      value = language === 'EN' ? `${d ? Number(d) + ' ' : ''}${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(m)-1]} ${y}` : `${y}年${Number(m)}月${d ? Number(d)+'日' : ''}`
    }
    return `${name ? name + (language === 'EN' ? ': ' : '：') : ''}${value}${row.note.trim() ? (language === 'EN' ? ` (${row.note.trim()})` : `（${row.note.trim()}）`) : ''}`
  }).join('\n')
}
export function productionDatesIssues(rows: ProductionDateRow[], limits: ProductionDateLimits) {
  const errors: string[] = [], warnings: string[] = []
  rows.forEach((row, index) => {
    const label = row.name.trim() || `第${index+1}项`
    const value = row.value.trim()
    const precision = row.precision || singleProductionDate(value).precision
    const valid = ['day', 'month', 'custom'].includes(precision) && (!value || (precision === 'custom' ? !/\d{4}[-/.年]\d/.test(value) :
      (precision === 'day' ? /^\d{4}-\d{2}-\d{2}$/ : /^\d{4}-\d{2}$/).test(value) && isProductionDateValid(value)))
    if (!valid) { errors.push(`${label}：生产日期格式无效；日期请用精确到日或月填写`); return }
    if (!value || precision === 'custom') { warnings.push(`${label}：未提供可核查日期，无法校验先后关系`); return }
    errors.push(...sampleDateOrderErrors({produceDate:value, ...limits}).filter(x => x.includes('生产日期')).map(x => `${label}：${x}`))
    if (precision === 'month') for (const [key, title] of [['sampleTime','抽样'],['sendDate','送样'],['entrustDate','委托']] as const) {
      if (limits[key]?.slice(0,7) === value) warnings.push(`${label}：生产月份与${title}日期同月，无法确定具体先后，请核对`)
    }
  })
  return { errors, warnings }
}
