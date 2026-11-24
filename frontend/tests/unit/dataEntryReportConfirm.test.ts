import { describe, expect, it } from 'vitest'
import { createDataEntryService } from '../../server/dataEntryDetail'
import { seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'

function setup() {
  let state = seedRegistration(), actor = demoActors[0]!, now = 10000
  const id = 'demo-yp-76', service = createDataEntryService({ actor: () => actor, read: () => state, write: next => { state = next } }, () => now)
  const detail = () => service.detail(id)
  const payload = (values = {}) => ({ version: detail().version, sampleVersion: detail().sample.version, requestId: crypto.randomUUID(), ...values })
  const mutate = (action: string, values = {}) => service.mutate(id, action, payload(values))
  const ready = () => { mutate('combine'); now += 4000; return detail() }
  return { id, service, detail, payload, mutate, ready, actor: (id: string) => { actor = demoActors.find(row => row.id === id)! } }
}

describe('report confirmation is independent from entry completion', () => {
  it('confirms the exact report with incomplete trial fields and no originals, preserving sample status and version', () => {
    const t = setup(), before = t.ready(), request = t.payload({ taskId: before.job!.id })
    const result = t.service.mutate(t.id, 'confirm-report', request)
    expect(result.reportConfirmed).toBe(true)
    expect(result.sample).toEqual(before.sample)
    expect(result.reportRevision).toBe(before.reportRevision)
    expect(result.reportStatus).toBe('ready')
    expect(result.capabilities.canEdit).toBe(true)
    expect(t.service.mutate(t.id, 'confirm-report', request).version).toBe(result.version)
    expect(t.detail().reportConfirmed).toBe(true)
    expect(() => t.mutate('complete')).toThrow(/试验信息/)
  })
  it('rejects unknown or unfinished results and conflicts or unauthorized users', () => {
    const t = setup()
    expect(() => t.mutate('confirm-report', { taskId: 'missing' })).toThrow()
    const running = t.mutate('combine')
    expect(() => t.mutate('confirm-report', { taskId: running.job!.id })).toThrow()
    const ready = t.ready(), stale = t.payload({ taskId: ready.job!.id })
    t.mutate('save', { form: ready.form })
    expect(() => t.service.mutate(t.id, 'confirm-report', stale)).not.toThrow()
    expect(() => t.mutate('confirm-report', { taskId: 'another-task' })).toThrow()
    t.actor('approver')
    expect(() => t.mutate('confirm-report', { taskId: ready.job!.id })).toThrow()
  })
  it('invalidates confirmation when form, layout, file list or order changes and binds new confirmation to the new result', () => {
    for (const change of ['form', 'layout', 'upload', 'delete', 'sort']) {
      const t = setup()
      const upload = () => t.mutate('upload', { kind: 'appendix', file: { name: 'appendix.docx', size: 4, dataUrl: 'data:application/octet-stream;base64,UEsDBA==' } })
      if (change === 'delete' || change === 'sort') { upload(); upload() }
      const before = t.ready()
      t.mutate('confirm-report', { taskId: before.job!.id })
      if (change === 'form') t.mutate('save', { form: { ...before.form, notes: 'changed' } })
      else if (change === 'layout') t.mutate('change-report-layout', { layoutId: 'extended', confirmed: true })
      else if (change === 'delete') t.mutate('delete', { fileId: before.files[0]!.id })
      else if (change === 'sort') t.mutate('sort', { ids: before.files.map(file => file.id).reverse() })
      else upload()
      expect(t.detail().reportConfirmed).toBe(false)
      expect(() => t.mutate('confirm-report', { taskId: before.job!.id })).toThrow()
      const latest = t.ready()
      expect(latest.reportConfirmed).toBe(false)
      expect(() => t.mutate('confirm-report', { taskId: before.job!.id })).toThrow()
      expect(t.mutate('confirm-report', { taskId: latest.job!.id }).reportConfirmed).toBe(true)
      expect(t.detail().sample.dataStatus).toBe('检测数据录入中')
    }
  })
})
