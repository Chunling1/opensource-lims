import { reportSettingFields, type ReportSettings, type ReportSettingsConfig, type ReportSettingKey } from '../../types/commissions/reportSettings'

export function matchesReportSettings(config: ReportSettingsConfig, value: ReportSettings) {
  return config.combinations.some(row => reportSettingFields.every(({ key }) => !value[key] || row[key] === value[key]))
}
export function allowedReportOptions(config: ReportSettingsConfig, value: ReportSettings, key: ReportSettingKey): string[] {
  const upstream = reportSettingFields.slice(0, reportSettingFields.findIndex(field => field.key === key))
  return [...new Set(config.combinations.filter(row => upstream.every(field => !value[field.key] || row[field.key] === value[field.key])).map(row => row[key]))]
}
export function reportSettingsIssues(config: ReportSettingsConfig, value: ReportSettings): Partial<Record<ReportSettingKey, string>> {
  const errors: Partial<Record<ReportSettingKey, string>> = {}
  for (const { key, label } of reportSettingFields) {
    if (value[key] && !allowedReportOptions(config, value, key).includes(value[key])) errors[key] = `${label}已不可用或与当前选择不匹配，请重新选择。`
  }
  return errors
}
export function changeReportSetting(config: ReportSettingsConfig, value: ReportSettings, key: ReportSettingKey, selection: string) {
  const next = { ...value, [key]: selection }
  const changes: string[] = []
  for (const field of reportSettingFields.slice(reportSettingFields.findIndex(field => field.key === key) + 1)) {
    const allowed = allowedReportOptions(config, next, field.key), current = next[field.key]
    if (allowed.length === 1) next[field.key] = allowed[0]!
    else if (current && !allowed.includes(current)) next[field.key] = ''
    if (current !== next[field.key]) changes.push(`${field.label}：${config.options[field.key].find(option => option.id === next[field.key])?.label || '请重新选择'}`)
  }
  return { value: next, changes }
}

// Configuration is data, never executable rules. Reject unusable payloads instead of falling back to hardcoded choices.
export function isReportSettingsConfig(value: unknown): value is ReportSettingsConfig {
  if (!value || typeof value !== 'object') return false
  const config = value as ReportSettingsConfig
  if (typeof config.version !== 'string' || !config.version || !config.options || !config.defaults || !Array.isArray(config.combinations) || !config.combinations.length) return false
  if (!reportSettingFields.every(({ key }) => Array.isArray(config.options[key]) && config.options[key].length && config.options[key].every(option => option && typeof option.id === 'string' && option.id && typeof option.label === 'string' && option.label) && new Set(config.options[key].map(option => option.id)).size === config.options[key].length && typeof config.defaults[key] === 'string')) return false
  if (!config.combinations.every(row => row && reportSettingFields.every(({ key }) => config.options[key].some(option => option.id === row[key])))) return false
  return matchesReportSettings(config, config.defaults)
}
