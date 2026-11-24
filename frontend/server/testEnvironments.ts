import { randomUUID } from 'node:crypto'
import { AppError } from '../src/services/common/errors'
import type { RegistrationDependencies, RegistrationState } from '../src/types/commissions/registration'
import type { TestEnvironment, EnvironmentDetail } from '../src/types/quality/testEnvironments'
import { canManageDefinitions } from '../src/types/quality/equipmentGroups'
import { testPlans } from './samplePlans'
import { registrationCsv } from './registrationDomain'

export function seedTestEnvironments(state: RegistrationState) {
  state.testEnvironments ??= [
    { id: 'environment-1', name: '恒温恒湿试验室（示例）', departmentId: 'lab', planIds: ['thermal-1', 'general-1'], version: 1 },
    { id: 'environment-2', name: '通风试验室（示例）', departmentId: 'lab', planIds: ['ventilation-1'], version: 1 },
    { id: 'environment-3', name: '专项试验室（示例）', departmentId: 'lab2', planIds: ['branch-1'], version: 1 },
  ]
}
export function createTestEnvironments(deps: RegistrationDependencies) {
  const visible = (row: { departmentId: string }) => deps.actor().scope === 'all' || row.departmentId === deps.actor().departmentId
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || (write ? !canManageDefinitions(user) : !user.roles.some(role => ['admin', 'quality', 'reviewer', 'approver'].includes(role)))) throw new AppError('FORBIDDEN', '无权执行试验环境操作。')
    return user
  }
  function options() {
    actor()
    return testPlans.filter(visible).map(({ id, name, code }) => ({ id, name, code }))
  }
  function detail(id: unknown): EnvironmentDetail {
    actor()
    const row = deps.read!()!.testEnvironments?.find(item => item.id === id && visible(item))
    if (!row) throw new AppError('NOT_FOUND', '试验环境不存在或无权访问，请刷新列表。')
    // A scoped record may contain associations set by an administrator. Preserve their IDs
    // without exposing another department's plan metadata to the current user.
    const allowed = options()
    return { ...structuredClone(row), plans: row.planIds.map(id => allowed.find(plan => plan.id === id) || { id, name: '无权访问的检测方案', code: '—' }) }
  }
  function query(input: Record<string, unknown>, all = false) {
    actor()
    if (input.name !== undefined && (typeof input.name !== 'string' || input.name.length > 200)) throw new AppError('VALIDATION', '试验环境查询条件有误。')
    const pageSize = input.pageSize ?? 10, requested = input.page ?? 1
    if (typeof pageSize !== 'number' || ![10, 20, 50].includes(pageSize) || typeof requested !== 'number' || !Number.isSafeInteger(requested) || requested < 1) throw new AppError('VALIDATION', '分页参数有误。')
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.length > 1000 || input.ids.some(id => typeof id !== 'string'))) throw new AppError('VALIDATION', '试验环境选择有误。')
    const name = String(input.name || '').trim().toLocaleLowerCase(), ids = input.ids as string[] | undefined
    const items = (deps.read!()!.testEnvironments || []).filter(row => visible(row) && row.name.toLocaleLowerCase().includes(name) && (!ids || ids.includes(row.id)))
    const page = Math.min(requested, Math.max(1, Math.ceil(items.length / pageSize)))
    return { items: structuredClone(all ? items : items.slice((page - 1) * pageSize, page * pageSize)), total: items.length, page, pageSize }
  }
  function save(input: Record<string, unknown>) {
    const user = actor(true), previous = input.id === undefined ? undefined : detail(input.id)
    
    if (typeof input.name !== 'string' || !input.name.trim() || input.name.trim().length > 200) throw new AppError('VALIDATION', '请填写试验环境描述，最多 200 个字符。', { fieldErrors: { name: '请填写试验环境描述，最多 200 个字符。' } })
    if (!Array.isArray(input.planIds) || input.planIds.length > 500 || input.planIds.some(id => typeof id !== 'string') || new Set(input.planIds).size !== input.planIds.length) throw new AppError('VALIDATION', '检测方案选择有误。')
    const planIds = input.planIds as string[], allowed = options()
    // Existing hidden associations must be retained; a scoped user cannot add or remove them.
    const hidden = (previous?.planIds || []).filter(id => !allowed.some(plan => plan.id === id))
    if (hidden.some(id => !planIds.includes(id)) || planIds.some(id => !allowed.some(plan => plan.id === id) && !hidden.includes(id))) throw new AppError('FORBIDDEN', '检测方案不存在或不在权限范围内，请重新选择。')
    const name = input.name.trim(), departmentId = previous?.departmentId || user.departmentId
    const state = structuredClone(deps.read!()!), rows = state.testEnvironments ??= []
    if (rows.some(row => row.id !== previous?.id && row.departmentId === departmentId && row.name.toLocaleLowerCase() === name.toLocaleLowerCase())) throw new AppError('VALIDATION', '该部门已存在相同的试验环境。', { fieldErrors: { name: '该部门已存在相同的试验环境。' } })
    const saved: TestEnvironment = { id: previous?.id || randomUUID(), name, departmentId, planIds: [...planIds], version: (previous?.version || 0) + 1 }
    if (previous) rows[rows.findIndex(row => row.id === previous.id)] = saved
    else rows.push(saved)
    deps.write!(state)
    return detail(saved.id)
  }
  function remove(input: Record<string, unknown>) {
    actor(true)
    const row = detail(input.id)
    
    const state = structuredClone(deps.read!()!)
    state.testEnvironments = state.testEnvironments!.filter(item => item.id !== row.id)
    deps.write!(state)
    return { id: row.id }
  }
  return { query, detail, options, save, remove, export: (input: Record<string, unknown>) => registrationCsv([['试验环境'], ...query(input, true).items.map(row => [row.name])]) }
}
