import { AppError } from '../src/services/common/errors'
import type { RegistrationDependencies } from '../src/types/commissions/registration'
import type { EquipmentLedgerRow } from '../src/types/quality/equipmentLedger'
import { emptyOverallPlan, overallPlanFields, overallPlanSearchFields, overallPlanOperators, overallPlanColumns, type OverallPlanRow, type OverallPlanValues, type OverallPlanKey } from '../src/types/quality/equipmentOverallPlan'
import { registrationCsv } from './registrationDomain'
export function createEquipmentOverallPlans(deps: RegistrationDependencies) {
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || !user.roles.some(role => (write ? ['admin', 'quality'] : ['admin', 'quality', 'reviewer', 'approver']).includes(role))) throw new AppError('FORBIDDEN', '无权执行设备总体计划操作。')
    return user
  }
  const visible = (row: EquipmentLedgerRow) => deps.actor().scope === 'all' || row.departmentId === deps.actor().departmentId
  function row(device: EquipmentLedgerRow): OverallPlanRow {
    const plan = deps.read!()!.equipmentOverallPlans?.[device.id]
    return { id: device.id, code: device.code, name: device.name, status: device.status, model: device.model, accuracy: device.accuracy, range: device.range, equipmentVersion: device.version || 1, version: plan?.version || 0, ...emptyOverallPlan(), ...plan?.values }
  }
  function detail(id: unknown) {
    actor()
    const device = deps.read!()!.equipmentLedger?.find(item => item.id === id)
    if (!device || !visible(device)) throw new AppError('NOT_FOUND', '设备不存在或无权访问，请刷新列表。')
    return row(device)
  }
  function query(input: Record<string, unknown>, all = false) {
    actor()
    const field = input.field ?? 'code', operator = input.operator ?? 'contains', value = input.value ?? ''
    if (!overallPlanSearchFields.some(item => item.key === field) || !overallPlanOperators.some(item => item.key === operator) || typeof value !== 'string' || value.length > 200) throw new AppError('VALIDATION', '查询条件有误。')
    const requestedPage = input.page ?? 1, pageSize = input.pageSize ?? 10
    if (typeof requestedPage !== 'number' || !Number.isSafeInteger(requestedPage) || requestedPage < 1 || typeof pageSize !== 'number' || ![10, 20, 50].includes(pageSize)) throw new AppError('VALIDATION', '分页参数有误。')
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.length > 1000 || input.ids.some(id => typeof id !== 'string'))) throw new AppError('VALIDATION', '所选设备有误。')
    const ids = input.ids as string[] | undefined, search = value.trim().toLocaleLowerCase()
    const numeric = (text: string) => /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)
    const items = (deps.read!()!.equipmentLedger || []).filter(device => visible(device) && (!ids || ids.includes(device.id))).map(row).filter(item => {
      if (!search) return true
      const content = String(item[field as keyof OverallPlanRow]).trim().toLocaleLowerCase()
      if (operator === 'contains') return content.includes(search)
      if (operator === 'eq') return numeric(content) && numeric(search) ? Number(content) === Number(search) : content === search
      if (!content) return false
      // Explanatory values such as “以检定证书为准” are not numeric measurements.
      if (numeric(search) && !numeric(content)) return false
      const comparison = numeric(content) && numeric(search) ? Number(content) - Number(search) : content.localeCompare(search, 'zh-CN', { numeric: true })
      return operator === 'gt' ? comparison > 0 : operator === 'gte' ? comparison >= 0 : operator === 'lt' ? comparison < 0 : comparison <= 0
    }).sort((a, b) => a.code.localeCompare(b.code, 'zh-CN', { numeric: true }))
    const page = Math.min(requestedPage, Math.max(1, Math.ceil(items.length / pageSize)))
    return { items: all ? items : items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, pageSize }
  }
  function save(input: Record<string, unknown>) {
    actor(true)
    if (!Array.isArray(input.records) || !input.records.length || input.records.length > 200) throw new AppError('VALIDATION', '请选择 1 至 200 台设备。')
    if (!input.changes || typeof input.changes !== 'object' || Array.isArray(input.changes)) throw new AppError('VALIDATION', '请勾选需要修改的字段。')
    const changes = input.changes as Record<string, unknown>, keys = Object.keys(changes)
    if (!keys.length || keys.some(key => !overallPlanFields.some(field => field.key === key))) throw new AppError('VALIDATION', '修改字段有误。')
    const patch: Partial<OverallPlanValues> = {}
    for (const key of keys as OverallPlanKey[]) {
      const value = changes[key]
      if (typeof value !== 'string' || value.trim().length > 1000 || key === 'checkRequired' && !['', '是', '否'].includes(value.trim())) throw new AppError('VALIDATION', '请检查计划字段，文本最多 1000 个字符。', { fieldErrors: { [key]: '请检查计划字段，文本最多 1000 个字符。' } })
      patch[key] = value.trim()
    }
    const ids = new Set<string>()
    const records = input.records.map(value => {
      if (!value || typeof value !== 'object' || Array.isArray(value)) throw new AppError('VALIDATION', '所选设备有误。')
      const target = value as Record<string, unknown>, current = detail(target.id)
      if (ids.has(current.id)) throw new AppError('VALIDATION', '所选设备重复。')
      ids.add(current.id)
      
      return current
    })
    // Validate every device before applying the submitted fields atomically.
    const state = structuredClone(deps.read!()!), plans = state.equipmentOverallPlans ||= {}
    for (const record of records) plans[record.id] = { version: record.version + 1, values: { ...emptyOverallPlan(), ...plans[record.id]?.values, ...patch } }
    deps.write!(state)
    return { count: records.length }
  }
  return { query, detail, save, export: (input: Record<string, unknown>) => registrationCsv([overallPlanColumns.map(column => column.label), ...query(input, true).items.map(item => overallPlanColumns.map(column => item[column.key]))]) }
}
