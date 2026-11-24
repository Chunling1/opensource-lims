import { describe, it, expect } from 'vitest'
import { randomUUID } from 'node:crypto'
import { createAttachmentDrafts, attachmentReferences } from '../../server/attachmentDrafts'

const file = () => ({ id: randomUUID(), name: '证明.txt', type: 'text/plain', size: 3, dataUrl: 'data:text/plain;base64,YWJj' })
describe('temporary form attachments', () => {
  it('uploads once, resolves references without trusting client metadata and isolates drafts', () => {
    const store = createAttachmentDrafts(), id = randomUUID(), original = file()
    const ref = store.upload(id, 'admin', 'personnel', '', original)
    expect(ref.dataUrl).toBe('')
    expect(store.upload(id, 'admin', 'personnel', '', original)).toEqual(ref)
    expect(store.resolve({ files: [{ ...ref, name: 'tampered', size: 0 }] }, [], id, 'admin', 'personnel', '').files).toEqual([original])
    expect(() => store.file(id, 'other', 'personnel', '', ref.id)).toThrow('无权')
    expect(() => store.file(id, 'admin', 'external', '', ref.id)).toThrow('无权')
    expect(() => store.resolve({ files: [ref] }, [], id, 'admin', 'personnel', 'another-record')).toThrow('无权')
    expect(() => store.resolve({ files: [ref] }, [], undefined, 'admin', 'personnel', '')).toThrow('不存在')
    expect(store.resolve({ files: [attachmentReferences(original)] }, [original], undefined, 'admin', 'personnel', 'saved-record').files).toEqual([original])
  })
  it('keeps staged files for retry, removes only temporary data, and rejects uploads arriving after cancellation', () => {
    const store = createAttachmentDrafts(), id = randomUUID(), original = file()
    const ref = store.upload(id, 'admin', 'external', '', original)
    expect(store.resolve({ evidence: [ref] }, [], id, 'admin', 'external', '').evidence).toEqual([original])
    expect(store.file(id, 'admin', 'external', '', ref.id)).toEqual(original)
    store.remove(id, 'admin', 'external', '', ref.id)
    expect(() => store.file(id, 'admin', 'external', '', ref.id)).toThrow()
    store.discard(id, 'admin', 'external', '')
    expect(() => store.upload(id, 'admin', 'external', '', original)).toThrow('失效')
    const cancelledBeforeArrival = randomUUID()
    store.discard(cancelledBeforeArrival, 'admin', 'external', '')
    expect(() => store.upload(cancelledBeforeArrival, 'admin', 'external', '', original)).toThrow('失效')
    expect(original.dataUrl).toBe('data:text/plain;base64,YWJj')
  })
  it('expires abandoned files and rejects malformed or oversized data', () => {
    let now = 0
    const store = createAttachmentDrafts(() => now), id = randomUUID(), original = file()
    const ref = store.upload(id, 'admin', 'personnel', '', original)
    expect(() => store.upload(id, 'admin', 'personnel', '', { ...file(), size: 30 * 1024 * 1024 })).toThrow()
    expect(() => store.upload(id, 'admin', 'personnel', '', { ...file(), dataUrl: 'invalid' })).toThrow()
    now = 60 * 60 * 1000 + 1; store.sweep()
    expect(() => store.file(id, 'admin', 'personnel', '', ref.id)).toThrow('失效')
    expect(() => store.resolve({}, [], id, 'admin', 'personnel', '')).toThrow('失效')
  })
})
