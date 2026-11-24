import { AppError } from '../common/errors'
import { repository } from '../storage/database'
import { assertRole, currentActor, resolveActor } from '../../stores/session'
import { moduleMap } from './modules'
import { limsService } from './limsService'
import type { Fields, LimsDatabase, FieldDefinition } from '../../types/lims'
import { sampleService } from '../samples/sampleService'
import type { SampleInput } from '../../types/sample'
export const sampleImportFields: FieldDefinition[] = [
  { key: 'category', label: '样品类别', required: true }, { key: 'customer', label: '委托单位', required: true }, { key: 'contact', label: '联系人' }, { key: 'phone', label: '联系电话' }, { key: 'quantity', label: '数量', type: 'number', min: 0.000001, required: true }, { key: 'unit', label: '单位', required: true }, { key: 'projects', label: '检测项目', type: 'multi', required: true }, { key: 'storage', label: '保存条件' }, { key: 'notes', label: '备注' },
]
export const importDefinition = (kind: string) => kind === 'samples' ? { title: '样品', fields: sampleImportFields } : moduleMap[kind]!
export function parseCsv(text: string): string[][] {
  const rows: string[][] = []; let row: string[] = [], cell = '', quoted = false
  text = text.replace(/^\uFEFF/, '')
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '"') { if (quoted && text[i + 1] === '"') { cell += '"'; i++ } else quoted = !quoted }
    else if (c === ',' && !quoted) { row.push(cell); cell = '' }
    else if ((c === '\n' || c === '\r') && !quoted) { if (c === '\r' && text[i + 1] === '\n') i++; row.push(cell); if (row.some(Boolean)) rows.push(row); row = []; cell = '' }
    else cell += c
  }
  if (quoted) throw new AppError('BUSINESS_RULE', 'CSV 引号未闭合。')
  row.push(cell); if (row.some(Boolean)) rows.push(row)
  return rows
}
const csvCell = (v: unknown) => `"${String(v ?? '').replace(/^[=+@-]/, "'$&").replaceAll('"', '""')}"`
export async function exportCsv(kind: string) {
  const def = moduleMap[kind]!; const rows: string[][] = [['编号', '名称', '状态', ...def.fields.map(f => f.label)]]
  for (let page = 1; ; page++) { const result = await limsService.list(kind, { page, pageSize: 50 }); result.items.forEach(r => rows.push([r.code, r.name, r.status, ...def.fields.map(f => Array.isArray(r.data[f.key]) ? (r.data[f.key] as string[]).join('|') : String(r.data[f.key] ?? ''))])); if (page * 50 >= result.total) break }
  return new Blob(['\uFEFF', rows.map(row => row.map(csvCell).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' })
}
export function previewImport(kind: string, text: string) {
  if (!['customers', 'projects', 'samples'].includes(kind)) throw new AppError('BUSINESS_RULE', '请选择客户、样品或检测项目导入。')
  const def = importDefinition(kind), rows = parseCsv(text), header = rows.shift() ?? []
  const nameIndex = header.indexOf('名称'); if (nameIndex < 0) throw new AppError('BUSINESS_RULE', 'CSV 缺少“名称”列。')
  if (rows.length > 1000) throw new AppError('BUSINESS_RULE', '每次最多导入 1000 条记录。')
  return rows.map((cells, i) => {
    const data: Fields = {}, errors: string[] = [], name = cells[nameIndex]?.trim() || ''
    if (!name) errors.push('名称必填')
    for (const f of def.fields) { const value = cells[header.indexOf(f.label)] ?? ''; data[f.key] = f.type === 'number' && value ? Number(value) : f.type === 'multi' ? value.split('|').filter(Boolean) : value; if (f.required && !value.trim()) errors.push(`${f.label}必填`); if (f.type === 'number' && value && (!Number.isFinite(Number(value)) || Number(value) < (f.min ?? -Infinity))) errors.push(`${f.label}无效`) }
    return { row: i + 2, name, data, errors }
  })
}
export async function importRow(kind: string, name: string, data: Fields) {
  if (kind === 'samples') return sampleService.create({ name, category: String(data.category), customer: String(data.customer), contact: String(data.contact || ''), phone: String(data.phone || ''), quantity: Number(data.quantity), unit: String(data.unit), projects: data.projects as string[], storage: String(data.storage || ''), notes: String(data.notes || '') } satisfies SampleInput)
  return limsService.save(kind, { name, data })
}
export async function exportSamples() {
  const rows: string[][] = [['编号', '名称', ...sampleImportFields.map(f => f.label)]]
  for (let page = 1; ; page++) { const result = await sampleService.list({ page, pageSize: 50 }); result.items.forEach(s => rows.push([s.code, s.name, ...sampleImportFields.map(f => { const value = s[f.key as keyof SampleInput]; return Array.isArray(value) ? value.join('|') : String(value) })])); if (page * 50 >= result.total) break }
  return new Blob(['\uFEFF', rows.map(row => row.map(csvCell).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' })
}
async function encodeBlob(blob: Blob) { const bytes = new Uint8Array(await blob.arrayBuffer()); let binary = ''; for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192)); return btoa(binary) }
export async function backup() {
  const state = await repository.read(); assertRole(resolveActor(state, currentActor.value.id), ['system'])
  const attachments = await Promise.all(state.attachments.map(async ({ blob, ...a }) => ({ ...a, base64: await encodeBlob(blob) })))
  return new Blob([JSON.stringify({ format: 'lims-backup', version: 2, exportedAt: new Date().toISOString(), state: { ...state, attachments } })], { type: 'application/json' })
}
export async function inspectBackup(file: File) {
  let value: { format: string; version: number; state: Omit<LimsDatabase, 'attachments'> & { attachments: { id: string; base64: string; type: string; size: number; name: string; actor: string; at: string; entityId: string }[] } }
  try { value = JSON.parse(await file.text()) } catch { throw new AppError('BUSINESS_RULE', '备份文件不是有效 JSON。') }
  if (value.format !== 'lims-backup' || value.version !== 2 || value.state.schema !== 2 || !Array.isArray(value.state.records) || !Array.isArray(value.state.samples) || !Array.isArray(value.state.attachments) || !Array.isArray(value.state.actors) || !Array.isArray(value.state.approvals) || !Array.isArray(value.state.audits)) throw new AppError('BUSINESS_RULE', '备份格式或版本不兼容。')
  const state = value.state, seen = new Set<string>()
  for (const r of state.records) { if (!r.id || seen.has(r.id) || !moduleMap[r.kind] || !r.data || !Number.isInteger(r.version) || r.version < 1 || !r.name) throw new AppError('BUSINESS_RULE', '备份包含无效或重复业务记录。'); seen.add(r.id) }
  if (!state.actors.some(a => a.roles.includes('admin') && state.records.some(r => r.kind === 'users' && r.id === a.id && r.status === '有效'))) throw new AppError('BUSINESS_RULE', '备份缺少有效管理员。')
  const sampleIds = new Set<string>()
  for (const s of state.samples) { if (!s.id || sampleIds.has(s.id) || !s.code || !s.name || !['pending', 'received', 'returned'].includes(s.status) || !Number.isFinite(s.quantity) || s.quantity <= 0 || !Array.isArray(s.projects) || !Array.isArray(s.events) || !state.sampleMeta?.[s.id] || !Number.isFinite(Date.parse(s.createdAt))) throw new AppError('BUSINESS_RULE', '备份样品数据无效。'); sampleIds.add(s.id) }
  const actorIds = new Set<string>()
  for (const a of state.actors) { if (!a.id || actorIds.has(a.id) || !Array.isArray(a.roles) || !['all', 'department'].includes(a.scope) || !seen.has(a.id)) throw new AppError('BUSINESS_RULE', '备份账号数据无效。'); actorIds.add(a.id) }
  for (const r of state.records) for (const f of moduleMap[r.kind]!.fields.filter(f => f.reference)) {
    const values = Array.isArray(r.data[f.key]) ? r.data[f.key] as string[] : [String(r.data[f.key] || '')]
    for (const id of values.filter(Boolean)) { if (!(f.reference === 'samples' ? sampleIds.has(id) : f.reference === 'actors' ? actorIds.has(id) : state.records.some(x => x.id === id && x.kind === f.reference))) throw new AppError('BUSINESS_RULE', `备份记录 ${r.code} 的${f.label}关联已损坏。`) }
  }
  for (const a of state.approvals) if (!seen.has(a.entityId) || !actorIds.has(a.applicantId) || !['pending', 'approved', 'rejected'].includes(a.status)) throw new AppError('BUSINESS_RULE', '备份审批记录无效。')
  const attachments = state.attachments.map(a => { let decoded: string; try { decoded = atob(a.base64) } catch { throw new AppError('BUSINESS_RULE', '附件编码无效。') }; const blob = new Blob([Uint8Array.from(decoded, x => x.charCodeAt(0))], { type: a.type }); if (blob.size !== a.size || !seen.has(a.entityId)) throw new AppError('BUSINESS_RULE', '附件内容或关联记录无效。'); const { base64: _base64, ...meta } = a; return { ...meta, blob } })
  return { ...state, attachments } as LimsDatabase
}
export async function restore(state: LimsDatabase, expectedRevision: number) {
  return repository.write(current => { const actor = resolveActor(current, currentActor.value.id); assertRole(actor, ['system']);  const revision = current.revision; Object.assign(current, structuredClone(state), { revision }); current.audits.push({ id: crypto.randomUUID(), entityId: 'workspace', kind: 'system', action: '恢复备份', actorId: actor.id, actor: actor.name, at: new Date().toISOString(), reason: `恢复 ${state.records.length} 条业务记录` }) })
}
export async function backupRevision() { const state = await repository.read(); assertRole(resolveActor(state, currentActor.value.id), ['system']); return state.revision }
