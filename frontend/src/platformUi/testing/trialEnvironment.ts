// One template input, four existing platform fields. Values remain separate on save.
const fields = [
  ['地点', 'calibrationPlace'], ['温度', 'temperature'],
  ['湿度', 'humidity'], ['压力', 'pressure'],
] as const
type EnvironmentKey = typeof fields[number][1]
type Environment = Record<EnvironmentKey, string>
const empty = (): Environment => ({calibrationPlace:'', temperature:'', humidity:'', pressure:''})
export const environmentFormatMessage = '请按“地点：…；温度：…；湿度：…；压力：…”填写，空值保留项目名称；四项数据未被覆盖。'

export function formatTrialEnvironment(source: Partial<Record<EnvironmentKey, unknown>>): string {
  const values = fields.map(([, key]) => String(source[key] ?? ''))
  if (values.every(value => !value)) return ''
  return fields.map(([label], i) => {
    const value = values[i]!
    // Quoting preserves semicolons, newlines, quotes and significant whitespace.
    return label + '：' + (/[;；\r\n"]/.test(value) || value.trim() !== value ? JSON.stringify(value) : value)
  }).join('；')
}

export function parseTrialEnvironment(text: string): Environment {
  if (!text.trim()) return empty()
  const parts: string[] = []
  let part = '', quoted = false, escaped = false
  for (const char of text) {
    if (escaped) { part += char; escaped = false; continue }
    if (quoted && char === '\\') { part += char; escaped = true; continue }
    if (char === '"') quoted = !quoted
    if (!quoted && (char === ';' || char === '；')) { parts.push(part); part = '' }
    else part += char
  }
  if (quoted || escaped) throw new Error(environmentFormatMessage)
  parts.push(part)
  const values = empty(), seen = new Set<string>()
  for (const segment of parts) {
    const match = segment.trim().match(/^(地点|温度|湿度|压力)\s*[:：]([\s\S]*)$/)
    if (!match || seen.has(match[1]!)) throw new Error(environmentFormatMessage)
    const key = fields.find(([label]) => label === match[1])![1]
    const raw = match[2]!.trim()
    let value: unknown = raw
    if (raw.startsWith('"')) {
      try { value = JSON.parse(raw) } catch { throw new Error(environmentFormatMessage) }
    }
    if (typeof value !== 'string') throw new Error(environmentFormatMessage)
    values[key] = value; seen.add(match[1]!)
  }
  if (seen.size !== fields.length) throw new Error(environmentFormatMessage)
  return values
}
