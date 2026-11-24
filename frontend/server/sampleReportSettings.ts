import { AppError } from '../src/services/common/errors'
import { matchesReportSettings, reportSettingsIssues } from '../src/services/commissions/reportSettings'
import { emptyReportSettings, reportSettingFields, type ReportSettings, type ReportSettingsConfig } from '../src/types/commissions/reportSettings'

// Mock backend configuration. Production can load the same data contract from its configuration store.
export const sampleReportConfig: ReportSettingsConfig = {
  version: '2',
  options: {
    formatId: [{ id: 'product', label: '产品' }, { id: 'sampling', label: '抽样' }, { id: 'engineering', label: '工程' }, { id: 'inspection', label: '检验' }, { id: 'calibration', label: '校准' }],
    titleId: [{ id: 'default_lab', label: '示例检测' }, { id: 'air-conditioning', label: '空调中心' }],
    languageId: [{ id: 'zh', label: '中文' }, { id: 'en', label: '英文' }],
    layoutId: [{ id: 'standard', label: '标准版' }, { id: 'extended', label: '扩展版' }],
  },
  defaults: { formatId: '', titleId: '', languageId: 'zh', layoutId: 'standard' },
  combinations: [],
}
for (const format of sampleReportConfig.options.formatId) for (const title of sampleReportConfig.options.titleId) for (const language of sampleReportConfig.options.languageId) for (const layout of sampleReportConfig.options.layoutId) {
  if (['inspection', 'calibration'].includes(format.id) && title.id !== 'default_lab' || format.id === 'calibration' && language.id !== 'zh' || layout.id === 'extended' && !['product', 'sampling'].includes(format.id)) continue
  sampleReportConfig.combinations.push({ formatId: format.id, titleId: title.id, languageId: language.id, layoutId: layout.id })
}
export function getSampleReportConfig() { return structuredClone(sampleReportConfig) }
export function parseReportSettings(input: unknown): ReportSettings {
  const result = emptyReportSettings()
  if (input === undefined) return result
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new AppError('VALIDATION', '报告设置格式有误。', { fieldErrors: { reportSettings: '请检查报告设置。' } })
  for (const { key } of reportSettingFields) {
    const value = (input as Record<string, unknown>)[key]
    if (value === undefined) continue
    if (typeof value !== 'string' || value.length > 100) throw new AppError('VALIDATION', '报告设置选项格式有误。', { fieldErrors: { reportSettings: '请检查报告设置。' } })
    result[key] = value
  }
  return result
}
export function validateReportSettings(value: ReportSettings, version?: string) {
  const config = getSampleReportConfig()
  
  if (!matchesReportSettings(config, value)) throw new AppError('VALIDATION', '报告设置已不可用或组合不匹配，请重新选择。', { fieldErrors: { reportSettings: '请检查报告设置。', ...Object.fromEntries(Object.entries(reportSettingsIssues(config, value)).map(([key, message]) => [`reportSettings.${key}`, message])) } })
}
