import { describe, expect, it } from 'vitest'
import { createDataEntryService } from '../../server/dataEntryDetail'
import { entryWord, entryPdf } from '../../server/dataEntryDocuments'
import { seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'
import { parseDataEntryQuery, dataEntryRows } from '../../server/testingDataEntry'
import { trialEquipmentText } from '../../src/types/testing/dataEntryDetail'
import { createOriginalRecordService } from '../../server/originalRecords'

function setup() {
  let state = seedRegistration(), actor = demoActors[0]!, now = 10000
  const id = 'demo-yp-76', service = createDataEntryService({ actor: () => actor, read: () => state, write: next => { state = next } }, () => now)
  const mutate = (action: string, values: Record<string, unknown> = {}) => {
    const detail = service.detail(id)
    return service.mutate(id, action, { version: detail.version, sampleVersion: detail.sample.version, requestId: crypto.randomUUID(), ...values })
  }
  const save = () => mutate('save', { form: { ...service.detail(id).form, conclusion: '试验结果符合要求。', conclusionStatus: '合格', tester1Id: 'analyst', testDates: [{ kind: 'range', from: '2026-09-01', to: '2026-09-02' }] } })
  const word = () => { const bytes = entryWord(service.detail(id)); return mutate('upload', { kind: 'report', file: { name: '完整报告.docx', size: bytes.length, dataUrl: `data:application/octet-stream;base64,${bytes.toString('base64')}` } }) }
  const originals = createOriginalRecordService({ actor: () => actor, read: () => state, write: next => { state = next } })
  const original = () => {
    const detail = originals.listing(id), bytes = Buffer.from('%PDF-1.4\n%%EOF')
    return originals.mutate(id, 'upload', { version: detail.version, sampleVersion: detail.sampleVersion, requestId: crypto.randomUUID(), file: { name: '原始记录.pdf', size: bytes.length, dataUrl: `data:application/pdf;base64,${bytes.toString('base64')}` } })
  }
  return { id, service, mutate, save, word, original, originals, state: () => state, actor: (id: string) => { actor = demoActors.find(row => row.id === id)! }, advance: (ms = 1500) => { now += ms } }
}
describe('data entry detail', () => {
  it('validates required trial data before report entry while allowing incomplete drafts', () => {
    const test = setup(), initial = test.service.detail(test.id)
    const draft = { ...initial.form, conclusion: '尚未完成的试验信息', conclusionStatus: '', tester1Id: '' }
    test.mutate('save', { form: draft })
    const before = structuredClone(test.state())
    for (const action of ['save', 'validate-report-entry']) {
      expect(() => test.mutate(action, { form: draft, prepareReport: true })).toThrowError(expect.objectContaining({
        code: 'VALIDATION', message: '请先补全试验信息，再进入报告填写。',
        fieldErrors: expect.objectContaining({ conclusionStatus: expect.any(String), tester1Id: expect.any(String), 'testDates.0': expect.any(String) }),
      }))
      expect(test.state()).toEqual(before)
    }
    const form = { ...draft, conclusionStatus: '不合格', tester1Id: 'analyst', testDates: [{ kind: 'range', from: '2026-09-01', to: '2026-09-02' }] }
    expect(() => test.mutate('save', { form, prepareReport: true })).toThrowError(expect.objectContaining({ fieldErrors: { failedParameters: expect.any(String) } }))
    const saved = test.mutate('save', { form: { ...form, failedParameters: '外观' }, prepareReport: true })
    expect(saved.form.conclusion).toBe(draft.conclusion)
    expect(saved.sample.dataStatus).toBe(initial.sample.dataStatus)
    const ready = structuredClone(test.state())
    expect(test.mutate('validate-report-entry').form).toEqual(saved.form)
    expect(test.state()).toEqual(ready)
  })
  it('warns about missing originals for this sample, including legacy files but excluding deleted migrated copies', () => {
    const test = setup(); test.save(); test.word(); test.mutate('combine'); test.advance()
    const missing = () => expect(() => test.mutate('complete')).toThrowError(expect.objectContaining({ code: 'BUSINESS_RULE', fieldErrors: { originalRecords: expect.any(String) } }))
    const before = structuredClone(test.state())
    missing(); expect(test.state()).toEqual(before)
    const uploaded = test.original(), record = uploaded.records[0]!
    const store = structuredClone(test.state().originalRecords![test.id]!)
    test.state().originalRecords = { 'demo-yp-77': store }
    missing()
    test.state().originalRecords![test.id] = { ...store, records: [{ id: 'empty', name: '无文件', source: 'file', files: [] }, { id: 'external', name: 'ELN', source: 'eln', eln: { systemId: 'demo-eln', recordId: 'record-1' } }] }
    missing()
    test.state().originalRecords![test.id] = store
    expect(test.mutate('complete').sample.dataStatus).toBe('检测数据录入完成')
    test.mutate('undo')
    const current = test.originals.listing(test.id)
    test.originals.mutate(test.id, 'remove', { version: current.version, sampleVersion: current.sampleVersion, requestId: crypto.randomUUID(), recordId: record.id })
    missing()
    const bytes = Buffer.from('%PDF-1.4\n%%EOF')
    test.mutate('upload', { kind: 'original', file: { name: '旧原始记录.pdf', size: bytes.length, dataUrl: `data:application/pdf;base64,${bytes.toString('base64')}` } })
    expect(test.mutate('complete').sample.dataStatus).toBe('检测数据录入完成')
    test.mutate('undo')
    const legacy = test.originals.listing(test.id)
    test.originals.mutate(test.id, 'remove', { version: legacy.version, sampleVersion: legacy.sampleVersion, requestId: crypto.randomUUID(), recordId: legacy.records[0]!.id })
    expect(test.service.detail(test.id).files.some(file => file.kind === 'original')).toBe(true)
    missing()
    test.original()
    expect(test.mutate('complete').sample.dataStatus).toBe('检测数据录入完成')
  })
  it('allows explicit completion without originals but still validates fields, report freshness and versions', () => {
    const test = setup(), acknowledged = { acknowledgeMissingOriginals: true }
    expect(() => test.mutate('complete', acknowledged)).toThrowError(expect.objectContaining({ code: 'VALIDATION' }))
    test.save()
    expect(() => test.mutate('complete', acknowledged)).toThrow(/最新最终报告/)
    test.mutate('combine'); test.advance()
    expect(() => test.mutate('complete', { acknowledgeMissingOriginals: 'true' })).toThrow(/尚未上传原始记录/)
    expect(test.mutate('complete', { ...acknowledged, version: 999 }).sample.dataStatus).toBe('检测数据录入完成')
    expect(test.state().dataEntries![test.id]!.events.at(-1)?.reason).toBe('已确认无原始记录，继续完成录入')
    test.mutate('undo')
    expect(() => test.mutate('complete')).toThrow(/尚未上传原始记录/)
    test.mutate('save', { form: { ...test.service.detail(test.id).form, notes: '更新资料' } })
    expect(() => test.mutate('complete', acknowledged)).toThrow(/最新最终报告/)
  })
  it('generates downloadable Word before PDF and reuses snapshots across refresh, uploads and layout changes', () => {
    const test = setup(), saved = test.save(), originalLayout = saved.sample.details!.reportSettings.layoutId
    const started = test.mutate('template-tasks'), id = started.templateJob!.id
    expect(started.templateJob).toMatchObject({ stage: 'word', wordAvailable: false, layoutId: originalLayout })
    expect(() => test.service.taskResult(test.id, id, 'word')).toThrow()
    expect(test.mutate('template-tasks').templateJob!.id).toBe(id)
    test.advance(850)
    expect(test.service.taskStatus(test.id, id)).toMatchObject({ stage: 'queued', wordAvailable: true, pdfAvailable: false })
    const word = entryWord(test.service.taskResult(test.id, id, 'word'))
    expect(word.toString()).toContain(saved.form.conclusion)
    expect(() => test.service.taskResult(test.id, id, 'pdf')).toThrow()
    test.advance(1200); expect(test.service.detail(test.id).templateJob!.stage).toBe('converting')
    test.advance(1200); expect(test.service.detail(test.id).templateJob!.pdfAvailable).toBe(true)
    test.word(); expect(test.service.detail(test.id).templateStale).toBe(false)
    expect(test.mutate('template-tasks').templateJob!.id).toBe(id)
    const alternate = saved.layouts.find(row => row.id !== originalLayout)!.id
    const changed = test.mutate('change-report-layout', { confirmed: true, layoutId: alternate })
    expect(changed.sample.details!.reportSettings.layoutId).toBe(originalLayout)
    expect(changed.templateStale).toBe(true)
    expect(changed.layoutId).toBe(alternate)
    const next = test.mutate('template-tasks').templateJob!
    expect(next.id).not.toBe(id); expect(next.layoutId).toBe(alternate)
    expect(entryWord(test.service.taskResult(test.id, id, 'word'))).toEqual(word)
    test.mutate('change-report-layout', { confirmed: true, layoutId: originalLayout })
    expect(test.service.detail(test.id).templateJob!.id).toBe(id)
    expect(test.mutate('template-tasks').templateJob!.id).toBe(id)
    expect(() => test.service.taskResult('demo-yp-77', id, 'word')).toThrow()
    expect(() => test.mutate('save', { form: saved.form, layoutId: 'missing' })).toThrowError(expect.objectContaining({ fieldErrors: { layoutId: expect.any(String) } }))
  })
  it('isolates failed conversion retries from Word generation and ignores late old-layout tasks', () => {
    const test = setup(); const saved = test.save()
    const failedWord = test.mutate('template-tasks', { scenario: 'word-failure' }).templateJob!
    test.advance(4000); expect(test.service.taskStatus(test.id, failedWord.id).stage).toBe('word-failed')
    const pdfTask = test.mutate('template-tasks', { scenario: 'pdf-failure' }).templateJob!
    test.advance(4000); expect(test.service.taskStatus(test.id, pdfTask.id)).toMatchObject({ stage: 'pdf-failed', wordAvailable: true })
    const word = entryWord(test.service.taskResult(test.id, pdfTask.id, 'word'))
    const retry = test.mutate('retry-template-pdf', { taskId: pdfTask.id }).templateJob!
    expect(retry.id).toBe(pdfTask.id); expect(retry.wordAvailable).toBe(true)
    expect(entryWord(test.service.taskResult(test.id, retry.id, 'word'))).toEqual(word)
    test.advance(3000); expect(test.service.detail(test.id).templateJob!.pdfAvailable).toBe(true)
    test.mutate('save', { form: { ...saved.form, notes: '新资料' } })
    const slow = test.mutate('template-tasks', { scenario: 'slow' }).templateJob!
    test.advance(10000); expect(test.service.taskStatus(test.id, slow.id).stage).toBe('queued')
    test.mutate('save', { form: saved.form }); test.mutate('change-report-layout', { confirmed: true, layoutId: saved.layouts.find(row => row.id !== saved.layoutId)!.id })
    const newest = test.mutate('template-tasks').templateJob!
    test.advance(60000)
    expect(test.service.taskStatus(test.id, slow.id).stage).toBe('ready')
    expect(test.service.detail(test.id).templateJob!.id).toBe(newest.id)
    expect(() => test.mutate('retry-template-pdf', { taskId: slow.id })).toThrow()
  })
  it('supports all optional file combinations and requires final output rather than a template to complete', () => {
    for (const mode of ['none', 'report', 'appendix', 'both']) {
      const test = setup(); test.save(); test.mutate('template-tasks'); test.advance(4000)
      expect(() => test.mutate('complete')).toThrow(/最终报告/)
      if (['report', 'both'].includes(mode)) test.word()
      if (['appendix', 'both'].includes(mode)) {
        const bytes = entryWord(test.service.detail(test.id))
        test.mutate('upload', { kind: 'appendix', file: { name: 'Conclusion.docx', size: bytes.length, dataUrl: `data:application/octet-stream;base64,${bytes.toString('base64')}` } })
      }
      const generated = test.mutate('combine'), id = generated.job!.id
      expect(test.mutate('combine').job!.id).toBe(id)
      test.advance(); expect(test.service.detail(test.id).reportStatus).toBe('ready')
      expect(test.mutate('combine').job!.id).toBe(id)
      const snapshot = test.service.taskResult(test.id, id, 'final')
      expect(snapshot.files.filter(file => file.kind !== 'original')).toHaveLength(mode === 'both' ? 2 : mode === 'none' ? 0 : 1)
      test.original()
      expect(test.mutate('complete').capabilities.canEdit).toBe(false)
      expect(() => test.mutate('template-tasks')).toThrow()
      expect(() => test.mutate('combine')).toThrow()
      expect(test.service.taskResult(test.id, id, 'final').form.conclusion).toBeTruthy()
      test.actor('other'); expect(() => test.service.taskResult(test.id, id, 'final')).toThrow()
    }
  })
  it('persists equipment filling options and uses the same text in the Word template', () => {
    const test = setup(), detail = test.service.detail(test.id)
    const first = test.mutate('save', { form: { ...detail.form, equipmentIds: ['equipment-1', 'equipment-2'] } })
    expect(trialEquipmentText(first.form, first.options.equipment)).toBe('DEMO-001 多参数分析仪；DEMO-002 压力试验机')
    const saved = test.mutate('save', { form: { ...first.form, showEquipmentCode: false, showEquipmentModel: true, showEquipmentManufacturer: true, showEquipmentSerial: true } })
    const expected = '多参数分析仪 / 演示通用型 / 演示设备厂商 / equipment-1-SN；压力试验机 / 演示通用型 / 演示设备厂商 / equipment-2-SN'
    expect(trialEquipmentText(saved.form, saved.options.equipment)).toBe(expected)
    expect(entryWord(saved).toString('utf8')).toContain(`试验设备：${expected}`)
    expect(saved.form.equipmentIds).toEqual(first.form.equipmentIds)
    expect(test.service.detail(test.id).form).toEqual(saved.form)
    expect(saved.reportRevision).toBeGreaterThan(first.reportRevision)
  })
  it('defaults missing trial dates to today and retains ranges for single-day history', () => {
    const test = setup()
    test.state().samples[75]!.workflow = {}
    const date = new Date(), today = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
    expect(test.service.detail(test.id).form.testDates).toEqual([{ kind: 'range', from: today, to: today }])
    test.save()
    Object.assign(test.state().dataEntries![test.id]!.form, { testDates: [{ kind: 'single', from: '2026-09-08', to: '' }] })
    expect(test.service.detail(test.id).form.testDates).toEqual([{ kind: 'range', from: '2026-09-08', to: '2026-09-08' }])
  })
  it('saves mixed dates, validates each period, migrates legacy dates and reports gaps accurately', () => {
    const test = setup(), form = test.save().form
    const periods = [{ kind: 'range', from: '2026-09-15', to: '2026-09-17' }, { kind: 'single', from: '2026-09-08', to: '' }, { kind: 'range', from: '2026-09-01', to: '2026-09-03' }]
    const saved = test.mutate('save', { form: { ...form, testDates: periods } })
    expect(saved.form.testDates[1]).toEqual({ kind: 'range', from: '2026-09-08', to: '2026-09-08' })
    expect(saved.sample.workflow).toMatchObject({ testStartDate: '2026-09-01', testEndDate: '2026-09-17' })
    expect(entryWord(saved).toString('utf8')).toContain('2026-09-01 至 2026-09-03；2026-09-08；2026-09-15 至 2026-09-17')
    const source = [{ ...test.state().samples[75]!, commissionCode: '', commissionName: '' }]
    expect(dataEntryRows(source, { dateField: 'testStartDate', from: '2026-09-08', to: '2026-09-08' })).toHaveLength(1)
    expect(dataEntryRows(source, { dateField: 'testEndDate', from: '2026-09-08', to: '2026-09-08' })).toHaveLength(1)
    expect(dataEntryRows(source, { dateField: 'testStartDate', from: '2026-09-09', to: '2026-09-14' })).toHaveLength(0)
    for (const testDates of [[], null, {}, Array(51).fill(periods[0]), [{ kind: 'other', from: '', to: '' }], [{ kind: 'single', from: 1, to: '' }], [{ kind: 'range', from: '2026-09-03', to: '2026-09-01' }], [{ kind: 'single', from: '2026-02-30', to: '' }]]) {
      expect(() => test.mutate('save', { form: { ...saved.form, testDates } })).toThrow()
      expect(test.service.detail(test.id).form.testDates).toEqual(saved.form.testDates)
    }
    for (const testDates of [[{ kind: 'range', from: '2026-09-01', to: '' }], [{ kind: 'single', from: '', to: '' }]]) {
      test.mutate('save', { form: { ...saved.form, testDates } })
      expect(() => test.mutate('complete')).toThrowError(expect.objectContaining({ code: 'VALIDATION' }))
    }
    Object.assign(test.state().dataEntries![test.id]!.form, { testDates: undefined, testStartDate: '2026-08-01', testEndDate: '2026-08-02' })
    expect(test.service.detail(test.id).form.testDates).toEqual([{ kind: 'range', from: '2026-08-01', to: '2026-08-02' }])
  })
  it('saves partial drafts, checks fields, retains assignment and isolates file ownership', () => {
    const test = setup(), original = structuredClone(test.state().samples[75]!)
    const before = test.service.detail(test.id)
    expect(before.template.error).toBeUndefined()
    const partial = test.mutate('save', { form: { ...before.form, conclusion: '草稿' } })
    expect(partial.form.conclusion).toBe('草稿')
    expect(partial.sample.dataStatus).toBe(original.dataStatus)
    expect(partial.sample.assignmentInfo?.tester1Id).toBe(original.assignmentInfo?.tester1Id)
    for (const change of [{ tester1Id: 'missing-person' }, { tester2Id: 'analyst', tester1Id: 'analyst' }, { calibrationEnabled: true, calibrationDate: '' }, { testDates: [{ kind: 'single', from: '2026-02-30', to: '' }] }, { testDates: [{ kind: 'range', from: '2026-10-01', to: '2026-09-01' }] }, { failedParameters: ['外部参数'] }, { equipmentIds: ['equipment-3'] }]) {
      expect(() => test.mutate('save', { form: { ...partial.form, ...change } })).toThrow()
      expect(test.service.detail(test.id).form).toEqual(partial.form)
    }
    expect(() => test.mutate('complete')).toThrow()
    const sampleVersion = partial.sample.version, uploaded = test.word()
    expect(uploaded.sample.version).toBe(sampleVersion)
    expect(uploaded.sample.attachments).toEqual([])
    expect(test.state().samples[75]!.attachments).toEqual(original.attachments)
    expect(() => test.service.file('demo-yp-77', uploaded.files[0]!.id)).toThrow()
    expect(uploaded.files[0]).not.toHaveProperty('dataUrl')
  })
  it('requires a fresh successful report, preserves content when regenerating, and supports undo', async () => {
    const test = setup(); test.save(); test.word()
    const start = test.mutate('combine'); expect(start.reportStatus).toBe('running')
    expect(() => test.mutate('complete')).toThrow()
    test.advance(); expect(test.service.detail(test.id).reportStatus).toBe('ready')
    const firstPdf = await entryPdf(test.service.detail(test.id)); expect(firstPdf.subarray(0, 5).toString()).toBe('%PDF-')
    const fileId = start.files[0]!.id
    const changed = test.mutate('save', { form: { ...start.form, notes: '更新备注' } })
    expect(changed.reportStatus).toBe('stale'); expect(changed.files[0]!.id).toBe(fileId)
    expect(() => test.mutate('complete')).toThrow()
    test.mutate('combine', { scenario: 'failure' }); test.advance(); expect(test.service.detail(test.id).reportStatus).toBe('failed')
    test.mutate('combine'); test.advance()
    test.original()
    const complete = test.mutate('complete')
    expect(complete.sample.dataStatus).toBe('检测数据录入完成'); expect(complete.capabilities.canEdit).toBe(false)
    expect(() => test.save()).toThrow()
    expect(test.mutate('undo').sample.dataStatus).toBe('检测数据录入中')
    expect(test.service.detail(test.id).files[0]!.id).toBe(fileId)
    test.state().samples[75]!.workflow!.auditDate = '2026-09-03'; test.mutate('complete')
    expect(() => test.mutate('undo')).toThrow()
  })
  it('normalizes legacy conclusions and requires failed parameters for unqualified reports', () => {
    const test = setup(); test.state().samples[75]!.assignmentInfo!.conclusion = '其它'
    expect(test.service.detail(test.id).form.conclusionStatus).toBe('不判定')
    expect(parseDataEntryQuery({ conclusion: '其它' }).conclusion).toBe('不判定')
    expect(dataEntryRows([{ ...test.state().samples[75]!, commissionCode: '', commissionName: '' }], {})[0]!.conclusion).toBe('不判定')
    test.save(); const form = test.service.detail(test.id).form
    test.mutate('save', { form: { ...form, conclusionStatus: '不合格' } }); test.word(); test.mutate('combine'); test.advance()
    expect(() => test.mutate('complete')).toThrowError(expect.objectContaining({ fieldErrors: { failedParameters: expect.any(String) } }))
    test.mutate('save', { form: { ...form, conclusionStatus: '不合格', failedParameters: '外观；自定义耐压参数' } })
    test.mutate('combine'); test.advance(); test.original(); expect(test.mutate('complete').sample.dataStatus).toBe('检测数据录入完成')
  })
  it('preserves free-text failed parameters and reads legacy selections as text', () => {
    const test = setup(), form = test.service.detail(test.id).form
    const saved = test.mutate('save', { form: { ...form, failedParameters: '  自定义参数；外观（裂纹）  ' } })
    expect(saved.form.failedParameters).toBe('自定义参数；外观（裂纹）')
    expect(() => test.mutate('save', { form: { ...saved.form, failedParameters: '长'.repeat(501) } })).toThrowError(expect.objectContaining({ fieldErrors: { failedParameters: expect.any(String) } }))
    expect(test.service.detail(test.id).form.failedParameters).toBe(saved.form.failedParameters)
    Object.assign(test.state().dataEntries![test.id]!.form, { failedParameters: ['外观', '耐压'] })
    expect(test.service.detail(test.id).form.failedParameters).toBe('外观、耐压')
    test.mutate('save', { form: { ...test.service.detail(test.id).form, conclusionStatus: '不合格', failedParameters: '   ' } })
    expect(() => test.mutate('complete')).toThrowError(expect.objectContaining({ fieldErrors: expect.objectContaining({ failedParameters: expect.any(String) }) }))
  })
  it('accepts stale writes, deduplicates request identifiers, and audits the real operator', () => {
    const test = setup(), detail = test.service.detail(test.id)
    const input = { version: detail.version, sampleVersion: detail.sample.version, requestId: 'same-save', form: { ...detail.form, conclusion: '保存' } }
    const saved = test.service.mutate(test.id, 'save', input)
    expect(test.service.mutate(test.id, 'save', input).version).toBe(saved.version)
    expect(test.state().dataEntries![test.id]!.events).toHaveLength(1)
    expect(test.state().dataEntries![test.id]!.events[0]!.actor).toContain('admin')
    expect(() => test.service.mutate(test.id, 'save', { ...input, form: { ...input.form, conclusion: '另一值' } })).toThrow()
    expect(() => test.service.mutate(test.id, 'save', { ...input, requestId: 'new' })).not.toThrow()
    test.state().samples[75]!.version++
    expect(() => test.service.mutate(test.id, 'save', { ...input, version: saved.version, requestId: 'newer' })).not.toThrow()
  })
  it('checks permission, department, void states and template changes', () => {
    const test = setup(); test.save(); test.word(); test.mutate('combine'); test.advance()
    test.actor('approver'); expect(test.service.detail(test.id).capabilities.canEdit).toBe(false); expect(() => test.mutate('complete')).toThrow()
    test.actor('other'); expect(() => test.service.detail(test.id)).toThrow()
    test.actor('finance'); expect(() => test.service.detail(test.id)).toThrow()
    test.actor('admin')
    test.state().samples[75]!.details!.reportSettings.layoutId = 'extended'
    expect(test.service.detail(test.id).reportStatus).toBe('stale')
    test.word(); test.mutate('combine'); test.advance()
    test.state().samples[75]!.name = '已更改样品名'
    expect(test.service.detail(test.id).reportStatus).toBe('stale')
    test.state().samples[75]!.status = 'void_pending'; expect(() => test.word()).toThrow()
  })
  it('keeps original records independent and validates file contents, ordering and size', () => {
    const test = setup(); test.save(); test.word(); test.mutate('combine'); test.advance()
    const pdf = Buffer.from('%PDF-1.4\n%%EOF'), input = { name: '记录.pdf', size: pdf.length, dataUrl: `data:application/pdf;base64,${pdf.toString('base64')}` }
    expect(test.mutate('upload', { kind: 'original', file: input }).reportStatus).toBe('ready')
    const complete = test.mutate('complete'); expect(complete.capabilities.canManageOriginals).toBe(true)
    expect(test.mutate('upload', { kind: 'original', file: input }).reportStatus).toBe('ready')
    test.mutate('undo')
    const a = test.mutate('upload', { kind: 'appendix', file: input }).files.filter(file => file.kind === 'appendix')[0]!
    const b = test.mutate('upload', { kind: 'appendix', file: { ...input, name: '附页.pdf' } }).files.filter(file => file.kind === 'appendix')[1]!
    expect(test.mutate('sort', { ids: [b.id, a.id] }).files.filter(file => file.kind === 'appendix').map(file => file.id)).toEqual([b.id, a.id])
    expect(() => test.mutate('sort', { ids: [b.id, b.id] })).toThrow()
    expect(() => test.mutate('delete', { fileId: 'unrelated' })).toThrow()
    expect(() => test.mutate('upload', { kind: 'original', file: { ...input, name: 'script.html' } })).toThrow()
    expect(() => test.mutate('upload', { kind: 'original', file: { ...input, size: 21 * 1024 * 1024 } })).toThrow()
    expect(() => test.mutate('upload', { kind: 'original', file: { ...input, name: 'image.png' } })).toThrow()
  })
})
