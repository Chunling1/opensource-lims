import { describe, expect, it, vi } from 'vitest'
import PdfPrinter from 'pdfmake'
import { createPrintQueue, type PrintSource } from '../../server/commissionPrint'
import { seedRegistration } from '../../server/registrationDomain'

function source(): PrintSource {
  const record = seedRegistration().commissions[0]!
  return { kind: 'commissions', id: record.id, code: record.code, name: record.name, canPrint: true, preview: { customer: record.customer, contact: record.contact, phone: record.phone, projects: [...record.projects] } }
}

describe('mock server print queue', () => {
  it('validates copies and document identity, deduplicates jobs, paginates and preserves snapshots', async () => {
    let clock = 100000
    const queue = createPrintQueue(() => clock, () => 0), record = source()
    const input = { documentType: 'commission', documentCode: record.code, type: 'product', layout: 'normal', copies: [4, 1] }
    expect(() => queue.submit(record, { ...input, type: 'engineering' })).toThrow('联次')
    expect(() => queue.submit(record, { ...input, documentCode: 'wrong-code' })).toThrow('单号')
    const job = queue.submit(record, input)
    expect(job.copies).toEqual([1, 4]); expect(job.status).toBe('queued')
    expect(queue.submit(record, input).id).toBe(job.id)
    clock += 6000; expect(queue.get(job.id, record).status).toBe('running')
    clock += 5000; expect(queue.get(job.id, record).status).toBe('ready')
    expect(queue.submit(record, input).id).not.toBe(job.id)
    expect(() => queue.get(job.id, { ...record, id: 'different' })).toThrow('不存在')
    const originalName = record.name
    record.name = '提交后修改，不应写入已排队的快照'
    const render = vi.spyOn(PdfPrinter.prototype, 'createPdfKitDocument')
    const pdf = await queue.pdf(job.id, record)
    const rendered = JSON.stringify(render.mock.calls[0]![0].content)
    render.mockRestore()
    expect(rendered).toContain(originalName)
    expect(rendered).toContain(record.code)
    expect(rendered).not.toContain('提交后修改，不应写入已排队的快照')
    expect(pdf.subarray(0, 5).toString()).toBe('%PDF-')
    expect(pdf.toString('latin1').match(/\/Type \/Page\b/g)).toHaveLength(2)
    expect(job.documentCode).toBe(record.code)
    expect(job).not.toHaveProperty('sampleIds')
    expect(queue.list(record, 2, 5).items).toHaveLength(0)
    expect(queue.list(record, 1, 5).total).toBe(2)
  })
  it('keeps queued jobs running independently of the page and supports failure/retry and expiry', async () => {
    let clock = 100000
    const queue = createPrintQueue(() => clock), record = source()
    const input = { documentType: 'commission', documentCode: record.code, type: 'engineering', layout: 'extended', copies: [1, 3] }
    const slow = queue.submit(record, { ...input, scenario: 'slow' })
    clock += 30000; expect(queue.get(slow.id, record).status).toBe('queued')
    clock += 21000; expect(queue.get(slow.id, record).status).toBe('ready')
    const failure = queue.submit(record, { ...input, scenario: 'failure' })
    const expired = queue.submit(record, { ...input, copies: [2], scenario: 'expired' })
    clock += 11000; expect(queue.get(failure.id, record).status).toBe('failed')
    expect(queue.submit(record, { ...input, scenario: 'failure' }).id).not.toBe(failure.id)
    await expect(queue.pdf(expired.id, record)).rejects.toThrow('过期')
  })
  it.each([0.2, 0.75, 0.9, 0.99])('draws a stable outcome once per new job: %s', value => {
    let clock = 100000, draws = 0
    const queue = createPrintQueue(() => clock, () => { draws++; return value }), record = source()
    const input = { documentType: 'commission', documentCode: record.code, type: 'product', layout: 'normal', copies: [1] }
    const task = queue.submit(record, input)
    expect(queue.submit(record, input).id).toBe(task.id)
    expect(draws).toBe(1)
    clock += 11000
    const next = queue.get(task.id, record)
    expect(next.status).toBe(value === 0.75 ? 'queued' : value === 0.9 ? 'failed' : 'ready')
    expect(next.expiresAt < clock).toBe(value === 0.99)
    expect(queue.get(task.id, record)).toEqual(next)
    expect(draws).toBe(1)
    clock += 50000
    expect(queue.submit(record, input).id).not.toBe(task.id)
    expect(draws).toBe(2)
  })
})
