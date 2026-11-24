export const reportSettingFields = [
  { key: 'formatId', label: '报告格式' },
  { key: 'titleId', label: '报告标题' },
  { key: 'languageId', label: '报告语言' },
  { key: 'layoutId', label: '首页版式' },
] as const
export type ReportSettingKey = typeof reportSettingFields[number]['key']
export type ReportSettings = Record<ReportSettingKey, string>
export interface ReportOption { id: string; label: string }
export interface ReportSettingsConfig {
  version: string
  options: Record<ReportSettingKey, ReportOption[]>
  defaults: ReportSettings
  combinations: ReportSettings[]
}
export function emptyReportSettings(): ReportSettings { return { formatId: '', titleId: '', languageId: '', layoutId: '' } }
