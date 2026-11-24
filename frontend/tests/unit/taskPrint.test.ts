import { describe, expect, it, vi } from 'vitest'
import PdfPrinter from 'pdfmake'
import { createTaskPrintQueue, taskPrintDocument } from '../../server/taskPrint'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'
import type { Actor } from '../../src/types/lims'

async function source() {
  const service = createRegistrationService({ actor: () => demoActors[0]! })
  await service.assignmentAction('demo-yp-51', 1, { version: 1, action: 'auto' }, 'auto')
  return service.taskPrintSource('demo-yp-51')
}
describe('task print queue', () => {
  it('prints pending and undone tasks with blank staff while keeping old files and saved assignment facts', async () => {
    let state = seedRegistration(), clock = 100000
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state, write: next => { state = next } })
    const queue = createTaskPrintQueue(() => clock, () => 0), id = 'demo-yp-51'
    const blank = { assignedById: '', assignedBy: '', dataEntryPerson: '', tester1: '', tester2: '', assignedDate: '' }
    const pending = await service.taskPrintSource(id)
    expect(pending).toMatchObject({ canPrint: true, snapshot: blank })
    const first = queue.submit(pending, { version: pending.version })
    const values = { account: 'admin', name: '演示用户', dataEntryPerson: 'analyst', tester1: 'analyst', tester2: 'reviewer', date: '2026-09-26' }
    await service.assignmentAction(id, pending.version, values, 'assign')
    const assigned = await service.taskPrintSource(id)
    expect(assigned.snapshot).toMatchObject({ assignedById: 'admin', assignedBy: '演示用户', dataEntryPerson: '李检测', tester1: '李检测', tester2: '王复核', assignedDate: values.date })
    const second = queue.submit(assigned, { version: assigned.version })
    await service.assignmentAction(id, assigned.version, {}, 'undo')
    const original = structuredClone(state), undone = await service.taskPrintSource(id)
    expect(undone).toMatchObject({ canPrint: true, snapshot: blank })
    expect(state.samples.find(sample => sample.id === id)!.assignmentInfo?.tester2).toBe('王复核')
    const third = queue.submit(undone, { version: undone.version })
    expect(state).toEqual(original)
    await service.assignmentAction(id, undone.version, { ...values, tester1: 'reviewer', tester2: 'analyst', date: '2026-09-27' }, 'assign')
    const reassigned = await service.taskPrintSource(id)
    expect(reassigned.snapshot).toMatchObject({ tester1: '王复核', tester2: '李检测', assignedDate: '2026-09-27' })
    const fourth = queue.submit(reassigned, { version: reassigned.version })
    clock += 11000
    const rendered: string[] = [], createPdf = PdfPrinter.prototype.createPdfKitDocument
    const render = vi.spyOn(PdfPrinter.prototype, 'createPdfKitDocument').mockImplementation(function (this: PdfPrinter, ...args) {
      rendered.push(JSON.stringify(args[0].content))
      return createPdf.apply(this, args)
    })
    try {
      for (const [job, snapshot] of [[first, pending], [second, assigned], [third, undone], [fourth, reassigned]] as const) {
        expect(queue.get(job.id, reassigned).historical).toBe(job.id !== fourth.id)
        await queue.pdf(job.id, reassigned)
        expect(rendered.at(-1)).toBe(JSON.stringify(taskPrintDocument(snapshot).content))
      }
    } finally { render.mockRestore() }
  })
  it('deduplicates only the same sample/version and retains independent immutable PDF snapshots', async () => {
    let clock = 100000
    const queue = createTaskPrintQueue(() => clock, () => 0), record = await source(), before = structuredClone(record)
    const job = queue.submit(record, { version: record.version })
    expect(job).toMatchObject({ status: 'queued', sourceVersion: record.version, submittedBy: { id: 'admin', name: '演示用户' }, historical: false })
    expect(record).toEqual(before)
    expect(queue.submit(record, { version: record.version }).id).toBe(job.id)
    clock += 6000; expect(queue.get(job.id, record).status).toBe('running')
    clock += 5000; expect(queue.get(job.id, record).status).toBe('ready')
    record.version++; record.name = '后来修改的名称'; record.snapshot.tester1 = '后来改派的检测人'
    expect(queue.get(job.id, record).historical).toBe(true)
    const render = vi.spyOn(PdfPrinter.prototype, 'createPdfKitDocument')
    const pdf = await queue.pdf(job.id, record)
    const definition = JSON.stringify(render.mock.calls[0]![0])
    render.mockRestore()
    expect(definition).toContain('检测任务单（演示）')
    expect(definition).toContain(before.name)
    expect(definition).toContain(before.snapshot.tester1)
    expect(definition).not.toContain('后来修改')
    expect(definition).not.toContain('后来改派')
    expect(pdf.subarray(0, 5).toString()).toBe('%PDF-')
    expect(await queue.pdf(job.id, record)).toEqual(pdf)
    expect(queue.submit(record, { version: record.version }).id).not.toBe(job.id)
    expect(queue.list(record, 1, 5).total).toBe(2)
    expect(queue.list(record, 2, 5).items).toHaveLength(0)
    expect(() => queue.get(job.id, { ...record, id: 'other' })).toThrow('不存在')
  })
  it('validates state and version and supports long queues, failure, retry and expiry', async () => {
    let clock = 100000
    const queue = createTaskPrintQueue(() => clock), record = await source()
    expect(() => queue.submit({ ...record, canPrint: false }, { version: record.version })).toThrow('仅任务分配中及后续阶段')
    expect(() => queue.submit(record, { version: '2' })).toThrow('版本')
    expect(() => queue.submit(record, { version: record.version, snapshot: {} })).toThrow('参数')
    const slow = queue.submit(record, { version: 1, scenario: 'slow' })
    await expect(queue.pdf(slow.id, record)).rejects.toThrow('尚未生成')
    clock += 30000; expect(queue.get(slow.id, record).status).toBe('queued')
    clock += 21000; expect(queue.get(slow.id, record).status).toBe('ready')
    const failed = queue.submit(record, { version: record.version, scenario: 'failure' })
    clock += 11000; expect(queue.get(failed.id, record).status).toBe('failed')
    const expired = queue.submit(record, { version: record.version, scenario: 'expired' })
    clock += 11000; await expect(queue.pdf(expired.id, record)).rejects.toThrow('过期')
    expect(queue.submit(record, { version: record.version, scenario: 'normal' }).id).not.toBe(expired.id)
  })
  it('keeps absent assignment fields blank and wraps long Chinese content on A4', async () => {
    const record = await source()
    record.snapshot.assignedById = ''; record.snapshot.assignedDate = ''; record.snapshot.tester2 = ''
    record.name = '很长的样品工程名称'.repeat(20)
    record.snapshot.parameters = ['检测参数'.repeat(80)]
    const definition = taskPrintDocument(record)
    expect(definition.pageSize).toBe('A4')
    const content = JSON.stringify(definition.content)
    for (const label of ['分配人工号', '分配日期', '检测人2']) expect(content).toContain(JSON.stringify([label, '']))
    let clock = 100000
    const queue = createTaskPrintQueue(() => clock, () => 0), job = queue.submit(record, { version: record.version })
    clock += 11000
    const pdf = await queue.pdf(job.id, record)
    expect(pdf.toString('latin1')).toMatch(/\/MediaBox \[0 0 595\.28 841\.89\]/)
  })
  it('enforces department, task read permissions and void restrictions without modifying samples', async () => {
    let state = seedRegistration(), actor: Actor = demoActors[0]!
    const service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { state = next } })
    const before = structuredClone(state)
    expect((await service.taskPrintSource('demo-yp-51')).canPrint).toBe(true)
    expect((await service.taskPrintSource('demo-yp-59')).canPrint).toBe(true)
    expect(state).toEqual(before)
    state.samples[58]!.dataStatus = '样品入库中'
    expect((await service.taskPrintSource('demo-yp-59')).canPrint).toBe(false)
    state.samples[58]!.dataStatus = '任务分配完成'
    for (const role of ['analyst', 'reviewer', 'approver']) { actor = demoActors.find(person => person.id === role)!; expect((await service.taskPrintSource('demo-yp-59')).canPrint).toBe(true) }
    actor = demoActors.find(person => person.id === 'business')!
    await expect(service.taskPrintSource('demo-yp-59')).rejects.toMatchObject({ code: 'FORBIDDEN' })
    actor = demoActors.find(person => person.id === 'other')!
    await expect(service.taskPrintSource('demo-yp-59')).rejects.toMatchObject({ code: 'NOT_FOUND' })
    actor = demoActors[0]!
    for (const status of ['voided', 'void_pending'] as const) {
      state.samples[58]!.status = status
      await expect(service.taskPrintSource('demo-yp-59')).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
    }
  })
})
