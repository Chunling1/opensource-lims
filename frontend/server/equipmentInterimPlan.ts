import { randomUUID } from 'node:crypto'
import { AppError } from '../src/services/common/errors'
import type { RegistrationDependencies } from '../src/types/commissions/registration'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import { interimPlanColumns, type InterimPlanRecord, type InterimPlanRow } from '../src/types/quality/equipmentInterimPlan'
import { createEquipmentOverallPlans } from './equipmentOverallPlan'
import { registrationCsv } from './registrationDomain'
export function createEquipmentInterimPlans(deps: RegistrationDependencies) {
  const equipment = createEquipmentOverallPlans(deps)
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || !user.roles.some(role => (write ? ['admin', 'quality'] : ['admin', 'quality', 'reviewer', 'approver']).includes(role))) throw new AppError('FORBIDDEN', '无权执行设备期间核查计划操作。')
    return user
  }
  function row(plan: InterimPlanRecord): InterimPlanRow {
    const device = equipment.detail(plan.equipmentId)
    return { ...plan, code: device.code, name: device.name, status: device.status, model: device.model, accuracy: device.accuracy, range: device.range, department: registrationDepartments.find(item => item.id === plan.departmentId)?.name || '无' }
  }
  function detail(id: unknown) {
    actor()
    const plan = deps.read!()!.equipmentInterimPlans?.find(item => item.id === id)
    if (!plan) throw new AppError('NOT_FOUND', '期间核查计划不存在，请刷新列表。')
    return row(plan)
  }
  function equipmentChoices(input: Record<string, unknown>) {
    actor()
    // Reuse the plan search rules and permission scope, then enrich only this page.
    const result = equipment.query(input), state = deps.read!()!
    const devices = new Map((state.equipmentLedger || []).map(device => [device.id, device]))
    return { ...result, items: result.items.map(item => ({ ...devices.get(item.id)!, validity: state.equipmentProfiles?.[item.id]?.validity || '' })) }
  }
  function query(input: Record<string, unknown>, all = false) {
    actor()
    // Shared device search semantics; ids here refer to plans, not devices.
    const matched = new Set(equipment.query({ ...input, ids: undefined }, true).items.map(item => item.id))
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.length > 1000 || input.ids.some(id => typeof id !== 'string'))) throw new AppError('VALIDATION', '所选计划有误。')
    const ids = input.ids as string[] | undefined, size = Number(input.pageSize || 10)
    const items = (deps.read!()!.equipmentInterimPlans || []).filter(plan => matched.has(plan.equipmentId) && (!ids || ids.includes(plan.id))).map(row).sort((a, b) => b.year - a.year || a.code.localeCompare(b.code, 'zh-CN', { numeric: true }) || a.checkDate.localeCompare(b.checkDate))
    const page = Math.min(Number(input.page || 1), Math.max(1, Math.ceil(items.length / size)))
    return { items: all ? items : items.slice((page - 1) * size, page * size), total: items.length, page, pageSize: size }
  }
  function save(input: Record<string, unknown>) {
    const user = actor(true), previous = input.id === undefined ? undefined : detail(input.id)
    
    const device = equipment.detail(input.equipmentId)
    if (typeof input.year !== 'number' || !Number.isInteger(input.year) || input.year < 1000 || input.year > 9999) throw new AppError('VALIDATION', '请选择有效年度。', { fieldErrors: { ['year']: '请选择有效年度。' } })
    const department = registrationDepartments.find(item => item.id === input.departmentId)
    if (!department || user.scope !== 'all' && department.id !== user.departmentId) throw new AppError('VALIDATION', '请选择有权限的实施部门。', { fieldErrors: { ['departmentId']: '请选择有权限的实施部门。' } })
    const values: Record<string, string> = {}
    for (const key of ['testDate', 'checkDate', 'points', 'method', 'notes']) {
      if (typeof input[key] !== 'string' || input[key].length > 1000) throw new AppError('VALIDATION', '请检查表单内容，文本最多 1000 个字符。', { fieldErrors: { [key]: '请检查表单内容，文本最多 1000 个字符。' } })
      values[key] = input[key].trim()
    }
    for (const key of ['testDate', 'checkDate']) {
      const date = values[key]!
      if (date && (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date)) throw new AppError('VALIDATION', '请填写有效的日期。', { fieldErrors: { [key]: '请填写有效的日期。' } })
    }
    const saved: InterimPlanRecord = { id: previous?.id || randomUUID(), version: (previous?.version || 0) + 1, equipmentId: device.id, year: input.year, departmentId: department.id, testDate: values.testDate!, checkDate: values.checkDate!, points: values.points!, method: values.method!, notes: values.notes! }
    const state = structuredClone(deps.read!()!), plans = state.equipmentInterimPlans ||= []
    if (previous) plans[plans.findIndex(item => item.id === previous.id)] = saved
    else plans.push(saved)
    deps.write!(state)
    return row(saved)
  }
  function remove(input: Record<string, unknown>) {
    actor(true)
    const plan = detail(input.id)
    
    const state = structuredClone(deps.read!()!)
    state.equipmentInterimPlans = state.equipmentInterimPlans!.filter(item => item.id !== plan.id)
    deps.write!(state)
    return { id: plan.id }
  }
  return { query, detail, equipmentChoices, save, remove, export: (input: Record<string, unknown>) => registrationCsv([interimPlanColumns.map(column => column.label), ...query(input, true).items.map(item => interimPlanColumns.map(column => String(item[column.key])))]) }
}
