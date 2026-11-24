import { describe, expect, it } from 'vitest'
import { createDataEntryService } from '../../server/dataEntryDetail'
import { completeReportConfig, completeReportGeneration } from '../../server/dataEntryGeneration'
import { entryWord } from '../../server/dataEntryDocuments'
import { seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'

function setup(id = 'demo-yp-76') {
  let state = seedRegistration(), actor = demoActors[0]!, now = 1000
  const service = createDataEntryService({ actor: () => actor, read: () => state, write: next => { state = next } }, () => now)
  const detail = () => service.detail(id)
  const mutate = (action: string, values: Record<string, unknown> = {}) => service.mutate(id, action, { version: detail().version, sampleVersion: detail().sample.version, requestId: crypto.randomUUID(), ...values })
  return { id, service, detail, mutate, advance: () => { now += 1000 }, actor: (id: string) => { actor = demoActors.find(row => row.id === id)! } }
}
describe('complete report download', () => {
  it('gates on backend plan and report rules including the selected layout', () => {
    const t = setup()
    expect(t.detail().completeReportGeneration.layoutIds).toEqual(['standard'])
    t.mutate('save', { form: t.detail().form, layoutId: 'extended' })
    expect(() => t.mutate('template-tasks', { kind: 'complete-report' })).toThrow(/暂不支持/)
    expect(t.mutate('template-tasks', { wordOnly: true }).templateJob).toBeDefined()
    const other = setup('demo-yp-80')
    expect(other.detail().completeReportGeneration.layoutIds).toEqual([])
    expect(() => other.mutate('template-tasks', { kind: 'complete-report' })).toThrow(/暂不支持/)
    const rules = completeReportConfig.rules
    try {
      completeReportConfig.rules = [{ settings: { formatId: 'product', layoutId: 'standard' } }]
      expect(completeReportGeneration(other.detail().sample).layoutIds).toEqual(['standard'])
      completeReportConfig.rules = []
      expect(completeReportGeneration(t.detail().sample).layoutIds).toEqual([])
    } finally { completeReportConfig.rules = rules }
  })
  it('keeps downloads separate, reuses current tasks, and does not upload or confirm automatically', () => {
    const t = setup()
    t.mutate('save', { form: { ...t.detail().form, conclusion: '已保存的检测结论' } })
    const template = t.mutate('template-tasks', { wordOnly: true }).templateJob!
    const full = t.mutate('template-tasks', { kind: 'complete-report' }).completeReportJob!
    expect(full.id).not.toBe(template.id)
    expect(t.mutate('template-tasks', { kind: 'complete-report' }).completeReportJob!.id).toBe(full.id)
    expect(() => t.service.taskResult(t.id, full.id, 'word')).toThrow(/尚未生成/)
    t.advance()
    expect(t.detail().completeReportJob).toMatchObject({ kind: 'complete-report', wordAvailable: true, pdfAvailable: false })
    const result = entryWord(t.service.taskResult(t.id, full.id, 'word'), true)
    expect(result.subarray(0, 2).toString()).toBe('PK')
    expect(result.toString()).toContain('自动生成完整报告')
    expect(result.toString()).toContain('已保存的检测结论')
    expect(entryWord(t.service.taskResult(t.id, template.id, 'word')).toString()).toContain('演示模板')
    expect(t.detail().files).toEqual([])
    expect(t.detail().reportConfirmed).toBe(false)
    t.mutate('upload', { kind: 'report', file: { name: '完整报告.docx', size: result.length, dataUrl: `data:application/octet-stream;base64,${result.toString('base64')}` } })
    expect(t.detail().files[0]).toMatchObject({ kind: 'report', name: '完整报告.docx' })
    expect(t.detail().reportConfirmed).toBe(false)
    t.mutate('save', { form: { ...t.detail().form, conclusion: '更新结论' } })
    expect(t.detail().completeReportStale).toBe(true)
    expect(() => t.service.taskResult(t.id, full.id, 'word')).toThrow(/已更新/)
    expect(t.mutate('template-tasks', { kind: 'complete-report' }).completeReportJob!.id).not.toBe(full.id)
  })
  it('handles failure, permission and scope without bypassing existing guards', () => {
    const t = setup(), failed = t.mutate('template-tasks', { kind: 'complete-report', scenario: 'word-failure' }).completeReportJob!
    t.advance()
    expect(t.detail().completeReportJob?.stage).toBe('word-failed')
    expect(t.mutate('template-tasks', { kind: 'complete-report' }).completeReportJob!.id).not.toBe(failed.id)
    t.actor('approver')
    expect(() => t.mutate('template-tasks', { kind: 'complete-report' })).toThrow(/权限/)
    t.actor('other')
    expect(() => t.detail()).toThrow(/不可访问/)
  })
})
