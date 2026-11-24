import { describe, expect, it } from 'vitest'
import { createDataEntryService } from '../../server/dataEntryDetail'
import { seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'

function setup() {
  let state = seedRegistration(), actor = demoActors[0]!, now = 10000
  const id = 'demo-yp-76', service = createDataEntryService({ actor: () => actor, read: () => state, write: next => { state = next } }, () => now)
  const detail = () => service.detail(id)
  const payload = (values: Record<string, unknown> = {}) => ({ version: detail().version, sampleVersion: detail().sample.version, requestId: crypto.randomUUID(), ...values })
  const mutate = (action: string, values: Record<string, unknown> = {}) => service.mutate(id, action, payload(values))
  const upload = (kind = 'report') => mutate('upload', { kind, file: { name: `${kind}.docx`, size: 4, dataUrl: 'data:application/octet-stream;base64,UEsDBA==' } })
  return { id, service, detail, payload, mutate, upload, state: () => state, actor: (id: string) => { actor = demoActors.find(row => row.id === id)! }, advance: () => { now += 4000 } }
}

describe('simple report layout confirmation', () => {
  it('adopts the default explicitly, persists across reloads and does not stale reports for adoption alone', () => {
    const t = setup(), before = t.detail()
    expect(before.layoutAdopted).toBe(false)
    expect(t.mutate('save', { form: before.form }).layoutAdopted).toBe(false)
    const request = t.payload({ form: t.detail().form, layoutId: 'standard', adoptLayout: true })
    const adopted = t.service.mutate(t.id, 'save', request)
    expect(adopted.layoutAdopted).toBe(true)
    expect(adopted.reportRevision).toBe(before.reportRevision)
    expect(t.detail().layoutAdopted).toBe(true)
    expect(t.service.mutate(t.id, 'save', request).version).toBe(adopted.version)
    expect(t.mutate('save', { form: adopted.form, layoutId: 'extended' }).layoutAdopted).toBe(false)
    expect(t.mutate('save', { form: adopted.form, layoutId: 'extended', adoptLayout: true }).layoutAdopted).toBe(true)
  })
  it('uses legacy report artifacts as adoption evidence, but not ordinary trial saves', () => {
    for (const artifact of ['report', 'appendix', 'template', 'final', 'none']) {
      const t = setup()
      if (artifact === 'report' || artifact === 'appendix') t.upload(artifact)
      else if (artifact === 'template') t.mutate('template-tasks')
      else if (artifact === 'final') t.mutate('combine')
      else t.mutate('save', { form: t.detail().form })
      delete t.state().dataEntries![t.id]!.layoutAdopted
      expect(t.detail().layoutAdopted).toBe(artifact !== 'none')
      t.mutate('save', { form: t.detail().form })
      expect(t.state().dataEntries![t.id]!.layoutAdopted).toBe(artifact !== 'none')
    }
  })
  it('requires layout confirmation for appendices or a system-only report and preserves files', () => {
    for (const artifact of ['appendix', 'final']) {
      const t = setup()
      if (artifact === 'appendix') t.upload('appendix')
      else t.mutate('combine')
      const before = t.detail()
      expect(() => t.mutate('save', { form: before.form, layoutId: 'extended', adoptLayout: true })).toThrow(/确认/)
      expect(t.detail().files).toEqual(before.files)
      const changed = t.mutate('change-report-layout', { layoutId: 'extended', confirmed: true })
      expect(changed.layoutAdopted).toBe(true)
      expect(changed.files).toEqual(before.files)
      expect(changed.reportRevision).toBe(before.reportRevision + 1)
    }
  })
  it('rejects invalid, conflicting and unauthorized adoption without changing the marker', () => {
    const t = setup()
    expect(() => t.mutate('save', { form: t.detail().form, adoptLayout: 'true' })).toThrow()
    const request = t.payload({ form: t.detail().form, adoptLayout: true })
    t.mutate('save', { form: t.detail().form })
    expect(() => t.service.mutate(t.id, 'save', request)).not.toThrow()
    t.actor('approver')
    expect(() => t.mutate('save', { form: t.detail().form, adoptLayout: true })).toThrow()
    t.actor('admin')
    expect(t.detail().layoutAdopted).toBe(true)
  })
  it('requires confirmation after generating templates and atomically clears only the complete report', () => {
    const t = setup(); t.upload(); t.upload('appendix'); t.upload('appendix'); t.mutate('template-tasks'); t.mutate('combine'); t.advance()
    const before = t.detail(), old = before.files.find(file => file.kind === 'report')!
    expect(before.reportStatus).toBe('ready')
    expect(() => t.mutate('save', { form: before.form, layoutId: 'extended' })).toThrow(/确认/)
    expect(() => t.mutate('change-report-layout', { layoutId: 'extended' })).toThrow(/确认/)
    expect(() => t.mutate('change-report-layout', { layoutId: 'missing', confirmed: true })).toThrow()
    expect(t.detail().files).toEqual(before.files); expect(t.detail().layoutId).toBe('standard')
    const request = t.payload({ layoutId: 'extended', confirmed: true })
    const changed = t.service.mutate(t.id, 'change-report-layout', request)
    expect(changed.layoutId).toBe('extended')
    expect(changed.sample.details!.reportSettings.layoutId).toBe('standard')
    expect(changed.files).toEqual(before.files.filter(file => file.kind === 'appendix'))
    expect(changed.templateStale).toBe(true); expect(changed.reportStatus).toBe('stale')
    expect(() => t.service.file(t.id, old.id)).toThrow()
    expect(t.service.mutate(t.id, 'change-report-layout', request).version).toBe(changed.version)
    expect(t.mutate('combine').reportStatus).toBe('running')
  })
  it('allows ordinary selection before generation but checks confirmation even without an uploaded report afterwards', () => {
    const t = setup()
    expect(t.mutate('save', { form: t.detail().form, layoutId: 'extended' }).layoutId).toBe('extended')
    t.mutate('template-tasks')
    expect(() => t.mutate('save', { form: t.detail().form, layoutId: 'standard' })).toThrow(/确认/)
    expect(t.mutate('change-report-layout', { layoutId: 'standard', confirmed: true }).layoutId).toBe('standard')
  })
  it('retains files on conflicts and enforces permissions', () => {
    const t = setup(); t.upload()
    const request = t.payload({ layoutId: 'extended', confirmed: true })
    t.upload('appendix')
    expect(() => t.service.mutate(t.id, 'change-report-layout', request)).not.toThrow()
    expect(t.detail().files).toHaveLength(1)
    t.actor('approver'); expect(() => t.mutate('change-report-layout', { layoutId: 'extended', confirmed: true })).toThrow()
    t.actor('other'); expect(() => t.mutate('change-report-layout', { layoutId: 'extended', confirmed: true })).toThrow()
  })
  it('restores unfinished legacy changes without losing their original report', () => {
    const t = setup(); t.upload(); const original = t.detail().files[0]!
    Object.assign(t.state().dataEntries![t.id]!, { layoutId: 'extended', layoutChange: { fromLayoutId: 'standard', reportId: original.id }, reportCandidate: { file: { id: 'unadopted' } } })
    expect(t.detail().layoutId).toBe('standard'); expect(t.detail().files[0]!.id).toBe(original.id)
    t.mutate('save', { form: t.detail().form })
    expect(t.state().dataEntries![t.id]).not.toHaveProperty('layoutChange')
    expect(t.state().dataEntries![t.id]).not.toHaveProperty('reportCandidate')
  })
})
