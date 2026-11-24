import { describe, expect, it } from 'vitest'
import { parseTemplateCapacityWarnings, templateCapacityMessage } from './templateCapacityWarnings'

describe('authoring download capacity notice', () => {
  it('decodes and deduplicates the download response fields', () => {
    expect(parseTemplateCapacityWarnings(encodeURIComponent(JSON.stringify(['SAMPLENAME', 'Client', 'SAMPLENAME'])))).toEqual(['SAMPLENAME', 'Client'])
    expect(parseTemplateCapacityWarnings(null)).toEqual([])
    expect(parseTemplateCapacityWarnings('%5B%5D')).toEqual([])
  })
  it.each(['%', '{}', '[12]', '["<script>"]'])('keeps a visible fallback for malformed metadata %s', header => {
    expect(parseTemplateCapacityWarnings(header)).toEqual(['待核对字段'])
  })
  it('clearly states successful download, possible truncation and the next action', () => {
    const message = templateCapacityMessage(['SAMPLENAME', 'TestDate'])
    expect(message).toContain('填写模板已下载')
    expect(message).toContain('样品名称（SAMPLENAME）')
    expect(message).toContain('核对 Word 和预览')
    expect(message).toContain('平台未截断原文')
  })
})
