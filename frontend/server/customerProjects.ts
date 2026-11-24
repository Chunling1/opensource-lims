import { randomUUID } from 'node:crypto'
import { AppError, problem } from '../src/services/common/errors'
import { canManageProjects, emptyProject, projectFields, type CustomerProject } from '../src/types/customers/projects'
import type { RegistrationDependencies } from '../src/types/commissions/registration'
import { registrationCsv } from './registrationDomain'
import { registrationOrganizations } from './registrationReferences'
import { parsePersonnelCsv } from './personnel'
export function createCustomerProjects(deps: RegistrationDependencies) {
  const read = () => deps.read!()!
  function actor(write = false) { const user = deps.actor(); if (deps.locked?.() || !user.roles.length || write && !canManageProjects(user)) throw new AppError('FORBIDDEN', '无权执行工程登记操作。'); return user }
  const visible = (row: CustomerProject) => deps.actor().scope === 'all' || row.departmentId === deps.actor().departmentId
  function detail(id: unknown) { actor(); const row = read().customerProjects?.find(row => row.id === id); if (!row || !visible(row)) throw new AppError('NOT_FOUND', '工程不存在或无权访问。'); return { ...row } }
  function ids(value: unknown) { if (!Array.isArray(value) || !value.length || value.length > 1000 || value.some(id => typeof id !== 'string' || !id || id.length > 100) || new Set(value).size !== value.length) throw new AppError('VALIDATION', '请选择有效的工程记录。'); return value as string[] }
  function parse(input: Record<string, unknown>) {
    const draft = emptyProject(true)
    for (const field of projectFields) {
      const raw = input[field.key] ?? ''
      if (typeof raw !== 'string' || raw.length > 500) throw problem('VALIDATION', `${field.label}最多 500 个字符。`, field.key)
      const value = raw.trim(); draft[field.key] = value
      if (field.options && value && !field.options.includes(value)) throw problem('VALIDATION', `请选择有效的${field.label}。`, field.key)
      if (field.kind === 'number' && value && (!/^\d+(\.\d{1,3})?$/.test(value) || Number(value) > 1000000000 || field.key === 'floors' && !Number.isInteger(Number(value)))) throw problem('VALIDATION', `${field.label}须为非负${field.key === 'floors' ? '整数' : '数字（最多三位小数）'}。`, field.key)
    }
    if (!draft.name) throw problem('VALIDATION', '请填写工程名称。', 'name')
    if (draft.customerPostcode && !/^\d{6}$/.test(draft.customerPostcode)) throw problem('VALIDATION', '委托单位邮编应为六位数字。', 'customerPostcode')
    return draft
  }
  function query(input: Record<string, unknown>, all = false) {
    actor(); const filters: Record<string, string> = {}
    for (const key of ['name', 'code', 'supervisionNumber']) { const value = input[key] ?? ''; if (typeof value !== 'string' || value.length > 200) throw new AppError('VALIDATION', '查询条件有误。'); filters[key] = value.trim().toLowerCase() }
    const size = input.pageSize ?? 10, requested = input.page ?? 1
    if (typeof size !== 'number' || ![10, 20, 50].includes(size) || !Number.isSafeInteger(requested) || Number(requested) < 1) throw new AppError('VALIDATION', '分页参数有误。')
    const selected = input.ids === undefined ? undefined : Array.isArray(input.ids) && !input.ids.length ? [] : ids(input.ids)
    const rows = (read().customerProjects || []).filter(visible).filter(row => Object.entries(filters).every(([key, value]) => row[key]!.toLowerCase().includes(value)) && (!selected || selected.includes(row.id)))
    const page = Math.min(Number(requested), Math.max(1, Math.ceil(rows.length / size)))
    return { items: all ? rows : rows.slice((page - 1) * size, page * size), total: rows.length, page, pageSize: size }
  }
  function save(input: Record<string, unknown>) {
    const user = actor(true), previous = input.id === undefined ? undefined : detail(input.id), draft = parse(input)
    const state = structuredClone(read()), rows = state.customerProjects ||= []
    if (!previous) state.customerProjectSequence = Math.max(state.customerProjectSequence || 0, ...rows.map(row => Number(row.code.slice(2)) || 0)) + 1
    const code = previous?.code || `GC${String(state.customerProjectSequence).padStart(6, '0')}`
    const row: CustomerProject = { ...draft, id: previous?.id || randomUUID(), code, departmentId: previous?.departmentId || user.departmentId }
    if (previous) rows[rows.findIndex(item => item.id === previous.id)] = row; else rows.push(row)
    deps.write!(state); return { ...row }
  }
  function batch(input: Record<string, unknown>) {
    actor(true); const records = ids(input.ids).map(detail), changes = input.changes
    if (!changes || typeof changes !== 'object' || Array.isArray(changes) || !Object.keys(changes).length || Object.keys(changes).some(key => !projectFields.some(field => field.key === key))) throw new AppError('VALIDATION', '请选择需要修改的字段。')
    const updates = records.map(row => ({ ...row, ...parse({ ...row, ...changes }) })), state = structuredClone(read())
    state.customerProjects = state.customerProjects!.map(row => updates.find(updated => updated.id === row.id) || row); deps.write!(state); return { count: updates.length }
  }
  function remove(input: Record<string, unknown>) { actor(true); const row = detail(input.id), state = structuredClone(read()); state.customerProjects = state.customerProjects!.filter(item => item.id !== row.id); deps.write!(state); return { id: row.id } }
  function options() { const user = actor(); const rows = (read().customerProjects || []).filter(visible); return { organizations: [...new Set([...registrationOrganizations.filter(row => user.scope === 'all' || row.departmentId === user.departmentId).map(row => row.name), ...rows.flatMap(row => projectFields.filter(field => field.kind === 'unit').map(field => row[field.key]!).filter(Boolean))])], regions: Object.fromEntries(['province', 'city', 'district'].map(key => [key, [...new Set([...(key !== 'district' ? ['北京市'] : []), ...rows.map(row => row[key]!).filter(Boolean)])]])) } }
  function importCsv(value: unknown) {
    const user = actor(true), [header, ...lines] = parsePersonnelCsv(value)
    if (!header || header.length !== projectFields.length || header.some((value, index) => value.trim() !== projectFields[index]!.label)) throw new AppError('VALIDATION', '模板列不匹配，请使用下载的模板。')
    if (!lines.length || lines.length > 1000) throw new AppError('VALIDATION', '每次请导入 1 至 1000 条工程记录。')
    const drafts = lines.map((values, index) => { try { if (values.length !== header.length) throw new AppError('VALIDATION', '列数与模板不一致。'); return parse(Object.fromEntries(projectFields.map((field, i) => [field.key, values[i]!]))) } catch (error) { if (error instanceof AppError) throw new AppError(error.code, `第 ${index + 2} 行：${error.message}`); throw error } })
    const state = structuredClone(read()), rows = state.customerProjects ||= [], start = Math.max(state.customerProjectSequence || 0, ...rows.map(row => Number(row.code.slice(2)) || 0))
    rows.push(...drafts.map((draft, index) => ({ ...draft, id: randomUUID(), code: `GC${String(start + index + 1).padStart(6, '0')}`, departmentId: user.departmentId })))
    state.customerProjectSequence = start + drafts.length
    deps.write!(state); return { count: drafts.length }
  }
  return { query, detail, save, batch, remove, options, importCsv, template: () => { actor(); return registrationCsv([projectFields.map(field => field.label)]) }, export: (input: Record<string, unknown>) => registrationCsv([['工程编号', ...projectFields.map(field => field.label)], ...query(input, true).items.map(row => [row.code, ...projectFields.map(field => row[field.key]!)])]) }
}
