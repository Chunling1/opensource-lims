import { expect, it } from 'vitest'
import { createOriginalRecordService } from '../../server/originalRecords'
import { originalAdapters, type OriginalAdapters } from '../../server/originalRecordAdapters'
import { seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'
import { originalPdf } from '../helpers/originalPdf'
import { PDFDocument } from 'pdf-lib'
const bytes = Buffer.from('%PDF-1.4\n%%EOF'), pdf = { name: '原始记录.pdf', size: bytes.length, dataUrl: `data:application/pdf;base64,${bytes.toString('base64')}` }
function setup(adapters: OriginalAdapters = originalAdapters) {
  let state = seedRegistration(), actor = demoActors[0]!
  const id = 'demo-yp-76', service = createOriginalRecordService({ actor: () => actor, read: () => state, write: value => { state = value } }, undefined, adapters)
  const list = () => service.listing(id)
  const input = (value: Record<string, unknown>) => ({ version: list().version, sampleVersion: list().sampleVersion, requestId: crypto.randomUUID(), ...value })
  const act = (action: string, value: Record<string, unknown>) => service.mutate(id, action, input(value))
  return { id, service, list, input, act, state: () => state, actor: (id: string) => { actor = demoActors.find(row => row.id === id)! } }
}
it('uploads PDF atomically, rejects other formats and isolates files and report state', () => {
  const t = setup(), before = structuredClone(t.state()), row = t.act('upload', { file: pdf }).records[0]!
  expect(row.source).toBe('file'); expect(row.files[0]).not.toHaveProperty('dataUrl')
  expect(t.service.file(t.id, row.id, row.files[0]!.id).dataUrl).toBe(pdf.dataUrl)
  expect(() => t.service.file('demo-yp-77', row.id, row.files[0]!.id)).toThrow()
  for (const file of [{ ...pdf, name: 'image.png' }, { ...pdf, size: 21 * 1024 * 1024 }, { ...pdf, dataUrl: 'data:application/pdf;base64,YmFk' }]) expect(() => t.act('upload', { file })).toThrow()
  expect(t.list().records).toHaveLength(1)
  expect(t.state().samples).toEqual(before.samples); expect(t.state().dataEntries).toEqual(before.dataEntries)
  for (const action of ['recognize', 'confirm', 'revise', 'create', 'configure', 'save-draft']) expect(() => t.act(action, { recordId: row.id })).toThrow(/不存在/)
  t.act('remove', { recordId: row.id }); expect(t.list().records).toHaveLength(0)
})
it('keeps idempotency, conflicts and completed-sample permissions', () => {
  const t = setup(), request = t.input({ file: pdf })
  t.service.mutate(t.id, 'upload', request); t.service.mutate(t.id, 'upload', request)
  expect(t.list().records).toHaveLength(1)
  expect(() => t.service.mutate(t.id, 'upload', { ...request, requestId: 'stale' })).not.toThrow()
  t.state().samples[75]!.dataStatus = '检测数据录入完成'
  t.act('upload', { file: pdf }); expect(t.list().records).toHaveLength(3)
  t.actor('approver'); expect(() => t.act('upload', { file: pdf })).toThrow(); expect(t.list().capabilities.canUpload).toBe(false)
  t.actor('other'); expect(() => t.list()).toThrow()
})
it('persists record order and names, validates ownership and deletes selections atomically', () => {
  const t = setup()
  t.act('upload', { file: pdf }); t.act('upload', { file: { ...pdf, name: 'second.pdf' } })
  const [first, second] = t.list().records
  t.act('reorder', { ids: [second!.id, first!.id] })
  expect(t.list().records.map(row => row.id)).toEqual([second!.id, first!.id])
  t.act('rename', { recordId: first!.id, name: '核对后原始记录' })
  expect(t.list().records[1]!.name).toBe('核对后原始记录')
  expect(t.service.file(t.id, first!.id, first!.files[0]!.id).name).toBe(pdf.name)
  for (const ids of [[first!.id], [first!.id, first!.id], [first!.id, 'foreign']]) expect(() => t.act('reorder', { ids })).toThrow()
  expect(() => t.act('remove', { ids: [first!.id, 'foreign'] })).toThrow()
  expect(t.list().records).toHaveLength(2)
  expect(() => t.act('rename', { recordId: first!.id, name: ' ' })).toThrow()
  t.actor('approver')
  expect(() => t.act('reorder', { ids: [first!.id, second!.id] })).toThrow()
  expect(() => t.act('rename', { recordId: first!.id, name: 'changed' })).toThrow()
  t.actor('admin'); t.act('remove', { ids: [first!.id, second!.id] }); expect(t.list().records).toHaveLength(0)
})
it('preserves legacy scan files and deduplicates files across old revisions without exposing OCR', () => {
  const t = setup(), file = { ...pdf, id: 'old-file', type: 'application/pdf' }
  t.state().originalRecords = { [t.id]: { version: 1, migratedFileIds: [], requests: [], events: [], records: [{ id: 'old-record', name: '旧原始记录', source: 'scan', draft: { files: [file] }, revisions: [{ files: [file] }] }] } }
  const row = t.list().records[0]!
  expect(row.files).toHaveLength(1); expect(row).not.toHaveProperty('draft'); expect(row).not.toHaveProperty('revisions')
  expect(t.service.file(t.id, row.id, file.id).dataUrl).toBe(pdf.dataUrl)
  t.act('upload', { file: pdf }); expect(t.list().records).toHaveLength(2)
  t.act('remove', { recordId: row.id }); expect(t.list().records).toHaveLength(1)
})
it('imports ELN PDF snapshots, updates explicitly and preserves previous bytes on failures', async () => {
  let version = '1', offline = false, pdfOffline = false
  const t = setup({ ...originalAdapters, eln: (sample, actor) => { if (offline) throw new Error('offline'); return originalAdapters.eln(sample, actor).map(row => ({ ...row, version })) }, pdf: async () => { if (pdfOffline) throw new Error('offline'); return originalPdf([400], `ELN version ${version}`) } })
  const item = t.service.elnQuery(t.id, {}).items[0]!, ids = [`${item.systemId}:${item.id}`]
  const request = t.input({ ids })
  await t.service.importEln(t.id, 'link', request); await t.service.importEln(t.id, 'link', request)
  expect(t.list().records).toHaveLength(1)
  const row = t.list().records[0]!, original = t.service.file(t.id, row.id, row.files[0]!.id).dataUrl
  version = '2'; offline = true
  expect(t.list().records[0]!.eln?.version).toBe('1')
  expect((await t.service.preview(t.id, t.list().version)).file.dataUrl).toBe(original)
  await expect(t.service.importEln(t.id, 'update-eln', t.input({ recordId: row.id }))).rejects.toThrow()
  expect(t.service.file(t.id, row.id, row.files[0]!.id).dataUrl).toBe(original)
  offline = false; pdfOffline = true
  await expect(t.service.importEln(t.id, 'update-eln', t.input({ recordId: row.id }))).rejects.toThrow(/导入失败/)
  expect(t.list().records[0]!.eln?.version).toBe('1')
  pdfOffline = false
  await t.service.importEln(t.id, 'update-eln', t.input({ recordId: row.id }))
  expect(t.list().records[0]!.eln?.version).toBe('2')
  expect(t.list().records[0]!.files[0]!.id).not.toBe(row.files[0]!.id)
  await expect(t.service.importEln(t.id, 'link', t.input({ ids: ['demo-eln:demo-yp-77-eln-1'] }))).rejects.toThrow()
  t.act('remove', { recordId: row.id }); expect(t.service.elnQuery(t.id, {}).items).toHaveLength(3)
})
it('merges actual PDF pages in order, retains single-PDF bytes and rejects invalid or stale results', async () => {
  const t = setup()
  const bytes1 = await originalPdf([300, 301]), bytes2 = await originalPdf([500])
  const file = (bytes: Buffer, name: string) => ({ name, size: bytes.length, dataUrl: `data:application/pdf;base64,${bytes.toString('base64')}` })
  const first = t.act('upload', { file: file(bytes1, 'first.pdf') }).records[0]!
  expect((await t.service.preview(t.id, t.list().version)).file.dataUrl).toBe(file(bytes1, '').dataUrl)
  t.act('upload', { file: file(bytes2, 'second.pdf') })
  const combined = await t.service.preview(t.id, t.list().version)
  const widths = async (dataUrl: string) => (await PDFDocument.load(Buffer.from(dataUrl.split(',')[1]!, 'base64'))).getPages().map(page => page.getWidth())
  expect(await widths(combined.file.dataUrl)).toEqual([300, 301, 500])
  expect(await t.service.preview(t.id, t.list().version)).toEqual(combined)
  const ids = t.list().records.map(row => row.id).reverse()
  t.act('reorder', { ids })
  expect(await widths((await t.service.preview(t.id, t.list().version)).file.dataUrl)).toEqual([500, 300, 301])
  expect((await t.service.preview(t.id, combined.sourceVersion)).pageCount).toBe(3)
  t.act('rename', { recordId: first.id, name: 'new name' })
  const oldJob = t.service.preview(t.id, t.list().version)
  t.act('reorder', { ids: [...ids].reverse() })
  await expect(oldJob).rejects.toThrow(/更新/)
  const bad = t.act('upload', { file: { ...pdf, name: '损坏.pdf' } }).records.at(-1)!
  await expect(t.service.preview(t.id, t.list().version)).rejects.toThrow(/损坏.pdf/)
  expect(t.list().records).toHaveLength(3)
  t.act('remove', { recordId: bad.id }); expect((await t.service.preview(t.id, t.list().version)).pageCount).toBe(3)
  t.actor('other'); await expect(t.service.preview(t.id, 1)).rejects.toThrow()
})
it('does not overwrite concurrent changes or partially import an ELN batch', async () => {
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  const t = setup({ ...originalAdapters, pdf: async () => { await gate; return originalPdf() } })
  const item = t.service.elnQuery(t.id, {}).items[0]!
  const job = t.service.importEln(t.id, 'link', t.input({ ids: [`${item.systemId}:${item.id}`] }))
  t.act('upload', { file: pdf }); release()
  await expect(job).resolves.toBeDefined(); expect(t.list().records).toHaveLength(2)
  const partial = setup({ ...originalAdapters, pdf: async (_s, _a, row) => { if (row.id.endsWith('-2')) throw new Error('failed'); return originalPdf() } })
  await expect(partial.service.importEln(partial.id, 'link', partial.input({ ids: partial.service.elnQuery(partial.id, {}).items.slice(0, 2).map(row => `${row.systemId}:${row.id}`) }))).rejects.toThrow(/导入失败/)
  expect(partial.list().records).toHaveLength(0)
})

