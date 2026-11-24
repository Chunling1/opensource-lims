export type TitleStyle = 'CN' | 'EN' | 'none'
export interface StandardDisplayRecord { id?: number; key: string; code: string; name: string }
export interface StandardDisplaySettings {
  standardShowName?: boolean
  standardTitleStyles?: Record<string,TitleStyle>
  standardSeparatorText?: string
}
const judgmentCode = /^[A-Z]{1,8}(?:\/[A-Z]{1,8})?(?:[ \t]+(?:EN|ISO|IEC))*\s*\d+(?:[.\-]\d+)*\s*[-－—:]\s*\d{4}(?!\d)/

export function judgmentEntries(value: string) {
  return value.split(/[；;、\n]+/).map(part => part.trim()).filter(Boolean)
}
export function judgmentEntry(value: string) {
  const titled = value.match(/^([A-Za-z][^《<>]*\d[^《<>]*?)\s+《(.+)》$/)
  if (titled) return {code: titled[1].trim(), name: titled[2]}
  const code = value.match(judgmentCode)?.[0]
  return {code: code?.trim() ?? value, name: code ? value.slice(code.length).trim() : ''}
}

export function judgmentRows(value: string) {
  const codes: string[] = [], names: Record<string,string> = {}
  for (const part of judgmentEntries(value)) {
    const code = part.match(judgmentCode)?.[0] ?? part
    const name = part.slice(code.length).trim()
    if (!codes.includes(code)) codes.push(code)
    if (name) names[code] = name
  }
  return { codes, names }
}
export function standardTitle(name: string, style: TitleStyle) {
  name = name.trim()
  while ((name.startsWith('《') && name.endsWith('》')) || (name.startsWith('<') && name.endsWith('>'))) name = name.slice(1, -1).trim()
  return !name || style === 'none' ? name : style === 'EN' ? `<${name}>` : `《${name}》`
}
export function standardPreview(codes: string[], names: Record<string,string>, show: boolean, styles: Record<string,TitleStyle>, language: TitleStyle, separator: string) {
  return codes.map(code => {
    const name = standardTitle((names[code] || '').replace(/\s+/g, ' '), styles[code] || language)
    return show && name ? `${code} ${name}` : code
  }).join(separator)
}
export function standardRecordPreview(rows: StandardDisplayRecord[], show: boolean, styles: Record<string,TitleStyle>, language: TitleStyle, separator: string) {
  return rows.map(row => standardPreview([row.code], {[row.code]: row.name}, show, {[row.code]: styles[row.key] || styles[row.code] || language}, language, '')).join(separator)
}
export function equipmentPreview(ids: number[], equipment: any[], flags: Record<string,boolean>, separator: string) {
  const keys = [...(flags.archiveNo ? ['archiveNo'] : []), 'name', ...['spec','maker','factoryNo'].filter(key => flags[key])]
  return ids.map(id => equipment.find(row => Number(row.id) === Number(id))).filter(Boolean).map(row => keys.map(key => String(row[key] || '').trim().replace(/\s+/g, ' ')).filter(Boolean).join(' ')).join(separator)
}
