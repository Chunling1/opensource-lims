import { describe, expect, it } from 'vitest'
import { getSampleReportConfig } from '../../server/sampleReportSettings'
import { allowedReportOptions, changeReportSetting, matchesReportSettings, isReportSettingsConfig } from '../../src/services/commissions/reportSettings'

describe('report settings combinations', () => {
  it('covers every option combination using the configured constraints', () => {
    const config = getSampleReportConfig()
    for (const format of config.options.formatId) for (const title of config.options.titleId) for (const language of config.options.languageId) for (const layout of config.options.layoutId) {
      const valid = !(['inspection', 'calibration'].includes(format.id) && title.id !== 'default_lab' || format.id === 'calibration' && language.id !== 'zh' || layout.id === 'extended' && !['product', 'sampling'].includes(format.id))
      expect(matchesReportSettings(config, { formatId: format.id, titleId: title.id, languageId: language.id, layoutId: layout.id })).toBe(valid)
    }
  })
  it('preserves valid selections, selects unique options and clears invalid choices when several remain', () => {
    const config = getSampleReportConfig()
    const original = { formatId: 'product', titleId: 'solar', languageId: 'en', layoutId: 'extended' }
    expect(changeReportSetting(config, original, 'formatId', 'inspection').value).toEqual({ formatId: 'inspection', titleId: 'default_lab', languageId: 'en', layoutId: 'standard' })
    expect(changeReportSetting(config, original, 'formatId', 'calibration').value).toEqual({ formatId: 'calibration', titleId: 'default_lab', languageId: 'zh', layoutId: 'standard' })
    config.combinations = config.combinations.filter(row => row.formatId !== 'engineering' || ['default_lab', 'air-conditioning'].includes(row.titleId))
    const changed = changeReportSetting(config, original, 'formatId', 'engineering')
    expect(changed.value.titleId).toBe('')
    expect(changed.value.languageId).toBe('en')
    expect(changed.changes).toContain('报告标题：请重新选择')
    expect(original.layoutId).toBe('extended')
  })
  it('supports new backend combinations without frontend condition changes and rejects unusable configs', () => {
    const config = getSampleReportConfig(), settings = { formatId: 'calibration', titleId: 'default_lab', languageId: 'zh', layoutId: 'standard' }
    expect(allowedReportOptions(config, settings, 'languageId')).toEqual(['zh'])
    config.combinations.push({ ...settings, languageId: 'en' })
    expect(allowedReportOptions(config, settings, 'languageId')).toEqual(['zh', 'en'])
    expect(isReportSettingsConfig(config)).toBe(true)
    expect(isReportSettingsConfig({ ...config, combinations: [] })).toBe(false)
    expect(isReportSettingsConfig({ ...config, defaults: { ...settings, titleId: 'missing' } })).toBe(false)
  })
})
