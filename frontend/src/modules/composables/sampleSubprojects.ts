export const RECEIPT_TYPES = ['预收款', '结算款', '进度款', '保证金', '奖惩', '其他'] as const

export interface SampleSubproject {
  projectName: string
  dept: string
  businessCategory: string
  amount: string
  receivedAmount: string
  receiptType: string
  paymentDescription: string
  remark: string
  [key: string]: unknown
}

export function blankSubproject(): SampleSubproject {
  return { projectName: '', dept: '', businessCategory: '', amount: '', receivedAmount: '', receiptType: '', paymentDescription: '', remark: '' }
}

// Preserve legacy dept/amount keys and source extensions; money remains decimal text.
export function normalizeSubprojects(value: unknown): SampleSubproject[] {
  if (!Array.isArray(value)) return []
  return value.filter((row) => row && typeof row === 'object' && !Array.isArray(row)).map((row) => {
    const result = { ...row } as SampleSubproject
    for (const key of Object.keys(blankSubproject())) result[key] = row[key] == null ? '' : String(row[key])
    return result
  })
}

export function parseLegacySubprojects(text: string): SampleSubproject[] {
  if (!text || text === '—') return []
  return text.split('；').map((entry) => {
    const match = /^(.*)[:：]([^:：]*)$/u.exec(entry)
    const dept = match ? match[1]! : entry
    const amount = match ? match[2]! : ''
    return { ...blankSubproject(), dept: dept === '—' ? '' : dept, amount: amount === '—' ? '' : amount }
  })
}

export function subprojectErrors(rows: SampleSubproject[]): string[] {
  const errors: string[] = []
  rows.forEach((row, index) => {
    if (!String(row.paymentDescription ?? '').trim()) errors.push(`请填写子项目第${index + 1}行付款说明`)
    for (const [key, label] of [['amount', '子项金额'], ['receivedAmount', '收款金额']] as const) {
      const value = String(row[key] ?? '').trim()
      // Signed values allow historical adjustments and reward/penalty entries.
      if (!/^-?\d{1,12}(\.\d{1,2})?$/.test(value)) errors.push(`子项目第${index + 1}行${label}须为最多两位小数的金额`)
    }
  })
  return errors
}

export function samplePricingErrors(rows: SampleSubproject[], standardPrice: string, complete = true, contractType = ''): string[] {
  const errors = subprojectErrors(rows)
  const price = String(standardPrice ?? '').trim()
  if ((complete || price) && !/^\d{1,12}(\.\d{1,2})?$/.test(price)) {
    errors.push('标准价格须填写有效金额（最多12位整数、2位小数，不能为负数）')
  }
  if (!complete || (!rows.length && contractType === '不回传外部ERP合同')) return errors
  if (!rows.length) errors.push('完成登记前请填写至少一个子项目')
  if (rows.length > 100) errors.push('样品子项目不能超过100项')
  rows.forEach((row, index) => {
    for (const [key, label] of [['projectName', '子项目名称'], ['dept', '核算部门'], ['businessCategory', '业务三级分类']] as const) {
      if (['', '—', '-'].includes(String(row[key] ?? '').trim())) errors.push(`请填写子项目第${index + 1}行${label}`)
    }
    if (!/^-?\d{1,12}(\.\d{1,2})?$/.test(String(row.amount ?? '').trim())) {
      errors.push(`子项目第${index + 1}行子项金额须填写有效金额（最多12位整数、2位小数）`)
    }
  })
  if (errors.length) return errors
  // Integer cents avoid rounding 0.1 + 0.2 and remain exact for 100 rows.
  const cents = (value: string) => {
    const text = value.trim()
    const [whole = '0', fraction = ''] = text.replace(/^-/, '').split('.')
    return (BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))) * (text.startsWith('-') ? -1n : 1n)
  }
  const format = (value: bigint) => `${value < 0n ? '-' : ''}${(value < 0n ? -value : value) / 100n}.${String((value < 0n ? -value : value) % 100n).padStart(2, '0')}`
  const total = rows.reduce((sum, row) => sum + cents(row.amount), 0n)
  if (total !== cents(price)) errors.push(`子项目金额合计 ${format(total)} 元必须等于标准价格 ${format(cents(price))} 元（差额 ${format(cents(price) - total)} 元）`)
  return errors
}

export function subprojectSummary(rows: SampleSubproject[]): [string, string][] {
  rows = normalizeSubprojects(rows)
  const fields: [string, string][] = [['结算明细', rows.length ? rows.map(row => `${row.dept || '—'}:${row.amount || '—'}`).join('；') : '—']]
  const labels: [keyof SampleSubproject, string][] = [['projectName', '子项目名称'], ['dept', '核算部门'], ['businessCategory', '业务三级分类'], ['amount', '子项金额'], ['receivedAmount', '收款金额'], ['receiptType', '收款类型'], ['paymentDescription', '付款说明'], ['remark', '备注']]
  rows.forEach((row, index) => labels.forEach(([key, label]) => fields.push([`子项目${index + 1}·${label}`, String(row[key] || '—')])))
  return fields
}
