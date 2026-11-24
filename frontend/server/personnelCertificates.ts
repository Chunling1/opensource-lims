import { randomUUID } from 'node:crypto'
import { AppError } from '../src/services/common/errors'
import { emptyPersonnel } from '../src/types/quality/personnel'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import type { RegistrationState, RegistrationDependencies, DemoAttachment } from '../src/types/commissions/registration'
import { certificateExportColumns, type CertificateListKind, type CertificateListRow, type CertificateRecord, type ApprovedProjectRecord } from '../src/types/quality/certificates'
import { createPersonnelService } from './personnel'
import { registrationCsv } from './registrationDomain'
import { attachmentReferences } from './attachmentDrafts'

// Seed once per mock session. Personnel registration and certificates share the same people.
export function seedPersonnelCertificates(state: RegistrationState) {
  state.personnelRecords ??= Array.from({ length: 12 }, (_, i) => ({
    ...emptyPersonnel(), id: `demo-person-${i + 1}`, version: 1, code: `DEMO-${String(i + 1).padStart(3, '0')}`,
    name: `演示人员${String(i + 1).padStart(2, '0')}`, gender: i % 2 ? '女' : '男', qualification: '工程师',
    departmentId: i % 2 ? 'lab2' : 'lab', department: registrationDepartments[i % 2]!.name, position: i % 3 ? '技术员（示例）' : '负责人（示例）',
  }))
  state.personnelCertificates ??= state.personnelRecords.flatMap(person => Array.from({ length: 6 }, (_, i) => {
    const number = `DEMO-C${person.code.slice(-3)}-${i + 1}`
    const data = Buffer.from(`这是 ${number} 的演示附件，仅用于验证附件查看与下载。`)
    return { id: `${person.id}-certificate-${i + 1}`, personId: person.id, version: 1, number,
      category: i % 2 ? '校准类（示例）' : '检测类（示例）', notes: '',
      files: i % 2 ? [] : [{ id: randomUUID(), name: '上岗证附件（演示）.txt', type: 'text/plain', size: data.length, dataUrl: `data:text/plain;base64,${data.toString('base64')}` }],
    }
  }))
  state.approvedProjects ??= state.personnelCertificates.flatMap(c => Array.from({ length: 6 }, (_, i) => ({
    id: `${c.id}-project-${i + 1}`, certificateId: c.id, version: 1, code: `DEMO-P${i + 1}`, item: `核准检测项目${i + 1}（示例）`, category: c.category, notes: '',
  })))
}
const invalid = (message: string, key?: string): never => { throw new AppError('VALIDATION', message, { fieldErrors: key ? { [key]: message } : undefined }) }
function text(value: unknown, label: string, required = false, limit = 100, key?: string) {
  if (value === undefined) value = ''
  if (typeof value !== 'string' || value.length > limit || required && !value.trim()) return invalid(`请正确填写${label}。`, key)
  return value.trim()
}
function ids(value: unknown, required = false): string[] {
  if (!Array.isArray(value) || value.length > 1000 || value.some(id => typeof id !== 'string' || !id || id.length > 200) || required && !value.length) throw new AppError('BAD_REQUEST', '请选择有效记录。')
  return [...new Set(value as string[])]
}
export function createPersonnelCertificates(deps: RegistrationDependencies) {
  const personnel = createPersonnelService(deps)
  const actor = (write = false) => {
    const a = deps.actor()
    if (deps.locked?.() || !a.roles.some(r => (write ? ['admin', 'quality'] : ['admin', 'quality', 'reviewer', 'approver']).includes(r))) throw new AppError('FORBIDDEN', '无权操作上岗证信息。')
    return a
  }
  const read = () => structuredClone(deps.read!()!)
  function visiblePeople() { const a = actor(); return (read().personnelRecords || []).filter(p => !p.deleted && (a.scope === 'all' || p.departmentId === a.departmentId)) }
  function certificate(id: string) {
    actor(); const state = read(), row = state.personnelCertificates?.find(c => c.id === id)
    if (!row) throw new AppError('NOT_FOUND', '上岗证不存在。')
    const person = personnel.detail(row.personId)
    return { ...row, name: person.name, code: person.code, projectCount: (state.approvedProjects || []).filter(p => p.certificateId === row.id).length }
  }
  function project(id: string) {
    actor(); const row = read().approvedProjects?.find(p => p.id === id)
    if (!row) throw new AppError('NOT_FOUND', '核准项目不存在。')
    const c = certificate(row.certificateId)
    return { ...row, name: c.name, number: c.number }
  }
  function query(kind: CertificateListKind, input: Record<string, unknown>, all = false) {
    const people = visiblePeople(), byPerson = new Map(people.map(p => [p.id, p])), state = read()
    const certs = (state.personnelCertificates || []).filter(c => byPerson.has(c.personId)), byCert = new Map(certs.map(c => [c.id, c]))
    const filters = input.filters ?? {}
    if (!filters || typeof filters !== 'object' || Array.isArray(filters)) throw new AppError('BAD_REQUEST', '查询条件格式有误。')
    const fields = kind === 'people' ? ['code', 'name', 'department', 'position'] : kind === 'certificates' ? ['category', 'number', 'name'] : ['code', 'item']
    for (const [key, value] of Object.entries(filters)) if (!fields.includes(key) || typeof value !== 'string' || value.length > 200) throw new AppError('BAD_REQUEST', '查询条件格式有误。')
    const pageSize = input.pageSize ?? 5, requested = input.page ?? 1, scope = input.scope ?? 'related'
    if (typeof pageSize !== 'number' || ![5, 10, 20].includes(pageSize) || !Number.isSafeInteger(requested) || Number(requested) < 1 || !['related', 'all'].includes(String(scope))) throw new AppError('BAD_REQUEST', '分页或查询范围有误。')
    const parents = input.parentIds === undefined ? [] : ids(input.parentIds), selected = input.ids === undefined ? undefined : ids(input.ids)
    let rows: CertificateListRow[]
    if (kind === 'people') rows = people.map(p => ({ id: p.id, code: p.code, name: p.name, gender: p.gender, department: p.department, position: p.position, version: String(p.version) }))
    else if (kind === 'certificates') rows = certs.filter(c => scope === 'all' || parents.includes(c.personId)).map(c => ({
      id: c.id, personId: c.personId, code: byPerson.get(c.personId)!.code, name: byPerson.get(c.personId)!.name, category: c.category, number: c.number, notes: c.notes, attachments: String(c.files.length), version: String(c.version),
    }))
    else rows = (state.approvedProjects || []).filter(p => byCert.has(p.certificateId) && (scope === 'all' || parents.includes(p.certificateId))).map(p => {
      const c = byCert.get(p.certificateId)!
      return { ...p, version: String(p.version), name: byPerson.get(c.personId)!.name, number: c.number }
    })
    rows = rows.filter(row => (!selected || selected.includes(row.id)) && Object.entries(filters).every(([key, value]) => {
      const filter = String(value).trim().toLocaleLowerCase(), actual = row[key]!.toLocaleLowerCase()
      return !filter || (key === 'category' || key === 'department' ? actual === filter : actual.includes(filter))
    }))
    const page = Math.min(Number(requested), Math.max(1, Math.ceil(rows.length / pageSize)))
    return { items: all ? rows : rows.slice((page - 1) * pageSize, page * pageSize), total: rows.length, page, pageSize }
  }
  
  function saveCertificate(input: Record<string, unknown>, id?: string) {
    actor(true); const state = read(), current = id ? certificate(id) : undefined
    
    const person = personnel.detail(current?.personId || text(input.personId, '所属人员', true, 200))
    const category = text(input.category, '上岗证类别', true, 100, 'category'), number = text(input.number, '上岗证号', true, 100, 'number'), notes = text(input.notes, '备注', false, 2000, 'notes')
    const rows = state.personnelCertificates ||= []
    if (rows.some(c => c.id !== id && c.personId === person.id && c.number.toLocaleLowerCase() === number.toLocaleLowerCase())) return invalid('该人员的上岗证号已存在。', 'number')
    if (!Array.isArray(input.files) || input.files.length > 100) return invalid('附件格式有误。')
    let total = 0
    const fileIds = new Set<string>()
    const files = input.files.map((raw: DemoAttachment) => {
      if (!raw || typeof raw !== 'object') return invalid('附件格式有误。')
      const name = text(raw.name, '附件名称', true, 255), type = text(raw.type, '附件类型', false, 200), fileId = text(raw.id, '附件编号', true, 200)
      const encoded = typeof raw.dataUrl === 'string' ? raw.dataUrl.match(/^data:[^,]*;base64,([A-Za-z0-9+/]*={0,2})$/)?.[1] : undefined
      if (fileIds.has(fileId) || !Number.isSafeInteger(raw.size) || raw.size <= 0 || encoded === undefined || encoded.length % 4 || Buffer.from(encoded, 'base64').length !== raw.size) return invalid('附件内容或大小不正确。')
      fileIds.add(fileId); total += raw.size
      if (total > 20 * 1024 * 1024) return invalid('附件总计不能超过 20 MB。')
      return { id: fileId, name, type, size: raw.size, dataUrl: raw.dataUrl }
    })
    const row: CertificateRecord = { id: id || randomUUID(), personId: person.id, version: (current?.version || 0) + 1, category, number, notes, files }
    if (id) rows[rows.findIndex(c => c.id === id)] = row; else rows.unshift(row)
    deps.write!(state); return attachmentReferences(certificate(row.id))
  }
  function saveProjects(input: Record<string, unknown>, id?: string) {
    actor(true); const state = read(), current = id ? project(id) : undefined
    
    const targetIds = current ? [current.certificateId] : ids(input.certificateIds, true)
    targetIds.forEach(certificate)
    const fields = { code: text(input.code, '核准项目代码', true, 100, 'code'), item: text(input.item, '核准检测项目', true, 200, 'item'), category: text(input.category, '类别', false, 100, 'category'), notes: text(input.notes, '备注', false, 2000, 'notes') }
    const rows = state.approvedProjects ||= []
    if (rows.some(p => p.id !== id && targetIds.includes(p.certificateId) && p.code.toLocaleLowerCase() === fields.code.toLocaleLowerCase())) return invalid('所选上岗证中已存在此项目代码，请检查后重试。', 'code')
    const saved: ApprovedProjectRecord[] = targetIds.map(certificateId => ({ id: id || randomUUID(), certificateId, version: (current?.version || 0) + 1, ...fields }))
    if (id) rows[rows.findIndex(p => p.id === id)] = saved[0]!; else rows.unshift(...saved)
    for (const c of state.personnelCertificates || []) if (targetIds.includes(c.id)) c.version++
    // Validate every target before one state write, so batch creation is atomic.
    deps.write!(state); return { count: saved.length }
  }
  function remove(kind: 'certificates' | 'projects', id: string, input: Record<string, unknown>) {
    actor(true); const current = kind === 'certificates' ? certificate(id) : project(id)
    
    const state = read()
    if (kind === 'certificates') {
      const count = (state.approvedProjects || []).filter(p => p.certificateId === id).length
      if (input.projectCount !== count) throw new AppError('BUSINESS_RULE', '关联项目已变化，请重新确认删除。')
      state.personnelCertificates = (state.personnelCertificates || []).filter(c => c.id !== id)
      state.approvedProjects = (state.approvedProjects || []).filter(p => p.certificateId !== id)
    } else {
      state.approvedProjects = (state.approvedProjects || []).filter(p => p.id !== id)
      const parent = state.personnelCertificates?.find(c => 'certificateId' in current && c.id === current.certificateId)
      if (parent) parent.version++
    }
    deps.write!(state); return { deleted: true }
  }
  return { query, certificate, project, saveCertificate, saveProjects, remove,
    options() {
      const people = visiblePeople(), peopleIds = new Set(people.map(p => p.id)), state = read()
      const certs = (state.personnelCertificates || []).filter(c => peopleIds.has(c.personId)), certIds = new Set(certs.map(c => c.id))
      return { departments: registrationDepartments.filter(d => actor().scope === 'all' || d.id === actor().departmentId).map(d => d.name), categories: [...new Set(certs.map(c => c.category))], projectCategories: [...new Set((state.approvedProjects || []).filter(p => certIds.has(p.certificateId)).map(p => p.category).filter(Boolean))] }
    },
    export(kind: CertificateListKind, input: Record<string, unknown>) {
      const available = certificateExportColumns[kind], columns = input.columns
      if (!Array.isArray(columns) || !columns.length || columns.some(k => typeof k !== 'string' || !Object.hasOwn(available, k))) throw new AppError('BAD_REQUEST', '导出列有误。')
      return registrationCsv([columns.map(k => available[k]!), ...query(kind, input, true).items.map(row => columns.map(k => row[k] || ''))])
    },
  }
}
