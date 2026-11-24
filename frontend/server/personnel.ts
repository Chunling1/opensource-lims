import { randomUUID } from 'node:crypto'
import { AppError } from '../src/services/common/errors'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import type { RegistrationDependencies } from '../src/types/commissions/registration'
import { emptyPersonnel, personnelFields, type PersonnelRecord, type PersonnelPage, type PersonnelDraft } from '../src/types/quality/personnel'
import { registrationCsv } from './registrationDomain'
import { parsePersonnelProfile } from './personnelProfile'
import { demoActors } from '../src/services/storage/demoActors'
import type { EntryPeoplePage, EntryPersonCandidate } from '../src/types/testing/dataEntryDetail'

// Quoted commas, embedded line breaks and doubled quotes are valid CSV cells.
export function parsePersonnelCsv(value: unknown): string[][] {
  if (typeof value !== 'string' || Buffer.byteLength(value, 'utf8') > 2 * 1024 * 1024) throw new AppError('VALIDATION', '请选择不超过 2 MB 的 CSV 文件。')
  const text = value.replace(/^\uFEFF/, ''), rows: string[][] = []
  let row: string[] = [], cell = '', quoted = false, closed = false
  const field = () => { row.push(cell); cell = ''; closed = false }
  const line = () => { field(); if (row.some(v => v.trim())) rows.push(row); row = [] }
  for (let i = 0; i < text.length; i++) {
    const c = text[i]!
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++ }
      else if (c === '"') { quoted = false; closed = true }
      else cell += c
    } else if (c === ',') field()
    else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; line() }
    else if (c === '"' && !cell && !closed) quoted = true
    else { if (closed || c === '"') throw new AppError('VALIDATION', 'CSV 引号格式有误，请使用下载的模板。'); cell += c }
  }
  if (quoted) throw new AppError('VALIDATION', 'CSV 引号未闭合。')
  if (cell || row.length || closed) line()
  return rows
}
export function createPersonnelService(deps: RegistrationDependencies) {
  const actor = () => { const a = deps.actor(); if (deps.locked?.() || !a.roles.some(r => ['admin', 'quality', 'reviewer', 'approver'].includes(r))) throw new AppError('FORBIDDEN', '无权访问人员登记。'); return a }
  const writeActor = () => { const a = actor(); if (!a.roles.some(r => ['admin', 'quality'].includes(r))) throw new AppError('FORBIDDEN', '无权修改人员登记。'); return a }
  const read = () => structuredClone(deps.read!()!)
  const visible = (row: PersonnelRecord) => !row.deleted && (actor().scope === 'all' || row.departmentId === actor().departmentId)
  function users(): EntryPersonCandidate[] {
    const a = actor()
    return demoActors.filter(p => p.active !== false && (a.scope === 'all' || a.departmentId === p.departmentId)).map(p => ({ id: p.id, name: p.name, departmentId: p.departmentId, departmentName: registrationDepartments.find(d => d.id === p.departmentId)?.name || p.departmentId, certificateNumber: p.certificateNumber || '', phone: p.phone || '', email: p.email || '', position: p.position || '', jobTitle: p.jobTitle || '' }))
  }
  function resolveUser(id: unknown) {
    const person = users().find(p => p.id === id)
    if (!person) throw new AppError('VALIDATION', '人员已不可选，请重新选择。', { fieldErrors: { ['name']: '人员已不可选，请重新选择。' } })
    return person
  }
  function queryUsers(input: Record<string, unknown>): EntryPeoplePage {
    const a = actor(), fields = ['account', 'name', 'certificateNumber'] as const
    for (const f of fields) if (input[f] !== undefined && (typeof input[f] !== 'string' || String(input[f]).length > 200)) throw new AppError('BAD_REQUEST', '人员查询条件有误。')
    const size = input.pageSize ?? 10, requested = input.page ?? 1
    if (typeof size !== 'number' || ![10, 20, 50].includes(size) || !Number.isSafeInteger(requested) || Number(requested) < 1) throw new AppError('BAD_REQUEST', '人员分页参数有误。')
    const rows = users().filter(p => fields.every(f => !input[f] || (f === 'account' ? p.id : p[f]).toLocaleLowerCase().includes(String(input[f]).trim().toLocaleLowerCase()))).sort((a, b) => a.id.localeCompare(b.id))
    const page = Math.min(Number(requested), Math.max(1, Math.ceil(rows.length / size)))
    return { items: rows.slice((page - 1) * size, page * size), total: rows.length, page, pageSize: size, scope: 'all', presetConfigured: false, departmentName: registrationDepartments.find(d => d.id === a.departmentId)?.name || '' }
  }
  function parse(input: Record<string, unknown>): PersonnelDraft & { departmentId: string } {
    const a = writeActor(), draft = emptyPersonnel()
    for (const f of personnelFields) {
      const value = input[f.key] ?? ''
      if (typeof value !== 'string' || value.length > 1000) throw new AppError('VALIDATION', `${f.label}格式有误或超过 1000 字。`, { fieldErrors: { [f.key]: `${f.label}格式有误或超过 1000 字。` } })
      draft[f.key] = value.trim()
      if ('required' in f && f.required && !draft[f.key]) throw new AppError('VALIDATION', `请填写${f.label}。`, { fieldErrors: { [f.key]: `请填写${f.label}。` } })
      if ('date' in f && value && (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value)) throw new AppError('VALIDATION', `${f.label}须为有效日期（YYYY-MM-DD）。`, { fieldErrors: { [f.key]: `${f.label}须为有效日期（YYYY-MM-DD）。` } })
    }
    if (draft.gender && !['男', '女'].includes(draft.gender)) throw new AppError('VALIDATION', '性别请填写男或女。', { fieldErrors: { ['gender']: '性别请填写男或女。' } })
    const department = registrationDepartments.find(d => d.name === draft.department)
    if (!department || a.scope !== 'all' && department.id !== a.departmentId) throw new AppError('VALIDATION', '所在部门不存在或无权选择。', { fieldErrors: { ['department']: '所在部门不存在或无权选择。' } })
    return { ...draft, departmentId: department.id }
  }
  function detail(id: string) {
    actor(); const row = read().personnelRecords?.find(r => r.id === id)
    if (!row || !visible(row)) throw new AppError('NOT_FOUND', '人员记录不存在或无权访问。')
    return row
  }
  function query(input: Record<string, unknown>, all = false): PersonnelPage {
    actor(); const filters = ['name', 'code', 'school', 'major', 'qualification', 'education', 'department'] as const
    for (const key of filters) if (input[key] !== undefined && (typeof input[key] !== 'string' || String(input[key]).length > 200)) throw new AppError('BAD_REQUEST', '查询条件格式有误。')
    const sort = personnelFields.find(f => f.key === (input.sort ?? 'code'))?.key, direction = input.direction ?? 'asc'
    const requested = input.page ?? 1, size = input.pageSize ?? 10
    if (!sort || !['asc', 'desc'].includes(String(direction)) || !Number.isSafeInteger(requested) || Number(requested) < 1 || typeof size !== 'number' || ![10, 20, 50].includes(size)) throw new AppError('BAD_REQUEST', '排序或分页参数有误。')
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.some(id => typeof id !== 'string'))) throw new AppError('BAD_REQUEST', '所选记录有误。')
    const rows = (read().personnelRecords || []).filter(visible).filter(r => filters.every(key => {
      const value = String(input[key] ?? '').trim().toLocaleLowerCase(), actual = r[key].toLocaleLowerCase()
      return !value || (key === 'qualification' ? actual === value : actual.includes(value))
    }) && (!input.ids || (input.ids as string[]).includes(r.id)))
      .sort((a, b) => (a[sort].localeCompare(b[sort], 'zh-CN', { numeric: true }) || a.id.localeCompare(b.id)) * (direction === 'desc' ? -1 : 1))
    const page = Math.min(Number(requested), Math.max(1, Math.ceil(rows.length / size)))
    // List/export responses do not need the profile's potentially large attachment payloads.
    return { items: (all ? rows : rows.slice((page - 1) * size, page * size)).map(({ profile: _profile, ...row }) => row), total: rows.length, page, pageSize: size }
  }
  function save(input: Record<string, unknown>, id?: string) {
    const draft = parse(input), state = read(), rows = state.personnelRecords ||= []
    const current = id ? detail(id) : undefined
    
    if (rows.some(r => !r.deleted && r.id !== id && r.code.toLocaleLowerCase() === draft.code.toLocaleLowerCase())) throw new AppError('VALIDATION', '人员编号已存在。', { fieldErrors: { ['code']: '人员编号已存在。' } })
    const profile = parsePersonnelProfile(input.profile === undefined ? current?.profile : input.profile)
    if (profile.accountId && resolveUser(profile.accountId).name !== draft.name) throw new AppError('VALIDATION', '姓名与所选用户不一致，请重新选择人员。', { fieldErrors: { ['name']: '姓名与所选用户不一致，请重新选择人员。' } })
    const row: PersonnelRecord = { ...draft, profile, id: id || randomUUID(), version: (current?.version || 0) + 1 }
    if (current) rows[rows.findIndex(r => r.id === id)] = row; else rows.push(row)
    deps.write!(state); return row
  }
  function remove(id: string, version: unknown) {
    writeActor(); const row = detail(id)
    
    const state = read(), target = state.personnelRecords!.find(r => r.id === id)!
    target.deleted = true; target.version++; deps.write!(state); return { deleted: true }
  }
  function importCsv(value: unknown) {
    writeActor(); const [header, ...lines] = parsePersonnelCsv(value)
    if (!header || header.length !== personnelFields.length || header.some((v, i) => v.trim() !== personnelFields[i]!.label)) throw new AppError('VALIDATION', '模板列不匹配，请使用下载的导入模板。')
    if (!lines.length || lines.length > 1000) throw new AppError('VALIDATION', '每次请导入 1 至 1000 条人员记录。')
    const state = read(), rows = state.personnelRecords ||= [], codes = new Set(rows.filter(r => !r.deleted).map(r => r.code.toLocaleLowerCase()))
    const added = lines.map((values, index) => {
      try {
        if (values.length !== header.length) throw new AppError('VALIDATION', '列数与模板不一致。')
        const draft = parse(Object.fromEntries(personnelFields.map((f, i) => [f.key, values[i]])))
        if (codes.has(draft.code.toLocaleLowerCase())) throw new AppError('VALIDATION', '人员编号重复。')
        codes.add(draft.code.toLocaleLowerCase()); return { ...draft, id: randomUUID(), version: 1 }
      } catch (error) { if (error instanceof AppError) throw new AppError(error.code, `第 ${index + 2} 行：${error.message}`); throw error }
    })
    rows.push(...added); deps.write!(state); return { count: added.length }
  }
  return { query, detail, save, remove, importCsv, queryUsers, resolveUser,
    template: () => { actor(); return registrationCsv([personnelFields.map(f => f.label)]) },
    export: (input: Record<string, unknown>) => registrationCsv([personnelFields.map(f => f.label), ...query(input, true).items.map(r => personnelFields.map(f => r[f.key]))]),
  }
}
