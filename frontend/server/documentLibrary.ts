import { randomUUID } from 'node:crypto'
import { AppError, problem } from '../src/services/common/errors'
import type { RegistrationDependencies, RegistrationState, DemoAttachment } from '../src/types/commissions/registration'
import { canManageDocuments, documentModuleTitle, type DocumentModule, documentColumns, documentMovementColumns, type LibraryDocument, type LibraryDocumentRow, type DocumentMovementKind, type DocumentMovement } from '../src/types/quality/documentLibrary'
import { registrationCsv } from './registrationDomain'
export function seedDocumentLibrary(state: RegistrationState, now = new Date(), module: DocumentModule = 'library') {
  const documentKey = module === 'monitoring' ? 'monitoringDocuments' : 'libraryDocuments', movementKey = module === 'monitoring' ? 'monitoringMovements' : 'documentMovements'
  const names = module === 'monitoring' ? ['年度质量监控计划', '实验室比对计划', '能力验证计划', '内部质量控制计划', '留样复测计划', '分部质量监控计划'] : ['质量手册', '程序文件', '设备操作规程', '样品管理规定', '安全操作指南', '分部作业指导书']
  if (state[documentKey]) return
  state[documentKey] = names.map((name, i) => ({ id: `${module}-document-${i + 1}`, code: `${module === 'monitoring' ? 'ZLJK' : 'WJ'}-${String(i + 1).padStart(3, '0')}`, category: module === 'monitoring' ? '质量监控' : i < 2 ? '体系文件' : '作业指导书', name, quantity: 10, outstanding: i === 1 ? 2 : 0, notes: '演示记录', departmentId: i === 5 ? 'lab2' : 'lab', version: 1, files: [] }))
  const row = state[documentKey][1]!, date = now.toISOString().slice(0, 10)
  state[movementKey] = [{ id: `${module}-document-issue-demo`, documentId: row.id, kind: 'issue', code: row.code, category: row.category, name: row.name, quantity: 3, date, person: '演示用户', operatorId: 'admin', operator: '演示用户', operatedAt: now.toISOString() }, { id: `${module}-document-recover-demo`, documentId: row.id, kind: 'recover', code: row.code, category: row.category, name: row.name, quantity: 1, date, person: '演示用户', operatorId: 'admin', operator: '演示用户', operatedAt: now.toISOString() }]
}
export function createDocumentLibrary(deps: RegistrationDependencies, module: DocumentModule = 'library') {
  const documentKey = module === 'monitoring' ? 'monitoringDocuments' : 'libraryDocuments', movementKey = module === 'monitoring' ? 'monitoringMovements' : 'documentMovements'
  const read = () => deps.read!()!
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || (write ? !canManageDocuments(user) : !user.roles.some(role => ['admin', 'quality', 'reviewer', 'approver'].includes(role)))) throw new AppError('FORBIDDEN', `无权操作${documentModuleTitle(module)}。`)
    return user
  }
  const visible = (row: LibraryDocument) => deps.actor().scope === 'all' || row.departmentId === deps.actor().departmentId
  function detail(id: unknown): LibraryDocumentRow {
    actor(); const row = read()[documentKey]?.find(row => row.id === id)
    if (!row || !visible(row)) throw new AppError('NOT_FOUND', '文件不存在或无权访问，请刷新列表。')
    return { ...structuredClone(row), remaining: row.quantity - row.outstanding, usage: !row.outstanding ? '未领用' : row.outstanding === row.quantity ? '全部领用' : '部分领用', historyCount: (read()[movementKey] || []).filter(item => item.documentId === row.id).length }
  }
  function text(value: unknown, key: string, label: string, required = false, max = 200) {
    if (typeof value !== 'string' || value.length > max || required && !value.trim()) throw problem('VALIDATION', `请填写${label}，最多 ${max} 个字符。`, key)
    return value.trim()
  }
  function quantity(value: unknown, min = 0) {
    if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > 1000000) throw problem('VALIDATION', `数量须为 ${min} 至 1000000 的整数。`, 'quantity')
    return value
  }
  
  function paginate<T>(rows: T[], input: Record<string, unknown>, all = false) {
    const size = input.pageSize ?? 10, requested = input.page ?? 1
    if (typeof size !== 'number' || ![10, 20, 50].includes(size) || !Number.isSafeInteger(requested) || Number(requested) < 1) throw new AppError('VALIDATION', '分页参数有误。')
    const page = Math.min(Number(requested), Math.max(1, Math.ceil(rows.length / size)))
    return { items: all ? rows : rows.slice((page - 1) * size, page * size), total: rows.length, page, pageSize: size }
  }
  function filters(input: Record<string, unknown>) {
    const name = text(input.name ?? '', 'name', '文件名称').toLowerCase(), category = text(input.category ?? '', 'category', '文件分类').toLowerCase()
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.length > 1000 || input.ids.some(id => typeof id !== 'string' || !id || id.length > 200) || new Set(input.ids).size !== input.ids.length)) throw new AppError('VALIDATION', '所选记录有误。')
    return (row: { id: string; name: string; category: string }) => row.name.toLowerCase().includes(name) && row.category.toLowerCase().includes(category) && (!input.ids || (input.ids as string[]).includes(row.id))
  }
  function query(input: Record<string, unknown>, all = false) {
    actor(); const filter = filters(input)
    const rows = (read()[documentKey] || []).filter(visible).filter(filter).sort((a, b) => a.code.localeCompare(b.code, 'zh-CN', { numeric: true })).map(row => { const result = detail(row.id); result.files = []; return result })
    return paginate(rows, input, all)
  }
  function save(input: Record<string, unknown>) {
    const user = actor(true), previous = input.id === undefined ? undefined : detail(input.id)
    
    const code = text(input.code, 'code', '文件编号', true), name = text(input.name, 'name', '文件名称', true), category = text(input.category ?? '', 'category', '文件分类'), count = quantity(input.quantity), notes = text(input.notes ?? '', 'notes', '备注', false, 2000)
    if ((read()[documentKey] || []).some(row => row.id !== previous?.id && row.code.toLowerCase() === code.toLowerCase())) throw problem('VALIDATION', '文件编号已存在。', 'code')
    if (count < (previous?.outstanding || 0)) throw problem('VALIDATION', `总数量不能少于尚未回收的 ${previous!.outstanding} 份。`, 'quantity')
    const row: LibraryDocument = { id: previous?.id || randomUUID(), code, name, category, quantity: count, notes, departmentId: previous?.departmentId || user.departmentId, outstanding: previous?.outstanding || 0, version: (previous?.version || 0) + 1, files: previous?.files || [] }
    const state = structuredClone(read()), rows = state[documentKey] ||= []
    if (previous) rows[rows.findIndex(item => item.id === previous.id)] = row; else rows.push(row)
    deps.write!(state); return detail(row.id)
  }
  function remove(input: Record<string, unknown>) {
    actor(true); const row = detail(input.id); 
    if (row.historyCount) throw new AppError('VALIDATION', '该文件已有领用或回收记录，不能删除。')
    const state = structuredClone(read()); state[documentKey] = state[documentKey]!.filter(item => item.id !== row.id); deps.write!(state); return { id: row.id }
  }
  function move(kind: DocumentMovementKind, input: Record<string, unknown>) {
    const user = actor(true), row = detail(input.id); 
    const person = text(input.person === undefined ? user.name : input.person, 'person', kind === 'issue' ? '领用人' : '回收人', true)
    const count = quantity(input.quantity, 1), date = text(input.date, 'date', '登记日期', true, 10)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date) throw problem('VALIDATION', '请填写有效的登记日期。', 'date')
    const lastDate = (read()[movementKey] || []).filter(item => item.documentId === row.id).map(item => item.date).sort().at(-1)
    if (lastDate && date < lastDate) throw problem('VALIDATION', `登记日期不能早于最近一次登记日期 ${lastDate}。`, 'date')
    if (count > (kind === 'issue' ? row.remaining : row.outstanding)) throw problem('VALIDATION', kind === 'issue' ? `剩余数量为 ${row.remaining}，不能超量领用。` : `未回收数量为 ${row.outstanding}，不能超量回收。`, 'quantity')
    const state = structuredClone(read()), target = state[documentKey]!.find(item => item.id === row.id)!
    target.outstanding += kind === 'issue' ? count : -count; target.version++
    const record: DocumentMovement = { id: randomUUID(), documentId: row.id, kind, code: row.code, category: row.category, name: row.name, quantity: count, date, person, operatorId: user.id, operator: user.name, operatedAt: new Date().toISOString() }
    ;(state[movementKey] ||= []).push(record); deps.write!(state); return record
  }
  function history(kind: DocumentMovementKind, input: Record<string, unknown>, all = false) {
    actor(); const filter = filters(input)
    if (input.documentId !== undefined) detail(input.documentId)
    const allowed = new Set((read()[documentKey] || []).filter(visible).map(row => row.id))
    return paginate((read()[movementKey] || []).filter(row => row.kind === kind && allowed.has(row.documentId) && (!input.documentId || row.documentId === input.documentId) && filter(row)).sort((a, b) => b.date.localeCompare(a.date) || b.operatedAt.localeCompare(a.operatedAt)).map(row => ({ ...row, person: row.person ?? row.operator })), input, all)
  }
  function saveFiles(input: Record<string, unknown>) {
    actor(true); const row = detail(input.id); 
    if (!Array.isArray(input.files) || input.files.length > 100) throw new AppError('VALIDATION', '附件不能超过 100 个。')
    let total = 0; const ids = new Set<string>()
    const files: DemoAttachment[] = input.files.map(raw => {
      if (!raw || typeof raw !== 'object') throw new AppError('VALIDATION', '附件格式有误。')
      const file = raw as DemoAttachment, encoded = typeof file.dataUrl === 'string' ? file.dataUrl.match(/^data:[^,]*;base64,([A-Za-z0-9+/]*={0,2})$/)?.[1] : undefined
      if (typeof file.id !== 'string' || !file.id || ids.has(file.id) || typeof file.name !== 'string' || !file.name.trim() || file.name.length > 255 || typeof file.type !== 'string' || file.type.length > 200 || !Number.isSafeInteger(file.size) || file.size <= 0 || encoded === undefined || encoded.length % 4 || Buffer.from(encoded, 'base64').length !== file.size) throw new AppError('VALIDATION', '附件格式或内容有误。')
      total += file.size; ids.add(file.id)
      if (total > 20 * 1024 * 1024) throw new AppError('VALIDATION', '附件总计不能超过 20 MB。')
      return { id: file.id, name: file.name, type: file.type, size: file.size, dataUrl: file.dataUrl }
    })
    const state = structuredClone(read()), target = state[documentKey]!.find(item => item.id === row.id)!
    target.files = files; target.version++; deps.write!(state); return detail(row.id)
  }
  return { query, detail, save, remove, move, history, saveFiles,
    export: (input: Record<string, unknown>) => registrationCsv([documentColumns.map(c => c.label), ...query(input, true).items.map(row => documentColumns.map(c => row[c.key]))]),
    exportHistory: (kind: DocumentMovementKind, input: Record<string, unknown>) => registrationCsv([documentMovementColumns(kind).map(c => c.label), ...history(kind, input, true).items.map(row => documentMovementColumns(kind).map(c => row[c.key]))]),
  }
}
