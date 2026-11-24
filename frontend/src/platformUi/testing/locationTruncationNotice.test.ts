import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { parseTemplateCapacityWarnings, templateCapacityMessage } from './templateCapacityWarnings'

describe('location truncation notice', () => {
  it('shows the exact nonblocking location message without asking to restore an appendix', () => {
    const codes = parseTemplateCapacityWarnings(encodeURIComponent('["LOCATION_TRUNCATED"]'))
    expect(templateCapacityMessage(codes)).toBe('检测地点超出模板容量，已截断，请核对')
    expect(templateCapacityMessage([...codes, 'SAMPLENAME'])).toContain('样品名称')
  })
  it('renders persistent yellow status notices in entry, review and version views', () => {
    for (const name of ['./EntryRecordPresentation.vue', '../reports/ReportReviewPresentation.vue', '../reports/ReportDetailPresentation.vue']) {
      const source = readFileSync(new URL(name, import.meta.url), 'utf8')
      expect(source).toMatch(/(?:class="alert alert-warning" role="status"|:message="notice" tone="warning")/)
    }
  })
})
