import { createHash, randomUUID } from 'node:crypto'
import { AppError } from '../src/services/common/errors'
import { registrationCanReadSamples } from '../src/services/commissions/registrationService'
import { entryCapabilities } from './dataEntryDetail'
import type { DemoAttachment, RegistrationDependencies } from '../src/types/commissions/registration'
import type { OriginalStore, OriginalContext, OriginalCapabilities, ElnPage, OriginalRecord } from '../src/types/testing/originalRecords'
import { originalAdapters, type OriginalAdapters } from './originalRecordAdapters'
import { mergeOriginalPdf } from './originalRecordPdf'
const previewJobs = new Map<string, ReturnType<typeof mergeOriginalPdf>>()

const hash = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex')
const object = (value: unknown): Record<string, unknown> => { if (!value || typeof value !== 'object' || Array.isArray(value)) throw new AppError('BAD_REQUEST', '请求格式有误。'); return value as Record<string, unknown> }
const text = (value: unknown, max = 200) => { if (typeof value !== 'string' || value.length > max) throw new AppError('VALIDATION', '文本内容有误。'); return value.trim() }
const maxFileSize = 20 * 1024 * 1024
function parseFile(value: unknown): DemoAttachment {
  const data = object(value), name = text(data.name, 255)
  if (!name.toLowerCase().endsWith('.pdf') || !Number.isSafeInteger(data.size) || Number(data.size) < 1 || Number(data.size) > maxFileSize || typeof data.dataUrl !== 'string') throw new AppError('VALIDATION', '仅支持不超过 20 MB 的 PDF 文件。')
  const base64 = data.dataUrl.match(/^data:[^,]*;base64,([A-Za-z0-9+/]*={0,2})$/)?.[1], bytes = base64 ? Buffer.from(base64, 'base64') : undefined
  if (!bytes || bytes.length !== data.size || bytes.subarray(0, 5).toString() !== '%PDF-') throw new AppError('VALIDATION', '文件内容与 PDF 格式不一致。')
  return { id: randomUUID(), name, size: bytes.length, type: 'application/pdf', dataUrl: `data:application/pdf;base64,${base64}` }
}
export function createOriginalRecordService(deps: RegistrationDependencies, now = () => Date.now(), adapters: OriginalAdapters = originalAdapters) {
  function context(id: string) {
    if (deps.locked?.()) throw new AppError('LOCKED', '工作空间已锁定。')
    const actor = deps.actor(), state = structuredClone(deps.read?.())
    if (!registrationCanReadSamples(actor)) throw new AppError('FORBIDDEN', '无权查看原始记录。')
    const sample = state?.samples.find(row => row.id === id && (actor.scope === 'all' || actor.departmentId === row.departmentId))
    if (!state || !sample) throw new AppError('NOT_FOUND', '样品不存在或已不可访问。')
    const store: OriginalStore = (state.originalRecords ??= {})[id] ??= { version: 1, records: [], migratedFileIds: [], requests: [], events: [] }
    for (const record of store.records) {
      if (record.source === 'scan') {
        // Keep legacy metadata stored, but expose only its original files in the simplified UI.
        const files = [...(record.revisions || []).flatMap(revision => revision.files), ...(record.draft?.files || [])]
        record.files = [...new Map(files.map(file => [file.id, file])).values()]; record.source = 'file'
      }
    }
    for (const file of state.dataEntries?.[id]?.files.filter(file => file.kind === 'original') || []) {
      if (store.migratedFileIds.includes(file.id)) continue
      store.records.push({ id: `legacy-${file.id}`, name: file.name, source: 'file', files: [file] }); store.migratedFileIds.push(file.id)
    }
    return { state, sample, actor, store }
  }
  function caps(c: ReturnType<typeof context>): OriginalCapabilities {
    const allowed = entryCapabilities(c.actor, c.sample).canManageOriginals
    return { canUpload: allowed, canLink: allowed, canDelete: allowed }
  }
  const find = (store: OriginalStore, recordId: string) => { const record = store.records.find(row => row.id === recordId); if (!record) throw new AppError('NOT_FOUND', '原始记录不存在或不属于此样品。'); return record }
  function external(c: ReturnType<typeof context>) {
    try { return adapters.eln(c.sample, c.actor) }
    catch (cause) { throw new AppError('UNAVAILABLE', '外部 ELN 暂不可用，请稍后重试。已导入的 PDF 保持不变。', { cause }) }
  }
  function listing(id: string): OriginalContext {
    const c = context(id)
    return { version: c.store.version, sampleVersion: c.sample.version, sampleCode: c.sample.code, capabilities: caps(c), maxFileSize, simulated: true,
      records: c.store.records.map(row => {
        return { id: row.id, name: row.name, source: row.source === 'eln' ? 'eln' : 'file', eln: row.eln, files: (row.files || []).map(({ dataUrl: _bytes, ...file }) => file), status: row.source === 'eln' ? row.files?.length ? '已导入 PDF' : '待导入 PDF' : '已上传', capabilities: caps(c) }
      }) }
  }
  function detail(id: string, recordId: string) { const record = listing(id).records.find(row => row.id === recordId); if (!record) throw new AppError('NOT_FOUND', '原始记录不存在。'); return record }
  function elnQuery(id: string, value: unknown): ElnPage {
    const c = context(id), input = object(value), code = text(input.sampleCode ?? '', 100), name = text(input.name ?? ''), page = Number(input.page ?? 1), pageSize = Number(input.pageSize ?? 10)
    if (!caps(c).canLink) throw new AppError('FORBIDDEN', '当前权限不允许关联外部原始数据。')
    if (!Number.isSafeInteger(page) || page < 1 || ![10, 20, 50].includes(pageSize)) throw new AppError('VALIDATION', '分页参数有误。')
    const rows = external(c).filter(item => item.sampleCode === c.sample.code && item.sampleCode.includes(code) && item.name.toLowerCase().includes(name.toLowerCase()))
    return { items: rows.slice((page - 1) * pageSize, page * pageSize).map(item => ({ ...item, linked: c.store.records.some(row => row.eln?.systemId === item.systemId && row.eln.recordId === item.id) })), total: rows.length, page, pageSize }
  }
  function live(id: string, recordId: string) {
    const c = context(id), record = find(c.store, recordId)
    if (!record.eln) throw new AppError('BAD_REQUEST', '此记录不是外部关联。')
    const result = adapters.eln(c.sample, c.actor).find(item => item.systemId === record.eln!.systemId && item.id === record.eln!.recordId && item.sampleCode === c.sample.code)
    if (!result) throw new AppError('NOT_FOUND', '外部记录已不存在或无权访问。')
    return result
  }
  function file(id: string, recordId: string, fileId: string) {
    const c = context(id), record = find(c.store, recordId), result = record.files?.find(file => file.id === fileId)
    if (!result) throw new AppError('NOT_FOUND', '文件不存在或不属于此记录。')
    return result
  }
  async function preview(id: string, version: number) {
    const c = context(id)
    version = c.store.version
    const key = hash({ id, version, records: c.store.records })
    if (c.store.preview?.sourceVersion === version && c.store.preview.file.id === key) return c.store.preview
    let job = previewJobs.get(key)
    if (!job) { job = mergeOriginalPdf(c.store.records); previewJobs.set(key, job) }
    try {
      const result = await job, latest = context(id)
      if (hash(latest.store.records) !== hash(c.store.records)) throw new AppError('BUSINESS_RULE', '合并期间原始记录已更新，请刷新预览。')
      latest.store.preview = { sourceVersion: version, pageCount: result.pageCount, file: { id: key, name: `${latest.sample.code}-原始记录.pdf`, type: 'application/pdf', size: result.bytes.length, dataUrl: `data:application/pdf;base64,${result.bytes.toString('base64')}` } }
      deps.write?.(latest.state)
      return latest.store.preview
    } finally { if (previewJobs.get(key) === job) previewJobs.delete(key) }
  }
  function checkImport(c: ReturnType<typeof context>, action: string, input: Record<string, unknown>) {
    if (!caps(c).canLink) throw new AppError('FORBIDDEN', '当前权限不允许导入外部原始记录。')
    if (typeof input.requestId !== 'string' || !input.requestId || input.requestId.length > 100) throw new AppError('BAD_REQUEST', '缺少请求标识。')
    const fingerprint = hash({ action, input }), previous = c.store.requests.find(req => req.actor === c.actor.id && req.id === input.requestId)
    if (previous) { if (previous.fingerprint !== fingerprint) throw new AppError('BUSINESS_RULE', '请求标识已用于不同内容。'); return true }
    
    return false
  }
  async function importEln(id: string, action: 'link' | 'update-eln', value: unknown) {
    const input = object(value), c = context(id)
    if (checkImport(c, action, input)) return listing(id)
    const existing = action === 'update-eln' ? find(c.store, String(input.recordId)) : undefined
    if (existing && !existing.eln) throw new AppError('VALIDATION', '此记录不是 ELN 记录。')
    const ids = existing ? [`${existing.eln!.systemId}:${existing.eln!.recordId}`] : input.ids
    if (!Array.isArray(ids) || !ids.length || ids.length > 50 || new Set(ids).size !== ids.length) throw new AppError('VALIDATION', '请选择不重复的外部记录。')
    const candidates = external(c), imported: OriginalRecord[] = []
    for (const key of ids) {
      const row = candidates.find(item => `${item.systemId}:${item.id}` === key && item.sampleCode === c.sample.code)
      if (!row) throw new AppError('VALIDATION', '外部记录已不可关联，请重新查询。')
      if (!existing && c.store.records.some(item => item.eln?.systemId === row.systemId && item.eln.recordId === row.id)) continue
      let file: DemoAttachment
      try {
        const bytes = Buffer.from(await adapters.pdf(c.sample, c.actor, row))
        file = parseFile({ name: `${row.name.replace(/[\\/:*?"<>|]/g, '_').slice(0, 240)}.pdf`, size: bytes.length, dataUrl: `data:application/pdf;base64,${bytes.toString('base64')}` })
        await mergeOriginalPdf([{ id: row.id, name: row.name, source: 'file', files: [file] }])
      } catch (cause) { throw new AppError('UNAVAILABLE', `“${row.name}”的 ELN PDF 导入失败，请重试。已有文件保持不变。`, { cause }) }
      imported.push({ id: existing?.id || randomUUID(), name: row.name, source: 'eln', files: [file], eln: { systemId: row.systemId, recordId: row.id, version: row.version, updatedAt: row.updatedAt, importedAt: new Date(now()).toISOString(), status: row.status } })
    }
    // Re-read after network/PDF work so neither sample edits nor concurrent uploads are overwritten.
    const latest = context(id)
    if (checkImport(latest, action, input)) return listing(id)
    if (existing) latest.store.records = latest.store.records.map(row => row.id === existing.id ? imported[0]! : row)
    else latest.store.records.push(...imported)
    latest.store.version++; delete latest.store.preview
    latest.store.requests.push({ id: input.requestId as string, actor: latest.actor.id, fingerprint: hash({ action, input }) })
    latest.store.events.push({ action, actor: latest.actor.id, at: new Date(now()).toISOString(), reason: imported.map(row => row.id).join(',') })
    deps.write?.(latest.state)
    return listing(id)
  }
  function mutate(id: string, action: string, value: unknown): OriginalContext {
    if (!['upload', 'remove', 'rename', 'reorder'].includes(action)) throw new AppError('NOT_FOUND', '原始记录操作不存在。')
    const input = object(value), c = context(id), { store, sample, actor } = c
    const allowed = action === 'link' ? caps(c).canLink : action === 'remove' ? caps(c).canDelete : caps(c).canUpload
    if (!allowed) throw new AppError('FORBIDDEN', '当前权限或记录状态不允许此操作。')
    if (typeof input.requestId !== 'string' || !input.requestId || input.requestId.length > 100) throw new AppError('BAD_REQUEST', '缺少请求标识。')
    const fingerprint = hash({ action, input }), previous = store.requests.find(req => req.actor === actor.id && req.id === input.requestId)
    if (previous) { if (previous.fingerprint !== fingerprint) throw new AppError('BUSINESS_RULE', '请求标识已用于不同内容。'); return listing(id) }
    
    if (action === 'upload') {
      const file = parseFile(input.file)
      store.records.push({ id: randomUUID(), name: file.name, source: 'file', files: [file] })
    } else if (action === 'rename') {
      const record = find(store, String(input.recordId)), name = text(input.name, 255)
      if (!name || record.source === 'eln') throw new AppError('VALIDATION', '请填写上传记录的名称，外部记录名称由 ELN 管理。')
      record.name = name
    } else if (action === 'reorder') {
      if (!Array.isArray(input.ids) || input.ids.length !== store.records.length || new Set(input.ids).size !== store.records.length) throw new AppError('VALIDATION', '请提交完整且不重复的记录顺序。')
      store.records = input.ids.map(id => find(store, String(id)))
    } else {
      const ids = input.ids ?? [input.recordId]
      if (!Array.isArray(ids) || !ids.length || new Set(ids).size !== ids.length) throw new AppError('VALIDATION', '请选择要删除的记录。')
      for (const id of ids) find(store, String(id))
      store.records = store.records.filter(row => !ids.includes(row.id))
    }
    store.version++; delete store.preview; store.requests.push({ id: input.requestId, actor: actor.id, fingerprint }); store.events.push({ action, actor: actor.id, at: new Date(now()).toISOString(), reason: typeof input.recordId === 'string' ? input.recordId : '' })
    deps.write?.(c.state)
    return listing(id)
  }
  return { listing, detail, elnQuery, live, file, mutate, importEln, preview }
}
