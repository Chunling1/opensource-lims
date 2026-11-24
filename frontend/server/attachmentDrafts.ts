import { AppError } from '../src/services/common/errors'
import type { DemoAttachment } from '../src/types/commissions/registration'

export type AttachmentScope = 'personnel' | 'external' | 'certificate' | 'equipment' | 'document' | 'monitoring-document' | 'daily-request'
const ttl = 60 * 60 * 1000
export function attachmentFiles(value: unknown): DemoAttachment[] {
  if (!value || typeof value !== 'object') return []
  if ('dataUrl' in value && 'id' in value && 'size' in value) return [value as DemoAttachment]
  return Object.values(value).flatMap(attachmentFiles)
}
export function attachmentReferences<T>(value: T): T {
  return JSON.parse(JSON.stringify(value, (key, item) => key === 'dataUrl' ? '' : item)) as T
}
export function createAttachmentDrafts(now = Date.now) {
  type Draft = { owner: string; scope: AttachmentScope; recordId: string; expires: number; closed: boolean; files: Map<string, DemoAttachment> }
  const drafts = new Map<string, Draft>()
  const fail = (message: string): never => { throw new AppError('VALIDATION', message) }
  function sweep() { for (const [id, draft] of drafts) if (draft.expires <= now()) { draft.files.clear(); draft.closed = true } }
  function get(id: string, owner: string, scope: AttachmentScope, recordId: string, create = false) {
    sweep()
    if (!/^[a-f0-9-]{36}$/.test(id)) return fail('附件草稿编号有误。')
    let draft = drafts.get(id)
    if (!draft && create) {
      if (drafts.size >= 200) return fail('附件草稿过多，请刷新会话后重试。')
      draft = { owner, scope, recordId, expires: now() + ttl, closed: false, files: new Map() }; drafts.set(id, draft)
    }
    if (!draft || draft.closed) return fail('临时附件已失效，请重新打开表单上传。')
    if (draft.owner !== owner || draft.scope !== scope || draft.recordId !== recordId) throw new AppError('FORBIDDEN', '无权访问此附件草稿。')
    draft.expires = now() + ttl
    return draft
  }
  return {
    sweep,
    upload(id: string, owner: string, scope: AttachmentScope, recordId: string, value: unknown) {
      const draft = get(id, owner, scope, recordId, true)
      if (!value || typeof value !== 'object') return fail('附件格式有误。')
      const file = value as DemoAttachment
      if (typeof file.name !== 'string' || !file.name.trim() || file.name.length > 255 || typeof file.type !== 'string' || file.type.length > 200 || !Number.isSafeInteger(file.size) || file.size <= 0 || file.size > 20 * 1024 * 1024 || typeof file.dataUrl !== 'string') return fail('附件格式或大小有误。')
      const encoded = file.dataUrl.match(/^data:[^,]*;base64,([A-Za-z0-9+/]*={0,2})$/)?.[1]
      if (encoded === undefined || encoded.length % 4 || Buffer.from(encoded, 'base64').length !== file.size) return fail('附件内容或大小不正确。')
      if (typeof file.id !== 'string' || !/^[a-f0-9-]{36}$/.test(file.id)) return fail('附件编号有误。')
      const prior = draft.files.get(file.id)
      if (prior) {
        if (prior.name !== file.name || prior.type !== file.type || prior.dataUrl !== file.dataUrl) return fail('附件编号重复，请重新选择文件。')
        return attachmentReferences(prior)
      }
      if (draft.files.size >= 100 || [...draft.files.values()].reduce((sum, f) => sum + f.size, file.size) > 20 * 1024 * 1024) return fail('临时附件总计不能超过 20 MB、100 个。')
      const stored = { id: file.id, name: file.name, type: file.type, size: file.size, dataUrl: file.dataUrl }
      draft.files.set(stored.id, stored)
      return attachmentReferences(stored)
    },
    file(id: string, owner: string, scope: AttachmentScope, recordId: string, fileId: string) {
      const file = get(id, owner, scope, recordId).files.get(fileId)
      if (!file) return fail('临时附件不存在。')
      return file
    },
    remove(id: string, owner: string, scope: AttachmentScope, recordId: string, fileId: string) { get(id, owner, scope, recordId).files.delete(fileId) },
    discard(id: string, owner: string, scope: AttachmentScope, recordId: string) {
      const existing = drafts.get(id)
      if (existing?.closed) {
        if (existing.owner !== owner || existing.scope !== scope || existing.recordId !== recordId) throw new AppError('FORBIDDEN', '无权访问此附件草稿。')
        return
      }
      const draft = get(id, owner, scope, recordId, true)
      draft.closed = true; draft.files.clear()
    },
    resolve<T>(input: T, previous: unknown, id: unknown, owner: string, scope: AttachmentScope, recordId: string): T {
      if (typeof id === 'string') get(id, owner, scope, recordId)
      const existing = new Map(attachmentFiles(previous).map(file => [file.id, file]))
      return JSON.parse(JSON.stringify(input), (_key, value) => {
        if (!value || typeof value !== 'object' || value.dataUrl !== '' || typeof value.id !== 'string') return value
        const stored = existing.get(value.id) || (typeof id === 'string' ? get(id, owner, scope, recordId).files.get(value.id) : undefined)
        if (!stored) return fail('附件不存在或已过期，请重新上传。')
        return { ...stored }
      }) as T
    },
  }
}
