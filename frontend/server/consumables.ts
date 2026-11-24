import { randomUUID } from 'node:crypto'
import { AppError, problem } from '../src/services/common/errors'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import type { RegistrationDependencies, RegistrationState } from '../src/types/commissions/registration'
import { canManageConsumables, consumableColumns, consumableTotal, type ConsumableRecord } from '../src/types/quality/consumables'
import { registrationCsv } from './registrationDomain'
import { parsePersonnelCsv } from './personnel'

export function seedConsumables(state: RegistrationState, now = new Date()) {
  if (state.consumables) return
  state.consumables = ['一次性手套', '移液枪头', '滤纸', '样品瓶', '称量纸', '擦镜纸'].map((name, index) => {
    const department = registrationDepartments[index === 5 ? 1 : 0]!, unitPrice = [35, 28.5, 16, 3.2, 12, 8][index]!, quantity = (index + 1) * 10
    return { id: `consumable-${index + 1}`, name, specification: ['100 只/盒', '200 μL', '90 mm', '100 mL', '100 张/包', '50 张/本'][index]!, purchasedAt: now.toISOString().slice(0, 10), unitPrice, quantity, totalAmount: consumableTotal(unitPrice, quantity), departmentId: department.id, department: department.name, notes: '演示记录', version: 1 }
  })
}
export function createConsumables(deps: RegistrationDependencies) {
  const read = () => deps.read!()!
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || (write ? !canManageConsumables(user) : !user.roles.some(role => ['admin', 'quality', 'inventory', 'reviewer', 'approver'].includes(role)))) throw new AppError('FORBIDDEN', '无权执行易耗品操作。')
    return user
  }
  const visible = (row: ConsumableRecord) => deps.actor().scope === 'all' || row.departmentId === deps.actor().departmentId
  function text(value: unknown, key: string, label: string, max = 200) {
    if (typeof value !== 'string' || value.length > max) throw problem('VALIDATION', `${label}格式有误，最多 ${max} 个字符。`, key)
    return value.trim()
  }
  function numeric(value: unknown, key: string, label: string, precision: number) {
    if (value === null || value === undefined || value === '') return null
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1000000 || Math.abs(value * 10 ** precision - Math.round(value * 10 ** precision)) > 0.00001) throw problem('VALIDATION', `${label}须为 0 至 1000000 的数字，最多 ${precision} 位小数。`, key)
    return value
  }
  function parse(input: Record<string, unknown>) {
    const user = actor(true), name = text(input.name, 'name', '物质名称')
    if (!name) throw problem('VALIDATION', '请填写物质名称。', 'name')
    const purchasedAt = text(input.purchasedAt, 'purchasedAt', '购买日期', 10)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(purchasedAt) || !Number.isFinite(Date.parse(purchasedAt)) || new Date(purchasedAt).toISOString().slice(0, 10) !== purchasedAt) throw problem('VALIDATION', '请填写有效的购买日期。', 'purchasedAt')
    const department = registrationDepartments.find(dept => dept.id === input.departmentId)
    if (!department || user.scope !== 'all' && user.departmentId !== department.id) throw problem('VALIDATION', '请选择权限范围内的购置部门。', 'departmentId')
    const unitPrice = numeric(input.unitPrice, 'unitPrice', '单价', 2), quantity = numeric(input.quantity, 'quantity', '数量', 3)
    return { name, purchasedAt, specification: text(input.specification ?? '', 'specification', '规格型号'), notes: text(input.notes ?? '', 'notes', '备注', 2000), departmentId: department.id, department: department.name, unitPrice, quantity, totalAmount: consumableTotal(unitPrice, quantity) }
  }
  function detail(id: unknown) {
    actor(); const row = read().consumables?.find(row => row.id === id)
    if (!row || !visible(row)) throw new AppError('NOT_FOUND', '易耗品记录不存在或无权访问，请刷新列表。')
    return { ...row }
  }
  function query(input: Record<string, unknown>, all = false) {
    actor()
    const name = text(input.name ?? '', 'name', '物质名称').toLowerCase(), department = text(input.department ?? '', 'department', '购置部门').toLowerCase(), quantity = text(input.quantity ?? '', 'quantity', '数量')
    if (quantity && (!/^\d+(\.\d{1,3})?$/.test(quantity) || Number(quantity) > 1000000)) throw problem('VALIDATION', '数量查询须为有效的非负数字，最多 3 位小数。', 'quantity')
    const size = input.pageSize ?? 10, requested = input.page ?? 1
    if (typeof size !== 'number' || ![10, 20, 50].includes(size) || !Number.isSafeInteger(requested) || Number(requested) < 1) throw new AppError('VALIDATION', '分页参数有误。')
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.length > 1000 || input.ids.some(id => typeof id !== 'string' || !id) || new Set(input.ids).size !== input.ids.length)) throw new AppError('VALIDATION', '所选记录有误。')
    const rows = (read().consumables || []).filter(row => visible(row) && row.name.toLowerCase().includes(name) && row.department.toLowerCase().includes(department) && (!quantity || row.quantity === Number(quantity)) && (!input.ids || (input.ids as string[]).includes(row.id))).sort((a, b) => b.purchasedAt.localeCompare(a.purchasedAt) || a.id.localeCompare(b.id))
    const page = Math.min(Number(requested), Math.max(1, Math.ceil(rows.length / size)))
    return { items: (all ? rows : rows.slice((page - 1) * size, page * size)).map(row => ({ ...row })), total: rows.length, page, pageSize: size }
  }
  function save(input: Record<string, unknown>) {
    const draft = parse(input), previous = input.id === undefined ? undefined : detail(input.id)
    
    const state = structuredClone(read()), rows = state.consumables ||= [], row: ConsumableRecord = { ...draft, id: previous?.id || randomUUID(), version: (previous?.version || 0) + 1 }
    if (previous) rows[rows.findIndex(item => item.id === previous.id)] = row; else rows.push(row)
    deps.write!(state); return { ...row }
  }
  function remove(input: Record<string, unknown>) {
    actor(true); const row = detail(input.id)
    
    const state = structuredClone(read()); state.consumables = state.consumables!.filter(item => item.id !== row.id); deps.write!(state); return { id: row.id }
  }
  function importCsv(value: unknown) {
    actor(true); const [header, ...lines] = parsePersonnelCsv(value)
    if (!header || header.length !== consumableColumns.length || header.some((value, index) => value.trim() !== consumableColumns[index]!.label)) throw new AppError('VALIDATION', '模板列不匹配，请使用下载的导入模板。')
    if (!lines.length || lines.length > 1000) throw new AppError('VALIDATION', '每次请导入 1 至 1000 条易耗品记录。')
    const added = lines.map((values, index) => {
      try {
        if (values.length !== header.length) throw new AppError('VALIDATION', '列数与模板不一致。')
        const input = Object.fromEntries(consumableColumns.map((field, index) => [field.key, values[index]!.trim()]))
        const draft = parse({ ...input, departmentId: registrationDepartments.find(dept => dept.name === input.department)?.id, unitPrice: input.unitPrice ? Number(input.unitPrice) : null, quantity: input.quantity ? Number(input.quantity) : null })
        if (input.totalAmount && (draft.totalAmount === null || !/^\d+(\.\d{1,2})?$/.test(input.totalAmount) || Number(input.totalAmount) !== draft.totalAmount)) throw new AppError('VALIDATION', '总金额与单价 × 数量不一致，请留空自动计算或填写正确金额。')
        return { ...draft, id: randomUUID(), version: 1 }
      } catch (error) { if (error instanceof AppError) throw new AppError(error.code, `第 ${index + 2} 行：${error.message}`); throw error }
    })
    const state = structuredClone(read()); (state.consumables ||= []).push(...added); deps.write!(state); return { count: added.length }
  }
  return { query, detail, save, remove, importCsv,
    template: () => { actor(); return registrationCsv([consumableColumns.map(column => column.label)]) },
    export: (input: Record<string, unknown>) => registrationCsv([consumableColumns.map(column => column.label), ...query(input, true).items.map(row => consumableColumns.map(column => { const value = row[column.key]; return (column.key === 'unitPrice' || column.key === 'totalAmount') && typeof value === 'number' ? value.toFixed(2) : value ?? '' }))]),
  }
}
