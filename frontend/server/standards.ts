import { migrateStandardGroups } from './standardGroupMigration'
import { clientToday } from '../src/services/common/date'
import { randomUUID } from 'node:crypto'
import { AppError, problem } from '../src/services/common/errors'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import type { RegistrationDependencies, RegistrationState } from '../src/types/commissions/registration'
import { canManageStandards, canEditStandard, standardExtensionDays, emptyStandard, standardColumns, standardQualifications, type StandardRecord, type StandardRow } from '../src/types/quality/standards'
import type { EquipmentGroupContext, EquipmentGroupState } from '../src/types/quality/equipmentGroups'
import { registrationCsv } from './registrationDomain'
import { parsePersonnelCsv } from './personnel'
export function seedStandards(state: RegistrationState) {
  migrateStandardGroups(state)
  state.standards ||= ['检测方法标准（示例）', '样品制备标准（示例）', '检验规程（示例）', '校准规范（示例）', '现场检测标准（示例）', '分部检测标准（示例）'].map((name, i) => ({ ...emptyStandard(), id: `standard-${i + 1}`, version: 1, code: `DEMO-${i + 1}-2026`, controlNumber: `BZ-${String(i + 1).padStart(3, '0')}`, name, category: ['方法标准', '操作规程', '技术规范'][i % 3]!, groupIds: [`standard-category-${i % 5 + 1}`], implementedAt: '2026-01-01', location: i % 2 ? '资料室' : '实验室', issuer: '演示用户', quantity: 5, qualification: standardQualifications[i % 4]!, departmentIds: [i === 5 ? 'lab2' : 'lab'], notes: '演示记录，非真实标准' }))
}
export function createStandards(deps: RegistrationDependencies) {
  migrateStandardGroups(deps.read!()!)
  const read = () => deps.read!()!
  function actor(write = false) { const user = deps.actor(); if (deps.locked?.() || (write ? !canManageStandards(user) : !user.roles.some(role => ['admin', 'quality', 'reviewer', 'approver'].includes(role)))) throw new AppError('FORBIDDEN', '无权操作检测标准。'); return user }
  const visible = (row: StandardRecord) => deps.actor().scope === 'all' || row.departmentIds.includes(deps.actor().departmentId) || !row.departmentIds.length && row.ownerDepartmentId === deps.actor().departmentId
  const groupOptions = () => (read().standardGroups || []).filter(row => deps.actor().scope === 'all' || row.departmentId === deps.actor().departmentId)
  function options() { actor(); return { departments: registrationDepartments.filter(row => deps.actor().scope === 'all' || row.id === deps.actor().departmentId), locations: [...new Set((read().standards || []).filter(visible).map(row => row.location).filter(Boolean))] } }
  function present(record: StandardRecord): StandardRow { return { ...structuredClone(record), extensionDays: standardExtensionDays(record.abolished, record.abolishedAt, clientToday()), departments: record.departmentIds.map(id => registrationDepartments.find(row => row.id === id)?.name).filter(Boolean).join('、') } }
  function detail(id: unknown) { actor(); const row = read().standards?.find(row => row.id === id); if (!row || !visible(row)) throw new AppError('NOT_FOUND', '标准不存在或无权访问，请刷新列表。'); return present(row) }
  
  function text(value: unknown, key: string, label: string, required = false, max = 200) { if (typeof value !== 'string' || value.length > max || required && !value.trim()) throw problem('VALIDATION', `请填写${label}，最多 ${max} 个字符。`, key); return value.trim() }
  function date(value: unknown, key: string, label: string) { const result = text(value, key, label, true, 10); if (!/^\d{4}-\d{2}-\d{2}$/.test(result) || !Number.isFinite(Date.parse(result)) || new Date(result).toISOString().slice(0, 10) !== result) throw problem('VALIDATION', `请填写有效的${label}。`, key); return result }
  function ids(value: unknown, key: string, max = 1000): string[] { if (!Array.isArray(value) || value.length > max || value.some(id => typeof id !== 'string' || !id) || new Set(value).size !== value.length) throw problem('VALIDATION', '所选记录有误。', key); return value }
  function bool(value: unknown, key: string) { if (typeof value !== 'boolean') throw problem('VALIDATION', '请选择是或否。', key); return value }
  function parse(input: Record<string, unknown>) {
    actor(true)
    const code = text(input.code, 'code', '标准编号', true), name = text(input.name, 'name', '标准名称', true), controlNumber = text(input.controlNumber ?? '', 'controlNumber', '受控号')
    const departmentIds = ids(input.departmentIds === undefined ? [] : input.departmentIds, 'departmentIds'), category = text(input.category ?? '', 'category', '类别'), choices = options()
    if (departmentIds.some(id => !choices.departments.some(row => row.id === id))) throw problem('VALIDATION', '请选择权限范围内的使用部门。', 'departmentIds')
    const implementedAt = date(input.implementedAt, 'implementedAt', '实施日期'), abolished = bool(input.abolished, 'abolished'), abolishedAt = abolished ? date(input.abolishedAt, 'abolishedAt', '作废日期') : ''
    if (abolishedAt && abolishedAt < implementedAt) throw problem('VALIDATION', '作废日期不得早于实施日期。', 'abolishedAt')
    const quantity = input.quantity === '' || input.quantity === null ? null : input.quantity
    if (quantity !== null && (typeof quantity !== 'number' || !Number.isSafeInteger(quantity) || quantity < 0 || quantity > 1000000)) throw problem('VALIDATION', '发放数量须为 0 至 1000000 的整数。', 'quantity')
    const qualification = text(input.qualification, 'qualification', '标准资质类别')
    if (qualification && !(standardQualifications as readonly string[]).includes(qualification)) throw problem('VALIDATION', '请选择有效的标准资质类别。', 'qualification')
    return { code, name, controlNumber, departmentIds, category, implementedAt, abolished, abolishedAt, extensionDays: null, replacementCode: abolished ? text(input.replacementCode ?? '', 'replacementCode', '替换标准号') : '', qualification, quantity: quantity as number | null, location: text(input.location ?? '', 'location', '存放地点'), issuer: text(input.issuer ?? '', 'issuer', '发放人'), outsideScope: bool(input.outsideScope, 'outsideScope'), english: bool(input.english, 'english'), notes: text(input.notes ?? '', 'notes', '备注', false, 2000) }
  }
  function duplicate(row: StandardRecord, others: StandardRecord[]) { if (others.some(item => item.id !== row.id && (row.controlNumber ? item.controlNumber.toLowerCase() === row.controlNumber.toLowerCase() : !item.controlNumber && item.code.toLowerCase() === row.code.toLowerCase()))) throw problem('VALIDATION', row.controlNumber ? '受控号已存在。' : '该标准编号已存在，请填写不同的受控号。', row.controlNumber ? 'controlNumber' : 'code') }
  function query(input: Record<string, unknown>, all = false) {
    actor(); const fields = ['code', 'name', 'controlNumber', 'location'] as const, filters = Object.fromEntries(fields.map(key => [key, text(input[key] ?? '', key, '查询条件').toLowerCase()]))
    const category = text(input.category ?? '', 'category', '类别').toLowerCase(), qualification = text(input.qualification ?? '', 'qualification', '标准资质类别'), departmentId = text(input.departmentId ?? '', 'departmentId', '使用部门')
    if (input.ownDepartment !== undefined && typeof input.ownDepartment !== 'boolean') throw new AppError('VALIDATION', '部门范围有误。')
    const selected = input.ids === undefined ? undefined : ids(input.ids, 'ids'), size = input.pageSize ?? 10, requested = input.page ?? 1
    if (typeof size !== 'number' || ![10, 20, 50].includes(size) || !Number.isSafeInteger(requested) || Number(requested) < 1) throw new AppError('VALIDATION', '分页参数有误。')
    const rows = (read().standards || []).filter(visible).map(present).filter(row => fields.every(key => row[key].toLowerCase().includes(filters[key]!)) && row.category.toLowerCase().includes(category) && (!qualification || row.qualification === qualification) && (!departmentId || row.departmentIds.includes(departmentId)) && (!input.ownDepartment || row.departmentIds.includes(deps.actor().departmentId)) && (!selected || selected.includes(row.id))).sort((a, b) => a.code.localeCompare(b.code, 'zh-CN', { numeric: true }))
    const page = Math.min(Number(requested), Math.max(1, Math.ceil(rows.length / size)))
    return { items: all ? rows : rows.slice((page - 1) * size, page * size), total: rows.length, page, pageSize: size, ...options() }
  }
  function save(input: Record<string, unknown>) { actor(true); const previous = input.id === undefined ? undefined : detail(input.id); if (previous) { if (!canEditStandard(deps.actor(), previous)) throw new AppError('FORBIDDEN', '跨部门标准请由具有全部部门权限的管理员维护。');  }; const row: StandardRecord = { ...parse(input), ownerDepartmentId: previous?.ownerDepartmentId || previous?.departmentIds[0] || deps.actor().departmentId, groupIds: [...(previous?.groupIds || [])], id: previous?.id || randomUUID(), version: (previous?.version || 0) + 1 }; duplicate(row, read().standards || []); const state = structuredClone(read()), rows = state.standards ||= []; if (previous) rows[rows.findIndex(item => item.id === previous.id)] = row; else rows.push(row); deps.write!(state); return detail(row.id) }
  function remove(input: Record<string, unknown>) { actor(true); const row = detail(input.id); if (!canEditStandard(deps.actor(), row)) throw new AppError('FORBIDDEN', '跨部门标准请由具有全部部门权限的管理员维护。');  const state = structuredClone(read()); state.standards = state.standards!.filter(item => item.id !== row.id); deps.write!(state); return { id: row.id } }
  function context(value: unknown): EquipmentGroupContext { actor(true); const selected = ids(value, 'ids', 200); if (!selected.length) throw new AppError('VALIDATION', '请至少选择一条标准。'); const records = selected.map(detail); return { records: records.map(row => ({ id: row.id, version: row.version })), groups: groupOptions().map(group => { const count = records.filter(row => row.groupIds.includes(group.id)).length; return { ...group, state: count === records.length ? 'checked' : count ? 'mixed' : 'unchecked' } }) } }
  function associations(input: Record<string, unknown>) {
    actor(true)
    if (!Array.isArray(input.records) || !input.records.length || input.records.length > 200 || input.records.some(row => !row || typeof row !== 'object') || !Array.isArray(input.groups) || input.groups.length > 1000) throw new AppError('VALIDATION', '分组关联参数有误。')
    const records = input.records as { id: string; version: number }[], current = context(records.map(row => row.id)), state = structuredClone(read()), seen = new Set<string>()
    records.forEach(row => detail(row.id))
    const groups = input.groups.map(value => { if (!value || typeof value !== 'object') throw new AppError('VALIDATION', '分组关联参数有误。'); const item = value as { id: string; version: number; state: EquipmentGroupState }; if (seen.has(item.id) || !['checked', 'unchecked', 'mixed'].includes(item.state)) throw new AppError('VALIDATION', '分组关联参数有误。'); seen.add(item.id); const group = current.groups.find(row => row.id === item.id); if (!group) throw new AppError('NOT_FOUND', '标准分组不存在，请重新选择。'); return item })
    for (const reference of records) { const row = state.standards!.find(row => row.id === reference.id)!, next = new Set(row.groupIds); for (const group of groups) { if (group.state === 'checked') next.add(group.id); else if (group.state === 'unchecked') next.delete(group.id) } if (next.size !== row.groupIds.length || row.groupIds.some(id => !next.has(id))) { row.groupIds = [...next]; row.version++ } }
    deps.write!(state); return { count: records.length }
  }
  function importCsv(value: unknown) {
    actor(true); const [header, ...lines] = parsePersonnelCsv(value)
    if (!header || header.length !== standardColumns.length || header.some((cell, index) => cell.trim() !== standardColumns[index]!.label)) throw new AppError('VALIDATION', '模板列不匹配，请使用下载的导入模板。')
    if (!lines.length || lines.length > 1000) throw new AppError('VALIDATION', '每次请导入 1 至 1000 条记录。')
    const added: StandardRecord[] = [], choices = options()
    for (const [index, line] of lines.entries()) try {
      if (line.length !== header.length) throw new AppError('VALIDATION', '列数与模板不一致。')
      const raw = Object.fromEntries(standardColumns.map((field, i) => [field.key, line[i]!.trim()]))
      const resolve = (value: string, rows: { id: string; name: string }[], label: string) => value ? value.split(/[;；、]/).map(name => { const matches = rows.filter(row => row.name === name.trim()); if (matches.length !== 1) throw new AppError('VALIDATION', `${label}“${name}”不存在、重名或无权使用。`); return matches[0]!.id }) : []
      const boolean = (value: string) => { if (!['', '是', '否'].includes(value)) throw new AppError('VALIDATION', '是否字段须填写是或否。'); return value === '是' }
      const row: StandardRecord = { ...parse({ ...raw, departmentIds: resolve(raw.departments!, choices.departments, '使用部门'), quantity: raw.quantity ? Number(raw.quantity) : null, abolished: !!raw.abolishedAt, outsideScope: boolean(raw.outsideScope!), english: boolean(raw.english!) }), id: randomUUID(), version: 1, ownerDepartmentId: deps.actor().departmentId, groupIds: [] }
      duplicate(row, [...(read().standards || []), ...added]); added.push(row)
    } catch (issue) { if (issue instanceof AppError) throw new AppError(issue.code, `第 ${index + 2} 行：${issue.message}`); throw issue }
    const state = structuredClone(read()); (state.standards ||= []).push(...added); deps.write!(state); return { count: added.length }
  }
  return { query, detail, options, save, remove, context, associations, importCsv,
    template: () => { actor(); return registrationCsv([standardColumns.map(c => c.label)]) },
    export: (input: Record<string, unknown>) => registrationCsv([standardColumns.map(c => c.label), ...query(input, true).items.map(row => standardColumns.map(c => typeof row[c.key] === 'boolean' ? row[c.key] ? '是' : '否' : row[c.key] ?? ''))]),
  }
}
