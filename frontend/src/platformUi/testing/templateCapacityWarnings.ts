/** Only field identifiers cross the download header; never include business values. */
export function parseTemplateCapacityWarnings(header: string | null): string[] {
  if (!header) return []
  try {
    const fields: unknown = JSON.parse(decodeURIComponent(header))
    if (Array.isArray(fields) && fields.every(x => typeof x === 'string' && /^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(x))) {
      return [...new Set(fields)]
    }
  } catch { /* A bad optional warning header must not discard a valid Word download. */ }
  return ['待核对字段']
}

const labels: Record<string, string> = {
  SAMPLENAME: '样品名称', SampleName: '样品名称', CLIENT: '委托单位', Client: '委托单位',
  MANUFACTURER: '生产单位', Manufacturer: '生产单位', TestDate: '检测日期',
  Conclusion: '结论', ManufacturingDate: '生产日期', Basis: '检测依据', BASIS: '检测依据', Place: '检测地点', PLACE: '检测地点',
}
export function templateCapacityMessage(fields: string[]): string {
  if (fields.includes('LOCATION_TRUNCATED')) {
    const other = fields.filter(field => field !== 'LOCATION_TRUNCATED')
    return '检测地点超出模板容量，已截断，请核对' + (other.length ? '；' + templateCapacityMessage(other) : '')
  }
  const names = [...new Set(fields.map(x => labels[x] ? `${labels[x]}（${x}）` : x))].join('、')
  return `填写模板已下载。${names}经 Doc 模块处理后与输入原文不一致，可能被截短或调整格式，请核对 Word 和预览。平台未截断原文；此提示不阻断生成。`
}
