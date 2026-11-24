import type { RegistrationSample } from '../src/types/commissions/registration'
import type { ReportSettings } from '../src/types/commissions/reportSettings'
import { getSampleReportConfig } from './sampleReportSettings'

// Mock backend capability configuration; production supplies the rules for its actual generators.
// A rule can apply to plans, report settings, or both. Unconfigured combinations stay disabled.
export const completeReportConfig: { version: string; rules: { planIds?: string[]; settings?: Partial<ReportSettings> }[] } = {
  version: '1',
  rules: [{ planIds: ['general-1'], settings: { formatId: 'product', titleId: 'default_lab', languageId: 'zh', layoutId: 'standard' } }],
}

export function completeReportGeneration(sample: RegistrationSample) {
  const config = getSampleReportConfig(), settings = sample.details?.reportSettings
  const layoutIds = config.options.layoutId.filter(layout => {
    const choice = { ...settings, layoutId: layout.id }
    return config.combinations.some(combination => Object.entries(combination).every(([key, value]) => choice[key as keyof ReportSettings] === value))
      && completeReportConfig.rules.some(rule => (rule.planIds?.length || Object.keys(rule.settings || {}).length)
        && (!rule.planIds || rule.planIds.includes(sample.details?.testPlanId || ''))
        && Object.entries(rule.settings || {}).every(([key, value]) => choice[key as keyof ReportSettings] === value))
  }).map(layout => layout.id)
  return { layoutIds, unavailableReason: '当前检测方案或报告版式暂不支持自动生成完整报告，可下载模板填写后上传。' }
}
